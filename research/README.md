# Research archive

Background research behind this bot's design decisions. Written 2026-09-18 by AI
research subagents, from primary sources, and kept here because three of its
findings are load-bearing for the code and would otherwise exist only in a chat
log.

**These are research notes, not evidence of profitability.** Nothing here was
backtested by the authors of these reports. Read the label on every claim before
repeating it.

| File | Lines | What it is |
|---|---|---|
| `fee-ceiling-and-quote-currency.md` | 232 | **Read this first.** The fee-drag formula (`turnover × rate`; account size cancels), the corrected 53.5%/yr figure, proof that no fee-reduction avenue is open, and why USDT is not tradeable in Canada. |
| `canadian-crypto-tax-usdt-report.md` | 539 | CRA treatment of crypto-to-crypto, business-income vs capital-gains factors, and the finding that **Kraken Canada prohibits USDT entirely**. |
| `regime-strategies-report.md` | 666 | Strategies organised by market regime, with exact rules. **Scoped to a 5-minute timeframe this bot no longer uses.** |
| `strategy-count-and-overfitting-sources.md` | 782 | How many configurations a small account can afford to test, with peer-reviewed numbers. |
| `freqtrade-strategy-repos-report.md` | 574 | Inventory of public Freqtrade strategy repos, verified via the GitHub API. **An inventory, not an evaluation.** |
| `turtle-risk-model-result.md` | 156 | **A negative result.** Completing the published Turtle system (ATR stop + risk-based sizing) was measured across a full 2×2 and made the strategy worse in every cell. Read this before proposing another strategy change. |
| `small-account-base-rates.md` | 384 | Base rates: what crypto buy-and-hold and passive benchmarks actually return. |
| `small-account-strategy-classes.md` | 945 | Strategy families evaluated for a small account. |
| `small-account-minimums-and-fees.md` | 627 | Minimum viable account sizes and the fee floor. |
| `small-account-algo-trading.md` | 788 | Peer-reviewed evidence on systematic crypto strategy performance, net of costs. |
| `small-account-cases-and-backtest-reliability.md` | 643 | Documented retail outcomes, and why a backtest cannot tell you whether a strategy works (in-sample Sharpe explains **R² ≈ 0.02** of out-of-sample). |
| `gh/` | — | The primary-source evidence the reports cite: upstream READMEs, licences, the NFI trading-modes doc, and file listings. |

Every claim in the reports carries an evidence label — `[VERIFIED-URL]`,
`[VERIFIED-SOURCE]`, `[API]`, `[RAW]`, `[PEER-REVIEWED]`, `[BLOG]`, `[CLAIM]`,
`[REASONING]` — and each report has a section listing what it could *not*
verify. Those sections are the most useful part. Do not cite anything from a
report that its own limitations section disowns.

---

## The three findings that changed this codebase

**1. The fee was wrong, and the reports said so first.**
`regime-strategies-report.md` §1.1 traced the whole chain: Kraken's API returns
empty fee arrays, so ccxt falls back to its hardcoded `taker: 0.0026` /
`maker: 0.0016`, while Kraken Pro Tier 1 actually charges **0.80% taker / 0.40%
maker**. The report's own remedy was *"set `"fee": 0.008` (taker) or `0.004`
(maker)"* — and the maker figure is the correct one here, because this bot uses
post-only orders. See `config/base.json` and `ai_orchestrator/tests/test_fees.py`.

**2. The trial budget is small, and it is already spent.**
Bailey, Borwein, López de Prado & Zhu (*Notices of the AMS*, May 2014): after
**7 independent configurations on a 2-year backtest**, the expected maximum
in-sample Sharpe is 1 while the expected out-of-sample Sharpe is **0**. Five
years buys you 45. Freqtrade's own FAQ recommends 10,000 hyperopt epochs, which
is a **~1,400× overrun** of that budget.

**This is a hard constraint, not advice.** Every parameter sweep, every
alternative strategy, and every regime variation spends from the same budget.
As of this writing the budget has been overrun twice over — a sweep of 8
parameter sets × 3 trailing-stop modes to settle the trailing stop, and 4 more
configurations to test the Turtle risk model. The sweep found 15/8 beating the
shipped 20/10, which is the *expected* result of a sweep and is why 20/10 (the
published Turtle parameter) is still the shipped value. **Do not switch to a
sweep winner.**

The Turtle experiment is written up in `turtle-risk-model-result.md`. It is a
negative result: the shipped configuration won all four cells, so the strategy
was reverted and the published system was *not* adopted. That file exists so the
same ground is not covered twice.

