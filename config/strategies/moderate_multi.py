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
# `technical` is where qtpylib's indicators actually live. Importing them via
# freqtrade.vendor.qtpylib.indicators still works but emits a FutureWarning on
# every startup, because that module is now only a re-export shim and is
# scheduled for removal. Importing from the source means no warning now and no
# breakage when the shim goes away.
from technical import qtpylib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


def _all_true(conditions: List[DataFrame]) -> DataFrame:
    """AND a group of boolean Series into a single Series.

    Returns a Series, never a list. That distinction is the whole point: the
    entry logic below once combined condition *groups* with `|`, which is
    `list | list` and raised TypeError on every candle for every pair.
    """
    signal = conditions[0]
    for extra in conditions[1:]:
        signal = signal & extra
    return signal


def _any_true(conditions: List[DataFrame]) -> DataFrame:
    """OR a group of boolean Series into a single Series."""
    signal = conditions[0]
    for extra in conditions[1:]:
        signal = signal | extra
    return signal


class ModerateMultiPairStrategy(IStrategy):
    """
    Moderate risk multi-pair strategy for CAD markets on Kraken Canada.
    """

    # One line, in plain language, shown to the operator in the bot's UI.
    #
    # Freqtrade ignores this attribute - it iterates a fixed list of the
    # attributes it cares about and never enumerates the class's own, so adding
    # one cannot break strategy loading. It exists so that someone who does not
    # read code is told what their bot does, instead of being shown the class
    # name. Keep it short, keep it free of jargon, and describe the *behaviour*
    # rather than the indicators.
    DESCRIPTION = "Looks for upward trends and oversold dips across four CAD pairs, with a stop loss on every trade"

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for moderate risk
    #
    # THE KEYS ARE MINUTES, NOT CANDLES. This ladder was written for a 5-minute
    # timeframe, where "30" meant six candles. Moving to 1h without rescaling it
    # would have made it decay to zero within two candles - the bot would exit at
    # the first sign of profit, on every trade, and the numbers would still look
    # plausible in the config. The times below are the same number of CANDLES as
    # before: 6, 12 and 24.
    minimal_roi = {
        "0": 0.04,
        "360": 0.02,     # 6 candles at 1h
        "720": 0.01,     # 12 candles
        "1440": 0        # 24 candles
    }

    # Stoploss
    stoploss = -0.08

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = False

    # Timeframe
    #
    # 1h, not 5m. This is the single change that matters most, and it is not a
    # tuning preference - it is arithmetic.
    #
    # Kraken Tier 1 charges 0.80% taker each way, so a round trip costs 1.60%.
    # Measured live from Kraken's public OHLC for the configured pairs:
    #
    #     pair       mean 5m candle range    mean 1h candle range
    #     BTC/CAD    0.075%                  0.650%
    #     SOL/CAD    0.076%                  0.914%
    #     XRP/CAD    0.110%                  1.237%
    #
    # On 5m the price would have to move about 21 candles' worth just to cover the
    # fee. On 1h that falls to between 1.3 and 2.5 candles. No strategy choice
    # closes a 21x gap; the timeframe does.
    #
    # The CAD pairs are also thin at 5m: 36% of BTC/CAD 5m candles have zero range
    # and 18% have zero volume, so there were five-minute windows in which nothing
    # traded at all.
    timeframe = "1h"

    # Process only new candles
    process_only_new_candles = True

    # These values can be overridden in the config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before strategy produces valid signals
    startup_candle_count: int = 200

    # -------------------------------------------------------------------------
    # PROTECTIONS - automatic circuit breakers
    # -------------------------------------------------------------------------
    # These MUST be defined here, in the strategy, and not in the config.
    # Freqtrade 2026.8 rejects a `protections` key in the configuration file
    # outright:
    #
    #   Configuration error: DEPRECATED: Setting 'protections' in the
    #   configuration is deprecated.
    #
    # (see freqtrade/configuration/deprecated_settings.py). Defining them as a
    # @property on the strategy is the supported location, and it also means a
    # protection travels with the strategy it protects.
    #
    # They are active in dry-run and live trading automatically. Backtesting and
    # hyperopt only honour them when --enable-protections is passed.
    #
    # Timings are in CANDLES, so every number below had to be rescaled when the
    # timeframe moved from 5m to 1h. Left alone, the "24 hour" drawdown window
    # would have become twelve days and the 1-hour cooldown would have become
    # twelve hours - while the comments still described the old durations.
    #
    # At 1h:  1 candle = 1 hour, 8 = 8 hours, 24 = 24 hours.
    #
    # Protections are evaluated in the order defined below.
    @property
    def protections(self):
        return [
            # Stop trading entirely if the account loses more than 10% within a
            # day. Without this, nothing stops a losing streak.
            #
            # calculation_mode "equity" measures real peak-to-trough drawdown on
            # the account equity curve. The legacy "ratios" mode derives it from
            # cumulative trade profit ratios, which drifts from the account-level
            # figure as position sizing changes. The docs recommend "equity" for
            # new setups.
            {
                "method": "MaxDrawdown",
                "calculation_mode": "equity",
                "lookback_period_candles": 24,    # last 24 hours
                "trade_limit": 10,                # wait for a real sample
                "stop_duration_candles": 24,      # then pause 24 hours
                "max_allowed_drawdown": 0.10,     # 10%
            },
            # If 3 trades hit their stop loss within 8 hours, something is wrong
            # with the market or the strategy. Pause the whole account rather
            # than keep feeding it money.
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 8,
                "trade_limit": 3,
                "stop_duration_candles": 8,
                "required_profit": 0.0,           # count all losing stoplosses
                "only_per_pair": False,           # account-wide, not per pair
            },
            # After any exit, wait 1 hour before re-entering that pair. Prevents
            # rapid re-entry churn, which mostly generates fees.
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 1,
            },
        ]

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
    # How many candles an EMA crossover keeps counting as a fresh trend.
    #
    # A crossover is a one-candle event; the trend it announces lasts longer.
    # Requiring the crossing candle itself is what made this strategy unable to
    # trade: it needed an EMA cross AND a MACD cross on the same 5-minute
    # candle, which over 400 candles of real-shaped data happened zero times.
    # Default 8, not 4. ADX and the directional indicators are computed over a
    # 14-period window and therefore LAG a trend change: after an EMA crossover
    # it takes several candles before DI+ actually exceeds DI-. With a window
    # shorter than that, the entry demanded the crossover and its own
    # confirmation on the same candle and could not fire at all.
    buy_trend_window = IntParameter(1, 20, default=8, space="buy", optimize=True)

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

        # ---------------------------------------------------------
        # Condition 1: Trend Following (EMA Crossover + RSI)
        # ---------------------------------------------------------
        trend_conditions = []

        if self.buy_ema_short.value and self.buy_ema_long.value:
            # EMA crossover (short crosses above long), counted as still live
            # for buy_trend_window candles afterwards.
            #
            # The second half of the condition matters: the short EMA must
            # still be above the long one. Without it, a crossover followed
            # immediately by a cross back down would keep registering as a
            # bullish entry for the rest of the window.
            ema_short = ta.EMA(dataframe, timeperiod=self.buy_ema_short.value)
            ema_long = ta.EMA(dataframe, timeperiod=self.buy_ema_long.value)
            ema_cross = qtpylib.crossed_above(ema_short, ema_long)
            ema_cross_recent = (
                ema_cross.rolling(self.buy_trend_window.value, min_periods=1).max().astype(bool)
                & (ema_short > ema_long)
            )
            trend_conditions.append(ema_cross_recent)

        if self.buy_rsi_enabled.value:
            # RSI still oversold: the trend is turning, not yet extended.
            #
            # The comment here used to read "RSI not overbought" while the code
            # required RSI *below* buy_rsi_value (default 30, range 20-40). The
            # code and the parameter range agree with each other, so the comment
            # was the wrong one. Worth stating plainly because it is the single
            # most restrictive condition left: of 28 candles with a recent EMA
            # crossover, only 8 also had RSI under 30. That is the intended
            # trade-off - it buys the turn rather than the run - but it should
            # be a known choice rather than an accident of a stale comment.
            rsi_ok = dataframe["rsi"] < self.buy_rsi_value.value
            trend_conditions.append(rsi_ok)

        if self.adx_enabled.value:
            # ADX shows trend strength
            adx_ok = (dataframe["adx"] > self.adx_value.value) & (dataframe["di_plus"] > dataframe["di_minus"])
            trend_conditions.append(adx_ok)

        if self.buy_macd_enabled.value:
            # MACD bullish: momentum is with the trade.
            #
            # This was a *second crossover* rather than a state, which turned
            # "MACD for momentum confirmation" into a second one-candle event
            # that had to coincide with the first. Two independent crossovers
            # landing on the same candle is vanishingly rare, so the entry
            # never fired. Confirmation is a condition that holds, not an
            # event that happens.
            macd_bullish = dataframe["macd"] > dataframe["macdsignal"]
            trend_conditions.append(macd_bullish)

        if self.volume_enabled.value:
            # Volume confirmation
            volume_ok = dataframe["volume_ratio"] > self.volume_factor.value
            trend_conditions.append(volume_ok)


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

        # ---------------------------------------------------------
        # Apply all conditions
        #
        # Within a group every condition must hold (AND) - they are
        # confirmations of one idea. Between groups either is enough (OR) - a
        # trend entry and a mean-reversion entry are different reasons to buy,
        # and neither is a prerequisite for the other.
        #
        # This block previously read `conditions[0] | conditions[1]`, which
        # combined two *lists* rather than two Series and raised
        # "TypeError: unsupported operand type(s) for |: 'list' and 'list'" on
        # every candle for every pair. The bot ran, fetched candles and could
        # not evaluate a single entry signal. Groups are reduced explicitly now,
        # so the operand is unambiguously a Series.
        # ---------------------------------------------------------
        # freqtrade pre-creates enter_tag but not enter_long, and assigning
        # through .loc creates the column as NaN everywhere the mask is False.
        # A NaN signal is not a valid 0/1 and would be read as "no signal" only
        # by luck, so both columns start defined.
        dataframe["enter_long"] = 0

        if trend_conditions:
            trend_signal = _all_true(trend_conditions)
            dataframe.loc[trend_signal, "enter_long"] = 1
            dataframe.loc[trend_signal, "enter_tag"] = "trend_follow"

        if mr_conditions:
            mr_signal = _all_true(mr_conditions)
            dataframe.loc[mr_signal, "enter_long"] = 1
            # Where both fire, the mean-reversion reason is recorded, matching
            # the precedence this strategy had before the fix.
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
        # Exits combine with OR, not AND, and that asymmetry with the entry
        # logic is deliberate: buying wants confirmations, selling wants to be
        # easy. Any one warning sign is enough to leave a position.
        #
        # This block previously read
        #   conditions[0] | conditions[1] if len(conditions) > 1 else conditions[0]
        # which silently ignored conditions[2] and beyond. With the MACD and
        # Bollinger exits enabled that dropped two of the four configured exit
        # reasons - and made their sell_macd_enabled / sell_bb_enabled switches
        # do nothing at all, which is worse than an obviously broken exit
        # because the operator sees a setting that appears to work.
        #
        # As with the entry signal, the column is defined first: assigning
        # through .loc otherwise leaves NaN wherever the mask is False.
        dataframe["exit_long"] = 0

        if conditions:
            dataframe.loc[_any_true(conditions), "exit_long"] = 1

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