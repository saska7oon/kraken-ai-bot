# Completing the Turtle system made the strategy worse

**Tested:** 2026-09-18. **Result: reverted. The shipped configuration won all four cells.**

This file exists so the experiment is not run again. It is a negative result, and
negative results are the ones that get forgotten and repeated.

---

## What was tested, and why it was worth testing

`regime-strategies-report.md` §2.A lists the Turtle system's rules. The strategy
implemented two of them:

| # | Rule | Before this test |
|---|---|---|
| 1 | Entry: 20-period high | implemented |
| 2 | Exit: 10-period low | implemented |
| 3 | Skip if the previous breakout in that direction was a winner | missing |
| 4 | Stop: 2N below entry, N = 20-period ATR | **missing** — flat −12% |
| 5 | Sizing: 1 unit = 1% of account risked per N | **missing** — equal weight |

The report is blunt that this matters (line 163): *"Position sizing is integral to
the original system, not optional; the entry rule alone is not the system."*

Rules 4 and 5 were the obvious candidates. They are **pre-specified published
rules**, not parameters found by searching this dataset, which is the one kind of
change the trial-budget literature in
`strategy-count-and-overfitting-sources.md` endorses.

## The measurements that motivated it

ATR(20) over the window this bot actually backtests (2025-04-16 onward):

| Pair | N = ATR(20) | Turtle 2N stop | what −12% really is |
|---|---|---|---|
| BTC/CAD | 3.14% | 6.29% | 3.8 × N |
| ETH/CAD | 4.91% | 9.82% | 2.4 × N |
| SOL/CAD | 5.65% | 11.29% | 2.1 × N |
| XRP/CAD | 5.10% | 10.20% | 2.4 × N |

So the flat −12% was **3.8N on BTC and 2.1N on SOL** — one stop distance across
pairs whose volatility differs by 1.8×. And sizing at 1% risk per N implies BTC
31.8% / ETH 20.4% / XRP 19.6% / SOL 17.7% of the account, where the bot gave each
33.3%. That looked like a defect: the same money on the most volatile pair as on
the least.

It is a real inconsistency. It is not a defect that costs money — see below.

## The RULE 2 constraint, and how it was worked around

The direct implementation needs `custom_stoploss`, which **RULE 2** in
`ai_orchestrator/plugins/strategy_generator.py` forbids, and which
`proposal_validator.py` rejects as a hard error.

RULE 2's reasoning was checked against freqtrade's source and is correct.
`IStrategy.custom_stoploss` is documented as never going below `self.stoploss`,
but that docstring is **wrong for freqtrade 2026.8**:
`Trade.adjust_stop_loss` computes `current_price * (1 - abs(stoploss))` and
`__set_stop_loss` assigns it with **no comparison against the strategy's
stoploss anywhere**. A custom_stoploss can widen the stop past 12%. The
validator's own error text says exactly this: *"A custom stop loss can
legitimately return a loss far larger than the configured limit."*

So the stop was implemented as **`custom_exit`** instead — same price level, real
stoploss machinery untouched, 12% ceiling genuinely hard. The validator has no
rules restricting `custom_exit` or `custom_stake_amount`.

**Honest limitation of that workaround:** `custom_exit` is evaluated once per
candle, so on a 1-day timeframe the exit fills at a candle's price rather than at
the exact 2N level. A violent day can overshoot. `custom_stoploss` would fill
closer to the level and cost the ceiling to do it.

## Result — a full 2×2, all four cells measured

Real freqtrade 2026.8, 721 Kraken 1d candles, `--timerange 20240928-`,
`--enable-protections`, fee 0.0045.

| | 12% stop | 2N stop |
|---|---|---|
| **equal weight (33.3% each)** | **+13.67%** ← shipped | +9.55% |
| **ATR sizing (1% risk / N)** | +4.91% | +5.37% |

| variant | return | CAGR | trades | max DD | Sharpe |
|---|---|---|---|---|---|
| equal weight + 12% (shipped) | **+13.67%** | 9.41% | 14 | 8.83% | 0.14 |
| equal weight + 2N | +9.55% | 6.61% | 15 | — | 0.10 |
| ATR sizing + 12% | +4.91% | 3.42% | 14 | 11.19% | 0.06 |
| ATR sizing + 2N | +5.37% | 3.74% | 15 | 10.79% | 0.07 |

**Main effects:**

- **Sizing: −6.47pp.** Equal weight averages 11.61%; ATR sizing averages 5.14%.
  This is where the damage is.
- **Stop: −1.83pp.** 12% averages 9.29%; 2N averages 7.46%.
- **Strong interaction.** The 2N stop costs 4.12pp under equal weight but *adds*
  0.46pp under ATR sizing. Neither rule can be judged alone.

**Both halves of the Turtle risk model made it worse. The shipped configuration
won every cell.**

Exit reasons under equal weight + 2N: `exit_signal` 10 (+19.55%),
`turtle_2n_stop` 3 (−8.60%), `stop_loss` 1 (−4.25%), `force_exit` 1 (+2.84%).
The 2N stop fired on 3 of 15 trades at an average of −8.28% each — trades that
the 10-day-low exit would have handled.

## Why it does not work here

1. **Turtle's risk model assumes a diversified portfolio.** It was designed to
   survive across dozens of loosely-correlated futures markets. This bot has
   **four pairs at 0.775 average pairwise correlation** — roughly 1.3 effective
   bets. The diversification the sizing exists to exploit is not present.
2. **The sample is far too small for the stop to pay for itself.** 2N stops cost
   you the trades that dip through and recover. Across thousands of Turtle trades
   that is a worthwhile trade for capital preservation. Across 15 trades in 17
   months it is three winners converted into losers.
3. **The 10-day-low exit is already a volatility-adaptive trailing stop.** It
   trails price structure rather than a fixed multiple of ATR. Adding a 2N stop
   duplicates a job that is already being done, and cuts trades short doing it.
   This is the same conclusion reached earlier about the fixed-percentage
   trailing stop, which lost in 8 of 8 parameter sets.

The flat −12% being 3.8N on BTC is an inconsistency, but the backtest says it is
a **harmless** one: the Donchian exit almost always fires before either stop.

## Why reverting is not overfitting

Selecting the best of four cells *would* be selecting on in-sample performance.
That is not what happened here. The reverted configuration is the **incumbent** —
it was not chosen from these results, it was already shipped, and nothing
measured beat it. Declining to change is the correct action, and it is the
opposite of picking a winner.

The trap this avoids is real: had the sweep found ATR sizing marginally ahead, the
disciplined reading would still have been "the difference is inside the noise of
14 trades."

## Trial budget

This experiment cost **4 configurations** (2 sizing modes × 2 stop modes). The
published budget is **7 on a 2-year dataset**. Combined with the earlier trailing
stop sweep, the budget for this dataset is long since spent.

That is the strongest argument against repeating this: the result is negative, the
sample cannot distinguish small differences, and further variations would be
fitting noise.

## What the research actually delivered

The strategy list did not beat the incumbent. The report predicted this about
itself, at line 666:

> *"the most valuable outputs of this research are the fee correction, the 5m
> viability arithmetic, and the trial-budget constraint, not the strategy list."*

That is now confirmed by measurement rather than accepted on faith. The fee
correction alone was worth **+3.7pp**, which is larger than anything the strategy
list produced.
