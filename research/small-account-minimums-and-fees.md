# Small Account Minimums and Fee Drag — Source-Verified Research

**Scope:** Minimum viable account size, fixed costs, and fee-drag solutions for algorithmic crypto trading with a **$1,000–2,000 CAD** account on **Kraken (Canada)**.

**Research date:** 2026-09-18. All live Kraken API data and web pages were fetched on this date.

**Labels used:**
- `[PEER-REVIEWED]` — peer-reviewed or NBER working paper that I actually fetched and read
- `[VERIFIED-URL]` — official/primary source (exchange docs, project docs, source code) that I actually fetched and read
- `[PRACTITIONER]` — named individual practitioner statement (maintainer, forum user), quoted verbatim
- `[BLOG]` — non-peer-reviewed secondary write-up
- `[MARKETING]` — content that sells a bot, signals, VPS, or carries an exchange referral; flagged explicitly
- `[CLAIM]` — assertion I could not independently verify
- `[REASONING]` — my own arithmetic or inference, explicitly grounded in a cited number

**Headline results (details below):**
1. **Kraken's minimum order sizes for CAD pairs are tiny (3.20–9.43 CAD).** Minimum order size is **not** the binding constraint on a $1,000–2,000 account. The binding constraint is **fees**.
2. **Kraken's base fee tier rose on 2026-07-09 to 0.40% maker / 0.80% taker.** The widely quoted "0.25% / 0.40%" is **outdated** for Kraken as of the research date. This roughly *doubles* the fee drag implied by most published commentary.
3. A $1,500 account doing **2 full-account round trips per month** pays **~14.4% of the account per year** in maker fees (28.8% at taker). It must earn that much gross just to break even.
4. **No peer-reviewed literature addresses small retail account fee drag specifically.** This is a genuine gap, not a research failure. What exists is (a) large-fund diseconomies of scale — the *opposite* direction, and (b) one peer-reviewed paper that explicitly notes retail pays more than large traders.
5. **The breakeven formula was found in a peer-reviewed source** (`annual cost = cost per trade × trades per year`); a published *worked example* was **NOT FOUND**. §C2 supplies the arithmetic: on Kraken, a market-order strategy must earn **>1.60% gross per full-account round trip** just to cover fees.
6. **The largest Canadian-specific risk is tax characterisation, not the tax rate.** An automated high-frequency strategy matches CRA's own worked example of **business income** — which means 100% inclusion at marginal rates plus mandatory CPP, not 50% inclusion. `[VERIFIED-URL]`
7. **A flat 10 CAD e-Transfer withdrawal fee** is **0.67% of a 1,500 CAD account per withdrawal**, and the 3.75% debit-card deposit fee is a severe trap. `[VERIFIED-URL]`
8. **Freqtrade documents no minimum account size at all** — it delegates to the exchange — but its own issue tracker shows maintainer-observed minimum stakes of **up to ~$60 on Kraken**. `[VERIFIED-URL]` / `[PRACTITIONER]`

---

## A. Exchange minimum order sizes / minimum notional

### A1. Kraken's documented cost minimum (quote-currency minimum notional) — `[VERIFIED-URL]`

Source: **Kraken Support, "Cost minimum for trading," last updated March 31, 2025**
https://support.kraken.com/articles/12425041458708-cost-minimum-for-trading

Verbatim: *"The Cost minimum order size goes by quote currency. The quote currency is the right or the second currency in a currency pair... If an order does not satisfy the cost minimum, it will be canceled and you will see the error, Cost minimum not met."*

The published table gives:

| Quote currency | Cost minimum |
|---|---|
| Australian Dollar | 1 AUD |
| **Canadian Dollar** | **1 CAD** |
| Swiss Franc | 0.5 CHF |
| Euro | 0.45 EUR |
| Pound Sterling | 0.43 GBP |
| Japanese Yen | 50 JPY |
| US Dollar | 0.5 USD |
| Bitcoin | 0.00002 BTC |
| Ethereum | 0.0002 ETH |
| Tether / USD Coin / Dai | 0.5 (each) |

**So for every CAD-quoted pair (BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD), Kraken's cost minimum is 1 CAD.** `[VERIFIED-URL]`

### A2. Kraken's documented base-currency minimum (order minimum) — `[VERIFIED-URL]`

Source: **Kraken Support, "Overview of deposit and trade minimums," last updated February 3, 2026** (the old `/articles/205893708-Minimum-order-size-volume-for-trading` URL now redirects here)
https://support.kraken.com/articles/360001389303-overview-of-cryptocurrency-minimums

Verbatim: *"The minimum order size goes by **base currency**."* and *"There is no way for us to make exceptions to the minimums, so please plan your activity accordingly."* and *"The values below can change without notice and may not always be current."*

Documented trade examples: *"If you are trading BTC, the volume of the order must be 0.0001 BTC or larger. If you are trading ETH, the volume of the order must be 0.01 ETH or larger."*

**Note a discrepancy I could not resolve:** this support article states BTC 0.0001 and ETH 0.01, but the live API (below, same day) returns BTC 0.00005 and ETH 0.001 — i.e. **2× and 10× lower**. The article itself warns the values "may not always be current." The API values are the machine-enforced ones. `[VERIFIED-URL]` for both; the discrepancy is reported rather than smoothed over.

Also documented: the **Buy Crypto** widget has *lower* minimums — *"The minimums are 1 unit of currency for USD, EUR, GBP, CAD, AUD, CHF and 110 JPY."* This is a UI path, not the order book, and its fees differ from Kraken Pro's schedule.

### A3. Live per-pair minimums for the four CAD pairs — `[VERIFIED-URL]`

Fetched directly from Kraken's public API on 2026-09-18:
`https://api.kraken.com/0/public/AssetPairs` and `https://api.kraken.com/0/public/Ticker`

| Pair (Kraken internal key) | `ordermin` (base units) | `costmin` | Last price (CAD) | `ordermin` × price | **Binding minimum notional** |
|---|---|---|---|---|---|
| XBT/CAD (`XXBTZCAD`) | 0.00005 BTC | 1 CAD | 112,916.00 | 5.6458 CAD | **5.65 CAD** |
| ETH/CAD (`XETHZCAD`) | 0.001 ETH | 1 CAD | 3,620.87 | 3.6209 CAD | **3.62 CAD** |
| SOL/CAD (`SOLCAD`) | 0.06 SOL | 1 CAD | 157.15 | 9.4290 CAD | **9.43 CAD** |
| XRP/CAD (`XXRPZCAD`) | 1.65 XRP | 1 CAD | 1.9375 | 3.1969 CAD | **3.20 CAD** |

Additional increment rules returned by the same API call (all four pairs, `lot_decimals = 8`):

| Pair | `tick_size` (price increment) | `pair_decimals` |
|---|---|---|
| XBT/CAD | 0.1 | 1 |
| ETH/CAD | 0.01 | 2 |
| SOL/CAD | 0.01 | 2 |
| XRP/CAD | 0.00001 | 5 |

**Kraken CAD quote-currency availability check:** the full `AssetPairs` response contains 12 CAD pairs: `EURCAD, PEPECAD, QCADUSD, SOLCAD, USDCCAD, USDTCAD, XDCCAD, XDGCAD, XETHZCAD, XXBTZCAD, XXRPZCAD, ZUSDZCAD`. All four pairs in question are `status: "online"`. `[VERIFIED-URL]`

### A4. Minimum deposit / minimum balance rules for Canada — `[VERIFIED-URL]`

Source: **Kraken Support, "Cash deposit options, fees, minimums and processing times," last updated August 17, 2026**
https://support.kraken.com/articles/360000381846-cash-deposit-options-fees-minimums-and-processing-times-

CAD deposit table, verbatim rows:

| Availability | Deposit method | Deposit minimum | Deposit fee |
|---|---|---|---|
| Canada only | Domestic wire transfer (Credit Union Atlantic) | 100 CAD | free** |
| Canada only | e-Transfer | 5 CAD | free |
| Canada only | Debit card | 10 CAD | **0.25 CAD + 3.75%** |
| Worldwide* | SWIFT (Bank Frick) | 4 CAD | 3 CAD |
| Canada only | Apaylo (Bill Pay) | 1 CAD | 0.25% per transaction, max 30 CAD per deposit |

**The debit-card option is a severe small-account trap: 3.75% + 0.25 CAD.** On a 1,500 CAD deposit that is ~56.50 CAD (3.77%) lost before a single trade. e-Transfer (5 CAD min, free) is the rational funding path. `[VERIFIED-URL]`

Source: **Kraken Support, "Cash withdrawal options, fees, minimums and processing times," last updated September 3, 2026**
https://support.kraken.com/articles/360000423043-cash-withdrawal-options-fees-minimums-and-processing-times-

| Availability | Withdrawal method | Withdrawal minimum | Withdrawal fee |
|---|---|---|---|
| Canada only | EFT (POSCONNECT) | 50 CAD | **0.35%** |
| Canada only | e-Transfer | 15 CAD | **10 CAD (flat)** |
| Worldwide* | SWIFT (Bank Frick) | 100 CAD | 13 CAD |

