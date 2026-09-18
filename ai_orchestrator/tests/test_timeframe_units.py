#!/usr/bin/env python3
"""The timeframe, the ROI ladder, the stoploss and the protections must agree.

Why this exists
---------------
Every one of these settings is a number whose meaning depends on the candle
length, and none of them says so in its own name. "30" in a minimal_roi ladder is
thirty MINUTES. A stoploss of -0.08 is a percentage of price, but whether it is
tight or loose depends entirely on how far the pair moves per candle. A
protection window of "24" is twenty-four CANDLES.

Move the timeframe and every one of them silently changes meaning. Nothing
errors. The bot starts, trades, and the numbers in the config still look
reasonable.

That is not hypothetical - it has now happened three times in this repository:

  1. minimal_roi was written for 5m, rescaled in the STRATEGY to 1h, and the
     CONFIG copy was left at the 5m values. The config wins, so the strategy's
     corrected ladder was dead.

  2. The same thing happened again on the move to 1d: the config's ladder still
     read {"0": 0.04, "30": 0.02, "60": 0.01, "120": 0}. At 1d that means "sell
     any profitable position after 2 hours", which is one twelfth of a candle.

  3. config/base.json declared "timeframe": "1h" while the strategy declared
     "1d" - and the comment next to it claimed freqtrade would use the
     strategy's value. It does not. The config wins.

Each time, the check in this file read only the STRATEGY and compared it to the
CONFIG's timeframe. It never compared the two copies of the numbers that had
actually drifted. It passed while the bug was live.

So this version checks both files, checks them against EACH OTHER, and checks the
precedence is documented - because the failure mode is not "a number is wrong",
it is "there are two numbers and the one in force is not the one you read".
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BASE = REPO / "config" / "base.json"
CANADA = REPO / "config" / "canada_kraken.json"
STRATEGY = REPO / "config" / "strategies" / "moderate_multi.py"

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "ok  " if ok else "FAIL"
    print(f"  {mark}  {label}")
    if detail and not ok:
        print(f"          {detail}")
    if not ok:
        FAILURES.append(label)


def load_config(path: pathlib.Path) -> dict:
    """Parse a freqtrade config, which is JSON with // and /* */ comments."""
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
    raw = re.sub(r",(\s*[}\]])", r"\1", raw)
    return json.loads(raw)


def timeframe_minutes(tf: str) -> int | None:
    m = re.fullmatch(r"(\d+)([mhdw])", str(tf).strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit]


def strategy_attrs() -> dict:
    """Read class-level assignments off the strategy without importing it."""
    tree = ast.parse(STRATEGY.read_text(encoding="utf-8"))
    out: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ModerateMultiPairStrategy":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    name = getattr(stmt.targets[0], "id", None)
                    if name:
                        try:
                            out[name] = ast.literal_eval(stmt.value)
                        except ValueError:
                            pass
    return out


def protection_candles() -> list[tuple[str, str, int]]:
    """Every integer field inside the protections property."""
    tree = ast.parse(STRATEGY.read_text(encoding="utf-8"))
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "protections":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Dict):
                    keys = [k.value for k in sub.keys if isinstance(k, ast.Constant)]
                    method = next(
                        (k for k in keys if isinstance(k, str) and k.endswith("Period")
                         or k in ("MaxDrawdown", "StoplossGuard", "CooldownPeriod")),
                        None,
                    )
                    for k, v in zip(sub.keys, sub.values):
                        if not isinstance(v, ast.Constant) or not isinstance(v.value, int):
                            continue
                        if not isinstance(k.value, str):
                            continue
                        if "candle" in k.value or "period" in k.value:
                            found.append((method or "protection", k.value, v.value))
    return found


