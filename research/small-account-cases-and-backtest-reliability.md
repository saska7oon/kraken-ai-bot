# Small crypto accounts ($1,000–$2,000) and algorithmic trading: documented real-world cases and the reliability of backtested claims

**Research date:** 2026-09-18
**Scope:** (1) documented small-account algo-trading outcomes with real numbers; (2) the overfitting / "too few trades" statistical problem; (3) the base rate at which backtested strategies survive live trading.

**Verification method.** Every URL below was fetched in this session. Where a claim is quoted, I downloaded the actual PDF or raw markdown and read it, or queried the GitHub API. I report HTTP status where relevant. Items I could not verify are in **§5 COULD NOT VERIFY** and are **not** cited as evidence anywhere else. Where I perform arithmetic on top of a sourced formula, it is labelled **[REASONING]** and the arithmetic is shown so it can be checked.

## Source-type legend

| Label | Meaning |
|---|---|
| **[PEER-REVIEWED]** | Refereed journal article |
| **[PREPRINT]** | SSRN / working paper — **not** peer reviewed |
| **[AMS NOTICES]** | *Notices of the AMS* — expository society magazine, not a standard refereed research journal |
| **[VERIFIED-URL]** | I fetched the artifact and confirmed the text/figures quoted exist at that URL |
| **[PRACTITIONER]** | Named individual documenting their own work, with enough detail to be checkable |
| **[BLOG]** | Self-published content, low evidentiary weight |
| **[CLAIM]** | An assertion of performance that I could **not** independently verify |
| **[REASONING]** | My own derivation/arithmetic, not a sourced claim |

**Cross-reference:** `research/strategy-count-and-overfitting-sources.md` (already in this workspace) covers the DSR/PBO/MinBTL literature in more depth. This document does not repeat that material wholesale; it re-verifies the primary PDFs independently and adds the **trade-count / statistical-significance** dimension, the **real-world case record**, and the **base-rate** question.

---

## 0. Bottom line up front

1. **Independently verified small-account crypto algo track records are essentially absent from public sources.** I found **zero** audited or API-verified records of a $1,000–$2,000 retail bot account. Every number I did find is **self-reported**, and in the two best-documented cases the underlying artifacts needed to reproduce the numbers **are not published at all**. This is the single most important finding in this report.
2. **The "few trades" problem is real, quantified, and severe — and it is worse than the usual rule of thumb suggests.** Freqtrade's own documentation states that its backtest p-value is *identical* to its SQN statistic and that this is a **t-statistic** — which means the standard significance machinery applies directly to trade counts. At 30 trades you need a per-trade mean/standard-deviation ratio of **0.36** to reach p<0.05, and **0.55** to clear the multiple-testing hurdle that Harvey–Liu–Zhu argue is now required. Those are enormous per-trade edges.
3. **The published overfitting literature contains a genuinely damning worked example.** Bailey et al. generate a *pure random walk*, fit a seasonal strategy with 8,800 parameter combinations, and obtain an in-sample Sharpe of **1.27** with a PSR statistic of **2.83** (i.e. under 1% probability the true Sharpe is below zero by the conventional test) — and then show the **probability of backtest overfitting is 55%**, with **~53% of out-of-sample Sharpes negative**. A conventionally "highly significant" backtest on data with no signal whatsoever.
4. **The best-documented real-world failure I found is a backtest case study, not a live one** — and it explicitly does the capital math for a **$2,000** account, concluding the ceiling for a "top-decile" 30% APY is about **$50/month**. Its seven strategies all lost over a 24-month window (−1.16% to −95.48%). It is self-reported, AI-assisted, and **its claimed "backtest receipts" do not exist in the repository**.
5. **Documented failures are better documented than documented successes — but the successful-looking ones are marketing.** The clearest asymmetry I found: strategy repositories that *show* losing results disclose them honestly; the most popular strategy repositories (NostalgiaForInfinity, MoniGoMani) carry **9+ affiliate/referral links and publish no performance disclosure at all**. The incentive gradient runs against disclosure.
6. **The strongest base-rate evidence says the backtest cannot tell you at all.** In the largest study of real deployed strategies — **888** crowd-sourced algorithms with true out-of-sample data — in-sample Sharpe ratio explained **R² ≈ 0.02** of out-of-sample Sharpe ratio, and in-sample annual returns correlated **weakly negatively** with out-of-sample returns. Risk metrics (volatility R² = 0.67) survived; return metrics did not.
7. **The two most-cited failure rates are fabricated-looking folklore, and I verified this by reading the pages that assert them.** "**87% of backtested strategies fail**" cites only Harvey–Liu–Zhu and Bailey et al. — **neither of which contains that number**. "**90% of trading bots fail**" is never sourced at all, and sits beside four other uncited statistics on a page that *also* correctly cites the 888-strategy study without linking it.
8. **The base rate is conditional, not constant** — ~53–78% of out-of-sample Sharpe ratios negative for a heavily-mined strategy versus **3%** for a validated one. Quoting a single failure rate destroys the actual finding.
9. **In the adjacent retail literature, persistence makes things worse, not better.** Among Brazilians who day-traded >300 days, **97% lost money** and only 0.4% out-earned a bank teller; the share who were profitable falls *monotonically* with days traded (29.8% at 1 day → **3.0%** at >300). "No evidence of learning."

---

## 1. Documented small-account outcomes with real numbers

### 1.1 The headline finding: no independently verified small-account track record exists in public sources

**Finding [REASONING, from the searches recorded in §5].** I searched for, and failed to find, any of the following:

- A crypto bot account whose P&L is **API-verified** by a third party (the crypto equivalent of a myfxbook-verified record).
- A published, reproducible **trade log** for a $1,000–$2,000 live account.
- An **audited** statement of a retail bot's returns.

Everything located is **self-reported**. I want to state this plainly rather than dress up self-reports as evidence: **in practice, every small-account P&L figure in the public record is self-reported, and most are unverifiable even in principle** because the raw data is never published. Section 1.4 gives a concrete, verified example of exactly that failure.

Two structural reasons the record is so thin, both verified:

**(a) The main community venue is not publicly archivable.** Freqtrade directs users to Discord (see the official channels list in `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/faq.md`). Discord content is not indexed by search engines and is not persistently citable, so the place where retail users actually post "here is my live result" is **structurally unverifiable**. I also confirmed that `https://github.com/freqtrade/freqtrade/discussions` returns **HTTP 404** — the project does not use GitHub Discussions as a public performance-log venue.

**(b) The issue tracker is a bug tracker, not a results log.** I searched the Freqtrade repository's issues via the GitHub API (`https://api.github.com/search/issues`). A query for live/results returned 237 issues and a query for profit/loss/stoploss returned 508 — and **every result I inspected was a software defect report** (websocket warnings, order-recovery bugs, OOM crashes, hyperopt behaviour). There is **no community practice of posting P&L in issues**. This is not a null result about profitability; it is a null result about *where the evidence would be*.

**(c) An important limitation on this section, stated up front.** A dedicated sub-investigation into Freqtrade community case studies (r/freqtrade_io, r/algotrading, Freqtrade Discord, strategy-repo live-trading disclosures) was **run and then stopped without completing**, because every avenue it needed was blocked from this environment (see §5 rows 2–4). **Consequently, community self-reports were not examined at all in this report.** The cases in §1.2–§1.7 are the ones I verified directly, by fetching raw GitHub content and enumerating repositories via the GitHub API. **§1 should be read as "what is verifiable from indexed, fetchable sources," not as "the complete public record."** This distinction is itself part of the finding: the venues where small-account results are actually posted are precisely the ones that cannot be independently checked.

### 1.2 The best-documented failure with a small-account frame: a $2,000 post-mortem (BACKTEST, not live)

**Source:** `https://github.com/francisx1999/crypto-trading-bot-postmortem` — README fetched from `https://raw.githubusercontent.com/francisx1999/crypto-trading-bot-postmortem/master/README.md` **[VERIFIED-URL]**. Repo metadata via GitHub API: **3 stars, 0 forks, created 2026-05-29, size 33 KB**.

The author (Francis Oyakhire) reports building and backtesting seven strategies over a 24-month window on Freqtrade. **[PRACTITIONER — self-reported backtests]**

| # | Strategy | 24-month result | Stated failure mode |
|---|---|---|---|
| 1 | v4 strict trend | **−1.16%** | Refuses to trade; negative per-trade EV |
| 2 | v5 baseline | **−33.08%** | Exit-on-opposite-cross bleeds |
| 3 | v5 hyperopt best | **−55.74%** | Tuning can't escape exit logic |
| 4 | Grid bot (DCA) | **−95.48%** | Trends crush mean reversion |
| 5 | F&G with stoploss | **−24.39%** | Stop kills winners-in-progress |
| 6 | F&G no stoploss | **−17.75%** (best) | Alt basket can't capture BTC sentiment |
| 7 | Macro regime EMA | **−57.09%** | Same exit logic as v5 |

The grid-bot row is worth quoting because it is the cleanest illustration of why win rate is a vanity metric:

> "A 93.3% win rate, and you still lost 95% of capital. ... 567 small wins (each ROI = +1.5%) totaled +$1,817. But 39 catastrophic stop-losses (-30% each, on a stacked DCA position) bled -$3,700." — with "**Final balance | $2,000 → $90**"

**The capital math, which is the part most directly relevant to this report [PRACTITIONER, with an unsourced assumption]:**

> "A **top-decile retail trader** (rare and usually survivorship-biased) might hit **30% annualized** sustained over years. Let's use that as a generous upper bound."
> "$2,000 × 30% APY = $50/mo. That's the *ceiling*, not the expected value."
> "**You need around $50,000 of risk capital for a working bot to produce tax-free-income-level returns.**"

⚠️ **How to read this.** The 30% APY figure is the author's own assumption, explicitly framed as a "generous upper bound," and it is **not sourced**. Treat the *direction* of the conclusion (small capital caps absolute returns) as arithmetic — which is unarguable — and the 30% input as **[CLAIM]**, not evidence. The author is commendably explicit about this, which is more than can be said for the sources in §1.5.

**Three verified weaknesses that cap how much weight this case can carry:**

