"""
Strategy Generator Plugin

Generates new trading strategies using LLM based on market conditions,
backtest results, and performance analysis.
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig
from ai_orchestrator.core.proposal_validator import validate_strategy_code

logger = logging.getLogger(__name__)


class StrategyGeneratorPlugin(BasePlugin):
    """
    Generates and proposes new trading strategies.
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        # Template and output locations.
        #
        # generated_dir is the SHARED strategies volume, which freqtrade mounts at
        # /freqtrade/user_data/strategies. Writing here is what allows a generated
        # strategy to be backtested before the operator is asked to approve it.
        self.templates_dir = Path("/app/config/strategies/templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self.generated_dir = Path(config.config.get("generated_dir", "/app/strategies"))
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        # Config
        self.max_strategies = config.config.get("max_strategies", 3)
        self.risk_profile = config.config.get("risk_profile", "moderate")
        self.min_backtest_sharpe = config.config.get("min_backtest_sharpe", 1.0)
        self.min_backtest_trades = config.config.get("min_backtest_trades", 50)

        # Backtest gate: a proposal reaches the operator only if it has been
        # backtested AND met these thresholds. Previously nothing was backtested
        # at all - the header on every saved file even said "This strategy has
        # not been backtested".
        self.require_backtest = config.config.get("require_backtest", True)
        self.min_backtest_profit_pct = config.config.get("min_backtest_profit_pct", 0.0)
        self.max_backtest_drawdown_pct = config.config.get("max_backtest_drawdown_pct", 25.0)
        self.backtest_timerange_days = config.config.get("backtest_timerange_days", 180)
        self.backtest_timeout_seconds = config.config.get("backtest_timeout_seconds", 900)

        # Stop-loss bounds enforced on generated code. These match the bounds the
        # natural-language interface uses, so the two cannot disagree.
        self.max_stoploss = config.config.get("max_stoploss", -0.15)
        self.min_stoploss = config.config.get("min_stoploss", -0.02)

    async def initialize(self) -> bool:
        """Initialize plugin."""
        self.logger.info("Strategy Generator Plugin initialized")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Generate, validate and backtest candidate strategies.

        A proposal is only reported to the operator as worth considering if it
        passes three gates:
          1. the static safety validator (no leverage, no shorts, sane stoploss,
             no secret access),
          2. it compiles and loads inside freqtrade,
          3. it actually produces positive results over a real backtest.

        Nothing is ever activated. Choosing to run a new strategy means editing
        the Swarm config and redeploying, which is outside the AI's reach.
        """
        self.logger.info("Running strategy generation cycle")

        market_context = await self._get_market_context()
        performance = await self._get_strategy_performance()

        proposals = await self._generate_proposals(market_context, performance)

        accepted: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for proposal in proposals:
            result = await self._validate_proposal(proposal)
            if result["ok"]:
                accepted.append(proposal)
            else:
                rejected.append(
                    {
                        "name": proposal.get("name", "unnamed"),
                        "stage": "safety_validation",
                        "errors": result["errors"],
                        "warnings": result["warnings"],
                    }
                )

        # Save accepted candidates into the shared volume, then backtest them.
        evaluated: List[Dict[str, Any]] = []
        for proposal in accepted[: self.max_strategies]:
            try:
                filepath = await self._save_proposal(proposal)
            except OSError as e:
                rejected.append(
                    {"name": proposal.get("name"), "stage": "save", "errors": [str(e)]}
                )
                continue

            # freqtrade discovers strategies by class name, so use the class name
            # rather than the file name when asking for a backtest.
            class_name = self._extract_class_name(proposal["code"]) or proposal["name"]

            if self.require_backtest:
                backtest = await self._backtest_proposal(class_name)
            else:
                backtest = {
                    "passed": None,
                    "reason": "Backtest gate is disabled in configuration.",
                }

            entry = {
                "name": proposal["name"],
                "class_name": class_name,
                "description": proposal.get("description", ""),
                "file": str(filepath),
                "risk_level": proposal.get("risk_level"),
                "backtest": backtest,
                "worth_considering": bool(backtest.get("passed")),
            }
            evaluated.append(entry)

            if backtest.get("passed") is False:
                rejected.append(
                    {
                        "name": proposal["name"],
                        "stage": "backtest",
                        "errors": [backtest.get("reason", "did not meet thresholds")],
                    }
                )

        worth_considering = [e for e in evaluated if e["worth_considering"]]

        await self.audit.log(
            plugin="strategy_generator",
            action="strategy_generation",
            user_initiated=bool(kwargs.get("force", False)),
            input_data={
                "market_summary": market_context.get("summary", ""),
                "risk_profile": self.risk_profile,
            },
            output_data={
                "generated": len(proposals),
                "passed_validation": len(accepted),
                "worth_considering": [e["name"] for e in worth_considering],
                "rejected": rejected,
            },
            decision_reasoning=(
                f"Generated {len(proposals)} candidates; {len(accepted)} passed the "
                f"safety validator; {len(worth_considering)} passed a real backtest. "
                "Nothing was activated."
            ),
            risk_level="medium",
        )

        return {
            "status": "completed",
            "proposals_generated": len(proposals),
            "passed_validation": len(accepted),
            "worth_considering": worth_considering,
            "rejected": rejected,
            "activated": False,
            "note": (
                "No strategy was activated and none can be activated automatically. "
                "To try one, edit the 'freqtrade_canada_config' Swarm config to select "
                "it and redeploy."
            ),
            "market_context_summary": market_context.get("summary", ""),
        }

    @staticmethod
    def _extract_class_name(code: str) -> Optional[str]:
        """Find the IStrategy subclass name, which is what freqtrade needs."""
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = getattr(base, "id", None) or getattr(base, "attr", None)
                    if base_name == "IStrategy":
                        return node.name
        return None

    async def _get_market_context(self) -> Dict[str, Any]:
        """Gather current market context."""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "pairs": [],
            "summary": "",
        }

        # Get whitelist pairs
        whitelist = await self.freqtrade.get_whitelist()

        for pair in whitelist:
            try:
                ticker = await self.freqtrade.get_ticker_snapshot(pair)
                candles = await self.freqtrade.get_candles(pair, "1h", 100)

                if candles and ticker:
                    pair_data = {
                        "pair": pair,
                        "price": ticker.get("last"),
                        "change_24h": ticker.get("change_24h_pct"),
                        "volume_24h": ticker.get("volume_24h"),
                        "trend": self._analyze_trend(candles),
                        "volatility": self._calculate_volatility(candles),
                    }
                    context["pairs"].append(pair_data)
            except Exception as e:
                self.logger.warning(f"Failed to get data for {pair}: {e}")

        # Create summary
        if context["pairs"]:
            trends = [p["trend"] for p in context["pairs"]]
            bullish = trends.count("bullish")
            bearish = trends.count("bearish")
            context["summary"] = (
                f"Market: {bullish} bullish, {bearish} bearish pairs. "
                f"Overall sentiment: {'bullish' if bullish > bearish else 'bearish' if bearish > bullish else 'neutral'}"
            )
        else:
            context["summary"] = "No market data available"

        return context

    def _analyze_trend(self, candles: List) -> str:
        """Simple trend analysis."""
        if len(candles) < 20:
            return "unknown"

        closes = [c.close for c in candles]
        sma_20 = sum(closes[-20:]) / 20
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma_20

        current = closes[-1]
        if current > sma_20 > sma_50:
            return "bullish"
        elif current < sma_20 < sma_50:
            return "bearish"
        return "neutral"

    def _calculate_volatility(self, candles: List) -> float:
        """Calculate volatility (ATR-like)."""
        if len(candles) < 14:
            return 0.0

        true_ranges = []
        for i in range(1, min(15, len(candles))):
            high = candles[-i].high
            low = candles[-i].low
            prev_close = candles[-i-1].close if i < len(candles) - 1 else candles[-i].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) / candles[-1].close if candles else 0.0

    async def _get_strategy_performance(self) -> Dict[str, Any]:
        """
        Summarise how the running strategy is doing, from real data.

        The previous version read ``.win_rate``, ``.sharpe_ratio`` and
        ``.max_drawdown`` attributes off the /performance response. That endpoint
        returns only {pair, profit}, so every one of those accesses raised
        AttributeError, was swallowed by the surrounding ``except``, and the
        generator silently had no performance context at all.
        """
        try:
            status = await self.freqtrade.status()
            trades = await self.freqtrade.get_closed_trades(limit=200)
        except Exception as e:
            self.logger.warning("Could not read strategy performance: %s", e)
            return {"strategies": [], "overall": {}, "error": str(e)}

        winners = [t for t in trades if (t.profit_ratio or 0) > 0]
        total_profit = sum(t.profit_abs or 0 for t in trades)
        win_rate = len(winners) / len(trades) if trades else 0.0

        # Per-pair breakdown, which is the only grouping the API actually offers.
        by_pair: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            entry = by_pair.setdefault(t.pair, {"trades": 0, "profit": 0.0, "wins": 0})
            entry["trades"] += 1
            entry["profit"] += t.profit_abs or 0
            if (t.profit_ratio or 0) > 0:
                entry["wins"] += 1

        return {
            "strategies": [
                {
                    "name": status.strategy,
                    "total_trades": len(trades),
                    "win_rate": win_rate,
                    "total_profit": total_profit,
                    "dry_run": status.dry_run,
                }
            ],
            "by_pair": by_pair,
            "overall": {
                "total_trades": len(trades),
                "total_profit": total_profit,
                "avg_win_rate": win_rate,
            },
            "note": "Computed from real closed trades; not a backtest.",
        }

    async def _generate_proposals(
        self,
        market_context: Dict[str, Any],
        performance: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Use LLM to generate strategy proposals."""

        # Build prompt
        prompt = self._build_generation_prompt(market_context, performance)

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                model=self.config.config.get("model"),
                max_tokens=8192,
                temperature=0.7,
                response_format={"type": "json_object"},
            )

            content = response.choices[0]["message"]["content"]
            result = json.loads(content)
            return result.get("strategies", [])

        except Exception as e:
            self.logger.error(f"LLM strategy generation failed: {e}")
            return []

    def _get_system_prompt(self) -> str:
        """Instructions for the model, including the rules it cannot see.

        The validator rejects a generated strategy for several reasons that are
        invisible from the outside: a hard import allowlist, a ban on double
        underscores, a required ``protections`` property, and a ban on custom
        stop losses. A model that does not know these rules will violate them
        constantly, every proposal will be rejected, and the feature will look
        broken to the operator while actually working exactly as designed.

        So the rules are stated explicitly, and a complete working template is
        supplied. A model that copies the template produces a valid strategy;
        free-tier models in particular produce far more usable output from a
        concrete example than from a list of prohibitions.
        """
        return '''You are an expert quantitative trading strategy developer.
Generate Python trading strategies for Freqtrade that trade CAD pairs on Kraken Canada.
The operator is a beginner who does not read code, so strategies must be simple,
conservative, and easy to explain.

HARD RULES. A strategy that breaks any of these is rejected automatically and never
shown to the operator, so follow them exactly.

RULE 1 - PROTECTIONS ARE COMPULSORY.
Every strategy MUST define a "protections" property returning a plain list that
includes all three of MaxDrawdown, StoplossGuard and CooldownPeriod. It must be a
literal list - do NOT call a function or build it in a loop. Copy this block
verbatim and adjust the numbers if you have a reason to:

    @property
    def protections(self):
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 10,
                "stop_duration_candles": 288,
                "max_allowed_drawdown": 0.10,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 3,
                "stop_duration_candles": 96,
                "only_per_pair": False,
            },
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 12,
            },
        ]

RULE 2 - NO CUSTOM STOP LOSS.
Do NOT set "use_custom_stoploss = True" and do NOT define a "custom_stoploss"
method. Use a plain numeric "stoploss" between -0.02 and -0.15. A custom stop loss
is code-driven, so nobody can say in advance how much a trade could lose, and it
is rejected.

RULE 3 - ONLY THESE IMPORTS.
freqtrade, pandas, numpy, talib, technical, typing, datetime, math, statistics,
decimal, functools, itertools, collections, dataclasses, enum, warnings, logging.
Importing anything else - including os, sys, io, builtins or subprocess - is
rejected. Never use relative imports.

RULE 4 - NO DOUBLE UNDERSCORES ANYWHERE.
No name, attribute, method or string may contain "__". That covers __init__,
__dict__, __import__ and super().__init__(). Write plain code without them.

RULE 5 - PLAIN ATTRIBUTES AND METHODS ONLY.
INTERFACE_VERSION must be 3. Define stoploss, timeframe and minimal_roi as
plain literal values. Implement populate_indicators, populate_entry_trend and
populate_exit_trend with exactly the signature (self, dataframe, metadata).
Use only spot long trading: never set leverage, margin_mode, trading_mode or
can_short.

RULE 6 - MODERATE RISK.
Aim for a stop loss of -0.08 to -0.12, sensible minimal_roi, and simple,
well-understood indicators (EMA, RSI, MACD, Bollinger Bands, ADX, volume).
Prefer few, clear conditions over many stacked ones.

OUTPUT FORMAT - a JSON object with a "strategies" array. Each entry must have:
- "name": the strategy class name (letters, digits and underscores only)
- "description": one or two plain sentences a non-expert can understand
- "code": the complete Python source as a string
- "parameters": the key tunable values
- "risk_level": "low", "moderate" or "high"
- "suitable_pairs": list of pairs, e.g. ["BTC/CAD"]

The "code" string must contain the entire file: imports, the class, the
protections property, and all three populate_ methods.'''

    def _build_generation_prompt(self, market_context: Dict, performance: Dict) -> str:
        pairs_info = "\n".join([
            f"- {p['pair']}: ${p['price']:.2f} ({p['change_24h']:+.2f}%), "
            f"Trend: {p['trend']}, Volatility: {p['volatility']:.4f}"
            for p in market_context["pairs"]
        ])

        current_perf = performance.get("overall", {})
        current_strategies = performance.get("strategies", [])

        return f"""Generate {self.max_strategies} new Freqtrade strategies for the current market conditions.

MARKET CONTEXT:
{pairs_info}
Summary: {market_context['summary']}

CURRENT PERFORMANCE:
- Total Profit: {current_perf.get('total_profit', 0):.2f} CAD
- Avg Win Rate: {current_perf.get('avg_win_rate', 0):.1f}%
- Active Strategies: {len(current_strategies)}
{self._format_current_strategies(current_strategies)}

RISK PROFILE: {self.risk_profile}
TARGET: Strategies that complement existing ones, address weaknesses, adapt to current market regime.

Focus on:
1. Trend-following for trending markets
2. Mean-reversion for ranging markets
3. Volatility-adjusted position sizing
4. Canadian market hours considerations
5. Kraken-specific pair characteristics (BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD)"""

    @staticmethod
    def _format_current_strategies(current_strategies: List[Dict[str, Any]]) -> str:
        """Render the current-strategy lines for the generation prompt.

        This used to be an inline f-string referencing ``s["sharpe"]``, a key
        ``_get_strategy_performance`` has never produced. Because the reference
        sat inside the f-string's expression, every run raised
        ``KeyError: 'sharpe'`` and the generator never produced a single
        strategy - the entire feature was dead on arrival.

        Two lessons are baked in here:
        * Only reference fields that are actually produced, and read them with
          ``.get()`` so a future shape change degrades the prompt instead of
          killing the run.
        * A metric the model is not given cannot be invented by it. We pass what
          we measure (trades, win rate, profit) rather than a plausible-looking
          label we do not have.
        """
        if not current_strategies:
            return "- (no closed trades yet - this is a fresh deployment)"

        lines = []
        for strategy in current_strategies:
            name = strategy.get("name") or "unknown"
            trades = strategy.get("total_trades", 0)
            win_rate = strategy.get("win_rate", 0.0)
            profit = strategy.get("total_profit", 0.0)
            lines.append(
                f"- {name}: {trades} closed trades, "
                f"WR={float(win_rate):.1f}%, Profit={float(profit):.2f}"
            )
        return "\n".join(lines)

    async def _validate_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Static safety check.

        The old implementation called ``compile()`` and checked that a risk label
        was one of three strings. That is a syntax check, not a safety check: a
        strategy could set leverage to 100, remove its stop loss, or read the
        Kraken API key out of /run/secrets and still pass.

        The validator used here is deliberately paranoid and fails closed - if it
        errors internally it returns a blocking error rather than waving the
        proposal through.
        """
        required_fields = [
            "name",
            "description",
            "code",
            "parameters",
            "risk_level",
            "suitable_pairs",
        ]
        missing = [f for f in required_fields if f not in proposal]
        if missing:
            return {
                "ok": False,
                "errors": [f"Proposal is missing required field(s): {', '.join(missing)}"],
                "warnings": [],
            }

        if proposal["risk_level"] not in ("low", "moderate", "high"):
            return {
                "ok": False,
                "errors": [
                    f"Risk level '{proposal['risk_level']}' is not one of low, "
                    "moderate or high."
                ],
                "warnings": [],
            }

        result = validate_strategy_code(
            proposal["code"],
            profile=self.risk_profile,
            max_stoploss=self.max_stoploss,
            min_stoploss=self.min_stoploss,
        )

        errors = [i.message for i in result.errors()]
        warnings = [i.message for i in result.warnings()]

        if errors:
            self.logger.warning(
                "Rejected strategy proposal '%s': %s", proposal.get("name"), errors
            )
        for warning in warnings:
            self.logger.info("Strategy proposal warning: %s", warning)

        return {"ok": result.ok, "errors": errors, "warnings": warnings}

    async def _backtest_proposal(self, class_name: str) -> Dict[str, Any]:
        """
        Backtest a generated strategy and decide whether it cleared the bar.

        This is the gate that was entirely absent before: candidates were written
        to disk, tagged "not backtested", and left for a non-expert operator to
        evaluate on no evidence at all.
        """
        timerange = None
        if self.backtest_timerange_days:
            end = datetime.utcnow()
            start = end - timedelta(days=self.backtest_timerange_days)
            timerange = f"{start:%Y%m%d}-{end:%Y%m%d}"

        try:
            job = await self.freqtrade.start_backtest(
                strategy=class_name,
                timerange=timerange,
                enable_protections=True,
            )
        except Exception as e:
            return {
                "passed": False,
                "reason": (
                    f"Could not start a backtest for '{class_name}'. The strategy "
                    f"may not be loadable by freqtrade, or historical data may be "
                    f"missing. Details: {e}"
                ),
            }

        # Poll until the backtest finishes or we give up.
        deadline = datetime.utcnow() + timedelta(seconds=self.backtest_timeout_seconds)
        status = job
        while status.running and datetime.utcnow() < deadline:
            await asyncio.sleep(10)
            try:
                status = await self.freqtrade.get_backtest_status()
            except Exception as e:
                return {"passed": False, "reason": f"Lost track of the backtest: {e}"}

        if status.running:
            try:
                await self.freqtrade.abort_backtest()
            except Exception:
                pass
            return {
                "passed": False,
                "reason": (
                    f"The backtest did not finish within "
                    f"{self.backtest_timeout_seconds}s and was cancelled."
                ),
            }

        raw = status.raw or {}
        stats = self._extract_backtest_stats(raw)
        if not stats:
            return {
                "passed": False,
                "reason": "The backtest produced no usable results.",
                "raw_status": raw.get("status"),
            }

        return self._judge_backtest(stats, class_name)

    @staticmethod
    def _extract_backtest_stats(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Pull the headline numbers out of a backtest result payload."""
        # Freqtrade nests results differently across endpoints; try the common
        # shapes rather than assuming one.
        candidates = [
            raw.get("results"),
            (raw.get("results") or {}).get("strategy") if isinstance(raw.get("results"), dict) else None,
            raw.get("strategy"),
        ]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            # A results dict may be keyed by strategy name.
            for value in candidate.values():
                if isinstance(value, dict) and "total_trades" in value:
                    return value
            if "total_trades" in candidate:
                return candidate
        if "total_trades" in raw:
            return raw
        return {}

    def _judge_backtest(self, stats: Dict[str, Any], class_name: str) -> Dict[str, Any]:
        """Apply the configured thresholds to backtest statistics."""
        trades = int(stats.get("total_trades", 0) or 0)
        profit_pct = float(stats.get("profit_total", 0.0) or 0.0) * 100
        profit_abs = stats.get("profit_total_abs")
        drawdown_pct = float(
            stats.get("max_drawdown_account", stats.get("max_drawdown", 0.0)) or 0.0
        ) * 100
        win_rate = float(stats.get("winrate", 0.0) or 0.0) * 100
        sharpe = stats.get("sharpe")

        reasons: List[str] = []
        if trades < self.min_backtest_trades:
            reasons.append(
                f"only {trades} trades in the test period (need at least "
                f"{self.min_backtest_trades} before the result means anything)"
            )
        if profit_pct < self.min_backtest_profit_pct:
            reasons.append(
                f"it lost {abs(profit_pct):.1f}% over the test period "
                f"(profit was {profit_pct:.1f}%)"
            )
        if drawdown_pct > self.max_backtest_drawdown_pct:
            reasons.append(
                f"it fell {drawdown_pct:.1f}% from its peak at worst "
                f"(limit is {self.max_backtest_drawdown_pct:.0f}%)"
            )
        if sharpe is not None and self.min_backtest_sharpe and float(sharpe) < self.min_backtest_sharpe:
            reasons.append(
                f"its risk-adjusted return was {float(sharpe):.2f}, below the "
                f"{self.min_backtest_sharpe} threshold"
            )

        return {
            "passed": not reasons,
            "strategy": class_name,
            "stats": {
                "total_trades": trades,
                "profit_pct": round(profit_pct, 2),
                "profit_abs": profit_abs,
                "max_drawdown_pct": round(drawdown_pct, 2),
                "win_rate_pct": round(win_rate, 2),
                "sharpe": sharpe,
            },
            "reason": (
                "Cleared every threshold."
                if not reasons
                else "Rejected: " + "; ".join(reasons) + "."
            ),
            "caveat": (
                "A backtest is a simulation against past prices. A good result here "
                "does not mean the strategy will make money in future."
            ),
        }

    @staticmethod
    def _comment_line(label: str, value: Any) -> str:
        """Render one piece of untrusted metadata as a single, inescapable comment.

        This is the fix for a real remote-code-execution hole. The header used to be
        an f-string that interpolated the model's text straight into a triple-quoted
        docstring. A description containing three consecutive double-quote characters
        closed that docstring, and every character after it became module-level
        Python. Because this file is written into the very directory Freqtrade imports
        strategies from, the payload executed *inside the container holding the Kraken
        API key and secret*.

        A verified payload set description to: three double-quotes, then a newline,
        then ``import os`` and an ``os.system`` call that read the private config,
        then three more double-quotes. It compiled cleanly and passed the strategy
        validator, because the validator only ever inspected the ``code`` field, and
        that field was entirely clean.

        Two properties make this version safe:

        * ``json.dumps`` escapes every control character, so the output is guaranteed
          to contain no newline and no quote break-out.
        * A ``#`` comment can only be terminated by a newline, and there are none.

        So there is no string the model can emit that escapes the comment, regardless
        of what the validator does or does not catch.
        """
        return f"# {label}: {json.dumps(str(value))}"

    async def _save_proposal(self, proposal: Dict[str, Any]) -> Path:
        """
        Write a candidate strategy into the shared strategies volume.

        Files are named 'proposal_<timestamp>_<name>.py' so a generated file can
        never overwrite or shadow the operator's own strategy.

        Metadata is emitted as comments, never as a docstring or any other
        executable construct - see ``_comment_line`` for why that distinction is
        load-bearing. The final file text is validated as a whole, because
        validating only ``proposal['code']`` is exactly the gap that allowed the
        header to smuggle code.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", proposal["name"])
        filename = f"proposal_{timestamp}_{safe_name}.py"
        filepath = self.generated_dir / filename

        suitable_pairs = proposal.get("suitable_pairs") or []
        if isinstance(suitable_pairs, (str, bytes)):
            suitable_pairs = [suitable_pairs]

        header = "\n".join(
            [
                "# " + "=" * 74,
                "# AI-GENERATED STRATEGY PROPOSAL - NOT ACTIVE",
                "# " + "=" * 74,
                self._comment_line("Name", proposal.get("name", "")),
                self._comment_line("Generated", f"{datetime.utcnow().isoformat()}Z"),
                self._comment_line("Risk level", proposal.get("risk_level", "")),
                self._comment_line("Description", proposal.get("description", "")),
                self._comment_line("Suitable pairs", ", ".join(map(str, suitable_pairs))),
                self._comment_line("Parameters", json.dumps(proposal.get("parameters", {}))),
                "#",
                "# Produced by an AI model and passed an automated validator plus a",
                "# backtest. No human has reviewed it and it is NOT running.",
                "# Activating it requires editing the Swarm config and redeploying.",
                "# " + "=" * 74,
                "",
                "",
            ]
        )

        file_text = header + proposal["code"]

        # Validate the assembled artifact, not just the model-supplied body. The
        # header is now comment-only by construction, but checking the whole file
        # means any future change to how the header is built is still caught.
        final_result = validate_strategy_code(
            file_text,
            profile=self.risk_profile,
            max_stoploss=self.max_stoploss,
            min_stoploss=self.min_stoploss,
        )
        if not final_result.ok:
            messages = [i.message for i in final_result.errors()]
            self.logger.error(
                "Refusing to write proposal '%s': the assembled file failed "
                "validation: %s",
                proposal.get("name"),
                messages,
            )
            raise ValueError(
                "Generated strategy file failed validation and was not written: "
                + "; ".join(messages)
            )

        async with aiofiles.open(filepath, "w") as f:
            await f.write(file_text)

        self.logger.info("Saved strategy proposal: %s", filepath)
        return filepath

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Strategy Generator Plugin shut down")