#!/usr/bin/env python3
"""Run the shipped strategy against real data and check it produces signals.

Why this exists
---------------
The strategy shipped with a fatal bug for its entire life:

    TypeError: unsupported operand type(s) for |: 'list' and 'list'
    moderate_multi.py, line 412, in populate_entry_trend

Every pair, every candle, on the live bot. The bot started, fetched data, and
then failed to evaluate a single entry signal. It could not have opened a trade.

Nothing in the test suite caught it. The validator checked the file's structure
- imports, banned calls, docstring, pair safety - and the strategy passed every
one of those checks, because the bug was not structural. It was a runtime type
error, and no test ever executed the code. A strategy that never runs is a
strategy that is never wrong, which is how a fatal bug survives 48 green cases.

So this test does the one thing that would have caught it: it imports the real
strategy file, hands it a real DataFrame, and calls the methods freqtrade calls.
If they raise, the test fails with the traceback.

What changed with the Donchian rewrite
--------------------------------------
This test used to build a DataFrame with the indicator columns pre-filled
(ema_9, rsi, macd, bb_percent...) and call populate_entry_trend directly. That
worked while the strategy read pre-computed columns, but it meant
populate_indicators was never executed by any test - the half of the strategy
that decides what the signals are computed FROM was untested.

The strategy now derives its own channels, so this file calls
populate_indicators first and feeds its output to the signal methods. The
pipeline under test is the real one.

The new check that matters most is the lookahead test. A Donchian channel must
be the highest high of the candles BEFORE the current one. Building it without
shift(1) - including the current candle in the maximum it is compared against -
does not crash, does not look wrong, and makes every backtest better than the
strategy can actually be. Section 4 pins that specific mistake.

No freqtrade, talib or technical install is required; they are stubbed into
sys.modules for the duration of the import.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

STRATEGY = (
    pathlib.Path(__file__).resolve().parents[2]
    / "config" / "strategies" / "moderate_multi.py"
)

#: Rows of synthetic candles. Must exceed the longest indicator period so the
#: warm-up NaNs are present - a strategy that only works on warm data is not
#: working. The trend filter is a 200-day EMA, so this must be comfortably
#: above 200 or every signal would be suppressed by the NaN guard and the test
#: would report a broken strategy when the fixture was simply too short.
ROWS = 700


def _install_stubs() -> None:
    """Put faithful-enough freqtrade / talib / technical modules in sys.modules."""
    import numpy as np
    import pandas as pd

    # ---- freqtrade.strategy ------------------------------------------------
    class _Param:
        """Mimics freqtrade's parameter descriptor: `self.x.value` is the value."""

        def __init__(self, *args, default=None, **kwargs):
            self.value = default if default is not None else (args[0] if args else None)

        def __get__(self, instance, owner=None):
            return self

    class IStrategy:
        # The strategy reads these off itself; freqtrade would normally set them.
        timeframe = "1d"
        stoploss = -0.12
        minimal_roi = {"0": 100}
        startup_candle_count = 200
        process_only_new_candles = True

        def __init__(self, config=None):
            self.config = config or {}

    fs = types.ModuleType("freqtrade.strategy")
    fs.IStrategy = IStrategy
    fs.IntParameter = _Param
    fs.DecimalParameter = _Param
    fs.CategoricalParameter = _Param
    fsi = types.ModuleType("freqtrade.strategy.interface")
    fsi.IStrategy = IStrategy
    ff = types.ModuleType("freqtrade")
    ff.strategy = fs
    sys.modules["freqtrade"] = ff
    sys.modules["freqtrade.strategy"] = fs
    sys.modules["freqtrade.strategy.interface"] = fsi

    # ---- talib.abstract ----------------------------------------------------
    def _series(df):
        return df["close"] if isinstance(df, pd.DataFrame) else df

    def EMA(df, timeperiod=9, **kw):
        return _series(df).ewm(span=int(timeperiod), adjust=False).mean()

    def RSI(df, timeperiod=14, **kw):
        s = _series(df)
        d = s.diff()
        up = d.clip(lower=0).ewm(alpha=1 / int(timeperiod), adjust=False).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / int(timeperiod), adjust=False).mean()
        return 100 - (100 / (1 + up / dn.replace(0, np.nan)))

    def ATR(df, timeperiod=14, **kw):
        """Wilder's ATR, which is what talib computes - not a rolling mean.

        The previous stub used a plain rolling mean of (high - low). That is a
        different number, and since the stoploss rationale quotes measured ATR
        values, a stub that does not match talib would make the test agree with
        a figure the live bot never sees.
        """
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(alpha=1 / int(timeperiod), adjust=False).mean()

    ta = types.ModuleType("talib")
    ta.abstract = types.ModuleType("talib.abstract")
    for fn in (EMA, RSI, ATR):
        setattr(ta.abstract, fn.__name__, fn)
    sys.modules["talib"] = ta
    sys.modules["talib.abstract"] = ta.abstract

    # ---- technical.qtpylib -------------------------------------------------
    qtp = types.ModuleType("technical.qtpylib")

    def crossed_above(a, b):
        return (a > b) & (a.shift(1) <= b.shift(1))

    def crossed_below(a, b):
        return (a < b) & (a.shift(1) >= b.shift(1))

    qtp.crossed_above = crossed_above
    qtp.crossed_below = crossed_below
    qtp.bollinger_bands = lambda s, window=20, stds=2.0, **kw: {
        "lower": s.rolling(int(window)).mean() - stds * s.rolling(int(window)).std(),
        "mid": s.rolling(int(window)).mean(),
        "upper": s.rolling(int(window)).mean() + stds * s.rolling(int(window)).std(),
    }
    qtp.typical_price = lambda df: (df["high"] + df["low"] + df["close"]) / 3
    tech = types.ModuleType("technical")
    tech.qtpylib = qtp
    sys.modules["technical"] = tech
    sys.modules["technical.qtpylib"] = qtp