1. **These are backtests, not live results.** The only live exposure reported was a 44-day dry-run of strategy v4 that fired **zero trades**. So this documents *backtested* failure, which is a weaker claim than *live* failure.
2. **The claimed "receipts" are not in the repository.** The README says: *"All seven strategies, all backtests, all source code is on the project repo: this repository"* and *"Backtest results are summarized in the tables above; **raw logs available on request**."* I enumerated the full repository tree via the GitHub API (`/git/trees/master?recursive=1`): it contains **5 strategy `.py` files, 1 hyperopt-loss file, 3 scripts, `config.example.json`, `LICENSE`, and `README.md` — and zero backtest result artifacts** (no JSON, no CSV, no exported trade logs). **The numbers cannot be reproduced from the published artifacts.** This is a textbook instance of the general problem.
3. **The analysis is AI-assisted and the timeline is internally loose.** The README's own footer states: *"AI-assisted (Claude) for code review, hyperopt loss design, and the postmortem analysis itself."* Separately, the narrative mixes an Apr–May 2026 dry-run with "Q2–Q3 2024" market events inside a claimed 24-month window, which does not obviously reconcile.

Also note the count: seven strategies are tabulated but only **five** distinct strategy files exist (v5 baseline and v5 hyperopt-best are two rows of the same file).

### 1.3 A documented failure with a full breakdown — but dry-run, not real money

**Source:** `https://github.com/OfficialGIGA/freqtrade-ml-strategy` — `RESULTS.md` and `README.md` fetched raw **[VERIFIED-URL]**. **1 star.**

This is the most *methodologically* transparent failure I found, and it is honest to the point of self-harm:

> "Real dry-run result: **-$93.98 across 139 trades** (Apr–May 2026, Kraken paper trading). This is shown deliberately. The strategy is not yet profitable..."

From `RESULTS.md` **[PRACTITIONER — self-reported, dry-run]**:

| Metric | Value |
|---|---|
| Period | April 19 – May 21, 2026 |
| Exchange | Kraken (**dry-run, no real capital**) |
| Pairs / timeframe | 17 USDT pairs, 4h |
| Total closed trades | **139** |
| Win rate | **32.4%** |
| Total dryrun PnL | **−$94.00** |

It breaks the loss down by entry regime and by exit reason, finding that its "risk_on" gate — the *most permissive* condition — was the worst performer (116 trades, 23.3% win rate, −$98.84), while 105 of 139 trades exited via stoploss at an 11% win rate. And it draws the correct statistical conclusion about its own promising sub-result:

> "The neutral regime signal shows promise (75% in 8 trades) but **n=8 is too small to conclude anything**."

And it states the disclaimer most vendors omit:

> "This is NOT financial advice and the strategy is **NOT proven to be profitable in live trading**. Results in dry-run do not guarantee live performance."

**Caveats:** dry-run (no real capital), self-reported, 1-star repository, **and no starting balance is stated** — so the −$94 cannot even be converted into a percentage return. It is a documented failure of a *method*, not a documented small-account loss.

### 1.4 The asymmetry: failures get disclosed, successes get marketed

This is the clearest structural pattern I verified, and it runs the opposite way to what a naive reader would expect.

**Repositories that disclose negative results (verified by fetching the README):**

- `OfficialGIGA/freqtrade-ml-strategy` (§1.3) — publishes a loss, a regime breakdown, and a "n=8 is too small" caveat. Also documents **four rejected strategies** with numbers in `backtest_notebooks/`: grid trading "Rejected. Mean −2.06% across 60d windows on BTC"; mean reversion 1h "Rejected. All 10 pairs negative 4h forward return"; mean reversion 72h "Rejected. +0.79% raw but −0.90% net with TP/SL"; relative strength momentum "Rejected. Gross −5.67%, max DD 51.95%". **[PRACTITIONER]**
- `TheoBrigitte/freqtrade` — README states: *"This repository is a collection of strategies, configurations, dry-run and backtest results I collected overtime"* and *"`backtest_results/` - Contains my backtest results, good or bad, they are all here."* **[PRACTITIONER]**

**Repositories with large audiences that publish no performance disclosure but do publish affiliate links:**

