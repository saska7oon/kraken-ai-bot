"""
Parameter Optimizer Plugin

Analyzes strategy performance and suggests hyperparameter adjustments
using LLM reasoning and Freqtrade's Edge/performance data.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


@dataclass
class ParameterSuggestion:
    """Parameter optimization suggestion."""
    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float
    expected_impact: str  # positive, neutral, negative


class ParamOptimizerPlugin(BasePlugin):
    """
    Optimizes strategy parameters based on performance analysis.
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        # Config
        self.trigger = config.config.get("trigger", "performance_drop")
        self.performance_threshold = config.config.get("performance_threshold", 1.0)  # Sharpe ratio
        self.min_trades_for_analysis = config.config.get("min_trades_for_analysis", 30)
        self.max_suggestions = config.config.get("max_suggestions", 5)
        self.auto_apply = config.config.get("auto_apply", False)  # Requires approval

    async def initialize(self) -> bool:
        """Initialize plugin."""
        self.logger.info("Parameter Optimizer Plugin initialized")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run parameter optimization analysis."""
        self.logger.info("Running parameter optimization analysis")

        # Check trigger condition
        should_run, trigger_reason = await self._check_trigger()

        if not should_run and not kwargs.get("force", False):
            return {
                "status": "skipped",
                "reason": "Trigger condition not met",
                "trigger": self.trigger,
            }

        # Collect REAL data. Note: Freqtrade's /performance endpoint returns only
        # {pair, profit}; it does not expose Sharpe ratio, win rate, drawdown or
        # expectancy. The previous version read those fields off a dataclass and
        # would have crashed with AttributeError on the first run. Every statistic
        # below is now computed from actual closed trades.
        trades = await self.freqtrade.get_closed_trades(limit=200)

        if not trades:
            return {
                "status": "no_data",
                "message": (
                    "Not enough closed trades to analyse yet. The optimizer needs "
                    f"at least {self.min_trades_for_analysis}."
                ),
                "closed_trades": 0,
            }

        status = await self.freqtrade.status()
        strategy_name = status.strategy or "unknown"

        analysis = self._analyze_performance(trades)

        if analysis["total_trades"] < self.min_trades_for_analysis:
            return {
                "status": "insufficient_data",
                "message": (
                    f"Only {analysis['total_trades']} closed trades so far; the "
                    f"optimizer waits for {self.min_trades_for_analysis} before "
                    f"drawing conclusions."
                ),
                "analysis": analysis,
            }

        suggestions = await self._generate_suggestions(strategy_name, analysis)
        filtered = self._filter_suggestions(suggestions)

        await self.audit.log(
            plugin="param_optimizer",
            action="parameter_optimization",
            user_initiated=bool(kwargs.get("force", False)),
            input_data={
                "trigger": trigger_reason,
                "strategy": strategy_name,
                "performance_summary": analysis,
            },
            output_data={"suggestions": [asdict(s) for s in filtered]},
            decision_reasoning=(
                f"Generated {len(filtered)} parameter suggestions from "
                f"{analysis['total_trades']} real closed trades ({trigger_reason})"
            ),
            risk_level="medium",
        )

        return {
            "status": "completed",
            "trigger": trigger_reason,
            "strategy": strategy_name,
            "analysis": analysis,
            "suggestions": [asdict(s) for s in filtered],
            # These are ALWAYS proposals. Nothing in this system can change
            # strategy parameters while the bot is running.
            "applied": False,
            "apply_instructions": (
                "To act on a suggestion, edit ModerateMultiPairStrategy in "
                "config/strategies/moderate_multi.py, push, and redeploy the stack. "
                "Backtest the change first."
            ),
        }

    async def _check_trigger(self) -> tuple:
        """
        Decide whether there is anything worth analysing.

        The previous trigger compared a "Sharpe ratio" read from a field that the
        API does not return, so it was always 0.0 and the trigger fired on every
        run for no reason.
        """
        if self.trigger == "performance_drop":
            trades = await self.freqtrade.get_closed_trades(limit=50)
            if len(trades) < self.min_trades_for_analysis:
                return False, f"Only {len(trades)} closed trades; not enough to judge"

            winners = [t for t in trades if (t.profit_ratio or 0) > 0]
            win_rate = len(winners) / len(trades)

            if win_rate < 0.4:
                return True, f"Win rate is low: {win_rate:.0%} over {len(trades)} trades"
            return False, f"Win rate acceptable: {win_rate:.0%} over {len(trades)} trades"

        elif self.trigger == "schedule":
            return True, "Scheduled run"

        elif self.trigger == "trade_count":
            # Genuine placeholder: this needs persistence between runs to compare
            # against the previous count. Returning False is honest; the old
            # version fell through and silently did nothing.
            self.logger.info(
                "trade_count trigger is not implemented; no analysis will run"
            )
            return False, "trade_count trigger is not implemented"

        return False, "Condition not met"

    def _analyze_performance(self, trades: List) -> Dict[str, Any]:
        """Compute statistics from real closed trades."""
        if not trades:
            return {}

        winners = [t for t in trades if (t.profit_ratio or 0) > 0]
        losers = [t for t in trades if (t.profit_ratio or 0) <= 0]

        avg_win = sum(t.profit_ratio for t in winners) / len(winners) if winners else 0.0
        avg_loss = sum(t.profit_ratio for t in losers) / len(losers) if losers else 0.0

        returns = [t.profit_ratio for t in trades if t.profit_ratio is not None]
        total_profit = sum(t.profit_abs or 0 for t in trades)

        # Per-trade Sharpe-style ratio. This is deliberately NOT the annualised
        # Sharpe ratio quoted in finance: with the trade counts available here,
        # annualising would be guesswork. Labelled accordingly so it is not
        # mistaken for the conventional figure.
        sharpe = 0.0
        if len(returns) > 1:
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            std = variance ** 0.5
            if std > 0:
                sharpe = mean / std

        # Maximum drawdown from the cumulative profit curve.
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cumulative += t.profit_abs or 0
            peak = max(peak, cumulative)
            if peak > 0:
                max_dd = max(max_dd, (peak - cumulative) / peak)

        exit_reasons: Dict[str, int] = {}
        for t in trades:
            if t.exit_reason:
                exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        pair_performance: Dict[str, Dict[str, Any]] = {}
        for t in trades:
            entry = pair_performance.setdefault(
                t.pair, {"wins": 0, "losses": 0, "total_profit": 0.0}
            )
            if (t.profit_ratio or 0) > 0:
                entry["wins"] += 1
            else:
                entry["losses"] += 1
            entry["total_profit"] += t.profit_abs or 0

        hold_times = [
            (t.close_date - t.open_date).total_seconds() / 3600
            for t in trades
            if t.close_date and t.open_date
        ]
        avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0.0

        return {
            "total_trades": len(trades),
            "win_rate": len(winners) / len(trades),
            "total_profit": total_profit,
            "per_trade_sharpe": sharpe,
            "sharpe_note": (
                "Per-trade ratio, not annualised. Treat as a rough consistency "
                "measure only."
            ),
            "max_drawdown_pct": max_dd * 100,
            "expectancy": (
                (len(winners) / len(trades)) * avg_win
                + (len(losers) / len(trades)) * avg_loss
            ),
            "detailed": {
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": (
                    abs(avg_win / avg_loss)
                    if avg_loss
                    else (float("inf") if avg_win else 0.0)
                ),
                "exit_reasons": exit_reasons,
                "pair_performance": pair_performance,
                "avg_hold_hours": avg_hold,
                "winning_trades": len(winners),
                "losing_trades": len(losers),
            },
        }

    async def _generate_suggestions(
        self,
        strategy_name: str,
        analysis: Dict,
    ) -> List[ParameterSuggestion]:
        """Generate parameter suggestions using the LLM, grounded in the real strategy."""
        # Fetch the actual strategy source rather than quoting a hardcoded
        # parameter list that drifts out of date and invites the model to
        # "suggest" changes to values that are not the real ones.
        strategy_source = ""
        try:
            info = await self.freqtrade.get_strategy(strategy_name)
            strategy_source = (info or {}).get("code", "") or ""
        except Exception as e:
            self.logger.info("Could not fetch strategy source: %s", e)

        if strategy_source:
            parameters_section = (
                "CURRENT STRATEGY SOURCE (read the real parameter values from this):\n"
                f"```python\n{strategy_source[:6000]}\n```"
            )
        else:
            parameters_section = (
                "CURRENT STRATEGY SOURCE: unavailable. Because you cannot see the "
                "real current values, return an empty suggestions array rather than "
                "guessing what the parameters are."
            )

        prompt = f"""Analyze this Freqtrade strategy's real trading record and suggest parameter optimizations.

