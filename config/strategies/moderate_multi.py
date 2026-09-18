"""
Moderate Multi-Pair Strategy for Kraken Canada (CAD Markets)

Designed for $1000 CAD starting capital, moderate risk profile.
Trades: BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD

Strategy Logic:
- Entry: close breaks above its own highest high of the last 20 days, while
  also above the 200-day EMA
- Exit: close falls below its lowest low of the last 10 days
- Stoploss: fixed at -12%
- Freqtrade's protections cap drawdown and cool down after consecutive losses

This docstring describes what the file does today. It used to list an EMA
crossover with an RSI filter, Bollinger Bands, MACD, and "Freqtrade Edge" -
none of which are in this file any more. The operator never saw the wrong text
(the UI reads the DESCRIPTION attribute on the class, not this docstring), but
anyone opening the source was told the bot did something it does not do.
"""

import logging

from freqtrade.enums import RunMode
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta
# `technical` is where qtpylib's indicators actually live. Importing them via
# freqtrade.vendor.qtpylib.indicators still works but emits a FutureWarning on
# every startup, because that module is now only a re-export shim and is
# scheduled for removal. Importing from the source means no warning now and no
# breakage when the shim goes away.
from technical import qtpylib
from typing import List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


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
    DESCRIPTION = "Buys when a coin breaks above its highest price in 20 days, and sells when it falls below its lowest price in 10 days"

    # Strategy interface version
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # -------------------------------------------------------------------------
    # PROFIT TARGETS - deliberately switched off
    # -------------------------------------------------------------------------
    # "0": 1.0 means "take profit at +100%".
    #
    # This is the most important line for a trend-following strategy. The
    # previous ladder capped a trade at +4%, which cannot capture the multi-week
    # moves this strategy exists to catch - the whole premise is that a few large
    # winners pay for many small losers, and a cap removes the large winners.
    #
    # A doubling is high enough not to interfere with an ordinary trend and low
    # enough to be a real level crypto reaches in a strong run. The project's
    # validator caps this target at 1.0 and would reject anything above it as
    # "a sign the numbers were invented rather than tested" - an unreachable
    # number and a switched-off setting look the same in a config file, and only
    # one of them is honest.
    #
    # THE KEYS ARE MINUTES. This is worth stating twice because it has already
    # caused one silent bug: the ladder was written for 5m, rescaled to 1h
    # (360/720/1440), and then the config copy was left at the 5m values
    # (30/60/120). Because freqtrade resolves these attributes with the
    # precedence "Configuration, Strategy, default", the stale config copy won.
    # At 1d the 5m ladder meant "sell any profitable position after 2 hours",
    # which is one twelfth of a single candle.
    #
    # Both copies are now {"0": 1.0} and ai_orchestrator/tests/test_timeframe_units.py
    # checks the config as well as this file, so a stale copy cannot hide again.
    minimal_roi = {
        "0": 1.0
    }

    # -------------------------------------------------------------------------
    # STOPLOSS - sized from measured volatility, not from a round number
    # -------------------------------------------------------------------------
    # Average True Range over 14 days, from Kraken's own daily candles:
    #
    #     BTC/CAD   2.70%      2xATR =  5.4%
    #     ETH/CAD   3.69%      2xATR =  7.4%
    #     SOL/CAD   4.22%      2xATR =  8.4%
    #     XRP/CAD   5.72%      2xATR = 11.4%
    #
    # -0.12 clears 2xATR on all four. The old -0.08 was only 1.4xATR on XRP,
    # which is inside the normal daily range - it would have been hit by noise
    # rather than by the trade being wrong.
    #
    # This is a plain number and NOT a custom_stoploss, deliberately. See RULE 2
    # in ai_orchestrator/plugins/strategy_generator.py: a code-driven stop means
    # nobody can say in advance how much a trade could lose. A number can be
    # stated in advance: at most 12%.
    #
    # A custom_stoploss method used to exist here. It was dead code -
    # use_custom_stoploss defaults to False and was never set, so freqtrade never
    # called it - and it has been removed rather than enabled, because enabling
    # it would have made the maximum loss unknowable.
    stoploss = -0.12

    # Trailing stop: once a trade is up 10%, follow the price down no closer than
    # 8% behind its peak, locking in roughly +2% at worst.
    #
    # 0.02/0.03 were 5m values. A 2% trail is smaller than one ordinary day's
    # range on every one of these pairs, so it would exit on the first quiet
    # pullback.
    # OFF. Measured with freqtrade's backtester: with this on, the strategy lost
    # money in 8 of 8 parameter sets; with it off, 7 of 8 were positive. The
    # Donchian 10-day-low exit is already a trailing stop, and it trails price
    # structure rather than a fixed percentage. See config/base.json.
    trailing_stop = False
    trailing_stop_positive = 0.08
    trailing_stop_positive_offset = 0.10
    trailing_only_offset_is_reached = True

    # -------------------------------------------------------------------------
    # TIMEFRAME - 1 day
    # -------------------------------------------------------------------------
    # This is the change that matters most, and it is arithmetic rather than
    # preference. Kraken Tier 1 charges 0.80% taker each way, so a round trip
    # costs 1.60% at taker, or 0.80% at maker (which this bot now guarantees via
    # post-only orders). Measured live from Kraken's public OHLC:
    #
    #     pair       mean 5m range   mean 1h range   mean 1d range
    #     BTC/CAD    0.075%          0.650%          3.37%
    #     SOL/CAD    0.076%          0.914%          6.59%
    #     XRP/CAD    0.110%          1.237%          6.06%
    #     ETH/CAD    -               0.740%          5.19%
    #
    # On 5m the price had to move about 21 candles' worth just to cover the fee.
    # On 1d, BTC/CAD's fee is 0.24x a single candle's range. No strategy choice
    # closes a 21x gap; the timeframe does.
    #
    # Kraken serves exactly 721 daily candles, about two years. That is a real
    # limitation and it is why the backtest numbers for this strategy swing from
    # -3.40% to +4.65% per month on arbitrary parameter choices: two years is one
    # market regime, not a sample.
    timeframe = "1d"

    # Process only new candles
    process_only_new_candles = True

    # These values can be overridden in the config
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles required before strategy produces valid signals.
    # The trend filter uses a 200-day EMA, so 200 daily candles must exist
    # before the first signal can be evaluated - about seven months of data.
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
    # Timings are in CANDLES. This is the third timeframe this strategy has been
    # on, and each move silently reinterprets every number below:
    #
    #     at 5m   1 candle = 5 minutes
    #     at 1h   1 candle = 1 hour
    #     at 1d   1 candle = 1 day      <- now
    #
    # The values were last set for 1h, where 24 candles meant one day. At 1d the
    # same 24 means twenty-four days, so a drawdown circuit breaker that was
    # meant to pause the bot for a day would have paused it for over three weeks.
    # Nothing would have errored; the bot would simply have stopped trading for a
    # month and the config would still have said "24".
    #
    # So these are NOT a mechanical rescale. A one-candle lookback is the
    # mechanical answer at 1d and it is useless - a drawdown measured over a
    # single day tells you almost nothing. The numbers below are re-derived from
    # what each guard is FOR:
    #
    #   MaxDrawdown    look back ~3.5 weeks, pause 1 week
    #   StoplossGuard  look back 10 days, pause 5 days
    #   CooldownPeriod 1 day, which is one candle
    #
    # The pause durations are deliberately much shorter than 24 candles. A
    # circuit breaker exists to stop the bot digging while a regime is hostile,
    # not to sit out a quarter of the year - and at a daily timeframe, a week is
    # already a long time to be flat.
    @property
    def protections(self):
        return [
            # Stop trading entirely if the account loses more than 10% within the
            # lookback window. Without this, nothing stops a losing streak.
            #
            # calculation_mode "equity" measures real peak-to-trough drawdown on
            # the account equity curve. The legacy "ratios" mode derives it from
            # cumulative trade profit ratios, which drifts from the account-level
            # figure as position sizing changes. The docs recommend "equity" for
            # new setups.
            {
                "method": "MaxDrawdown",
                "calculation_mode": "equity",
                "lookback_period_candles": 24,    # 24 days, about 3.5 weeks
                "trade_limit": 10,                # wait for a real sample
                "stop_duration_candles": 7,       # then pause 1 week
                "max_allowed_drawdown": 0.10,     # 10%
            },
            # If 3 trades hit their stop loss within 10 days, something is wrong
            # with the market or the strategy. Pause the whole account rather
            # than keep feeding it money.
            #
            # trade_limit 3 is a low bar on purpose. With a -12% stop and at most
            # 3 positions, three stopouts is a meaningful fraction of the wallet,
            # and the pairs are 0.775 correlated on average - so they tend to stop
            # out together rather than independently.
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 10,
                "trade_limit": 3,
                "stop_duration_candles": 5,       # pause 5 days
                "required_profit": 0.0,           # count all losing stoplosses
                "only_per_pair": False,           # account-wide, not per pair
            },
            # After any exit, wait one candle - one day - before re-entering that
            # pair. Prevents rapid re-entry churn, which mostly generates fees.
            {
                "method": "CooldownPeriod",
                "stop_duration_candles": 1,
            },
        ]

    # -------------------------------------------------------------------------
    # ORDER TYPES AND TIME IN FORCE
    # -------------------------------------------------------------------------
    # These MUST match config/base.json, and the config is what actually wins:
    # ("order_types", None) and ("order_time_in_force", None) are both in the
    # override list in freqtrade/resolvers/strategy_resolver.py.
    #
    # They are repeated here rather than left out because a strategy should
    # describe itself. But a copy that contradicts the config is worse than no
    # copy at all - this block used to declare order_time_in_force "GTC" while
    # the config said "PO", so anyone reading the strategy would have concluded
    # the bot was not using post-only orders, and they would have been reading
    # the file that loses.
    #
    # stoploss_on_exchange is false in both. With it true, freqtrade places a
    # stop order on Kraken itself, which would fire even if the bot is down - but
    # Kraken's stop orders are market orders, so a wick would take the taker fee
    # and the fill could be far from the stop price. The bot checks the stoploss
    # every candle instead, which on a daily timeframe is the same cadence the
    # rest of the strategy runs at.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "force_entry": "market",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # "PO" is Post Only - Kraken rejects the order if it would cross the spread,
    # so the maker rate is guaranteed rather than hoped for. See the long note in
    # config/base.json for why a limit order alone is not enough.
    order_time_in_force = {
        "entry": "PO",
        "exit": "PO",
    }

    # Plot configuration for FreqUI.
    #
    # Every column named here must exist in the dataframe, and this list used to
    # name ema_9, ema_21, ema_50, ema_200, bb_lowerband, macd, rsi and
    # stoch_rsi_k - none of which populate_indicators produces any more. FreqUI
    # would have shown empty panels for an indicator set the strategy no longer
    # computes, which reads as a broken chart rather than a stale config.
    #
    # The Donchian channel is the strategy's whole thesis, so it belongs on the
    # price chart: a breakout is visible as price crossing the upper line.
    plot_config = {
        "main_plot": {
            "donchian_high": {"color": "#D50000"},   # the entry trigger
            "donchian_low": {"color": "#00C853"},    # the exit trigger
            "ema_trend": {"color": "#2962FF"},       # the trend filter
        },
        "subplots": {
            "atr": {
                "atr_percent": {"color": "#FF6D00"},
            },
            "volume": {
                "volume": {"color": "#424242"},
            },
        },
    }

    # ============================================================
    # PARAMETERS
    # ============================================================
    # These are the CLASSIC Donchian channel values, not tuned ones, and that is
    # a deliberate choice rather than laziness.
    #
    # The Turtle traders used a 20-day breakout for entry and a 10-day breakout
    # for exit (their "System 1"). 20 and 10 are round numbers that were chosen
    # before anyone had this data, which is exactly what makes them trustworthy:
    # they cannot have been fitted to the two years Kraken will give us.
    #
    # WHY NOT OPTIMIZE. A parameter sweep over this strategy on real Kraken daily
    # data produced:
    #
    #     15/8  +4.65%/mo      30/15  +3.75%/mo      20/10  +2.93%/mo
    #     20/20 +4.15%/mo      25/12  +1.59%/mo      10/5   +1.92%/mo
    #     40/20 +3.88%/mo      50/25  -3.40%/mo
    #
    # A range of -3.40% to +4.65% per month from arbitrary neighbouring numbers
    # is not a strategy with a good setting inside it. It is noise, and picking
    # the top of that range would be fitting to one regime. The honest reading is
    # that this edge is unproven and may be zero - the sweep is why the bot runs
    # in dry-run to collect its own evidence instead of trusting a backtest.
    #
    # 50/25 going negative is the useful warning: a slower version of the same
    # idea lost money over the same two years, so the sign of the result depends
    # on the window rather than on the idea.
    #
    # Hyperopt is left switched off (optimize=False) on purpose. A tool that
    # searches thousands of combinations will always find a profitable one in a
    # two-year sample, and that number would not survive contact with next year.
    entry_window = IntParameter(10, 60, default=20, space="buy", optimize=False)
    exit_window = IntParameter(5, 40, default=10, space="sell", optimize=False)

    # Trend filter: only buy breakouts that happen above the 200-day EMA.
    #
    # A breakout is a statement that price is going up. In a sustained downtrend
    # breakouts fail far more often, and each failure costs the full fee. This
    # filter removes counter-trend entries rather than trying to time them.
    #
    # 200 daily candles is about seven months, and startup_candle_count must be
    # at least this long or the first signals are computed on a partial EMA.
    trend_filter_window = IntParameter(100, 250, default=200, space="buy", optimize=False)

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
        Donchian channels, a long-term trend filter, and ATR for reference.

        A Donchian channel is simply the highest high and the lowest low over the
        last N candles. Breaking above the high is the entry; falling below the
        low is the exit. It is the oldest mechanical trend-following rule there
        is, which is a feature: it was not discovered by searching this data.
        """

        # ---------------------------------------------------------
        # Donchian channels
        # ---------------------------------------------------------
        # shift(1) IS LOAD-BEARING AND MUST NOT BE REMOVED.
        #
        # Without it, the current candle's own high is included in the maximum it
        # is being compared against. close > max(high) including today's high is
        # true only when today closed exactly at its high - and on the candles
        # where it does fire, the strategy is being told about the breakout using
        # the breakout candle itself.
        #
        # shift(1) makes the channel the highest high of the candles BEFORE this
        # one, so the comparison is "is today's close above everything that came
        # before it". That is the real question, and it is answerable at the
        # moment the candle closes.
        #
        # A lookahead here would not crash and would not look wrong. It would
        # simply make every backtest better than the strategy can be, which is
        # the most expensive kind of bug to ship.
        dataframe["donchian_high"] = (
            dataframe["high"].rolling(self.entry_window.value).max().shift(1)
        )
        dataframe["donchian_low"] = (
            dataframe["low"].rolling(self.exit_window.value).min().shift(1)
        )

        # How far price sits above or below the channel, as a percentage. Not
        # used by the signals - it is plotted so a human can see how decisive a
        # given breakout was rather than only whether it happened.
        dataframe["donchian_position"] = (
            (dataframe["close"] - dataframe["donchian_low"])
            / (dataframe["donchian_high"] - dataframe["donchian_low"])
        )

        # ---------------------------------------------------------
        # Trend filter
        # ---------------------------------------------------------
        # Breakouts fail more often in downtrends, and every failure costs a full
        # round trip in fees. This only permits breakouts above the long EMA.
        #
        # On daily candles the default 200 is about seven months of history.
        dataframe["ema_trend"] = ta.EMA(
            dataframe, timeperiod=self.trend_filter_window.value
        )

        # ---------------------------------------------------------
        # ATR - measured, and used to justify the stoploss number
        # ---------------------------------------------------------
        # The signals below do not read this. It is here because the stoploss is
        # a fixed -12% and that number is only defensible relative to volatility:
        # measured daily ATR is 2.70% (BTC), 3.69% (ETH), 4.22% (SOL) and 5.72%
        # (XRP), so -12% is at least 2.1xATR on all four. Plotting it makes that
        # claim checkable against live data instead of taken on trust.
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_percent"] = dataframe["atr"] / dataframe["close"] * 100

        # ---------------------------------------------------------
        # Volume - context, and a tradability guard
        # ---------------------------------------------------------
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean"]

        return dataframe

    # ============================================================
    # ENTRY SIGNALS
    # ============================================================
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Buy when price closes above its highest close in entry_window days, while
        above the long-term trend filter.
        """

        # Both columns are defined before any .loc assignment. Assigning through
        # .loc creates the column as NaN everywhere the mask is False, and a NaN
        # is not a valid 0/1 signal - it would be read as "no signal" only by
        # luck. enter_long in particular is NOT pre-created by freqtrade.
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        # The breakout: today's close above every high of the previous 20 days.
        breakout = dataframe["close"] > dataframe["donchian_high"]

        # Only in an uptrend. This is the filter that stops the bot buying
        # breakouts into a falling market.
        uptrend = dataframe["close"] > dataframe["ema_trend"]

        # NaN GUARD, and it is not cosmetic. The first entry_window candles have
        # no channel, so donchian_high is NaN there. Every comparison against NaN
        # is False, which happens to be the safe answer - but the EMA comparison
        # is NaN too, and relying on NaN comparisons to fail in the right
        # direction is relying on luck. This states the requirement outright.
        has_history = (
            dataframe["donchian_high"].notna() & dataframe["ema_trend"].notna()
        )

        # A candle with no volume is not a price anyone traded at. This matters
        # more on the thin CAD books than it would on a major pair: 18% of
        # BTC/CAD 5-minute candles had zero volume, and a "breakout" printed on
        # one of those is a quote, not a trade.
        tradable = dataframe["volume"] > 0

        signal = breakout & uptrend & has_history & tradable

        dataframe.loc[signal, "enter_long"] = 1
        dataframe.loc[signal, "enter_tag"] = "donchian_breakout"

        return dataframe

    # ============================================================
    # EXIT SIGNALS
    # ============================================================
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Sell when price closes below its lowest close in exit_window days.

        The exit window is deliberately shorter than the entry window (10 vs 20).
        That asymmetry is the classic Turtle shape and it is what makes the
        strategy trend-following rather than a coin flip: entries need a high bar
        to happen at all, exits need a low one so that a position which has
        stopped working is left quickly. A trade therefore stays open while the
        trend persists and closes when it breaks.
        """

        dataframe["exit_long"] = 0

        breakdown = dataframe["close"] < dataframe["donchian_low"]
        has_history = dataframe["donchian_low"].notna()

        dataframe.loc[breakdown & has_history, "exit_long"] = 1

        return dataframe

    # ============================================================
    # ORDER PRICING - deliberately NOT overridden here
    # ============================================================
    # custom_entry_price and custom_exit_price used to be defined here. They have
    # been removed so that order pricing has exactly ONE source of truth: the
    # entry_pricing / exit_pricing blocks in config/base.json.
    #
    # Two reasons, and the second is the important one.
    #
    # 1. They were partly dead. custom_entry_price branched on
    #    entry_tag == "mean_reversion", and that tag no longer exists - entries
    #    are tagged "donchian_breakout" now. The branch could never be taken.
    #
    # 2. They silently overrode the maker logic. When custom_entry_price is
    #    defined, freqtrade uses the price it returns and entry_pricing.price_side
    #    never decides anything. So the config could say price_side "same" - the
    #    resting side, the maker side - and the order would still be placed by a
    #    number in this file. A reader checking the config would have concluded
    #    the bot rests on the book, and they would have been reading the wrong
    #    file.
    #
    # That is the same failure mode as the minimal_roi ladder and the
    # use_custom_stoploss flag: two places claiming to control one thing, where
    # the copy that looks authoritative is not the one in force.
    #
    # With these gone, pricing comes from the config:
    #     entry_pricing.price_side = "same"   -> the bid, a resting buy
    #     exit_pricing.price_side  = "same"   -> the ask, a resting sell
    #     order_time_in_force      = "PO"     -> Kraken rejects a crossing order
    # and all three are checked by ai_orchestrator/tests/test_order_types.py.

    # ============================================================
    # CONFIRM TRADE ENTRY
    # ============================================================
    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time: datetime, entry_tag: Optional[str],
        side: str, **kwargs
    ) -> bool:
        """
        Last check before an entry order is placed.
        """

        # The position limit is read from the config, NOT hardcoded.
        #
        # This used to be `if len(open_trades) >= 3`. That is the same number as
        # max_open_trades, so it looked correct - but max_open_trades is a
        # setting the operator can change in the bot's UI, and this line would
        # have silently capped it. Raising the limit to 5 in the UI would have
        # produced a bot that still refused the fourth trade, with the UI showing
        # 5 and nothing anywhere saying why.
        #
        # max_open_trades is already enforced by freqtrade itself, so this check
        # is a second gate. `get_open_trade_count` is the right call for it: it
        # runs a COUNT in live mode and reads the backtest counter in backtest
        # mode, so the same line works in both. The previous version called
        # `Trade.get_trades(is_open=True)`, which does not exist - it raised
        # TypeError on every single entry attempt. freqtrade's safe wrapper
        # swallows that and substitutes True, so instead of blocking anything
        # the exception skipped the rest of this method, which meant the spread
        # guard below never ran either.
        # `-1` and infinity BOTH mean "no limit" in freqtrade, and -1 is not a
        # historical curiosity: config_validation accepts it, `freqtrade
        # new-config` offers it as "unlimited open trades", and freqtrade's own
        # lookahead-analysis forces it. Testing only for infinity makes this
        # line refuse every trade in those runs, because `0 >= -1` is true - a
        # bot that silently never trades. That is exactly what happened here:
        # the sentinel check was written against infinity alone, and the
        # TypeError above meant it was never executed long enough to show it.
        max_open_trades = self.config.get("max_open_trades", 3)
        if max_open_trades not in (float("inf"), -1) and Trade.get_open_trade_count() >= max_open_trades:
            logger.info("Entry refused for %s: already at max_open_trades (%s)", pair, max_open_trades)
            return False

        # Do not enter while the book is unusually wide.
        #
        # Measured top-of-book spreads on these pairs are small - 0.0039% on
        # BTC/CAD, 0.0071% on ETH/CAD, 0.0135% on SOL/CAD, 0.1565% on XRP/CAD -
        # so 0.5% does not fire in normal conditions. It is a guard against the
        # moments that are not normal: a thin CAD book during a violent move,
        # where a resting order would be filled at a price that no longer
        # reflects the market.
        #
        # This is skipped outside live/dry-run. `dp.ticker` makes a real network
        # request, so calling it during a backtest would make the result depend
        # on whatever the exchange happened to be quoting at the time, and the
        # backtest could not be reproduced.
        if self.dp.runmode in (RunMode.DRY_RUN, RunMode.LIVE):
            ticker = self.dp.ticker(pair)
            ask = ticker.get("ask") if ticker else None
            bid = ticker.get("bid") if ticker else None
            # A pair with no usable quote is not a pair to buy blind.
            if ask and bid:
                spread = (ask - bid) / bid
                if spread > 0.005:
                    logger.info(
                        "Entry refused for %s: spread %.4f%% is wider than 0.5%%",
                        pair, spread * 100,
                    )
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
        Exits are never blocked, and that is the deliberate answer.

        This method used to list four exit reasons and return True for each of
        them, then return True at the end as well. Every possible input produced
        the same result, so the branches did nothing except suggest that some
        exits might be refused.

        The rule this bot follows is the asymmetry the entry and exit signals
        already encode: entries need several conditions to agree, exits need one.
        A confirmation hook that could veto an exit would work against that, and
        a vetoed stoploss is the single most expensive thing this file could do.
        Returning True unconditionally is not an omission - it is the policy,
        stated in one line instead of four.
        """
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
    # The `get_open_trades` helper that used to live here has been removed.
    # It wrapped a call that did not exist in this freqtrade version, and its
    # only caller now uses `Trade.get_open_trade_count()` directly - one line
    # that works in both live and backtest mode, instead of a helper that
    # raised on every call.