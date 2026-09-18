# Strategy Classes and Their Net-of-Fee Evidence in Crypto

**Scope:** Can a small crypto account (~$1,000–2,000 CAD) profit from algorithmic trading? This document
covers **strategy classes and their net-of-fee evidence**, not account-size mechanics.

**Assumed cost environment (given in the research brief):** spot, daily candles, **~0.40% maker fee per
side = ~0.80% per round trip**. This is the single most important number in this document. Every
net-of-fee figure below is compared against it explicitly.

**Label key**
- `[PEER-REVIEWED]` — published in a peer-reviewed journal; I read the source text.
- `[VERIFIED-URL]` — I fetched and read the document at the URL given; not necessarily peer-reviewed.
- `[PRACTITIONER]` — industry research, not peer-reviewed.
- `[BLOG]` — low-quality or unauthored web content; treated as non-evidence.
- `[CLAIM]` — a number reported second-hand that I could **not** verify at the primary source.
- `[REASONING]` — my own arithmetic, built on labelled inputs. Not a sourced fact.

**Method note.** `web_search` and `lite.duckduckgo.com` were both intermittently rate-limited during
this research. PDFs were retrieved with `curl` and text-extracted with `pypdf`; two paywalled-but-open
PDFs were read through the `r.jina.ai` text proxy. Every source below was actually opened and read.
Where I could only obtain an abstract or a citing paper's summary, I say so.

---

## 0. The arithmetic that governs everything else

Before the strategy classes, the cost arithmetic, because it determines which classes are even
eligible.

**General formula `[REASONING]`, built on the Novy-Marx & Velikov rule quoted in §6:**

Let `f` = one-sided notional turnover per rebalance (fraction of the position replaced), `c` = round-trip
cost (0.008 here), `N` = number of rebalances per year.

- Long-only: annual fee drag ≈ `N × f × c`
- Long/short (both legs turn over): annual fee drag ≈ `N × f × c × 2`

**Breakeven condition:** a strategy survives only if its **gross edge per round trip exceeds 0.80% of the
notional traded per round trip.**

**"How many trades per year can I afford?" `[REASONING]`**

At 0.80% per round trip on full account notional:

| Gross annual edge of the strategy | Max full-notional round trips per year before fees consume the edge |
|---|---|
| 2% | 2.5 |
| 5% | 6.25 |
| 10% | 12.5 |
| 20% | 25 |
| 30% | 37.5 |

**Critical caveat `[REASONING]`:** this assumes each trade deploys 100% of account equity. A strategy
that risks only 20% of equity per trade incurs only 20% of that drag — but it also earns its edge on only
20% of the notional. The fee-vs-edge ratio is **per unit of notional traded**, not per unit of account
equity. The binding constraint is therefore: *edge per dollar traded must exceed 0.80% of that dollar.*
This is the correct way to state it, and it is what makes low-turnover classes structurally advantaged.

**Practitioner statement of the same arithmetic `[BLOG]`** — pomegra.io,
<https://pomegra.io/learn/library/track-e-trading-risk/technical-analysis/chapter-14-what-doesnt-work-and-the-data/transaction-costs-and-edge>:
worked example of a 55% win-rate strategy with 1% wins and 0.9% losses → `(0.55 × 1%) + (0.45 × −0.9%) =
0.145%` gross edge; against 20bp of cost the strategy loses `0.055%` per trade; over 100 trades that is
`−5.5%/year`. The same page states "100 trades per year costs 20%" at 0.2% per trade. **I could not verify
this site's cited studies** (it references an "Arnott et al. 2018" hedge-fund study and a "Jank, Kempf,
Kaniel 2022" study with no links); treat the arithmetic as illustrative, the citations as unverified. Note
also that its "20% per year" figure assumes every trade uses the full account notional — the caveat above
applies.

---

## 1. Low-frequency trend following (MA crossover, Donchian, time-series momentum)

### 1.1 The best crypto-specific net-of-fee evidence I found

**Borgards, O. (2021), "Dynamic time series momentum of cryptocurrencies," *The North American Journal
of Economics and Finance* 57:101428.** `[PEER-REVIEWED]`

- Article record (DOI/venue confirmation): <https://ideas.repec.org/a/eee/ecofin/v57y2021ics1062940821000590.html>
- Full text read via a mirror of the Elsevier article PDF: <https://community.portfolio123.com/uploads/short-url/amrMsuqIKzdHcHHyvMud4YNPwZB.pdf>
- Publisher landing page (paywalled): <https://www.sciencedirect.com/science/article/pii/S1062940821000590>

This is the single most useful source in this document, because **it reports gross *and* net returns at a
stated fee, at multiple frequencies**, and because its strategy has very low trade counts.

Sample: 20 cryptocurrencies vs the S&P 500, **1 Jan 2014 – 31 Dec 2019**. Fee assumption: **"trading fees
of 0.2% per trade"** (footnote cites Bitfinex's fee schedule). That is a **0.4% round trip — half of our
0.80% assumption.**

Verified figures from Table 5 (returns in %, over the full 6-year sample; "profit per trade" in %):

| Frequency | Side | Gross profit/trade | Net profit/trade | Trades (6 yrs) | Total return gross | Total return net | Max DD net | Return/DD net |
|---|---|---|---|---|---|---|---|---|
| 1D | Long | 7.248 | 6.848 | 18.25 | 134.477 | **127.177** | −16.519 | 12.144 |
| 1D | Short | 10.581 | 10.181 | 18.05 | 180.702 | **173.482** | −14.806 | 16.366 |
| 1h | Long | 0.996 | 0.596 | 457.85 | 492.052 | 308.912 | −42.322 | 19.413 |
| 1h | Short | 1.002 | 0.602 | 449.95 | 448.198 | 268.217 | −26.755 | 23.355 |
| 5m | Long | 0.093 | −0.307 | 4729.55 | 727.852 | **−1163.970** | −1004.960 | −1.371 |
| 5m | Short | 0.066 | −0.334 | 4543.40 | 647.536 | **−1169.820** | −1025.000 | −1.299 |

Buy-and-hold comparison (Table 5, panel c): **total return 185.959%, max drawdown −90.207%, return/DD
2.094** for the same 20-coin universe over the same window.

Direct quotations I verified in the text:

- "After deducting trading fees, only positive long momentum trades in the 1D frequency are profitable for
  the S&P500, while cryptocurrencies do always generate a positive total net return in the 1D and 1 h
  frequencies."
- "Even after deducting a trading fee of 0.2% per trade, the trading strategy would still be significantly
  profitable for cryptocurrencies in the lower frequencies which is never the case for the S&P500."
- "In the 5 m frequency, the trading fees eat up the mean gross profit per trade of both asset classes so
  that the net profit per trade is always negative."
- "However, it should also be noted that the selection of the observation period and the transaction fees
  have a major impact on the profitability of the momentum trading strategy."
- On concentration risk: "the proportion of the largest winner returns that make up the total gross
  return which we name percentage of breakeven trades. For example, 8.2% (4.9%) of the largest
  cryptocurrency (S&P500) long momentum returns in the 1 h frequency make up the total gross return of
  492.1% (59.4%)."

**Why this matters for a small account — the key structural insight `[REASONING]`:**

The 1D strategy traded only **18.25 times over 6 years ≈ 3 trades/year**. At 0.4% round trip, total fee
drag over the whole sample was `18.25 × 0.400 = 7.30` percentage points, which is exactly the gap between
134.477 gross and 127.177 net. Scaled to **our 0.80% round trip, the drag doubles to ~14.6 points over 6
years ≈ 2.4%/year** — small relative to the gross return. **Low-frequency trend following is the one
active class in this document where a high fee is survivable, because the trade count is tiny.** That
conclusion is robust to the fee assumption; it is *not* robust to the sample period, as Borgards himself
warns.

**Important caveats on Borgards `[REASONING]`:**
1. The fee tested (0.4% round trip) is **half** our assumed 0.80%. Net figures must be re-derived.
2. The 1D net return (127%) was **below buy-and-hold gross (186%)** over this window. Momentum's
   advantage here is drawdown (−16.5% vs −90.2%), not return.
