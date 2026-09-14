"""
Natural Language Configuration Plugin
=====================================

Translates plain-language commands into either:

1. **Runtime actions** that Freqtrade genuinely supports over its REST API -
   pause, resume, pair restriction, status queries. These are executed for real.

2. **Configuration proposals** - everything else (stoploss, margin of capital at
   risk, profit targets, max open trades, strategy choice). Freqtrade reads its
   configuration at startup and has **no** runtime config-write endpoint, and
   this process cannot write the Swarm config either. A proposal is therefore
   recorded, explained, audited, and handed back with the exact values to apply
   by updating the Swarm config and redeploying.

Why this file was rewritten
---------------------------
The previous version POSTed to ``/api/v1/config`` (which does not exist) and
reported ``"status": "success"`` for every change. It also POSTed to
``/api/v1/whitelist/add`` and ``/whitelist/remove`` (also nonexistent) and
called ``/api/v1/resume`` (nonexistent). Every "applied" change was a lie: the
errors were caught by a broad ``except`` and returned as failed results that
nothing surfaced.

It also allowed ``dry_run`` to be treated as an ordinary config value. Switching
a bot from simulation to real money is not an ordinary config change, and for a
non-expert operator it is the single most dangerous action available.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ai_orchestrator.core.freqtrade_api import FreqtradeAPIError, UnsupportedOperation
from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY BOUNDS AND FROZEN KEYS
# =============================================================================
# Keys that may never be proposed, let alone changed, through this interface.
# Switching to live trading must be a deliberate, out-of-band act.
FROZEN_KEYS: Dict[str, str] = {
    "dry_run": (
        "Switching between simulation and live trading cannot be done through the AI "
        "interface. This is deliberate: live mode places real orders with real money. "
        "To go live you must edit the 'freqtrade_canada_config' Swarm config in "
        "Portainer, change dry_run to false, and redeploy - and you should have weeks "
        "of satisfactory dry-run results first."
    ),
    "exchange": "Exchange credentials are managed as Swarm secrets only.",
    "exchange.key": "Exchange credentials are managed as Swarm secrets only.",
    "exchange.secret": "Exchange credentials are managed as Swarm secrets only.",
    "api_server": "API server credentials are managed as Swarm secrets only.",
    "jwt_secret_key": "Secret material; managed as Swarm secrets only.",
    "ws_token": "Secret material; managed as Swarm secrets only.",
}

# Hard bounds. Anything outside these is refused regardless of what was asked.
BOUNDS: Dict[str, Dict[str, Any]] = {
    "stoploss": {
        "min": -0.15,
        "max": -0.02,
        "explain": (
            "The stop loss is how much a single trade can lose before it is closed "
            "automatically. -8% is the moderate default; the loosest permitted is -15%."
        ),
    },
    "max_open_trades": {
        "min": 1,
        "max": 5,
        "explain": (
            "How many trades can be open at the same time. More trades means more of "
            "your money is in the market at once."
        ),
    },
    "tradable_balance_ratio": {
        "min": 0.10,
        "max": 0.95,
        "explain": (
            "The share of your wallet the bot is allowed to use. 0.90 means 90%, "
            "keeping 10% back."
        ),
    },
    "trailing_stop_positive": {
        "min": 0.005,
        "max": 0.10,
        "explain": (
            "Once a trade is in profit by this much, the bot follows the price up and "
            "closes if it falls back."
        ),
    },
    "amount_reserve_percent": {"min": 0.0, "max": 0.20, "explain": "Fee/slippage buffer."},
}

# Intents that are executed for real over the REST API.
RUNTIME_ACTIONS = {"pause_resume", "show_status", "explain_trade", "restrict_pairs"}
# Intents that only ever produce a proposal.
PROPOSAL_INTENTS = {"change_risk", "change_stoploss", "change_position_size", "change_strategy"}


@dataclass
class NLCommand:
    """Parsed natural language command."""

    intent: str
    parameters: Dict[str, Any]
    confidence: float
    original_text: str
    requires_approval: bool = True


class NLConfigPlugin(BasePlugin):
    """
    Natural language to configuration translator.

    Commands such as "make it more conservative", "pause trading",
    "why did it sell ETH?".
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        self.auto_apply_safe = config.config.get("auto_apply_safe", False)
        self.require_approval_for = config.config.get(
            "require_approval_for",
            ["change_risk", "whitelist_change", "strategy_change", "stoploss_change"],
        )

        self.intent_patterns = {
            "change_risk": [
                r"(more|less|higher|lower|increase|decrease).*(risk|aggressive|conservative)",
                r"(conservative|moderate|aggressive)\s*mode",
            ],
            "restrict_pairs": [
                r"(add|remove|include|exclude).*(pair|whitelist|coin|token)",
                r"whitelist.*(add|remove)",
            ],
            "change_stoploss": [
                r"(tighten|loosen|widen|change).*(stoploss|stop.loss|stop)",
            ],
            "change_position_size": [
                r"(increase|decrease|change).*(position|stake|size|amount)",
            ],
            "pause_resume": [
                r"(pause|stop|halt|resume|start|continue)\s*(trading|bot)?",
            ],
            "change_strategy": [
                r"(switch|change|use).*(strategy|approach|method)",
            ],
            "show_status": [
                r"(show|display|get|what).*(status|performance|trades|profit|balance)",
            ],
            "explain_trade": [
                r"(why|explain|reason).*(bought|sold|trade|entry|exit)",
            ],
        }

    async def initialize(self) -> bool:
        self.logger.info("Natural language config plugin initialized")
        if self.auto_apply_safe:
            self.logger.warning(
                "auto_apply_safe is set, but config changes are never applied "
                "automatically by this plugin - only runtime actions can execute."
            )
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Event-driven plugin; can also be invoked manually with a command."""
        command = kwargs.get("command")
        if command:
            return await self.process_command(command)
        return {"status": "idle", "message": "NL config plugin ready for commands"}

    # ------------------------------------------------------------------ command
    async def process_command(self, text: str, user_id: str = "operator") -> Dict[str, Any]:
        """Interpret a command and either execute it or return a proposal."""
        self.logger.info("Processing command: %s", text)

        parsed = await self._parse_intent(text)
        if not parsed or parsed.confidence < 0.5:
            return {
                "status": "unclear",
                "message": (
                    "I could not understand that. Try something like: "
                    "'show my status', 'pause trading', or 'make it more conservative'."
                ),
                "suggestions": self._get_suggestions(),
            }

        changes = await self._generate_changes(parsed)
        if not changes:
            return {
                "status": "no_action",
                "intent": parsed.intent,
                "message": (
                    "I understood the request but it does not map to something I can "
                    "change. Nothing was modified."
                ),
            }

        # Refuse frozen keys outright, before anything is proposed.
        blocked = [c for c in changes if c.get("frozen")]
        if blocked:
            await self._audit_blocked(parsed, blocked, user_id)
            return {
                "status": "refused",
                "intent": parsed.intent,
                "message": " ".join(c["frozen_reason"] for c in blocked),
            }

        requires_approval = self._requires_approval(parsed, changes)

        await self.audit.log(
            plugin="nl_config",
            action="command_received",
            user_initiated=True,
            input_data={"command": text, "user": user_id},
            output_data={
                "intent": parsed.intent,
                "parameters": parsed.parameters,
                "confidence": parsed.confidence,
                "changes": changes,
                "requires_approval": requires_approval,
            },
            decision_reasoning=f"Parsed intent: {parsed.intent} (confidence {parsed.confidence:.0%})",
            risk_level="high" if requires_approval else "low",
            approved_by=user_id if not requires_approval else None,
        )

        if requires_approval:
            return {
                "status": "pending_approval",
                "intent": parsed.intent,
                "confidence": parsed.confidence,
                "proposed_changes": changes,
                "message": self._format_changes_message(parsed, changes),
                "approval_required": True,
            }

        result = await self._apply_changes(changes)
        return {
            "status": "applied",
            "intent": parsed.intent,
            "changes": changes,
            "result": result,
        }

    # ------------------------------------------------------------------- intent
    async def _parse_intent(self, text: str) -> Optional[NLCommand]:
        prompt = f"""Parse this trading bot command into a structured intent.