STRATEGY: {strategy_name}

MEASURED PERFORMANCE (computed from {analysis.get('total_trades', 0)} real closed trades):
- Win Rate: {analysis.get('win_rate', 0):.1%}
- Total Profit: {analysis.get('total_profit', 0):.2f} CAD
- Max Drawdown: {analysis.get('max_drawdown_pct', 0):.2f}%
- Expectancy per trade: {analysis.get('expectancy', 0):.4f}
- Per-trade Sharpe-style ratio: {analysis.get('per_trade_sharpe', 0):.2f} (not annualised)

DETAILED METRICS:
- Avg Win: {analysis.get('detailed', {}).get('avg_win', 0):.2%}
- Avg Loss: {analysis.get('detailed', {}).get('avg_loss', 0):.2%}
- Profit Factor: {analysis.get('detailed', {}).get('profit_factor', 0):.2f}
- Avg Hold Time: {analysis.get('detailed', {}).get('avg_hold_hours', 0):.1f} hours

EXIT REASONS:
{json.dumps(analysis.get('detailed', {}).get('exit_reasons', {}), indent=2)}

PAIR PERFORMANCE:
{json.dumps(analysis.get('detailed', {}).get('pair_performance', {}), indent=2)}

{parameters_section}

Suggest up to {self.max_suggestions} parameter changes.

