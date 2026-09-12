"""
Strategy Generator Plugin

Generates new trading strategies using LLM based on market conditions,
backtest results, and performance analysis.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

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

        # Strategy templates directory
        self.templates_dir = Path("/app/config/strategies/templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Generated strategies directory
        self.generated_dir = Path("/app/config/strategies/generated")
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        # Config
        self.max_strategies = config.config.get("max_strategies", 3)
        self.risk_profile = config.config.get("risk_profile", "moderate")
        self.min_backtest_sharpe = config.config.get("min_backtest_sharpe", 1.0)
        self.min_backtest_trades = config.config.get("min_backtest_trades", 50)

    async def initialize(self) -> bool:
        """Initialize plugin."""
        self.logger.info("Strategy Generator Plugin initialized")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Generate new strategies based on current market conditions.
        """
        self.logger.info("Running strategy generation cycle")

        # Get market context
        market_context = await self._get_market_context()

        # Get performance of current strategies
        performance = await self._get_strategy_performance()

        # Generate strategy proposals
        proposals = await self._generate_proposals(market_context, performance)

        # Filter and validate
        validated = []
        for proposal in proposals:
            if await self._validate_proposal(proposal):
                validated.append(proposal)

        # Select best proposals
        selected = validated[:self.max_strategies]

        # Save proposals for review
        saved = []
        for proposal in selected:
            filepath = await self._save_proposal(proposal)
            saved.append(str(filepath))

        # Log to audit
        await self.audit.log_strategy_generation(
            strategy_code=json.dumps([p["code"] for p in selected]),
            pair="multi",
            reasoning=f"Generated {len(selected)} strategies based on market analysis",
            backtest_results={"proposals": len(proposals), "validated": len(validated)},
        )

        return {
            "proposals_generated": len(proposals),
            "validated": len(validated),
            "selected": len(selected),
            "saved_files": saved,
            "market_context_summary": market_context.get("summary", ""),
        }

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
                ticker = await self.freqtrade.get_ticker(pair)
                candles = await self.freqtrade.get_candles(pair, "1h", 100)

                if candles and ticker:
                    pair_data = {
                        "pair": pair,
                        "price": ticker.get(pair, {}).get("last", 0),
                        "change_24h": ticker.get(pair, {}).get("percentage", 0),
                        "volume_24h": ticker.get(pair, {}).get("baseVolume", 0),
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
        """Get current strategy performance."""
        try:
            perf = await self.freqtrade.get_performance()
            return {
                "strategies": [
                    {
                        "name": p.strategy,
                        "win_rate": p.win_rate,
                        "total_profit": p.total_profit,
                        "sharpe": p.sharpe_ratio,
                        "max_drawdown": p.max_drawdown,
                        "total_trades": p.total_trades,
                    }
                    for p in perf
                ],
                "overall": {
                    "total_profit": sum(p.total_profit for p in perf),
                    "avg_win_rate": sum(p.win_rate for p in perf) / len(perf) if perf else 0,
                },
            }
        except Exception as e:
            self.logger.warning(f"Failed to get performance: {e}")
            return {"strategies": [], "overall": {}}

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

    async def _validate_proposal(self, proposal: Dict[str, Any]) -> bool:
        """Validate a strategy proposal."""
        required_fields = ["name", "description", "code", "parameters", "risk_level", "suitable_pairs"]
        for field in required_fields:
            if field not in proposal:
                self.logger.warning(f"Proposal missing field: {field}")
                return False

        # Check code syntax
        try:
            compile(proposal["code"], "<string>", "exec")
        except SyntaxError as e:
            self.logger.warning(f"Proposal has syntax error: {e}")
            return False

        # Check risk level matches profile
        if proposal["risk_level"] not in ["low", "moderate", "high"]:
            return False

        return True

    async def _save_proposal(self, proposal: Dict[str, Any]) -> Path:
        """Save strategy proposal to file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{proposal['name']}_{timestamp}.py"
        filepath = self.generated_dir / filename

        # Add header with metadata
        header = f'''"""
Auto-generated strategy: {proposal['name']}
Generated: {datetime.utcnow().isoformat()}Z
Description: {proposal['description']}
Risk Level: {proposal['risk_level']}
Suitable Pairs: {', '.join(proposal['suitable_pairs'])}
Parameters: {json.dumps(proposal['parameters'], indent=2)}

REVIEW REQUIRED BEFORE USE - This strategy has not been backtested.
"""

'''
        full_code = header + proposal["code"]

        async with aiofiles.open(filepath, "w") as f:
            await f.write(full_code)

        self.logger.info(f"Saved strategy proposal: {filepath}")
        return filepath

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Strategy Generator Plugin shut down")