**The e-Transfer withdrawal fee is a flat 10 CAD.** On a 1,500 CAD account that is **0.67% of the entire account per withdrawal** — a genuinely size-regressive fixed cost. Four withdrawals per year costs 2.67% of the account, independent of strategy quality. `[VERIFIED-URL]` for the fee; `[REASONING]` for the percentage-of-account framing.

**I did not find any documented Kraken minimum account balance** — only minimum *deposits* and minimum *orders*. See COULD NOT VERIFY.

### A5. Kraken trading fees — **the base tier changed on 2026-07-09** `[VERIFIED-URL]`

Source: **Kraken Support, "Cross-platform fee tier changes (July 2026)," last updated July 9, 2026**
https://support.kraken.com/articles/cross-platform-fee-tier-changes

Verbatim: *"Starting July 9, 2026, we're changing how your fee tier is determined on Kraken. Your tier will now be based on your Spot volume or Assets on Platform, whichever qualifies you for the best rate."*

The article's own fee table (spot):

| Tier | Spot 30-Day Vol (USD) OR | AoP (USD) | Maker (%) | Taker (%) |
|---|---|---|---|---|
| **Tier 1** | **$0+** | **N/A** | **0.40 %** | **0.80 %** |
| Tier 2 | $2.5K+ | N/A | 0.30 % | 0.60 % |
| Tier 3 | $10K+ | 20k | 0.22 % | 0.38 % |
| Tier 4 | $25K+ | 50k | 0.20 % | 0.35 % |
| Tier 5 | $50K+ | 100k | 0.15 % | 0.30 % |
| Tier 6 | $100K+ | 200k | 0.12 % | 0.25 % |
| Tier 7 | $250K+ | 400k | 0.10 % | 0.22 % |
| Tier 8 | $500K+ | 600k | 0.08 % | 0.20 % |
| Tier 9 | $1M+ | 1m | 0.06 % | 0.18 % |
| Tier 10 | $2.5M+ | 2.5m | 0.04 % | 0.15 % |
| Tier 11 | $5M+ | 5m | 0.02 % | 0.12 % |
| Tier 12 | $10M+ | 10m | 0.0 % | 0.10 % |

Independently corroborated by scraping the current public schedule pages on the same date (both the global and Canada-specific pages, which render identical tables): `https://www.kraken.com/features/fee-schedule` and `https://www.kraken.com/ca/features/fee-schedule`. Both show Tier 1 = $0+ → 0.40% maker / 0.80% taker. `[VERIFIED-URL]`

Corroborating support article: **"What are Maker and Taker fees?", last updated February 9, 2026** — https://support.kraken.com/articles/360000526126-what-are-maker-and-taker-fees- — which states *"Fee schedule volume-based discounts are based on crypto trading volume only. Making purchases using the Buy Crypto widget, Kraken app as well as trading stablecoin and FX pairs on our order books does not contribute to the fee schedule 30-day volume."* `[VERIFIED-URL]`

**Two critical consequences for a small account:**

1. **The commonly cited "0.25% maker / 0.40% taker" Kraken base rate is stale.** It does not appear anywhere in the current published schedule. Any fee-drag analysis built on 0.25%/0.40% understates Kraken's current base cost by ~60%.
2. **A small account is structurally locked into the worst tier.** AoP-based tier improvement is unreachable (Tier 3 needs 20k AoP; a 1,500 CAD account has ~1.5k). The only route to a better tier is **30-day spot volume**, i.e. trading *more* — which raises total fees even as the rate falls (see §C3).

### A6. Historical context: Kraken's fees used to be far lower — `[PEER-REVIEWED]`

Makarov & Schoar's published exchange table (data through Feb 2018) lists: *"Kraken USA CAD, EUR, GBP, JPY, USD ... 0.00%-0.26%"*. Source: Igor Makarov & Antoinette Schoar, "Trading and arbitrage in cryptocurrency markets," *Journal of Financial Economics* 135(2), 2020, pp. 293–319, accepted version at https://researchonline.lse.ac.uk/id/eprint/100409/1/Cryptocurrency_Markets_JFE_final_v4.pdf (DOI: https://doi.org/10.1016/j.jfineco.2019.07.001).

So Kraken's base-tier fee has moved from **0.00–0.26% (2017–18)** to **0.40%/0.80% (July 2026)**. Fee-drag conclusions drawn from older crypto literature are not transferable to the current schedule. `[PEER-REVIEWED]` for the historical figure; `[REASONING]` for the comparison.

### A7. Does minimum order size mechanically cap the number of positions? — **No, for these pairs** `[REASONING]`

The task premise was that minimum order size forces coarse position sizing and caps position count. **For Kraken CAD pairs at a $1,000–2,000 account, this premise does not hold**, because the binding minimum notional is 3.20–9.43 CAD.

However, the *effective* minimum is larger than the raw exchange minimum once stoploss headroom is accounted for. Freqtrade documents the exact adjustment `[VERIFIED-URL]` (see §D2):

`effective_min_stake ≈ min_notional × (1 + amount_reserve_percent) / (1 − stoploss)`

With Freqtrade's defaults (`amount_reserve_percent = 0.05`) and a 10% stoploss:

| Pair | Binding min notional | Effective min stake @5% reserve, 10% SL | @5% reserve, 5% SL |
|---|---|---|---|
| XBT/CAD | 5.65 CAD | 6.59 CAD | 6.24 CAD |
| ETH/CAD | 3.62 CAD | 4.22 CAD | 4.00 CAD |
| SOL/CAD | 9.43 CAD | **11.00 CAD** | 10.42 CAD |
| XRP/CAD | 3.20 CAD | 3.73 CAD | 3.53 CAD |

**Maximum concurrent positions implied by the binding minimum (SOL/CAD, 11.00 CAD effective):**

| Account | Max concurrent SOL/CAD positions | A 10-position book needs |
|---|---|---|
| 1,000 CAD | 90.9 | 110 CAD = 11.0% of account |
| 1,500 CAD | 136.4 | 110 CAD = 7.3% of account |
| 2,000 CAD | 181.8 | 110 CAD = 5.5% of account |

**Conclusion:** minimum order size permits far more positions than a small account would ever want. The real sizing constraints on a $1,000–2,000 Kraken CAD account are (a) fees, (b) Freqtrade's `tradable_balance_ratio` (0.99) and `max_open_trades` division, and (c) the flat 10 CAD e-Transfer withdrawal fee. `[REASONING]`

**Caveat — the premise does hold in other settings.** Freqtrade's maintainer reports minimum stakes *"as high as 60$ on pairs that had a steep raise"* `[PRACTITIONER]`, and Freqtrade's own backtesting docs warn that *"trading-limits are inflated by using a historic price, resulting in minimum amounts > 50$"* `[VERIFIED-URL]`. So the conclusion is pair- and moment-specific, not universal.

---

## B. Fee drag / transaction cost economics — the literature

### B1. The foundational "costs are certain" argument — `[PEER-REVIEWED]`

**William F. Sharpe, "The Arithmetic of Active Management," *Financial Analysts Journal* Vol. 47, No. 1, January/February 1991, pp. 7–9.** Author's own copy: https://web.stanford.edu/~wfsharpe/art/active/active.htm

Verbatim: *"(1) before costs, the return on the average actively managed dollar will equal the return on the average passively managed dollar and (2) after costs, the return on the average actively managed dollar will be less than the return on the average passively managed dollar."*

And: *"Active managers must pay for more research and must pay more for trading."*

**Scope limit — important:** this is a statement about **averages across a whole market**, proved with *"only the laws of addition, subtraction, multiplication and division."* It says **nothing** about small accounts, nothing about turnover arithmetic, and nothing about crypto. It establishes only that active trading carries higher costs than not trading. It is routinely over-cited as if it proved more than that. `[REASONING]`

### B2. The Fundamental Law of Active Management — citation verified, text not read

**Richard C. Grinold, "The Fundamental Law of Active Management," *The Journal of Portfolio Management*, Spring 1989.** DOI verified via Crossref: https://doi.org/10.3905/jpm.1989.409211 (published 1989-04-30).

I **could not read the original text** (paywalled; no open-access copy located; SSRN returns 403). I therefore make **no claim** about its contents beyond the existence and identity of the citation. Related follow-ups located but also not read: "The fundamental law of active management: Redux," *Journal of Empirical Finance* (2017), DOI https://doi.org/10.1016/j.jempfin.2017.05.005 (listed as hybrid open access). `[VERIFIED-URL]` for the citation only.

### B3. Diseconomies of scale — **the literature runs the opposite direction from small-account disadvantage** `[PEER-REVIEWED]`

**Ľuboš Pástor, Robert F. Stambaugh & Lucian A. Taylor, "Scale and Skill in Active Management," NBER Working Paper 19891 (February 2014); published in *Journal of Financial Economics* 116(1), 2015, pp. 23–45.** https://www.nber.org/papers/w19891 (DOI: https://doi.org/10.3386/w19891)

Abstract, verbatim: *"We empirically analyze the nature of returns to scale in active mutual fund management. We find strong evidence of decreasing returns at the industry level: As the size of the active mutual fund industry increases, a fund's ability to outperform passive benchmarks declines. At the fund level, all methods considered indicate decreasing returns, but estimates that avoid econometric biases are insignificant. We also find that the active management industry has become more skilled over time. This upward trend in skill coincides with industry growth, which precludes the skill improvement from boosting fund performance. Finally, we find that performance deteriorates over a typical fund's lifetime."*

