#!/usr/bin/env python3
"""Do this strategy's own signals clear Kraken's real fee?

The question
------------
A strategy can look reasonable and still be impossible: if the moves it catches
are smaller than the round-trip cost, every trade loses regardless of how good the
signal is. That is a property of the fee and the timeframe, not of the strategy's
cleverness, and it is invisible in a signal count.

So this measures the thing that decides it - the forward move after each real
signal, against the 1.60% round trip that Kraken Tier 1 charges.

How
---
Fetches real OHLC from Kraken's public API and evaluates the strategy's ACTUAL
entry conditions, transcribed from config/strategies/moderate_multi.py. The
indicators are reimplemented in pandas because talib is not installed in every
environment this runs in.

This is deliberately a reimplementation and not an import of the strategy file.
An import would need freqtrade and talib present, which would mean the check could
not run where it is most useful. The cost is that the two can drift - so the
conditions below name the line they came from, and `test_fee_hurdle.py` asserts the
strategy still contains those conditions.

What this is NOT
----------------
Not a backtest. It does not model position sizing, stoploss, ROI, trailing stops,
the protections, or the order book. It answers one narrow question - is the move
bigger than the fee - and a strategy can pass this and still lose money, or fail it
and still be worth running on a different timeframe. Read it as a feasibility
filter, not a verdict.

The sample is small and that is stated, not hidden: Kraken's public OHLC serves 720
candles per interval, so 1h gives 30 days. Thirty days is not enough to conclude
anything about edge. It IS enough to check whether a move of the required size
occurs at all, which is what the fee hurdle asks.
"""

from __future__ import annotations

import json
import statistics
import sys
import urllib.request

PAIRS = {
    "BTC/CAD": "XBTCAD",
    "ETH/CAD": "XETHCAD",
    "SOL/CAD": "SOLCAD",
    "XRP/CAD": "XXRPZCAD",
}

#: Kraken Tier 1 taker, both sides. See config/base.json's fee block.
ROUND_TRIP_FEE = 0.016

#: The strategy's own parameters, from config/strategies/moderate_multi.py.
EMA_SHORT, EMA_LONG = 9, 21
TREND_WINDOW = 8
RSI_PERIOD = 14
BUY_RSI = 30          # trend entry: rsi < 30
MR_RSI = 35           # mean-reversion entry: rsi < 35
ADX_PERIOD = 14
ADX_MIN = 25
VOLUME_FACTOR = 1.5
BB_WINDOW, BB_STD = 20, 2.0


def fetch(pair: str, interval: int) -> list[dict]:
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    with urllib.request.urlopen(url, timeout=45) as r:
        d = json.load(r)
    if d.get("error"):
        return []
    key = [k for k in d["result"] if k != "last"][0]
    out = []
    for row in d["result"][key]:
        out.append({
            "t": int(row[0]), "open": float(row[1]), "high": float(row[2]),
            "low": float(row[3]), "close": float(row[4]), "volume": float(row[6]),
        })
    return out


# ---------------------------------------------------------------------------
# Indicators, reimplemented (talib is not always available)
# ---------------------------------------------------------------------------
def ema(vals: list[float], n: int) -> list[float]:
    out, k = [], 2.0 / (n + 1)
    prev = None
    for v in vals:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def wilder(vals: list[float], n: int) -> list[float]:
    """Wilder's smoothing, which is what RSI/ADX/ATR use - not a plain EMA."""
    out, prev = [], None
    for v in vals:
        prev = v if prev is None else (prev * (n - 1) + v) / n
        out.append(prev)
    return out


def rsi(closes: list[float], n: int = 14) -> list[float]:
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = wilder(gains, n), wilder(losses, n)
    out = []
    for g, l in zip(ag, al):
        out.append(100.0 if l == 0 else 100 - 100 / (1 + g / l))
    return out


def macd(closes: list[float]):
    fast, slow = ema(closes, 12), ema(closes, 26)
    line = [f - s for f, s in zip(fast, slow)]
    sig = ema(line, 9)
    return line, sig, [l - s for l, s in zip(line, sig)]


def adx_di(candles: list[dict], n: int = 14):
    tr, pdm, ndm = [0.0], [0.0], [0.0]
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        ph, pl = candles[i - 1]["high"], candles[i - 1]["low"]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
        up, dn = h - ph, pl - l
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)
    atr = wilder(tr, n)
    pdi = [100 * p / a if a else 0 for p, a in zip(wilder(pdm, n), atr)]
    ndi = [100 * m / a if a else 0 for m, a in zip(wilder(ndm, n), atr)]
    dx = [100 * abs(p - m) / (p + m) if (p + m) else 0 for p, m in zip(pdi, ndi)]
    return wilder(dx, n), pdi, ndi


