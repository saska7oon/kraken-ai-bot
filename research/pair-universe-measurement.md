# Does a wider pair universe help? Measured on Kraken USDC pairs

Written 2026-09-18. Prompted by the operator's hypothesis that **47 USDC pairs
give better setups than 4 CAD pairs**. Both halves of that hypothesis were
tested against live Kraken data rather than argued.

**Method.** Kraken public `OHLC` (1d, 721 candles, the maximum Kraken returns)
and `AssetPairs`. The strategy's own entry rule was re-implemented exactly:
`close > highest high of prior 20 days` **and** `close > 200-day EMA`. Setups are
counted as *runs* (a fresh breakout, not every day spent above the line), which
is the same funnel used in the original trade-count analysis.

**Universe filter.** Kraken's Canada prohibition list (extracted from
`support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated`, updated
16 Sep 2026) and stablecoin-vs-stablecoin pairs were **removed**. This matters:
the raw USDC list includes 10 pairs Canadians cannot trade and 9
stablecoin/stablecoin pairs whose "breakouts" are noise. Raw counts overstate
the opportunity by ~55%.

---

## 1. The operator's first claim: more setups — CONFIRMED

| universe | pairs | setups |
|---|---|---|
| CAD | 4 | **37** |
| USDC, raw | 40 | 146 (3.9×) |
| **USDC, Canada-legal & non-stablecoin** | **30** | **94 (2.5×)** |

`[MEASURED]` So the usable gain is **2.5×**, not 3.9×. Still substantial.

## 2. The operator's second claim: higher volatility — CONFIRMED, and stronger than framed

**29 of 30 tradeable USDC pairs have a higher ATR(20) than BTC/CAD (3.14%).**

| pair | ATR(20) | avg \|open→close\| | setups |
|---|---|---|---|
| FARTCOIN/USDC | 8.52% | 5.05% | 0 |
| PEAQ/USDC | 8.48% | **5.64%** | 5 |
| TRUMP/USDC | 8.13% | 4.28% | 0 |
| DOT/USDC | 7.06% | 4.73% | 1 |
| ADA/USDC | 5.78% | 3.19% | 2 |
| **LINK/USDC** | 5.61% | 3.33% | **8** |
| **BCH/USDC** | 5.31% | 2.79% | **10** |
| SOL/USDC | 4.35% | 2.92% | 7 |
| ETH/USDC | 3.91% | 2.02% | 13 |
| XBT/USDC | 2.82% | 1.49% | 13 |
| *(BTC/CAD, reference)* | *3.14%* | *1.49%* | *14* |

`[MEASURED]`

**Why this is the strongest argument anyone has made about the fee problem.**
The round-trip fee is a **fixed 0.80%**. Its bite therefore depends entirely on
how far the asset moves:

| pair | avg daily move | fee as share of the move |
|---|---|---|
| BTC/CAD | 1.49% | **54%** |
| ETH/USDC | 2.02% | 40% |
| SOL/USDC | 2.92% | 27% |
| LINK/USDC | 3.33% | 24% |
| **PEAQ/USDC** | **5.64%** | **14%** |

`[REASONING]` This **partially escapes the fee ceiling** — not by trading less,
but by trading assets that move further per unit of fee. It is a different lever
from every one examined in `fee-ceiling-and-quote-currency.md`, all of which
were closed. This one is open.

## 3. But the mechanism is NOT "more choice per day"

The operator's framing was *"more setups means we can be more discerning and find
higher quality."* That requires several candidates on the **same day** to choose
between. Measured:

| | 4 CAD pairs | 30 USDC pairs |
|---|---|---|
| distinct days with ≥1 setup | 30 | **66** |
| days with **exactly 1** setup (no choice) | **83%** | **77%** |
| days with **>3** setups (ranking would matter) | **0%** | **6%** |
| mean setups per active day | 1.20 | 1.42 |

`[MEASURED]`