- `NostalgiaForInfinity` (the most-forked strategy lineage in this workspace's survey) — its README contains a **"Referral Links"** section with **9 monetised exchange links** (Binance, Kucoin, Gate, OKX, MEXC, Bitget, Kraken, BitMart, HTX), each with a stated fee discount/rebate. I grepped the README for performance terms and found **no live-trading result disclosure at all**. **[VERIFIED-URL]** — `https://raw.githubusercontent.com/iterativv/NostalgiaForInfinity/develop/README.md`
- `MoniGoMani` (Rikj000) — README carries **iConomi and Binance referral links** plus a "buy me a coffee" link; **no performance numbers**. **[VERIFIED-URL]**

**Why this matters.** The repository with the strongest incentive to overstate results publishes none; the repositories that publish losses have 1–3 stars. **The publication of a positive track record is negatively correlated with the incentive to publish one, and positively correlated with having no audience.** That is a selection effect that should make any reader more sceptical of the "success stories" they do encounter, not less.

### 1.5 Marketing presented as case studies — a verified example

**Source:** `https://dev.to/henry_lin_3ac6363747f45b4/lesson-23-freqtrade-small-capital-live-trading-3ioc` **[VERIFIED-URL]** — fetched and read in full. **[BLOG] / marketing — NOT evidence.**

This article is squarely on-topic for "$1,000–$2,000 algo trading" and is exactly the kind of source that would be cited as a "real-world case" by a less careful researcher. It contains:

- A **"Real cases:"** block: *"User A: Initial $10,000, lost 15% (-$1,500) in first week, mentally collapsed, stopped trading / User B: Initial $1,000, lost 15% (-$150) in first week, calmly analyzed, adjusted strategy, profitable after 3 months"* — **anonymous, unsourced, no dates, no exchange, no trade log. This is not a case study; it is an illustration.**
- A **"First Week Live Trading Summary Report"** with precise figures: 28 trades, 57.1% win rate, +$45.60 (+4.56%), a daily P&L table, and a backtest/dry-run/live comparison (25.5% / 18.2% / 4.56%). The header dates it "2023-04-20 to 2023-04-26", but **the article was posted 2025-11-15** — so the table cannot be a record of the author's own trading during the article's writing.
- A funnel to a 2-hour YouTube course (`youtube.com/playlist?list=...`) on the author's channel.

**Verdict: the numbers are illustrative templates, not measurements.** They are formatted to look like audit output (tables, `USDT` units, timestamps), which is precisely what makes this genre dangerous. I record it here as a *negative* finding: **the most search-visible "small capital live trading" case study I could find is fabricated-looking template data attached to a course funnel.**

One genuinely useful thing the article does contain, as **[PRACTITIONER]** guidance rather than evidence: it lists "live performance much worse than dry-run" with explicit diagnostic thresholds — if first-week live return is <30% of dry-run, treat it as a warning; a difference >70% or a loss means "pause trading, deep analysis." It offers no source for these thresholds.

### 1.6 Strategy-repo READMEs with backtest claims — and a verified internal inconsistency

**Source:** `https://github.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade` — README fetched raw **[VERIFIED-URL]**. **3 stars.** **[CLAIM]**

The README publishes a backtest table for a single-pair (SOL/USDT futures) regime strategy:

| Metric | Value |
|---|---|
| Period | Jul 2022 – Jan 2026 (3.5 years) |
| **Total Return** | **+1,450%** |
| Sharpe Ratio | 0.37 |
| Sortino Ratio | 0.87 |
| **Calmar Ratio** | **73.00** |
| Max Drawdown | 29.24% |
| Profit Factor | 1.40 |
| **Total Trades** | **204** |
| Win Rate | 40.2% |

**[REASONING] — this table is internally inconsistent, and I can show the arithmetic.** Calmar ratio is annualised return ÷ maximum drawdown. +1,450% total over 3.5 years implies a CAGR of 15.5^(1/3.5) − 1 ≈ **118.8%**. With a 29.24% max drawdown, Calmar should be ≈ 118.8 / 29.24 ≈ **4.1**. The README claims **73.00** — roughly **18× too high**. A Calmar of 73 alongside a Sharpe of 0.37 and a Sortino of 0.87 is not credible: Calmar cannot sensibly exceed Sortino by two orders of magnitude on the same return series.

Two further verified red flags: the README's Quick Start still contains the literal placeholder **`git clone https://github.com/YOUR_USERNAME/RegimeFilterStrategy-Freqtrade.git`** (a copied template), and it states settings of **"95% stake"** on a single pair — meaning essentially the whole account is exposed to one instrument.

**This is the single best concrete illustration of §3's point**: a published backtest with 204 trades, an apparently respectable profit factor, and an impossible risk statistic, on a 3-star repository, with no live result and no way to reproduce the backtest.

### 1.7 Backtest tables that ARE checkable, from a documented strategy collection

**Source:** `https://github.com/paulcpk/freqtrade-strategies-that-work` (README; the copy in this workspace at `research/gh/paulcpk_README.md` matches) **[PRACTITIONER]**. Stale (~5 years), with an explicit warning: *"These strategies are highly experimental and for educational purposes only. Use at your own risk."*

| Strategy | Buy count | Avg profit % | Total profit % |
|---|---|---|---|
| EMAPriceCrossoverWithThreshold.py | 272 | 1.31 | 118.53 |
| DoubleEMACrossoverWithTrend.py | 655 | 0.56 | 122.50 |
| MACDCrossoverWithTrend.py | 300 | 0.49 | 49.42 |
| RSIDirectionalWithTrendSlow.py | 108 | 0.91 | 32.75 |
| RSIDirectionalWithTrend.py | 181 | 0.27 | 16.16 |

Backtest period 2018-03-01 → 2020-03-01, 1h, 8 pairs. **[CLAIM]** — but note these at least publish the **trade count** alongside the return, which is the minimum disclosure needed for the analysis in §2. I checked the internal consistency: with `max_open_trades ≈ 3`, 272 trades × 1.31% × (1/3) ≈ 119% is consistent with the stated 118.53% total, so these numbers are at least arithmetically coherent.

**Note the period: 2018-03 → 2020-03 includes the 2019 rally.** A strategy collection whose entire published evidence is one 24-month window that happens to contain a large bull move, and which is now ~5 years stale against a framework that has since changed its config schema and interface version, is not evidence about 2026 crypto.

### 1.8 Failures are under-reported — the asymmetry, stated explicitly

**[REASONING, grounded in the verified observations above.]** The asymmetry is not merely suspected; it is visible in the structures I verified:

1. **Reputation and revenue are asymmetric.** A published loss costs the author audience; a published win (or an unpublished win implied by a paid product) gains it. NostalgiaForInfinity's 9 affiliate links (§1.4) monetise *trading volume by followers*, not follower profitability — the incentive is to maximise adoption, and publishing a drawdown would reduce adoption.
2. **Failures are unobservable by construction.** A person whose bot lost money has no reason to write it up, and if they do (as in §1.2 and §1.3) they get 1–3 stars. The population of "people who tried and stopped" is invisible, so **any sample of published results is survivorship-biased by construction.**
3. **The best-documented failure in this report is a backtest, not a live account.** Even among people willing to publish a loss, live-account losses are rarer in the record than backtest losses — because running live requires capital, and having lost it removes the motivation to write.
4. **One asymmetry runs the *other* way, and it matters.** The two most transparent sources I found (§1.3, §1.4) both disclose losses *because* disclosure of a negative result is itself the product — a portfolio piece demonstrating research discipline. So the sample of *transparent* sources is skewed toward people whose strategy failed. **You cannot use the published record to estimate a base rate in either direction** — see §3.

---

## 2. Backtest overfitting and the "few trades" problem

### 2.1 Freqtrade's own documentation on backtest reliability — what it actually says

**Source A:** `https://www.freqtrade.io/en/stable/backtesting/` (HTTP 200) and the canonical raw markdown `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/backtesting.md` **[VERIFIED-URL]**.

Freqtrade's backtest report includes a **`Mean profit p-value`** metric, defined as:

> "Two-sided p-value of a one-sample Student's t-test against the null hypothesis that the mean per-trade return is zero — in short, **'is the average profit distinguishable from noise?'** A small value (the usual bar is below `0.05`) means the observed edge is unlikely to be down to chance. **Its underlying t-statistic is identical to `SQN`.**"

This is the single most important sentence in this report for the small-account question, because it makes the trade-count problem **exactly** the classical t-statistic problem. The docs then state two caveats that cut *against* the reliability of the test:

> "Two things keep this honest. **The test assumes trades are independent and identically distributed, which real strategies rarely are (trades overlap and cluster in time), so the figure is an _optimistic_ lower bound — the true uncertainty is usually larger.** And because backtesting and hyperopt evaluate many strategies, some will score a low p-value by chance alone, so a small value only tells you a result is hard to explain by noise; it is not by itself proof of a genuine edge."

The docs' own worked example demonstrates the problem — **and it is, literally, a $1,000 account.** The canonical backtest output in the Freqtrade documentation is:

| Metric | Value |
|---|---|
| **Starting balance** | **1000 USDT** |
| Total/Daily avg trades | **77** / 2.48 |
| Total profit % | 5.72% |
| **CAGR %** | **92.41%** |
| **Sharpe (closed trades)** | **3.89** |
| Sortino (closed trades) | 2.57 |
| Calmar (closed trades) | 43.03 |
| SQN | 0.71 |
| **Mean profit p-value** | **0.4768** |
| Avg. stake amount | 345.478 USDT (≈35% of the account per trade) |

And the docs' own gloss on that p-value:

> "A value of `0.4768` therefore means roughly a 48% chance of a swing this large turning up from randomness alone - in other words **the average profit is not distinguishable from luck.**"

**[VERIFIED-URL] — Freqtrade's own reference example is a $1,000 account whose headline backtest shows a 92% CAGR and a Sharpe of 3.89, and which is statistically indistinguishable from noise at 77 trades.** Note also the stake sizing: an average stake of 345 USDT on a 1000 USDT balance with `max_open_trades = 3` means roughly **35% of the account in a single position** — the position-sizing regime this report's §4 discusses.

The docs also state the simulation's structural optimism, in the "Assumptions made by backtesting" section:

> "All orders are filled at the requested price (**no slippage**) as long as the price is within the candle's high/low range"
> "Stoploss exits happen exactly at stoploss price, even if low was lower"
> "backtesting will **never** replace running a strategy in dry-run mode. Also, keep in mind that past results don't guarantee future success."

And a small-account-specific hazard that is easy to miss:

> "This can lead to situations where trading-limits are inflated by using a historic price, resulting in **minimum amounts > 50$**."

**[REASONING]** On a $1,000 account with `max_open_trades = 3` and a $50+ exchange minimum per order, the minimum viable position size consumes ~15% of the account before any risk decision is made — and the backtest may have used a *smaller* historical minimum, so the simulated position sizing is not reproducible live. For a $2,000 account the constraint is proportionally half as binding but still real.

**Source B:** `https://www.freqtrade.io/en/stable/lookahead-analysis/` and `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/lookahead-analysis.md` **[VERIFIED-URL]**.

> "Lookahead bias is **the bane of any strategy** since it is sometimes very easy to introduce this bias, but can be very hard to detect."
> "Many strategies, without the programmer knowing, have fallen prey to lookahead bias. **This typically makes the strategy backtest look profitable, sometimes to extremes**, but this is not realistic as the strategy is 'cheating' by looking at data it would not have in dry or live modes."

And, critically for anyone hoping to repair a found strategy:

> "If you found a biased strategy online and want to have the same results, just without bias, then you will be out of luck most of the time. **Usually the bias in the strategy is THE driving factor for 'too good to be true' profits.** Removing conditions or indicators that push the profits up from bias will usually make the strategy significantly worse."

The docs also honestly list the tool's **false-negative** mode: signals that never trigger are not verified, so "the strategy will be reported as non-biased" incorrectly. And they note the tool chains backtests with `--dry-run-wallet` forced to 1 billion and `--stake-amount` forced to 10,000 — i.e. **the validation tool deliberately uses account sizes 10,000× larger than a retail account**, so it says nothing about whether a small account could actually take those trades.

**Source C:** `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/faq.md` **[VERIFIED-URL]**. Freqtrade's own FAQ, under the heading *"I have made 12 trades already, why is my total profit negative?"*:

> "I understand your disappointment but unfortunately **12 trades is just not enough to say anything.** If you run backtesting, you can see that the current algorithm does leave you on the plus side, but that is after **thousands of trades** and even there, you will be left with losses on specific coins that you have traded tens if not hundreds of times. ... it will **_always_ be a gamble**, which should leave you with modest wins on monthly basis but **you can't say much from few trades.**"

This is the project maintainers, in their own documentation, telling users that (a) trade counts in the tens are uninformative, (b) the profitable backtest they are comparing against is a *thousands-of-trades* result, and (c) the whole enterprise is "always a gamble."

### 2.2 How many trades before a result is distinguishable from luck? — the quantitative answer

**The identity that makes this tractable.** Freqtrade states that the backtest p-value's "underlying t-statistic is identical to `SQN`" **[VERIFIED-URL]**. Van Tharp's System Quality Number is defined as:

> **SQN = √(number of trades) × (expectancy / standard deviation of R-multiples)** — formula as documented by Edgewonk (Van Tharp's own brand) and Tradervue: `https://help.tradervue.com/article/3438-sqn-calculation` **[VERIFIED-URL]**

Tradervue reproduces Van Tharp's interpretation scale **[VERIFIED-URL]**:

| SQN | Interpretation (Van Tharp's scale) |
|---|---|
| 1.6 – 1.9 | Poor, but tradeable |
| 2.0 – 2.4 | Average |
| 2.5 – 2.9 | Good |
| 3.0 – 4.9 | Excellent |
| 5.0 – 6.9 | Superb |
| 7.0+ | "Maybe the Holy Grail!" |

**So `SQN` *is* the t-statistic, and `t = √N × (mean/SD)`.** The requirement "p < 0.05" therefore translates directly into a required per-trade edge that **scales as 1/√N**. **[REASONING — arithmetic on the two verified facts above]**

| N trades | Required mean/SD for t = 1.96 (p<0.05) | Required mean/SD for t = 3.0 (Harvey–Liu–Zhu hurdle, §2.5) |
|---|---|---|
| 10 | 0.620 | 0.949 |
| 20 | 0.438 | 0.671 |
| **30** | **0.358** | **0.548** |
| 50 | 0.277 | 0.424 |
| **100** | **0.196** | **0.300** |
| 200 | 0.139 | 0.212 |
| 500 | 0.088 | 0.134 |
| 1000 | 0.062 | 0.095 |

**How to read this table.** "mean/SD" is the average profit per trade divided by the standard deviation of per-trade profit. A typical trend-following crypto strategy with a 40% win rate and a 2:1 reward/risk has a per-trade mean/SD of roughly 0.1–0.2. **At 30 trades, such a strategy cannot possibly reach significance** — it would need a mean/SD of 0.36–0.55, i.e. a per-trade edge two to five times larger than a good strategy actually has. At 100 trades it is borderline. **You need on the order of 200–1,000 trades before a realistic edge becomes statistically distinguishable from luck.**

**A rule of thumb, labelled.** Van Tharp's scale implies a common practitioner rule of **"at least 100 trades"** before reading an SQN (quantmonitor.net states "2.5 or higher, measured over at least 100 trades"; journalplus.co notes "the same edge reads 3.33 at 100 trades but only 1.67 at 25 trades"). **[BLOG / PRACTITIONER folklore — third-party restatements of Van Tharp, not a peer-reviewed finding]**. My table above independently confirms the *direction and rough magnitude* of that rule of thumb from the t-statistic identity: 100 trades is approximately the point where a realistic edge (mean/SD ≈ 0.2) reaches p ≈ 0.05 — and it is **not** sufficient to clear a multiple-testing-corrected hurdle.

### 2.3 The minimum track record length — and a verified reproduction of the published numbers

**Source:** Bailey, D. H., & López de Prado, M., "The Sharpe Ratio Efficient Frontier," *Journal of Risk* (2012). Preprint PDF verified: `https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf` **[PREPRINT]** — 46 pages, downloaded and text-extracted in this session.

The paper defines the **Minimum Track Record Length (MinTRL)** — the length of track record needed to reject the null of "no skill beyond a threshold" at a given confidence. Two things it states plainly:

> "It is important to note that **MinTRL is expressed in terms of number of observations, not annual or calendar terms.**"
> "CLT is typically assumed to hold for samples in excess of **30 observations** (Hogg and Tanis (1996))."

And its worked figures **[PREPRINT]**:

> "For example, **a 2.73 years track record is required for an annualized Sharpe of 2 to be considered greater than 1 at a 95% confidence level**" (daily IID Normal returns).
> Weekly: **2.83 years** ("a 3.7% increase"). Monthly: **3.24 years** ("an 18.7% increase").
> With hedge-fund-realistic skewness/kurtosis (γ₃ = −3, γ₄ = 10, from Brooks and Kat 2002): **4.99 years** — "54% longer than what we required with Normal monthly returns, and 82.8% longer than what was needed with Normal daily returns."

**[REASONING] — I reproduced their headline figures exactly.** Using the standard IID-Normal form of MinTRL, `MinTRL = 1 + (1 + SR²/2) · (Z_α / (SR − SR*))²`, expressed in observations at the return frequency:

| Case | q (obs/yr) | My computed MinTRL | Paper's stated figure |
|---|---|---|---|
| Daily | 252 | 688.3 obs = **2.73 years** | **2.73 years** ✓ |
| Weekly | 52 | 147.1 obs = **2.83 years** | **2.83 years** ✓ |
| Monthly | 12 | 38.9 obs = **3.24 years** | **3.24 years** ✓ |

This exact three-way match confirms I am applying the published method correctly, which licenses the following extension for the small-account case.

**[REASONING] — the "short window ⇒ enormous confidence interval" result, made concrete.** Using the same normal-approximation, the annualised Sharpe a strategy must *exhibit* merely to be distinguishable from **zero** at 95% confidence, given only N observations:

| Observations available | Required annualised Sharpe to beat 0 at 95% |
|---|---|
| 30 days | **> 4.77** |
| 100 days | **> 2.61** |
| 252 days (1 year) | **> 1.65** |
| 504 days (2 years) | **> 1.16** |
| 1000 days (~4 years) | **> 0.83** |

**This is the quantitative treatment the question asks for.** A retail trader who has run a bot for three months and shows a Sharpe of 2.0 has, statistically, **demonstrated nothing** — the bar at 100 observations is 2.61. And a Sharpe of 2.0 needs **2.73 years** of daily data before it can even be called greater than 1.0 with confidence. The paper's own framing of why this matters:

> "In general it is misleading to judge strategies' performance by merely comparing their respective point estimates of ŜR, without considering the estimation errors involved in each calculation."

### 2.4 Backtest overfitting, with a genuinely damning worked example

**Source:** Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J., "The Probability of Backtest Overfitting," *Journal of Computational Finance* (2015 revision). Preprint PDF verified: `https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf` **[PREPRINT]** — 34 pages, downloaded and text-extracted.

**The central worked example — a pure random walk that passes a conventional significance test.** The authors build a seasonal strategy over a four-dimensional parameter mesh of **8,800 combinations** and fit it to **1,000 daily prices generated by a random walk** (about 4 years). Verbatim:

> "Parameters were optimized (Entry day = 11, Holding period = 4, Stop loss = -1 and Side = 1), resulting in an annualized **Sharpe ratio of 1.27**. Given the elevated Sharpe ratio, we may conclude that this strategy's performance is significantly greater than zero for any confidence level. Indeed, the **PSR-Stat is 2.83, which implies a less than 1% probability that the true Sharpe ratio is below 0**."
> "We have estimated the PBO using our CSCV procedure... **approx. 53% of the SR OOS are negative, despite all SR IS being positive** and ranging between 1 and 2.2. ... **despite the elevated SR IS, the PBO is as high as 55%.**"

**[PREPRINT] — the punchline: a backtest on data with *provably zero* signal produced a Sharpe of 1.27 and a sub-1% "significance" level, yet the probability of backtest overfitting is 55% and more than half of out-of-sample Sharpes are negative.** The authors' conclusion: "The CSCV framework has succeeded in diagnosing that the backtest was overfit."

**The control case, which proves the method discriminates.** When they plant a *real* monthly seasonal effect in the same random-walk generator, the optimal configuration gets a similar in-sample Sharpe (1.54 vs 1.27) but **PBO falls to 13%** with only 13% of OOS Sharpes negative. So PBO is not a blanket "everything is overfit" verdict — it distinguishes signal from noise, and it correctly flagged the random-walk case as overfit.

**Their generic example is worse:**

> "Whereas 100% of the SR IS are positive, **about 78% of the SR OOS are negative.** Also, **Sharpe ratios IS range between 1 and 3**, indicating that backtests with high Sharpe ratios tell us nothing regarding the representativeness of that result." (PBO = 74%)
> "We cannot hope escaping the risk of overfitting by exceeding some SR IS threshold. On the contrary, it appears that **the higher the SR IS, the lower the SR OOS.**"

For contrast, their "real investment strategy" example shows **PBO of 0.04%** and only 3% of OOS Sharpes negative — so a low PBO is achievable, and is therefore informative when reported. **It is almost never reported** (§2.6).

**The theoretical result — Minimum Backtest Length (MinBTL).** From "Pseudo-Mathematics and Financial Charlatanism" (Bailey, Borwein, López de Prado & Zhu, *Notices of the AMS* 61(5), May 2014, pp. 458–471) **[AMS NOTICES]** — PDF verified at `https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf`:

> **Theorem 3.1:** MinBTL ≈ ([(1−γ)Z⁻¹(1−1/N) + γZ⁻¹(1−1/(N·e))] / E[max_N SR])² **< 2·ln[N] / E[max_N SR]²**

with the headline implication, verbatim:

> "**if only 5 years of data are available, no more than 45 independent model configurations should be tried**, or we are almost guaranteed to produce strategies with an annualized Sharpe ratio IS of 1, but an expected Sharpe ratio OOS of zero."
> "**After trying only 7 independent strategy configurations, the expected maximum SR IS is 1 for a 2-year long backtest**, while the expected SR OOS is 0."

**[REASONING] — why this bites a small retail trader specifically.** Hyperopt and parameter sweeps make it trivial to exceed 45 configurations. The Freqtrade FAQ's own worked example references "**1000 hyperopt epochs**". At N = 1,000 trials, `MinBTL < 2·ln(1000)/E[max SR]² = 13.8/E[max SR]²` — to hold the expected maximum in-sample Sharpe at 1.0 you would need ~13.8 years of data. **A retail trader with 2–4 years of data who runs 1,000 hyperopt epochs has a MinBTL far in excess of their available history, and the published result is therefore expected to be overfit by construction.** The authors are explicit that N must be *independent* configurations (they suggest PCA dimension reduction otherwise), so the true effective N is smaller than 1,000 — but still far above 45.

### 2.5 The multiple-testing hurdle: why t = 2.0 is not enough

**Source:** Harvey, C. R., Liu, Y., & Zhu, H., "…and the Cross-Section of Expected Returns," *Review of Financial Studies* 29(1), 2016, pp. 5–68. PDF verified: `https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF` **[PEER-REVIEWED]** — 64 pages, downloaded and text-extracted.

This is the paper that quantifies how much the significance bar must rise once you account for how many things have been tried. Verbatim:

> "Hundreds of papers and factors attempt to explain the cross-section of expected returns. Given this extensive data mining, it does not make any economic or statistical sense to use the usual significance criteria for a newly discovered factor, e.g., **a t-ratio greater than 2.0**."
> "**We argue that a newly discovered factor today should have a t-statistic that exceeds 3.0.** We provide a time-series of recommended 'cutoffs' from the first empirical test in 1967 through to present day. **Many published factors fail to exceed our recommended cutoffs.**"
> "While a **t-statistic of 3.0 (which corresponds to a p-value of 0.27%)** seems like a very high hurdle, we also argue that there are good reasons to expect that **3.0 is too low**."
> "**a t-statistic of 2.0 is no longer appropriate—even for factors that are derived from theory.**"

Supporting numbers **[PEER-REVIEWED]**:

- They catalogue **316** published factors, and note "Our collection of 316 factors likely underrepresents the factor population."
- "Holm at 113 factors is **3.29** (p-value = 0.10%), while Holm at **316** factors is **3.64** (p-value = 0.03%)."
- "Across various correlation specifications, our estimates show that in general **a t-statistic of 3.9 and 3.0 is needed to control FWER at 5% and FDR at 1%**, respectively."
- In the appendix, modelling observed t-statistics as exponential draws above a 2.57 cutoff: "about **71.1% of tried factors are discarded**" and "the total number of factor tests is estimated to be **824**."
- "Our analysis of factor discoveries leads to the same conclusion – **many of the factors discovered in the field of finance are likely false** discoveries."

**Why this transfers to a retail bot, with one honest caveat.** **[REASONING]** The transfer is by *structure*, not by subject matter: the HLZ argument is that the correct hurdle depends on the number of trials performed, and it derives a higher hurdle from a documented count of trials. A retail trader running a hyperopt sweep over hundreds of configurations is performing exactly the same kind of search, and Freqtrade's docs already warn that "some will score a low p-value by chance alone" **[VERIFIED-URL]**. The caveat: HLZ's 3.0 figure is derived from the factor-research literature (published academic factors, low correlation, long samples), so it should be treated as an **indication that the bar is well above 2.0**, not as a precisely calibrated threshold for a 30-trade crypto backtest. My §2.2 table gives the trade-count translation for both hurdles.

### 2.6 The disclosure standard the literature demands — and the near-total failure to meet it

The Deflated Sharpe Ratio paper is explicit that a backtest without a trial count is uninterpretable. **Source:** Bailey, D. H., & López de Prado, M., "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality," *Journal of Portfolio Management* 40(5), 2014, pp. 94–107. Preprint PDF verified: `https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf` **[PREPRINT]** — 22 pages, downloaded and text-extracted.

> "the most important piece of information missing from virtually all backtests published in academic journals and investment offerings is the **number of trials attempted**. Without this information, it is impossible to assess the relevance of a backtest. **Put bluntly, a backtest where the researcher has not controlled for the extent of the search involved in his or her finding is worthless, regardless of how excellent the reported performance might be.**"
> "If we apply the holdout method enough times (say 20 times for a 95% confidence level), **false positives are no longer unlikely: They are expected.**"
> "**backtest overfitting in the presence of memory effects leads to negative performance out-of-sample.** Thus, selection bias combined with backtest overfitting misleads investors into allocating capital to strategies that will systematically lose money. The customary disclaimer that 'past performance does not guarantee future results' is **too lenient** when in fact adverse outcomes are very likely."

**The paper's numerical example, which is the clearest single illustration of the deflation effect [PREPRINT]:**

A strategist researching Treasury seasonality backtests many configurations and finds a strategy with an annualized **Sharpe of 2.5 over 5 years of daily data (T = 1250)**. By the conventional test this looks overwhelmingly significant. After deflating for the number of trials, the **Deflated Sharpe Ratio is 0.9002** — i.e. **only a 90% probability that the true Sharpe is above zero**, below the 95% bar, and the investor declines. The paper notes the counterfactual:

> "Should the strategist have made his discovery after running **only N = 46 independent trials**, the investor may have allocated some funds, as DSR would have been 0.9505, above the 95% confidence level."
> "If the strategy had exhibited Normal returns (γ̂₃ = 0, γ̂₄ = 3), DSR [would have passed] after **N = 88** independent trials."

**[REASONING] The practical translation: a 5-year, Sharpe-2.5 backtest survives scrutiny only if you ran fewer than ~46 trials.** Any hyperopt sweep over 100+ configurations exceeds that, and non-normal crypto returns (fat tails, negative skew) tighten it further. Given that the Freqtrade FAQ itself describes 1,000-epoch hyperopt runs, **a hyperopt-optimized crypto strategy is, by this standard, essentially guaranteed to be overfit.**

**And nobody reports the inputs.** I verified this directly on every real-world source in §1: **not one of the strategy repositories, blog posts, or case studies I fetched reports the number of configurations tried.** The Freqtrade backtest report does not surface it either. This is not a hypothetical methodological gap — it is the actual state of the public record.

The authors' proposed mitigation is worth stating because it is cheap and almost never followed:

> "From the set of strategy configurations that are theoretically justifiable, **sample a fraction 1/e of them (roughly 37%) at random** and measure their performance. After that, keep drawing and measuring the performance of additional configurations from that set, one by one, until you find one that beats all of the previous. That is the optimal number of trials."

---

## 3. The base rate at which backtested strategies survive live trading

**Headline: no source states a defensible "X% of backtested strategies survive live trading." The largest empirical study on the question does not report a survival fraction — it reports something more damning: backtest Sharpe ratio has essentially *no* predictive power for live Sharpe ratio (R² ≈ 0.02). And the two most widely circulated failure-rate numbers ("87%", "90%") are vendor folklore with no traceable source, which I verified by reading the pages that assert them.**

**Four different questions get conflated here, and they have four different answers.** Conflating them is the most common error in this space:

| Question | Best verified answer |
|---|---|
| Does backtest performance predict live performance? | **R² ≈ 0.02 — essentially no** (888 real strategies) |
| What fraction of *published academic factors* are false discoveries? | ~71% of tried factors discarded; 58% post-publication decay |
| What fraction of *retail day traders* profit? | ~20% in a given year; **<1%** persistently |
| What fraction of *retail crypto investors* lost money? | Majority; >4/5 under a monthly-buying assumption (simulation-based) |

### 3.1 The most on-point source: 888 real strategies with true out-of-sample data

**Wiecki, T., Campbell, R., Lent, J., & Stauth, J. (Quantopian Inc.), "All that glitters is not gold: Comparing backtest and out-of-sample performance on a large cohort of trading algorithms."** PDF verified and read in full: `https://community.portfolio123.com/uploads/short-url/3WHpAUOzhCG8QAUez71HpoWnA62.pdf` (SSRN working version; published in *Journal of Investments* 25(3):69, paywalled). **[PEER-REVIEWED]** — 19 pages, downloaded and text-extracted in this session.

**Sample (verbatim):** "a unique dataset of **888 algorithmic trading strategies** developed and backtested on the Quantopian platform with **at least 6 months of out-of-sample performance**," backtested 2010–2015. This is real crowd-sourced strategies with real deployed out-of-sample data — not a simulation.

**The key results, all verified verbatim:**

> "we find that commonly reported backtest evaluation metrics like the Sharpe ratio offer **little value in predicting out of sample performance (R² < 0.025)**."
> "we found a **weakly negative but highly significant** correlation between annual returns periods (**Pearson R²=0.015**; p < 0.001)"
> "Sharpe ratio IS was positively correlated with Sharpe ratio OOS (**Pearson R²=0.02**; p < 0.0001)"
> "**All other IS vs OOS performance metrics were not significant with Pearson R² values below 0.005**, including information ratio, Calmar ratio, and financial alpha."
> "in line with prior theoretical considerations, we find empirical evidence of overfitting – **the more backtesting a quant has done for a strategy, the larger the discrepancy between backtest and out-of-sample performance**." (Spearman R²=0.017 between log backtest-days and Sharpe shortfall)

**The contrast that makes this paper valuable:** risk metrics that are *not* return-based held up far better — **annual volatility R² = 0.67**, **maximum drawdown R² = 0.34**. So the finding is specific: *returns and risk-adjusted returns do not survive out-of-sample; risk characteristics do.*

**[REASONING] Why this is the single most important base-rate finding in this report.** An R² of 0.02 means **98% of the variance in live Sharpe ratio is unexplained by the backtest Sharpe ratio.** For a small-account trader this is the whole ballgame: the number you would use to decide whether to deploy capital carries essentially no information about what happens when you do. And the paper's own conclusion states it directly: a reported backtest Sharpe ratio "**can not be expected to prevail in future market environments with any reasonable confidence**."

⚠️ **One important negative finding about this paper.** I grepped the full text: it **does not** report what fraction of the 888 strategies lost money, and it contains **no "87%" or "90%" figure**. Any site citing the 888-strategy study for a *percentage failure rate* is over-reading it. This matters because, as §3.7 shows, that is exactly what one vendor blog does.

### 3.2 The largest out-of-sample audit of *public* strategies: 895 strategies, 2 survive, **0 beat holding**

This is the strongest large-N evidence I found on the base-rate question, and I verified its numbers **directly from its raw data file**, not from its prose.

**Source:** `https://github.com/Apex-prim/strategy-audit` — README and `LEDGER.csv` fetched raw **[VERIFIED-URL]**. Repo metadata via GitHub API: **3 stars, 0 forks, MIT, created 2026-08-20, pushed 2026-08-24** — i.e. brand new and unreplicated by anyone else.

**What it is.** An out-of-sample audit of **895 unique strategy classes from 53 public repositories** — "Every public freqtrade strategy that could be found and loaded... run by **freqtrade itself** on its own declared timeframe, in its author's window and in years the author never saw." The author runs freqtrade 2026.7 itself rather than re-implementing the logic, explicitly to pre-empt "you rewrote my logic wrong."

**I independently recomputed the headline results from `LEDGER.csv` (233,709 bytes, 895 data rows, 23 columns).** My own computation, not the author's summary:

| My computation from the raw CSV | Result |
|---|---|
| Total strategies in ledger | **895** ✓ |
| Strategies surviving through the final gate (`survives_through = E6`) | **2** |
| …of which `beats_bh == True` | **0** ✓ |
| Strategies dropped at the first gate (`E0`) | 878 |
| `beats_bh == True` anywhere in the ledger | 28 (but 0 survive the gates) |

**The two survivors, in full (my extraction from the CSV):**

| Strategy | Repo | OOS trades | OOS avg/trade | OOS p | OOS CI lower | OOS total | Buy-and-hold | Beats B&H? |
|---|---|---|---|---|---|---|---|---|
| `CombinedBinHClucAndMADV5` | davidzr/freqtrade-strategies | **1,295** | **+0.46%** | **8.4e-15** | +0.344 | **+106.91%** | **+346.34%** | **No** |
| `ClucHAnix_5m_old` | TheoBrigitte/freqtrade | 2,190 | +0.29% | 6.5e-05 | +0.148 | +111.99% | +346.34% | **No** |

**These figures match the README's prose exactly** — it states the survivor "returns **+106.9%** while buy-and-hold returns **+346.3%**" and "earns a genuine **+0.46%** *per trade*," which is precisely what the CSV rows contain. That is a real verification, not a restatement.

**[REASONING] This single row is the most instructive number in this entire report.** `CombinedBinHClucAndMADV5` has **1,295 out-of-sample trades** (far above the ~200–1,000 threshold I derived in §2.2), a per-trade edge of **+0.46%**, **p = 8.4 × 10⁻¹⁵**, and a **positive 95% confidence-interval lower bound** — a *statistically bulletproof* edge by every test in §2. And it still **underperforms simply holding the coins by 239 percentage points of cumulative return.** The author's own framing is exactly right: "**It is not broken and it is not noise: it captures a fraction of a rise it never predicted, and holding captured all of it.**" **Statistical significance is necessary but nowhere near sufficient.**

**The funnel, and where the corpus dies.** The author reports the largest single drop as `G2_is_pos`: **456 → 158** — "strategies that lose money **in the window their own author chose**. **Two thirds of published strategies are already negative before anyone tests them on new data.**" The second-largest is `G7_recursive` (51 killed, **50 of them measured indicator drift** — indicator values that change with how much history you feed them).

**The pre-registered endpoint:** "PRIMARY ENDPOINT — survivors that beat buy-and-hold, frozen rule: **0 of 456 eligible = 0.00%**." Multiplicity is handled explicitly: Benjamini–Hochberg threshold 3.872e-02 over 81 tests (72 rejected), with **Benjamini–Yekutieli** (valid under *arbitrary* dependence) reported alongside at 2.752e-03 — "both survivors still clear it."

**The most valuable part: the author's own self-criticism, which I quote because it is what separates this from the sources in §3.7.**

- The README **was previously wrong**: "The README once carried *'571 strategies, 55 clean'* for a day after the corpus had grown past 900, and a reader built an assessment on it — so the numbers here now have a return code behind them rather than a promise." A CI gate (`verify_ledger.py`) now rebuilds the ledger block from `LEDGER.csv` and fails on any mismatch.
- The verdict for this corpus is **"repair-adjusted", not pre-registered**: `freeze_guard.py` reports "ladder last changed: 2026-08-22 10:59:04 UTC / first observation: 2026-08-21 19:58:24 UTC / **verdict: repair-adjusted**" — because the last two gates were added 15 hours *after* the first result card. The author states plainly: "**Transparency does not convert a post-hoc decision into a pre-registered one.**"
- **The aggregate verdict depends on the window, and the author says so.** Splitting by calendar year (a division declared before the run): in 2020, 2021, 2023, 2024 (up years) **0 of 5** survivors beat buy-and-hold; in 2022, 2025, 2026 (down years) **5 of 5** did. "Seven years, seven correct calls by the sign of the market. **The aggregate verdict was a property of the window.**" And crucially: "**That is not a discovery of working strategies.** In 2022 the market fell 66.7% while these five returned between −5.9% and +3.5% — they were barely in the market at all, and **sitting out a crash is something cash does without any strategy.**"

**Caveats I must state, and they are real:**

1. **This is out-of-sample *backtest*, not live trading.** It answers "backtest → new data," which is *not* the same as "backtest → live with real fills." It is nevertheless the closest large-N evidence that exists.
2. **Self-published and unreplicated** — 3 stars, 0 forks, weeks old, and "independent" is the author's own description. I verified the data file's contents but **could not independently reproduce the ladder's specific counts**: my naive recomputation with guessed thresholds gave 533 strategies with `is_trades>0` and 192 with `is_exp>0`, versus the README's 496 and 158. The gates have thresholds I do not have (`verify_ledger.py` would settle it), so **I confirm the endpoints (2 survivors, 0 beating buy-and-hold, and the exact return figures) but not the intermediate funnel counts.**
3. **The corpus is 65% copies.** The author reports "**65% of the 2,567 strategy classes found are copies** of a few originals, propagated without anyone re-testing them," and 17 of 53 repos contributed no original strategy (one holds 477 classes). So the **effective number of independent strategies is far below 895** — which the author addresses via Benjamini–Yekutieli but which any reader should keep in mind.
4. **One window, 8 pairs, one execution model**, as the author repeatedly states.

**A directly corroborating line-by-line audit.** The same author audited five strategies from `paulcpk/freqtrade-strategies-that-work` — the exact repo I cited in §1.7 — applying significance tests to both windows **[VERIFIED-URL]**:

| Strategy | In-sample avg/trade | IS p | Out-of-sample avg/trade | OOS p |
|---|---|---|---|---|
| EMAPriceCrossoverWithThreshold | 1.39% | **0.113** | 0.65% | 0.161 |
| DoubleEMACrossoverWithTrend | 0.38% | **0.049** | 0.19% | 0.290 |
| MACDCrossoverWithTrend | 0.42% | **0.128** | 0.05% | 0.883 |
| RSIDirectionalWithTrendSlow | 1.03% | **0.381** | 0.27% | 0.924 |
| RSIDirectionalWithTrend | 0.34% | **0.238** | −0.07% | 0.556 |

> "**Four of the five were never statistically significant in their author's own window, and none is significant out of sample.** Only `DoubleEMACrossoverWithTrend` clears p < 0.05 in-sample, and only just (0.049). The strongest performer of the set — `EMAPriceCrossoverWithThreshold` at 1.39% per trade — sits at **p = 0.113**."

**[REASONING] This is the empirical confirmation of §2.2.** A published strategy collection advertising total profits of 16–122% (§1.7) turns out to be **statistically insignificant in its own backtest window** for 4 of 5 strategies — exactly what the trade-count arithmetic predicts. And the fee sensitivity is equally damning: at **0.3% per side** (routine for XLM/DASH/ADA hourly spreads in 2018–2020), three of the five go to ~zero or negative — "`MACDCrossoverWithTrend` 0.01% ← **zero wearing a plus sign**."

⚠️ **One discrepancy I could not resolve.** The README's prose says "Under the rules declared before the sweep, **66** strategies survive and **four** beat the market," while the ledger block says E0 survivors **17** / beating buy-and-hold **3** — and my CSV computation gives 15 E1-survivors of which **3** beat buy-and-hold. The "3" agrees; the survivor counts (66 vs 17 vs 15) do not. Given the author documents that the corpus grew and that numbers changed, the prose likely reflects a superseded corpus state. **Treat the ledger block and the CSV as authoritative; treat the prose's 66/4 as stale.**



### 3.3 The base rate is *conditional*, not constant — the most useful nuance in the literature

**[PREPRINT]** — Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" (verified in §2.4, `https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf`).

The same paper supplies both ends of the range:

| Example | Share of out-of-sample Sharpe ratios that are negative | PBO |
|---|---|---|
| Heavily-mined seasonal strategy on a **random walk** | **~53%** (and **~78%** in the generic example) | **55%** / **74%** |
| Synthetic series with a **real planted effect** | 13% | 13% |
| A **real investment strategy** | **3%** | **0.04%** |

**This is the single most important qualification in the base-rate question.** There is no fixed failure rate to quote, because the failure rate is a *function of the development process*. A strategy found by searching thousands of configurations has a ~50–78% chance of negative out-of-sample performance; a strategy with a genuine underlying effect has ~3%. **Quoting one number for "backtested strategies" destroys the actual finding.** The correct statement is: *the base rate depends on how hard you searched, and for a hyperopt-heavy retail workflow (§2.6) it is at the bad end of that range.*

### 3.4 Academic false-discovery rates — a *different* question, and the difference matters

**[PEER-REVIEWED] — Harvey, Liu & Zhu (2016)** (verified in §2.5, `https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF`). Their appendix estimate is the most-cited "failure rate" in finance: modelling observed t-statistics as exponential draws above a 2.57 cutoff, "the mean absolute value of the t-statistic for the underlying factor population is 2.07 and **about 71.1% of tried factors are discarded**," with the total number of factor tests estimated at **824**. Conclusion: "**most claimed research findings in financial economics are likely false**."

**[PEER-REVIEWED] — McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal of Finance* 71(1):5–32.** Verified from the author's final manuscript: `https://tevgeniou.github.io/EquityRiskFactors/bibliography/AcademicReviewFactor.pdf` — abstract verbatim:

> "We study the out-of-sample and post-publication return-predictability of **97 variables**... Portfolio returns are **26% lower out-of-sample** and **58% lower post-publication**. The out-of-sample decline is an upper bound estimate of data mining effects. We estimate a **32% (58% − 26%) lower return from publication-informed trading**."

⚠️ **Version warning for citation hygiene.** Earlier working-paper versions circulate with *different* numbers (82 characteristics / 10% / 35%; 95 characteristics / 13%). **Cite 97 / 26% / 58% only against the published JF version**, which is what I read.

**[REASONING] Do not present these as "X% of trading bots fail."** The gap is not a detail:

| Claim | Status |
|---|---|
| "~71% of *tried academic factors* are discarded; many published factors are likely false" | **[PEER-REVIEWED]** (HLZ 2016) |
| "Published predictors decay ~58% post-publication" | **[PEER-REVIEWED]** (McLean & Pontiff 2016) |
| "~X% of *retail crypto bots* lose money live" | **No credible source found. Not established.** |

HLZ's 71.1% is about *academic equity factors*, is an *inference* from a fitted distribution rather than a direct count, and concerns *factors tested and discarded* — a different population from *retail traders who deployed and lost*. The transferable content is the **mechanism** (multiple testing inflates the best-looking result), not the number.

### 3.5 Retail trader base rates — the right evidence, from adjacent markets

No crypto-specific base rate exists (§3.6), so the best available proxies come from equity/futures day-trading research. **These are not crypto**, and the caveat is load-bearing.

**[PEER-REVIEWED] — Barber, B., Lee, Y.-T., Liu, Y.-J., & Odean, T. (2014), "The cross-section of speculator skill: Evidence from day trading," *Journal of Financial Markets* 18:1–24.** PDF verified and read: `https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf` — Taiwan Stock Exchange, 1992–2006.

> "In the average year during our 1992–2006 sample period, about **450,000** Taiwanese individuals engaged in day trading... about **20% of these day traders earn positive abnormal returns net of fees**... **Of course, some outperformance would be expected by sheer luck.**"
> "we document that **only the 4,000 most profitable day traders (less than 1% of the total population of day traders) from the prior year go on to earn reliably positive abnormal returns net of trading costs in the subsequent year**."
> Abstract: "**Less than 1% of the day trader population is able to predictably and reliably earn positive abnormal returns net of fees.**"

**[REASONING] The 20%-versus-<1% distinction is the cleanest illustration of why these questions get conflated.** "20% of day traders are profitable" sounds like a workable base rate; the paper's own gloss is that this is consistent with luck, and that **under 1%** show *persistent* skill. **Quoting the 20% as a success rate is a serious error** — and it is exactly the error that the "you can be profitable too" genre depends on.

**[PEER-REVIEWED] — Chague, F., De-Losso, R., & Giovannetti, B. (2019), "Day trading for a living?"** PDF verified and read: `https://repec.eae.fea.usp.br/documentos/Chague_Losso_Giovannetti_47WP.pdf` — Brazilian equity futures, all 19,646 individuals who began day trading 2013–2015.

> "We observe all individuals who began to day trade between 2013 and 2015 in the Brazilian equity futures market... and persisted for at least 300 days: **97% of them lost money, only 0.4% earned more than a bank teller (US$54 per day)**, and the top individual earned only US$310 per day with great risk (a standard deviation of US$2,560). Additionally, we find **no evidence of learning** by day trading."

And the attrition pattern, which is the most citable single result in this literature — share of traders with positive net profit, by days traded:

| Days traded | 1 | 2–50 | 51–100 | 101–200 | 201–300 | >300 |
|---|---|---|---|---|---|---|
| % positive net profit | 29.8% | 15.5% | 8.9% | 6.8% | 5.4% | **3.0%** |

> "the proportion of successful day traders **decreases monotonically** with the number of days they trade. This peculiar pattern is similar to what we would find, for instance, in the casino roulette."

**[REASONING] This monotonic decline is the most directly relevant finding in this report for a small-account trader**, because it is precisely the opposite of what a learning curve would produce. The longer people persist, the *fewer* of them are profitable — which is consistent with early profits being luck that mean-reverts, leaving only the skilled (or the lucky) survivors. For a bot trader, the analogue is: **early profitability is weak evidence, and persisting does not improve the odds.**

**[VERIFIED-URL] — regulators, primary sources (different instruments, but useful context):**

- **ESMA (2018)**, ref ESMA71-98-128: "NCAs' analyses on CFD trading across different EU jurisdictions shows that **74-89% of retail accounts typically lose money** on their investments, with average losses per client ranging from €1,600 to €29,000." — `https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors` — **leveraged CFDs, account level, EU, 2018 — not crypto bots.**
- **CFTC**, *Must Know Forex*: "**Two out of three forex customers lose money.** ... Over the past year, about one-third of customers at registered OTC forex dealers made a profit, while two-thirds lost money." (footnote: based on disclosures for Q2 2021–Q1 2022) — `https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/CustomerAdvisory_MustKnowForex.html` — **retail OTC forex — not crypto bots.**

### 3.6 Crypto-specific evidence

**[VERIFIED-URL] — BIS Bulletin No 69, "Crypto shocks and retail losses" (Cornelli, Doerr, Frost & Gambacorta, 20 Feb 2023).** PDF verified and read: `https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf`.

> "In nearly all economies in our sample, **a majority of investors probably lost money** on their bitcoin investment."
> "The **median investor would have lost $431 by December 2022**, corresponding to almost half of their total $900 in funds invested since downloading the app."
> "If investors continued to invest at a monthly frequency, **over four fifths of users would have lost money**."
> "**almost three-quarters of the users downloaded a crypto platform app when the price of bitcoin was above $20,000**"

⚠️ **Critical methodological caveat, stated by the authors themselves and essential when citing this:** these are **simulated/proxy losses, not realized account P&L**. Verbatim: "**Assuming users invested in bitcoin on the same day they downloaded the app, we proxy the size of the loss** ... we assume that each new user bought $100 of bitcoin in the month of the first app download and in each subsequent month." **This is an adoption-timing model, not a measurement of strategy or bot performance.** It says retail investors bought near the top; it says nothing about algo trading.

**And the crypto-specific base rate genuinely does not exist.** I found no peer-reviewed study of crypto trading-bot or strategy survival. Searches returned only vendor blogs plus one tangential peer-reviewed paper on chart patterns in the Mt.Gox era that contains no profitability base rate. **This is a real gap in the literature, not a gap in my search.**

### 3.7 The "87%" and "90%" failure rates — traced, and both are unsourced vendor folklore

This is the most valuable negative finding of this section, and I verified both pages by reading them.

**(i) "Why 87% of Backtested Strategies Fail in Live Trading"** — `https://www.sigmentic.com/blog/why-backtested-strategies-fail` — fetched and read in full. **[BLOG — no traceable source]**

> "Research in empirical finance puts the failure rate of backtested trading strategies at **up to 87%**."

**No citation is given for 87% anywhere on the page.** The only studies it names are Harvey, Liu & Zhu (2016) and Bailey/Borwein/López de Prado/Zhu (2014) — **I read both in full (§2.4, §2.5, §3.4); neither contains an 87% figure.** It also cites "HFR data consistently shows annual systematic fund attrition in the **5% to 15%** range" — that is **hedge-fund closure rates**, a completely different quantity from strategy failure, and it is presented adjacent to the 87% claim in a way that implies support. The page is a funnel for a validation product ("Join the waitlist", "Start Free").

**(ii) "Why 90% of Trading Bots Fail"** — `https://intradaylab.com/blog/why-trading-bots-fail-backtest-mistakes` — fetched and read in full. **[BLOG — no traceable source]**

Its "Key Stats" box asserts five numbers, **none with any citation**:

> "**73%** of automated trading accounts fail within six months of going live / **44%** of published trading strategies fail to replicate backtest results on new data / The backtested-to-live failure rate for traditional algos is estimated at **80%+** / **22%** of live algo trading losses among retail traders are caused by infrastructure failures — not bad strategy design / Only **60%** of retail traders even run proper historical validation before going live"

**The "90%" in the title is never sourced anywhere in the article.** Its closing line asserts it as established fact: "The 90% failure statistic isn't pessimistic. It's clarifying."

⚠️ **The instructive detail: this page mixes one genuine, correctly-cited finding with four unsourced numbers.** It states — accurately — "A study of **888 algorithmic strategies** found that backtested Sharpe ratios are poor predictors of real-world performance — the **R² was less than 0.025**." That is the Wiecki et al. paper from §3.1, and the figure is right. **But the page never links it**, so a reader cannot check it, and it sits alongside four fabricated-looking statistics. This is precisely the pattern that makes vendor content dangerous: a real citation lending credibility to invented neighbours.

**[REASONING] Conclusion on the folklore numbers.** The "87%" appears to be invented or telephone-gamed from unrelated figures (hedge-fund attrition, or HLZ's 71.1%). The "90%" has no source at all. **Neither should be cited.** The defensible substitute is §3.1 (R² ≈ 0.02) and §3.3 (conditional base rate).

### 3.8 What the verified real-world record does tell you about base rates

**[REASONING, from the verified cases in §1.]** My case sample is small and deliberately **not** presented as representative — but its *composition* is informative:

- Of the documented cases I verified with actual numbers, **every single one was a loss** (§1.2: seven strategies, all negative; §1.3: −$94 over 139 trades).
- The only positive numbers I found were **backtest claims with no live counterpart** (§1.6: +1,450%, with a mathematically impossible Calmar ratio) or **fabricated-looking templates** (§1.5).
- The two most-adopted strategy repositories publish **no performance numbers at all** (§1.4).

**I cannot compute a base rate from this, and neither can anyone else from public sources.** The honest conclusion: **the base rate is unknown; the *mechanism* of failure is well established; and the published evidence is systematically biased in both directions** (§1.8). The one number I would actually rely on is Wiecki's R² ≈ 0.02 — not because it is a failure rate, but because it says the backtest cannot tell you, which is the operationally relevant fact.

---

## 4. What this means for a $1,000–$2,000 account

**[REASONING — synthesis of the verified material above, clearly labelled as inference.]**

1. **The statistical bar is not reachable at small account sizes within any reasonable timeframe.** §2.2 shows that distinguishing a realistic edge from luck needs ~200–1,000 trades. At a plausible 2–5 trades/week for a small multi-pair bot, that is **1–10 years** of live running. A six-month "it's working" conclusion is not supported by anything in this report.
2. **The backtest will look better than reality, and the mechanism is documented in the tool's own manual** — no slippage modelled, stoplosses filled exactly at the stop price, lookahead bias "easy to introduce, hard to detect," and hyperopt exploring far more configurations than MinBTL permits.
3. **Small accounts hit structural frictions that backtests do not model.** Freqtrade documents exchange minimum order sizes that can exceed $50, and the lookahead-analysis tool itself validates at a 1-billion wallet with 10,000 stakes. Position-size granularity, minimum-notional limits, and the resulting inability to size positions precisely are *specific* to small accounts and are **not** in the backtest.
4. **The capital ceiling is arithmetic, not strategy.** Even granting the unsourced 30% APY figure from §1.2, $2,000 × 30% = $600/year ≈ $50/month. **This is the strongest single argument in the report**, precisely because it requires no strategy assumption at all beyond a generous upper bound: at $1,000–$2,000, the *maximum plausible* outcome is a hobby-scale sum, while the downside is total loss plus the cost of the VPS, the subscription, and the time.
5. **The disclosure you would need to evaluate any claim is essentially never published.** No source I found reported its trial count, its PBO, or its MinTRL — the three quantities the peer-reviewed literature says are required (§2.6). Any claim that omits them is, in the DSR authors' words, "worthless, regardless of how excellent the reported performance might be."

---

## 5. COULD NOT VERIFY

Explicitly listed so these gaps are not mistaken for findings.

| # | Item | Why it could not be verified |
|---|---|---|
| 1 | **Any independently verified (API/audited) small-account crypto track record** | None found in any search. This is the report's central negative finding. |
| 2 | **Reddit content** (r/algotrading, r/freqtrade_io, r/CryptoCurrency) | `old.reddit.com` returns a "Welcome to Reddit" block page; the Reddit JSON API returns non-JSON; `web_fetch` on `reddit.com` returns an empty JS shell. **Reddit was inaccessible from this environment**, so community self-reports could not be examined at all. |
| 3 | **Freqtrade Discord** | Not publicly indexed or archivable by design. Confirmed the project points users there (`docs/faq.md`), and that `github.com/freqtrade/freqtrade/discussions` is HTTP 404. |
| 4 | **Freqtrade GitHub Discussions** | HTTP 404 — the venue does not exist. |
| 5 | **Any crypto-specific study of trading-bot or strategy survival** | **Does not appear to exist.** Searches returned only vendor blogs plus one tangential peer-reviewed paper (chart patterns in the Mt.Gox era) that contains no profitability base rate. The crypto-specific base rate is genuinely unestablished in the literature. |
| 6 | **"Fraction of backtested strategies that survive live trading" as a single number** | **No peer-reviewed source states it.** The best dataset (888 strategies) reports R² ≈ 0.02, not a survival fraction. |
| 7 | **"87% of backtested strategies fail"** (`sigmentic.com`) | **No source given; the number is not present in either study the page cites** (both read in full by me). [FOLKLORE] |
| 8 | **"90% of trading bots fail"** (`intradaylab.com`) | **Never sourced in the article.** Its four companion stats (73% / 44% / 80%+ / 22% / 60%) are likewise uncited. [FOLKLORE] |
| 9 | **"90% of crypto trading bots lose money"** (`markettrace.ai`) and **">80% of retail bot traders lose" from "2026 data from multiple exchanges"** (`coincentral.com`) | Reported by a sub-investigation; **I did not independently fetch these two pages**, and no exchange, dataset, or study is named. [FOLKLORE — not cited as evidence] |
| 10 | **"SEC research consistently puts [day-trader failure] around 90%"** | No SEC document found stating it; explicitly rejected as too broad by the source that examined it. [FOLKLORE] |
| 11 | **"73–81% of retail crypto investors incurred losses"** attributed to **BIS Working Paper 1049** | **Not in BIS Bulletin 69**, which I read in full. WP 1049 itself was unfetchable (bis.org served an HTML block page). **Unresolved — do not cite.** |
| 12 | **Prop-firm pass rates** (FTMO "10–12%", Apex "12–18%", cross-firm "8–17%") | No primary source verified. The compiler of the 8–17% figure itself states that no reproducible calculation remains. [CLAIM — not cited] |
| 13 | **eToro/JFE retail-crypto trading paper** ("Are cryptos different? Evidence from retail trading") | ScienceDirect returned HTTP 403; no open copy located. **Likely the best peer-reviewed retail-crypto dataset and I could not access it** — a notable gap. |
| 14 | **`francisx1999/crypto-trading-bot-postmortem` backtest numbers** | **Unreproducible.** Verified via GitHub API that the repo contains zero backtest artifacts; the README defers to "raw logs available on request." Self-reported and AI-assisted. |
| 15 | **`OfficialGIGA` and `Bananajoexxc` figures** | Self-reported; no starting balance stated for the former; the latter's Calmar ratio is internally impossible (§1.6). |
| 16 | **Wiecki et al. — the fraction of the 888 strategies that lost money** | **Not reported in the paper**; I grepped the full text. Only aggregate R² and top-10 portfolio results are given. Do not let anyone attribute a failure percentage to this study. |
| 17 | **FCA "≈80% of CFD customers lose money"** | Cited secondhand only; I did not fetch the FCA handbook page. [CLAIM — not cited] |
| 18 | **Search-engine access generally** | `web_search` returned "No results found" for most queries; DuckDuckGo Lite served a bot challenge mid-session; Brave Search returned HTTP 429 persistently; Bing returned query-irrelevant results; SearxNG instances sat behind anti-bot pages; Semantic Scholar API returned 429. Discovery relied on early DDG Lite results, direct URL construction, the GitHub API, and raw-file fetches. |

---

## 6. Source list, with verification status

| Source | URL | Status |
|---|---|---|
| Freqtrade backtesting docs | `https://www.freqtrade.io/en/stable/backtesting/` | **[VERIFIED-URL]** HTTP 200 |
| Freqtrade backtesting docs (raw) | `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/backtesting.md` | **[VERIFIED-URL]** |
| Freqtrade lookahead-analysis docs | `https://www.freqtrade.io/en/stable/lookahead-analysis/` | **[VERIFIED-URL]** HTTP 200 |
| Freqtrade lookahead docs (raw) | `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/lookahead-analysis.md` | **[VERIFIED-URL]** |
| Freqtrade FAQ (raw) | `https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/faq.md` | **[VERIFIED-URL]** |
| Bailey/Borwein/LdP/Zhu, "Pseudo-Mathematics and Financial Charlatanism," *Notices of the AMS* 61(5) | `https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf` | **[AMS NOTICES]** PDF downloaded, text extracted |
| Bailey/Borwein/LdP/Zhu, "The Probability of Backtest Overfitting" | `https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf` | **[PREPRINT]** 34 pp. extracted |
| Bailey & López de Prado, "The Deflated Sharpe Ratio," *JPM* 40(5) | `https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf` | **[PREPRINT]** 22 pp. extracted |
| Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier" | `https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf` | **[PREPRINT]** 46 pp. extracted; **figures independently reproduced** |
| Harvey, Liu & Zhu, "…and the Cross-Section of Expected Returns," *RFS* 29(1) | `https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF` | **[PEER-REVIEWED]** 64 pp. extracted |
| Van Tharp SQN scale (Tradervue) | `https://help.tradervue.com/article/3438-sqn-calculation` | **[VERIFIED-URL]** |
| Van Tharp SQN formula/thresholds (Edgewonk, Van Tharp's brand) | `https://edgewonk.zendesk.com/hc/en-us/articles/360010061840-SQN-by-setup-System-Quality-Number` | **403 (Cloudflare) — scale corroborated via Tradervue instead** |
| OfficialGIGA freqtrade-ml-strategy README | `https://raw.githubusercontent.com/OfficialGIGA/freqtrade-ml-strategy/main/README.md` | **[VERIFIED-URL]** |
| OfficialGIGA RESULTS.md | `https://raw.githubusercontent.com/OfficialGIGA/freqtrade-ml-strategy/main/RESULTS.md` | **[VERIFIED-URL]** |
| francisx1999 crypto-trading-bot-postmortem README | `https://raw.githubusercontent.com/francisx1999/crypto-trading-bot-postmortem/master/README.md` | **[VERIFIED-URL]**; repo tree enumerated via GitHub API |
| Bananajoexxc RegimeFilterStrategy README | `https://raw.githubusercontent.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade/main/README.md` | **[VERIFIED-URL]** |
| NostalgiaForInfinity README (affiliate links) | `https://raw.githubusercontent.com/iterativv/NostalgiaForInfinity/develop/README.md` | **[VERIFIED-URL]** |
| MoniGoMani README (affiliate links) | `https://raw.githubusercontent.com/Rikj000/MoniGoMani/main/README.md` | **[VERIFIED-URL]** |
| dev.to "Lesson 23: Freqtrade Small Capital Live Trading" | `https://dev.to/henry_lin_3ac6363747f45b4/lesson-23-freqtrade-small-capital-live-trading-3ioc` | **[VERIFIED-URL]** — **[BLOG], numbers are illustrative templates, NOT evidence** |
| paulcpk freqtrade-strategies-that-work | `https://github.com/paulcpk/freqtrade-strategies-that-work` | **[PRACTITIONER]**; workspace copy cross-checked |
| **Wiecki, Campbell, Lent & Stauth, "All that glitters is not gold"** (888 strategies) | `https://community.portfolio123.com/uploads/short-url/3WHpAUOzhCG8QAUez71HpoWnA62.pdf` | **[PEER-REVIEWED]** — 19 pp. downloaded, extracted, read |
| Barber, Lee, Liu & Odean (2014), "The cross-section of speculator skill," *JFM* 18:1–24 | `https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf` | **[PEER-REVIEWED]** — 24 pp. read |
| Chague, De-Losso & Giovannetti (2019), "Day trading for a living?" | `https://repec.eae.fea.usp.br/documentos/Chague_Losso_Giovannetti_47WP.pdf` | **[PEER-REVIEWED]** — 18 pp. read |
| Harvey & Liu, "Evaluating Trading Strategies," *JPM* 40(5):108–118 | `https://people.duke.edu/~charvey/Research/Published_Papers/P116_Evaluating_trading_strategies.pdf` | **[PEER-REVIEWED]** — 11 pp. read |
| Harvey & Liu, "Backtesting," *JPM* 42(1) | `https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF` | **[PEER-REVIEWED]** — 17 pp. read |
| McLean & Pontiff (2016), *Journal of Finance* 71(1):5–32 | `https://tevgeniou.github.io/EquityRiskFactors/bibliography/AcademicReviewFactor.pdf` | **[PEER-REVIEWED]** — author's final manuscript (JF typeset PDF paywalled) |
| BIS Bulletin No 69, "Crypto shocks and retail losses" | `https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf` | **[VERIFIED-URL]** — 8 pp. read; **simulation-based, not realized P&L** |
| ESMA press release ESMA71-98-128 (27 Mar 2018) | `https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors` | **[VERIFIED-URL]** — regulator, primary |
| CFTC, *Must Know Forex* customer advisory | `https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/CustomerAdvisory_MustKnowForex.html` | **[VERIFIED-URL]** — regulator, primary |
| Sigmentic, "Why 87% of Backtested Strategies Fail" | `https://www.sigmentic.com/blog/why-backtested-strategies-fail` | **[VERIFIED-URL]** — **[BLOG]; 87% has NO source; vendor funnel** |
| Intraday Lab, "Why 90% of Trading Bots Fail" | `https://intradaylab.com/blog/why-trading-bots-fail-backtest-mistakes` | **[VERIFIED-URL]** — **[BLOG]; 90% never sourced; five uncited stats** |

---

## 7. Three-sentence summary

**Verified:** the statistical machinery for judging a backtest is real, quantitative, and damning — a random-walk backtest can show Sharpe 1.27 with a sub-1% significance level while having a **55% probability of being overfit**; an annualized Sharpe of 2 needs **2.73 years** of daily data to beat 1.0 at 95%; **30 trades requires a per-trade mean/SD of 0.36–0.55** to be distinguishable from luck, which no realistic crypto strategy achieves; and in the largest study of real deployed strategies (**888** algorithms), in-sample Sharpe explained **R² ≈ 0.02** of out-of-sample Sharpe. **Verified:** the public real-world record for $1,000–$2,000 accounts contains **no independently verified track record at all** — the best-documented case is a seven-strategy, all-negative backtest post-mortem whose claimed "receipts" I confirmed are absent from its repository, the most-adopted strategy repos publish **nine affiliate links and no performance data**, and the two most-cited failure rates (**"87%"**, **"90%"**) have **no traceable source** in the studies they cite. **Conclusion:** at $1,000–$2,000 the binding constraint is not strategy quality but arithmetic and statistics — a generous 30% APY on $2,000 is ~$50/month, the backtest cannot tell you whether the strategy works (R² ≈ 0.02), and the evidence needed to know would take hundreds of trades and years of live running to accumulate.