def _load_strategy():
    spec = importlib.util.spec_from_file_location("moderate_multi_under_test", STRATEGY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ModerateMultiPairStrategy


def _make_dataframe(seed: int = 20260917, phase: float = 12.0, rows: int = ROWS):
    """Raw OHLCV candles that trend and pull back.

    Only OHLCV is produced. The indicator columns are deliberately NOT
    pre-filled any more: populate_indicators is the thing under test, so filling
    its output in by hand would test the signal methods against numbers the
    strategy never computed.

    `seed` and `phase` vary the regime, so a condition can be judged across more
    than one market shape rather than one lucky series.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=rows, freq="D")

    # A slow cycle plus noise. The cycle guarantees the series makes new highs
    # (so the Donchian breakout is reachable) and new lows (so the exit is too).
    trend = np.sin(np.linspace(0, phase * np.pi, rows)) * 8000
    close = pd.Series(60000 + trend + rng.normal(0, 700, rows), index=idx)
    # Highs and lows must straddle the close, or a "close above every prior
    # high" test becomes impossible for fixture reasons.
    high = close + rng.uniform(50, 900, rows)
    low = close - rng.uniform(50, 900, rows)
    vol = pd.Series(rng.uniform(80, 400, rows), index=idx)

    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        },
        index=idx,
    )


def _analyse(strat, df):
    """Run the real pipeline: indicators first, then the signal methods."""
    out = strat.populate_indicators(df.copy(), {"pair": "BTC/CAD"})
    out = strat.populate_entry_trend(out, {"pair": "BTC/CAD"})
    out = strat.populate_exit_trend(out, {"pair": "BTC/CAD"})
    return out


def _check_signal(name, out, sig_col):
    """Check one signal column is well-formed and actually fires."""
    problems = []
    if sig_col not in out.columns:
        print(f"  FAIL  no {sig_col!r} column produced")
        return [f"{name} did not create the {sig_col!r} column"]

    sig = out[sig_col]
    n_on = int((sig == 1).sum())
    n_nan = int(sig.isna().sum())
    bad = sorted(set(sig.dropna().unique()) - {0, 1})

    if sig_col == "enter_long" and "enter_tag" in out.columns:
        tags = out.loc[sig == 1, "enter_tag"].value_counts().to_dict()
        print(f"        entry tags: {tags or 'none'}")

    print(f"  ok    {name}: {n_on} signal(s) of {len(sig)} rows, {n_nan} NaN")

    if n_nan:
        problems.append(
            f"{name}: {n_nan} NaN value(s) in {sig_col}. freqtrade treats a "
            "missing signal as an error; the column must be 0 or 1 everywhere."
        )
    if bad:
        problems.append(f"{name}: {sig_col} contains non-0/1 values: {bad}")
    if n_on == 0:
        problems.append(
            f"{name}: never fired on {len(sig)} candles built to trigger it. "
            "Either the logic is unreachable or the fixture is wrong - both need "
            "looking at."
        )
    return problems


def _check_lookahead(strat):
    """The channel must be built from PRIOR candles, not the current one.

    This is the decisive test for the shift(1) in populate_indicators, and it is
    constructed so that the two implementations give different answers on the
    same candle.

    A Donchian entry asks "did today close above every high that came before it".
    The wrong version asks "did today close above every high including today's".
    Those differ only when today's high is above today's close - which is almost
    every candle. So on a candle where the close is above all PRIOR highs but
    below the CURRENT high:

        correct (shift(1))  -> donchian_high is the prior high, close > it, FIRES
        wrong   (no shift)  -> donchian_high is today's high, close < it, silent

    The fixture below builds exactly that candle, so a missing shift(1) fails
    here rather than quietly inflating every backtest.
    """
    import numpy as np
    import pandas as pd

    problems = []
    rows = 260
    idx = pd.date_range("2024-01-01", periods=rows, freq="D")

    # A flat base, then a clear step up on the final candle.
    close = np.full(rows, 100.0)
    high = np.full(rows, 101.0)
    low = np.full(rows, 99.0)
    # Final candle: closes above every prior high (101.0) but its own high is
    # higher still, at 110. Correct logic sees a breakout; lookahead does not.
    close[-1] = 105.0
    high[-1] = 110.0
    low[-1] = 104.0

    df = pd.DataFrame(
        {
            "open": np.concatenate([[100.0], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(rows, 100.0),
        },
        index=idx,
    )

    out = strat.populate_indicators(df, {"pair": "BTC/CAD"})
    ch = out["donchian_high"].iloc[-1]
    ch_expected = 101.0
    fired = bool(out["donchian_high"].iloc[-1] < out["close"].iloc[-1])

    print(f"  --    final candle: close=105.0, own high=110.0, prior high=101.0")
    print(f"        donchian_high computed as {ch:.2f} (want {ch_expected:.2f})")

    if not np.isclose(ch, ch_expected):
        problems.append(
            f"donchian_high on the final candle is {ch:.2f}, expected {ch_expected:.2f} "
            "(the highest high of the PREVIOUS 20 candles). If it equals 110.0 the "
            "current candle is included in its own channel - a lookahead that makes "
            "backtests better than reality."
        )
        print(f"  FAIL  donchian_high includes the current candle")

    if not fired:
        problems.append(
            "the breakout did not register on a candle that closed above every "
            "prior high - the channel is looking at the wrong candles"
        )
        print("  FAIL  breakout did not fire")
    else:
        print("  ok    breakout fires on a close above the PRIOR high only")

    # And the guard that stops the wrong answer being reachable by accident:
    # a close exactly equal to the channel must not count as a breakout, or the
    # strategy fires on every flat candle.
    df2 = df.copy()
    df2.loc[df2.index[-1], "close"] = 101.0
    df2.loc[df2.index[-1], "high"] = 101.0
    out2 = strat.populate_indicators(df2, {"pair": "BTC/CAD"})
    tie = out2["donchian_high"].iloc[-1] < out2["close"].iloc[-1]
    if tie:
        problems.append("a close exactly at the prior high counted as a breakout")
        print("  FAIL  a tie counted as a breakout")
    else:
        print("  ok    a close exactly at the prior high is not a breakout")

    return problems


def _check_parameters_bind(strat, cls) -> list:
    """Changing a window must change the outcome.

    The previous version of this check flipped the *_enabled switches, which
    gated conditions that no longer exist. The equivalent question for a
    Donchian strategy is whether the window lengths are actually read: a
    parameter wired to nothing is a setting that appears to work, which is more
    dangerous than one that is visibly missing because it is trusted.
    """
    problems = []
    print()
    print("  Window parameters actually change the result (across 3 regimes):")

    regimes = [
        _make_dataframe(seed=20260917, phase=12.0),
        _make_dataframe(seed=7, phase=9.0),
        _make_dataframe(seed=99, phase=15.0),
    ]

    for attr in ("entry_window", "exit_window", "trend_filter_window"):
        param = getattr(cls, attr, None)
        if param is None:
            print(f"    --    {attr} not present, skipped")
            continue
        original = param.value
        moved = 0
        sample = ""
        try:
            for i, regime in enumerate(regimes):
                results = []
                for val in (10, 40, 200):
                    param.value = val
                    out = _analyse(strat, regime)
                    results.append(
                        int((out["enter_long"] == 1).sum())
                        + int((out["exit_long"] == 1).sum())
                    )
                if len(set(results)) > 1:
                    moved += 1
                    if not sample:
                        sample = f"e.g. 10/40/200 -> {results} on shape {i + 1}"
        finally:
            param.value = original

        if moved:
            print(f"    ok    {attr} changes the result on {moved}/3 shapes ({sample})")
        else:
            problems.append(
                f"{attr} made no difference on any of 3 market shapes - it is "
                "wired to nothing"
            )
            print(f"    FAIL  {attr} never changes the result")

    return problems


def _check_real_data(strat) -> list:
    """Run on real Kraken daily candles, not just synthetic ones.

    Synthetic data proves the code runs. It cannot prove the strategy fires on a
    real market, because the fixture was written by the same person who wrote
    the logic and can encode the same wrong assumption. This fetches actual
    candles and reports what the strategy does with them.

    A network failure is reported as a skip, not a failure - the test suite must
    still run without internet access.
    """
    import json
    import urllib.request

    print()
    print("  Real Kraken daily candles (721 per pair, about two years):")

    problems = []
    pairs = {
        "BTC/CAD": "XXBTZCAD",
        "ETH/CAD": "XETHZCAD",
        "SOL/CAD": "SOLCAD",
        "XRP/CAD": "XXRPZCAD",
    }

    import pandas as pd

    for label, kraken_id in pairs.items():
        url = (
            "https://api.kraken.com/0/public/OHLC"
            f"?pair={kraken_id}&interval=1440"
        )
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.load(resp)
        except Exception as exc:
            print(f"    --    {label}: skipped ({type(exc).__name__})")
            continue

        if payload.get("error"):
            print(f"    --    {label}: skipped ({payload['error']})")
            continue

        key = [k for k in payload["result"] if k != "last"][0]
        rows = payload["result"][key]
        df = pd.DataFrame(
            {
                "open": [float(r[1]) for r in rows],
                "high": [float(r[2]) for r in rows],
                "low": [float(r[3]) for r in rows],
                "close": [float(r[4]) for r in rows],
                "volume": [float(r[6]) for r in rows],
            },
            index=pd.to_datetime([int(r[0]) for r in rows], unit="s"),
        )

        out = _analyse(strat, df)
        entries = int((out["enter_long"] == 1).sum())
        exits = int((out["exit_long"] == 1).sum())
        warm = int(out["donchian_high"].isna().sum())
        atr = out["atr_percent"].iloc[-1]

        print(
            f"    ok    {label:9} {len(df):>4} candles, {entries:>2} entries, "
            f"{exits:>2} exits, ATR {atr:>5.2f}%"
        )

        if warm == 0:
            problems.append(f"{label}: no warm-up NaN in donchian_high")

    return problems


def main() -> int:
    print("=" * 72)
    print("THE STRATEGY ACTUALLY RUNS")
    print("=" * 72)

    _install_stubs()
    cls = _load_strategy()
    strat = cls(config={"max_open_trades": 3})

    problems: list[str] = []

    print()
    print("1. Indicators build, and the pipeline runs end to end:")
    df = _make_dataframe()
    try:
        out = _analyse(strat, df)
    except Exception as e:
        import traceback

        print(f"  FAIL  the pipeline raised {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    for col in ("donchian_high", "donchian_low", "ema_trend", "atr", "atr_percent"):
        present = col in out.columns
        print(f"  {'ok  ' if present else 'FAIL'}  {col} present")
        if not present:
            problems.append(f"populate_indicators did not produce {col!r}")

    print()
    print("2. Signal columns are well-formed and reachable:")
    problems += _check_signal("populate_entry_trend", out, "enter_long")
    problems += _check_signal("populate_exit_trend", out, "exit_long")

    print()
    print("2b. Every column plot_config names actually exists:")
    # plot_config named ema_9, ema_21, ema_50, ema_200, bb_lowerband, macd, rsi
    # and stoch_rsi_k after the Donchian rewrite removed all of them. FreqUI
    # would have drawn empty panels for an indicator set the strategy no longer
    # computes, which reads as a broken chart rather than a stale config - and
    # nothing errored, because a plot name is just a string.
    plot_cols = []
    for section in ("main_plot", "subplots"):
        for group, spec in (cls.plot_config.get(section) or {}).items():
            if section == "main_plot":
                plot_cols.append(group)
            else:
                plot_cols.extend(spec.keys() if isinstance(spec, dict) else [])
    missing = sorted({c for c in plot_cols if c not in out.columns})
    print(f"  {'ok  ' if not missing else 'FAIL'}  {len(plot_cols)} plotted column(s), "
          f"{len(missing)} missing")
    if missing:
        print(f"        missing: {missing}")
        problems.append(
            f"plot_config names columns the strategy does not produce: {missing}. "
            "FreqUI would show empty panels."
        )

    print()
    print("3. The channel is built from PRIOR candles (no lookahead):")
    problems += _check_lookahead(strat)

    problems += _check_parameters_bind(strat, cls)
    problems += _check_real_data(strat)

    print()
    print("=" * 72)
    if problems:
        print(f"FAILED - {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASSED - the strategy runs, fires, and does not read the future")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