def main() -> int:
    print("=" * 72)
    print("Every time-dependent setting must agree across both files")
    print("=" * 72)

    cfg = load_config(BASE)
    canada = load_config(CANADA)
    attrs = strategy_attrs()

    cfg_tf = cfg.get("timeframe")
    strat_tf = attrs.get("timeframe")
    minutes = timeframe_minutes(strat_tf or "")

    print("\n1. The timeframe, in both files:")
    check("config sets a timeframe", bool(cfg_tf), repr(cfg_tf))
    check("strategy sets a timeframe", bool(strat_tf), repr(strat_tf))
    check(
        "they are the same",
        cfg_tf == strat_tf,
        f"config={cfg_tf!r} strategy={strat_tf!r}. The CONFIG wins - "
        "freqtrade/resolvers/strategy_resolver.py resolves these with the "
        "precedence 'Configuration, Strategy, default' and ('timeframe', None) "
        "is in that list, so the strategy's value is discarded.",
    )
    check("the timeframe is parseable", minutes is not None, repr(strat_tf))
    if minutes is None:
        print("\nFAILED - cannot continue without a valid timeframe")
        return 1
    print(f"        {strat_tf} = {minutes} minutes per candle")

    # The numbers that must match between the two files. A mismatch means the
    # file an operator reads is not the file in force.
    print("\n2. Both configs and the strategy agree on every shared number:")
    shared = (
        "stoploss",
        "trailing_stop",
        "trailing_stop_positive",
        "trailing_stop_positive_offset",
        "trailing_only_offset_is_reached",
        "minimal_roi",
    )
    for key in shared:
        in_cfg = cfg.get(key)
        in_canada = canada.get(key)
        in_strat = attrs.get(key)
        check(
            f"{key} is identical in base.json and canada_kraken.json",
            in_cfg == in_canada,
            f"base={in_cfg!r} canada={in_canada!r} - both are loaded, so the "
            "bot's behaviour would depend on file order",
        )
        if in_strat is not None:
            check(
                f"{key} agrees with the strategy",
                in_cfg == in_strat,
                f"config={in_cfg!r} strategy={in_strat!r} - the config wins, so "
                "the strategy's value is dead code",
            )

    print("\n3. The ROI ladder means something at this timeframe:")
    roi = cfg.get("minimal_roi") or {}
    durations = sorted(int(k) for k in roi if str(k).isdigit())
    nonzero = [d for d in durations if d > 0]
    check("minimal_roi is set in the config", bool(roi), repr(roi))

    # Two legitimate shapes, and nothing in between:
    #   - disabled: a single unreachable target, correct for trend following
    #   - a real ladder that spans several candles
    disabled = len(nonzero) == 0 and all(v >= 1 for v in roi.values())
    if disabled:
        check(
            "ROI is deliberately switched off (unreachable target)",
            True,
            "",
        )
        print(f"        target {list(roi.values())} is unreachable by design")
    else:
        if nonzero:
            longest = max(nonzero)
            check(
                f"the ladder spans at least 3 candles ({3 * minutes} minutes)",
                longest >= 3 * minutes,
                f"longest key is {longest} minutes = {longest / minutes:.2f} candles "
                f"at {strat_tf}; the ladder would decay almost immediately",
            )
            check(
                "every duration is a whole number of candles",
                all(d % minutes == 0 for d in nonzero),
                f"durations {nonzero} are not multiples of {minutes}",
            )
        else:
            check(
                "the ladder is either disabled or spans several candles",
                False,
                f"{roi} has a duration of 0 but no unreachable target - it would "
                "close any profitable position at once",
            )

    print("\n4. The stoploss is plausible for this timeframe:")
    stop = cfg.get("stoploss")
    check("stoploss is set", isinstance(stop, (int, float)), repr(stop))
    if isinstance(stop, (int, float)):
        check(
            "stoploss is within the range RULE 2 permits (-0.02 to -0.15)",
            -0.15 <= stop <= -0.02,
            f"{stop} is outside it - "
            "ai_orchestrator/plugins/strategy_generator.py defines that range",
        )
        # Measured daily ATR from Kraken: 2.70 / 3.69 / 4.22 / 5.72 percent.
        # A stop below 2x the highest of those is inside ordinary daily noise.
        highest_atr = 0.0572
        check(
            "stoploss is at least 2x the highest measured daily ATR",
            abs(stop) >= 2 * highest_atr,
            f"|{stop}| = {abs(stop):.3f} but 2xATR on XRP/CAD is "
            f"{2 * highest_atr:.3f} - the stop would be hit by a normal day "
            "rather than by the trade being wrong",
        )

    print("\n5. The protections are plausible wall-clock durations:")
    prot = protection_candles()
    check("protections are defined in the strategy", bool(prot), "none found")
    for method, field, value in sorted(set(prot)):
        hours = value * minutes / 60
        ok = 1 <= hours <= 24 * 31
        check(
            f"{method}.{field} = {value} candles ({hours:.1f}h)",
            ok,
            "outside the plausible 1h-31d range - likely not rescaled",
        )

    print("\n6. The units and the override precedence are written down:")
    raw = STRATEGY.read_text(encoding="utf-8")
    cfg_raw = BASE.read_text(encoding="utf-8")
    for needed, why, where in (
        ("MINUTES", "the ROI keys' unit is stated", raw),
        ("CANDLES", "the protections' unit is stated", raw),
        ("rescaled", "the rescaling is recorded", raw),
        # The single most valuable sentence in either file, because the wrong
        # version of it is what let three separate drifts go unnoticed.
        ("Configuration, Strategy, default",
         "the override precedence is stated", cfg_raw + raw),
    ):
        check(f"the comment {why}", needed in where)

    print()
    print("=" * 72)
    if FAILURES:
        print(f"FAILED - {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASSED - every time-dependent number agrees across both files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