3. It is a "parameter-less dynamic momentum cycle" rule, not a plain MA crossover; results are not
   automatically transferable to a 50/200-day MA system.
4. The 5m result is a clean demonstration that **at high frequency the fee consumes the entire edge**,
   even at only 0.4% round trip.

### 1.2 The canonical TSMOM-in-crypto result (gross only)

**Liu, Y. & Tsyvinski, A., "Risks and Returns of Cryptocurrency," NBER Working Paper No. 24877 (Aug
2018); published as *Review of Financial Studies* 34(6):2689–2727 (2021).** `[VERIFIED-URL]` (NBER working
paper version read in full)

- PDF read: <https://www.nber.org/system/files/working_papers/w24877/w24877.pdf>
- NBER landing page: <https://www.nber.org/papers/w24877>
- Published version (paywalled): <https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024>

**Note:** I read the 2018 NBER working paper, not the 2021 RFS published version. Figures may differ.

Sample: Bitcoin 08/04/2013–05/31/2018, Ethereum from 08/07/2015, plus Ripple.

Verified findings:
- **Strong time-series momentum at daily and weekly horizons.** Table 14: daily own-return coefficient
  `0.06***` (t = 2.96); weekly `0.19***` (3.73), `0.22***` (4.52), `0.21***` (4.26), `0.09*` (1.72).
  R² is 0.00–0.05 — the effect is statistically detectable but explains very little variance.
- Table 15 (weekly quintiles, full sample): **top quintile 11.22%/week, Sharpe 0.45**; bottom quintile
  2.60%/week, Sharpe 0.19; **difference 8.62%/week**.
- Table 16 (sample restricted to 2013 onward): **top quintile 7.18%/week, Sharpe 0.34**; difference
  4.35%/week. *Momentum magnitude roughly halved when the earliest data were excluded.*
- Table 17 (no-lookahead, out-of-sample quintile cutoffs): still "strong momentum effect."
- Bitcoin return characteristics: weekly mean **3.79%**, SD **16.64%**; **Sharpe 0.09 daily, 0.23 weekly,
  0.31 monthly**.
- **No transaction cost analysis of any kind.** I searched the full text for "transaction cost"/"trading
  cost" — the only hits are in the reference list. **These are gross returns with no fee deduction.**

