"""
Moderate Multi-Pair Strategy for Kraken Canada (CAD Markets)

Designed for $1000 CAD starting capital, moderate risk profile.
Trades: BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD

Strategy Logic:
- Trend following with EMA crossover (9/21) + RSI filter
- Bollinger Bands for mean reversion entries
- MACD for momentum confirmation
- Volume confirmation on entries
- Dynamic position sizing via Freqtrade Edge
"""

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, CategoricalParameter
from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class ModerateMultiPairStrategy(IStrategy):
    """
    Moderate risk multi-pair strategy for CAD markets on Kraken Canada.
    """

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for moderate risk
    minimal_roi = {
        "0": 0.04,
        "30": 0.02,
        "60": 0.01,
        "120": 0
    }

    # Stoploss
    stoploss = -0.08

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = False

    # Timeframe
    timeframe = "5m"

    # Process only new candles
    process_only_new_candles = True

    # These values can be overridden in the config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before strategy produces valid signals
    startup_candle_count: int = 200

    # Order types
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_on_exchange_interval": 60,
        "stoploss_on_exchange_limit_ratio": 0.99,
    }

    # Time in force
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }

    # Plot configuration for FreqUI
    plot_config = {
        "main_plot": {
            "ema_9": {"color": "#2962FF"},
            "ema_21": {"color": "#FF6D00"},
            "ema_50": {"color": "#00C853"},
            "ema_200": {"color": "#D50000"},
            "bb_lowerband": {"color": "#757575"},
            "bb_middleband": {"color": "#757575"},
            "bb_upperband": {"color": "#757575"},
        },
        "subplots": {
            "rsi": {
                "rsi": {"color": "#AA00FF"},
                "rsi_overbought": {"color": "#FF0000"},
                "rsi_oversold": {"color": "#00FF00"},
            },
            "macd": {
                "macd": {"color": "#2962FF"},
                "macdsignal": {"color": "#FF6D00"},
                "macdhist": {"color": "#00C853"},
            },
            "volume": {
                "volume": {"color": "#424242"},
            },
        },
    }

    # ============================================================
    # HYPEROPT PARAMETERS (Can be optimized)
    # ============================================================

    # RSI parameters
    buy_rsi_enabled = CategoricalParameter([True, False], default=True, space="buy", optimize=True)
    buy_rsi_value = IntParameter(20, 40, default=30, space="buy", optimize=True)
    sell_rsi_enabled = CategoricalParameter([True, False], default=True, space="sell", optimize=True)
    sell_rsi_value = IntParameter(60, 80, default=70, space="sell", optimize=True)

    # EMA parameters
    buy_ema_short = IntParameter(5, 15, default=9, space="buy", optimize=True)
    buy_ema_long = IntParameter(18, 30, default=21, space="buy", optimize=True)

    # Bollinger Bands parameters
    buy_bb_enabled = CategoricalParameter([True, False], default=True, space="buy", optimize=True)
    buy_bb_std = DecimalParameter(1.5, 2.5, default=2.0, space="buy", optimize=True)
    sell_bb_enabled = CategoricalParameter([True, False], default=True, space="sell", optimize=True)

    # MACD parameters
    buy_macd_enabled = CategoricalParameter([True, False], default=True, space="buy", optimize=True)
    sell_macd_enabled = CategoricalParameter([True, False], default=True, space="sell", optimize=True)

    # Volume parameters
    volume_enabled = CategoricalParameter([True, False], default=True, space="buy", optimize=True)
    volume_factor = DecimalParameter(1.0, 3.0, default=1.5, space="buy", optimize=True)

    # Trend filter (ADX)
    adx_enabled = CategoricalParameter([True, False], default=True, space="buy", optimize=True)
    adx_value = IntParameter(20, 35, default=25, space="buy", optimize=True)

    # ============================================================
    # INFORMATIVE PAIRS (Optional - for correlation filtering)
    # ============================================================
    def informative_pairs(self) -> List[Tuple[str, str]]:
        """
        Define additional informative pairs for correlation analysis.
        Returns list of (pair, timeframe) tuples.
        """
        # We could add BTC/CAD as informative for all pairs
        # but for simplicity, we'll skip this for now
        return []

    # ============================================================
    # POPULATE INDICATORS
    # ============================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several technical analysis indicators to the dataframe.
        """

        # ---------------------------------------------------------
        # RSI
        # ---------------------------------------------------------
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi_overbought"] = 70
        dataframe["rsi_oversold"] = 30

        # ---------------------------------------------------------
        # EMAs
        # ---------------------------------------------------------
        dataframe["ema_9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema_21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)

        # EMA crossover signals
        dataframe["ema_cross_up"] = qtpylib.crossed_above(
            dataframe["ema_9"], dataframe["ema_21"]
        )
        dataframe["ema_cross_down"] = qtpylib.crossed_below(
            dataframe["ema_9"], dataframe["ema_21"]
        )

        # ---------------------------------------------------------
        # Bollinger Bands
        # ---------------------------------------------------------
        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lowerband"] = bb["lower"]
        dataframe["bb_middleband"] = bb["mid"]
        dataframe["bb_upperband"] = bb["upper"]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lowerband"]) / (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        )
        dataframe["bb_width"] = (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        ) / dataframe["bb_middleband"]

        # ---------------------------------------------------------
        # MACD
        # ---------------------------------------------------------
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]
        dataframe["macd_cross_up"] = qtpylib.crossed_above(
            dataframe["macd"], dataframe["macdsignal"]
        )
        dataframe["macd_cross_down"] = qtpylib.crossed_below(
            dataframe["macd"], dataframe["macdsignal"]
        )

        # ---------------------------------------------------------
        # ADX (Trend Strength)
        # ---------------------------------------------------------
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["di_plus"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["di_minus"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # ---------------------------------------------------------
        # Volume
        # ---------------------------------------------------------
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean"]

        # ---------------------------------------------------------
        # ATR (Volatility)
        # ---------------------------------------------------------
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_percent"] = dataframe["atr"] / dataframe["close"] * 100

        # ---------------------------------------------------------
        # Stochastic RSI
        # ---------------------------------------------------------
        stoch_rsi = ta.STOCHRSI(dataframe, timeperiod=14, fastk_period=3, fastd_period=3)
        dataframe["stoch_rsi_k"] = stoch_rsi["fastk"]
        dataframe["stoch_rsi_d"] = stoch_rsi["fastd"]

        # ---------------------------------------------------------
        # Pair-specific adjustments
        # ---------------------------------------------------------
        pair = metadata.get("pair", "")
        if pair:
            # Adjust parameters per pair volatility
            if "BTC" in pair:
                dataframe["pair_volatility_factor"] = 1.0
            elif "ETH" in pair:
                dataframe["pair_volatility_factor"] = 1.1
            elif "SOL" in pair:
                dataframe["pair_volatility_factor"] = 1.5
            elif "XRP" in pair:
                dataframe["pair_volatility_factor"] = 1.3
            else:
                dataframe["pair_volatility_factor"] = 1.0

        return dataframe

    # ============================================================
    # ENTRY SIGNALS
    # ============================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Generate buy signals based on multiple confluence factors.
        """

        conditions = []

        # ---------------------------------------------------------
        # Condition 1: Trend Following (EMA Crossover + RSI)
        # ---------------------------------------------------------
        trend_conditions = []

        if self.buy_ema_short.value and self.buy_ema_long.value:
            # EMA crossover (short crosses above long)
            ema_cross = qtpylib.crossed_above(
                ta.EMA(dataframe, timeperiod=self.buy_ema_short.value),
                ta.EMA(dataframe, timeperiod=self.buy_ema_long.value)
            )
            trend_conditions.append(ema_cross)

        if self.buy_rsi_enabled.value:
            # RSI not overbought
            rsi_ok = dataframe["rsi"] < self.buy_rsi_value.value
            trend_conditions.append(rsi_ok)

        if self.adx_enabled.value:
            # ADX shows trend strength
            adx_ok = (dataframe["adx"] > self.adx_value.value) & (dataframe["di_plus"] > dataframe["di_minus"])
            trend_conditions.append(adx_ok)

        if self.buy_macd_enabled.value:
            # MACD bullish crossover
            macd_cross = qtpylib.crossed_above(dataframe["macd"], dataframe["macdsignal"])
            trend_conditions.append(macd_cross)

        if self.volume_enabled.value:
            # Volume confirmation
            volume_ok = dataframe["volume_ratio"] > self.volume_factor.value
            trend_conditions.append(volume_ok)

        # Combine trend conditions (ALL must be true)
        if trend_conditions:
            conditions.append(trend_conditions)

        # ---------------------------------------------------------
        # Condition 2: Mean Reversion (Bollinger Bands + RSI)
        # ---------------------------------------------------------
        mr_conditions = []

        if self.buy_bb_enabled.value:
            # Price near lower Bollinger Band
            bb_oversold = dataframe["bb_percent"] < 0.1
            mr_conditions.append(bb_oversold)

            # RSI oversold
            if self.buy_rsi_enabled.value:
                rsi_oversold = dataframe["rsi"] < 35
                mr_conditions.append(rsi_oversold)

            # MACD histogram turning up
            if self.buy_macd_enabled.value:
                macd_hist_up = dataframe["macdhist"] > dataframe["macdhist"].shift(1)
                mr_conditions.append(macd_hist_up)

            # Volume spike
            if self.volume_enabled.value:
                volume_spike = dataframe["volume_ratio"] > (self.volume_factor.value * 1.5)
                mr_conditions.append(volume_spike)

        # Combine mean reversion conditions
        if mr_conditions:
            conditions.append(mr_conditions)

        # ---------------------------------------------------------
        # Apply all conditions (OR logic between condition groups)
        # ---------------------------------------------------------
        if conditions:
            dataframe.loc[
                (conditions[0]) | (conditions[1] if len(conditions) > 1 else False),
                "enter_long"
            ] = 1

        # Tag entries for analysis
        dataframe.loc[dataframe["enter_long"] == 1, "enter_tag"] = "trend_follow"
        # Tag mean reversion entries separately
        if mr_conditions:
            mr_signal = mr_conditions[0]
            for cond in mr_conditions[1:]:
                mr_signal &= cond
            dataframe.loc[mr_signal & (dataframe["enter_long"] == 0), "enter_long"] = 1
            dataframe.loc[mr_signal, "enter_tag"] = "mean_reversion"

        return dataframe

    # ============================================================
    # EXIT SIGNALS
    # ============================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Generate sell signals.
        """

        conditions = []

        # ---------------------------------------------------------
        # Condition 1: Trend Reversal (EMA Cross Down)
        # ---------------------------------------------------------
        if self.sell_rsi_enabled.value:
            rsi_overbought = dataframe["rsi"] > self.sell_rsi_value.value
            conditions.append(rsi_overbought)

        # EMA crossover down
        ema_cross_down = qtpylib.crossed_below(dataframe["ema_9"], dataframe["ema_21"])
        conditions.append(ema_cross_down)

        # MACD bearish crossover
        if self.sell_macd_enabled.value:
            macd_cross_down = qtpylib.crossed_below(dataframe["macd"], dataframe["macdsignal"])
            conditions.append(macd_cross_down)

        # ---------------------------------------------------------
        # Condition 2: Mean Reversion Exit (Upper BB)
        # ---------------------------------------------------------
        if self.sell_bb_enabled.value:
            bb_overbought = dataframe["bb_percent"] > 0.9
            conditions.append(bb_overbought)

        # ---------------------------------------------------------
        # Apply exit conditions
        # ---------------------------------------------------------
        if conditions:
            dataframe.loc[
                conditions[0] | conditions[1] if len(conditions) > 1 else conditions[0],
                "exit_long"
            ] = 1

        return dataframe

    # ============================================================
    # CUSTOM ENTRY PRICE (Limit Orders)
    # ============================================================
    def custom_entry_price(
        self, pair: str, current_time: datetime, proposed_rate: float,
        entry_tag: Optional[str], side: str, **kwargs
    ) -> float:
        """
        Custom entry price for limit orders.
        Places limit order slightly below current price for better fill.
        """
        # Get current ticker from exchange
        # For now, use a small offset
        if entry_tag == "mean_reversion":
            # More aggressive for mean reversion
            return proposed_rate * 0.998
        else:
            # Standard trend follow
            return proposed_rate * 0.999

    # ============================================================
    # CUSTOM EXIT PRICE (Limit Orders)
    # ============================================================
    def custom_exit_price(
        self, pair: str, trade: "Trade", current_time: datetime,
        proposed_rate: float, current_profit: float, **kwargs
    ) -> float:
        """
        Custom exit price for limit orders.
        """
        if current_profit > 0.02:
            # In profit - place limit slightly above
            return proposed_rate * 1.001
        else:
            # Near break-even or loss - market order via stoploss_on_exchange
            return proposed_rate

    # ============================================================
    # CUSTOM STOPLOSS
    # ============================================================
    def custom_stoploss(
        self, pair: str, trade: "Trade", current_time: datetime,
        current_rate: float, current_profit: float, **kwargs
    ) -> float:
        """
        Dynamic stoploss based on volatility (ATR).
        """
        # Get ATR from dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) > 0:
            last_atr = dataframe["atr"].iloc[-1]
            # Use 2x ATR as stoploss, but cap at configured stoploss
            atr_stoploss = - (last_atr * 2) / current_rate
            return max(atr_stoploss, self.stoploss)
        return self.stoploss

    # ============================================================
    # CONFIRM TRADE ENTRY
    # ============================================================
    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time: datetime, entry_tag: Optional[str],
        side: str, **kwargs
    ) -> bool:
        """
        Additional validation before entering trade.
        """
        # Check if we already have too many correlated positions
        # (Simplified - in production, check correlation matrix)
        open_trades = self.get_open_trades()
        if len(open_trades) >= 3:
            return False

        # Don't enter if spread is too wide
        ticker = self.dp.ticker(pair)
        if ticker:
            spread = (ticker["ask"] - ticker["bid"]) / ticker["bid"]
            if spread > 0.005:  # 0.5% max spread
                return False

        return True

    # ============================================================
    # CONFIRM TRADE EXIT
    # ============================================================
    def confirm_trade_exit(
        self, pair: str, trade: "Trade", order_type: str, amount: float,
        rate: float, time_in_force: str, exit_reason: str,
        current_time: datetime, **kwargs
    ) -> bool:
        """
        Additional validation before exiting trade.
        """
        # Always allow stoploss exits
        if exit_reason in ["stoploss", "trailing_stop_loss", "stoploss_on_exchange"]:
            return True

        # Allow ROI exits
        if exit_reason == "roi":
            return True

        # Allow signal exits
        if exit_reason == "exit_signal":
            return True

        return True

    # ============================================================
    # LEVERAGE (Not used for spot)
    # ============================================================
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        return 1.0

    # ============================================================
    # HELPER METHODS
    # ============================================================
    def get_open_trades(self):
        """Get open trades from Freqtrade."""
        from freqtrade.persistence import Trade
        return Trade.get_trades(is_open=True)