"""
Autonomous Agent Plugin

⚠️ DANGEROUS - DISABLED BY DEFAULT ⚠️

This plugin allows the LLM to make trading decisions directly.
Requires explicit opt-in and human approval for every trade.
Use with extreme caution.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


class TradeAction(Enum):
    """Trade action types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class AgentDecision:
    """Autonomous agent trading decision."""
    pair: str
    action: TradeAction
    confidence: float
    reasoning: str
    position_size_pct: float  # % of available balance
    stoploss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    time_horizon: str = "intraday"  # intraday, swing, position
    risk_level: str = "medium"


class AutonomousAgentPlugin(BasePlugin):
    """
    Autonomous trading agent - DISABLED BY DEFAULT.
    
    WARNING: This plugin can execute real trades.
    Only enable if you fully understand the risks.
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)

        # SAFETY CHECKS - Plugin refuses to initialize if not explicitly configured
        self.explicitly_enabled = config.config.get("explicitly_enabled", False)
        self.require_confirmation = config.config.get("require_confirmation", True)
        self.max_position_pct = config.config.get("max_position_pct", 0.02)  # 2% max per trade
        self.max_daily_trades = config.config.get("max_daily_trades", 10)
        self.allowed_pairs = config.config.get("allowed_pairs", [])
        self.max_drawdown_pct = config.config.get("max_drawdown_pct", 0.10)

        if not self.explicitly_enabled:
            self.logger.warning(
                "AUTONOMOUS AGENT PLUGIN DISABLED - "
                "Set 'explicitly_enabled: true' in config to enable. "
                "This plugin can execute real trades. Use with extreme caution."
            )

        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        self.daily_trade_count = 0
        self.last_reset_date = datetime.utcnow().date()

    async def initialize(self) -> bool:
        """Initialize plugin - fails if not explicitly enabled."""
        if not self.explicitly_enabled:
            self.logger.error("Autonomous Agent Plugin NOT initialized - not explicitly enabled")
            return False

        self.logger.warning("⚠️ AUTONOMOUS AGENT PLUGIN ENABLED - REAL TRADES POSSIBLE ⚠️")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run autonomous trading cycle."""
        if not self.explicitly_enabled:
            return {"status": "disabled", "message": "Plugin not explicitly enabled"}

        # Reset daily counter
        if datetime.utcnow().date() > self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = datetime.utcnow().date()

        if self.daily_trade_count >= self.max_daily_trades:
            return {"status": "rate_limited", "message": f"Daily trade limit reached: {self.max_daily_trades}"}

        # Check drawdown
        status = await self.freqtrade.status()
        if status.profit_pct < -self.max_drawdown_pct * 100:
            return {"status": "drawdown_limit", "message": f"Max drawdown exceeded: {status.profit_pct:.2f}%"}

        # Get market analysis
        market_analysis = await self._get_market_analysis()

        # Generate decisions for each allowed pair
        decisions = []
        for pair in self.allowed_pairs or await self.freqtrade.get_whitelist():
            if self.daily_trade_count >= self.max_daily_trades:
                break

            decision = await self._analyze_pair(pair, market_analysis)
            if decision and decision.action != TradeAction.HOLD:
                decisions.append(decision)

        # Execute decisions (with confirmation)
        executed = []
        for decision in decisions:
            if self.require_confirmation:
                # Log for approval - actual execution would require user confirmation
                await self.audit.log_trade_decision(
                    plugin="autonomous_agent",
                    pair=decision.pair,
                    decision=decision.action.value,
                    reasoning=decision.reasoning,
                    confidence=decision.confidence,
                    market_context=market_analysis.get(decision.pair, {}),
                )
                executed.append({
                    "pair": decision.pair,
                    "action": decision.action.value,
                    "status": "pending_approval",
                    "confidence": decision.confidence,
                })
            else:
                # EXTREMELY DANGEROUS - Auto-execute
                result = await self._execute_decision(decision)
                executed.append(result)

        self.daily_trade_count += len(executed)

        return {
            "status": "completed",
            "decisions": len(decisions),
            "executed": len(executed),
            "daily_count": self.daily_trade_count,
            "details": executed,
        }

    async def _get_market_analysis(self) -> Dict[str, Any]:
        """Get market analysis from Market Analyst plugin or direct."""
        try:
            # Try to get from market analyst plugin
            market_plugin = self.orchestrator.plugins.get("market_analyst")
            if market_plugin:
                return await market_plugin.run()
        except Exception:
            pass

        # Fallback: basic analysis
        analysis = {}
        for pair in self.allowed_pairs or await self.freqtrade.get_whitelist():
            try:
                ticker = await self.freqtrade.get_ticker_snapshot(pair)
                candles = await self.freqtrade.get_candles(pair, "1h", 100)
                analysis[pair] = {
                    "ticker": ticker,
                    "trend": self._simple_trend(candles) if candles else "unknown",
                }
            except Exception:
                analysis[pair] = {"error": "Failed to fetch data"}

        return analysis

    def _simple_trend(self, candles: List) -> str:
        """Simple trend detection."""
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

    async def _analyze_pair(self, pair: str, market_context: Dict) -> Optional[AgentDecision]:
        """Analyze a pair and make trading decision."""
        context = market_context.get(pair, {})
        ticker = context.get("ticker", {})
        trend = context.get("trend", "unknown")

        if "error" in context:
            return None

        # Build decision prompt
        prompt = f"""Make a trading decision for {pair} on Kraken Canada (CAD market).

CURRENT DATA:
- Price: {ticker.get('last', 'N/A')} CAD
- 24h Change: {ticker.get('percentage', 'N/A')}%
- 24h Volume: {ticker.get('baseVolume', 'N/A')}
- Trend: {trend}
- Bid: {ticker.get('bid', 'N/A')}
- Ask: {ticker.get('ask', 'N/A')}

CONSTRAINTS:
- Spot trading only (no margin/futures for Canadian users)
- Max position size: {self.max_position_pct * 100:.1f}% of balance
- Max daily trades: {self.max_daily_trades}
- Current daily trades: {self.daily_trade_count}
- Risk level: Moderate
- Stake currency: CAD

Respond with JSON:
{{
  "action": "buy|sell|hold|close",
  "confidence": 0.0-1.0,
  "reasoning": "detailed explanation",
  "position_size_pct": 0.0-1.0,
  "stoploss_pct": 0.05-0.15,
  "take_profit_pct": 0.02-0.10,
  "time_horizon": "intraday|swing|position",
  "risk_level": "low|medium|high"
}}

Only suggest BUY if confidence > 0.7 and clear setup.
Only suggest SELL/CLOSE if position exists and clear exit signal.
Default to HOLD with explanation."""

        messages = [
            {"role": "system", "content": "You are a disciplined quantitative trader. Prioritize capital preservation. Be conservative."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                max_tokens=1024,
                temperature=0.2,  # Low temperature for consistency
                response_format={"type": "json_object"},
            )

            content = response.choices[0]["message"]["content"]
            result = json.loads(content)

            # Validate decision
            action = TradeAction(result["action"])
            confidence = max(0.0, min(1.0, result["confidence"]))
            position_size = max(0.0, min(self.max_position_pct, result.get("position_size_pct", 0.01)))

            # Safety checks
            if action == TradeAction.BUY and confidence < 0.7:
                action = TradeAction.HOLD
                result["reasoning"] += " [Downgraded to HOLD: confidence < 0.7]"

            if action == TradeAction.BUY and position_size > self.max_position_pct:
                position_size = self.max_position_pct

            return AgentDecision(
                pair=pair,
                action=action,
                confidence=confidence,
                reasoning=result["reasoning"],
                position_size_pct=position_size,
                stoploss_pct=result.get("stoploss_pct"),
                take_profit_pct=result.get("take_profit_pct"),
                time_horizon=result.get("time_horizon", "intraday"),
                risk_level=result.get("risk_level", "medium"),
            )

        except Exception as e:
            self.logger.error(f"Decision failed for {pair}: {e}")
            return None

    async def _execute_decision(self, decision: AgentDecision) -> Dict[str, Any]:
        """Execute a trading decision - EXTREMELY DANGEROUS."""
        # This would use Freqtrade's forcebuy/forcesell API
        # For safety, this is NOT implemented - only logs for approval

        return {
            "pair": decision.pair,
            "action": decision.action.value,
            "status": "logged_for_approval",
            "confidence": decision.confidence,
            "message": "Auto-execution disabled - requires manual approval",
        }

    async def force_decision(self, pair: str, action: str) -> Dict[str, Any]:
        """Force a specific decision (for testing/override)."""
        if not self.explicitly_enabled:
            return {"status": "disabled"}

        # This would be called via NL config plugin with explicit approval
        self.logger.warning(f"FORCED DECISION: {action} {pair}")

        await self.audit.log_trade_decision(
            plugin="autonomous_agent",
            pair=pair,
            decision=action,
            reasoning="Manual override via NL config",
            confidence=1.0,
            market_context={},
            approved_by="user_override",
        )

        return {"status": "logged", "pair": pair, "action": action}

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Autonomous Agent Plugin shut down")