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
strategy file, hands it a real DataFrame, and calls the two methods freqtrade
calls. If they raise, the test fails with the traceback.

The stubs are deliberately faithful where it matters. `ta` and `qtpylib` are
implemented with real pandas operations rather than returning constants, because
the bug being guarded against is a pandas *type* error: a stub returning a bare
list would reproduce it, and a stub returning a constant would hide it. The
indicators only need to have the right shape and type, not the right values -
the strategy's arithmetic is its own business, but whether its operands are
Series is exactly what broke.

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
#: working.
ROWS = 400


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
        timeframe = "5m"
        stoploss = -0.05
        minimal_roi = {"0": 0.10}
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

    def MACD(df, fastperiod=12, slowperiod=26, signalperiod=9, **kw):
        s = _series(df)
        macd = EMA(s, fastperiod) - EMA(s, slowperiod)
        sig = macd.ewm(span=int(signalperiod), adjust=False).mean()
        return macd, sig, macd - sig

    def ADX(df, timeperiod=14, **kw):
        return pd.Series(25.0, index=df.index)

    def ATR(df, timeperiod=14, **kw):
        return (df["high"] - df["low"]).rolling(int(timeperiod)).mean()

    def PLUS_DI(df, timeperiod=14, **kw):
        return pd.Series(20.0, index=df.index)

    def MINUS_DI(df, timeperiod=14, **kw):
        return pd.Series(15.0, index=df.index)

    def STOCHRSI(df, timeperiod=14, fastk_period=3, fastd_period=3, **kw):
        r = RSI(df, timeperiod)
        k = (r - r.rolling(int(fastk_period)).min()) / (
            r.rolling(int(fastk_period)).max() - r.rolling(int(fastk_period)).min()
        ) * 100
        return k, k.rolling(int(fastd_period)).mean()

    ta = types.ModuleType("talib.abstract")
    ta.EMA, ta.RSI, ta.MACD, ta.ADX = EMA, RSI, MACD, ADX
    ta.ATR, ta.PLUS_DI, ta.MINUS_DI, ta.STOCHRSI = ATR, PLUS_DI, MINUS_DI, STOCHRSI
    ta.get = lambda name, *a, **kw: globals().get(name)
    talib = types.ModuleType("talib")
    talib.abstract = ta
    sys.modules["talib"] = talib
    sys.modules["talib.abstract"] = ta

    # ---- technical.qtpylib -------------------------------------------------
    def crossed_above(a, b):
        a, b = pd.Series(a), pd.Series(b)
        return (a > b) & (a.shift(1) <= b.shift(1))

    def crossed_below(a, b):
        a, b = pd.Series(a), pd.Series(b)
        return (a < b) & (a.shift(1) >= b.shift(1))

    def bollinger_bands(s, std=2.0, **kw):
        s = pd.Series(s)
        mid = s.rolling(20).mean()
        dev = s.rolling(20).std()
        return mid + std * dev, mid, mid - std * dev

    def typical_price(df):
        return (df["high"] + df["low"] + df["close"]) / 3

    tech = types.ModuleType("technical")
    qtp = types.ModuleType("technical.qtpylib")
    qtp.crossed_above, qtp.crossed_below = crossed_above, crossed_below
    qtp.bollinger_bands, qtp.typical_price = bollinger_bands, typical_price
    qtp.indicators = qtp
    tech.qtpylib = qtp
    sys.modules["technical"] = tech
    sys.modules["technical.qtpylib"] = qtp