RULES:
1. current_value MUST be the value actually present in the source above. If you
   cannot find it there, do not suggest that parameter.
2. Do not promise or estimate returns. Use "expected_impact" only to describe
   direction of the change in risk or trade frequency.
3. A sample of {analysis.get('total_trades', 0)} trades is small. If the record is
   too thin to support a conclusion, return fewer suggestions, or none.
4. Prefer changes that reduce drawdown over changes that chase returns.

Return JSON with a "suggestions" array; each item has:
- parameter: string (full parameter path)
- current_value: any
- suggested_value: any
- reason: string
- confidence: float (0-1)
- expected_impact: "positive"|"neutral"|"negative\""""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a quantitative trading strategy reviewer. You make "
                    "measured, conservative suggestions grounded strictly in the "
                    "data provided, and you say when the evidence is too thin."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                max_tokens=4096,
                temperature=0.4,
                response_format={"type": "json_object"},
            )

            content = response.choices[0]["message"]["content"]
            result = json.loads(content)

            suggestions = []
            for s in result.get("suggestions", []):
                try:
                    suggestions.append(
                        ParameterSuggestion(
                            parameter=s["parameter"],
                            current_value=s.get("current_value"),
                            suggested_value=s.get("suggested_value"),
                            reason=s.get("reason", ""),
                            confidence=float(s.get("confidence", 0.0)),
                            expected_impact=s.get("expected_impact", "neutral"),
                        )
                    )
                except (KeyError, TypeError, ValueError) as e:
                    self.logger.warning("Skipping malformed suggestion: %s", e)

            return suggestions

        except Exception as e:
            # Budget exhaustion is expected; it is not an error condition.
            self.logger.info("AI parameter optimization unavailable: %s", e)
            return []

    def _filter_suggestions(self, suggestions: List[ParameterSuggestion]) -> List[ParameterSuggestion]:
        """Filter and rank suggestions."""
        # Filter by confidence
        filtered = [s for s in suggestions if s.confidence >= 0.5]

        # Sort by confidence * expected impact
        impact_score = {"positive": 1.0, "neutral": 0.5, "negative": 0.0}
        filtered.sort(key=lambda s: s.confidence * impact_score.get(s.expected_impact, 0), reverse=True)

        return filtered[:self.max_suggestions]

    async def apply_suggestions(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Record parameter suggestions as reviewed. **Nothing is applied.**

        The previous implementation logged each suggestion and reported
        ``"status": "logged_for_approval"``, which reads like progress but changes
        nothing - and when ``auto_apply`` was on it stamped the audit entry with
        ``approved_by="auto"``, attributing a human approval decision to a machine.
        That is the worst kind of audit entry: it looks like consent that was
        never given.

        Freqtrade reads strategy parameters at startup and offers no runtime write
        path, and this service cannot write the strategy file either. Applying a
        suggestion is a deliberate manual act: edit the strategy, backtest it,
        push, redeploy.
        """
        if not suggestions:
            return {"applied": False, "count": 0, "message": "No suggestions to record."}

        await self.audit.log(
            plugin="param_optimizer",
            action="suggestions_reviewed",
            user_initiated=True,
            input_data={"suggestions": suggestions},
            output_data={"applied": False},
            decision_reasoning=(
                f"{len(suggestions)} parameter suggestion(s) returned to the operator. "
                "No change was applied: parameters are set in the strategy file and "
                "cannot be modified at runtime."
            ),
            risk_level="medium",
            approved_by=None,
        )

        return {
            "applied": False,
            "count": len(suggestions),
            "status": "instructions_only",
            "message": (
                "These suggestions have NOT been applied and cannot be applied "
                "automatically. To act on one: edit the strategy file, backtest it, "
                "then push and redeploy."
            ),
            "suggestions": suggestions,
        }

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Parameter Optimizer Plugin shut down")