**Signals do not cluster into menus.** On 77% of active days there is exactly
one setup, so there is nothing to rank. Ranking would apply on **4 days out of
66 — 6% of opportunities.** "Be more discerning" is therefore **not** the
mechanism that delivers the gain.

**The real mechanism is more active days:** 30 → 66. The bot currently sits idle
most of the time; a wider universe roughly **doubles the number of days it has
something to do.**

## 4. Why that matters more than it sounds

Doubling active days roughly doubles the trade count over the same period —
from ~14 to ~31 across the backtest window.

**And sample size is the binding constraint** (`README.md` finding 4): 14 trades
cannot distinguish skill from luck, and a zero-edge sample produces +13.67%
21–31% of the time. A wider universe is the only lever found so far that
**increases N without spending trial budget on parameter tuning.** It does not
reach the ~200 trades needed, but it moves in the right direction on the one
axis that matters most.

## 5. Caveats, stated plainly

- **The highest-volatility pairs produce the fewest setups.** FARTCOIN, TRUMP,
  S, MELANIA, CC, BERA, APE and XDC all show **0**. They are in downtrends, so
  they never break a 20-day high above their 200 EMA. The pairs that both move
  and fire are **moderate**-volatility: BCH (5.31% ATR, 10 setups), LINK
  (5.61%, 8), SOL (4.35%, 7). The volatility gain and the setup gain only
  overlap in that middle band.
- **History is short.** Most USDC pairs have 642 candles against CAD's 721, and
  several have far fewer (CC 313, PEAQ 389). Less history, less reliable.
- **More trades means more fees.** Fee drag is `turnover × rate`; doubling N
  doubles it, from ~2.6%/yr to ~5.3%/yr. The volatility argument is what offsets
  this — but only if the extra trades are in higher-move assets, which §5 shows
  is only partly true.
- **This is untested as a strategy.** Everything above is a *signal count*, not
  a backtest. Whether the edge survives on these pairs is unknown, and testing
  it **spends trial budget**.
- **Tax changes shape but is not disqualifying.** A USDC quote adds a
  disposition per entry (the USDC spent), but the gain is ~nil since USDC's ACB
  ≈ its CAD value, and the helper automates the reporting. The real tax wrinkle
  is **FX exposure**: USDC is pegged to USD, not CAD, and USD/CAD moved
  1.3500 → 1.4694 (an **8.85% range**) over the measured window. Holding USDC is
  holding an FX position. See `cad-vs-usdc-execution-measurement.md`.
- **Execution is roughly neutral.** The fee is identical (0.40% maker — the
  0.20% stablecoin schedule applies only when the stablecoin is the *base*), and
  for a **post-only maker** the spread advantage largely evaporates. The
  counterintuitive effect: BTC/CAD's top bid held ~$113, so a $300 maker order
  becomes the dominant order at that level, while BTC/USDC's top bid held
  ~$10,500 and the same order queues behind it.

## 6. Bottom line

**The operator's instinct is correct, and the strongest version of it is not the
one they gave.**

- ✅ A wider universe gives **2.5× the setups** after filtering to pairs a
  Canadian can legally trade.
- ✅ **29 of 30** USDC pairs move more than BTC/CAD, so the fixed 0.80% fee is a
  far smaller share of the move (14% vs 54% on the best cases). **This is the
  first lever found that is not closed.**
- ✅ The gain arrives as **more active days (30 → 66)**, which roughly doubles
  the trade count and therefore **attacks the binding constraint: sample size.**
- ❌ It does **not** arrive as "more choice per day" — 77% of active days offer
  exactly one setup, and ranking would matter on 6% of opportunities.

**Recommended next step:** this is worth testing, but only *with* the Phase 0
benchmark harness in place, because the result is otherwise unfalsifiable — and
it must be recorded in the trial ledger, because it spends budget. The test is
not "does USDC make more money" but **"does a wider universe produce more
trades, and does the strategy still beat buy-and-hold on the identical window?"**