**This is the literature the task pointed at, and it says the opposite of what a small-account argument needs.** It documents that **being large is a disadvantage**, and explicitly notes that fund-level decreasing-returns estimates are **statistically insignificant** once econometric biases are avoided. It provides **no support** for the proposition that a small account is disadvantaged by fixed costs. `[REASONING]`

### B4. Turnover is not inherently bad — a necessary counterweight `[PEER-REVIEWED]`

**Ľuboš Pástor, Robert F. Stambaugh & Lucian A. Taylor, "Do Funds Make More When They Trade More?", NBER Working Paper 20700 (November 2014, revised April 2016); published in *Journal of Finance* (2017), DOI https://doi.org/10.1111/jofi.12509.** Free full text: https://www.nber.org/system/files/working_papers/w20700/w20700.pdf

Abstract, verbatim: *"We model optimal fund turnover in the presence of time-varying profit opportunities. Our model predicts a positive relation between an active fund's turnover and its subsequent benchmark-adjusted return. We find such a relation for equity mutual funds. This time-series relation between turnover and performance is stronger than the cross-sectional relation, as the model predicts. Also as predicted, the turnover-performance relation is stronger for funds trading less-liquid stocks, such as small-cap funds. Turnover has a common component that is positively correlated with proxies for stock mispricing, consistent with funds exploiting time-varying opportunities."*

Further, from the body: *"We find a stronger turnover-performance relation as well for funds charging higher fees"* and the relation is *"stronger for small funds than large funds, consistent with the ability of smaller funds to trade less-liquid stocks, given that smaller funds trade in smaller dollar amounts."*

**Read carefully, this does NOT license high turnover for a retail crypto bot.** (a) It concerns *equity mutual funds* managing large pools, not a 1,500 CAD account. (b) The dependent variable is **benchmark-adjusted return**, and the paper's model has funds trading only when they *"identify opportunities to establish positions that yield profits in the subsequent period, net of trading costs"* — i.e. the result is conditional on genuine skill. (c) A 1,600-basis-point round-trip cost (Kraken taker/taker) is orders of magnitude above the equity costs in this literature. It does, however, refute any blanket claim that "lower turnover is always better." `[REASONING]`

**Searched for and did not find** the term "break-even"/"breakeven" anywhere in this paper (0 hits). It contains no breakeven-turnover formula.

### B5. The one peer-reviewed source that explicitly flags a **retail** cost disadvantage `[PEER-REVIEWED]`