def _load_strategy():
    spec = importlib.util.spec_from_file_location("moderate_multi_under_test", STRATEGY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ModerateMultiPairStrategy


def _make_dataframe(seed: int = 20260917, phase: float = 12.0):
    """Candles that actually trend and pull back, so both branches can fire.

    `seed` and `phase` vary the regime, so a condition can be judged across
    more than one market shape rather than one lucky series.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=ROWS, freq="5min")
    # A slow cycle plus noise: guarantees both crossovers and oversold dips,
    # so neither condition group is vacuously empty.
    trend = np.sin(np.linspace(0, phase * np.pi, ROWS)) * 400
    close = pd.Series(60000 + trend + rng.normal(0, 90, ROWS), index=idx)
    high = close + rng.uniform(5, 60, ROWS)
    low = close - rng.uniform(5, 60, ROWS)
    vol = pd.Series(rng.uniform(80, 400, ROWS), index=idx)

    df = pd.DataFrame(
        {"open": close.shift(1).fillna(close.iloc[0]), "high": high,
         "low": low, "close": close, "volume": vol},
        index=idx,
    )
    # The indicator columns populate_indicators would have produced.
    df["ema_9"] = close.ewm(span=9, adjust=False).mean()
    df["ema_21"] = close.ewm(span=21, adjust=False).mean()
    df["rsi"] = 50 + 30 * np.sin(np.linspace(0, 10 * np.pi, ROWS))
    df["macd"] = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    df["macdsignal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macdhist"] = df["macd"] - df["macdsignal"]
    # ADX and the directional indicators must be *derived from the trend*, not
    # drawn independently.
    #
    # Two earlier versions of this fixture failed here, in opposite directions.
    # Constants (adx = 28, di_plus = 22) made the ADX condition vacuously true,
    # so adx_enabled looked like a dead switch. Independent sine waves made it
    # vary but never coincide with the other conditions, so a five-condition
    # confluence entry fired zero times - a fixture that models no correlation
    # cannot produce a confluence, and the strategy looked broken when it was
    # the data that was.
    #
    # In a real market these are not independent: DI+ exceeds DI- while the
    # short EMA is above the long one, and ADX rises with the distance between
    # them. Modelling that is what makes "all five agree" a reachable state.
    # ADX is a LAGGING measure of how strongly price has been moving - it is
    # high in a strong downtrend as much as in a strong uptrend. Modelling it
    # as a function of the current EMA spread got this exactly wrong: right
    # after a crossover the spread is near zero, so ADX was always weakest at
    # the precise candle the entry looks for, and the trend path could not fire
    # at any RSI threshold.
    #
    # Deriving it from recent absolute movement instead means a cross that
    # follows a decisive move still sees elevated ADX, which is what a real
    # chart looks like.
    moves = df["close"].pct_change().abs()
    strength = (moves / moves.quantile(0.95)).clip(0, 1)
    df["adx"] = 12 + 24 * strength.rolling(14, min_periods=1).mean().pow(0.5)
    # DI+/DI- follow the trend direction but LAG it, because they are computed
    # over a 14-period window. Making them track the EMA direction exactly -
    # which is what this fixture did at first - makes "DI+ above DI-" a
    # restatement of "the short EMA is above the long one", so the condition
    # becomes redundant and adx_enabled can never change the outcome. A lagging
    # DI is both more realistic and what keeps that switch meaningful.
    up_now = (df["ema_9"] > df["ema_21"]).astype(float)
    up_lagged = up_now.rolling(10, min_periods=1).mean()
    df["di_plus"] = 14 + 16 * up_lagged
    df["di_minus"] = 30 - 16 * up_lagged
    # Must exceed volume_factor * 1.5 (1.5 * 1.5 = 2.25) on some candles,
    # or the mean-reversion path is unreachable for fixture reasons.
    df["volume_ratio"] = 1.2 + 1.6 * (np.sin(np.linspace(0, 20 * np.pi, ROWS)) + 1) / 2
    df["bb_percent"] = (np.sin(np.linspace(0, 8 * np.pi, ROWS)) + 1) / 2
    return df


def _check(name, df, fn, sig_col, fired_paths=None):
    """Call one signal method and check the signal column is well-formed."""
    problems = []
    try:
        out = fn(df.copy(), {"pair": "BTC/CAD"})
    except Exception as e:
        print(f"  FAIL  {name} raised {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return [f"{name} raised {type(e).__name__}: {e}"]

    if sig_col not in out.columns:
        problems.append(f"{name} did not create the {sig_col!r} column")
        print(f"  FAIL  no {sig_col!r} column produced")
        return problems

    sig = out[sig_col]
    n_on = int((sig == 1).sum())
    if "enter_tag" in out.columns and sig_col == "enter_long":
        tags = out.loc[sig == 1, "enter_tag"].value_counts().to_dict()
        print(f"        entry paths that fired: {tags or 'none'}")
        fired_paths.update(tags.keys())
    n_nan = int(sig.isna().sum())
    bad = sorted(set(sig.dropna().unique()) - {0, 1})

    print(f"  ok    {name}: {sig_col} has {n_on} signal(s) out of {len(sig)} rows, "
          f"{n_nan} NaN")

    if n_nan:
        problems.append(
            f"{name}: {n_nan} NaN value(s) in {sig_col}. freqtrade treats a "
            "missing signal as an error; the column must be 0 or 1 everywhere."
        )
    if bad:
        problems.append(f"{name}: {sig_col} contains non-0/1 values: {bad}")
    if n_on == 0:
        problems.append(
            f"{name}: never fired on {len(sig)} synthetic candles that were built "
            "to trigger it. Either the logic is unreachable or the test data is "
            "wrong - both need looking at."
        )
    return problems


def _check_switches(strat, df, cls) -> list:
    """Every *_enabled switch must actually change the outcome.

    The exit block used to drop conditions[2] and beyond, which meant the MACD
    and Bollinger exit switches were connected to nothing. The operator could
    turn an exit off and see no change at all - a setting that appears to work
    is more dangerous than one that is visibly missing, because it is trusted.
    So: flip each switch, and require the signal count to move.
    """
    problems = []
    print()
    print("  Configured switches actually do something (across 4 market shapes):")
    cases = [
        ("sell_bb_enabled", "exit_long", strat.populate_exit_trend),
        ("sell_macd_enabled", "exit_long", strat.populate_exit_trend),
        ("sell_rsi_enabled", "exit_long", strat.populate_exit_trend),
        # The buy-side toggles matter for the same reason. Note the direction
        # differs: turning a buy condition OFF relaxes the AND, so it should
        # produce *more* entries, not fewer. Either movement is a pass; no
        # movement is a dead switch.
        ("buy_macd_enabled", "enter_long", strat.populate_entry_trend),
        ("buy_bb_enabled", "enter_long", strat.populate_entry_trend),
        ("buy_rsi_enabled", "enter_long", strat.populate_entry_trend),
        ("adx_enabled", "enter_long", strat.populate_entry_trend),
        ("volume_enabled", "enter_long", strat.populate_entry_trend),
    ]
    regimes = [
        _make_dataframe(seed=20260917, phase=12.0),
        _make_dataframe(seed=7, phase=9.0),
        _make_dataframe(seed=99, phase=15.0),
        _make_dataframe(seed=4242, phase=6.0),
    ]

    for attr, col, fn in cases:
        param = getattr(cls, attr, None)
        if param is None:
            print(f"    --    {attr} not present, skipped")
            continue
        original = param.value
        moved = 0
        sample = ""
        try:
            for i, regime in enumerate(regimes):
                param.value = True
                on = int((fn(regime.copy(), {"pair": "BTC/CAD"})[col] == 1).sum())
                param.value = False
                off = int((fn(regime.copy(), {"pair": "BTC/CAD"})[col] == 1).sum())
                if on != off:
                    moved += 1
                    if not sample:
                        sample = f"e.g. {on} -> {off} on shape {i + 1}"
        finally:
            param.value = original

        # A condition that is correctly wired can still fail to bind on any one
        # dataset, because another condition already excludes those candles. So
        # the test asks whether the switch moves the outcome on ANY shape. Only
        # a switch that never moves it - which is what the dropped-conditions
        # bug produced - is dead.
        mark = "ok   " if moved else "FAIL "
        print(f"    {mark} {attr:20} moved on {moved}/{len(regimes)} shapes  {sample}")
        if not moved:
            problems.append(
                f"{attr} changed nothing on any of {len(regimes)} market shapes: "
                "the switch is not wired to the signal it claims to control."
            )
    return problems


def _check_reachability(strat, cls) -> list:
    """Every entry path must be reachable on at least one market shape.

    The trend path once required an EMA crossover AND a MACD crossover on the
    same candle, which fired zero times on every shape: the strategy was
    described as trend-following and was in practice mean-reversion only.

    Reachability is asserted rather than a per-shape count, because five ANDed
    conditions make a trend entry genuinely uncommon and some shapes will
    legitimately produce none. What must never happen is a path that is
    unreachable everywhere - which is exactly what the bug produced.
    """
    problems = []
    print()
    print("  Entry paths reachable across market shapes:")
    shapes = [(20260917, 12.0), (7, 9.0), (99, 15.0), (4242, 6.0), (1234, 18.0)]
    seen: dict = {}
    for seed, phase in shapes:
        d = _make_dataframe(seed=seed, phase=phase)
        out = strat.populate_entry_trend(d.copy(), {"pair": "BTC/CAD"})
        tags = out.loc[out["enter_long"] == 1, "enter_tag"].value_counts().to_dict()
        for k, v in tags.items():
            seen[k] = seen.get(k, 0) + v
    print(f"        totals across {len(shapes)} shapes: {seen or 'none'}")
    for path in ("trend_follow", "mean_reversion"):
        mark = "ok   " if seen.get(path) else "FAIL "
        print(f"    {mark} {path:18} {seen.get(path, 0)} signal(s)")
        if not seen.get(path):
            problems.append(
                f"entry path {path!r} never fired on any of {len(shapes)} market "
                "shapes - that path is unreachable."
            )
    return problems


def main() -> int:
    print("Strategy executes end to end (entry and exit signals):")
    if not STRATEGY.exists():
        print(f"FAIL - strategy not found at {STRATEGY}")
        return 1

    _install_stubs()
    try:
        cls = _load_strategy()
    except Exception as e:
        print(f"  FAIL  importing the strategy raised {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    strat = cls(config={"stake_currency": "CAD"})
    df = _make_dataframe()
    fired_paths: set = set()

    problems = []
    problems += _check("populate_entry_trend", df, strat.populate_entry_trend,
                       "enter_long", fired_paths)
    problems += _check("populate_exit_trend", df, strat.populate_exit_trend, "exit_long")
    problems += _check_reachability(strat, cls)
    problems += _check_switches(strat, df, cls)

    print()
    if problems:
        print(f"FAILED - {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASSED - the strategy runs and produces usable signals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
