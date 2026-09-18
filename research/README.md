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
| `small-account-plan.md` | 260 | A core–satellite plan for this account size, **with a critique appended**: three of its claims are marked as not accepted, and its own Phase 5 item may dominate the whole plan. |
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

**3. The venue's fee schedule sets a ceiling on trade frequency.**
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

> **Second correction (2026-09-18):** this section previously read *"the venue's
> fee schedule, **not the signal**, is the binding constraint."* That is
> misleading and is superseded by finding 4 below. The fee schedule constrains
> how *often* you may trade; it does **not** constrain whether you can *know*
> your strategy works. At this trade count the fee drag is survivable
> (**~2.7%/yr**, about 29% of the reported CAGR) and the binding constraint is
> **sample size**.

The consequence for signal-hunting: **no strategy choice fixes a 0.80% taker
fee**, and the levers that matter are the fee tier, the number of trades taken,
and order type (post-only maker).

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

**4. The backtest cannot tell you whether this strategy works.**

This is the most important finding in the archive, and it is uncomfortable.

Freqtrade's own backtesting documentation presents a **77-trade, Sharpe 3.89**
example on a $1,000 account and labels it **p = 0.4768 — *"not distinguishable
from luck"***. This bot's backtest is **14 trades at Sharpe 0.14**: *weaker than
the example Freqtrade uses to warn people*. [VERIFIED-URL:
<https://www.freqtrade.io/en/stable/backtesting/>]

Since Freqtrade confirms its t-statistic **is** SQN, `t = √N · mean / SD` — a
realistic trend strategy needs **~200–1,000 trades** before the result means
anything. A Monte Carlo of a **zero-edge** 14-trade sample produces **≥ +13.67%
about 21–31% of the time**. Our headline number sits inside that band.

**So `+13.67%` is not evidence of an edge.** It is consistent with no edge at
all. Read the backtest as *"the plumbing works and nothing exploded"*, not as
*"this makes money."*

Buy-and-hold comparison cuts **both** ways and settles nothing:
- 17-month window: equal-weight B&H **+53.06%** vs bot **+13.67%** — B&H wins.
- From 2024-11-27, when all four pairs existed: B&H **−26.06%** vs bot
  **+13.67%** — bot wins.

Neither establishes skill. **The bot's −8.83% drawdown against B&H's −63.51%
reflects low exposure — it is in cash most of the time — not risk management.**

**The benchmark is not zero. It is buy-and-hold.** This is the sharpest version
of the problem, from an out-of-sample audit of **895 public Freqtrade strategies
across 53 repos** (recomputed from the raw `LEDGER.csv`):

| stage | count |
|---|---|
| strategies audited | **895** |
| dropped at the first gate | **878** |
| survived every gate | **2** |
| …of those, beat buy-and-hold | **0** |

The decisive row is `CombinedBinHClucAndMADV5`: **1,295 out-of-sample trades,
+0.46%/trade, p = 8.4 × 10⁻¹⁵, positive 95% CI lower bound** — an edge *no
statistician would dispute*, which survived lookahead detection, recursion
detection, significance testing and economic screening. **It returned +106.91%
against buy-and-hold's +346.34% — it lost to doing nothing by 239 percentage
points.**

**28 strategies did beat buy-and-hold — and every one failed a robustness gate**
(9 in-sample not significant, 6 lookahead bias, 5 too few trades, 3
out-of-sample not significant, 3 recursive, 2 not positive in-sample). The
lookahead failures show the trap: `NOTankAi_15_Cleaned_v2` at **+63,645,298%**,
`ichiV1` at **+18,701,080%**. A strategy returning 63 million percent is not a
great strategy — it is a broken one. **455 of 895 (51%) are flagged recursive.**

So the operational question is not *"does this bot have an edge?"* but
***"does it beat doing nothing?"*** — and for this bot "doing nothing" means
holding the same four pairs. **Always report buy-and-hold on the identical
window, across multiple start dates.** Without it, `+13.67%` is uninterpretable.

**Treat the audit as suggestive, not conclusive** — it is one unreplicated
amateur pipeline (3 stars, 0 forks, single author, ~65% of the corpus is
copies), its README prose contradicts its own ledger, and the author's own
year-split shows the verdict **flips with market direction** (0 of 5 beat B&H in
up years, 5 of 5 in down years). What makes it count is that it is the **fifth
independent dataset reaching the same conclusion**: Hudson & Urquhart's 15,000
rules, Borgards' six-year crypto study, the 888 Quantopian algorithms
(IS→OOS Sharpe R² = 0.02), a local Monte Carlo, and now this.

Two independent peer-reviewed lines agree on where the honest case lies:
Hudson & Urquhart (~15,000 technical rules) found many beat buy-and-hold on
risk-adjusted return and drawdown, but only **4.96–15.69% beat it on raw
return**, with **no out-of-sample predictability** in Bitcoin; Borgards (2021)
measured low-frequency crypto trend following at **+127% vs B&H +186%**, with
drawdown **−16.5% vs −90.2%**. **The defensible claim is drawdown management,
not return.**

Retail base rates, five independent regulators, all in the same band:
ESMA **74–89%**, FCA **82%**, ASIC **63–80%**, BIS **73–81%**, Brazil **97%** of
those persisting 300+ days — with *"no evidence of learning"*. And the public
record for $1,000–$2,000 accounts contains **no independently verified track
record at all**. Full evidence in `small-account-algo-trading.md` and
`small-account-cases-and-backtest-reliability.md`.

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
- **Fund by e-Transfer, never by debit card.** A debit-card deposit costs
  **0.25% + 3.75% ≈ $56.50 on $1,500** — about four round trips' worth of fees,
  spent before the bot trades once. e-Transfer deposit is free; e-Transfer
  withdrawal is a flat **$10 CAD (0.67%)**.
- **Kraken minimum stakes may silently skip trades.** The nominal minimum is
  $3–10 CAD, but Freqtrade's maintainer reports Kraken minimums *"as high as
  60$"* on some pairs, and stakes below the minimum cause trades to be **skipped
  without an error**. At 1/3 of a $1,000 wallet (~$333) this is not binding, but
  it is worth checking on any smaller allocation.
- **The 1-day `CooldownPeriod` interacts with the superficial-loss rule.**
  Re-entering a pair within 30 days of a stopped-out exit can **deny the capital
  loss** under CRA's superficial-loss rule. Unquantified — flag it to an
  accountant.
- **Expected income at this size is small and should be stated plainly:**
  $1,500 at the reported 9.4% CAGR is **~$141/yr ≈ $12/month**, before tax and
  before the $10 withdrawal fee.
- **A claim in this archive's own evidence set is false.**
  `gh/` contains `Bananajoexxc/RegimeFilterStrategy`, which advertises a Calmar
  ratio of **73.00**. Its own figures (+1,450% over 3.5 years → CAGR 118.8%)
  imply Calmar **4.06**, and 73 contradicts its own stated Sharpe of 0.37 —
  **18× overstated**. It is retained as evidence of what these repos claim, not
  as a strategy.
- **Two recovered live cases worth reading before scaling anything.**
  A bot with **2,729 live trades over 60 days** finished at profit factor
  **1.15** against a ≥1.3 target, win rate **33.6%** against ≥45%, and a maximum
  losing streak of **18** against ≤5. The operator's verdict: *"The system
  didn't lose money. It just never earned the right to scale."* He also found
  that *"at points, 100% of live positions sat in one coin (ADA), and I never
  decided that"* — the concentration risk this archive documents elsewhere,
  appearing live. Separately, a **$1,000 paper account with 480 trades** and
  *"up about $25"* asked whether it was ready to go live. By the SQN identity it
  needs mean/SD > 0.089 and has roughly **0.003 — about 20× short.**
- **Comment threads and Freqtrade's Discord remain unretrieved** — the largest
  unreachable evidence source left. One recovered case now carries
  `removal_type: "deleted"`, so the public record is shrinking, not stable.

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