Before running another sweep, read §5 of `strategy-count-and-overfitting-sources.md`
and use a held-out `--timerange` that has never been optimised on.

**3. The venue's fee schedule, not the signal, is the binding constraint.**
At Kraken Tier 1 a round trip costs ~0.80%. On 5-minute candles the average
BTC/CAD candle's entire range is 0.118% — the fee is 13.6 candles of total
range, so no 5m strategy survives. On daily candles the arithmetic is just as
blunt: one trade per day would cost roughly **53.5% of the wallet per year** in
fees and would need 64–75% directional accuracy just to break even.

> **Correction (2026-09-18):** this figure was previously stated as **97%/yr**,
> which held the fee tier fixed at Tier 1. Daily trading on a $1,500 account
> reaches **Tier 3** (0.22% maker), which almost halves the cost. The corrected
> figure is **~53.5%/yr**. The conclusion is unchanged; the number was wrong.
> See `fee-ceiling-and-quote-currency.md` §1.

The consequence: **looking for a better signal will not produce more trades.**
No strategy choice fixes a 0.80% taker fee. The levers that actually matter are
the fee tier, the number of trades taken, and order type (post-only maker).

**And the fee tier is a closed door.** Since July 2026 tiers are the best of
volume *or* assets held, but Tiers 1–2 have **no assets route at all** and the
first threshold is $20,000 USD — 14–28× this account. Kraken+ (zero fees to
$10k/mo) **explicitly excludes API trading**. Every frequency increase buys a
smaller rate cut than the volume it demands. Full analysis in
`fee-ceiling-and-quote-currency.md`.

**The fee drag formula, which reframes the whole question:**
`annual fee % = round trips/yr × (2/k) × maker_rate`. **Account size cancels
out.** A $1,000 account and a $1,000,000 account trading monthly both pay
3.20%/yr — so "is there a strategy for a small account?" has no distinct
answer. The constraint is turnover, not capital.

---

## Also worth knowing

- **Regime detection is a filter, not an architecture.** The word "regime"
  appears **0 times** in the Freqtrade documentation; the maintainers have
  refused to build strategy switching, citing remote-code-execution risk; every
  community regime-switching repo found has 0–4 stars. The endorsed pattern is a
  regime *filter inside one strategy*.
- **The four CAD pairs are not four bets.** Measured average pairwise daily
  correlation is **0.775**, and Giller (arXiv:2412.04263) puts a 14-coin retail
  portfolio at ~2 effective independent bets. Adding pairs does not add
  diversification.
- **Look-ahead bias is the LLM-specific risk, and it is not covered by
  overfitting statistics.** A deliberately leaky strategy with a Sharpe of 35
  passes both the Deflated Sharpe Ratio and PBO. That is why
  `freqtrade lookahead-analysis` is run against this strategy; the current
  result is `has_bias: No`, 15 signals, 0 biased.
- **`recursive-analysis` has not been run** (startup-candle sufficiency). It is
  the remaining official check recommended by the reports.
- **A trap: "does Kraken list the market?" is the wrong question.** Kraken's
  public `AssetPairs` endpoint lists `USDT/CAD`, but **Canadian clients cannot
  deposit, hold or trade USDT at all** — it was suspended 30 Nov 2023 and
  residual balances were force-converted to USD. The question that matters is
  *"can a Canadian client trade it?"*. DAI, PYUSD, RLUSD, WBTC, WETH, XAUT,
  PAXG and XMR are prohibited too; **USDC and USD are not**.
- **Single-snapshot spreads are not evidence.** Measured 20 seconds apart,
  BTC/CAD's top-of-book spread moved **3.7×** and SOL/CAD's **3×**. Thin books
  do not hold a top level. USD spreads did not move at all, which is the depth
  signal. Any spread comparison in this archive that rests on one sample should
  be discarded — trade counts are the robust measure.

## What is deliberately not committed here

- `gh/*_tree.json` — 3.4 MB of GitHub API tree dumps. Re-fetchable, no lasting
  value.
- `gh/official_strats/` — 68 strategy files copied from
  `freqtrade/freqtrade-strategies`. Excluded because this repo has **no LICENSE
  file**, and vendoring GPL-3.0 code into it raises a licensing question that
  should be answered deliberately rather than by accident. (Those files also
  carry two third-party authors' email addresses in their headers, published
  upstream as attribution — another reason not to copy them around.)

The full raw evidence set remains outside version control at
`../research/` if it is ever needed.