**`[REASONING]`** At 8.62%/week gross difference the fee looks irrelevant; but this is a *weekly-rebalanced
long/short quintile portfolio*. If each week's long and short legs turn over fully, that is `52 × 0.008 × 2
= 83%` of notional per year in fees at our 0.80% round trip. The gross figures cannot be compared to net
without knowing turnover, which the paper does not report. **This is a genuine gap in the literature, not
a gap in my search.**

### 1.3 The honest state of the crypto-momentum literature: fragile and inconclusive

**Grobys, K., Kolari, J.W., Sandretto, D., Shahzad, S.J.H. & Äijö, J. (2025), "Cryptocurrency momentum has
(not) its moments," *Financial Markets and Portfolio Management* 39:443–476.** `[PEER-REVIEWED]`, open
access (CC BY).

- DOI: <https://doi.org/10.1007/s11408-025-00474-9>
- PDF read via text proxy: <https://link.springer.com/content/pdf/10.1007/s11408-025-00474-9.pdf>

Sample: top-30 market-cap coins at each year-end, **weekly rebalancing**, **Jan 2016 – Dec 2023 (416 weekly
observations, 89 unique coins)**, equal-weighted long/short portfolios.

Verified findings:
- **Profits of 1.74%/week from Jan 2016 to Jul 2020 — "only nominally significant at the 10% level."**
- **In the ex-post July 2020 sample: "the average return on cryptocurrency momentum is negative and
  statistically insignificant."**
- **Overall sample: "an insignificant average raw payoff of 0.90% per week."**
- **Severe crashes: "in December 2020 ... cryptocurrency momentum crashed by −255.23%."** And: "one single
  outlier corresponds to **37% of the overall compounded return** of the cryptocurrency momentum
  strategy."
- Excluding that single event: "1.51% per week for the overall sample with a t-statistic of 2.63."
- Risk-managed (volatility-scaled) variants: 1.86%–2.40%/week, "more than 200%" better than plain.
- **Tail risk is irreducible:** power-law exponent α < 3, so "the variance of this strategy is
  statistically undefined" and "traditional statistical methodologies can yield invalid inferences."
  Risk management "does not significantly change the tail risk."
- **Coin-universe churn: "on average, the turnover of coins in the investment opportunity set is 37%
  annually."** Only 8 coins (BTC, ETH, XRP, DOGE, LTC, XMR, XLM and one more) stayed in the top 30 from
  2015 to 2022. **`[REASONING]` This is survivorship/drift risk in the *universe*, independent of trading
  costs.**
- **No transaction costs are applied.** The paper reports raw and risk-adjusted payoffs only.

The paper's own literature review, verified in text, documents how contradictory this field is:

| Study | Sample | Claim |
|---|---|---|
| Grobys & Sapkota (2019) | monthly, 143 coins, 2014–2018 | **no** momentum support |
| Liu et al. (2020) | 2015–2018 | **36% per week** |
| Liu et al. (2022) | weekly, 1,827 coins, 2014–Jul 2020 | **~3% per week** |
| Shen et al. (2020) | weekly, 1,786 coins, 2013–2019 | insignificant **negative** returns |
| Grobys et al. (2025) | weekly, top-30, 2016–2023 | **0.90%/week, insignificant** |

**`[REASONING]`** A claimed edge that ranges from −X% to +36% per week depending on the coin universe is
not an edge a $1,500 account should rely on. The pattern — large payoffs in studies that include
small/illiquid coins, vanishing payoffs in studies restricted to tradable large caps — is the central
finding of this whole document.

### 1.4 A cost-free, daily-rebalanced TSMOM backtest (illustrates the trap)

**Gbadebo, A.D. (2026), "Momentum Trading in Cryptocurrencies: A Comparative Study of Time-Series and
Cross-Sectional Strategies," *Buhalterinės apskaitos teorija ir praktika* 33, Vilnius University Press.**
`[VERIFIED-URL]`, open access. Low-tier venue — treat with caution.

- DOI: <https://doi.org/10.15388/batp.2026.1>
- PDF read: <https://pdfs.semanticscholar.org/6268/ade6dda7434bbf7d71ac6cc0cbb12bf32bc6.pdf>
- Journal copy: <https://www.journals.vu.lt/BATP/en/article/download/44540/42590/138419>

Sample: 8 coins (BTC, ETH, LTC, XRP, BNB, ADA, DOGE, SOL), **1 Jan 2020 – 31 Oct 2025**, EMA-based signals,
**rebalanced DAILY**.

Verified Table 3 results:

| Metric | Time-Series Momentum | Cross-Sectional Momentum |
|---|---|---|
| Mean daily return | 0.000741 | 0.000371 |
| Volatility | 0.026301 | 0.029104 |
| Sharpe ratio (as reported) | 0.028174 | 0.012757 |
| Cumulative return | 3.9125× | 1.9809× |
| Max drawdown | 45.5% | 55.0% |
| Annual (as reported) | **31.96%** | 14.59% |

**The decisive limitation, quoted verbatim from the paper's Limitations section:**
> "The analysis is based on daily data covering 1 January 2020 to 31 October 2025 and **does not
> incorporate transaction costs, slippage, funding rates, or liquidity constraints.** Short-selling
> feasibility is assumed, and **reported performance reflects gross returns.**"

**`[REASONING]` — this is the most important worked example in the document.** The strategy rebalances
**daily**. At 0.80% per round trip:
- at 5% one-sided daily turnover: `365 × 0.05 × 0.008 = 14.6%/year` of fee drag
- at 10%: `29.2%/year`
- at 20%: `58.4%/year`

The reported **31.96% annual gross return is consumed entirely** at ~11% daily turnover, and the paper does
not report turnover. Also note the paper's own "Sharpe Ratio" column is a **daily** Sharpe (0.0282), which
annualises to roughly `0.0282 × √365 ≈ 0.54`, not a headline Sharpe of 0.03. `[REASONING]`

### 1.5 A widely-cited trend-following figure that explicitly excludes costs

**Rozario, E., Holt, S., West, J. & Ng, S. (2020), "A Decade of Evidence of Trend Following Investing in
Cryptocurrencies," arXiv:2009.12155.** `[VERIFIED-URL]` — **preprint, not peer-reviewed**; funded by
Globe, a crypto derivatives exchange (declared in the acknowledgements).

- PDF read: <https://arxiv.org/pdf/2009.12155> · abstract: <https://arxiv.org/abs/2009.12155>

Sample: BTCUSD spot (Bitstamp), **13 Sep 2011 – 12 Dec 2019**, hourly and daily, SMA/EMA/DEMA crossover,
walk-forward parameter selection.

Verified findings:
- **Headline: "Combining walk forward returns from BTCUSD SMA from 2011 - 2019 we achieve a return of
  73700%, which is an annualised return of 255%."**
- **The cost assumption, quoted verbatim: "We assumed negligible transaction fees, bid-offer spread,
  slippage and market impact from trades."**
- Best *in-sample* (full-period, hyper-optimised) Sharpe ratios: SMA 1.0907, EMA 1.3515, DEMA 1.3165.
- **The honest walk-forward numbers are far worse:** "Using recent data slices (2015-2016, 2016-2017,
  2017-2018) we note variable and sub-par performance from all strategies with **Sharpe ratios < 1 and
  negative Sharpe ratios** from SMA and EMA using 2016-2017 and DEMA using 2017-2018 as training data."
- "for all strategies, window sizes show little trend with date with large variations in both long and
  short windows from 200-1000 hrs."
- "Of particular interest to practitioners is the **notable absence of profitable intra-day trend
  following strategies** for BTCUSD spot markets."

**`[REASONING]`** The 255%/year figure is gross, and the authors say so. The gap between the "best
possible" Sharpe (~1.1–1.35) and the walk-forward Sharpe (<1, sometimes negative) is the real result: the
in-sample optimum is not achievable out-of-sample. **Do not cite 255% as a net-of-fee return.**

### 1.6 Class 1 bottom line

| Evidence | Gross | Net of fees | Verdict |
|---|---|---|---|
| Borgards 1D momentum (2014–19, ~3 trades/yr) | 134–181% / 6yr | 127–173% at 0.4% RT; ≈119–165% at 0.8% RT `[REASONING]` | **Survives high fees** — but underperformed buy-and-hold on return; won on drawdown |
| Borgards 5m momentum | 648–728% | **−1164% to −1170%** even at 0.4% RT | **Destroyed by fees** |
| Liu & Tsyvinski weekly quintiles | 8.62%/wk spread | **not reported** | Gross only; turnover unknown |
| Grobys et al. weekly L/S | 0.90%/wk, insignificant | **not applied** | Fragile, crash-prone, α<3 |
| Gbadebo daily TSMOM | 31.96%/yr | **not applied; ~14.6–58%/yr drag `[REASONING]`** | Gross-only; likely negative net |
| Rozario et al. BTC trend | 255%/yr walk-forward | **"negligible" costs assumed** | Gross only; walk-forward Sharpe <1 |

**Verdict on Class 1:** There is real, peer-reviewed evidence of time-series momentum in crypto. The only
source that actually nets out fees (Borgards) finds it survives **only at low frequency and low trade
count**, and only because the trade count is ~3/year. At high frequency the same paper shows fees destroy
it outright. The literature is genuinely inconclusive on magnitude and highly sensitive to coin universe
and sample period.

---

## 2. Buy-and-hold as the benchmark

### 2.1 The central caution: period dependence is not a caveat, it is the whole story

Every figure below is window-specific. There is no stable "crypto buy-and-hold return."

**Verified buy-and-hold figures:**

| Source | Universe & window | Return | Max drawdown |
|---|---|---|---|
| Borgards (2021), Table 5c `[PEER-REVIEWED]` | 20 cryptos, Jan 2014 – Dec 2019 (6 yrs) | **+185.96% total** (≈19%/yr `[REASONING]`) | **−90.21%** |
| Liu & Tsyvinski (2018/2021) `[VERIFIED-URL]` | BTC, Aug 2013 – May 2018 | weekly mean 3.79%, SD 16.64%; Sharpe 0.09/0.23/0.31 (D/W/M) | — |
| Gbadebo (2026) Table 2a `[VERIFIED-URL]` | 8 coins, Jan 2020 – Oct 2025 (daily mean returns) | BTC 0.115%, ETH 0.198%, BNB 0.123%, XRP 0.201%, ADA 0.141%, DOGE 0.028%, SOL 0.234%, LTC 0.111% | — |
| Rozario et al. (2020) `[VERIFIED-URL]` | BTCUSD, Sep 2011 – Dec 2019 | price series used as the trend-following benchmark | — |

**Statistical significance of buy-and-hold, verified in Gbadebo Table 2b** — this is the most useful table
in the document for a small-account decision:

| Coin | t-stat | p-value | 95% CI | Significant? |
|---|---|---|---|---|
| BTC | 1.9679 | 0.0492 | [0.0000, 0.0027] | yes, 5% |
| BNB | 2.2184 | 0.0266 | [0.0002, 0.0039] | yes, 5% |
| ETH | 1.6514 | 0.0988 | [−0.0003, 0.0033] | marginal, 10% |
| SOL | 1.7637 | 0.0779 | [−0.0003, 0.0053] | marginal, 10% |
| XRP | 1.0466 | 0.2954 | [−0.0011, 0.0036] | **no** |
| ADA | 1.2152 | 0.2244 | [−0.0008, 0.0036] | **no** |
| DOGE | 1.3753 | 0.1692 | [−0.0009, 0.0053] | **no** |
| LTC | 0.3653 | 0.7149 | [−0.0016, 0.0023] | **no** |

The paper's own summary: "only Bitcoin and Binance Coin display statistically significant mean returns at
the 5% level, whereas Ethereum and Solana are marginally significant at the 10% level. For the remaining
cryptocurrencies, the confidence intervals include zero."

**`[REASONING]`** Over Jan 2020 – Oct 2025 — a window that *includes* the 2020–2021 bull market — **six of
eight major coins had mean daily returns statistically indistinguishable from zero.** The "crypto always
goes up" premise does not survive a t-test over the most recent six years. A strategy that must beat
buy-and-hold must beat *this*, and buy-and-hold's realized return over a given future window is unknown.

### 2.2 Buy-and-hold's fee profile — the structural advantage

`[REASONING]` Buy-and-hold incurs **one round trip, once**. At 0.80% that is a **0.80% lifetime cost**, and
it is paid at entry, not annually. No active strategy in this document can match that. The entire question
of "can algo trading beat buy-and-hold for a small account" is therefore the question of whether the
strategy's gross edge exceeds `0.80% × (round trips per year)`, **plus** a risk-adjusted margin for the
drawdown profile.

### 2.3 Buy-and-hold caveats

- **Survivorship / universe churn `[PEER-REVIEWED]`:** Grobys et al. (2025) report **37% annual turnover of
  the top-30 coin universe**; only 8 of the top 30 in 2015 were still there in 2022. A backtest that
  buy-and-holds *today's* majors over a past window is contaminated by hindsight.
- **Drawdown `[PEER-REVIEWED]`:** Borgards reports −90.21% max drawdown for a 20-coin buy-and-hold
  portfolio. `[REASONING]` A −90% drawdown on a $1,500 account is a −$1,350 loss; behavioral survival
  through that is a real constraint, not a theoretical one.
- **Period dependence `[REASONING]`:** the same asset class produced ≈19%/yr (2014–2019) and
  near-zero, insignificant mean returns for most coins (2020–2025). Neither figure predicts the next
  window.

---

## 3. Dollar-cost averaging (DCA)

### 3.1 The classic result: lump-sum usually beats DCA

**Vanguard Research (July 2012), "Dollar-cost averaging just means taking risk later," Shtekhman, A.,
Tasopoulos, C. & Wimmer, B.** `[PRACTITIONER]` — not peer-reviewed, but the most-cited study on this
question, and the full text is available.

- PDF read: <https://static.twentyoverten.com/5980d16bbfb1c93238ad9c24/rJpQmY8o7/Dollar-Cost-Averaging-Just-Means-Taking-Risk-Later-Vanguard.pdf>

Method: US$1,000,000 (or local equivalent) either invested immediately (LSI) or moved from cash into the
target portfolio in equal increments over 6–36 months (DCA); both held 10 years; **rolling 10-year
periods**; markets: US (1926–2011), UK (1976–2011), Australia (1984–2011); allocations 100% equity, 60/40,
100% bonds.

Verified figures:

| Market | 12-month DCA: LSI wins | 100% equity | 60/40 | 100% bonds |
|---|---|---|---|---|
| US (1926–2011) | **67%** | 66% | 67% | 65% |
| UK (1976–2011) | **67%** | 68% | 67% | 61% |
| Australia (1984–2011) | **66%** | 62% | 66% | 58% |

- **Magnitude of the advantage:** US 12-month DCA average ending value **$2,395,824** vs LSI
  **$2,450,264** → **LSI 2.3% more**. UK **2.2%** more, Australia **1.3%** more.
- **Longer DCA periods favour LSI more:** "In the United States, for example, LSI outperformed 36-month DCA
  in approximately **90%** of the 10-year spans."
- **Risk-adjusted:** "LSI has provided better returns **and risk-adjusted returns**, on average" (Sharpe
  ratios compared across all 12-month DCA periods).
- **Dispersion is wide** (US, LSI minus DCA, 60/40, 10-yr): 5th percentile **−$203,776**, 25th −$42,819,
  median **+$55,151**, 75th +$151,725, 95th +$309,133. "it is possible for either strategy to underperform
  the other over a given period—potentially by a significant amount."
- **DCA did help in downturns:** "We found that DCA performed better during market downturns, so DCA may be
  a logical alternative for investors who prefer some short-term downside protection."
- **The crucial distinction, quoted verbatim:** "Most popular commentary addresses DCA in terms of
  consistent investments made using current income—i.e., an employee transferring a portion of each
  paycheck into a retirement account. In that case, investable cash becomes available only in relatively
  small amounts over time, **which makes DCA a prudent way to invest (and really the only sound
  alternative** to accumulating that money in cash and then actively trying to time the market at some
  later point). Our research, in contrast, focuses on the strategies for investing an immediately available
  large sum of money. Here, the average performance results have favored lump-sum investing."

### 3.2 Academic backing

**Constantinides, G.M. (1979), "A Note on the Suboptimality of Dollar-Cost Averaging as an Investment
Policy," *Journal of Financial and Quantitative Analysis* 14(2):443–450.** `[PEER-REVIEWED]` —
**partially verified.** I read the abstract at RePEc but **could not read the full text** (JSTOR blocked).

- RePEc record: <https://ideas.repec.org/a/cup/jfinqa/v14y1979i02p443-450_00.html>
- DOI: <https://doi.org/10.2307/2330513> · JSTOR: <https://www.jstor.org/stable/2330513>

Verified from the abstract: the paper opens by quoting Malkiel's claim that "Periodic investments of equal
dollar amounts in common stocks can substantially reduce (but not avoid) the risks of equity investment by
insuring that the entire portfolio of stocks will not be purchased at temporarily inflated prices. The
investor who makes equal dollar investments will buy fewer shares when prices are high and more shares when
prices are low." The paper's title asserts the **suboptimality** of DCA as an investment policy.
**I have not read the derivation — cite the title and the abstract, not a specific result.**

### 3.3 What DCA does and does not fix — for a small crypto account `[REASONING]`

**DCA does NOT reduce fee drag per dollar traded.** This is the key point for this report. Buying $1,500 in
one order costs `1,500 × 0.008 = $12.00` in round-trip fees. Buying $125/month for 12 months costs
`12 × 125 × 0.008 = $12.00` — **identical fee drag**, just spread over a year. If anything, DCA is
*slightly worse*, because a fixed minimum order size and minimum fee floor make small orders
proportionally more expensive. **DCA converts one round trip into N round trips for the same total
capital.**

**DCA DOES reduce timing risk**, which is a genuine and separate benefit: it lowers the variance of the
entry price and the probability of buying the entire position at a local peak. Vanguard's own data
confirms DCA did better in downturns. For a $1,000–2,000 CAD account where the whole balance is a single
entry decision, this risk reduction is real.

**Net assessment:** DCA is a **risk-management choice with a small expected-return cost** (Vanguard: LSI
ahead 2/3 of the time by ~1.3–2.3% of terminal wealth over 10 years), **not a fee-reduction technique.**
Any claim that DCA improves net returns in a high-fee environment is not supported by the evidence found.

---

## 4. Periodic rebalancing (fixed-weight BTC/ETH/SOL/XRP, monthly/quarterly)

This is the class where I found the strongest, most directly applicable peer-reviewed evidence — and it
partly **contradicts** the popular "rebalancing premium" story.

### 4.1 The theory: the diversification return and its size

**Willenbrock, S. (2011), "Diversification Return, Portfolio Rebalancing, and the Commodity Return Puzzle,"
*Financial Analysts Journal* 67(4):42–49.** `[PEER-REVIEWED]`

- arXiv copy read: <https://arxiv.org/pdf/1109.1256> · abstract: <https://arxiv.org/abs/1109.1256>

Verified formulas (Eq. 6, 7, 10):
- `g_p ≈ Σᵢ wᵢ ( gᵢ + ½(σᵢ² − σᵢₚ) )`
- **`Diversification Return ≈ ½ Σᵢ wᵢ(σᵢ² − σᵢₚ)`**, equivalently **`≈ ½( Σᵢ wᵢσᵢ² − σ²_p )`**
- "The diversification return of an asset is thus approximately half the difference between the asset's
  variance and the asset's covariance with the portfolio."
- **"it is essential to maintain (nearly) constant weights in order to obtain a diversification return."**

`[REASONING]` Note what this formula says: the diversification return is a function of **variance
reduction**, and it is **independent of fees**. It tells you nothing about whether rebalancing beats
buy-and-hold net of costs. For that, see below.

### 4.2 The decisive source: rebalancing *with* transaction costs

**El Bernoussi, R. & Rockinger, M. (2023), "Rebalancing with transaction costs: theory, simulations, and
actual data," *Financial Markets and Portfolio Management* 37(2):121–160.** `[PEER-REVIEWED]`, open access
(CC BY).

- DOI: <https://doi.org/10.1007/s11408-022-00419-6>
- PDF read via text proxy (publisher PDF is open access): <https://link.springer.com/content/pdf/10.1007/s11408-022-00419-6.pdf>

This is the most directly applicable peer-reviewed paper for this strategy class.

**Theory (verified):**
- Rebalancing alpha, Eq. (3): `D = −a₁a₂W₀ (r₁₁ − r₂₁)(r₁₂ − r₂₂)` — the fixed-weight (FW) strategy beats
  buy-and-hold (BH) only when the **cross-sectional spread differentials have a negative product**, i.e.
  when relative performance **mean-reverts**.
- **Corollary 1 (verified):** "As long as ρ₁,₂ > −(SR)², meaning that the autocorrelation is larger than
  minus the square of the Sharpe ratio, then `E[W_FW] < E[W_BH]`." **BH wins unless autocorrelation is
  meaningfully negative.**
- **Magnitude of the rebalancing alpha, quoted verbatim:** "assume an equally weighted portfolio, and let
  W₀ = 100. Assume asset one is a stock with a return in one month of 3% and of −3% in the next month.
  Assume that the second asset is a bond with a return of 0. Then D = 0.25 ∗ 0.03² = 0.000225. If this game
  goes on for an entire year, **the final difference is of the magnitude of 1.35bp, a very small difference
  in practice.**"

**Simulations (verified):** two assets, μ = 5%, σ = 25%, transaction cost 2% each. "We notice that the FW
strategy has the larger SR only when assets move strongly in opposite directions and are mean-reverting...
What this simulation allows to show is that **the parameter values need to be rather extreme for the FW
strategy to have higher SR than the BH strategy**."

**Actual data (verified) — the headline numbers.** A Swiss-pension-fund-style portfolio (risk-free, bonds,
several equity indices, commodities, real estate), **Jan 1999 – Jun 2021**, **rebalanced monthly**,
starting at 100:

| Strategy | Terminal wealth (Jun 2021) |
|---|---|
| Buy-and-hold | **128.40** |
| Fixed-weight, no transaction cost | 135.90 |
| Fixed-weight, **0.5% transaction cost** | **132.2** |
| Fixed-weight, **1% transaction cost** | **128.6** (≈ tie with BH) |
| Fixed-weight, **2% transaction cost** | **121.8** (BH wins) |

Quoted verbatim: "We notice that it is only with a relatively high transaction cost of 2% for each asset
that the fixed-weight strategy no longer dominates the buy-and-hold strategy. In practice, the level of
transaction cost is in the range of 0.5%, and therefore, a fixed-weight strategy is interesting."

**Table 9 (verified)** — annualized Sharpe ratios across allocations:
- Allocation 1: BH 0.24 → FW 0.27 (0% TC) → **0.25 (0.5% TC)** → 0.24 (1% TC)
- Allocation 5: BH 0.40 → FW 0.50 (0% TC) → **0.47 (0.5% TC)** → 0.45 (1% TC)

**Statistical significance (verified, and this is the crux):**
- "From a purely statistical point of view, it turns out that **the null hypothesis of the SR of BH being
  equal to the SR of FW cannot be rejected in the long-run**."
- "We also performed bootstrap tests attempting to reject SR(FW)=SR(BH) but **we were not successful**."
- The authors still prefer FW: "Even though the allocations are from a statistical point of view not
  different, most pension fund managers when confronted with this diagram would prefer a FW strategy."

**Conclusion (verified):** "Generally, if a portfolio manager managing a well-diversified portfolio faces
transaction costs of less than 2% and if she anticipates a future market with mean reversion, then she
should rebalance her portfolio."

**A nuance that favours crypto `[PEER-REVIEWED]` + `[REASONING]`:** "when assets move in the same direction,
little rebalancing will be required" → lower turnover and lower costs. Crypto majors are **highly
positively correlated** (Gbadebo: cross-sectional momentum is weakened by "high correlations among major
cryptocurrencies"). `[REASONING]` This means a BTC/ETH/SOL/XRP fixed-weight portfolio generates **less
drift-driven turnover** than an uncorrelated multi-asset portfolio — a genuine structural advantage for
crypto rebalancing over, say, stocks/bonds/commodities.

### 4.3 Mapping our 0.80% round trip onto this evidence `[REASONING]`

El Bernoussi & Rockinger's cost parameter is **per asset traded**, and their breakpoints are 0.5% (FW wins
clearly), ~1% (a wash), 2% (BH wins). **Our assumed 0.80% maker round trip sits between the "wins clearly"
and "wash" points.**

Therefore, for a monthly-rebalanced fixed-weight crypto portfolio at 0.80% per round trip, the evidence
supports this conclusion: **rebalancing is approximately neutral to slightly positive versus buy-and-hold
in expected return, with the benefit being a modest risk/drawdown reduction rather than an alpha.** The
Sharpe improvement is real in the data but **not statistically significant** in the only peer-reviewed test
I found.

**Turnover `[REASONING]`:** a monthly-rebalanced fixed-weight portfolio trades **only the drift**, not the
whole book. If drift produces 5–15% one-sided turnover per month, annual fee drag is
`12 × (0.05 to 0.15) × 0.008 = 0.48% to 1.44%/year`. That is **roughly 10–30× cheaper than a
daily-rebalanced active strategy** and is the main reason this class is attractive at high fee levels.

### 4.4 Crypto-specific rebalancing studies

**Sornmayura, S., Sakolvieng, N. & Numgaroonaroonroj, K. (2024), "Optimizing Cryptocurrency Portfolios: A
Comparative Study of Rebalancing Strategies," *GATR Journal of Finance and Banking Review* 8(4):1–16.**
`[VERIFIED-URL]`, open access. **Low-tier publisher — treat with caution.**

- DOI: <https://doi.org/10.35609/jfbr.2024.8.4(1)>
- PDF read: <http://gatrenterprise.com/GATRJournals/JFBR/pdf_files/JFBR-Vol-8(4)/1.Sutta%20Sornmayura.pdf>
- RePEc record: <https://ideas.repec.org/p/gtr/gatrjs/jfbr220.html>

Method: simulation of **10,000 portfolios of 7 assets** (ETH, BTC, USDT, LTC, SOL, DOGE, MATIC);
time-based rebalancing (daily/weekly/monthly) and threshold-based (5%/10%/15%); Sharpe ratio vs passive
buy-and-hold.

Verified mean Sharpe ratios (**note: these are DAILY Sharpe ratios, not annualized**):

| Strategy | Mean Sharpe | SD |
|---|---|---|
| Threshold 5% | **0.0715** | 0.00480 |
| Threshold 10% | 0.0700 | 0.00495 |
| Weekly (7d) | 0.0695 | 0.00500 |
| Monthly (30d) | 0.0690 | 0.00505 |
| **Buy-and-hold** | **0.06856** | 0.00509 |
| Threshold 15% | 0.0685 | 0.00510 |
| Daily (1d) | higher (highest) | — |

Verified significance: statistically significant differences vs buy-and-hold for **daily rebalancing
(t ≈ 2.82, p ≈ 0.005)** and the **5% and 10% thresholds**. **NOT significant** for weekly, monthly, or the
15% threshold.

**Two critical limitations `[REASONING]`:**
1. **No transaction costs are modelled.** The paper states the elevated transaction costs of frequent
   rebalancing "need careful consideration," that "the overall gain from the daily rebalancing approach
   would be reliant on the equilibrium between augmented returns and amplified costs," and recommends
   future research "consider the transaction costs and tax implications."
2. **The economically significant-looking strategies are exactly the ones most damaged by fees.** The
   *only* strategies that beat buy-and-hold significantly are **daily rebalancing** and **5%/10%
   thresholds** — the highest-turnover options. The fee-neutral options (monthly, 15% threshold) are
   statistically indistinguishable from buy-and-hold. **`[REASONING]` At 0.80% per round trip, the
   statistically-significant results are the ones most likely to be destroyed, and the survivors are the
   ones with no measurable edge.** Also note the monthly-vs-BH difference is 0.0690 vs 0.06856 = **0.0004
   in daily Sharpe** — economically negligible and well inside the 0.005 SD.

**QuantPedia (Dec 2021), "Estimating Rebalancing Premium in Cryptocurrencies."** `[PRACTITIONER]` — the
underlying study is SSRN 3982120, which I **could not read** (SSRN abstract page returns HTTP 403; the
`Delivery.cfm` PDF link returned HTML).

- Article read: <https://quantpedia.com/estimating-rebalancing-premium-in-cryptocurrencies/>
- Unread primary: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3982120>

Verified from the article text: portfolio of **27 cryptocurrencies, 31.12.2018 – 29.10.2021**; "both the
daily and monthly rebalanced portfolios outperformed the Market Cap weighted benchmark"; "there is a
significant rebalancing premium in cryptocurrencies"; 95% IEI + 5% crypto strategies 5 and 7 had "a Sharpe
ratio above 2."

**However:** all the performance **tables in this article are images**, so **no numeric Sharpe/return
figures could be extracted or verified.** The article also concedes the key fragility: "all of this works
because there is no outlier within the cryptocurrencies... If there was an outlier, the rebalancing might
not be profitable" — illustrated with the 2010 commodity counter-example. **No transaction cost analysis is
presented.** Treat the qualitative claim as `[PRACTITIONER]` and the numbers as **unverified**.

### 4.5 Class 4 bottom line

| Question | Verified answer | Source |
|---|---|---|
| Does rebalancing alpha exist? | Yes, when spreads mean-revert; `D = −a₁a₂W₀(r₁₁−r₂₁)(r₁₂−r₂₂)` | El Bernoussi & Rockinger (2023) `[PEER-REVIEWED]` |
| How big is it? | **~1.35bp/year** in the paper's own illustration | same |
| Net of costs? | FW wins at 0.5% TC; **wash at ~1% TC**; BH wins at 2% TC | same |
| Statistically significant? | **No** — cannot reject SR(FW) = SR(BH); bootstrap tests failed | same |
| Crypto-specific, monthly? | **Not significantly different from buy-and-hold** | Sornmayura et al. (2024) |
| Crypto-specific, daily/5% threshold? | Significantly better — but highest turnover, no costs modelled | same |
| Turnover vs active trading | **Much lower** (~0.48–1.44%/yr drag at 0.80% RT) | `[REASONING]` |

**Verdict on Class 4:** This is the **most fee-viable active strategy class** in this document. Its
advantage over buy-and-hold is small, statistically insignificant, and primarily a **risk/drawdown**
benefit rather than a return benefit. At 0.80% round trip, **monthly** rebalancing is defensible; **daily**
rebalancing is not, despite the crypto study showing daily rebalancing had the highest Sharpe — because
that study ignored costs.

---

## 5. Mean reversion / range trading on daily candles

### 5.1 The strongest direct evidence: a measured edge that is too small to clear fees

**Kitron, N.A. & Wengrowicz, J.M. (Aug 2026), "Short-horizon mean reversion in cryptocurrency markets: a
matched cross-market measurement," arXiv:2608.21888.** `[VERIFIED-URL]` — **preprint, not peer-reviewed**;
independent researchers. But it is the **only** source I found that measures a crypto mean-reversion edge
*and* prices it against explicit fees. That makes it uniquely valuable here.

- PDF read: <https://arxiv.org/pdf/2608.21888>

Sample: **15-minute** bars, **183 Binance pairs** vs **187 US stocks/ETFs**, one matched strictly
out-of-sample walk-forward protocol, frozen six-month holdout, exact permutation null.

Verified findings:
- **"90% of 183 Binance pairs carry significant directional reversal against 2.7% of 187 US stocks and
  ETFs."** The signal "lives in signs, not magnitudes."
- **The cost comparison — the decisive result:** "The gross edge peaks near **1.3bp per trade against a
  5bp round-trip cost**: large enough to detect, too small to clear benchmark spot capture costs."
- "the gross edge per trade stays below the shaded spot round-trip cost band throughout, peaking near
  1.3bp against a 5bp cheapest band; the 10–20bp taker band lies above the axis range."
- **"not one of the 183 crypto pairs clears even the 5bp maker band at any threshold, the median pair earns
  0.46bp per trade at τ = 0.02 where it trades at all against zero for the median stock, and moving to
  5-minute bars makes matters worse rather than better (0.15bp), because higher frequency shrinks each
  opportunity faster than it shrinks costs."**
- "Thresholding cannot rescue it, because trading fewer, better bars shrinks the opportunity count faster
  than it grows the edge."
- **"Explicit fees, not the quoted spread, are what bind here: top-of-book on the focal Binance pairs is of
  order a tick, well inside the edge, so a maker who never crosses still pays the fee schedule."**
- Cost bands used: "**≈5bp at maker fees and 10–20bp at taker fees**, bracketing published retail and
  mid-tier schedules on the major venues over the sample."
- Mechanism: the reversal "concentrates after moves driven by aggressive taker flow and grows with flow
  intensity" — consistent with compensated liquidity provision.

**`[REASONING]` This is the single cleanest quantitative result in this document.** At a **5bp** maker round
trip — **16× cheaper than our assumed 0.80% (80bp)** — the entire cross-section of 183 crypto pairs fails to
clear costs. At **80bp**, the measured 1.3bp edge is roughly **60× too small**. And note the direction of
the frequency effect: "moving to 5-minute bars makes matters worse rather than better (0.15bp)."
**Higher frequency makes the net result worse, not better, at any fixed fee level.**

### 5.2 Peer-reviewed crypto reversal evidence: the edge is in illiquid coins

**Zaremba, A., Bilgin, M.H., Long, H., Mercik, A. & Szczygielski, J.J. (2021), "Up or down? Short-term
reversal, momentum, and liquidity effects in cryptocurrency markets," *International Review of Financial
Analysis* 78:101908.** `[PEER-REVIEWED]`, open access (CC BY).

- DOI: <https://doi.org/10.1016/j.irfa.2021.101908>
- Open-access PDF read: <https://earsiv.medeniyet.edu.tr/bitstreams/3e37aa89-3fde-4d77-9ec8-605e846962e6/download>

Sample: **daily prices of more than 3,600 coins.**

Verified findings:
- "we document that the cryptocurrencies with **low last day's return significantly outperform** their
  counterparts with high last day's return" — a daily reversal.
- **The reversal is a liquidity phenomenon, and this is the crux:** "the daily reversals result from the
  **illiquidity of the vast majority of traded cryptocurrencies**. In consequence, the pattern is
  cross-sectionally dependent on liquidity, and **the handful of largest and most tradeable coins exhibit
  daily momentum rather than a reversal.**"
- Bivariate sorts by Amihud ILLIQ (liquid = lowest 2%, illiquid = remaining 98%):
  - **Illiquid (98%) — Panel A:** "strong daily reversal pattern... high (in absolute terms) negative
    returns associated with p-values close to zero," robust across 1-, 3- and 8-factor models.
  - **Most liquid (top 2%) — Panel B.1 (value-weighted):** "the quintile of assets with the highest LRET
    outperforms the assets with the lowest LRET by **0.31% per month**... The eight-factor model alpha on
    the long-short portfolio equals **0.31%**." Panel B.2 (equal-weighted): **0.18% per month**, 8-factor
    alpha **0.20%**.
- Table 7 (value-weighted, Panel A.1, small coins): low-minus-high = **3.84% per month** (highly
  significant) — but these are small/illiquid coins.

**`[REASONING]` Two devastating implications for a small account:**
1. **The big reversal edge (3.84%/month) is in illiquid coins** — precisely where a $1,000–2,000 CAD order
   pays the widest spreads and the worst slippage. The paper explicitly attributes the effect to
   illiquidity, so the edge and the cost are the *same phenomenon*; you cannot capture the one without
   paying the other.
2. **In the liquid majors (BTC/ETH) the effect inverts to momentum, and it is tiny:** 0.31%/month gross for
   a long-short portfolio ≈ **3.7%/year gross** `[REASONING]`. A **daily-rebalanced** long-short strategy
   at 0.80% round trip would pay `365 × f × 0.008 × 2` — at even 2% daily one-sided turnover that is
   **11.7%/year**, more than 3× the entire gross edge.

**No transaction cost analysis in this paper.** I verified that the phrase "positive and significant after
controlling for transaction costs" appears in the paper's *literature review table* as a description of
**Tzouvanas et al. (2020)**, not as the authors' own result.

### 5.3 `[CLAIM]` — an implausible second-hand figure

Zaremba et al.'s literature table records, for **Tzouvanas, Kizys & Tsend-Ayush (2020)** (12 coins, Dec
2015 – Jan 2019): "7/7 long-short strategy is the most profitable, with **weekly return of 19.396%
(32.004%) for 12 (6) cryptocurrencies. Returns remain positive and significant after controlling for
transaction costs.**"

`[CLAIM]` — I did **not** open Tzouvanas et al. (2020). A ~19–32% **weekly** return on a 6–12 coin
long-short strategy is not credible on its face, and it is directly contradicted by the peer-reviewed
evidence in §1.3 (Grobys et al.: 0.90%/week, insignificant) and §5.2 (liquid coins show only 0.31%/month).
**Do not cite this figure. It is listed here only to document that implausible claims circulate in this
literature and get repeated in peer-reviewed literature tables.**

### 5.4 Related verified context

- **Borgards (2021)** `[PEER-REVIEWED]`: "As opposed to mean reversion trading strategies, where the
  counter-reaction of an overreaction is traded, momentum trading strategies have less winning trades but
  higher returns per trade." `[REASONING]` Mean reversion has *more* winning trades but a *lower* edge per
  trade — which is exactly the wrong payoff profile when there is a fixed 0.80% cost per round trip.
- **Grobys et al. (2025)** `[PEER-REVIEWED]` cite Borgards & Czudaj (2020) as showing "persistent price
  overreactions occurred for twelve cryptocurrencies" — evidence that overreaction exists, without a
  net-of-cost result.
- **Begušić, S. & Kostanjčar, Z. (2019), "Momentum and liquidity in cryptocurrencies," arXiv:1904.00890**
  `[VERIFIED-URL]` — preprint. Jan 2015 – Jan 2019, 711 coins meeting inclusion criteria. Finds "a strong
  momentum effect in the most liquid cryptocurrencies, which supports the theories of investor herding
  behavior," and proposes "illiquid losers and liquid winners" long-only strategies with improved
  risk-adjusted performance vs a market-cap-weighted portfolio. `[REASONING]` Consistent with Zaremba et
  al.: the sign of short-horizon predictability flips with liquidity. **No transaction cost analysis.** I
  read the abstract and introduction only.

### 5.5 Class 5 bottom line

| Evidence | Edge measured | Fee level tested | Net result |
|---|---|---|---|
| Kitron & Wengrowicz (2026), 15-min, 183 pairs `[VERIFIED-URL]` preprint | **max 1.3bp/trade** | **5bp** maker RT | **Fails everywhere**; median 0.46bp |
| Zaremba et al. (2021), daily, top-2% liquid coins `[PEER-REVIEWED]` | **0.31%/month** (=3.7%/yr `[REASONING]`) | none applied | Daily rebalancing at 0.80% RT costs ~11.7%/yr at 2% turnover `[REASONING]` |
| Zaremba et al. (2021), daily, illiquid 98% `[PEER-REVIEWED]` | 3.84%/month VW | none applied | Edge and cost are the same phenomenon (illiquidity) |
| Tzouvanas et al. (2020) `[CLAIM]` | 19.4%/week | claimed yes | **Primary not verified; implausible** |

**Verdict on Class 5:** Mean reversion is the **worst-hit** class by a high fee, exactly as the brief
anticipated, and the evidence is unusually clean about it. The only study that prices a crypto
mean-reversion edge against real fees finds it fails by a factor of ~4 even at 5bp round-trip costs. At
0.80% it is not close. The peer-reviewed daily-horizon evidence confirms the edge lives in illiquid coins,
where a small account cannot capture it without paying a wider spread than the edge. **Range trading on
daily candles in liquid crypto majors at 0.80% round trip is not supported by any evidence I found.**

---

## 6. Turnover and the destruction of edge by fees

### 6.1 The definitive peer-reviewed quantification

**Novy-Marx, R. & Velikov, M. (2016), "A Taxonomy of Anomalies and Their Trading Costs," *Review of
Financial Studies* 29(1):104–147.** `[PEER-REVIEWED]`

- NBER Working Paper 20721 PDF read (Dec 2014 version): <https://www.nber.org/system/files/working_papers/w20721/w20721.pdf>
- NBER record: <https://www.nber.org/papers/w20721> · publisher: <https://academic.oup.com/rfs/article/29/1/104/1844518>

**Note:** I read the NBER working paper, not the final RFS version.

**The cost-drag rule of thumb, quoted verbatim — this is the most transferable formula I found:**
> "Round trip transaction costs for typical value-weighted strategies average in excess of 50 bps... **Transaction costs consequently generally reduce realized spreads by more than 1% of the monthly one-sided turnover, i.e., if the long side of a strategy turns over 20% per month, the realized long/short spread will be at least 20 bps per month lower than the gross spread, and the statistical significance of the spread will be reduced proportionately.** Transaction costs for equal-weighted strategies are generally **two to three times as high**, and often less profitable to actually implement."

**The headline threshold finding, quoted verbatim:**
> "While many of the strategies that we study remain significantly profitable after accounting for transaction costs, **only two of the strategies that have more than 50% one-sided monthly turnover have significant net spreads**, even when these strategies are designed with trading costs mitigation in mind."

And from the abstract: "**Most of the anomalies that we consider with one-sided monthly turnover lower than 50% continue to generate statistically significant net spreads**, at least when designed to mitigate transaction costs. **Few of the strategies with higher turnover do.**"

**Verified figures from Table 3 (value-weighted, decile sorts, US equities):**

| Turnover group | Example anomaly | Gross return (%/mo) | One-sided turnover (%/mo) | T-costs (%/mo) | Net return (%/mo) | Cost as % of gross |
|---|---|---|---|---|---|---|
| **Low** (annual rebal.) | Size | 0.33 | 1.23 | 0.04 | 0.28 | 12% |
| | Value | 0.47 | 2.91 | 0.05 | 0.42 | 11% |
| | Piotroski F-score | 0.20 | 7.24 | 0.11 | 0.09 | 55% |
| **Mid** (monthly) | Net Issuance | 0.57 | 14.36 | 0.20 | 0.37 | 35% |
| | **Momentum** | **1.33** | **34.52** | **0.65** | **0.68** | **49%** |
| | ValMomProf | 1.43 | 26.81 | 0.43 | 0.99 | 30% |
| | PEAD (CAR3) | 0.91 | 34.69 | 0.57 | 0.34 | 63% |
| **High** (monthly, ~90% TO) | Industry Momentum | 0.93 | 90.13 | 1.22 | **−0.29** | **131%** |
| | Short-run Reversals | 0.37 | 90.87 | 1.65 | **−1.28** | **446%** |
| | Industry Relative Reversals | 0.98 | 90.28 | 1.78 | **−0.80** | **182%** |
| | High-frequency Combo | 1.61 | 91.04 | 1.45 | 0.16 | 90% |

Verified narrative: "The cost of trading the high-turnover strategies, at least when designed with complete
disregard for trading costs, **always exceeds 1% per month**." And: "Given that accounting for the
effective bid-ask spread alone eradicates the profits from all but two of these strategies, we contend that
there are significant **barriers to arbitrage** among the high-turnover strategies."

**The limits-to-arbitrage framing, quoted verbatim:** "these so called anomalies do not test market
efficiency if they should not attract arbitrage capital because they are not actually profitable to trade."
`[REASONING]` This is the Grossman–Stiglitz-style reasoning the brief asked for: an apparent edge that
cannot pay the cost of exploiting it is not a tradable edge, and its persistence is *evidence of the cost
barrier*, not evidence of opportunity.

### 6.2 Translating the rule to our 0.80% crypto fee `[REASONING]`

Novy-Marx & Velikov calibrated to **>50bp round trip** on US equities. **Our crypto assumption is 80bp —
1.6× higher.** The rule scales linearly, so:

**Annual fee drag ≈ `N_rebalances × f × 0.008`** (long-only), `× 2` for long/short.

| Strategy profile | One-sided turnover per rebalance | Rebalances/yr | Annual fee drag @ 0.80% RT |
|---|---|---|---|
| Monthly fixed-weight rebalance (only drift traded) | 5% | 12 | **0.48%** |
| Monthly fixed-weight rebalance | 15% | 12 | **1.44%** |
| Monthly active rotation (full book) | 100% | 12 | **9.6%** |
| Weekly long/short momentum, 30% turnover/leg | 30% | 52 | **25.0%** |
| Weekly long/short momentum, full re-formation | 100% | 52 | **83.2%** |
| Daily TSMOM, 5% turnover | 5% | 365 | **14.6%** |
| Daily TSMOM, 10% turnover | 10% | 365 | **29.2%** |
| Daily long/short, 2% turnover/leg | 2% | 365 | **11.7%** |
| 15-min mean reversion (Kitron & Wengrowicz) | — | — | Edge is 1.3bp vs 80bp cost = **fails ~60×** |

**Cross-checking against the peer-reviewed crypto evidence:**

- **Gbadebo's daily-rebalanced TSMOM** reported **31.96% gross annual** return. `[REASONING]` At the
  10%-daily-turnover line, fee drag is **29.2%/year** — the gross edge is essentially exactly consumed. At
  20% turnover the strategy is deeply negative. **This is why the absence of a cost analysis in that paper
  is not a minor omission; it is the difference between a 32% return and a loss.**
- **Grobys et al.'s weekly long/short momentum** averaged 0.90%/week gross = **46.8%/year** `[REASONING]`
  — but that average was **statistically insignificant** and included a **−255.23% month**. At full weekly
  re-formation the fee drag is **83%/year**, more than the entire gross payoff. The strategy is not
  viable at 0.80% round trip even taking the gross average at face value.
- **Borgards' 1D momentum** traded ~3×/year. Fee drag ≈ **2.4%/year** `[REASONING]`. **This is the only
  active crypto strategy in this document whose fee drag is small relative to its measured gross edge.**

### 6.3 `[BLOG]` practitioner statements (recorded, not relied upon)

- pomegra.io (URL above): "Costs compound with frequency. If a single trade costs 0.2%, one trade per year
  costs 0.2% of the account. 10 trades per year costs 2%. 100 trades per year costs 20%." Also: "your edge
  should be at least **2–3× your transaction costs**." Its cited studies are **unverified**.
- flytradr.com, <https://www.flytradr.com/blog/transaction-costs-fees-spreads-latency-approximation>:
  "A strategy that trades 50 times per year can often survive modest costs. A strategy that trades 500
  times per year needs a much larger edge." `[BLOG]` — consistent with the peer-reviewed arithmetic above,
  but I did not verify any numbers on this page.

### 6.4 Class 6 bottom line

The peer-reviewed evidence is unambiguous and it maps directly onto crypto:

1. **Fee drag is linear in turnover.** `drag ≈ turnover × round-trip cost`.
2. **The empirical threshold is ~50% one-sided monthly turnover.** Below it, most anomalies survive net
   of costs; above it, almost none do (Novy-Marx & Velikov, RFS 2016).
3. **At 80bp round trip, crypto's threshold is lower than US equities' ~50bp.** `[REASONING]` Scaling
   proportionally, the survivable one-sided monthly turnover is roughly **30% instead of 50%**.
4. **Real, published anomaly returns get cut roughly in half by costs even at 50bp** — momentum: 1.33%/mo
   gross → 0.68%/mo net (−49%, cost 0.65%/mo at >50bp round trip). Scaling that cost linearly to our 80bp
   gives `0.65 × 80/50 = 1.04%/mo`, leaving **0.29%/mo net** — a further 56% cut `[REASONING]`.
5. **High-turnover anomalies go outright negative:** costs exceeded gross spreads for 5 of 7 high-turnover
   anomalies, by 1.3× to 4.5×.

---

## 7. Synthesis: ranking the six classes for a $1,000–2,000 CAD account at 0.80% round trip

| Rank | Class | Annual fee drag `[REASONING]` | Best verified net-of-fee evidence | Assessment |
|---|---|---|---|---|
| 1 | **Buy-and-hold** | 0.80% once, ever | n/a (it *is* the benchmark) | Unbeatable on cost; −90% drawdowns; recent 6-yr means mostly insignificant |
| 2 | **Monthly/quarterly rebalancing** | 0.48–1.44% | El Bernoussi & Rockinger (2023): FW ≈ BH at ~1% TC; **not statistically distinguishable** | Fee-viable. Small, insignificant return edge; genuine risk reduction |
| 3 | **Low-frequency trend following (~3 trades/yr)** | ~2.4% | Borgards (2021): 127–173% net over 6 yrs at 0.4% RT | Fee-viable. Only active class with real net-of-fee crypto evidence. Sample-period fragile |
| 4 | **DCA** | Same as lump sum per dollar | Vanguard (2012): LSI wins 2/3 of the time; DCA helps in downturns | Not a fee strategy — a timing-risk strategy |
| 5 | **Weekly/monthly momentum rotation** | 9.6–83% | Grobys et al. (2025): 0.90%/wk **insignificant**, −255% crash month, α<3 | Fee-infeasible. Literature fundamentally contradictory |
| 6 | **Daily mean reversion / range trading** | 11.7%+ | Kitron & Wengrowicz (2026): max 1.3bp edge vs 5bp cost | Fee-infeasible by ~60× at our fee. Worst-hit class |

**The single most important finding of this research:** the only crypto strategy class with **peer-reviewed,
net-of-fee, positive results at a low trade count** is **low-frequency trend following** (Borgards 2021,
~3 trades/year). Everything that trades more frequently than roughly monthly is either demonstrated to
fail net of fees, or has never been tested net of fees at all — and the arithmetic in §6 says it would
fail.

---

## COULD NOT VERIFY

Listed explicitly, because the gaps matter as much as the findings.

1. **SSRN 3982120, "Rebalancing Premium in Cryptocurrencies" (the primary source behind QuantPedia's
   article).** SSRN abstract pages return **HTTP 403**; the `Delivery.cfm` PDF URL returned an HTML page,
   not a PDF. **I could not read the primary source or verify any of its numbers.** The QuantPedia
   restatement is labelled `[PRACTITIONER]` and its performance tables are images. **All numeric claims
   about the 27-crypto rebalancing premium are unverified.**

2. **Constantinides (1979), JFQA 14(2):443–450.** Read only the abstract (via RePEc). **JSTOR blocked the
   full text.** The paper's *conclusion* (DCA is suboptimal) is supported by its title and abstract; the
   *derivation and any specific numeric result are unread.*

3. **Liu & Tsyvinski — the published RFS 2021 version.** I read the **2018 NBER working paper** only. The
   published version may report different magnitudes. **Also: no turnover figure is reported anywhere in
   the version I read**, so the 8.62%/week gross momentum spread **cannot be converted to a net figure.**

4. **Tzouvanas, Kizys & Tsend-Ayush (2020)** — the "19.396% weekly return, significant after transaction
   costs" claim. Reported only in Zaremba et al.'s literature-review table. **Primary source not opened.**
   Labelled `[CLAIM]` and flagged as implausible.

5. **A crypto-specific net-of-fee momentum study with reported turnover.** I searched for the
   "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market: A Comprehensive Analysis under
   Realistic Assumptions" paper (attributed to the *Journal of Financial Markets*, 2024). The AUT/ACFR
   working-paper PDF returned **HTTP 403**; the only accessible copies were a ResearchGate landing page and
   a Scribd upload, **neither of which I could read.** **This is the single most important unverified
   source for Class 1** — its abstract claims it accounts for transaction costs and daily price
   fluctuations and finds many momentum portfolios earn negative profits. **I could not verify that.**
   Search-result summaries of it are `[CLAIM]` only.

6. **Barroso & Santa-Clara (2015) risk-managed momentum, and the Finance Research Letters 2025 crypto
   risk-managed momentum paper** (reported to lift average weekly returns from 3.18% to 3.47% with
   transaction-cost robustness checks). **Not opened.** Springer/ScienceDirect PDF access was blocked; only
   the abstract was seen via a search result. `[CLAIM]`.

7. **Sharpe (1991) "The Arithmetic of Active Management" and Grossman & Stiglitz (1980).** **Not fetched.**
   The Grossman–Stiglitz-style reasoning in §6.1 is supported by the **verified Novy-Marx & Velikov
   quotation**, not by the original papers. **Do not attribute the argument to the originals on the basis
   of this document.**

8. **Any Canadian- or Kraken-specific fee schedule.** The brief supplied the 0.40%/side assumption; I did
   **not** verify it against a live fee schedule. Minimum order sizes, withdrawal fees, on-chain network
   fees, and small-order spread widening — all of which bear disproportionately on a $1,000–2,000 CAD
   account — are **entirely unaddressed** in this document.

9. **No crypto-specific study measuring "rebalancing premium" *net of a stated fee* was found.** El
   Bernoussi & Rockinger is equities/bonds/commodities/real estate. Sornmayura et al. is crypto but
   cost-free. **The crypto rebalancing-net-of-fees question is genuinely unanswered in the literature I
   could reach.**

10. **joreim (2026) TSMOM paper** — <https://joirem.com/wp-content/uploads/journal/published_paper/volume-04/issue-4/J_vH0edAQL.pdf>.
    Read in full (18.03%/28.58% annualized TSMOM, Sharpe 0.823/1.223), but **JOIREM is a low-quality venue
    with no evident peer review, and the paper performs no cost analysis.** Recorded as a data point,
    labelled `[BLOG]`-grade, **not relied upon.**

11. **Two sources cited by other papers could not be reached at all:** the AUT/ACFR copy of the
    "realistic assumptions" momentum paper (HTTP 403) and the Bernoussi & Rockinger PDF at Springer's own
    URL (JavaScript challenge — the open-access text was obtained through the `r.jina.ai` proxy instead,
    so the *content* was verified, but I note the access route).
