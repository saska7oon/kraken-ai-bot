#!/usr/bin/env python3
"""Which entry condition is actually blocking this strategy?

Why
---
The strategy produced one signal in thirty days. "Too few trades" is not
actionable on its own - five conditions are ANDed for the trend entry and four
for the mean-reversion entry, and relaxing the wrong one changes nothing.

This counts, for real 1h data, how many candles pass each condition alone, then
in the order they are combined, so the binding constraint is visible as the step
where the count collapses.

That distinction matters because the conditions are wildly different in how
restrictive they are. A condition that alone passes 40% of candles is not the
problem even if it is the one that "feels" cautious.

Not a backtest, not advice - a measurement of which knob does something.
"""

from __future__ import annotations

import statistics
import sys

sys.path.insert(0, "tools")
from fee_hurdle_analysis import (  # noqa: E402
    ADX_MIN, BB_STD, BB_WINDOW, BUY_RSI, EMA_LONG, EMA_SHORT, MR_RSI,
    ROUND_TRIP_FEE, TREND_WINDOW, VOLUME_FACTOR,
    adx_di, bollinger, ema, fetch, macd, rsi,
)

PAIRS = {"BTC/CAD": "XBTCAD", "SOL/CAD": "SOLCAD", "XRP/CAD": "XXRPZCAD"}


def diagnose(label: str, pair: str) -> None:
    candles = fetch(pair, 60)
    if len(candles) < 250:
        print(f"  {label}: not enough candles")
        return

    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]
    e_s, e_l = ema(closes, EMA_SHORT), ema(closes, EMA_LONG)
    r = rsi(closes)
    m_line, m_sig, m_hist = macd(closes)
    a, pdi, ndi = adx_di(candles)
    _, _, _, bb_pct = bollinger(closes, BB_WINDOW, BB_STD)
    vmean = [statistics.mean(vols[max(0, i - 19):i + 1]) for i in range(len(vols))]

    def cross_above(x, y, i):
        return i > 0 and x[i - 1] <= y[i - 1] and x[i] > y[i]

    idx = range(210, len(candles) - 1)
    total = len(list(idx))

    # Each condition measured alone.
    alone = {
        "EMA cross within window": lambda i: any(
            cross_above(e_s, e_l, j) for j in range(max(1, i - TREND_WINDOW + 1), i + 1)
        ) and e_s[i] > e_l[i],
        f"RSI < {BUY_RSI}": lambda i: r[i] < BUY_RSI,
        f"ADX > {ADX_MIN} and DI+ > DI-": lambda i: a[i] > ADX_MIN and pdi[i] > ndi[i],
        "MACD > signal": lambda i: m_line[i] > m_sig[i],
        f"volume > {VOLUME_FACTOR}x mean": lambda i: vmean[i] > 0 and vols[i] / vmean[i] > VOLUME_FACTOR,
    }

    print(f"  {label}  ({total} candles examined)")
    print(f"    {'condition (alone)':32} {'passes':>7} {'%':>7}")
    for name, fn in alone.items():
        n = sum(1 for i in idx if fn(i))
        print(f"    {name:32} {n:>7} {n/total*100:>6.1f}%")

    # Cumulative, in the order populate_entry_trend combines them.
    print(f"    {'-'*32} {'-'*7} {'-'*7}")
    order = list(alone.items())
    passing = set(idx)
    for name, fn in order:
        passing = {i for i in passing if fn(i)}
        print(f"    {'AND ' + name:32} {len(passing):>7} {len(passing)/total*100:>6.1f}%")

    # Mean reversion, separately.
    mr_alone = {
        "BB percent < 0.1": lambda i: bb_pct[i] is not None and bb_pct[i] < 0.1,
        f"RSI < {MR_RSI}": lambda i: r[i] < MR_RSI,
        "MACD hist rising": lambda i: m_hist[i] > m_hist[i - 1],
        f"volume > {VOLUME_FACTOR*1.5:.2f}x mean": lambda i: vmean[i] > 0 and vols[i] / vmean[i] > VOLUME_FACTOR * 1.5,
    }
    print()
    print(f"    {'mean-reversion (alone)':32} {'passes':>7} {'%':>7}")
    for name, fn in mr_alone.items():
        n = sum(1 for i in idx if fn(i))
        print(f"    {name:32} {n:>7} {n/total*100:>6.1f}%")
    passing = set(idx)
    for name, fn in mr_alone.items():
        passing = {i for i in passing if fn(i)}
        print(f"    {'AND ' + name:32} {len(passing):>7} {len(passing)/total*100:>6.1f}%")

    # How often is a move of the required size even available?
    need = ROUND_TRIP_FEE
    up = sum(1 for i in idx if i + 6 < len(closes) and (closes[i+6]-closes[i])/closes[i] > need)
    dn = sum(1 for i in idx if i + 6 < len(closes) and (closes[i+6]-closes[i])/closes[i] < -need)
    print()
    print(f"    candles where a +{need*100:.1f}% move happened within 6 candles: "
          f"{up} ({up/total*100:.1f}%)")
    print(f"    candles where a -{need*100:.1f}% move happened within 6 candles: "
          f"{dn} ({dn/total*100:.1f}%)")
    print()


def main() -> int:
    print("=" * 78)
    print("Which condition blocks the entry?")
    print("=" * 78)
    print()
    for label, pair in PAIRS.items():
        try:
            diagnose(label, pair)
        except Exception as e:
            print(f"  {label}: {type(e).__name__}: {e}\n")
    print("=" * 78)
    print("  The binding constraint is the step where the count collapses.")
    print("  'A move of the required size' is the ceiling on any entry rule: if")
    print("  that percentage is small, no signal can be profitable often enough.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