def bollinger(closes: list[float], n: int = 20, stds: float = 2.0):
    upper, mid, lower, pct = [], [], [], []
    for i in range(len(closes)):
        if i + 1 < n:
            upper.append(None); mid.append(None); lower.append(None); pct.append(None)
            continue
        w = closes[i + 1 - n:i + 1]
        m = statistics.mean(w)
        s = statistics.pstdev(w)
        u, lo = m + stds * s, m - stds * s
        upper.append(u); mid.append(m); lower.append(lo)
        pct.append((closes[i] - lo) / (u - lo) if u != lo else 0.5)
    return upper, mid, lower, pct


# ---------------------------------------------------------------------------
def analyse(label: str, pair: str, interval: int, tf_name: str) -> dict | None:
    candles = fetch(pair, interval)
    if len(candles) < 250:
        print(f"  {label:9} {tf_name:>3}  not enough candles ({len(candles)})")
        return None

    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]

    e_s, e_l = ema(closes, EMA_SHORT), ema(closes, EMA_LONG)
    r = rsi(closes, RSI_PERIOD)
    m_line, m_sig, m_hist = macd(closes)
    a, pdi, ndi = adx_di(candles, ADX_PERIOD)
    _, _, _, bb_pct = bollinger(closes, BB_WINDOW, BB_STD)
    vmean = [statistics.mean(vols[max(0, i - 19):i + 1]) for i in range(len(vols))]

    def cross_above(x, y, i):
        return i > 0 and x[i - 1] <= y[i - 1] and x[i] > y[i]

    signals = []
    for i in range(210, len(candles) - 1):
        # trend entry - populate_entry_trend, "Condition 1"
        cross_recent = any(cross_above(e_s, e_l, j) for j in range(max(1, i - TREND_WINDOW + 1), i + 1))
        trend = (
            cross_recent and e_s[i] > e_l[i]
            and r[i] < BUY_RSI
            and a[i] > ADX_MIN and pdi[i] > ndi[i]
            and m_line[i] > m_sig[i]
            and vmean[i] > 0 and vols[i] / vmean[i] > VOLUME_FACTOR
        )
        # mean-reversion entry - "Condition 2"
        mr = (
            bb_pct[i] is not None and bb_pct[i] < 0.1
            and r[i] < MR_RSI
            and m_hist[i] > m_hist[i - 1]
            and vmean[i] > 0 and vols[i] / vmean[i] > VOLUME_FACTOR * 1.5
        )
        if trend or mr:
            signals.append((i, "trend" if trend else "mr"))

    if not signals:
        print(f"  {label:9} {tf_name:>3}  {len(candles):>4} candles   "
              f"0 signals")
        return {"pair": label, "tf": tf_name, "signals": 0}

    # Forward return at several horizons, gross and net of the fee.
    horizons = [1, 3, 6, 12, 24]
    rows = {}
    for h in horizons:
        rets = [(closes[i + h] - closes[i]) / closes[i] for i, _ in signals if i + h < len(closes)]
        if not rets:
            continue
        net = [x - ROUND_TRIP_FEE for x in rets]
        rows[h] = {
            "n": len(rets),
            "mean_gross": statistics.mean(rets),
            "mean_net": statistics.mean(net),
            "best_net": max(net),
            "win_net": sum(1 for x in net if x > 0) / len(net),
        }

    kinds = {}
    for _, k in signals:
        kinds[k] = kinds.get(k, 0) + 1

    print(f"  {label:9} {tf_name:>3}  {len(candles):>4} candles   "
          f"{len(signals):>3} signals  ({kinds.get('trend',0)} trend, {kinds.get('mr',0)} mean-rev)")
    for h, s in rows.items():
        print(f"              +{h:>2} candles: mean gross {s['mean_gross']*100:>6.2f}%   "
              f"mean net {s['mean_net']*100:>6.2f}%   "
              f"best {s['best_net']*100:>6.2f}%   winners {s['win_net']*100:>4.0f}%")

    return {"pair": label, "tf": tf_name, "signals": len(signals), "rows": rows}


def main() -> int:
    print("=" * 78)
    print("Do this strategy's signals clear Kraken's 1.60% round trip?")
    print("=" * 78)
    print()
    print(f"  round trip charged: {ROUND_TRIP_FEE*100:.2f}%  (Tier 1 taker, both sides)")
    print("  net = gross forward move minus that fee. A negative net means the")
    print("  average trade loses money even when the signal was right.")
    print()

    results = []
    for label, pair in PAIRS.items():
        for tf_name, interval in (("1h", 60),):
            try:
                out = analyse(label, pair, interval, tf_name)
                if out:
                    results.append(out)
            except Exception as e:
                print(f"  {label:9} {tf_name:>3}  error: {type(e).__name__}: {e}")
        print()

    total = sum(r["signals"] for r in results)
    print("=" * 78)
    print(f"  total signals across {len(PAIRS)} pairs in 30 days of 1h data: {total}")
    print()
    print("  Read this as a feasibility check, not a backtest: it models no stoploss,")
    print("  no ROI, no position sizing and no protections, and 30 days is far too")
    print("  short to establish an edge. What it does show is whether a move of the")
    print("  required size occurs at all after these signals - and if the mean net is")
    print("  negative at every horizon, the timeframe or the pairs need to change")
    print("  before any strategy tuning can help.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
