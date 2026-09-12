"""
Market Analyst Plugin

Analyzes market conditions, news sentiment, fear/greed index, and on-chain data
to provide trading insights and regime detection.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from ai_orchestrator.core.plugin_manager import BasePlugin, PluginConfig

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Market regime classification."""
    regime: str  # trending_up, trending_down, ranging, volatile, uncertain
    confidence: float
    indicators: Dict[str, Any]
    description: str


@dataclass
class SentimentData:
    """Sentiment analysis result."""
    source: str
    sentiment: str  # bullish, bearish, neutral
    score: float  # -1 to 1
    key_topics: List[str]
    timestamp: str


class MarketAnalystPlugin(BasePlugin):
    """
    Analyzes market conditions and provides regime detection + sentiment.
    """

    def __init__(self, config: PluginConfig, orchestrator):
        super().__init__(config, orchestrator)
        self.openrouter = orchestrator.openrouter_client
        self.freqtrade = orchestrator.freqtrade_client
        self.audit = orchestrator.audit_logger

        # Config
        self.sources = config.config.get("sources", ["technical", "fear_greed"])
        self.pairs_to_analyze = config.config.get("pairs", [])  # Empty = all whitelist
        self.regime_threshold = config.config.get("regime_threshold", 0.6)

    async def initialize(self) -> bool:
        """Initialize plugin."""
        self.logger.info("Market Analyst Plugin initialized")
        return True

    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run market analysis cycle."""
        self.logger.info("Running market analysis")

        # Get pairs to analyze
        if self.pairs_to_analyze:
            pairs = self.pairs_to_analyze
        else:
            pairs = await self.freqtrade.get_whitelist()

        results = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pairs_analyzed": len(pairs),
            "regime": None,
            "sentiment": [],
            "pair_analysis": {},
            "alerts": [],
        }

        # Analyze each pair
        for pair in pairs:
            try:
                analysis = await self._analyze_pair(pair)
                results["pair_analysis"][pair] = analysis
            except Exception as e:
                self.logger.warning(f"Failed to analyze {pair}: {e}")
                results["pair_analysis"][pair] = {"error": str(e)}

        # Determine overall regime
        regime = await self._determine_regime(results["pair_analysis"])
        results["regime"] = asdict(regime)

        # Get sentiment from LLM
        if "news" in self.sources or "fear_greed" in self.sources:
            sentiment = await self._get_sentiment_analysis(results)
            results["sentiment"] = [asdict(s) for s in sentiment]

        # Generate alerts
        results["alerts"] = self._generate_alerts(results)

        # Log to audit
        await self.audit.log(
            plugin="market_analyst",
            action="market_analysis",
            user_initiated=False,
            input_data={"pairs": pairs, "sources": self.sources},
            output_data=results,
            decision_reasoning=f"Market regime: {regime.regime} ({regime.confidence:.0%})",
            risk_level="low",
        )

        return results

    async def _analyze_pair(self, pair: str) -> Dict[str, Any]:
        """Comprehensive technical analysis for a pair."""
        # Get multiple timeframes
        candles_5m = await self.freqtrade.get_candles(pair, "5m", 200)
        candles_1h = await self.freqtrade.get_candles(pair, "1h", 200)
        candles_4h = await self.freqtrade.get_candles(pair, "4h", 100)
        candles_1d = await self.freqtrade.get_candles(pair, "1d", 100)
        ticker = await self.freqtrade.get_ticker(pair)

        ticker_data = ticker.get(pair, {}) if ticker else {}

        return {
            "pair": pair,
            "price": ticker_data.get("last", 0),
            "change_24h": ticker_data.get("percentage", 0),
            "volume_24h": ticker_data.get("baseVolume", 0),
            "bid": ticker_data.get("bid", 0),
            "ask": ticker_data.get("ask", 0),
            "spread_pct": ((ticker_data.get("ask", 0) - ticker_data.get("bid", 0)) / ticker_data.get("bid", 1)) * 100 if ticker_data.get("bid") else 0,
            "timeframes": {
                "5m": self._analyze_timeframe(candles_5m, "5m"),
                "1h": self._analyze_timeframe(candles_1h, "1h"),
                "4h": self._analyze_timeframe(candles_4h, "4h"),
                "1d": self._analyze_timeframe(candles_1d, "1d"),
            },
            "support_resistance": self._find_support_resistance(candles_1d),
            "volume_profile": self._analyze_volume(candles_1h),
        }

    def _analyze_timeframe(self, candles: List, timeframe: str) -> Dict[str, Any]:
        """Analyze a single timeframe."""
        if len(candles) < 50:
            return {"status": "insufficient_data"}

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        current = closes[-1]

        # Moving averages
        sma_20 = sum(closes[-20:]) / 20
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else sma_20
        sma_200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else sma_50

        ema_9 = self._calculate_ema(closes, 9)
        ema_21 = self._calculate_ema(closes, 21)

        # RSI
        rsi = self._calculate_rsi(closes, 14)

        # MACD
        macd, signal, hist = self._calculate_macd(closes)

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger(closes, 20, 2)
        bb_position = (current - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

        # ATR
        atr = self._calculate_atr(highs, lows, closes, 14)
        atr_pct = atr / current * 100 if current > 0 else 0

        # Trend
        if current > ema_9 > ema_21 > sma_50:
            trend = "strong_bullish"
        elif current > ema_9 > ema_21:
            trend = "bullish"
        elif current < ema_9 < ema_21 < sma_50:
            trend = "strong_bearish"
        elif current < ema_9 < ema_21:
            trend = "bearish"
        else:
            trend = "neutral"

        # Momentum
        momentum_1h = (current - closes[-12]) / closes[-12] * 100 if len(closes) >= 12 else 0
        momentum_4h = (current - closes[-4]) / closes[-4] * 100 if len(closes) >= 4 else 0
        momentum_1d = (current - closes[-1]) / closes[-1] * 100 if len(closes) >= 1 else 0

        return {
            "trend": trend,
            "price": current,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "ema_9": ema_9,
            "ema_21": ema_21,
            "rsi": rsi,
            "macd": {"macd": macd, "signal": signal, "histogram": hist},
            "bollinger": {"upper": bb_upper, "middle": bb_middle, "lower": bb_lower, "position": bb_position},
            "atr": atr,
            "atr_pct": atr_pct,
            "momentum": {"1h": momentum_1h, "4h": momentum_4h, "1d": momentum_1d},
            "volume_trend": "increasing" if volumes[-1] > sum(volumes[-20:]) / 20 else "decreasing",
        }

    def _calculate_ema(self, values: List[float], period: int) -> float:
        """Calculate EMA."""
        if len(values) < period:
            return sum(values) / len(values) if values else 0
        k = 2 / (period + 1)
        ema = sum(values[-period:]) / period
        for v in values[-period+1:]:
            ema = v * k + ema * (1 - k)
        return ema

    def _calculate_rsi(self, values: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(values) < period + 1:
            return 50.0

        gains = []
        losses = []
        for i in range(1, period + 1):
            change = values[-i] - values[-i-1]
            if change > 0:
                gains.append(change)
            else:
                losses.append(abs(change))

        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, values: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD."""
        ema_fast = self._calculate_ema(values, fast)
        ema_slow = self._calculate_ema(values, slow)
        macd = ema_fast - ema_slow

        # For signal, we'd need historical MACD values - simplified
        signal_line = macd * 0.9  # Approximation
        histogram = macd - signal_line

        return macd, signal_line, histogram

    def _calculate_bollinger(self, values: List[float], period: int = 20, std_dev: int = 2):
        """Calculate Bollinger Bands."""
        if len(values) < period:
            return values[-1], values[-1], values[-1]

        recent = values[-period:]
        middle = sum(recent) / period
        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return upper, middle, lower

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calculate ATR."""
        if len(closes) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, period + 1):
            high = highs[-i]
            low = lows[-i]
            prev_close = closes[-i-1] if i < len(closes) else closes[-i]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges)

    def _find_support_resistance(self, candles: List) -> Dict[str, List[float]]:
        """Find key support and resistance levels."""
        if len(candles) < 20:
            return {"support": [], "resistance": []}

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        # Simple pivot points
        resistance = []
        support = []

        for i in range(2, len(highs) - 2):
            # Resistance (local high)
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance.append(highs[i])
            # Support (local low)
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support.append(lows[i])

        # Keep only significant levels (tested multiple times)
        current_price = candles[-1].close

        resistance = sorted([r for r in resistance if r > current_price])[:5]
        support = sorted([s for s in support if s < current_price], reverse=True)[:5]

        return {"support": support, "resistance": resistance}

    def _analyze_volume(self, candles: List) -> Dict[str, Any]:
        """Analyze volume profile."""
        if len(candles) < 20:
            return {"status": "insufficient_data"}

        volumes = [c.volume for c in candles]
        avg_volume = sum(volumes[-20:]) / 20
        current_volume = volumes[-1]

        # Volume trend
        recent_avg = sum(volumes[-5:]) / 5
        older_avg = sum(volumes[-20:-5]) / 15 if len(volumes) >= 20 else recent_avg

        return {
            "current": current_volume,
            "average_20": avg_volume,
            "ratio": current_volume / avg_volume if avg_volume > 0 else 1,
            "trend": "increasing" if recent_avg > older_avg else "decreasing",
            "anomaly": current_volume > avg_volume * 3,
        }

    async def _determine_regime(self, pair_analyses: Dict[str, Any]) -> MarketRegime:
        """Determine overall market regime."""
        if not pair_analyses:
            return MarketRegime(
                regime="uncertain",
                confidence=0.0,
                indicators={},
                description="No data available",
            )

        # Count trends across pairs and timeframes
        trend_counts = {"bullish": 0, "bearish": 0, "neutral": 0, "strong_bullish": 0, "strong_bearish": 0}
        volatility_sum = 0
        volatility_count = 0

        for pair, analysis in pair_analyses.items():
            if "error" in analysis:
                continue

            for tf, tf_data in analysis.get("timeframes", {}).items():
                if "trend" in tf_data:
                    trend = tf_data["trend"]
                    if trend in trend_counts:
                        trend_counts[trend] += 1

            # Average volatility
            for tf, tf_data in analysis.get("timeframes", {}).items():
                if "atr_pct" in tf_data:
                    volatility_sum += tf_data["atr_pct"]
                    volatility_count += 1

        avg_volatility = volatility_sum / volatility_count if volatility_count > 0 else 0
        total_signals = sum(trend_counts.values())

        if total_signals == 0:
            return MarketRegime(
                regime="uncertain",
                confidence=0.0,
                indicators={"trend_counts": trend_counts},
                description="Insufficient signals",
            )

        # Determine regime
        bullish_total = trend_counts["bullish"] + trend_counts["strong_bullish"] * 2
        bearish_total = trend_counts["bearish"] + trend_counts["strong_bearish"] * 2

        bullish_pct = bullish_total / (total_signals + trend_counts["strong_bullish"] + trend_counts["strong_bearish"])
        bearish_pct = bearish_total / (total_signals + trend_counts["strong_bullish"] + trend_counts["strong_bearish"])

        if bullish_pct > 0.6 and avg_volatility < 3:
            regime = "trending_up"
            confidence = bullish_pct
            desc = f"Strong uptrend across {bullish_pct:.0%} of signals, low volatility"
        elif bearish_pct > 0.6 and avg_volatility < 3:
            regime = "trending_down"
            confidence = bearish_pct
            desc = f"Strong downtrend across {bearish_pct:.0%} of signals, low volatility"
        elif avg_volatility > 5:
            regime = "volatile"
            confidence = min(avg_volatility / 10, 0.9)
            desc = f"High volatility ({avg_volatility:.1f}% ATR), choppy conditions"
        elif abs(bullish_pct - bearish_pct) < 0.2:
            regime = "ranging"
            confidence = 1 - abs(bullish_pct - bearish_pct)
            desc = f"Mixed signals, range-bound market"
        elif bullish_pct > bearish_pct:
            regime = "trending_up"
            confidence = bullish_pct
            desc = f"Moderate uptrend ({bullish_pct:.0%} bullish)"
        else:
            regime = "trending_down"
            confidence = bearish_pct
            desc = f"Moderate downtrend ({bearish_pct:.0%} bearish)"

        return MarketRegime(
            regime=regime,
            confidence=confidence,
            indicators={
                "trend_counts": trend_counts,
                "avg_volatility": avg_volatility,
                "bullish_pct": bullish_pct,
                "bearish_pct": bearish_pct,
            },
            description=desc,
        )

    async def _get_sentiment_analysis(self, analysis_results: Dict) -> List[SentimentData]:
        """Get sentiment analysis via LLM."""
        # Build context for LLM
        context = {
            "regime": analysis_results["regime"],
            "pairs": analysis_results["pair_analysis"],
            "timestamp": analysis_results["timestamp"],
        }

        prompt = f"""Analyze the current cryptocurrency market sentiment for Canadian traders on Kraken.

