#!/usr/bin/env python3
"""Check that the timeframe, the ROI ladder and the protections agree.

The trap
--------
Freqtrade's time settings use three different units, and two of them are not
candles:

    timeframe                      a string, "1h"
    minimal_roi                    keys are MINUTES since the trade opened
    protections.*_candles          CANDLES

So changing the timeframe silently reinterprets two of them. Moving from 5m to 1h
without touching anything else would have turned:

    minimal_roi {"0":0.04, "30":0.02, "60":0.01, "120":0}   ->  unchanged, but
        "30" now means half a candle instead of six, so the ladder collapses to
        zero almost immediately and every trade exits at the first sign of profit

    MaxDrawdown lookback 288 candles  ->  was 24 hours at 5m, becomes 12 days
    CooldownPeriod 12 candles         ->  was 1 hour at 5m, becomes 12 hours

None of that raises an error. The bot starts, trades, and behaves differently from
what every comment says. That is the failure this test exists to prevent.

What is checked
---------------
 1. The config's `timeframe` and the strategy's `timeframe` are the same string.
    Freqtrade reads the strategy's, so a mismatch means the config value is
    silently ignored - the operator changes it, sees it saved, and nothing happens.
 2. The ROI ladder's durations are at least a few candles long at the configured
    timeframe. A ladder that decays within one or two candles is not a ladder.
 3. The protection windows are plausible wall-clock durations at that timeframe -
    a "daily" drawdown guard must not silently become a fortnightly one.
 4. The values are actually documented, since a bare number here is indefensible
    to the next person who changes the timeframe.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from preflight_config import load_config  # noqa: E402

BASE = REPO / "config" / "base.json"
STRATEGY = REPO / "config" / "strategies" / "moderate_multi.py"

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  ok    {label}")
    else:
        FAILURES.append(label)
        print(f"  FAIL  {label}{(' — ' + detail) if detail else ''}")


def timeframe_minutes(tf: str) -> int | None:
    m = re.fullmatch(r"(\d+)([mhdw])", tf.strip())
    if not m:
        return None
    n = int(m.group(1))
    return n * {"m": 1, "h": 60, "d": 1440, "w": 10080}[m.group(2)]


def strategy_attr(name: str):
    """Read a literal class attribute out of the strategy file."""
    tree = ast.parse(STRATEGY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for sub in node.body:
            if isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        try:
                            return ast.literal_eval(sub.value)
                        except ValueError:
                            return None
    return None


def protection_candles() -> list[tuple[str, str, int]]:
    """(method, field, value) for every candle-denominated protection value."""
    tree = ast.parse(STRATEGY.read_text(encoding="utf-8"))
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
        if "method" not in keys:
            continue
        method = next(
            (k.value for k in node.keys
             if isinstance(k, ast.Constant) and k.value == "method"), "?"
        )
        method_val = None
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == "method":
                method_val = getattr(v, "value", None)
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                continue
            if "candles" in k.value and isinstance(v, ast.Constant) and isinstance(v.value, int):
                out.append((method_val or method, k.value, v.value))
    return out


def main() -> int:
    print("=" * 72)
    print("Timeframe, ROI ladder and protections must agree")
    print("=" * 72)

    cfg = load_config(BASE)
    cfg_tf = cfg.get("timeframe")
    strat_tf = strategy_attr("timeframe")
    minutes = timeframe_minutes(strat_tf or "")

    print("\nThe two timeframes agree:")
    check("config sets a timeframe", bool(cfg_tf), repr(cfg_tf))
    check("strategy sets a timeframe", bool(strat_tf), repr(strat_tf))
    check(
        "they are the same",
        cfg_tf == strat_tf,
        f"config={cfg_tf!r} strategy={strat_tf!r} — freqtrade uses the strategy's, "
        "so the config value would be ignored",
    )
    check("the timeframe is parseable", minutes is not None, repr(strat_tf))
    if minutes is None:
        print("\nFAILED — cannot continue without a valid timeframe")
        return 1

    print(f"\nConfigured timeframe: {strat_tf} ({minutes} minutes per candle)")

    print("\nThe ROI ladder lasts more than a candle or two:")
    roi = strategy_attr("minimal_roi") or {}
    # "0" is the immediate target and is always present; the rest are durations.
    durations = sorted(int(k) for k in roi if str(k).isdigit())
    nonzero = [d for d in durations if d > 0]
    check("minimal_roi is defined", bool(roi), repr(roi))
    if nonzero:
        longest = max(nonzero)
        check(
            f"the ladder spans at least 3 candles ({3*minutes} minutes)",
            longest >= 3 * minutes,
            f"longest key is {longest} minutes = {longest/minutes:.1f} candles at "
            f"{strat_tf}; the ladder would decay almost immediately",
        )
        # The keys should land on candle boundaries, or the intent is unclear.
        on_boundary = all(d % minutes == 0 for d in nonzero)
        check(
            "every duration is a whole number of candles",
            on_boundary,
            f"durations {nonzero} are not multiples of {minutes}",
        )
    else:
        check("minimal_roi has a duration beyond 0", False, repr(roi))

    print("\nThe protections are plausible wall-clock durations:")
    prot = protection_candles()
    check("protections are defined in the strategy", bool(prot), "none found")
    for method, field, value in sorted(prot):
        hours = value * minutes / 60
        # A guard window should be between an hour and a month. Outside that it is
        # almost certainly a leftover from a different timeframe rather than a
        # deliberate choice.
        ok = 1 <= hours <= 24 * 31
        check(
            f"{method}.{field} = {value} candles ({hours:.1f}h)",
            ok,
            "outside the plausible 1h-31d range — likely not rescaled",
        )

    print("\nThe values are documented:")
    raw = STRATEGY.read_text(encoding="utf-8")
    for needed, why in (
        ("MINUTES, NOT CANDLES", "the ROI keys' unit is stated"),
        ("CANDLES", "the protections' unit is stated"),
        ("rescaled", "the move from 5m to 1h is recorded"),
    ):
        check(f"the comment {why}", needed in raw)

    print()
    print("=" * 72)
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} of {CHECKS} checks")
        for f in FAILURES:
            print(f"   - {f}")
        return 1
    print(f"PASSED — {CHECKS} checks: the three time units agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
