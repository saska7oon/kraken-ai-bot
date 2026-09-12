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

        # Get current strategy and performance
        strategy_info = await self.freqtrade.get_strategy()
        performance = await self.freqtrade.get_performance()
        trades = await self.freqtrade.get_closed_trades(limit=200)

        if not performance:
            return {"status": "no_performance_data"}

        # Analyze performance
        analysis = self._analyze_performance(performance, trades)

        # Generate suggestions via LLM
        suggestions = await self._generate_suggestions(strategy_info, analysis)

        # Filter and rank suggestions
        filtered = self._filter_suggestions(suggestions)

        # Log to audit
        await self.audit.log(
            plugin="param_optimizer",
            action="parameter_optimization",
            user_initiated=kwargs.get("force", False),
            input_data={
                "trigger": trigger_reason,
                "strategy": strategy_info.get("strategy", "unknown"),
                "performance_summary": analysis,
            },
            output_data={"suggestions": [asdict(s) for s in filtered]},
            decision_reasoning=f"Generated {len(filtered)} parameter suggestions based on {trigger_reason}",
            risk_level="medium",
        )

        return {
            "status": "completed",
            "trigger": trigger_reason,
            "strategy": strategy_info.get("strategy"),
            "analysis": analysis,
            "suggestions": [asdict(s) for s in filtered],
            "auto_apply": self.auto_apply,
        }

    async def _check_trigger(self) -> tuple:
        """Check if optimization should run."""
        if self.trigger == "performance_drop":
            perf = await self.freqtrade.get_performance()
            if perf:
                avg_sharpe = sum(p.sharpe_ratio for p in perf) / len(perf) if perf else 0
                if avg_sharpe < self.performance_threshold:
                    return True, f"Sharpe ratio below threshold: {avg_sharpe:.2f} < {self.performance_threshold}"

        elif self.trigger == "schedule":
            # Handled by scheduler
            return True, "Scheduled run"

        elif self.trigger == "trade_count":
            trades = await self.freqtrade.get_closed_trades(limit=1)
            # Would need to track trade count since last optimization
            pass

        return False, "Condition not met"

    def _analyze_performance(
        self,
        performance: List,
        trades: List,
    ) -> Dict[str, Any]:
        """Analyze trading performance."""
        if not performance:
            return {}

        p = performance[0]  # Main strategy

        # Trade analysis
        winning_trades = [t for t in trades if t.profit_ratio and t.profit_ratio > 0]
        losing_trades = [t for t in trades if t.profit_ratio and t.profit_ratio <= 0]

        avg_win = sum(t.profit_ratio for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.profit_ratio for t in losing_trades) / len(losing_trades) if losing_trades else 0

        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

        # Exit reason breakdown
        exit_reasons = {}
        for t in trades:
            if t.exit_reason:
                exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

        # Pair performance
        pair_performance = {}
        for t in trades:
            if t.pair not in pair_performance:
                pair_performance[t.pair] = {"wins": 0, "losses": 0, "total_profit": 0}
            if t.profit_ratio and t.profit_ratio > 0:
                pair_performance[t.pair]["wins"] += 1
            else:
                pair_performance[t.pair]["losses"] += 1
            pair_performance[t.pair]["total_profit"] += t.profit_abs or 0

        # Time analysis
        hold_times = []
        for t in trades:
            if t.close_date and t.open_date:
                hold_time = (t.close_date - t.open_date).total_seconds() / 3600  # hours
                hold_times.append(hold_time)

        avg_hold = sum(hold_times) / len(hold_times) if hold_times else 0

        return {
            "sharpe_ratio": p.sharpe_ratio,
            "win_rate": p.win_rate,
            "total_trades": p.total_trades,
            "total_profit": p.total_profit,
            "max_drawdown": p.max_drawdown,
            "expectancy": p.expectancy,
            "detailed": {
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
                "exit_reasons": exit_reasons,
                "pair_performance": pair_performance,
                "avg_hold_hours": avg_hold,
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
            },
        }

    async def _generate_suggestions(
        self,
        strategy_info: Dict,
        analysis: Dict,
    ) -> List[ParameterSuggestion]:
        """Generate parameter suggestions using LLM."""

        strategy_name = strategy_info.get("strategy", "ModerateMultiPairStrategy")

        prompt = f"""Analyze this Freqtrade strategy performance and suggest parameter optimizations.

STRATEGY: {strategy_name}

PERFORMANCE SUMMARY:
- Sharpe Ratio: {analysis.get('sharpe_ratio', 0):.2f}
- Win Rate: {analysis.get('win_rate', 0):.1f}%
- Total Trades: {analysis.get('total_trades', 0)}
- Total Profit: {analysis.get('total_profit', 0):.2f} CAD
- Max Drawdown: {analysis.get('max_drawdown', 0):.2f}%
- Expectancy: {analysis.get('expectancy', 0):.4f}

DETAILED METRICS:
- Avg Win: {analysis['detailed'].get('avg_win', 0):.2%}
- Avg Loss: {analysis['detailed'].get('avg_loss', 0):.2%}
- Profit Factor: {analysis['detailed'].get('profit_factor', 0):.2f}
- Avg Hold Time: {analysis['detailed'].get('avg_hold_hours', 0):.1f} hours

EXIT REASONS:
{json.dumps(analysis['detailed'].get('exit_reasons', {}), indent=2)}

PAIR PERFORMANCE:
{json.dumps(analysis['detailed'].get('pair_performance', {}), indent=2)}

CURRENT STRATEGY PARAMETERS (from ModerateMultiPairStrategy):
- buy_rsi_enabled: True, buy_rsi_value: 30
- sell_rsi_enabled: True, sell_rsi_value: 70
- buy_ema_short: 9, buy_ema_long: 21
- buy_bb_enabled: True, buy_bb_std: 2.0
- sell_bb_enabled: True
- buy_macd_enabled: True, sell_macd_enabled: True
- volume_enabled: True, volume_factor: 1.5
- adx_enabled: True, adx_value: 25
- stoploss: -0.08
- trailing_stop: True, trailing_stop_positive: 0.02, trailing_stop_positive_offset: 0.03
- minimal_roi: {{"0": 0.04, "30": 0.02, "60": 0.01, "120": 0}}

Suggest up to {self.max_suggestions} parameter changes to improve performance.
Focus on:
1. Improving win rate without sacrificing expectancy
2. Reducing max drawdown
3. Optimizing for current market regime
4. Pair-specific adjustments

Return JSON with "suggestions" array, each with:
- parameter: string (full parameter path)
- current_value: any
- suggested_value: any
- reason: string
- confidence: float (0-1)
- expected_impact: "positive"|"neutral"|"negative"""

        messages = [
            {"role": "system", "content": "You are an expert quantitative trading strategy optimizer. Suggest specific, actionable parameter changes."},
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
                suggestions.append(ParameterSuggestion(
                    parameter=s["parameter"],
                    current_value=s["current_value"],
                    suggested_value=s["suggested_value"],
                    reason=s["reason"],
                    confidence=s["confidence"],
                    expected_impact=s["expected_impact"],
                ))

            return suggestions

        except Exception as e:
            self.logger.error(f"LLM parameter optimization failed: {e}")
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
        """Apply parameter suggestions to Freqtrade config."""
        if not self.auto_apply:
            return {"status": "requires_approval", "message": "Auto-apply disabled"}

        results = []
        for s in suggestions:
            try:
                # Update Freqtrade config
                # This would require knowing the exact config structure
                # For now, log the intended change
                await self.audit.log_config_change(
                    plugin="param_optimizer",
                    config_changes={s["parameter"]: s["suggested_value"]},
                    reasoning=s["reason"],
                    user_initiated=False,
                    approved_by="auto" if self.auto_apply else None,
                )
                results.append({"parameter": s["parameter"], "status": "logged_for_approval"})
            except Exception as e:
                results.append({"parameter": s["parameter"], "status": "failed", "error": str(e)})

        return {"status": "completed", "results": results}

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Parameter Optimizer Plugin shut down")