MARKET REGIME: {context['regime']['regime']} (confidence: {context['regime']['confidence']:.0%})
DESCRIPTION: {context['regime']['description']}

KEY PAIRS (CAD markets):
{json.dumps({k: v.get('price', 0) for k, v in context['pairs'].items() if 'price' in v}, indent=2)}

Provide sentiment analysis from these perspectives:
1. Technical sentiment (based on charts/indicators)
2. Fear & Greed context (crypto fear/greed index)
3. Macro factors (CAD/USD, BTC dominance, regulatory)
4. Canadian-specific factors (Kraken Canada restrictions, tax implications)

Return JSON with "sentiments" array, each with:
- source: string
- sentiment: "bullish"|"bearish"|"neutral"
- score: float (-1 to 1)
- key_topics: array of strings
- timestamp: ISO string"""

        messages = [
            {"role": "system", "content": "You are a professional crypto market analyst specializing in Canadian markets."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.openrouter.chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.5,
                response_format={"type": "json_object"},
            )

            content = response.choices[0]["message"]["content"]
            result = json.loads(content)
            sentiments = []

            for s in result.get("sentiments", []):
                sentiments.append(SentimentData(
                    source=s["source"],
                    sentiment=s["sentiment"],
                    score=s["score"],
                    key_topics=s["key_topics"],
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))

            return sentiments

        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return []

    def _generate_alerts(self, results: Dict) -> List[Dict[str, Any]]:
        """Generate alerts based on analysis."""
        alerts = []

        regime = results["regime"]
        if regime["regime"] == "volatile" and regime["confidence"] > 0.7:
            alerts.append({
                "type": "high_volatility",
                "severity": "warning",
                "message": f"High volatility regime detected: {regime['description']}",
                "action": "Consider reducing position sizes, tightening stoplosses",
            })

        if regime["regime"] in ["trending_up", "trending_down"] and regime["confidence"] > 0.8:
            alerts.append({
                "type": "strong_trend",
                "severity": "info",
                "message": f"Strong {regime['regime']} detected: {regime['description']}",
                "action": "Trend-following strategies favored",
            })

        # Check for pair-specific alerts
        for pair, analysis in results["pair_analysis"].items():
            if "error" in analysis:
                continue

            # Volume anomaly
            vol = analysis.get("volume_profile", {})
            if vol.get("anomaly"):
                alerts.append({
                    "type": "volume_spike",
                    "severity": "info",
                    "pair": pair,
                    "message": f"Unusual volume on {pair}: {vol['ratio']:.1f}x average",
                    "action": "Monitor for breakout/breakdown",
                })

            # Spread warning
            if analysis.get("spread_pct", 0) > 0.5:
                alerts.append({
                    "type": "wide_spread",
                    "severity": "warning",
                    "pair": pair,
                    "message": f"Wide spread on {pair}: {analysis['spread_pct']:.2f}%",
                    "action": "Avoid market orders, use limits",
                })

        return alerts

    async def shutdown(self):
        """Cleanup."""
        self.logger.info("Market Analyst Plugin shut down")