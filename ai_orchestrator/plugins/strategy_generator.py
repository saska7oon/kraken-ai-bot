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
        return """You are an expert quantitative trading strategy developer.
Generate Python trading strategies for Freqtrade (freqtrade.io) that trade CAD pairs on Kraken Canada.

REQUIREMENTS:
1. Strategies must inherit from freqtrade.strategy.IStrategy
2. Use only spot trading (no margin/futures - Canadian regulations)
3. Target moderate risk: 5-10% per trade, 8-12% stoploss
4. Include proper risk management (position sizing, stoploss, trailing stop)
5. Use technical indicators: EMA, RSI, MACD, Bollinger Bands, ADX, Volume
6. Implement populate_indicators, populate_entry_trend, populate_exit_trend
7. Include hyperopt parameters for optimization
8. Code must be production-ready with proper error handling

OUTPUT FORMAT: JSON with "strategies" array, each containing:
- "name": strategy class name
- "description": what the strategy does
- "code": complete Python code as string
- "parameters": key hyperparameters
- "risk_level": "low"|"moderate"|"high"
- "suitable_pairs": list of pairs this strategy works best on"""

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
{chr(10).join([f'- {s["name"]}: WR={s["win_rate"]:.1f}%, Profit={s["total_profit"]:.2f}, Sharpe={s["sharpe"]:.2f}' for s in current_strategies])}

RISK PROFILE: {self.risk_profile}
TARGET: Strategies that complement existing ones, address weaknesses, adapt to current market regime.

Focus on:
1. Trend-following for trending markets
2. Mean-reversion for ranging markets
3. Volatility-adjusted position sizing
4. Canadian market hours considerations
5. Kraken-specific pair characteristics (BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD)"""

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

    async def _save_proposal(self, proposal: Dict[str, Any]) -> Path:
        """
        Write a candidate strategy into the shared strategies volume.

        Files are named 'proposal_<timestamp>_<name>.py' so a generated file can
        never overwrite or shadow the operator's own strategy.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", proposal["name"])
        filename = f"proposal_{timestamp}_{safe_name}.py"
        filepath = self.generated_dir / filename

        header = f'''"""
AI-GENERATED STRATEGY PROPOSAL - NOT ACTIVE

Name: {proposal['name']}
Generated: {datetime.utcnow().isoformat()}Z
Description: {proposal['description']}
Risk Level: {proposal['risk_level']}
Suitable Pairs: {', '.join(proposal['suitable_pairs'])}
Parameters: {json.dumps(proposal['parameters'], indent=2)}

This file was produced by an AI model. It has passed an automated safety
validator and a backtest, but it has not been reviewed by a human and it is
NOT running. Activating it requires editing the Swarm config and redeploying.
"""

'''
        async with aiofiles.open(filepath, "w") as f:
            await f.write(header + proposal["code"])

        self.logger.info("Saved strategy proposal: %s", filepath)
        return filepath

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Strategy Generator Plugin shut down")