COMMAND: "{text}"

CONTEXT:
- Bot: Freqtrade on Kraken Canada (CAD markets)
- Pairs: BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD
- Current: dry-run (simulation), 1000 CAD, moderate risk
- Strategy: ModerateMultiPairStrategy

AVAILABLE INTENTS:
1. change_risk - Adjust risk level (conservative/moderate/aggressive)
2. restrict_pairs - Restrict which pairs are traded
3. change_stoploss - Adjust stoploss percentage
4. change_position_size - Adjust stake amount / max open trades
5. pause_resume - Pause or resume trading
6. change_strategy - Switch strategy
7. show_status - Show bot status/performance
8. explain_trade - Explain a specific trade decision
9. optimize_params - Trigger parameter optimization
10. generate_strategy - Request new strategy generation
11. market_analysis - Request market analysis

Return JSON with: intent, parameters, confidence (0-1), original_text.

Examples:
"make it more conservative" -> {{"intent": "change_risk", "parameters": {{"risk_level": "conservative"}}, "confidence": 0.9}}
"why did it sell ETH?" -> {{"intent": "explain_trade", "parameters": {{"pair": "ETH/CAD", "side": "sell"}}, "confidence": 0.9}}"""

        messages = [
            {
                "role": "system",
                "content": "You are a trading bot command parser. Extract intent and parameters accurately.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0]["message"]["content"]
            result = json.loads(content)
            return NLCommand(
                intent=result.get("intent", "unknown"),
                parameters=result.get("parameters", {}) or {},
                confidence=float(result.get("confidence", 0.0) or 0.0),
                original_text=text,
            )
        except Exception as e:
            # AI unavailable or budget exhausted is a normal state, not an error.
            self.logger.info("LLM parsing unavailable (%s); using pattern fallback", e)
            return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> Optional[NLCommand]:
        """Deterministic pattern-based parsing, used when the AI is unavailable."""
        text_lower = text.lower()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if not re.search(pattern, text_lower):
                    continue

                params: Dict[str, Any] = {}
                if intent == "change_risk":
                    for level in ("conservative", "moderate", "aggressive"):
                        if level in text_lower:
                            params["risk_level"] = level
                            break
                elif intent == "restrict_pairs":
                    params["action"] = "add" if any(
                        w in text_lower for w in ("add", "include")
                    ) else "remove"
                    pairs = re.findall(r"([A-Z]{2,5}/CAD)", text.upper())
                    if pairs:
                        params["pairs"] = pairs
                elif intent == "pause_resume":
                    params["action"] = "pause" if any(
                        w in text_lower for w in ("pause", "stop", "halt")
                    ) else "resume"

                return NLCommand(
                    intent=intent, parameters=params, confidence=0.7, original_text=text
                )

        return None

    # ------------------------------------------------------------------ changes
    async def _generate_changes(self, parsed: NLCommand) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []

        if parsed.intent == "change_risk":
            risk_level = str(parsed.parameters.get("risk_level", "moderate")).lower()
            changes.extend(self._get_risk_config(risk_level))

        elif parsed.intent == "restrict_pairs":
            action = parsed.parameters.get("action", "add")
            pairs = parsed.parameters.get("pairs", []) or []
            if pairs:
                changes.append(
                    {
                        "type": "runtime_pairs",
                        "action": "restrict",
                        "pairs": pairs,
                        "description": (
                            f"Restrict trading to {', '.join(pairs)} "
                            f"(runtime only; {action} requested)"
                        ),
                        "plain_language": (
                            "This changes which coins the bot is allowed to trade right "
                            "now. It does not survive a restart - to make it permanent, "
                            "update the pair list in the Swarm config."
                        ),
                    }
                )

        elif parsed.intent == "change_stoploss":
            value = parsed.parameters.get("value") or parsed.parameters.get("stoploss")
            if value is not None:
                changes.append(
                    self._config_change(
                        "stoploss",
                        value,
                        f"Set the stop loss to {abs(float(value)) * 100:.1f}%",
                    )
                )
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": (
                            "A stop loss change needs a specific percentage, e.g. "
                            "'set the stop loss to 6 percent'."
                        ),
                    }
                )

        elif parsed.intent == "change_position_size":
            if "max_open_trades" in parsed.parameters:
                changes.append(
                    self._config_change(
                        "max_open_trades",
                        parsed.parameters["max_open_trades"],
                        "Change how many trades can be open at once",
                    )
                )
            elif "tradable_balance_ratio" in parsed.parameters:
                changes.append(
                    self._config_change(
                        "tradable_balance_ratio",
                        parsed.parameters["tradable_balance_ratio"],
                        "Change how much of the wallet the bot may use",
                    )
                )
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": (
                            "Specify either how many simultaneous trades you want, or "
                            "what share of your wallet the bot may use."
                        ),
                    }
                )

        elif parsed.intent == "pause_resume":
            action = parsed.parameters.get("action", "pause")
            changes.append(
                {
                    "type": "bot_control",
                    "action": action,
                    "description": (
                        "Pause trading (open trades are still managed)"
                        if action == "pause"
                        else "Resume taking new trades"
                    ),
                    "plain_language": (
                        "Pausing stops the bot opening NEW trades. It keeps managing "
                        "anything already open, so your positions are not abandoned."
                        if action == "pause"
                        else "The bot will start looking for new trades again."
                    ),
                }
            )

        elif parsed.intent == "change_strategy":
            strategy = parsed.parameters.get("strategy") or parsed.parameters.get("strategy_name")
            if strategy:
                changes.append(
                    {
                        "type": "proposal_only",
                        "key": "strategy",
                        "value": strategy,
                        "description": f"Switch strategy to {strategy}",
                        "plain_language": (
                            "The strategy decides when to buy and sell. Changing it "
                            "changes the bot's entire behaviour, so this needs a "
                            "backtest before it is worth considering."
                        ),
                    }
                )
            else:
                changes.append(
                    {
                        "type": "clarification",
                        "description": "Name the strategy you want to switch to.",
                    }
                )

        elif parsed.intent == "show_status":
            changes.append({"type": "query", "action": "status", "description": "Show current status"})

        elif parsed.intent == "explain_trade":
            changes.append(
                {
                    "type": "query",
                    "action": "explain_trade",
                    "pair": parsed.parameters.get("pair"),
                    "side": parsed.parameters.get("side"),
                    "description": "Explain a trade decision",
                }
            )

        elif parsed.intent in ("optimize_params", "generate_strategy", "market_analysis"):
            plugin = {
                "optimize_params": "param_optimizer",
                "generate_strategy": "strategy_generator",
                "market_analysis": "market_analyst",
            }[parsed.intent]
            changes.append(
                {
                    "type": "trigger",
                    "action": plugin,
                    "description": f"Run the {plugin} plugin now",
                }
            )

        # Reject any attempt to touch a frozen key.
        for change in changes:
            key = change.get("key")
            if key and self._is_frozen(key):
                change["frozen"] = True
                change["frozen_reason"] = self._frozen_reason(key)

        return changes

    # ------------------------------------------------------------- change helpers
    def _is_frozen(self, key: str) -> bool:
        if key in FROZEN_KEYS:
            return True
        return any(key.startswith(f"{root}.") for root in FROZEN_KEYS)

    def _frozen_reason(self, key: str) -> str:
        for candidate in (key, key.split(".")[0]):
            if candidate in FROZEN_KEYS:
                return FROZEN_KEYS[candidate]
        return f"Changing '{key}' is not permitted through this interface."

    def _config_change(self, key: str, value: Any, description: str) -> Dict[str, Any]:
        """Build a config proposal, validated against BOUNDS."""
        change: Dict[str, Any] = {
            "type": "proposal_only",
            "key": key,
            "value": value,
            "description": description,
            "applies_via": "config_redeploy",
            "plain_language": "",
        }

        bounds = BOUNDS.get(key)
        if bounds:
            change["plain_language"] = bounds["explain"]
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                change["invalid"] = True
                change["reason"] = f"'{value}' is not a number."
                return change

            if numeric < bounds["min"] or numeric > bounds["max"]:
                change["invalid"] = True
                change["reason"] = (
                    f"{key} must be between {bounds['min']} and {bounds['max']}. "
                    f"You asked for {numeric}."
                )
        return change

    def _get_risk_config(self, risk_level: str) -> List[Dict[str, Any]]:
        """
        Map a risk profile to a set of proposals.

        All values stay inside BOUNDS; the 'aggressive' profile is flagged so the
        operator has to think about it explicitly.
        """
        profiles: Dict[str, List[Dict[str, Any]]] = {
            "conservative": [
                {"key": "max_open_trades", "value": 2, "description": "At most 2 trades at once"},
                {"key": "stoploss", "value": -0.05, "description": "Stop loss of 5%"},
                {"key": "trailing_stop_positive", "value": 0.015, "description": "Follow profit from 1.5%"},
                {"key": "tradable_balance_ratio", "value": 0.80, "description": "Use at most 80% of the wallet"},
            ],
            "moderate": [
                {"key": "max_open_trades", "value": 3, "description": "At most 3 trades at once"},
                {"key": "stoploss", "value": -0.08, "description": "Stop loss of 8%"},
                {"key": "trailing_stop_positive", "value": 0.02, "description": "Follow profit from 2%"},
                {"key": "tradable_balance_ratio", "value": 0.90, "description": "Use at most 90% of the wallet"},
            ],
            "aggressive": [
                {"key": "max_open_trades", "value": 4, "description": "At most 4 trades at once"},
                {"key": "stoploss", "value": -0.12, "description": "Stop loss of 12%"},
                {"key": "trailing_stop_positive", "value": 0.03, "description": "Follow profit from 3%"},
                {"key": "tradable_balance_ratio", "value": 0.95, "description": "Use up to 95% of the wallet"},
            ],
        }

        profile = profiles.get(risk_level)
        if profile is None:
            return [
                {
                    "type": "clarification",
                    "description": (
                        "Choose one of: conservative, moderate or aggressive."
                    ),
                }
            ]

        changes = [
            self._config_change(item["key"], item["value"], item["description"])
            for item in profile
        ]

        if risk_level == "aggressive":
            changes.append(
                {
                    "type": "note",
                    "description": "Higher risk",
                    "plain_language": (
                        "The aggressive profile allows larger losses on a single trade "
                        "(12%) and keeps less of your wallet in reserve. It can lose "
                        "money faster than the moderate profile."
                    ),
                }
            )
        return changes

    def _requires_approval(self, parsed: NLCommand, changes: List[Dict]) -> bool:
        """Queries run immediately; anything that alters behaviour needs approval."""
        if not changes:
            return False
        if all(c["type"] == "clarification" for c in changes):
            return False
        if all(c["type"] == "query" for c in changes):
            return False
        return True

    def _format_changes_message(self, parsed: NLCommand, changes: List[Dict]) -> str:
        lines = [
            f'Command understood as: {parsed.intent} (confidence {parsed.confidence:.0%})',
            "",
            "Requested changes:",
        ]
        for change in changes:
            marker = "  - "
            if change.get("invalid"):
                lines.append(f"{marker}REFUSED: {change['description']} - {change['reason']}")
                continue
            lines.append(f"{marker}{change.get('description', change.get('type'))}")
            if change.get("plain_language"):
                lines.append(f"      What this means: {change['plain_language']}")

        if any(c.get("applies_via") == "config_redeploy" for c in changes):
            lines += [
                "",
                "IMPORTANT: Freqtrade cannot change these settings while running.",
                "Approving records your decision and gives you the exact values to put",
                "into the 'freqtrade_canada_config' Swarm config, then redeploy.",
                "Nothing changes until you do that.",
            ]
        return "\n".join(lines)

    def _get_suggestions(self) -> List[str]:
        return [
            "show my status",
            "pause trading",
            "make it more conservative",
            "why did my last trade close?",
        ]

    # ------------------------------------------------------------------- apply
    async def _apply_changes(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute changes.

        Runtime actions run for real. Config proposals are NOT applied - they are
        returned as instructions, because nothing in this system can change the
        bot's configuration while it is running.
        """
        executed: List[Dict[str, Any]] = []
        proposals: List[Dict[str, Any]] = []

        for change in changes:
            kind = change.get("type")

            if kind == "proposal_only":
                if change.get("invalid"):
                    executed.append(
                        {"change": change, "status": "refused", "reason": change.get("reason")}
                    )
                    continue
                proposals.append(
                    {
                        "key": change["key"],
                        "value": change["value"],
                        "description": change.get("description"),
                    }
                )
                continue

            if kind == "note" or kind == "clarification":
                continue

            if kind == "query":
                executed.append(await self._handle_query(change))
                continue

            if kind == "trigger":
                try:
                    result = await self.orchestrator.run_plugin_now(change["action"])
                    executed.append(
                        {"change": change, "status": "triggered", "result": result}
                    )
                except Exception as e:
                    executed.append({"change": change, "status": "failed", "error": str(e)})
                continue

            if kind == "bot_control":
                executed.append(await self._handle_bot_control(change))
                continue

            if kind == "runtime_pairs":
                executed.append(await self._handle_restrict_pairs(change))
                continue

            executed.append(
                {"change": change, "status": "unsupported", "reason": f"Unknown change type '{kind}'"}
            )

        return {
            "executed": executed,
            "proposals": proposals,
            "proposals_applied": False,
            "note": (
                "Proposed settings are not applied automatically. Update the "
                "'freqtrade_canada_config' Swarm config and redeploy to apply them."
                if proposals
                else "No configuration changes were required."
            ),
        }

    async def _handle_query(self, change: Dict[str, Any]) -> Dict[str, Any]:
        action = change.get("action")
        if action == "status":
            try:
                status = await self.freqtrade.status()
                return {
                    "change": change,
                    "status": "success",
                    "data": {
                        "state": status.state,
                        "dry_run": status.dry_run,
                        "open_trades": status.open_trades_count,
                        "max_open_trades": status.max_open_trades,
                        "current_balance": status.current_balance,
                        "profit_pct": round(status.profit_pct, 2),
                    },
                }
            except FreqtradeAPIError as e:
                return {"change": change, "status": "failed", "error": str(e)}

        if action == "explain_trade":
            explainer = self.orchestrator.plugins.get("explainer")
            if not explainer:
                return {
                    "change": change,
                    "status": "unavailable",
                    "error": "Explainer plugin is not loaded.",
                }
            trades = await self.freqtrade.get_trades(limit=5)
            if change.get("pair"):
                trades = [t for t in trades if t.pair == change["pair"]] or trades
            if not trades:
                return {
                    "change": change,
                    "status": "no_data",
                    "error": "No closed trades found to explain yet.",
                }
            explanation = await explainer.explain_trade(trades[0])
            return {"change": change, "status": "success", "data": explanation}

        return {"change": change, "status": "unsupported", "error": f"Unknown query '{action}'"}

    async def _handle_bot_control(self, change: Dict[str, Any]) -> Dict[str, Any]:
        action = change.get("action")
        try:
            if action == "pause":
                result = await self.freqtrade.pause()
            elif action == "resume":
                result = await self.freqtrade.start()
            else:
                return {"change": change, "status": "unsupported", "error": f"Unknown action '{action}'"}
            return {"change": change, "status": "success", "result": result}
        except FreqtradeAPIError as e:
            return {"change": change, "status": "failed", "error": str(e)}

    async def _handle_restrict_pairs(self, change: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await self.freqtrade.set_whitelist(change["pairs"])
            return {"change": change, "status": "success", "result": result}
        except UnsupportedOperation as e:
            return {"change": change, "status": "refused", "error": str(e)}
        except FreqtradeAPIError as e:
            return {"change": change, "status": "failed", "error": str(e)}

    async def _audit_blocked(
        self, parsed: NLCommand, blocked: List[Dict[str, Any]], user_id: str
    ) -> None:
        """Record a refused attempt. Refusals are security-relevant events."""
        await self.audit.log(
            plugin="nl_config",
            action="command_refused",
            user_initiated=True,
            input_data={"command": parsed.original_text, "user": user_id},
            output_data={"blocked": blocked},
            decision_reasoning=(
                "Command attempted to modify a frozen setting "
                f"({', '.join(c.get('key', '?') for c in blocked)}). Refused by policy."
            ),
            risk_level="high",
            approved_by=None,
        )

    async def approve_and_apply(
        self, changes: List[Dict[str, Any]], approved_by: str = "operator"
    ) -> Dict[str, Any]:
        """
        Apply pre-approved changes.

        Runtime actions execute. Configuration proposals are recorded as approved
        and returned with the exact values to apply out of band.
        """
        result = await self._apply_changes(changes)

        await self.audit.log(
            plugin="nl_config",
            action="command_approved",
            user_initiated=True,
            input_data={"changes": changes},
            output_data=result,
            decision_reasoning=(
                "Operator approved the proposed changes. Runtime actions were executed; "
                "configuration proposals still require a Swarm config update and redeploy."
            ),
            risk_level="high",
            approved_by=approved_by,
        )
        return result

    async def shutdown(self) -> None:
        self.logger.info("Natural language config plugin shut down")
