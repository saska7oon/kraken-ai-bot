"""
Explainer Plugin
================

The AI's primary job in this bot is **explanation, not prediction**.

The operator does not know crypto trading. This plugin turns raw bot state into
plain language: what the bot is doing, what happened, what it means, and whether
anything needs attention. It is also the only place that talks to the operator
in prose.

Deliberate design constraints
-----------------------------
* **No price predictions, no trading advice.** Asking an LLM to forecast markets
  produces confident, unaccountable nonsense. The system prompt forbids it, and
  the deterministic summary path never offers an opinion at all.
* **Grounded in real data.** Every fact comes from the Freqtrade REST API. The
  model narrates numbers; it does not invent them.
* **Degrades gracefully.** If the AI is unavailable or its daily budget is spent,
  the plugin still produces a useful, deterministic plain-language summary. The
  bot never depends on the AI to function.
* **Low request volume.** One scheduled digest per day plus on-demand questions,
  instead of asking an LLM to re-derive what Python already computes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ai_orchestrator.core.freqtrade_api import FreqtradeAPIError, Trade
from ai_orchestrator.core.notifier import DiscordNotifier
from ai_orchestrator.core.openrouter_client import AIBudgetExhausted
from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)

# The model is asked to explain, never to advise.
SYSTEM_PROMPT = """You are explaining a crypto trading bot's behaviour to its owner.

The owner is intelligent but is NOT knowledgeable about crypto trading and does
NOT read code. Your job is to explain clearly and honestly what the bot is doing
and what the numbers mean.

ABSOLUTE RULES:
1. NEVER predict prices or market direction.
2. NEVER recommend buying, selling, or holding any asset.
3. NEVER suggest the owner switch to live trading.
4. Only state facts present in the DATA section. If something is not there, say
   you do not know - never invent a number.
5. Do not use jargon without explaining it in the same sentence.
6. Be honest about losses and about uncertainty. Do not be reassuring at the
   expense of being accurate.
7. If the bot is in dry-run (simulation), make clear that no real money is at
   stake. If it is live, make that unmistakable and prominent.