**Makarov & Schoar (2020), *Journal of Financial Economics* 135(2), 293–319** (free accepted version: https://researchonline.lse.ac.uk/id/eprint/100409/1/Cryptocurrency_Markets_JFE_final_v4.pdf).

Verbatim, on arbitrage constraints: *"In practice, the arbitrageur has to incur a number of transaction costs, but their magnitudes are too small to prevent arbitrageurs from implementing the above trading strategies... exchanges have trading fees, which increase the cost of trading."*

And, critically: *"But all large exchanges state that for large traders they provide preferential customized fees that are far below the cost for retail investors. In sum, these fees are small for large transactions. Overall, we believe that for large players the round-up trading costs should be within 50 to 75 basis points."*

Also: *"The exchange fees are comparable to the bid-ask spreads, which are, on average, between 1 and 10 basis points"* and *"many exchanges charge withdrawal fees; these range from 10 to 50 basis points per withdrawal for most of the exchanges."*

**This is the closest thing I found to a peer-reviewed statement of a small-account cost disadvantage**, and note how narrow it is: the authors' point is that costs are *negligible for large players* (50–75 bp round trip) while **explicitly noting that retail pays more**. They do not quantify the retail premium. The 50–75 bp figure is for **large players in 2017–18**, and Kraken's *current* retail round trip is **80–160 bp** — i.e. today's retail cost exceeds that paper's *large-player* estimate. `[REASONING]` for the comparison. Note also the paper's own data window (Jan 2017–Feb 2018); its absolute cost levels are dated.

### B6. Transaction costs and rebalancing — where the "wider bands" solution comes from `[PEER-REVIEWED]`

**W. Qiao, D. Bu, A. Gibberd, Y. Liao, T. Wen & E. Li, "When 'time varying' volatility meets 'transaction cost' in portfolio selection," *Journal of Empirical Finance* (2023).** Free accepted version: https://eprints.lancs.ac.uk/id/eprint/205305/1/JEF_final_copy.pdf (DOI: https://doi.org/10.1016/j.jempfin.2023.06.006)

This is the most useful *readable* peer-reviewed source on the fee-drag solution space. Verbatim, its literature review of cost-mitigation strategies:

> *"To mitigate the impact of transaction cost in portfolio allocation, there is a large number of existing studies in the literature. For example, the strategy discussed in Gârlanu and Pedersen (2013) and Gârlanu and Pedersen (2016) suggest that investors should trade only partially toward the desired position, e.g. trading only 15% toward the zero-cost optimal targets each day. Another available strategy (Kirby and Ostdiek 2012) allows the sensitivity of portfolio weights to volatility changes to be adjusted via a tuning parameter, and thus, the portfolio turnover can be controlled to a desired low level. These strategies successfully control over portfolio turnovers through reducing trading frequency, but a common drawback here is the use of a constant trading reduction rate over time which ignores the time-varying trade-off between portfolio risk reduction and the increase of transaction costs."*

And its own approach: rebalance *"solely when a change point has been detected in the covariance matrix, striking an optimal trade-off between rebalancing the portfolio to capturing the recent information in return data and avoiding excessive trading."*

Its empirical result: *"we document that our new strategy simultaneously lowers portfolio risk exposure and turnovers, largely improving portfolio out-of-sample sharpe ratio with transaction costs"* and *"GMV RRW achieves the lowest turnovers in all the cases. In terms of the Sharpe ratio after deducting transaction costs, we find that the GMV RRW provides the highest Sharpe ratio after transaction cost in all the data sets."*

**This supplies the formal, peer-reviewed basis for three of the fee-drag solutions the task asked about:** (i) **trade only partially toward target** (Gârleanu–Pedersen: ~15%/day), (ii) **wider/no-trade bands and reduced rebalance frequency**, and (iii) **condition rebalancing on a detected regime change rather than a calendar**. Note the important caveat the authors themselves raise: a *constant* partial-adjustment rate ignores that the cost/risk trade-off is time-varying.

The canonical theoretical origin of the no-trade-region result (Magill & Constantinides 1976, *JET*, DOI https://doi.org/10.1016/0022-0531(76)90018-1; Constantinides 1986, *JPE*, DOI https://doi.org/10.1086/261410) is **paywalled and I did not read it**, so I do not characterize its contents — I cite the Qiao et al. characterization instead. `[VERIFIED-URL]` for those citations only.

### B7. **Does any literature address fee drag for small accounts specifically? — NO** 

**Finding: I could not find any peer-reviewed or working-paper treatment of the fee-drag problem for small retail accounts** (sub-$10k), in crypto or equities. Targeted OpenAlex full-text and title searches for retail/small-account transaction-cost disadvantage returned unrelated results (household finance, information costs, banking). The literature divides into:

- **Large-fund/industry diseconomies of scale** (Pástor–Stambaugh–Taylor) — the *opposite* direction;
- **Institutional portfolio rebalancing under proportional costs** (Qiao et al. and the no-trade-region literature) — assumes institutional scale, and in Qiao et al.'s own calibration assumes **10–60 bp** per dollar traded, an order of magnitude below Kraken retail;
- **Crypto arbitrage costs** (Makarov–Schoar) — which notes retail pays more but quantifies only large-player costs.

**No source I found proposes or evaluates the specific solution set (lower turnover, wider rebalance bands, batching, tax-aware trading, holding-period extension) *for small accounts*.** The mechanisms are established for institutional portfolios; their application to a 1,500 CAD account is an extrapolation, and I flag it as such. `[REASONING]`

---

## C. Breakeven turnover arithmetic

### C1. An explicit annual cost formula — **FOUND** `[PEER-REVIEWED]`

Qiao et al. (2023), *Journal of Empirical Finance* (URL above), state their transaction-cost arithmetic verbatim:

> *"The transaction cost of each is calculated as **50 basis points times monthly turnover times 12 (to annualize)**."*

and, for the weekly rebalancing experiment:

> *"The transaction cost of each is calculated as **50 basis points times weekly turnover times 52 (to annualize)**."*

They also state their per-dollar cost assumption: *"Following standard practice of Robert et al. (2012), we set the transaction cost per dollar traded to decrease linear from 0.6% to 0.1% during the period 1967 to 1990, and set it to be a constant 0.1% from 1991 to 2017."*

**So the general form is: `annual cost drag = (cost per trade) × (trades per year)`**, and a strategy breaks even when its gross annual return exceeds that drag. This is the formula shape, from a peer-reviewed source. `[PEER-REVIEWED]`

### C2. Applied to a Kraken CAD small account — `[REASONING]`, grounded in C1 + §A5

I could **not find any source giving a worked "N round trips per year at fee level F consumes edge E" example**, in the literature or in credible practitioner writing. **NOT FOUND** as a published worked example. What follows is my own arithmetic using the verified Kraken Tier 1 rate and the Qiao et al. formula shape.

**Definition used:** one "round trip" = buying and then selling the **entire account value** once (traded notional = 2 × account value). If a strategy holds 10 equal positions, one position's round trip is 0.1 of this.

Kraken Tier 1: maker 0.40%, taker 0.80% per leg.

| | Per leg | Round trip | Gross return required per full-account round trip |
|---|---|---|---|
| Maker / maker | 0.40% | **0.80%** | > 0.80% |
| Maker entry + taker exit | 0.60% | **1.20%** | > 1.20% |
| Taker / taker (market orders) | 0.80% | **1.60%** | > 1.60% |

**A market-order strategy on Kraken must earn >1.6% gross per full-account round trip before it makes a single cent.** For a typical bot taking many small trades, that is the number that has to be beaten on average, per trade.

**Annual fee drag on a 1,500 CAD account, at the fee tier the volume itself earns:**

| Round trips / month | 30-day volume | Fee tier earned | Maker rate | Annual traded notional | Annual cost (maker) | **% of account** | Annual cost (taker) | **% of account** |
|---|---|---|---|---|---|---|---|---|
| 1 | 3,000 | Tier 2 | 0.30% | 36,000 | 108 | **7.2%** | 216 | **14.4%** |
| 2 | 6,000 | Tier 2 | 0.30% | 72,000 | 216 | **14.4%** | 432 | **28.8%** |
| 4 | 12,000 | Tier 3 | 0.22% | 144,000 | 317 | **21.1%** | 475 | **36.5%** |
| 6 | 18,000 | Tier 3 | 0.22% | 216,000 | 475 | **31.7%** | 821 | **54.7%** |
| 10 | 30,000 | Tier 4 | 0.20% | 360,000 | 720 | **48.0%** | 1,260 | **84.0%** |
| 20 | 60,000 | Tier 5 | 0.15% | 720,000 | 1,080 | **72.0%** | 2,160 | **144.0%** |
| 30 | 90,000 | Tier 5 | 0.15% | 1,080,000 | 1,620 | **108.0%** | 2,160 | **144.0%** |

`[REASONING]` — arithmetic on verified Kraken rates (§A5). Two notes on the construction: (i) Kraken's tier thresholds are quoted in USD and I treated CAD≈USD for threshold purposes, which is a simplification that shifts at most one tier boundary; (ii) tiers are 30-day rolling, so the rate is not fixed across a year.

### C3. The perverse tier interaction — `[REASONING]`

**Higher turnover lowers the fee *rate* but raises total cost, always.** Compare the 1-round-trip case (Tier 2, maker 0.30%) with the 20-round-trip case (Tier 5, maker 0.15%): the maker **rate halves**, yet annual cost rises from **7.2% to 72.0% of the account**, because annual volume rises 20×. From Tier 1 (0.40%) to Tier 5 (0.15%) the rate falls 62%, and total cost still rises. The volume-discount structure does not rescue a small account; it merely softens the slope. `[REASONING]`

### C4. What this means for a 1,000–2,000 CAD account

For the account to be net-positive, its strategy must clear **~14–32% gross annually at 2–6 full-account round trips per month** (maker), or **29–55%** (taker). A 10-round-trips-per-month maker strategy needs **>48% gross annually** just to break even. These are not impossible numbers in crypto, but they are far above the equity-market edges the academic literature studies.

**A warning about fee assumptions in backtests and published fee-drag commentary.** Qiao et al. assume **0.1% per dollar traded** for post-1991 equities; the Freqtrade docs' own `--fee` example is **0.1%**; and the crypto-bot blog in §D4 uses **0.1% per trade**. Kraken's current Tier 1 is **0.40% maker / 0.80% taker** — i.e. those assumptions understate the per-leg cost by **4× (maker) to 8× (taker)**, and understate annual fee drag by the same factor. Any small-account backtest or article built on 0.1% per side is not merely optimistic; it is wrong by an order of magnitude on the dominant cost term. `[REASONING]`

**This is the single most decision-relevant number in this report.** Fee drag, not minimum order size, is what constrains a $1,000–2,000 CAD Kraken account.

---

## D. Practitioner consensus on minimum account size

### D1. Freqtrade's own documentation — `[VERIFIED-URL]`

Read from the source of truth: raw markdown on the `develop` branch (`https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/configuration.md`), re-verified against the live pages `https://www.freqtrade.io/en/stable/configuration/` and `.../backtesting/`.

**"Minimum trade stake" (docs/configuration.md), verbatim:**

> *"The minimum stake amount will depend on exchange and pair and is usually listed in the exchange support pages."*
>
> *"Assuming the minimum tradable amount for XRP/USD is 20 XRP (given by the exchange), and the price is 0.6$, the minimum stake amount to buy this pair is `20 * 0.6 ~= 12`. This exchange has also a limit on USD - where all orders must be > 10$ - which however does not apply in this case."*
>
> *"To guarantee safe execution, freqtrade will not allow buying with a stake-amount of 10.1$, instead, it'll make sure that there's enough space to place a stoploss below the pair (+ an offset, defined by `amount_reserve_percent`, which defaults to 5%)."*
>
> *"With a reserve of 5%, the minimum stake amount would be ~12.6$ (`12 * (1 + 0.05)`). If we take into account a stoploss of 10% on top of that - we'd end up with a value of ~14$ (`12.6 / (1 - 0.1)`)."*
>
> *"To limit this calculation in case of large stoploss values, the calculated minimum stake-limit will never be more than 50% above the real limit."*
>
> **Warning:** *"Since the limits on exchanges are usually stable and are not updated often, some pairs can show pretty high minimum limits, simply because the price increased a lot since the last limit adjustment by the exchange. Freqtrade adjusts the stake-amount to this value, unless it's > 30% more than the calculated/desired stake-amount - in which case the trade is rejected."*

**Documented config parameters (defaults, verbatim from the docs table):**

| Parameter | Default | Docs text |
|---|---|---|
| `tradable_balance_ratio` | **`0.99`** | *"Ratio of the total account balance the bot is allowed to trade."* |
| `amount_reserve_percent` | **`0.05`** | *"Reserve some amount in min pair stake amount. The bot will reserve `amount_reserve_percent` + stoploss value when calculating min pair stake amount in order to avoid possible trade refusals."* |
| `amend_last_stake_amount` | **`false`** | *"Use reduced last stake amount if necessary."* |
| `last_stake_amount_min_ratio` | **`0.5`** | *"Defines minimum stake amount that has to be left and executed."* |

**Why 0.99:** *"By default, the bot assumes that the `complete amount - 1%` is at it's disposal... Freqtrade will reserve 1% for eventual fees when entering a trade and will therefore not touch that by default."*

**Stake = balance / max_open_trades, explicitly documented:** *"when using dynamic stake amount, it will split the complete balance into `max_open_trades` buckets per trade"*; and in backtesting docs, *"`stake_amount` as `"unlimited"` ... will split the starting balance into `max_open_trades` pieces."* Confirmed in source at `freqtrade/wallets.py::_calculate_unlimited_stake_amount`.

**Dust handling, verbatim:** *"The minimum last stake amount can be configured using `last_stake_amount_min_ratio` - which defaults to 0.5 (50%). This means that the minimum stake amount that's ever used is `stake_amount * 0.5`. **This avoids very low stake amounts, that are close to the minimum tradable amount for the pair and can be refused by the exchange.**"*

**Backtesting fee handling:** *"All profit calculations include fees, and freqtrade will use the exchange's default fees for the calculation."* The `--fee` option exists for rebates: *"This fee must be a ratio, and will be applied twice (once for trade entry, and once for trade exit)"*, example `--fee 0.001`. The config table says the `fee` parameter *"Should normally not be configured"*. **The docs do NOT recommend 0.0025 or any specific "realistic" fee** — zero hits for `0.0025` in all docs.

**Critical backtesting warning (docs/backtesting.md), verbatim:** *"Exchanges have certain trading limits, like minimum (and maximum) base currency, or minimum/maximum stake (quote) currency... **This can lead to situations where trading-limits are inflated by using a historic price, resulting in minimum amounts > 50$.**"* Example given: *"BTC minimum tradable amount is 0.001. BTC trades at 22.000$ today ... Today's minimum would be `0.001 * 22_000` - or 22$. However the limit could also be 50$ - based on `0.001 * 50_000` in some historic setting."*

**KEY ABSENCE FINDING:** Freqtrade's documentation contains **no absolute minimum stake or minimum account size in any currency, and no statement about how much money you need to run Freqtrade.** It explicitly delegates this to the exchange. Also, `"available_balance"` is **not** a documented `stake_amount` option (only a positive float or `"unlimited"`).

**Undocumented hard constraint found in source:** `stake_amount="unlimited"` combined with `max_open_trades = -1` raises `ConfigurationError("max_open_trades` and `stake_amount` cannot both be unlimited.")` in `freqtrade/configuration/config_validation.py`. The bot refuses to start, and **the docs never mention this.** `[VERIFIED-URL]`

### D2. Freqtrade maintainer statements with concrete numbers — `[PRACTITIONER]`

Freqtrade's maintainer (`xmatthias`) on the project's own issue tracker — these are primary practitioner statements, not marketing:

**On Kraken specifically** — issue #7120, 2022-07-24, https://github.com/freqtrade/freqtrade/issues/7120:
> *"freqtrade uses the minimum amounts exchanges enforce - based on the assumed stoploss it would take - which for binance is ~15 USDT - but can also be more depending on the exchange and pair used. 15$ is a rough estimate for this - but i've seen minimum stakes of as high as 60$ on pairs that had a steep raise (and the exchange didn't adjust the limits yet)."*

And in issue #7183 (2022-08-05), https://github.com/freqtrade/freqtrade/issues/7183:
> *"the 60$ i've seen were on kraken - binance had their limits lower - as long as you stay above 20$ you'll be fine there."*

**On why the effective minimum exceeds the exchange minimum** — issue #5208, 2021-06-29, https://github.com/freqtrade/freqtrade/issues/5208:
> *"While binance states the minimum order amount - that's the minimum it allows you to place your orders. For freqtrade, we also need to account for an eventual stoploss - so the minimum will be raised by 'stoploss' (or a maximum of 50% if you use very large stoplosses) - + 'amount_reserve_percent' - to be sure the stoploss has enough room to be placed after price rounding and such. While you observed 12$ as minimum - this minimum will go up to 15$ or higher if you use a larger stoploss."*

**On the dust problem** — issue #8093, 2023-02-02, https://github.com/freqtrade/freqtrade/issues/8093:
> *"Exchanges usually have 2 limits - one on the amount - and one on value... while a 10% drop will still have you own 10 KRL - it might be below the 10$ value - which means you can't sell it anymore. you're also ignoring fees, which different exchanges handle differently (you might buy 10 KRL on binance - but if you don't own BNB - you'll only get 9.9 KRL, the 0.1 KRL is fees. Now the worst case in that case is if KRL trades in lot-sizes of 1 - which means you can only sell 9 KRL, and the 0.9 KRL remain on the account (also called bina[nce dust])."*

And in the same thread: *"Usual position limits are around 10-15$."*

**Empirical demonstration that small stakes silently drop trades** — issue #7183, user's backtest with a 1,000 USDT starting balance, verbatim:
> *"Where X is: 20 -> 1 buy, 25 -> 4 buys, 35 -> 6 buys, 50 -> 22 buys, 55 -> 24 buys, 100+ -> 24 buys"*

A 5× difference in trade count between a 20 and 100 stake, on the same strategy and data, caused purely by exchange minimum-size rejection. **This is exactly the mechanical distortion the task asked about — and it operates on stake size, not on account size per se.** `[PRACTITIONER]`

**The maintainer's counter-position** (same thread, 2022-08-06), which I record because it is the strongest argument against worrying about this:
> *"the really relevant value in backtesting is anyway the relative profit. If you start with 100$ - or 10k$ - that's an amount that won't change."*

I note this is only true **if** minimum-size rejection does not truncate the trade population — which the same thread's own data (20 → 1 buy vs 100 → 24 buys) shows it does. `[REASONING]`

### D3. Independent practitioner consensus — `[PRACTITIONER]`

Reddit r/algotrading, quoted verbatim (via the `.rss` endpoint; HTML/JSON were blocked from this environment):

- **"Low Capital Starts" (2023)** — https://www.reddit.com/r/algotrading/comments/113f2dk/low_capital_starts/ — the OP is nearly the exact case in question: *"I'm not going to be starting out with $25k. I probably wouldn't be comfortable starting out with more than a few thousand to be honest... but Im thinking in terms of $1-2k per year over a LONG time frame. With that, what can I realistically expect as a ceiling?"* Top reply (u/Big_Enthusiasm_5577): *"Low capital is a completely different problem than growing an account. Considering the strategy in terms of % earned rather than nominal capital, unless the nominal is quite large or you can't buy fractionals. If the strategy itself is reliable and can scale, there's other avenues to scale capital like a prop firm."* Another (u/masilver): *"I have an algo I'm going live with this week. I'm only using $600. I'm not going to be rich from it, but I shouldn't have more than a $200-300 drawdown, either. So it depends on your algo."*
- **"How much money did you start with?" (2015)** — https://www.reddit.com/r/algotrading/comments/29j0es/how_much_money_did_you_start_with/ — u/georgeo: *"If you have a solid system, you can trade 1 lots for $2K, if you don't, $100mil won't save you."* u/skgoa: *"3k is the absolute bottom of what experience traders are saying you need to start in forex. Lower than that and the commissions will eat a too high fraction of your profits. 10k is a pretty common point to start"*.
- **"Costs for Algo Traders" (2022)** — https://www.reddit.com/r/algotrading/comments/wgw77h/costs_for_algo_traders/ — OP's stack: *"Live Data Feed - $12/mth, Ninjatrader Lease - $75/mth, VPS - $50/mth, Total - $137/mth"*; counterpoint u/symm3tri: *"my strategy uses 5 minute data from Robinhood, is set up in python, and runs on aws free tier, so I have essentially no monthly costs."* Relevant because **fixed monthly infrastructure costs, not just fees, are a distinct small-account problem** — $137/month is 9% of a $1,500 account *per month*. `[PRACTITIONER]` + `[REASONING]`

**Convergence:** independent practitioners cluster at **$2,000–$10,000+**, with fee-drag and position-sizing as the stated reasoning. **No independent source I found claims profitability at $1,000–2,000.**

### D4. Blogs and marketing content — flagged

- `[BLOG]` **algotrading101.com** — https://algotrading101.com/learn/how-much-money-do-you-need-for-trading/ — *"You need 20 times your yearly expenses to be a full-time trader. However, the minimum amount needed could be as low as $300, if you just want to test your ideas and learn."* Best articulation found of the structural point: *"The minimum capital required is defined as the smallest amount required to run your strategy. In other words, it is the amount that lets you trade your intended bet size."* Worked example: *"Imagine that your strategy requires you to buy 1% of your trading capital in Apple stock. If your trading capital is $2000, you need to buy $20 of Apple stock. But one share of Apple stock is trading at $200 at the time of this writing. Hence, $2000 is not enough. You need $20,000 to get started."* Note this example is an **equities share-granularity** problem; crypto's fractional units make it far less binding (see §A7).
- `[BLOG]` **tradingbotexperts.com** — https://www.tradingbotexperts.com/blog/how-much-money-do-you-need-to-start-bot-trading — **FLAGGED: marketing** (email-capture "Get My Free Bot Report", bot recommendations). Numbers: *"most experienced crypto bot traders suggest a minimum of $500 to $1,000 to run a basic strategy with enough position size to cover fees"*; *"A strategy that makes 100 trades per month at 0.1 percent per trade on a $1,000 account is spending roughly $100 per month on fees alone, which is ten percent of the account"*. The fee arithmetic is directionally consistent with mine, but note it assumes **0.1% per trade** — vs Kraken's current **0.40%/0.80%**, i.e. it understates the drag 4–8×.
- `[MARKETING]` **freyafinance.com** — https://www.freyafinance.com/academy/getting-started/how-much-capital-for-bot-trading — vendor academy (sells exchange/bot accounts). Table: DCA bot single pair — *"Absolute Minimum $200 / Practical Minimum $500 / Recommended $1,000-2,000"*. States its own caveat: *"The dollar amounts and percentages in this guide are worked examples, not recommendations."* Its own $1,000 worked example shows *"round-trip fee $2.00"* on a *"1.5% TP"* — i.e. it assumes **0.1% per side**, again 4–8× below Kraken's current rate.
- `[MARKETING]` **gixodia.com** — https://gixodia.com/en/blog/minimum-capital-trading-bot — sells a $199–249/mo bot subscription. **Forex, not crypto.** Claim: *"Straight answer: $2,000 minimum, $5,000 recommended, $25,000 optimal."* Self-serving circularity: *"You need whatever the broker's minimum margin is, typically $2,000."*
- `[MARKETING]` **clearedge.trading** — https://clearedge.trading/post/money-needed-algorithmic-trading — sells an automation platform ($69–149/mo). **Futures, not crypto.** *"Starting algorithmic trading requires approximately $500-$2,500 in initial capital for most retail traders using futures contracts."*
- `[MARKETING]` **smartalgotrade.com** — https://www.smartalgotrade.com/algo-trading-blog/how-much-money-do-you-need-to-start-algo-trading/ — sells EAs and runs an affiliate program. *"Supplementing income $1,000–$5,000"*.
- `[MARKETING]` **Forex Factory thread 1416044** — https://www.forexfactory.com/thread/1416044-how-much-capital-do-you-actually-need-to — **appears to be an independent forum thread but is not**: posted by user "Smartalgotra", which Forex Factory labels "Commercial User" and flags as "Commercial Content"; it reposts smartalgotrade.com.
- `[MARKETING]` **ontilttrading.com** — https://ontilttrading.com/how-much-money-do-you-need-for-a-trading-bot/ — **heaviest flag: PrimeXBT exchange referral with promo code** (*"use promo code PRIMEOTT, you'll immediately get a +7% bonus"*). Claim: *"Experts typically recommend starting with at least $1,000 to $5,000 for beginners."*
- `[MARKETING]` **tradingcopilot.app** — https://www.tradingcopilot.app/blog/best-crypto-trading-bots-small-accounts — bot-comparison affiliate site. Its fixed-cost reasoning is nonetheless the sharpest of the marketing set: *"A $50,000 account paying $100/month for a bot needs 0.2% monthly returns just to break even on the subscription. A $500 account paying that same $100? You need 20% monthly returns just to cover the fee. That's not realistic — it's a guaranteed loss."*

**Pattern:** every source claiming a $500–$2,000 "absolute minimum" for crypto bots turned out to be **vendor/marketing content**, and each assumed per-trade fees of ~0.1% — far below Kraken's current 0.40%/0.80%. Independent practitioners, by contrast, cluster at $2,000–$10,000+. `[REASONING]`

---

## E. Canadian / CAD-specific overhead

### E1. CRA's crypto hub page and its current title — `[VERIFIED-URL]`

The CRA's crypto landing page is now titled **"Information for crypto-asset users and tax professionals"** (page details 2025-10-29):
https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide.html

It indexes six sub-pages: `crypto-assets-tax-obligations.html`, `books-records-crypto.html`, `value-crypto.html`, `income-crypto-transactions.html`, `income-crypto-mining-staking-activities.html`, `gst-hst-crypto-transactions.html`.

The phrase *"Guide for cryptocurrency users and tax professionals"* **does not appear on the live page.** The earliest Wayback snapshot retrievable (captured 2025-01-29) already carried the new title. See COULD NOT VERIFY.

### E2. Capital gain vs. business income — `[VERIFIED-URL]`

Source: https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html (page details 2025-12-02)

Verbatim:
> *"Generally, your income from crypto-assets transactions may be considered business income when your crypto-assets activities are consistent with those of a person carrying on a business."*
> *"Generally, if a crypto-asset transaction is not made on account of business income, it would be considered capital in nature."*

CRA's stated factors, verbatim headings: *"**Frequency of transactions** – You have a history of extensive buying and selling of crypto-assets"*; *"**Period of ownership** – You hold your crypto-assets for a short period of time, and you turn them over quickly"*; *"**Knowledge of crypto-asset markets**"*; *"**Time spent** – You spend a substantial part of your time studying crypto-asset markets"*; *"**Financing** – You finance your crypto-asset purchases by some form of debt"*; *"**Advertising** – You advertise that you are willing to buy crypto-assets"*.

And critically: *"Whether you are carrying on a business or not must be determined on a case-by-case basis and consider all the factors of your transaction. However, an isolated crypto-asset transaction could be determined to be on account of business income when it is considered an adventure or concern in the nature of trade."*

CRA's own worked example: *"You regularly buy and sell various types of crypto-assets. You pay close attention to the fluctuations… and intend to profit from the fluctuations. **Your activities are consistent with someone who is carrying on a business.**"*

**This is the most important Canadian finding for a bot operator.** An automated strategy that trades frequently, holds briefly, and exists to profit from fluctuations matches CRA's own example of business income — **two of the six listed factors (frequency, short holding period) are properties of the *design* of a trading bot, not of the operator's intent.** If characterised as business income, the consequence is *"you must report the **full amount** of your profits"* — 100% inclusion at marginal rates, not 50%, with no capital-loss carryforward treatment. `[VERIFIED-URL]` for the quotes; `[REASONING]` for the design implication.

CRA sources its factor list to **IT-479R, *Transactions in Securities*** (archived; bulletin dated February 29, 1984; page details 2017-11-07): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html — para 11 lists eight factors, and para 12 states *"Although none of the individual factors in 11 above may be sufficient…, the combination of a number of those factors may well be sufficient for that purpose."* CRA cautions: *"this does not mean that crypto-assets are necessarily securities (for example, shares and bonds) for income tax purposes."* `[VERIFIED-URL]`

### E3. Adjusted cost base and the identical-properties rule — `[VERIFIED-URL]`

CRA's crypto pages define ACB only loosely — *"your adjusted cost base (**usually the cost of a crypto-asset, plus expenses to acquire it**)"* — and **the phrase "identical properties" appears zero times across all six crypto sub-pages** (verified by grep of the fetched pages).

The pooled average-cost rule comes from the general capital gains guide, **T4037** (page details 2026-02-11): https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4037/capital-gains.html

> *"Properties of a group are considered to be identical if each property in the group is the same as all the others… You may buy and sell several identical properties at different prices over a period of time. If you do this, **you have to calculate the average cost of each property in the group at the time of each purchase** to determine your adjusted cost base (ACB). **Dispositions of identical properties do not affect the ACB.** The average cost is calculated by dividing the total cost of identical properties purchased… by the total number of identical properties owned."*

**So the CRA method is pooled average cost, not per-lot FIFO.** `[VERIFIED-URL]` for the rule; `[REASONING]` for its application to crypto of the same type — **CRA never names crypto-assets as identical properties**, so this is an inference from the general rule, not a CRA statement about crypto. Flagged in COULD NOT VERIFY.

**Is there a de minimis exemption for small gains? No — not for crypto.** The only small-amount de minimis in T4037 is currency-specific: *"Foreign exchange gains or losses from capital transactions of foreign currencies (**that is money**)… you must only report the amount of your net gain or loss for the year that is **more than $200**."* Crypto is not government-issued currency — CRA states *"Since cryptocurrency is not government-issued currency, using cryptocurrency as payment for goods or services is treated as a **barter transaction** for income tax purposes."* The separate $1,000 personal-use-property rule applies to personal-use property, not investment crypto. `[VERIFIED-URL]` for the quotes.

**Consequence: every crypto-to-crypto swap is a disposition, and there is no threshold below which a trade is too small to report.** For a bot making hundreds of small trades, that is hundreds of reportable dispositions. `[REASONING]`

### E4. Superficial loss rule — `[VERIFIED-URL]`, independently re-verified

Source (I fetched and read this myself): https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html (page details 2026-02-05). Identical wording in T4037.

Verbatim:
> *"A superficial loss can occur when you dispose of **capital property** for a loss and both of the following conditions are met: You, or a person affiliated with you, buys, or has a right to buy, the same or identical property (called "substituted property") **during the period starting 30 calendar days before the sale and ending 30 calendar days after the sale**; You, or a person affiliated with you, **still owns, or has a right to buy, the substituted property 30 calendar days after the sale**."*
>
> *"If you have a superficial loss in 2025, you cannot deduct it when you calculate your income for the year. However, if you are the person who acquires the substituted property, **you can usually add the amount of the superficial loss to the adjusted cost base of the substituted property**."*

Affiliated persons include *"you and your spouse or common-law partner."* Listed exceptions: deemed disposition on ceasing residency, change of use, becoming/ceasing to be tax-exempt within 30 days, death, expiry of an option, shareholder appropriation on winding-up, and dispositions by corporations/partnerships/trusts of non-depreciable capital property.

**This is a direct, mechanical constraint on bot design.** A stop-loss-and-rebuy strategy, or a strategy that exits a losing position and re-enters the same asset within 30 days, **has its loss denied** and the amount pushed into ACB. A mean-reversion bot that repeatedly stops out and re-enters the same pair is exactly the pattern the rule targets. `[REASONING]`

**COULD NOT VERIFY** a CRA statement naming crypto-assets in the superficial-loss context — applicability follows by construction (crypto on capital account + same coin re-bought within the window). Flagged.

### E5. Capital gains inclusion rate — current status, dated `[VERIFIED-URL]`, independently re-verified

**Rate today (2026-09-18): 50% (one-half).** I verified this directly: CRA's *Capital losses* page states verbatim **"The inclusion rate for 2025 is 50%."** and carries a table row **"From 2001 to 2025 — 1/2 (50%)"**. Corroborated by T4037 and by CRA's crypto page (2025-12-02): *"If you have disposed of a crypto-asset on account of capital, you must include **half** of your capital gains (known as taxable capital gains) in your income for the year."*

**Dated sequence:**

| Date | Event | Source |
|---|---|---|
| 2024-04-16 | Budget 2024 proposes raising the inclusion rate from 1/2 to 2/3 for corporations/trusts and on individual gains above $250,000, for gains realized on or after 2024-06-25 | https://www.canada.ca/en/department-finance/news/2024/06/capital-gains-inclusion-rate.html (page details 2024-06-10); https://budget.canada.ca/2024/report-rapport/tm-mf-en.html |
| 2024-06-10 | Notice of Ways and Means Motion tabled to implement the measure | same Finance backgrounder |
| **2025-01-31** | **DEFERRAL** — Minister LeBlanc defers the increase *"from June 25, 2024 to **January 1, 2026**"* | https://www.canada.ca/en/department-finance/news/2025/01/government-of-canada-announces-deferral-in-implementation-of-change-to-capital-gains-inclusion-rate.html |
| **2025-01-31** | **CRA reverts to administering 50%** — *"the Canada Revenue Agency (CRA) has **reverted to administering the currently enacted capital gains inclusion rate of one-half**."* Late-filing penalty/interest relief to 2025-06-02; corrective reassessments for corporations that had filed at 2/3 | https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2025/update-cra-administration-proposed-capital-gains-taxation-changes.html |
| **2025-03-21** | **CANCELLATION** — *"Today, Prime Minister Carney announced that the Government of Canada will **cancel the proposed hike in the capital gains inclusion rate**."* The Lifetime Capital Gains Exemption increase to $1,250,000 is retained | https://www.pm.gc.ca/en/news/news-releases/2025/03/21/prime-minister-mark-carney-cancels-proposed-capital-gains-tax-increase — **I fetched and read this page myself** |
| 2025-11-04 | Budget 2025 tax-measures page lists measures proceeding; **no inclusion-rate increase** appears | https://budget.canada.ca/2025/report-rapport/tm-mf-en.html |
| 2026-03-26 | Royal assent, Bill C-15 (Budget 2025 Implementation Act, No. 1), S.C. 2026, c. 3 — the enacted text contains **zero "inclusion rate" amendments**; it enacts the LCGE increase instead | https://www.parl.ca/legisinfo/en/bill/45-1/c-15 |

**So: the 66.67% increase was proposed (2024-04-16), deferred to 2026-01-01 (2025-01-31), and then cancelled (2025-03-21). The inclusion rate is 50%.** `[VERIFIED-URL]`

**Live trap worth flagging to any reader:** Finance's June 2024 backgrounder at https://www.canada.ca/en/department-finance/news/2024/06/capital-gains-inclusion-rate.html **is still online and un-updated** (page details 2024-06-10) and still describes the 2/3 increase as proceeding. A reader who finds that page first will get the wrong answer. `[VERIFIED-URL]`

### E6. Record-keeping — and does it scale with trade count? **Yes, linearly** `[VERIFIED-URL]`

Source: https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html (page details 2025-11-10)

Verbatim:
> *"If you engage in crypto-asset transactions, **you have to keep adequate books and records to support each transaction**. This applies to individuals and businesses."*

Required per-transaction fields, verbatim: *"The number of units and type of crypto-asset for each transaction; The **date and time** of each transaction; The **value of the crypto-asset (in Canadian dollars) at the time of each transaction**; A description of the nature of each transaction and the other party… (even if it is just their crypto-asset address); The addresses associated with each digital wallet used; The beginning wallet balance (and its cost) and ending wallet balance for each crypto-asset for each year."*

For exchange activity: *"Trade ledgers (buy, sell and swaps); Transfer ledgers (deposits and withdrawals…); Records supporting any other types of transactions that took place on the exchange."*

Retention: *"You are responsible for keeping all required books and records for **at least six years** from the end of the last taxation year to which the records and books of account relate."* (Corroborated by the general records page: https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/keeping-records/where-keep-your-records-long-request-permission-destroy-them-early.html)

Vendor-risk clause: *"regularly export a history of your activity to make sure you have adequate books and records in case the exchange ceases operating, stops offering services in Canada, or you lose access to your account."*

**Does the burden scale with trade count? Yes — CRA's obligation is per-transaction** ("records to support **each** transaction", CAD value "at the time of **each** transaction"), so record-keeping workload is linear in trade count. A bot making 500 trades/year generates 500 reportable dispositions, each requiring a timestamped CAD valuation. `[VERIFIED-URL]` for the quotes; `[REASONING]` for the linear-scaling conclusion.

### E7. Is there a measured cost of filing many small trades? **NO — the strongest evidence is a vendor price ladder** 

**Do Canadian crypto exchanges issue tax slips? No general slip regime for crypto.** CRA's T5008 guide **T4091** (https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t5008.html, page details 2026-08-18; PDF at https://www.canada.ca/content/dam/cra-arc/formspubs/pub/t4091/t4091-26e.pdf) defines covered securities as *"publicly traded shares…; publicly traded debt obligations; debt obligations of, or guaranteed by [governments]…; prescribed debt obligations…; publicly traded interests in a partnership or a trust; any option or contract for any of the properties listed above; publicly traded options or contracts for any property including any commodity…"* — **crypto-assets are not in that list, and the words "crypto"/"virtual currency" appear 0 times in the T4091 PDF.** `[VERIFIED-URL]`

Note the reporting posture for *covered* securities, which shows CRA's general approach: *"You have to prepare a T5008 slip for all reportable transactions, **regardless of the amount of proceeds. There is no administrative limit for reporting securities transactions.**"*

**Third-party reporting is coming but not yet:** Budget 2025 lists among measures proceeding the *"**Crypto-Asset Reporting Framework** and the Common Reporting Standard (subject to a deferred application date of **January 1, 2027**)"* (https://budget.canada.ca/2025/report-rapport/tm-mf-en.html). For tax years before 2027 there is no CARF crypto slip, so the taxpayer self-computes ACB and proceeds. `[VERIFIED-URL]`

**What exists on cost scaling:**
- `[PRACTITIONER]` **Assertion, not a measurement** — Rizwan Ali, CPA (Fullstake CPA), "Best Crypto Tax Software Canada 2026," updated May 2026, https://fullstakecpa.com/best-crypto-tax-software-canada-2026-koinly-vs-cointracker-vs-coinledger-compared/ — on Koinly: *"**Pricing scales aggressively for high-transaction-count traders**"*; *"Pricing: Free preview, paid plans **tiered by transaction count**"*. He also asserts the software does *"NOT… Make judgment calls on capital gains vs. business income classification… Defend you in a CRA audit."* This is an assertion about pricing structure, **not** a measured compliance cost.
- `[BLOG]` / vendor list price — **Koinly pricing page**, fetched 2026-09-18: https://koinly.io/pricing/ — embedded plan data shows Newbie **100 transactions, CAD 69**; Hodler **1,000 transactions, CAD 149**; Trader **3,000 transactions, CAD 299**; Pro **10,000+ transactions, CAD 399**. One commercial tool's price rises **~5.8×** from the 100-trade tier to the 10,000-trade tier.

**FINDING: I could not find any CRA, government, peer-reviewed, or academic source that *measures* the dollar cost of filing a given number of crypto trades in Canada.** The only quantified, source-verified cost-scaling data point is a vendor's own published price ladder; the only practitioner statement is a qualitative assertion. This is a genuine evidence gap — see COULD NOT VERIFY. `[REASONING]`

**Other Canadian overhead found:**
- **CPP on business income is mandatory.** If trading is business income, CPP contributions on self-employment income are required: https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/line-22200-deduction-cpp-qpp-contributions-on-self-employment-other-earnings.html (page details 2026-01-20) — *"Claim the CPP or QPP contributions that you: **have to make on self-employment**"*. For 2025 CRA states *"the YMPE is $71,300 and the YAMPE is $81,200"*. `[VERIFIED-URL]`
- **EI is opt-in, not automatic.** T4002 Ch. 1: *"As a self-employed individual **you may be eligible to contribute** to employment insurance (EI) for yourself. **You may register to participate**…"* (https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4002/t4002-3.html). So EI is *not* an automatic consequence of a business-income reassessment; CPP is. `[VERIFIED-URL]`
- **Business treatment also forces inventory accounting** — CRA offers Method 1 (lower of cost or year-end FMV per item) or Method 2 (entire inventory at year-end FMV) (`value-crypto.html`), and states *"each type is considered to be a separate asset and must be valued separately."* This roughly doubles year-end valuation work versus capital treatment. `[VERIFIED-URL]` + `[REASONING]`
- **T1135 (foreign property > $100,000) does not mention crypto.** https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/information-been-moved/foreign-reporting/foreign-income-verification-statement.html requires reporting by residents who own *"specified foreign property costing more than $100,000"* — but the page never mentions crypto-assets. **COULD NOT VERIFY** whether crypto held on a foreign exchange is specified foreign property. In practice a $1,000–2,000 account is far below the threshold regardless. `[VERIFIED-URL]` for the threshold; gap flagged.

### E8. Canadian overhead: bottom line for a $1,000–2,000 account — `[REASONING]`

Three Canadian-specific costs bite a small account, and **none of them scale down with account size**:

1. **A flat 10 CAD e-Transfer withdrawal fee** (Kraken, §A4) = **0.67% of a 1,500 CAD account per withdrawal**, independent of strategy.
2. **A 3.75% + 0.25 CAD debit-card deposit fee** if funded the wrong way = ~56.50 CAD on a 1,500 CAD deposit, before any trading. Use e-Transfer.
3. **Per-transaction record-keeping** for six years, with the obligation defined per transaction by CRA — so a bot's trade count *is* an administrative cost multiplier, and tax software prices it in tiers (CAD 69 → 399 across one vendor's ladder).

And the largest Canadian-specific risk is **characterisation, not rate**: a high-frequency automated strategy matches CRA's own example of business income, which would move the account from 50% inclusion to **100% inclusion at marginal rates plus mandatory CPP**. That change is worth far more than the difference between Kraken's Tier 1 and Tier 5 fees. `[REASONING]`

---

## COULD NOT VERIFY

1. **No documented Kraken minimum account balance.** Kraken documents minimum *deposits* (§A4) and minimum *orders* (§A1–A3), but I found no minimum *balance* requirement for Canada.
2. **Kraken BTC/ETH minimum order size discrepancy unresolved.** Support article says 0.0001 BTC / 0.01 ETH; live API returns 0.00005 BTC / 0.001 ETH on the same day. Both verified; not reconciled.
3. **Grinold (1989) full text not read.** Citation verified via Crossref (DOI 10.3905/jpm.1989.409211); content not characterized. No open-access copy located; SSRN returns 403.
4. **Magill & Constantinides (1976) and Constantinides (1986) full texts not read.** Cited via Qiao et al.'s characterization only.
5. **Pástor–Stambaugh–Taylor "Scale and Skill" published JFE version not read** (closed access). Abstract read from NBER WP 19891, which is the same paper.
6. **No published worked example of "N round trips per year consumes edge E at fee level F."** The *formula* was found (Qiao et al.); a worked breakeven example was **NOT FOUND**. §C2 is my own arithmetic, labelled `[REASONING]`.
7. **No peer-reviewed literature on fee drag for small retail accounts** (sub-$10k), in crypto or equities. This is a substantive gap in the literature, not a search failure. See §B7.
8. **No peer-reviewed source on minimum viable capital for retail algo trading.** None of the practitioner sources in §D are peer-reviewed.
9. **Kraken's fee schedule is region-selected and JS-rendered.** I verified the global and `/ca/` pages render identical tables, but I could not rule out that a logged-in Canadian account sees a different schedule. The July 2026 support article is the strongest evidence and it matches.
10. **Search infrastructure was severely degraded.** `web_search` returned "No results found" throughout. The prescribed DuckDuckGo-lite fallback (`lite.duckduckgo.com`) worked for the first few queries then began failing with `TypeError: fetch failed`; `html.duckduckgo.com`, Mojeek, Brave, Ecosia, Startpage and multiple SearXNG instances were all captcha-blocked or rate-limited from this environment. Scholarly work was therefore done through the **OpenAlex, Crossref, Semantic Scholar and NBER APIs** (which worked), and primary sources through direct URL fetches and the Kraken public API. **Reddit HTML/JSON is blocked here; only `.rss` worked, so Reddit coverage in §D3 is partial, not exhaustive.**
11. **Wiley/Elsevier/T&F PDF endpoints blocked curl** (Cloudflare). This is why several peer-reviewed papers are cited by DOI only.
12. **Kraken CAD withdrawal fee page** was located only at the second URL tried; the first (`/hc/articles/360000767986`) did not render a CAD table.
13. **No CRA statement names crypto-assets as "identical properties."** The phrase appears **zero times** across all six CRA crypto sub-pages. Pooled average-cost ACB for crypto is an inference from T4037's generic rule, not a CRA statement about crypto.
14. **No CRA statement applies the superficial loss rule to crypto-assets by name.** Applicability follows by construction (capital property + same coin re-bought within the 30-day window).
15. **No single CRA or Finance page states in words that the inclusion-rate increase is cancelled.** The cancellation is established by the PM release (2025-03-21), the measure's absence from Budget 2025 and from Bill C-15 as enacted, and CRA's 50% tables.
16. **CRA does not publish an explicit 2026 inclusion rate.** Its inclusion-rate table ends at *"From 2001 to 2025 — 1/2 (50%)"*. The 50% figure for 2025 is explicit; 2026 is inferred from the cancellation and the absence of any enacted change.
17. **No measured (government, peer-reviewed, or academic) dollar cost of filing N crypto trades in Canada.** Only a vendor price ladder (Koinly, CAD 69→399) and a CPA's qualitative assertion were found.
18. **Whether crypto held on a foreign exchange is T1135 "specified foreign property"** — CRA's T1135 page does not mention crypto-assets. Immaterial at $1,000–2,000 (threshold is $100,000) but unresolved.
19. **A CRA page titled "Guide for cryptocurrency users and tax professionals"** — no live trace and no Wayback snapshot found; the earliest retrievable snapshot (2025-01-29) already carried the current title.
20. **Kraken CAD funding/withdrawal pages are region-selected and JS-rendered.** I verified the tables I quote render consistently, but I could not rule out that a logged-in Canadian account sees different figures.
21. **OpenAlex/Crossref/Semantic Scholar are bibliographic, not full-text-searchable at scale.** My "no literature exists on X" findings (§B7, §C2) rest on targeted title and full-text queries plus the failure of multiple search engines from this environment. They are strong but not exhaustive negative results.

---

## Source index

**Kraken (primary, all fetched 2026-09-18):**
- Cost minimum for trading — https://support.kraken.com/articles/12425041458708-cost-minimum-for-trading (upd. 2025-03-31)
- Overview of deposit and trade minimums — https://support.kraken.com/articles/360001389303-overview-of-cryptocurrency-minimums (upd. 2026-02-03)
- Cross-platform fee tier changes (July 2026) — https://support.kraken.com/articles/cross-platform-fee-tier-changes (upd. 2026-07-09)
- Fee schedule (global) — https://www.kraken.com/features/fee-schedule
- Fee schedule (Canada) — https://www.kraken.com/ca/features/fee-schedule
- What are Maker and Taker fees? — https://support.kraken.com/articles/360000526126-what-are-maker-and-taker-fees- (upd. 2026-02-09)
- Cash deposit options, fees, minimums — https://support.kraken.com/articles/360000381846-cash-deposit-options-fees-minimums-and-processing-times- (upd. 2026-08-17)
- Cash withdrawal options, fees, minimums — https://support.kraken.com/articles/360000423043-cash-withdrawal-options-fees-minimums-and-processing-times- (upd. 2026-09-03)
- Public API — https://api.kraken.com/0/public/AssetPairs · https://api.kraken.com/0/public/Ticker

**Freqtrade (primary):**
- Configuration docs — https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/configuration.md · https://www.freqtrade.io/en/stable/configuration/
- Backtesting docs — https://www.freqtrade.io/en/stable/backtesting/
- Issue #7120 — https://github.com/freqtrade/freqtrade/issues/7120
- Issue #7183 — https://github.com/freqtrade/freqtrade/issues/7183
- Issue #5208 — https://github.com/freqtrade/freqtrade/issues/5208
- Issue #8093 — https://github.com/freqtrade/freqtrade/issues/8093
- Issue #5856 — https://github.com/freqtrade/freqtrade/issues/5856

**Peer-reviewed / working papers:**
- Sharpe (1991), *FAJ* 47(1):7–9 — https://web.stanford.edu/~wfsharpe/art/active/active.htm
- Grinold (1989), *JPM* — https://doi.org/10.3905/jpm.1989.409211 (citation only)
- Pástor, Stambaugh & Taylor, NBER WP 19891 / *JFE* 116(1):23–45 — https://www.nber.org/papers/w19891
- Pástor, Stambaugh & Taylor, NBER WP 20700 / *JF* — https://www.nber.org/system/files/working_papers/w20700/w20700.pdf
- Makarov & Schoar (2020), *JFE* 135(2):293–319 — https://researchonline.lse.ac.uk/id/eprint/100409/1/Cryptocurrency_Markets_JFE_final_v4.pdf
- Qiao, Bu, Gibberd, Liao, Wen & Li (2023), *J. Empirical Finance* — https://eprints.lancs.ac.uk/id/eprint/205305/1/JEF_final_copy.pdf
- Magill & Constantinides (1976), *JET* — https://doi.org/10.1016/0022-0531(76)90018-1 (citation only)
- Constantinides (1986), *JPE* — https://doi.org/10.1086/261410 (citation only)

**CRA / Government of Canada (primary, all fetched 2026-09-18):**
- Crypto hub: Information for crypto-asset users and tax professionals — https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide.html (2025-10-29)
- Income from crypto-asset transactions (capital vs. business income) — https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html (2025-12-02)
- Books and records for crypto-assets — https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html (2025-11-10)
- Valuing crypto-assets — https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/value-crypto.html
- T4037 Capital Gains — https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4037/capital-gains.html (2026-02-11)
- Line 12700 — Capital losses (inclusion rate; superficial loss) — https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html (2026-02-05)
- IT-479R *Transactions in Securities* (archived) — https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html
- Keeping records — retention period — https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/keeping-records/where-keep-your-records-long-request-permission-destroy-them-early.html
- T5008 / T4091 guide — https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t5008.html (2026-08-18)
- CPP on self-employment income (line 22200) — https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/line-22200-deduction-cpp-qpp-contributions-on-self-employment-other-earnings.html (2026-01-20)
- T4002 Ch. 1 (EI opt-in for self-employed) — https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/t4002/t4002-3.html
- T1135 — https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/information-been-moved/foreign-reporting/foreign-income-verification-statement.html
- **Inclusion rate timeline:** Finance Budget 2024 backgrounder — https://www.canada.ca/en/department-finance/news/2024/06/capital-gains-inclusion-rate.html (2024-06-10, *still online un-updated*); **deferral** — https://www.canada.ca/en/department-finance/news/2025/01/government-of-canada-announces-deferral-in-implementation-of-change-to-capital-gains-inclusion-rate.html (2025-01-31); CRA administrative reversal — https://www.canada.ca/en/revenue-agency/news/newsroom/tax-tips/tax-tips-2025/update-cra-administration-proposed-capital-gains-taxation-changes.html (2025-01-31); **cancellation** — https://www.pm.gc.ca/en/news/news-releases/2025/03/21/prime-minister-mark-carney-cancels-proposed-capital-gains-tax-increase (2025-03-21); Budget 2025 measures — https://budget.canada.ca/2025/report-rapport/tm-mf-en.html; Bill C-15 royal assent — https://www.parl.ca/legisinfo/en/bill/45-1/c-15

**Practitioner / vendor (E7 only):**
- Koinly pricing (vendor list prices) — https://koinly.io/pricing/
- Fullstake CPA, "Best Crypto Tax Software Canada 2026" (practitioner assertion) — https://fullstakecpa.com/best-crypto-tax-software-canada-2026-koinly-vs-cointracker-vs-coinledger-compared/