Write in plain English. Be concise: short paragraphs, no walls of text. Aim for
under 250 words unless asked a detailed question."""


class ExplainerPlugin(BasePlugin):
    """Turns bot state into plain-language explanation."""

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger
        self.notifier = DiscordNotifier()

        self.send_digest_to_discord = config.config.get("send_digest_to_discord", True)
        self.include_technical = config.config.get("include_technical_detail", False)

    async def initialize(self) -> bool:
        self.logger.info("Explainer plugin initialized")
        if not self.notifier.configured:
            self.logger.info(
                "Discord webhook not configured; digests will only be available "
                "through the API."
            )
        return True

    # ---------------------------------------------------------------- scheduled
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Scheduled run: build the digest and optionally push it to Discord."""
        digest = await self.build_digest()
        delivered = False
        if self.send_digest_to_discord:
            delivered = await self.notifier.send(digest["text"])

        await self.audit.log(
            plugin="explainer",
            action="daily_digest",
            user_initiated=False,
            input_data={"delivered_to_discord": delivered},
            output_data={"ai_used": digest.get("ai_used", False)},
            decision_reasoning="Scheduled plain-language status digest",
            risk_level="low",
        )
        return {"status": "ok", "delivered": delivered, "ai_used": digest.get("ai_used", False)}

    # -------------------------------------------------------------------- facts
    async def _collect_facts(self) -> Dict[str, Any]:
        """
        Gather everything the explanation may reference.

        Every field is best-effort: a partial picture is better than an
        exception, and the narrator is told when data is missing.
        """
        facts: Dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_complete": True,
        }

        try:
            status = await self.freqtrade.status()
            facts.update(
                {
                    "state": status.state,
                    "dry_run": status.dry_run,
                    "stake_currency": status.stake_currency,
                    "strategy": status.strategy,
                    "timeframe": status.timeframe,
                    "open_trades": status.open_trades_count,
                    "max_open_trades": status.max_open_trades,
                    "starting_balance": status.starting_balance,
                    "current_balance": status.current_balance,
                    "profit_total": status.profit_total,
                    "profit_pct": round(status.profit_pct, 3),
                }
            )
        except FreqtradeAPIError as e:
            facts["data_complete"] = False
            facts["status_error"] = str(e)
            self.logger.warning("Could not read bot status: %s", e)

        try:
            facts["whitelist"] = await self.freqtrade.get_whitelist()
        except FreqtradeAPIError:
            facts["whitelist"] = []

        try:
            open_trades = await self.freqtrade.get_open_trades()
            facts["open_trade_details"] = [
                {
                    "pair": t.pair,
                    "open_rate": t.open_rate,
                    "stake_amount": t.stake_amount,
                    "profit_ratio": t.profit_ratio,
                    "profit_abs": t.profit_abs,
                }
                for t in open_trades
            ]
        except FreqtradeAPIError:
            facts["open_trade_details"] = []

        try:
            closed = await self.freqtrade.get_closed_trades(limit=20)
            winners = [t for t in closed if (t.profit_abs or 0) > 0]
            losers = [t for t in closed if (t.profit_abs or 0) < 0]
            facts["recent_closed_trades"] = len(closed)
            facts["recent_winners"] = len(winners)
            facts["recent_losers"] = len(losers)
            facts["recent_best"] = _trade_brief(max(closed, key=lambda t: t.profit_abs or 0)) if closed else None
            facts["recent_worst"] = _trade_brief(min(closed, key=lambda t: t.profit_abs or 0)) if closed else None
        except FreqtradeAPIError:
            facts["recent_closed_trades"] = None

        # Protections and safety posture are the most important thing for a
        # novice to see, so report them explicitly rather than burying them.
        try:
            cfg = await self.freqtrade.get_config()
            facts["protections"] = cfg.get("protections", [])
            facts["stoploss"] = cfg.get("stoploss")
            facts["max_open_trades_config"] = cfg.get("max_open_trades")
        except FreqtradeAPIError:
            facts["protections"] = None

        autonomous = self.orchestrator.plugins.get("autonomous_agent")
        facts["autonomous_trading_enabled"] = bool(
            getattr(autonomous, "explicitly_enabled", False)
        )

        budget = self.openrouter.budget_status()
        facts["ai_requests_today"] = budget["requests_today"]
        facts["ai_requests_remaining"] = budget["remaining"]

        return facts

    # ------------------------------------------------------------------- digest
    async def build_digest(self) -> Dict[str, Any]:
        """Plain-language status summary, with or without the AI."""
        facts = await self._collect_facts()

        deterministic = _deterministic_digest(facts)

        if not self.openrouter.api_key:
            return {
                "text": deterministic,
                "ai_used": False,
                "reason": "No OpenRouter API key configured.",
                "facts": facts,
            }

        try:
            narrative = await self._narrate(
                "Write a short status update for the bot owner. Cover: whether the "
                "bot is running and whether it is in simulation or using real money; "
                "the wallet and overall profit or loss; any open trades; what the "
                "recent trades did; and anything that needs the owner's attention "
                "(for example missing safety protections). If there is nothing "
                "unusual, say so plainly.",
                facts,
            )
        except AIBudgetExhausted as e:
            return {
                "text": deterministic,
                "ai_used": False,
                "reason": str(e),
                "facts": facts,
            }
        except Exception as e:
            self.logger.info("AI narration unavailable (%s); using deterministic digest", e)
            return {
                "text": deterministic,
                "ai_used": False,
                "reason": f"AI unavailable: {e}",
                "facts": facts,
            }

        return {"text": narrative, "ai_used": True, "facts": facts}

    async def answer_question(self, question: str) -> Dict[str, Any]:
        """Answer a plain-language question grounded in real bot data."""
        question = (question or "").strip()
        if not question:
            return {"answer": "Ask me something about the bot, for example: 'how am I doing?'.", "ai_used": False}

        facts = await self._collect_facts()

        await self.audit.log(
            plugin="explainer",
            action="question_asked",
            user_initiated=True,
            input_data={"question": question},
            output_data={"facts_keys": sorted(facts)},
            decision_reasoning="Operator asked a question about bot behaviour",
            risk_level="low",
        )

        try:
            answer = await self._narrate(question, facts)
            return {"answer": answer, "ai_used": True, "facts": facts}
        except AIBudgetExhausted as e:
            return {
                "answer": (
                    f"I have used my daily AI allowance, so I cannot answer in prose "
                    f"right now ({e}). Here is the raw summary instead:\n\n"
                    f"{_deterministic_digest(facts)}"
                ),
                "ai_used": False,
                "facts": facts,
            }
        except Exception as e:
            self.logger.info("AI unavailable for question (%s)", e)
            return {
                "answer": (
                    "The AI is unavailable right now, so I cannot answer that in "
                    f"prose. Here is what I can tell you from the data:\n\n"
                    f"{_deterministic_digest(facts)}"
                ),
                "ai_used": False,
                "facts": facts,
            }

    async def explain_trade(self, trade: Trade) -> Dict[str, Any]:
        """Explain why a specific trade ended the way it did."""
        facts = {
            "pair": trade.pair,
            "opened_at": trade.open_date.isoformat() if trade.open_date else None,
            "closed_at": trade.close_date.isoformat() if trade.close_date else None,
            "open_rate": trade.open_rate,
            "close_rate": trade.close_rate,
            "stake_amount": trade.stake_amount,
            "profit_abs": trade.profit_abs,
            "profit_ratio": trade.profit_ratio,
            "exit_reason": trade.exit_reason,
            "enter_tag": trade.enter_tag,
        }

        fallback = _deterministic_trade_explanation(facts)
        try:
            text = await self._narrate(
                "Explain to the owner why this trade closed and what the result means. "
                "Describe the exit reason in plain language. Do not predict future "
                "prices.",
                facts,
            )
            return {"explanation": text, "ai_used": True, "trade": facts}
        except Exception as e:
            # Budget exhaustion and network failures are both expected states.
            self.logger.info("AI unavailable for trade explanation (%s)", e)
            return {"explanation": fallback, "ai_used": False, "trade": facts}

    # ---------------------------------------------------------------- narration
    async def _narrate(self, instruction: str, facts: Dict[str, Any]) -> str:
        """Ask the model to narrate the supplied facts."""
        import json

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"DATA (authoritative - do not contradict or extend it):\n"
                    f"{json.dumps(facts, indent=2, default=str)}\n\n"
                    f"TASK:\n{instruction}"
                ),
            },
        ]

        response = await self.openrouter.chat_completion(
            messages=messages, max_tokens=1024, temperature=0.3
        )
        return response.choices[0]["message"]["content"].strip()

    async def shutdown(self) -> None:
        await self.notifier.close()
        self.logger.info("Explainer plugin shut down")


# =============================================================================
# DETERMINISTIC FALLBACKS
#
# These run without any AI at all. The bot must be explainable even when the
# model is unreachable or its budget is spent.
# =============================================================================
def _money(value: Any, currency: str = "CAD") -> str:
    try:
        return f"{float(value):,.2f} {currency}"
    except (TypeError, ValueError):
        return "unknown"


def _trade_brief(trade: Trade) -> Optional[Dict[str, Any]]:
    if trade is None:
        return None
    return {
        "pair": trade.pair,
        "profit_abs": trade.profit_abs,
        "profit_ratio": trade.profit_ratio,
        "exit_reason": trade.exit_reason,
    }


def _deterministic_digest(facts: Dict[str, Any]) -> str:
    """Build a factual, jargon-free status summary with no AI involved."""
    currency = facts.get("stake_currency") or "CAD"
    lines: List[str] = ["Bot status", "=========="]

    if facts.get("status_error"):
        lines.append(
            "I could not reach the trading bot to read its status, so this summary "
            "is incomplete."
        )
        return "\n".join(lines)

    dry_run = facts.get("dry_run")
    if dry_run is True:
        lines.append(
            "Mode: SIMULATION (dry run). No real money is being used - trades are "
            "pretend, using a virtual wallet."
        )
    elif dry_run is False:
        lines.append(
            "Mode: LIVE. The bot is placing REAL orders with REAL money."
        )
    else:
        lines.append("Mode: unknown.")

    lines.append(f"Bot running: {'yes' if facts.get('state') == 'running' else 'no'}")
    lines.append(
        f"Wallet: {_money(facts.get('current_balance'), currency)} "
        f"(started at {_money(facts.get('starting_balance'), currency)})"
    )

    profit = facts.get("profit_total")
    if profit is not None:
        direction = "up" if float(profit) >= 0 else "down"
        lines.append(
            f"Overall result: {direction} {_money(abs(float(profit)), currency)} "
            f"({facts.get('profit_pct')}%)"
        )

    lines.append(
        f"Open trades: {facts.get('open_trades', 0)} of a maximum of "
        f"{facts.get('max_open_trades', 0)}"
    )

    for t in facts.get("open_trade_details") or []:
        ratio = t.get("profit_ratio")
        pct = f"{float(ratio) * 100:.2f}%" if ratio is not None else "unknown"
        lines.append(f"  - {t.get('pair')}: currently {pct}")

    if facts.get("recent_closed_trades"):
        lines.append(
            f"Recent closed trades: {facts['recent_closed_trades']} "
            f"({facts.get('recent_winners', 0)} made money, "
            f"{facts.get('recent_losers', 0)} lost money)"
        )
        worst = facts.get("recent_worst")
        if worst:
            lines.append(
                f"  Worst recent trade: {worst['pair']} "
                f"{_money(worst.get('profit_abs'), currency)}"
            )
    else:
        lines.append("No trades have closed yet.")

    # Safety section: the most important part for a non-expert operator.
    lines.append("")
    lines.append("Safety")
    lines.append("------")
    protections = facts.get("protections")
    if protections:
        lines.append(f"Protections active: {len(protections)}")
    elif protections == []:
        lines.append(
            "WARNING: no trade protections are configured. Nothing would "
            "automatically halt trading if losses pile up."
        )
    else:
        lines.append("Protections: could not be read.")

    stoploss = facts.get("stoploss")
    if stoploss is not None:
        lines.append(
            f"Stop loss: {abs(float(stoploss)) * 100:.1f}% - the most a single trade "
            f"can lose before the bot closes it."
        )

    if facts.get("autonomous_trading_enabled"):
        lines.append(
            "WARNING: autonomous AI trading is ENABLED. The AI can place trades "
            "without asking you first."
        )
    else:
        lines.append("Autonomous AI trading: off (the AI only suggests, never trades).")

    return "\n".join(lines)


def _deterministic_trade_explanation(facts: Dict[str, Any]) -> str:
    """Explain a closed trade without the AI."""
    profit = facts.get("profit_abs")
    currency = "CAD"
    try:
        profit_f = float(profit)
    except (TypeError, ValueError):
        profit_f = None

    if profit_f is None:
        outcome = "The result of this trade is not available."
    elif profit_f > 0:
        outcome = f"It made a profit of {_money(profit_f, currency)}."
    elif profit_f < 0:
        outcome = f"It made a loss of {_money(abs(profit_f), currency)}."
    else:
        outcome = "It broke even."

    reason = facts.get("exit_reason")
    reason_text = {
        "roi": "the trade reached the profit target the strategy was aiming for",
        "stop_loss": "the price fell to the stop loss, which is the safety limit that caps losses",
        "trailing_stop_loss": "the price rose, then fell back, so the bot locked in the gain it had",
        "exit_signal": "the strategy's sell conditions were met",
        "force_exit": "it was closed manually",
        "emergency_exit": "an emergency exit was triggered",
    }.get(str(reason), f"the exit reason recorded was '{reason}'")

    return (
        f"{facts.get('pair')}: opened at {facts.get('open_rate')} and closed at "
        f"{facts.get('close_rate')}. {outcome} "
        f"The bot closed it because {reason_text}."
    )
