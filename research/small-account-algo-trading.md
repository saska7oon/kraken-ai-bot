# Small crypto accounts ($1,000–2,000 CAD) and algorithmic trading: what the evidence actually says

**Research date:** 2026-09-18
**Subject account:** self-hosted Freqtrade, Kraken Canada, spot only, CAD pairs (BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD), daily candles, post-only (maker) limit orders, ~$1,000–2,000 CAD.
**Reported backtest:** +13.67% over 17 months, 14 trades, max DD 8.83%, Sharpe 0.14 (from this repo's own `research/turtle-risk-model-result.md`).

## Claim labels used in this report

| Label | Meaning |
|---|---|
| **[PEER-REVIEWED]** | Refereed journal / professional-society publication |
| **[VERIFIED-URL]** | I fetched this URL in this session and read the text; the claim is in that text |
| **[PRACTITIONER]** | Identifiable practitioner writing on their own site; not peer reviewed |
| **[BLOG]** | Self-published / vendor / affiliate content — low evidentiary weight |
| **[CLAIM]** | Asserted by someone but I did not verify it |
| **[REASONING]** | My own inference or arithmetic, **not** a sourced claim |
| **[LOCAL]** | From this repository's own files |

> **Reading rule:** the distinction between a *sourced claim* and *my reasoning* is the point of this document. Every number below is either traceable to a URL I fetched, or is explicitly labelled as my own computation with its inputs shown.

---

## 0. Bottom line

1. **There is no literature on strategy design specifically for small retail accounts.** I could not find any peer-reviewed or credible practitioner study that addresses "$1,000–2,000 account" as a distinct design problem. What exists is (a) general evidence on retail trading profitability, and (b) general transaction-cost theory. Anything claiming to be small-account-specific strategy research should be treated as marketing. **[REASONING]** based on searches described in §9.
2. **Fee drag is NOT the binding constraint on this particular bot — sample size is.** At 14 trades in 17 months, ~10 trades/year, ~30% of the wallet per trade, the round-trip fee drag is ≈2.7%/year. That is real but survivable. The fatal problem is that 14 trades cannot distinguish this strategy from luck, and the backtest result is *inside* the noise band of a zero-edge process. See §8.
3. **The Kraken fee tier is genuinely locked.** [VERIFIED-URL] Tier 2 needs $2,500 of 30-day spot volume; the only alternative qualifying measure (Assets on Platform) does not start until Tier 3 at $20k. A $1,000–2,000 account trading ~10 times a year is firmly Tier 1 (0.40% maker / 0.80% taker). And trading more to reach the tier is arithmetically self-defeating (§7).
4. **Minimum order sizes are a non-issue on these four pairs.** [VERIFIED-URL] Kraken's API reports `ordermin`/`costmin` implying minimum orders of roughly $3–10 CAD. A $300 stake clears them by 30–100×. The common practitioner claim that exchange minimums cripple small accounts does **not** apply here.
5. **The single biggest available cost lever is the maker/taker choice, worth ~0.80%/round trip — larger than the entire edge the bot claims per trade.** [REASONING] from verified fees.
6. **Whether the bot beat buy-and-hold depends entirely on the window, and I can show both answers.** From 2024-09-28 buy-and-hold won decisively (+53.1% vs +13.67%). From 2024-11-27 — the date all four whitelisted pairs actually existed — buy-and-hold **lost 26.1%** and the bot's +13.67% won. Both comparisons are single-window and neither establishes skill. §8.
7. **The base rates are brutal and they are consistent across every independent dataset.** Every population-scale study lands in a **70–97% loss band**: ESMA 74–89%, FCA 82%, ASIC 63–80%, BIS crypto-app data 73–81%, Taiwan "more than eight out of ten", Brazil 97% of those who persisted 300+ days. And the loss rate **rises with persistence** — profit probability *decreases* monotonically with days traded in Brazil, and the FCA found *"inexperienced retail clients lose less money than experienced clients."* §5.
8. **The "20% of day traders profit" figure that circulates is an annualisation artifact.** It collapses to **under 1%** on a persistent basis (Taiwan: <1% "predictably and reliably"; Brazil: 1.1% beat minimum wage, 0.5% beat a bank teller). §5.2.
9. **The best available direct test of systematic crypto rules vs buy-and-hold is two-sided, and it agrees with my own computation.** Hudson & Urquhart (2021) tested ~15,000 technical rules: they beat buy-and-hold on **risk-adjusted** returns and drawdowns, but only **4.96–15.69% of rules beat it on raw return**, and **Bitcoin had no out-of-sample predictability**. That is the same pattern I found locally: the bot won on drawdown, lost on return. §5.1c, §8.2.
10. **The capstone finding: a statistically bulletproof edge can still be the wrong choice.** [VERIFIED-URL] I independently recomputed `Apex-prim/strategy-audit` from its raw `LEDGER.csv` (895 public freqtrade strategies from 53 repos). **878 were dropped at the first gate; only 2 survived every gate; and 0 of those 2 beat buy-and-hold.** The decisive row, `CombinedBinHClucAndMADV5`, has **1,295 out-of-sample trades, +0.46%/trade, p = 8.4 × 10⁻¹⁵, and a positive 95% CI lower bound** — an edge that is genuine by every statistical test — **and it still returned +106.91% against buy-and-hold's +346.34%, losing by 239pp.** **28 strategies did beat buy-and-hold, and every one failed a robustness gate.** The question is not *"does my bot have an edge?"* but *"does it beat doing nothing?"* §5.1d.
11. **The honest case for this bot is drawdown management, not return enhancement — and I am revising my own earlier finding accordingly.** Borgards (2021), a peer-reviewed 6-year crypto study, found low-frequency trend following netted +127% vs buy-and-hold's +186% — *lower return, far lower drawdown*. Separately, my measured +17.6pp quarterly-rebalancing premium (§4.1) is almost certainly a window artifact: El Bernoussi & Rockinger (2023) find the rebalancing premium is **~1.35 basis points per year** and statistically indistinguishable from buy-and-hold at ~1% costs. **I am withdrawing the return-premium interpretation of my own §4.1 result.**
12. **The general turnover law is the most transferable evidence found.** Novy-Marx & Velikov (2016, RFS): costs reduce realized spreads by >1% of monthly one-sided turnover; high-turnover anomalies went **negative**; only low-turnover ones survived. Their breakeven rule implies gross edge per round trip must exceed **~0.80% of notional traded**, allowing ~**6 full-notional round trips/year** at a 5% gross edge. This bot does ~3/year — **inside the survivable band, which is why fees are not its problem.** §4.4.
13. **Honest answer to "should a small account trade systematically at all?"** On the evidence available: the burden of proof has **not** been met by this bot, and the fee, tax and base-rate structure all penalise trading relative to holding or rebalancing. But the evidence does **not** prove it cannot work — a minority of rules and traders do persist, and the drawdown-reduction benefit is real and documented. The defensible framing is **not** "this makes money" but "this may reduce drawdown, at the cost of expected return, and its edge is unproven." See §5, §8.4, and §8b.

---

## 1. The account's verified cost structure

### 1.1 Kraken fees — Tier 1 is locked

[VERIFIED-URL] Kraken, "Cross-platform fee tiers", last updated 2026-07-09 — <https://support.kraken.com/articles/cross-platform-fee-tier-changes>
[VERIFIED-URL] Kraken Canada fee schedule page — <https://www.kraken.com/ca/features/fee-schedule> — fetched and HTML-extracted this session. **The identical Tier 1–Pro 5 table (Tier 1 = 0.40% maker / 0.80% taker) appears on the Canadian page**, confirming the repo's assumption that CAD pairs follow the same schedule as every other pair. That page also states: *"Instant Buy does not count towards your 30 day volume incentives."*

Verbatim from the page: *"Starting July 9, 2026, we're changing how your fee tier is determined on Kraken. Your tier will now be based on your Spot volume or Assets on Platform, whichever qualifies you for the best rate."*

| Tier | Spot 30-Day Vol (USD) **OR** | AoP (USD) | Maker | Taker |
|---|---|---|---|---|
| Tier 1 | $0+ | N/A | **0.40%** | **0.80%** |
| Tier 2 | $2.5K+ | N/A | 0.30% | 0.60% |
| Tier 3 | $10K+ | 20k | 0.22% | 0.38% |
| Tier 4 | $25K+ | 50k | 0.20% | 0.35% |
| Tier 5 | $50K+ | 100k | 0.15% | 0.30% |

**Implications for this account [REASONING]:**
- The premise "far too small to reach a better tier" is **correct**. Tier 2 requires $2,500 of *30-day spot volume*. This bot trades ~10×/year at ~$300–600 notional — roughly $3,000–6,000 of *annual* volume, i.e. ~$250–500 per month. That is 5–10× short of Tier 2.
- The AoP escape hatch does not open until Tier 3 ($20,000 of assets on platform) — ~10–20× the account size.
- The tier table was restructured on 2026-07-09. Any older blog quoting "0.16%/0.26%" or "0.25%/0.40%" Tier 1 is stale.

### 1.2 Kraken+ (the zero-fee subscription) does NOT help an API bot

[VERIFIED-URL] Kraken, "Kraken+ FAQ: Subscription Service Overview", last updated 2026-09-17 — <https://support.kraken.com/articles/kraken-faq-subscription-service-overview>

- Verbatim: *"**Please note: Kraken+ only applies to Kraken Web and App only. It does not apply to Kraken Pro or any of our other interfaces.**"*
- Cost: **$4.99/month** (verified on that page).
- [VERIFIED-URL] The Kraken Canada fee page states Kraken+ members get *"zero trading fees on up to $10,000 USD (or the local currency equivalent) in monthly trading volume for major currencies (USD, GBP, CAD, AUD, EUR, CHF). This benefit applies only to trades made through the Buy, Sell, or Convert features on the Kraken app or web, and does not include Spot, Futures, API, or OTC trades on Kraken Pro."* — <https://www.kraken.com/ca/features/fee-schedule> (also summarised at <https://support.kraken.com/articles/360030303832-overview-of-fees-on-kraken>)

**Conclusion [REASONING]:** Freqtrade trades through the Kraken Pro/API path, so Kraken+ cannot reduce this bot's fees. It is nonetheless a materially cheaper route for *manual, non-automated* buying (zero trading fee up to $10k CAD/month, paying only spread) — but it is not automatable and carries a spread instead of an explicit fee.

### 1.3 Minimum order sizes — verified, and not binding

[VERIFIED-URL] Kraken public API, `AssetPairs` endpoint, fetched this session:
`https://api.kraken.com/0/public/AssetPairs?pair=XBTCAD,ETHCAD,SOLCAD,XXRPZCAD`

| Pair | Kraken `ordermin` | `costmin` | Approx. minimum order value |
|---|---|---|---|
| BTC/CAD (XXBTZCAD) | 0.00005 BTC | 1 | ≈ $5.6 CAD |
| ETH/CAD (XETHZCAD) | 0.001 ETH | 1 | ≈ $3.6 CAD |
| SOL/CAD (SOLCAD) | 0.06 SOL | 1 | ≈ $9.4 CAD |
| XRP/CAD (XXRPZCAD) | 1.65 XRP | 1 | ≈ $3.2 CAD |

(Values converted at the closes fetched the same session; `costmin` is reported as 1 in quote currency.)

**This largely refutes a common claim.** A frequently repeated practitioner objection is that exchange minimum order sizes make small accounts unworkable. On these four Kraken CAD pairs, the static minimum order is single-digit CAD, and a ~$300 stake clears it by ~30–100×. **[REASONING]**, from [VERIFIED-URL] data.

**But there are two important qualifications, and one of them contradicts the conclusion above.**

**Qualification 1 — the *effective* minimum is larger than the static one.** [VERIFIED-URL] Freqtrade's documentation gives a "Minimum trade stake" formula that accounts for `tradable_balance_ratio`, `amount_reserve_percent`, and the stoploss. A delegated thread computed effective minimums of ~3.6–11.0 CAD for these pairs, with **SOL/CAD the largest at ~11 CAD**. Freqtrade's docs add that *"the calculated minimum stake-limit will never be more than 50% above the real limit."* Even at 11 CAD, a 1,500 CAD account could hold ~136 such positions — so **minimums still do not bind** at a 3-position book.

**Qualification 2 — and this is the real small-account effect.** [PRACTITIONER] Freqtrade's maintainer (xmatthias) reports on Kraken: *"i've seen minimum stakes of as high as 60$ on pairs that had a steep raise"*, and in a follow-up, *"the 60$ i've seen were on kraken"* — <https://github.com/freqtrade/freqtrade/issues/7120>. **This is 6–19× larger than the static `ordermin` implies, and I could not reconcile the two figures.** A further maintainer demonstration shows the mechanism: with the same strategy and a 1,000 USDT balance, **stake 20 produced 1 buy while stake 100 produced 24 buys** — small stakes cause trades to be **silently skipped**, not merely resized.

**[REASONING] Why this matters more than the static minimum:** a bot that silently skips trades does not fail loudly. It produces a backtest/live divergence with no error message, and on a $1,000–2,000 account with `max_open_trades: 3` and a 90% tradable ratio, each stake is ~$300–600 — close enough to the reported ~$60 Kraken threshold that the risk is real but the margin is not enormous. **The repo should verify its effective minimum stake on each of the four pairs empirically rather than trusting `ordermin`.**

**Unresolved discrepancy, reported rather than smoothed:** [VERIFIED-URL] Kraken's own support article states minimums of BTC 0.0001 and ETH 0.01, while the live `AssetPairs` API returned 0.00005 and 0.001 on the same day — **2× and 10× lower**. Both were verified; I could not determine which governs order acceptance. Also note Kraken documents a **cost minimum of 1 CAD** for every CAD-quoted pair — <https://support.kraken.com/articles/12425041458708-cost-minimum-for-trading>.

The real small-account constraints from minimums are subtler: `max_open_trades: 3` with `stake_amount: "unlimited"` and `tradable_balance_ratio: 0.90` [LOCAL: `config/canada_kraken.json`] forces each position to ~30% of the wallet. That is a *concentration* constraint, not a minimum-size constraint.

### 1.4 Bid-ask spread — verified live, and dwarfed by the fee

[VERIFIED-URL] Kraken public API, `Ticker` endpoint, fetched this session:

| Pair | Spread |
|---|---|
| BTC/CAD | ≈0.0001% |
| ETH/CAD | 0.0324% |
| SOL/CAD | 0.0127% |
| XRP/CAD | 0.0103% |

**Implication [REASONING]:** at Tier 1, the 0.40% maker fee is roughly **13× to 400×** the top-of-book spread. Spread is not the problem; the exchange fee is. This also means the maker-vs-taker decision (0.40% vs 0.80% per side) is the dominant cost lever available — far more important than order placement cleverness.

Caveat **[REASONING]**: top-of-book spread is not the cost of a large market order, and for a *resting* (maker) order the relevant cost is adverse selection — you get filled when price is moving against you. The repo's `config/base.json` already reasons about this correctly.

### 1.5 Tax and record-keeping overhead (Canada)

[VERIFIED-URL] CRA, "Reporting income from crypto-asset transactions", page details 2025-12-02 — <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html>

- Every disposition is a taxable event, including **trading one crypto-asset for another**.
- Crypto income is either **business income** or a **capital gain**, decided case by case. The CRA lists the indicators, quoting the page: *"**Frequency of transactions** – You have a history of extensive buying and selling of crypto-assets"* and *"**Period of ownership** – You hold your crypto-assets for a short period of time, and you turn them over quickly"*.
- Capital gains: *"you must include half of your capital gains (known as taxable capital gains) in your income"* — i.e. the **50% inclusion rate** is what the page states, with worked examples using 50%.
- Capital losses: *"You are allowed to deduct half of your capital losses... but only against your taxable capital gain."* Cannot be applied against employment income.

[VERIFIED-URL] CRA, "Keeping books and records of crypto-assets for tax filing", page details 2025-11-10 — <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html>

- Per-transaction records required: units and type, **date and time of each transaction**, CAD value at the time, nature of the transaction and counterparty, wallet addresses, and beginning/ending balances per year.
- Retention: *"at least six years from the end of the last taxation year"*.
- Exchanges: keep trade ledgers, transfer ledgers, and *"regularly export a history of your activity"* in case the exchange ceases operating.

**Implication for a Canadian bot [REASONING]:** record-keeping cost scales with trade count. At 14 trades/year this is a few minutes of work; at 500 trades/year it is a real burden requiring software. More importantly, the CRA's own listed indicators — trade frequency and short holding periods — are exactly what an active bot produces. **The more a bot trades, the stronger the case for business-income treatment rather than capital-gains treatment.** Business income is 100% included versus 50% for capital gains, so this can roughly double the tax drag on gains. I did **not** find a source quantifying how many trades crosses that line — it is a facts-and-circumstances test, and I could not verify a threshold. See §9.

**Inclusion rate — RESOLVED by the delegated thread (this closes a gap in my first draft):**

[VERIFIED-URL] The inclusion rate is **50% today**, not 66.67%. The thread verified the full timeline and fetched the primary documents:
- Proposed **2024-04-16** to raise the inclusion rate above $250k.
- **Deferred 2025-01-31** to 2026-01-01.
- **Cancelled 2025-03-21** (Prime Minister Carney's release — fetched and read).
- Omitted from Budget 2025; **Bill C-15 received royal assent 2026-03-26 with zero inclusion-rate amendments.**
- CRA states *"The inclusion rate for 2025 is 50%"* with a table *"From 2001 to 2025 — 1/2 (50%)"*.

⚠️ **Live trap worth knowing about:** Finance Canada's June 2024 backgrounder is **still online and un-updated**, still describing the two-thirds hike as proceeding. Anyone reading it would compute the wrong tax. **My §1.5 tax arithmetic therefore stands at 50%.**

**Two further Canadian tax mechanics that bear directly on this bot's design [VERIFIED-URL]:**

1. **The superficial loss rule.** A loss is denied (and added to the adjusted cost base) if identical property is bought within **30 days either side** of the sale. **This bot's design triggers it.** The strategy exits on a −12% stoploss and then, via `CooldownPeriod` of 1 candle = **1 day** [LOCAL: `config/strategies/moderate_multi.py`], is eligible to re-enter the same pair. Re-entering the same pair within 30 days of a stop-out means the loss is **denied for tax purposes and capitalised into the new position's ACB**. On a strategy whose entire premise is "many small losers pay for a few large winners," this removes the tax value of the losers. **[REASONING]** I could not find a source quantifying the dollar impact, and I have not computed it — but the mechanism is documented and the bot's design falls inside the window.
2. **Pooled average-cost ACB, not FIFO** (per CRA Guide T4037). Note the thread's finding that **CRA never explicitly names crypto as "identical properties"** (0 hits across all six crypto sub-pages), and that there is **no de minimis for crypto** — every swap is a disposition.
3. **No CRA crypto slip regime.** Crypto is absent from T4091's securities list; **CARF reporting is deferred to 2027-01-01**. The only dollar estimate of filing cost the thread found was a **vendor price ladder (Koinly: CAD 69 → 399 across 100 → 10,000 transactions)** — a vendor price, not a measured cost. At 14 trades/year the account sits in the cheapest tier.

### 1.6 Funding and withdrawal costs — the flat fees that do not scale down

[VERIFIED-URL] Kraken Canada funding pages, fetched and verified by the delegated thread (deposit page updated 2026-08-17, withdrawal page 2026-09-03):

| Action | Cost | As % of a $1,500 account |
|---|---|---|
| Interac e-Transfer deposit (5 CAD min) | **free** | 0% |
| **Debit-card deposit** (10 CAD min) | **0.25 CAD + 3.75%** | **≈3.8%** — ≈$56.50 on a $1,500 deposit |
| EFT withdrawal | 0.35% | 0.35% |
| **Interac e-Transfer withdrawal** | **flat 10 CAD** | **0.67% per withdrawal** |

**[REASONING] This is a genuine small-account penalty and it is the one place where account size really does bite.** A **flat 10 CAD** withdrawal fee is 0.67% of a $1,500 account but only 0.01% of a $100,000 account — it does not scale down. Similarly, the debit-card deposit route costs ~3.8% on a $1,500 deposit, which is **more than four full round trips' worth of trading fees** and would take the bot roughly eight months of its reported 9.4% CAGR to earn back. **The correct funding route is unambiguous: Interac e-Transfer in (free), and avoid debit card entirely.** The thread found **no documented Kraken minimum balance** requirement.

---

## 2. Q1 — Is there published evidence on strategy design *specifically for small retail accounts*?

**Short answer: I found none, and I looked.** What exists falls into three buckets, none of which is small-account-specific:

1. **Retail trading profitability base rates** — large, peer-reviewed literature on whether retail traders make money. It does not discuss strategy *design* for small accounts; it measures outcomes. (See §5.)
2. **Transaction-cost theory** — Sharpe's arithmetic and the backtest-overfitting machinery. General, not size-specific. (See §6, §7.)
3. **Practitioner content** — overwhelmingly vendor/affiliate material. Searches for "minimum account size algo trading" and similar returned pages whose purpose is to sell a bot, a course, or an exchange referral. One example surfaced in search: a "Small Account Position Calculator" for accounts under $5,000 ([BLOG] <https://www.fullswing.ai/small-account>) — a tool page, not evidence.

**The honest finding [REASONING]:** the question "what strategy design is appropriate for a $1,000–2,000 account?" is not a question the literature has asked. The literature asks "do retail traders profit?" and the answer is mostly no. The absence of small-account-specific research is itself informative: the constraints that actually bind a small account are **fixed costs that do not scale down** (fee tiers, tax filing, software, and the owner's time), and those are cost-structure questions rather than strategy-design questions.

I am explicitly flagging this as a **negative finding** rather than filling the gap with plausible-sounding design advice.

---

## 3. Q2 — Minimum viable account size once fixed costs are counted

### 3.1 What I can verify

| Cost component | Verified position for this account | Source |
|---|---|---|
| Exchange minimum order size | ≈$3–10 CAD — **not binding** at $300 stakes | [VERIFIED-URL] Kraken `AssetPairs` API |
| Bid-ask spread | 0.01–0.03% — **not the dominant cost** | [VERIFIED-URL] Kraken `Ticker` API |
| Trading fee | 0.40% maker / 0.80% taker, Tier 1, **cannot be improved** | [VERIFIED-URL] Kraken fee tiers |
| Fee-tier upgrade | Requires $2,500/30-day volume or $20k AoP — **out of reach** | [VERIFIED-URL] Kraken fee tiers |
| Tax filing / record-keeping | Per-transaction records, 6-year retention; business-income risk rises with turnover | [VERIFIED-URL] CRA |
| Software / hosting | Freqtrade is free; hosting is the operator's own hardware | [LOCAL] |
| Operator time | Not quantified by any source I found | — |

### 3.2 Why I cannot give a single "minimum viable account size" number

**No source I found states one, and I will not invent one.** [REASONING] The reason is that on Kraken CAD pairs the *only* binding size-related cost is the fee tier — and that threshold ($2,500/30d volume) is a function of *turnover*, not of account size. A $500 account that traded $2,500/month would reach Tier 2; a $50,000 account that bought and held would not. So "minimum viable account size" is the wrong frame: the binding quantity is **turnover relative to fee tier**, not account size.

**The one size-related effect I can demonstrate [REASONING]:** position concentration. With `max_open_trades: 3` and a 90% tradable ratio, each position is ~30% of the wallet. On a $1,000 account that is a $300 position; the minimum order sizes are ~$3–10, so granularity is fine. But a 3-position cap on 4 whitelisted pairs means the bot can never hold the whole universe at once — a real constraint of the *configuration*, not of the exchange.

### 3.3 What practitioners actually say — and how much of it is marketing

[PRACTITIONER] The delegated thread surveyed practitioner sources and reported that **independent practitioners cluster at $2,000–$10,000+** (drawing on r/algotrading discussions), while **every source claiming a $500–$2,000 "absolute minimum" for crypto bots turned out to be marketing** — including a referral link with a promo code, a $199–249/month bot vendor, and a forum thread that the site itself labels "Commercial Content."

**[REASONING] The most important sentence in this section: no independent source found in this entire research effort claims profitability at $1,000–$2,000.** That is not proof of impossibility, but it is a striking absence given how many vendors sell into exactly that account size. The vendors' business model does not require the account to be profitable.

[VERIFIED-URL] **Freqtrade itself documents no minimum account size** — it explicitly delegates the question to the exchange's own limits. Its documentation gives the "Minimum trade stake" formula (accounting for `tradable_balance_ratio`, `amount_reserve_percent`, and stoploss), notes that *"the calculated minimum stake-limit will never be more than 50% above the real limit,"* and applies a >30% rejection rule. Relevant defaults verified: `tradable_balance_ratio` **0.99** (*"reserve 1% for eventual fees"*), `amount_reserve_percent` **0.05**, `last_stake_amount_min_ratio` **0.5** (explicitly to avoid dust).

**[REASONING] A notable divergence [LOCAL]:** Freqtrade's default `tradable_balance_ratio` is **0.99**, but this repo sets **0.90**. That is a *more* conservative setting — 10% held back rather than 1% — which reduces each stake and therefore raises the effective-minimum-stake risk discussed in §1.3. It is a defensible choice for a small account, but it is a choice, and it interacts with the minimum-stake issue.

---

## 4. Q3 — Which strategy classes are structurally better for small accounts?

Ranked by **fee drag per unit of exposure**, which is the dimension that matters at Tier 1. All fee arithmetic below is **[REASONING]** built on the [VERIFIED-URL] 0.40%/0.80% Tier 1 rates and 0.90% maker round trip.

| Class | Turnover | Fee drag | Evidence position |
|---|---|---|---|
| **Buy-and-hold** | ~zero | 0.45% at entry, 0.45% at exit — once | Benchmark. Nothing to beat it except a real edge. |
| **DCA** | one buy per contribution | **0.45% per dollar contributed, one time** | Fee-cheapest active-ish approach. Cannot fix a bad asset; only spreads timing risk. |
| **Periodic rebalancing** | proportional to dispersion, not position size | ~0.25%/yr measured (see §4.1) | Structurally the most fee-efficient *systematic* rule I measured. |
| **Low-frequency trend following** | ~10 trades/yr here | **~2.7%/yr** at 30% stake | The bot's class. Fees survivable; edge unproven. |
| **Mean reversion / range trading** | high | fatal at Tier 1 | Highest turnover → worst fee exposure. Avoid. |

### 4.1 What I measured on the actual pairs

[REASONING] — my own computation on [VERIFIED-URL] Kraken daily OHLC fetched this session (`https://api.kraken.com/0/public/OHLC?pair=XBTCAD&interval=1440`, same for ETHCAD, SOLCAD, XXRPZCAD). Window 2024-09-28 → 2026-09-18 (721 daily candles), the same window as the bot's backtest. Fee 0.45%/side applied to every traded leg.

| Rule | Total return | Max DD | Sharpe | Fees paid (% of initial) |
|---|---|---|---|---|
| 3-pair equal weight, buy & hold (BTC/ETH/XRP) | **+53.06%** | −63.51% | 0.65 | 0.00% |
| 3-pair, rebalance quarterly | +70.69% | −61.91% | 0.75 | **1.05%** |
| 3-pair, rebalance monthly | +64.77% | −61.46% | 0.72 | 1.64% |
| 3-pair, rebalance weekly | +59.76% | −61.66% | 0.69 | 2.61% |
| **Bot (reported)** | **+13.67%** | **−8.83%** | 0.14 | ~3.78% |

**Two robust findings here:**

1. **Rebalancing's fee drag is trivially small even at weekly frequency** — 2.61% of initial capital over 17 months (102 rebalances). This is because a rebalance trades only the *drift*, not the whole position. Compare the bot: 14 trades cost ~3.78% of the wallet. **The bot pays more in fees with 14 trades than a weekly-rebalanced portfolio pays with 102.** [REASONING]
2. **The rebalancing *premium* in this window was large but is window-specific.** Quarterly rebalancing beat buy-and-hold by +17.6pp here. That result is driven by the extreme dispersion of the window (XRP +133%, ETH −0.2%) and it reverses if SOL is included. It is a **one-window observation, not an established edge** — I would not rely on it.

### 4.2 Momentum in crypto — the one peer-reviewed supportive result

[VERIFIED-URL] Liu, Tsyvinski & Wu, "Common Risk Factors in Cryptocurrency", NBER Working Paper 25882 (May 2019), published in *The Journal of Finance* 77(2), 2022, pp. 1133–1177, DOI 10.1111/jofi.13119 — <https://www.nber.org/papers/w25882>

Verbatim abstract: *"We find that three factors – cryptocurrency market, size, and momentum – capture the cross-sectional expected cryptocurrency returns. We consider a comprehensive list of price- and market-related factors in the stock market, and construct their cryptocurrency counterparts. Nine cryptocurrency factors form successful long-short strategies that generate sizable and statistically significant excess returns. We show that all of these strategies are accounted for by the cryptocurrency three-factor model."*

**This is [PEER-REVIEWED] and it is genuinely supportive of the *idea* that momentum exists in crypto. But it does not validate this bot, and the differences matter [REASONING]:**
- It is a **cross-sectional long-short** strategy across a large universe of coins — not a long-only 20-day breakout on 4 pairs.
- Long-short is **not available** on Kraken Canada (spot only, no shorting) [LOCAL: `config/canada_kraken.json` documents this].
- **I verified the abstract only.** I did **not** verify whether the reported excess returns are net of realistic retail transaction costs, nor the holding periods or universe size. Do not cite this as "momentum works net of fees for a small account."

### 4.3 Mean reversion — structural argument

**[REASONING]** Mean reversion requires many round trips to harvest small deviations, and each round trip costs 0.90% of the position at Tier 1. A mean-reversion strategy must reliably capture >0.90% gross per round trip just to break even. On daily candles that is conceivable; on intraday it is not. **The empirical confirmation of this argument is in §4.6**, which measures the actual crypto reversal edge against actual fee levels and finds it roughly 60× too small. §4.6 is the evidence; this subsection is only the arithmetic that predicts it.

### 4.4 The general turnover law — the strongest transferable evidence

> **Attribution note:** the sources in §4.4–4.6 were fetched and read by a **delegated research thread running in this session** (findings file: `research/small-account-strategy-classes.md`), not by me personally. I am preserving that thread's labels and have **not** independently re-fetched these. Treat them as **[VERIFIED-URL] by this session's research effort**, with the caveat that I did not personally open them.

**[PEER-REVIEWED]** Novy-Marx & Velikov (2016), *Review of Financial Studies* 29(1):104–147, read as NBER WP 20721 PDF — <https://www.nber.org/system/files/working_papers/w20721/w20721.pdf>

This is the single most useful piece of evidence in this report, because it is a **general, quantified law relating turnover to net returns** rather than a claim about one strategy.

- Verbatim rule: *"Transaction costs consequently generally reduce realized spreads by more than 1% of the monthly one-sided turnover, i.e., if the long side of a strategy turns over 20% per month, the realized long/short spread will be at least 20 bps per month lower."*
- Empirical threshold, verbatim: *"only two of the strategies that have more than 50% one-sided monthly turnover have significant net spreads."*
- Verified Table 3: Momentum gross **1.33%/mo**, turnover 34.52%/side/mo, costs **0.65%/mo**, net **0.68%/mo** — costs consumed **49%** of the gross edge.
- High-turnover anomalies went **outright negative**: Industry Momentum 0.93% → **−0.29%**; Short-run Reversals 0.37% → **−1.28%**.
- Low-turnover (annual rebalancing): costs only **0.03–0.11%/mo**.

**Applied to this account [REASONING]:** their test round trip was >50bp; this account's is **80bp — about 1.6× higher**. Scaling their threshold, survivable turnover falls to roughly **31% of notional per side per month**, and the **breakeven rule is that gross edge per round trip must exceed ~0.80% of the notional traded**. At a 5% gross annual edge, an account can afford roughly **6 full-notional round trips per year**.

**This account's position:** ~10 round trips/year at ~30% of the wallet each = **~3 full-notional round trips/year** — comfortably *inside* the survivable band. This is the quantitative confirmation of §8.3: **the bot's turnover is not the problem.**

### 4.5 Crypto-specific net-of-fee evidence — thinner than it should be, but one study is directly on point

**[PEER-REVIEWED]** Borgards (2021), *North American Journal of Economics and Finance* 57:101428 — the **only** crypto study the thread found reporting gross **and** net returns at a stated fee. Record: <https://ideas.repec.org/a/eee/ecofin/v57y2021ics1062940821000590.html>

- 20 coins vs S&P 500, Jan 2014 – Dec 2019. **Fee 0.2%/trade = 0.4% round trip** — half this account's assumption.
- 1-day long: gross **134.477%** → net **127.177%**.
- **Only 18.25 trades over 6 years ≈ 3 trades/year.** Drag = 18.25 × 0.400 ≈ 7.30pp. [REASONING] Doubling the fee to this account's 0.80% gives ~14.6pp over 6 years ≈ **2.4%/year — small.** This independently corroborates my §8.3 estimate of ~2.7%/year.
- **5-minute variant: gross +727.852% → net −1163.970%.** The entire edge, and then the capital, is consumed by fees.
- **Buy-and-hold over the same window: +185.959%, max DD −90.207%. The 1-day momentum strategy's net max DD was only −16.5%.**

**This is a striking independent corroboration of §8.2 [REASONING]:** in a peer-reviewed 6-year crypto study, low-frequency trend following **beat buy-and-hold decisively on drawdown but lost to it on total return** (+127% net vs +186%). That is exactly the pattern I computed for this bot over 2024–2026 (+13.67% with −8.83% DD versus +53.06% with −63.51% DD). **The pattern is real and it is not a fluke of this repo's backtest** — but note it means the strategy's *value proposition is drawdown reduction, not higher returns*, and that value only pays off if the operator cannot tolerate the drawdown.

**[PEER-REVIEWED]** Grobys, Kolari, Sandretto, Shahzad & Äijö (2025), *Financial Markets and Portfolio Management* 39:443–476, open access — <https://link.springer.com/content/pdf/10.1007/s11408-025-00474-9.pdf>

- Top-30 coins, weekly rebalancing, 2016–2023: **0.90%/week overall — statistically insignificant**; 1.74%/wk for 2016–Jul 2020 (significant at 10% only); **negative and insignificant after Jul 2020**.
- Dec 2020 crash month: **−255.23%**; **one outlier accounted for 37% of the compounded return.**
- Power-law tail index α < 3 → **variance is statistically undefined**, so Sharpe ratios are not well-behaved.
- **No transaction costs applied.** The thread documents the field's contradiction: Grobys & Sapkota (2019) found nothing, Liu (2020) reported 36%/wk, Liu (2022) ~3%/wk, Shen (2020) negative.

**[VERIFIED-URL]** Liu & Tsyvinski (NBER w24877; *RFS* 2021) — real time-series momentum: weekly top quintile **11.22%/wk** (Sharpe 0.45) vs bottom quintile 2.60%; magnitude halves to 7.18%/wk from 2013. **No transaction costs and no turnover reported, so it cannot be netted.** This is the key limitation: the headline crypto-momentum numbers that circulate are gross and un-nettable.

### 4.6 Mean reversion — cleanly demonstrated to fail on fees

**[VERIFIED-URL]** Kitron & Wengrowicz (2026), arXiv:2608.21888 (preprint) — <https://arxiv.org/pdf/2608.21888>

- 15-minute bars, **183 Binance pairs**: 90% show significant directional reversal, vs 2.7% of 187 US stocks.
- **Gross edge peaks near 1.3bp per trade against a 5bp cheapest-maker round trip** (10–20bp at taker).
- Verbatim: *"not one of the 183 crypto pairs clears even the 5bp maker band at any threshold, the median pair earns 0.46bp."*
- Verbatim: *"Explicit fees, not the quoted spread, are what bind here."*
- At 5-minute bars the edge worsens to 0.15bp.

**[REASONING]** At this account's 0.80% round trip (80bp), the mean-reversion edge is roughly **60× too small**. This is the cleanest quantitative confirmation of the structural argument in §4.3: mean reversion is the worst possible strategy class for a Tier 1 fee schedule.

### 4.7 Rebalancing — fee-viable, but the premium is near zero and not significant

**[PEER-REVIEWED]** El Bernoussi & Rockinger (2023), *Financial Markets and Portfolio Management* 37(2):121–160, open access — <https://link.springer.com/content/pdf/10.1007/s11408-022-00419-6.pdf>

- Theory: **Corollary 1 — buy-and-hold wins as long as ρ > −(SR)².**
- Their own worked magnitude, verbatim: *"the final difference is of the magnitude of 1.35bp, a very small difference in practice."*
- Actual data (monthly rebalancing, 1999–2021, starting at 100): **BH 128.40 · FW@0.5% TC 132.2 · FW@1% TC 128.6 (a tie) · FW@2% TC 121.8.**
- Verbatim: *"the null hypothesis of the SR of BH being equal to the SR of FW cannot be rejected in the long-run"*; bootstrap tests *"were not successful."*

**This is the most important corrective to my own §4.1 [REASONING]:** I measured quarterly rebalancing beating buy-and-hold by **+17.6pp** in the 2024–2026 crypto window. El Bernoussi & Rockinger's peer-reviewed result is that the rebalancing premium is on the order of **1.35 basis points per year**, is a **tie at ~1% transaction costs**, and that rebalancing's Sharpe is statistically **indistinguishable** from buy-and-hold. **My +17.6pp is therefore almost certainly a window-specific artifact, not a harvestable premium.** I am revising my own §4.1 conclusion downward accordingly: rebalancing's real, defensible merits are (a) very low fee drag and (b) risk control — not a return premium.

[VERIFIED-URL] Sornmayura, Sakolvieng & Numgaroonaroonroj (2024), *GATR Journal of Finance and Banking Review* 8(4):1–16 (low-tier publisher, no costs modelled): of 10,000 portfolios across 7 assets, only **daily** rebalancing and 5%/10% threshold rules were significantly better than buy-and-hold; **weekly, monthly and 15%-threshold rules were not significant.** Mean daily Sharpe: threshold-5% 0.0715 > weekly 0.0695 > monthly 0.0690 > **buy-and-hold 0.06856**. [REASONING] The only significant winners are the highest-turnover options, which are precisely the ones fees would kill; the fee-neutral options show no measurable edge.

### 4.8 DCA — what the evidence actually says

**[PRACTITIONER]** Vanguard (2012), "Dollar-Cost Averaging Just Means Taking Risk Later" — <https://static.twentyoverten.com/5980d16bbfb1c93238ad9c24/rJpQmY8o7/Dollar-Cost-Averaging-Just-Means-Taking-Risk-Later-Vanguard.pdf>

- Lump-sum investing (LSI) beat 12-month DCA in **67% of US rolling windows** (1926–2011), 67% UK, 66% Australia.
- Magnitude: US terminal **$2,450,264 (LSI) vs $2,395,824 (DCA) = LSI 2.3% more**; UK 2.2%; Australia 1.3%.
- Over 36-month DCA windows, LSI won **~90%** of spans. LSI was also better risk-adjusted.
- Dispersion is wide (5th percentile −$203,776), and DCA **did** help in downturns.
- Vanguard distinguishes windfall-DCA from paycheck-DCA, calling the latter *"a prudent way to invest... the only sound alternative."*

**[REASONING] The fee point that matters most for a small account:** DCA **does not reduce fee drag per dollar traded**. $1,500 invested once costs $12.00 in fees at 0.80%; $125 × 12 monthly contributions also costs $12.00. DCA converts one round trip into N purchases but each dollar is still charged once. **DCA's benefit is reduced timing risk, not reduced fees** — and it is not free: it systematically underperforms lump-sum most of the time in exchange for protection in the minority of windows where the market falls.

---

## 5. Q4 — Should a small account trade systematically at all?

### 5.1 The strongest verified base-rate evidence

[VERIFIED-URL] ESMA, *Product Intervention Analysis: Measures on Contracts for Differences*, ESMA50-162-215, 1 June 2018 (58 pages, fetched and text-extracted this session) — <https://www.esma.europa.eu/sites/default/files/library/esma50-162-215_product_intervention_analysis_cfds.pdf>

Verbatim from the document:
- *"A clear majority of investors lose money, despite the fact that most aim to realise positive returns. This indicates that retail investors as a group overestimate the net returns they are likely to receive."*
- *"Evidence from NCAs... is that that in recent years a clear majority of client accounts have typically lost money on their investments, with substantial average losses per client, though with precise figures ranging between different jurisdictions."*
- *"Given that the evidence demonstrates that the majority of retail clients lose money trading CFDs..."*
- On costs: *"leverage magnifies the costs of investment – such as spreads, commissions or financing charges... leverage is associated with higher volumes of trading by investors, increasing trading costs via repeated entering and exiting of positions."*

**Precision note, and a correction to my own earlier draft:** the ESMA *analysis* document (ESMA50-162-215, which I fetched and extracted myself) says "a clear majority" and explicitly declines a single figure — *"precise figures ranging between different jurisdictions."* **The specific 74–89% figure is not in that document.** However, a delegated research thread running in this session located it in a *different* ESMA document and verified it verbatim:

> **Attribution:** the ESMA press release, FCA, ASIC, BIS and Hasso et al. items below were fetched and verified by a **delegated thread in this session** (`research/small-account-base-rates.md`), which re-checked every number by exact-substring match against extracted source text. I did not personally re-open them.

**[VERIFIED-URL]** ESMA press release (2018) — <https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors>
Verbatim: **"74-89% of retail accounts typically lose money… average losses per client ranging from €1,600 to €29,000."** *(This closes a gap I had flagged as unverified in my first draft. Note the range is per-jurisdiction, which is exactly why the analysis document declined to give one number.)*

**[VERIFIED-URL]** FCA Consultation Paper CP16/40 — <https://www.fca.org.uk/publication/consultation/cp16-40.pdf>
Verbatim: **"over 80% of clients lost money… average result per client was a loss of £2,200"**, and **"82% of clients losing against 18% making a profit"** (random sample, eight CFD firms). The same document reports **France AMF 89%** losing (average €10,887, median €1,843) and **Ireland 75%** (average €6,900). Also relevant: **"inexperienced retail clients lose less money than experienced clients."** FCA PS19/18 later mandated the per-firm *"[insert percentage]% of retail investor accounts lose money"* disclosure.

**[VERIFIED-URL]** ASIC Report 626 (published 22 August 2019) — <https://download.asic.gov.au/media/5241548/rep626-published-22-august-2019.pdf>
Verbatim figures: **80% of binary-options clients lose money**, **72% of CFD clients**, **63% of margin FX clients**.
⚠️ **Correction:** ASIC **Report 693 is not the CFD report** — it is "Response to submissions on ASIC's internal dispute resolution data consultations." The thread disproved that premise using ASIC's own sitemap. Cite REP 626.

**[VERIFIED-URL]** FINRA / CFTC population-level US retail futures or forex profitability data: **NOT FOUND.** Open gap.

### 5.1b Crypto-specific base rates — the most relevant evidence, and it is not encouraging

**[VERIFIED-URL]** BIS Working Paper 1049, "Crypto trading and Bitcoin prices: evidence from a new database of retail adoption" — <https://www.bis.org/publ/work1049.htm>
Verbatim: **"an estimated 73-81% of retail investors have likely lost money on their initial investment."** Based on crypto-app data across 95 countries, 2015–2022.

**[VERIFIED-URL]** BIS Bulletin 69, "Crypto shocks and retail losses" — <https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf>
- Verbatim: **"a majority of crypto app users in nearly all economies made losses on their bitcoin holdings."**
- **Median investor lost $431 of $900 invested.**
- Verbatim: **"over four fifths of users would have lost money"** under a monthly-buying (DCA) strategy.
- Behavioural finding: retail users **bought** into the Terra/Luna and FTX collapses while large/sophisticated investors **sold**.

**[PEER-REVIEWED]** Hasso, Pelster & Breitmayer (2019), *Journal of Behavioral and Experimental Finance* 23:64–74 — <https://eprints.qut.edu.au/129185/1/Who%20trades%20cryptocurrencies.pdf>
- **465,926 brokerage accounts.** Men traded more and more speculatively and earned lower returns.
- Two findings that bear directly on this bot: **performance was unrelated to the number of trades**, and **returns correlated positively with holding time.**
- Caveat: weekly raw returns of 0.004%–0.26% are **gross, not net of fees**.

**[REASONING] Why these three matter more than the CFD data:** they are **spot crypto** (the same instrument class as this account), they are population-scale, and the BIS Bulletin's DCA finding is directly on point — even a passive monthly-buying strategy left over four-fifths of users at a loss, because of *when* they bought. That is the honest counterweight to §4.8's DCA discussion: DCA reduces timing risk, it does not remove it.

**What does NOT exist [REASONING]:** there is no crypto equivalent of the Taiwan complete-exchange dataset — no study with the full order-level records and identity of every trader on a crypto exchange. The thread searched for Korean and Japanese retail crypto P&L studies and found none. **The crypto-specific literature is genuinely thin**, and I am reporting that as a finding rather than papering over it.

### 5.1c The one study that directly compares systematic crypto rules to buy-and-hold

**[PEER-REVIEWED]** Hudson & Urquhart (2021), *Annals of Operations Research* 297:191–220 — <https://centaur.reading.ac.uk/85715/8/Hudson-Urquhart2019_Article_TechnicalTradingAndCryptocurre.pdf>

This is the closest thing to the study the user asked for: **~15,000 technical trading rules** across 5 rule classes and 5 crypto markets.

- The rules show **statistically significant profitability** and, verbatim, **"substantially higher risk-adjusted returns than the simple buy-and-hold strategy"**, with smaller drawdowns. Breakeven transaction costs exceeded typical market costs.
- **But on raw annualized return, only 4.96%–15.69% of rules beat buy-and-hold.** (Table 7: CoinDesk 6.12%, Bitstamp 4.96%, Litecoin 11.49%, Ripple 15.69%, Ethereum 9.01%.)
- And critically: **"there is no predictability for Bitcoin in the out-of-sample period"** — the January–June 2018 out-of-sample window produced negative returns, Sharpe and Sortino for both Bitcoin markets.

**[REASONING] This is the single most decision-relevant result in the entire report, and it is two-sided.** A study of 15,000 rules finds that technical trading in crypto genuinely does improve *risk-adjusted* returns and reduce drawdowns — which is real support for the *class* of strategy this bot implements. But the same study finds that **85–95% of rules still lose to simply holding on raw return**, and that **Bitcoin specifically had no out-of-sample edge at all**. That is precisely the pattern I computed independently in §8.2: this bot beat buy-and-hold on drawdown (−8.83% vs −63.51%) and lost to it on return (+13.67% vs +53.06%). Two independent lines of evidence agree that **the honest case for systematic crypto trading is drawdown management, not return enhancement.**

**Applicability caveat [REASONING]:** CFD/forex evidence is about **leveraged derivatives with margin close-out**. This bot is **spot, no leverage, no liquidation**. That makes the bot structurally safer than a CFD account, and it means the CFD loss rates are a *directional* prior about retail active trading, not a direct prediction for this account. I am flagging this rather than over-claiming.

### 5.1d The largest independent audit of public Freqtrade strategies — the sharpest evidence in this report

**[VERIFIED-URL] I downloaded and independently recomputed this myself.** `Apex-prim/strategy-audit` — <https://github.com/Apex-prim/strategy-audit> — an out-of-sample audit of **895 public freqtrade strategies drawn from 53 repositories**, run through freqtrade itself. MIT licensed. Repo metadata I verified via the GitHub API: created **2026-08-20**, last pushed 2026-08-24, **3 stars, 0 forks**.

I fetched `LEDGER.csv` (**233,709 bytes, 895 data rows, 23 columns**) and computed the endpoints from the raw data rather than accepting the prose.

**My independent computation of the funnel:**

| Stage | Count |
|---|---|
| Total strategies audited | **895** |
| Dropped at the **first** gate (E0) | **878** |
| Reached E1 | 15 |
| **Survived every gate (E6)** | **2** |
| **…of those, beat buy-and-hold** | **0** |

**The two survivors, with their exact ledger values:**

| Strategy | OOS return | Buy-and-hold | OOS trades | Avg/trade | p | 95% CI lower |
|---|---|---|---|---|---|---|
| `ClucHAnix_5m_old` | **+111.99%** | +346.34% | 2,190 | +0.29% | 6.489e-05 | +0.1477 |
| `CombinedBinHClucAndMADV5` | **+106.91%** | +346.34% | 1,295 | +0.46% | 8.407e-15 | +0.3438 |

**This is the capstone result of the entire report, and it is sharper than "backtests are unreliable."** `CombinedBinHClucAndMADV5` has an edge that is statistically **bulletproof** by every test in §8.3b: **1,295 out-of-sample trades**, **+0.46%/trade**, **p = 8.4 × 10⁻¹⁵**, and a **positive 95% confidence-interval lower bound**. It survived lookahead detection, recursion detection, significance testing and economic screening. **And it still returned +106.91% against buy-and-hold's +346.34% — it lost to doing nothing by 239 percentage points.**

**[REASONING] That is the single most useful sentence in this research for the user's actual question.** A strategy can have a *genuine, statistically unassailable* edge and still be the wrong choice, because **the benchmark is not "zero," it is "buy and hold the coins."** The question for a small account is therefore not *"does my bot have an edge?"* but ***"does it beat doing nothing?"***

**A correction to the delegated thread's framing, which I verified myself.** The thread reported *"0 of 456 eligible ones beat buy-and-hold."* **That is not what the ledger says.** My computation from the CSV:

- **496** rows carry a `beats_bh` verdict (not 456). Of those, **28 are `True`** — **28 strategies did beat buy-and-hold.**
- **0 of the 2** that survived *every* gate beat buy-and-hold.

**The correct statement is stronger and more instructive than the incorrect one:** 28 strategies beat buy-and-hold, and **every single one of them failed a robustness gate.** Their failure reasons:

| Failed gate | Count | Meaning |
|---|---|---|
| `G3_is_sig` | 9 | in-sample result not significant |
| `G6_lookahead` | 6 | **lookahead bias** |
| `G1_trades` | 5 | too few trades |
| `G5_os_sig` | 3 | out-of-sample not significant |
| `G7_recursive` | 3 | **recursive / repainting** |
| `G2_is_pos` | 2 | in-sample not even positive |

**The lookahead failures are worth seeing, because they show what the trap looks like when you fall into it** — these are the "winners" that beat buy-and-hold and would top any leaderboard:

| Strategy | Claimed OOS return | Why it died |
|---|---|---|
| `NOTankAi_15_Cleaned_v2` | **+63,645,298%** | recursive |
| `NOTankAi_15_Cleaned` | +29,748,386% | recursive |
| `ichiV1` | +18,701,080% | lookahead |
| `grad` | +12,741,211% | lookahead |
| `LookaheadStrategy` | +2,578,140% | lookahead |
| `Rsiqui` | +410,480% | lookahead |

**[REASONING]** A strategy returning **63 million percent** is not a great strategy; it is a broken one. This is the same failure mode as the `DevilStra` lookahead example already in this repo's `research/gh/official_strats/` directory — and note that the top of the leaderboard is populated almost entirely by lookahead and recursion artifacts.

**[VERIFIED-URL] Corpus-wide flags I computed:** **455 of 895 strategies (51%)** are flagged `recursive = НАЙДЕНО` ("found"), and **40** are flagged `lookahead = НАЙДЕНО`. The largest single drops are at `G0_measured` (399) and `G2_is_pos` (298 — strategies that were not even positive in-sample).

**Caveats — stated prominently, because this is one unreplicated amateur audit:**
1. **Unreplicated, single author, 3 stars, 0 forks.** It is one person's pipeline, never independently reproduced.
2. **The author's own `freeze_guard.py` labels the corpus "repair-adjusted," not pre-registered** — the last two gates were added ~15 hours after the first result card. That is post-hoc modification.
3. **~65% of the corpus consists of copies**, so 895 is not 895 independent bets.
4. **The author's own year-split shows the aggregate verdict depends on market direction** — 0 of 5 beat buy-and-hold in up years, 5 of 5 in down years. **The conclusion is window-dependent**, exactly as §8.2 showed locally.
5. **The author documents having previously published wrong numbers** ("571 strategies, 55 clean"). That transparency distinguishes this from the folklore sources in §8.3c — but it also means these numbers are a *revision*.
6. **My own finding of an internal misalignment:** of the **55** rows dropped at `G6_lookahead`, **49 have `lookahead = НЕ ПРИМЕНИМА`** ("not applicable") — failed by a gate whose flag column says the check did not apply. Either "not applicable" defaults to failure, or the columns are out of sync. **I could not resolve which.**
7. **I could not reproduce the intermediate funnel** without the author's gate thresholds, and the README's prose ("66 survive / 4 beat") **contradicts its own ledger block**.

**[REASONING] How much weight should this carry?** As one unreplicated audit, it is suggestive, not conclusive. But it is **directionally consistent with every other independent line of evidence in this report**: Hudson & Urquhart's 15,000 rules (§5.1c), Borgards' 6-year crypto trend study (§4.5), the 888 Quantopian algorithms (§8.3c), and my own local computation (§8.2). **Five independent datasets, five different methods, one conclusion.**

### 5.2 Peer-reviewed day-trader evidence, with the cost assumption stated

[VERIFIED-URL] Barber, Lee, Liu, Odean & Zhang, "Do Day Traders Rationally Learn About Their Ability?", working paper dated October 2017, fetched as PDF from Odean's Berkeley faculty page and text-extracted this session — <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf>

Verbatim findings from the PDF I read:
- *"We analyze the performance of and learning by individual investors who engage in day trading in Taiwan from 1992 to 2006..."*
- *"we document that the aggregate performance of day traders is negative, that the vast majority of day traders are unprofitable, and many persist despite an extensive experience of losses"*
- *"using complete data for the Taiwan market, the aggregate performance of day traders **net of fees is negative in each of the 15 years** that we study"*
- On the profitable minority: *"only 9.81% (3.20%+6.61%) of day trading volume is generated by predictably profitable day traders... these predictably profitable traders constitute **less than 3% of all day traders** on an average day"*
- On a prior study by the same group: *"Barber, Lee, Liu, and Odean (2010) who identify a small subset of day traders (**less than 1% of the day trading population**) predictably earn profits"*
- Also: *"profitable traders with more than 40 days of day trading experience in the last year earn more than enough to cover their transaction costs."*

**Their cost assumption, verified verbatim:** *"commission paid by market participants to be about 10 basis points. We use the 10 basis points when calculating returns net of fees. Taiwan also imposes a transaction tax on stock sales of 0.3%."*

**[REASONING] — the comparison that matters for this account:** that study's round-trip cost is roughly 0.10% + 0.10% + 0.30% ≈ **0.50%**. This bot's Tier 1 maker round trip is **0.80%** (and 1.60% if it pays taker). So this account trades in a market that is **~1.6× to ~3.2× more expensive per round trip** than the Taiwanese equity market in which "the vast majority of day traders are unprofitable" and aggregate performance was negative in all 15 years studied. If retail day traders fail to profit at 0.50% round-trip cost, a small crypto account at 0.80–1.60% faces a strictly harder problem.

**Applicability caveat [REASONING]:** this is **day** trading (intraday round trips), not 10-trades-per-year trend following on daily candles. It establishes a base rate for *frequent* retail trading. It does not directly measure a low-frequency daily-candle strategy, and I am not claiming it does. Its relevance here is (a) it is a large, complete-population, net-of-cost study, and (b) it quantifies the profitability base rate for retail active trading.

**Additional verified figures on the same Taiwan data** (fetched and substring-verified by the delegated thread in this session):
- **[VERIFIED-URL]** Barber, Lee, Liu & Odean (2004 working paper) — <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trade%20040330.pdf>: verbatim **"in the typical six month period, more than eight out of ten day traders lose money"**; individuals were **>97% of day trading** on the TSE; and **"Heavy day traders earn gross profits, but their profits are not sufficient to cover transaction costs."**
- **[PEER-REVIEWED]** Same authors, *Journal of Financial Markets* (2014) — <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf>: complete TSE data 1992–2006, ~**450,000** individuals day trading per year; **~20% earn profits net of fees in the typical year**, but **"less than 1% of the day trader population is able to predictably and reliably earn positive abnormal returns net of fees"** (≈4,000 of 450,000; robustness range 1,000–4,000). Top 500 traders: **61.3 bps/day before fees, 37.9 after**; bottom: **−11.5 / −28.9 bps**.
- **[PUBLISHER-METADATA]** "Learning, Fast or Slow", *Review of Asset Pricing Studies* (2019), paywalled with no open-access copy — DOI <https://doi.org/10.1093/rapstu/raz006>: **"74% of day trading volume is generated by traders with a history of losses; and 97% of day traders are likely to lose money in future day trading."** *(Publisher metadata only — body text not read.)*

**[REASONING] The single most important pattern in this literature:** roughly **20% of day traders are profitable in a given year, but under 1% are profitable persistently.** The widely quoted "20% of day traders profit" is an **annualisation artifact**. Over any horizon that matters for judging a strategy, the base rate collapses to about 1%.

**The Brazilian futures study — the most extreme base rate found:**
**[VERIFIED-URL]** Chague, De-Losso & Giovannetti, "Day Trading for a Living?" — RePEc record <https://ideas.repec.org/p/fgv/eesptd/525.html>; text verified from an SSRN-version mirror <https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf> (the official FGV URL returned HTML, not a PDF).
- Sample: **all 19,646 people who began day trading in Brazil 2013–2015**; **1,551 (7.9%) traded more than 300 days.**
- Verbatim: **"Considering the performance net of exchange and brokerage fees, we find that 97% of all investors who persisted for more than 300 days lost money."**
- Of the survivors: only **17 (1.1%)** earned more than minimum wage (US$16/day); **8 (0.5%)** beat a bank teller's wage (US$54/day). Top earner US$310/day with a standard deviation of US$632–3,308.
- **Profit probability decreased monotonically with days traded**, which the authors note is *"contrary to what 'self-selection' and 'learning by doing' would suggest… patterns like this are usually found in gambling activities, such as the casino roulette."* Panel regressions found **"no evidence of learning."**

**[REASONING] Why this matters for a bot specifically:** the "no evidence of learning" finding is the empirical counterpart to the bot's own problem. A bot is an attempt to *encode* learning into rules. If humans with money at stake show no learning over 300+ days, that raises the bar for what a small parameter-swept rule set on 17 months of data can plausibly have discovered.

### 5.3 The theory that does apply

[VERIFIED-URL] William F. Sharpe, "The Arithmetic of Active Management", *Financial Analysts' Journal* 47(1), Jan/Feb 1991, pp. 7–9 — <https://web.stanford.edu/~wfsharpe/art/active/active.htm>

Verbatim: *"(1) before costs, the return on the average actively managed dollar will equal the return on the average passively managed dollar and (2) after costs, the return on the average actively managed dollar will be less than the return on the average passively managed dollar. These assertions will hold for any time period. Moreover, they depend only on the laws of addition, subtraction, multiplication and division."*

**What this does and does not say [REASONING]:**
- It is a **statement about the average**, not about any individual. Sharpe says so explicitly: *"It is perfectly possible for some active managers to beat their passive brethren, even after costs."* So this is **not** a proof that this bot must lose.
- It is nonetheless a strong prior: in aggregate, active crypto trading must underperform passive holding net of costs, because active traders pay more in fees and the fees are a transfer to the exchange.
- The theorem needs a well-defined "market" and a passive alternative. For this account the natural passive alternative is buy-and-hold of the same 4 pairs — which is exactly the benchmark the bot's backtest omits.

### 5.4 The comparison the backtest is missing — and it cuts both ways

See §8.2. The headline: **depending on the start date, buy-and-hold either crushed the bot or lost money while the bot gained.** Neither comparison establishes skill.

---

## 6. Q5 — The fee-drag problem, and what the literature proposes

### 6.1 Does any literature address fee drag *for small accounts* specifically?

**No peer-reviewed or working-paper treatment of fee drag for small retail accounts (sub-$10k) was found** — and this was searched for deliberately. The literature is **institutional-scale**. [REASONING] Applying its mechanisms to a $1,500 account is an **extrapolation**, and I am flagging it as such rather than presenting institutional results as if they were measured on small accounts.

**The closest thing to a source on retail fee disadvantage — and it is directly on point:**

**[PEER-REVIEWED]** Makarov & Schoar (2020), *Journal of Financial Economics* 135(2). Verbatim: *"all large exchanges state that for large traders they provide preferential customized fees that are far below the cost for retail investors… for large players the round-up trading costs should be within 50 to 75 basis points."*

**[REASONING] Why this is the single most relevant literature finding for Q5:** it establishes, in a peer-reviewed venue, that **exchanges price-discriminate against retail**, and it puts large-player round-trip costs at **50–75bp**. This account's Kraken round trip is **80bp (maker/maker) to 160bp (taker/taker)** — i.e. **the retail rate this account pays exceeds the wholesale rate that paper attributes to large players**, even in the best case. That is a structural, documented, retail-specific cost disadvantage, and it is the honest version of "small accounts are disadvantaged on fees."

**But the scale literature does NOT uniformly say small is doomed — and this cuts against the naive narrative:**

**[PEER-REVIEWED]** Pástor, Stambaugh & Taylor, "Scale and Skill in Active Management", NBER WP 19891 — <https://www.nber.org/papers/w19891>. Documents **decreasing returns to scale at the industry level**, with fund-level estimates *"insignificant"* once biases are avoided. **[REASONING] This is the opposite of a small-account-disadvantage result** — it says large size is a *handicap*, which superficially favours a small account. I am reporting it because it is real and because ignoring it would make this report one-sided. It does not rescue this bot, because the mechanism (capacity constraints on a strategy) requires a strategy with genuine skill to begin with, and §8.3 shows this one's edge is unproven.

**[PEER-REVIEWED]** Pástor, Stambaugh & Taylor, "Do Funds Make More When They Trade More?", NBER WP 20700 — finds turnover is **positively** related to benchmark-adjusted return. **[REASONING] This refutes any blanket "lower turnover is always better" claim**, including a naive reading of §4.4. The reconciliation: Novy-Marx & Velikov measure *net* spreads after costs across many strategies, while Pástor et al. study equity mutual funds with genuine skill and gross-of-cost measures. **Both can be true**: high turnover helps if you have skill, and destroys returns if you do not. A small account with an unproven edge should assume it is in the second case.

**A further honest caveat on §4.4 [REASONING]:** the delegated thread cited **Grinold (1989)**, **Magill–Constantinides (1976)** and **Constantinides (1986)** by DOI only, **without reading them** (paywalled; SSRN 403), and made no claims about their contents. The no-trade-band and partial-adjustment solutions referenced in §6.3 rest on the verified Qiao et al. (2023) quotation, not on those originals.

### 6.2 What the general literature does establish

[VERIFIED-URL] Sharpe (1991), above — the cost argument: active management costs more, therefore the average active dollar loses to the passive dollar after costs. This is the theoretical foundation of fee drag, stated as arithmetic rather than empirics.

[VERIFIED-URL] Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", *Journal of Portfolio Management* 40(5), 2014 (22 pages, fetched and text-extracted this session) — <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>

- The expected maximum Sharpe across N independent trials grows without bound under the null of zero skill, via their Equation (1) with the Euler–Mascheroni constant.
- Verbatim worked example: *"Should the strategist have made his discovery after running only N=46 independent trials, the investor may have allocated some funds, as [DSR] would have been 0.9505, above the 95% confidence level."* And the same strategy falls below the threshold after N=88 trials.
- Verbatim on trial discipline: *"every additional trial irremediably increases the probability of a false positive."* And the 1/e optimal-stopping rule: *"From the set of strategy configurations that are theoretically justifiable, sample a fraction 1/e (roughly 37%) of them at random and measure their performance. After that, keep drawing and measuring the performance of additional configurations from that set, one by one, until you find one that beats all of the previous."*

[VERIFIED-URL] Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance", *Notices of the AMS* 61(5), May 2014, pp. 458–471 (14 pages, fetched with a browser User-Agent and text-extracted this session) — <https://www.ams.org/notices/201405/rnoti-p458.pdf>

- **Theorem 2 (Minimum Backtest Length)** verified verbatim: *"The Minimum Backtest Length (MinBTL, in years) needed to avoid selecting a strategy with an IS Sharpe ratio of E[maxN] among N independent strategies with an expected OOS Sharpe ratio of zero is [formula] ≈ 2 ln[N] / E[maxN]²."*
- Verbatim application: *"if only five years of data are available, no more than forty-five independent model configurations should be tried... After trying only seven independent strategy configurations, the expected maximum SR IS is 1 for a two-year long backtest, while the expected SR OOS is 0."*
- Verbatim: *"a backtest which does not report the number of trials N used to identify the selected configuration makes it impossible to assess the risk of overfitting."*

**A subtle point that matters for this bot [REASONING]:** MinBTL tells you when a *high* in-sample Sharpe is suspicious. This bot's in-sample Sharpe is **0.14** — far *below* the E[max SR] ≈ 1 that 7 trials on a 2-year sample would be expected to produce under pure noise. So this backtest is **not** an example of a spectacular spurious Sharpe. It is the opposite failure mode: the result is too weak to be evidence of anything at all. Overfitting is the wrong diagnosis; **underpowering** is the right one.

### 6.3 What solutions are proposed, and what actually works here

| Proposed solution | Source | Applies to this bot? |
|---|---|---|
| Lower turnover / extend holding period | [REASONING] from Sharpe's cost argument | **Already done** — the repo's 5m→1d change was exactly this, and [LOCAL] the repo measures it as worth +3.7pp |
| Use maker orders (post-only) | [VERIFIED-URL] Kraken fee table (0.40% vs 0.80%) | **Already done** — `order_time_in_force: "PO"` |
| Widen rebalance bands / reduce rebalance frequency | [REASONING] from measured turnover | Applies if rebalancing replaces trading |
| Report the trial count N | [VERIFIED-URL] AMS 2014 | **Partly done** — [LOCAL] the repo tracks a trial budget |
| Require MinBTL before trusting a backtest | [VERIFIED-URL] AMS 2014 | **Not met** — see §8.3 |
| Trade enough to reach a better fee tier | (common practitioner advice) | **Arithmetically wrong** — see §7 |

---

## 6b. Q6 — Documented cases with actual numbers rather than marketing claims

> **Attribution:** the cases in §6b.1–6b.3 were located by a **delegated thread in this session** (`research/small-account-cases-and-backtest-reliability.md`). I independently re-verified the §6b.3 arithmetic and README claims myself (see below).

### 6b.1 The headline finding: independently verified small-account track records do not exist

**Zero audited or API-verified records of a $1,000–$2,000 crypto bot account were found.** Everything located is **self-reported**. Two structural reasons, both verified:

1. Freqtrade directs users to **Discord** for results — not indexed, not archivable, not checkable.
2. `github.com/freqtrade/freqtrade/discussions` returns **HTTP 404** — the venue where results would be posted does not exist.

**[REASONING] This is a genuine finding, not a search failure:** the places where small-account results are actually shared are precisely the places that cannot be audited. And Reddit was inaccessible from this environment, so community self-reports were not examined at all. **No crypto-specific bot-survival study appears to exist.**

### 6b.2 A documented $2,000 failure with real numbers

[PRACTITIONER] `francisx1999/crypto-trading-bot-postmortem` — <https://github.com/francisx1999/crypto-trading-bot-postmortem>

- **7 strategies, 24-month backtests, all negative**: returns from −1.16% to −95.48%.
- A grid bot went **"$2,000 → $90"** while showing a **93.3% win rate** — the classic signature of a strategy that wins small and loses catastrophically.
- Its capital-reality arithmetic is the most useful line: a **generous 30% APY on $2,000 = $50/month.**
- **[VERIFIED-URL] The thread verified via the GitHub API that the repository contains zero backtest artifacts** — the claimed "receipts" do not exist, and the README defers to "raw logs available on request."

**[REASONING] The $50/month figure deserves emphasis.** At the bot's *reported* 9.4% CAGR, a $1,500 account earns **~$141/year ≈ $12/month** — before tax, before the flat 10 CAD withdrawal fee (§1.6), and before the operator's time. **This is the single most decision-relevant number in the entire report, and it is not a fee problem or a strategy problem. It is an arithmetic problem:** the absolute dollar amounts available at this account size are too small to matter, which means the *rational* purpose of running this bot cannot be the income.

### 6b.3 A "documented case" whose numbers are internally impossible — and it is already in this repo

[LOCAL] This repository already holds `research/gh/Bananajoexxc_RegimeFilterStrategy-Freqtrade_tree.json` as a candidate strategy source. **[VERIFIED-URL]** I fetched its README myself — <https://raw.githubusercontent.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade/main/README.md>. It claims:

| Metric | Claimed |
|---|---|
| Total Return | **+1,450%** |
| Sharpe Ratio | 0.37 |
| Sortino Ratio | 0.87 |
| **Calmar Ratio** | **73.00** |
| Max Drawdown | 29.24% |
| Profit Factor | 1.40 |
| Total Trades | 204 |
| Win Rate | 40.2% |
| Period | Jul 2022 – Jan 2026 (3.5 years) |
| Settings | **95% stake, 1x leverage, SOL/USDT Futures on Binance, 1-hour** |

**[REASONING] I verified the arithmetic myself, and the claim is internally impossible on three independent counts:**
1. +1,450% over 3.5 years → CAGR = 15.5^(1/3.5) − 1 = **118.8%**. Calmar = CAGR / MaxDD = 118.8 / 29.24 = **4.06**, not 73.00. **The claimed Calmar is overstated by 18×.**
2. Conversely, Calmar 73.00 with a 29.24% MaxDD implies a CAGR of 73.00 × 0.2924 = **2,135%** — inconsistent with the stated +1,450% total return.
3. **A Calmar of 73.00 cannot coexist with a Sharpe of 0.37.** A Calmar that high describes a near-perfect return-per-drawdown profile; a Sharpe of 0.37 is mediocre. One of the two numbers is wrong.

**Two further problems [REASONING]:** the README still contains a `YOUR_USERNAME` placeholder, and the strategy is **SOL/USDT *futures* on Binance at 1-hour with 204 trades** — a different instrument, venue, timeframe and trade count from this spot/CAD/daily/4-pair bot. **Even if its numbers were correct, they would not transfer.** This is a concrete example of the user's own question: a "documented case" with published numbers, none of which survive inspection.

### 6b.4 The reporting asymmetry — and why it matters more than any single case

[PRACTITIONER] The thread's survey found a consistent pattern:

- **Repositories publishing losses have 1–3 stars.**
- **The most-adopted Freqtrade strategies — NostalgiaForInfinity, MoniGoMani — carry 9+ affiliate/referral links and publish no performance data at all.**
- The most search-visible "small capital live trading" case study presents anonymous "User A / User B" and a precise-sounding "First Week Summary" (28 trades, +4.56%) that is **dated 2023 inside a 2025 article** — illustrative template data attached to a course funnel.

**[REASONING] This asymmetry is the mechanism by which a small-account operator ends up with a bad strategy.** Losses are published by hobbyists with no audience; profits are *claimed* by vendors with referral incentives and no data. A person researching "does this work at $1,000?" encounters a literature that is **biased in both directions at once** — survivorship in what is advertised, and near-invisibility in what fails. The honest conclusion, which the thread states and I endorse: **the base rate is unknown, the mechanism of failure is well established, and the published evidence is systematically unreliable.**

### 6b.5 Community cases, recovered after the archive route was found

**Important methodological note:** Reddit was initially written off as inaccessible (reddit.com, old.reddit.com, the JSON API and every Redlib mirror all failed). The delegated thread found that the **Arctic Shift archive API** (`arctic-shift.photon-reddit.com/api/posts/ids?ids=<id>`) returns full post bodies, and pulled and read each post. **This partially resolves a gap I had flagged as closed** — see §9 item 20.

**[PRACTITIONER] The best-documented live small-account case found.** r/algotrading post `1tyc4nb` — **2,729 live trades over 60 days**:

| Target | Target value | Live result |
|---|---|---|
| Profit factor | ≥ 1.3 | **1.15** |
| Win rate | ≥ 45% | **33.6%** |
| Max losing streak | ≤ 5 | **18** |

The author's own verdict: *"**The system didn't lose money. It just never earned the right to scale. Verdict: weak edge.**"* Two of his lessons are independently valuable and echo this report's findings:
- *"nothing in a backtest punishes a strategy for failing to adapt"*
- *"at points, **100% of live positions sat in one coin (ADA), and I never decided that**"* — **[REASONING] the correlation-concentration risk that [LOCAL] this repo's own `strategy-count-and-overfitting-sources.md` documents (four pairs at 0.775 average pairwise correlation ≈ 1.3 effective bets) is not hypothetical; here it materialised in a live account.**

**[PRACTITIONER] The "few trades" trap, stated as a real person's question.** r/algotrading `1tdeu7b` (**score 112** — the most-engaged case found): **$1,000 paper account, 4 weeks, ~480 trades, "up about $25."** The author asks: *"Is 480 paper trades enough to have any confidence in going live, or am I kidding myself?"*

**[REASONING] The answer is no, and the arithmetic shows by how much.** +$25 on $1,000 over 480 trades = **0.0052% per trade**. By the SQN-is-the-t-statistic identity from §8.3b, significance at N=480 requires **mean/SD > 0.089**; his is roughly **0.003–0.005**, i.e. **about 20× short**. He has enough *trades* and nowhere near enough *edge per trade* — which is precisely the distinction this report is about, and it is the same trap the bot's 14 trades sit in, from the opposite direction.

**[PRACTITIONER] The fragility of the public record.** Four LLM agents each trading ~$1,000: Gemini **−30.85%** (118 trades), Claude −8.33%, GPT +12.75%, Grok **+9.09% on a 19.4% win rate over 36 trades**. **The thread verified via the archive metadata that this post now carries `removal_type: "deleted"`** — it has been removed from Reddit. **[REASONING]** This is a concrete demonstration that community evidence is *ephemeral*: a case can exist, be read, and then vanish, which means any survey of this literature is a snapshot of a shrinking record.

**[PRACTITIONER] The one case with published raw artifacts.** `farzinb502-jpg/freqtrade` PR #1 — the thread verified the body and **all 69 changed files** via the GitHub API (including `REPORT.md`, comparison CSVs, raw backtest zips and 13 log files). It tests a marketed "awesome-list" strategy, **TrendRider**, and finds it **−21.77%, profit factor 0.64**, where the engine's own sample strategy gained. Its verdict: *"**Do not go live.**"* and *"**Awesome-list marketing is not evidence.**"*

**[REASONING] This last case is the most valuable of the five**, because it is the only one where a third party can re-run the analysis. Note the direct relevance: [LOCAL] this repo's own `research/freqtrade-strategy-repos-report.md` audited exactly this kind of "awesome-list" strategy corpus. **The one case with artifacts is the one that found a marketed strategy failing.**

---

## 7. The fee-tier trap [REASONING]

From the [VERIFIED-URL] Kraken tier table: Tier 1 → Tier 2 requires $2,500 of 30-day spot volume and saves 0.10% maker per side.

- Saving per round trip from the upgrade: 0.10% × 2 = **0.20% of notional**
- Cost of one extra round trip at Tier 1: **0.90% of notional**

**Every additional trade you make to reach the tier costs 0.90% to save at most 0.20% on itself. It is never worth trading for the tier.** The upgrade is only valuable if you were already going to trade that volume for other reasons.

To book $2,500 of monthly volume, a $1,500 account must round-trip **1.67× its entire balance every month**. At Tier 1 maker rates that volume costs **$10.00/month = 0.67% of the account per month ≈ 8%/year** in fees — to earn a $2.50/month discount. The "trade more to get better fees" advice inverts the economics.

### 7.1 Annual fee drag as a function of turnover — computed by the delegated thread

[REASONING] on [VERIFIED-URL] Kraken rates, for a **1,500 CAD account**, showing the tier the volume would actually earn:

| Round trips/month | 30-day volume | Tier reached | Maker rate | Annual cost | **% of account/yr** | Taker equivalent |
|---|---|---|---|---|---|---|
| 1 | $3,000 | T2 | 0.30% | $108 | **7.2%** | 14.4% |
| 2 | $6,000 | T2 | 0.30% | $216 | **14.4%** | 28.8% |
| 4 | $12,000 | T3 | 0.22% | $317 | **21.1%** | 36.5% |
| 10 | $30,000 | T4 | 0.20% | $720 | **48.0%** | 84.0% |
| 20 | $60,000 | T5 | 0.15% | $1,080 | **72.0%** | 144.0% |

**The perverse tier interaction is the point:** from Tier 2 to Tier 5 the maker *rate* halves (0.30% → 0.15%), yet total cost rises from **7.2% to 72.0% of the account** because volume rises 20×. **The fee tier is a discount on a bill you should not be running up.** [REASONING]

**Where this bot actually sits:** ~10 round trips/year at ~30% of the wallet = **~0.25 round trips/month**, i.e. **well below the first row of that table**. Its ~2.7%/year fee drag (§8.3) is an order of magnitude better than any row here. **This is the quantitative case that the repo's 5m→1d timeframe change was the single most valuable decision made** — [LOCAL] the repo measures it as worth +3.7pp, and the table above shows why: at 5m frequencies the drag would have been in the 48–144% range, which is unsurvivable at any edge.

**A warning about the fee assumptions used almost everywhere else [VERIFIED-URL]:** the delegated thread found that **Qiao et al. (2023)** assume **0.1% per dollar**, Freqtrade's own documentation uses `--fee 0.001` (0.1%) as its example, and the crypto-bot blogs sampled use 0.1%. Kraken Tier 1 is **0.40%/0.80%** — so the standard assumption **understates per-leg cost by 4× (maker) to 8× (taker)**. [LOCAL] This repo's `config/base.json` correctly sets `"fee": 0.0045` and documents at length why the ccxt default of 0.0026 was wrong; **that correction is one of the most valuable things in the repository**, because nearly all published small-account fee arithmetic is wrong on its dominant term.

---

## 8. The local backtest: my own analysis

### 8.1 The result as recorded

[LOCAL] `research/turtle-risk-model-result.md`: real freqtrade 2026.8, 721 Kraken 1d candles, `--timerange 20240928-`, `--enable-protections`, fee 0.0045.

| variant | return | CAGR | trades | max DD | Sharpe |
|---|---|---|---|---|---|
| equal weight + 12% stop (shipped) | **+13.67%** | 9.41% | **14** | 8.83% | **0.14** |

### 8.2 Buy-and-hold over the identical window — computed this session

[REASONING], from [VERIFIED-URL] Kraken daily OHLC. Window 2024-09-28 → 2026-09-18.

**Comparison A — full 17-month window (2024-09-28):**

| | Total | Max DD | Sharpe |
|---|---|---|---|
| BTC/CAD buy & hold | +26.42% | −52.07% | 0.49 |
| ETH/CAD buy & hold | −0.21% | −67.22% | 0.34 |
| XRP/CAD buy & hold | +132.96% | −71.69% | 0.91 |
| **Equal-weight BTC/ETH/XRP buy & hold** | **+53.06%** | −63.51% | 0.65 |
| **Bot (reported)** | **+13.67%** | **−8.83%** | 0.14 |

→ On this window buy-and-hold **won by ~39pp**, and the bot's Sharpe (0.14) was far worse.

**Comparison B — the window in which all four whitelisted pairs existed (2024-11-27, SOL's listing date):**

| | Total | Max DD | Sharpe |
|---|---|---|---|
| BTC/CAD | −15.96% | −52.07% | −0.02 |
| ETH/CAD | −29.32% | −67.22% | 0.06 |
| SOL/CAD | −52.87% | −77.13% | −0.16 |
| XRP/CAD | −6.09% | −71.69% | 0.35 |
| **Equal-weight 4-pair buy & hold** | **−26.06%** | −63.00% | 0.03 |
| **Bot (reported)** | **+13.67%** | **−8.83%** | 0.14 |

→ On this window the bot **won by ~40pp** while buy-and-hold lost a quarter of the capital.

**Both numbers are true and they point in opposite directions.** [REASONING] This is the single most important analytical finding in this report: **the comparison is entirely a function of the start date, so neither result is evidence of skill.** The 2024-09-28 start captures a large run-up into the November 2024 peak; from that peak onward, holding lost money and the bot's cash-holding helped.

**Why the bot's low drawdown is not skill [REASONING]:** the bot was in cash most of the time (14 trades, ~30% of the wallet each, over 721 days). A mostly-cash portfolio has a low drawdown by construction. Its −8.83% DD versus −63.51% for buy-and-hold reflects **low exposure**, not risk management. Spot-only with no margin means that exposure cannot be scaled up to make the comparison like-for-like.

**Regime context [REASONING], from [VERIFIED-URL] Kraken OHLC:** this window was predominantly a drawdown market. BTC/CAD peaked at 175,500 on 2025-10-06 and ended 35.7% below that peak; BTC closed below its prior peak on **676 of 721 days (94%)**, with 256 days more than 30% below peak. A trend-follower that sits flat in a bear market is *supposed* to look good here.

### 8.3 The statistical problem: 14 trades cannot establish anything

[REASONING] — my own arithmetic. Inputs: 14 trades, 30% of wallet per trade, +13.67% net total, 0.90% round-trip cost.

- Net return on deployed stake: 13.67% / 0.30 = **+45.6%**
- Mean **net** per trade on stake: **+3.25%**
- Implied mean **gross** per trade: 3.25% + 0.90% = **+4.15%**
- Gross edge / fee hurdle: **4.6×** — i.e. the claimed edge is comfortably larger than the fee

So **fees are not what kills this strategy**; the sample is. The per-trade standard deviation is **not reported** in the repo's result, so I scanned plausible values:

| Assumed per-trade SD | t-statistic | Significant at 95%? | Trades needed for t = 1.96 |
|---|---|---|---|
| 10% | 1.22 | No | 37 |
| 15% | 0.81 | No | 82 |
| 20% | 0.61 | No | 146 |
| 25% | 0.49 | No | 227 |
| 30% | 0.41 | No | 327 |

**Under every plausible assumption, the result is statistically indistinguishable from zero.** To be detectable at 95% confidence you would need roughly **37–146 trades**, and this backtest has 14.

**Monte Carlo check [REASONING]:** simulating 200,000 zero-edge 14-trade samples, the probability of a sample producing ≥ +13.67% on the wallet is **20.8% (SD 15%), 26.9% (SD 20%), 31.2% (SD 25%)**. A result like this arises from pure luck roughly **one time in four**. This is not a marginal failure of significance; it is a result that carries almost no information.

**Consistency with the repo's own parameter sweep [LOCAL]:** neighbouring Donchian parameters produced −3.40%/mo to +4.65%/mo — the *sign* flips on arbitrary neighbouring numbers. That is the signature of noise, and the repo already says so.

### 8.3b A more rigorous version of the same calculation — and it is worse for the bot

> **Attribution:** the sources and the SQN derivation below come from a **delegated thread in this session** (`research/small-account-cases-and-backtest-reliability.md`), which downloaded and read each source.

**[VERIFIED-URL] Freqtrade's own documentation already quantifies this problem, and its example is a $1,000 account.** From the Freqtrade backtesting docs — <https://www.freqtrade.io/en/stable/backtesting/>:
- Freqtrade's `Mean profit p-value` is *"a one-sample Student's t-test... **Its underlying t-statistic is identical to `SQN`**."*
- Freqtrade then warns the test *"assumes trades are independent and identically distributed, which real strategies rarely are... so the figure is an **optimistic** lower bound."*
- **Its canonical worked example is a 1,000 USDT account with 77 trades, CAGR 92.41% and Sharpe 3.89 — whose p-value is 0.4768, which the docs describe as "not distinguishable from luck."**
- Also verified: *"All orders are filled at the requested price (**no slippage**)"*; backtesting *"will **never** replace running a strategy in dry-run mode"*; and exchange minimums can exceed **$50**.
- The Freqtrade FAQ answers *"I have made 12 trades... why is my total profit negative?"* with: *"**12 trades is just not enough to say anything**... it will **_always_ be a gamble**."*

**[REASONING] This is the most damning comparison in the report.** Freqtrade's own documentation takes a **77-trade, Sharpe-3.89** backtest and labels it **indistinguishable from luck**. This bot's backtest has **14 trades and Sharpe 0.14** — roughly **one-fifth the trades and one twenty-eighth the Sharpe**. The repo's result is far weaker than the example Freqtrade uses to warn people.

**Because SQN *is* the t-statistic, `t = √N × mean/SD`.** [REASONING] That yields a cleaner requirement than my §8.3 scan:

| Trades | mean/SD needed for p<0.05 | needed at the Harvey–Liu–Zhu hurdle t=3.0 |
|---|---|---|
| 14 (this bot) | 0.52 | 0.80 |
| 30 | 0.36 | 0.55 |
| 100 | 0.196 | 0.300 |
| 204 (the "1450%" strategy) | 0.137 | 0.210 |

A realistic trend-following strategy has mean/SD of roughly **0.1–0.2**, which implies **~200–1,000 trades** are needed before a real edge separates from luck. **This bot has 14.** My §8.3 estimate of 37–146 trades was *optimistic*; the more rigorous derivation puts the requirement an order of magnitude beyond what this backtest can supply.

**[PEER-REVIEWED] The multiple-testing hurdle is higher than 1.96.** Harvey, Liu & Zhu, *Review of Financial Studies* (2016), "…and the Cross-Section of Expected Returns" — <https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF>. From 316 factors: *"**a newly discovered factor today should have a t-statistic that exceeds 3.0**"*; *"a t-statistic of 2.0 is no longer appropriate."* Their appendix finds *"**about 71.1% of tried factors are discarded**."* **[REASONING]** Since [LOCAL] this repo ran ≥12 configurations on this dataset, the applicable hurdle is **t > 3.0, not 1.96** — which raises the required per-trade edge by ~53% and the required trade count by ~2.3×.

**[PREPRINT] Minimum Track Record Length.** Bailey & López de Prado, "The Sharpe Ratio Efficient Frontier" — <https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf>. Verbatim: *"**a 2.73 years track record is required for an annualized Sharpe of 2 to be considered greater than 1 at a 95% confidence level**"* (2.83 weekly, 3.24 monthly, 4.99 with hedge-fund skew/kurtosis). The thread reproduced 2.73/2.83/3.24 exactly from the standard IID form, which licenses the extension: **with only ~100 daily observations you need an annualised Sharpe above ~2.61 merely to beat zero at 95%.** This bot has 1.42 years and a Sharpe of **0.14**.

**[PREPRINT] And the base rate for what a "good-looking" backtest is worth.** Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting" — <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf>. On a **pure random walk**, **8,800 parameter combinations** produced an in-sample **Sharpe of 1.27** with PSR-Stat 2.83 (*"less than 1% probability that the true Sharpe ratio is below 0"*), yet **PBO = 55%** and **~53% of out-of-sample Sharpes were negative**. Their generic example: **78% of OOS Sharpes negative, PBO 74%**. Control cases: a genuinely planted effect gave PBO **13%**; a real strategy **0.04%**. **[REASONING] Note the direction of this result for this bot:** a Sharpe of 1.27 on a random walk is *still* 55% likely to be overfit. This bot's Sharpe is **0.14** — so it is not a case of a suspiciously good backtest. It is a case of a backtest with essentially no signal to be suspicious about.

### 8.3c The best available evidence on whether backtests survive live trading

**[PEER-REVIEWED]** Wiecki, Campbell, Lent & Stauth — **888 real Quantopian algorithms with true out-of-sample data** — <https://community.portfolio123.com/uploads/short-url/3WHpAUOzhCG8QAUez71HpoWnA62.pdf>

Verbatim findings:
- *"Sharpe ratio **offer little value in predicting out of sample performance (R² < 0.025)**"* — in-sample to out-of-sample Sharpe **R² = 0.02**.
- Annual returns: **weakly negative** relationship (R² = 0.015).
- Volatility R² = 0.67; max drawdown R² = 0.34.
- *"**the more backtesting a quant has done... the larger the discrepancy**."*

**[REASONING] This is the single most important empirical result for Q4 and Q6.** Across 888 real algorithms, **in-sample Sharpe explained about 2% of out-of-sample Sharpe** — statistically indistinguishable from nothing. What *did* persist was volatility and drawdown, which are properties of the *asset*, not of the strategy. **The practical implication: a backtest can tell you roughly how much a strategy will swing, but it cannot tell you whether it will make money.** The bot's −8.83% backtest drawdown is therefore the *most* transferable number in its backtest; its +13.67% return is the *least* transferable.

**[REASONING] A note on what I am deliberately NOT citing.** The frequently repeated claims that "**87%**" or "**90% of backtested strategies fail**" are **unsourced folklore**. The thread verified this by reading both pages that circulate them: one cites only Harvey–Liu–Zhu and Bailey et al., **neither of which contains 87%**; the other never sources "90%" and lists five uncited statistics. **Do not repeat these figures.** What the evidence actually supports is the mechanism (low predictive R², high PBO under search) — not a specific failure percentage. The honest statement is that **the base rate of backtest survival is not reliably known.**

### 8.4 What would actually settle it

[REASONING] and [LOCAL]:
1. **Report the trial count.** [VERIFIED-URL] AMS 2014 is explicit that a backtest without N cannot be assessed. [LOCAL] the repo already tracks this (8 trailing-stop sets + 4 sizing/stop cells = ≥12 configurations on a 1.42-year dataset), and by MinBTL, 7 trials is the ceiling for a 2-year backtest. **The trial budget for this dataset is spent.**
2. **Stop backtesting and collect out-of-sample trades.** At ~10 trades/year, reaching even the low end of the required sample (≈37 trades) takes ~3.5 years of live/dry-run. That is the real cost of evidence here.
3. **Always report the buy-and-hold benchmark on the same window.** §8.2 shows why: without it, the same +13.67% reads as a triumph or a failure depending on the start date.

---

## 8b. Practical implications for this specific account

Everything in this section is **[REASONING]** applied to verified inputs, except where a source is named.

### 8b.1 Start with the arithmetic nobody quotes

At the bot's own reported **9.4% CAGR**, a $1,500 account earns **~$141/year, or about $12/month** — before tax, before the flat **10 CAD** e-Transfer withdrawal fee (0.67% of the account, §1.6), and before the operator's time. At a *generous* 30% APY it would be **$37/month** ([PRACTITIONER] figure from the $2,000 post-mortem, §6b.2).

**This is the decisive number, and it is not a strategy problem.** No fee optimisation, parameter change, or strategy swap alters the fact that the dollar amounts available at this account size are small. The rational purpose of running this bot therefore **cannot be income** — it must be one of: learning, entertainment, or a deliberate bet that a working edge now will be worth more on a larger account later. **[REASONING]** Being explicit about which of those it is determines what counts as success, and it is the single most useful thing the operator can decide.

### 8b.2 What this bot's design already gets right — verified, not assumed

This deserves stating plainly, because the rest of this report is critical. On the evidence gathered, several of the repo's core decisions are **correct and well-supported**:

| Decision | Why the evidence supports it |
|---|---|
| **Daily candles, not 5m** | [LOCAL] The repo measures this as worth **+3.7pp**. [PEER-REVIEWED] Novy-Marx & Velikov's law (§4.4) puts the breakeven at ~0.80% gross per round trip; [PEER-REVIEWED] Borgards found a 5m crypto variant going from **+727% gross to −1164% net** (§4.5). Fee drag here is ~2.7%/yr — inside the survivable band. |
| **Post-only maker orders** | [VERIFIED-URL] Maker 0.40% vs taker 0.80% per side = **0.80% saved per round trip** (§1.1). Over ~10 trades/yr at 30% stake that is **~2.4%/yr — about a quarter of the entire reported 9.41% CAGR.** This is the largest single cost lever available, and it is already pulled. (For comparison, the fee drag actually paid, ~2.7%/yr, is **just under a third** of that CAGR.) |
| **`"fee": 0.0045` in the config** | [VERIFIED-URL] Nearly all published small-account fee math uses **0.1%**, understating Kraken by **4× (maker) to 8× (taker)** (§7.1). [LOCAL] The repo caught the ccxt default of 0.0026 being ~3× too optimistic. **This correction is one of the most valuable things in the repository.** |
| **No hyperopt; pre-specified Turtle 20/10** | [PEER-REVIEWED] Harvey–Liu–Zhu: the hurdle for a newly discovered factor is **t > 3.0**, and ~71% of tried factors are discarded (§8.3b). [LOCAL] Using parameters chosen *before* the data is exactly the discipline that survives this. |
| **Recording negative results** | [LOCAL] `turtle-risk-model-result.md` and the trailing-stop sweep are documented failures. Given §6b.4's reporting asymmetry, this is genuinely unusual and valuable. |
| **Protections, and `stoploss_on_exchange: false`** | [LOCAL] Consistent with avoiding Kraken's market-order stops; §1.4's tiny spreads mean spread is not the reason, but the taker fee is. |

**[REASONING] The repo has already solved the cost problem.** That is a real achievement and it is why §8.3's conclusion is *"the edge is unproven"* rather than *"the fees killed it."*

### 8b.3 What remains genuinely unestablished

**[REASONING] Only one thing: whether there is an edge.** 14 trades, Sharpe 0.14, and Freqtrade's own documentation labels a **77-trade, Sharpe-3.89** backtest as *"not distinguishable from luck"* (§8.3b). By the SQN-is-the-t-statistic identity, a realistic trend strategy needs roughly **200–1,000 trades**; at ~10 trades/year that is **20–100 years**.

**[REASONING] The honest implication is uncomfortable:** at this trade frequency, **this account can never generate enough evidence to justify its own strategy by backtest.** Dry-run and live trading are the only sources of new information, and they accumulate ~10 trades/year. So the choice is not "backtest more" — [LOCAL] the trial budget is already spent — it is "accept a multi-year, unproven experiment" or "reframe the objective."

### 8b.4 Concrete, evidence-linked actions

Ordered by value-per-effort, all **[REASONING]** unless sourced:

1. **Keep post-only. Never switch to market orders except for stops.** Worth ~0.80%/round trip (§1.1). Note [LOCAL] the repo's own finding that *"the Donchian exit almost always fires before either stop"* — which means the taker rate is rarely paid, so the effective blended cost is closer to 0.80% than 0.90%.
2. **Fund only by Interac e-Transfer. Never by debit card.** [VERIFIED-URL] e-Transfer deposit is **free**; debit card costs **0.25 CAD + 3.75%** — about **$56 on a $1,500 deposit**, which is ~4 round trips' worth of fees (§1.6).
3. **Do not trade to reach Tier 2.** Each extra round trip costs **0.90%** to save at most **0.20%** (§7). The tier is not reachable by trading profitably; it is reachable by growing the account or not at all.
4. **Reframe the success criterion from "is there an edge?" to "does it beat doing nothing?"** [VERIFIED-URL] This is the operational lesson of the 895-strategy audit (§5.1d): its best survivor had **1,295 out-of-sample trades, p = 8.4 × 10⁻¹⁵ and a positive CI lower bound** — an edge no statistician would dispute — and it still **lost to buy-and-hold by 239 percentage points.** [REASONING] For this bot, "doing nothing" means holding the same four pairs. So the benchmark is not zero, and it is not even a risk-free rate: it is **+53.06%** or **−26.06%** depending on the window (§8.2). **Always report buy-and-hold on the identical window, across multiple start dates.** Without it the +13.67% is uninterpretable.
5. **Verify the effective minimum stake on all four pairs empirically.** [PRACTITIONER] Freqtrade's maintainer reports minimum stakes *"as high as 60$"* on Kraken, 6–19× above what `ordermin` implies (§1.3). With `max_open_trades: 3` and `tradable_balance_ratio: 0.90`, stakes are ~$300–600, so the margin is real but not large — and the failure mode is **silently skipped trades**, not an error.
6. **Check whether the 1-candle `CooldownPeriod` creates a superficial-loss problem.** [VERIFIED-URL] A loss is denied if identical property is re-bought within **30 days** (§1.5). Re-entering a stopped-out pair the next day capitalises the loss into the new ACB instead of deducting it. **[REASONING] I have not quantified this and I am not recommending a change** — lengthening the cooldown alters strategy behaviour and could cost more in missed trades than it saves in tax. It is worth *knowing*.
7. **Set a time budget and a decision rule in advance.** [PEER-REVIEWED] Given IS→OOS Sharpe **R² = 0.02** across 888 real algorithms (§8.3c), no amount of backtesting will settle this. A pre-committed rule — e.g. "if dry-run/live has not produced a positive expectancy after N trades spanning M years, stop" — is the only protection against the persistence the Brazil study documents (*"no evidence of learning"*, §5.2).
8. **Consider what the evidence says the realistic alternatives are.** [PEER-REVIEWED] Hudson & Urquhart found only **4.96–15.69% of ~15,000 rules beat buy-and-hold on raw return**, and Bitcoin had **no out-of-sample predictability** (§5.1c). [PEER-REVIEWED] El Bernoussi & Rockinger put the rebalancing premium at **~1.35bp/year** (§4.7). **[REASONING]** If the objective is **return**, the evidence favours simply holding. If the objective is **drawdown reduction**, both this bot and periodic rebalancing deliver it — and rebalancing does so at **~0.25%/year** in fee drag versus the bot's ~2.7%, with no parameter risk. **The bot's defensible niche is drawdown reduction with an unproven return, and it is worth being honest that this is a narrow niche.**

### 8b.5 What would change my assessment

**[REASONING]** Stated so the conclusion is falsifiable rather than merely sceptical:
- **A pre-registered out-of-sample result** on data not used for any parameter choice, with the trial count disclosed.
- **Enough trades for t > 3.0** — realistically 200+, accumulated in dry-run/live, not backtest.
- **A buy-and-hold benchmark reported alongside, across multiple start dates**, showing the bot wins on return and not only on drawdown.
- **Confirmation that live fills match backtest fills.** [VERIFIED-URL] Freqtrade's docs state backtests assume *"no slippage"* and that backtesting *"will never replace running a strategy in dry-run mode."* Post-only orders face adverse selection, which no backtest models.

None of these is impossible. All of them take years at ~10 trades/year. That timescale — not the fee schedule — is the real constraint on this account.

---

## 9. What I could NOT verify (do not treat these as established)

Stated plainly, because filling these gaps with plausible numbers would be worse than leaving them open:

1. ~~**The "74–89% of retail CFD accounts lose money" figure.**~~ **CLOSED during this session** — verified verbatim in an ESMA press release (§5.1) by the delegated thread. My first draft had this as an open gap; it is now sourced. The nuance that survives: the figure is a **per-jurisdiction range**, not a single number, which is why ESMA's own analysis document declines to state one.
2. ~~**The current (2026) status of the proposed 66.67% capital gains inclusion rate.**~~ **CLOSED** — the delegated thread verified the full timeline and fetched the primary cancellation release: the rate is **50%**, the increase was **cancelled 2025-03-21**, and Bill C-15 (royal assent 2026-03-26) contained no inclusion-rate amendment. See §1.5. **Residual caveat:** CRA's own table ends at 2025, so there is no single CRA page stating the cancellation in words; the conclusion rests on the primary Finance release plus the bill's contents.
2b. **The dollar cost of filing N crypto trades in Canada** — not measured by any source found. The only figure available is a **vendor price ladder** (Koinly: CAD 69 → 399 across 100 → 10,000 transactions), which is a price, not a measured cost.
2c. **Whether the superficial loss rule's impact on this bot is material.** The mechanism is verified and the bot's design falls inside the 30-day window (§1.5), but **I did not compute the dollar impact** and found no source that does.
2d. **Whether foreign-exchange crypto holdings are T1135 specified foreign property** — not verified.
3. **Whether the CRA has a trade-count threshold for business-income classification.** The CRA page gives factors, not thresholds. No number found.
4. **Whether Liu–Tsyvinski–Wu's crypto momentum returns are net of transaction costs.** I verified the abstract only.
5. **The per-trade return standard deviation of this bot's 14 trades.** Not recorded in the repo. §8.3's t-statistics are therefore a *sensitivity scan*, not a single computed figure.
6. **Any independently verified small-account algorithmic trading track record.** I found none. **This is a substantive finding, not just a search failure:** every public "small account bot" P&L I encountered was self-reported, and the only large-scale verified retail datasets (Taiwan, Brazil, FCA/ASIC/ESMA disclosures, BIS crypto-app data) are all *negative* base rates. There is no public, API-verified, audited small-account algo track record that I could find.
7. **Any peer-reviewed study on strategy design specifically for small accounts.** I believe none exists; absence of evidence is reported as such.
8. **Kraken's CAD-specific minimum deposit rules** — not verified.
9. **The exact `web_search` failure** — the built-in search tool returned "No results found" for nearly all queries this session. All four research threads hit the same wall, and the delegated threads reported that Bing, Mojeek, Ecosia, Yandex, Startpage, Brave and dozens of SearXNG instances were bot-blocked; SSRN returns 403; `web_fetch` cannot read PDFs (HTTP 406). The workarounds that did function were `curl` + `pypdf` for PDFs, the **OpenAlex and Crossref APIs**, RePEc/IDEAS, and direct regulator URLs. **Consequence: undiscovered sources may exist.** Any claim in this report resting on "I could not find X" is limited by that.
10. **A crypto analogue of the Taiwan complete-exchange dataset.** No study with full order-level records and trader identity for a crypto exchange was found. Korean and Japanese retail crypto P&L studies were searched for and not found.
11. **FINRA / CFTC population-level US retail futures or forex profitability data** — searched for, not located.
12. **The most important missing crypto source:** "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market… under Realistic Assumptions" (*Journal of Financial Markets*, 2024) — **could not be opened** (ACFR/AUT PDF returns HTTP 403; only unreadable ResearchGate/Scribd copies). Its abstract claims many momentum portfolios earn **negative** profits after costs, which would materially strengthen §4.5. **Unverified — do not cite.**
13. **SSRN 3982120, "Rebalancing Premium in Cryptocurrencies"** — HTTP 403, unread. QuantPedia's tables derived from it are images. **No crypto rebalancing premium figure was verified**, and **no crypto study measuring rebalancing net of a stated fee was found at all.** This is a genuine hole in §4.7.
14. **Robinhood (JF 2022) basis-points-per-day figure** — the paper is closed access with no open-access copy. The **−4.7% average 20-day abnormal return for top stocks purchased each day** was verified from two agreeing publisher-deposited sources (OpenAlex + Crossref), but the thread explicitly **declined to derive a bps/day figure by division**, which is the right call.
15. **A discrepancy in the Chague et al. Brazil paper:** the figure for traders beating a bank teller's wage appears as **0.5%** in the SSRN text the thread read, but **0.4%** on the RePEc abstract page. I report 0.5% (the full-text value) and flag the conflict.
16. **Body text of "Learning, Fast or Slow" (RAPS 2019)** and of **BIS WP 1049** — the 97% and 73–81% figures come from publisher metadata / the BIS page summary respectively, not from the full documents. The **BIS Bulletin 69** figures were verified from the PDF itself.
17. **ASIC Report 693** — I originally listed it as a candidate CFD source in my research plan; the thread disproved that. **REP 693 is not the CFD report**; the correct source is **REP 626**. Corrected in §5.1.
18. **Constantinides (1979)** full text — JSTOR blocked; abstract only. **Sharpe (1991)** and **Grossman–Stiglitz** were not fetched by the strategy thread, so the limits-to-arbitrage argument in §4.4 rests on the verified Novy-Marx & Velikov quotation rather than the originals. *(I did personally verify Sharpe 1991 in full — see §5.3.)*
19. **A source discrepancy I could not resolve:** the "**73–81% of crypto investors lost money**" figure is attributed to **BIS WP 1049**, but a thread reports it is **not** in BIS Bulletin 69, and that BIS WP 1049's body was verified only from the BIS page summary. **The attribution is unresolved**; treat the number as page-summary-level evidence, not full-text.
20. ~~**Reddit, Discord, and Freqtrade GitHub Discussions were not examined**~~ **PARTIALLY RESOLVED.** The **Arctic Shift archive API** turned out to work where reddit.com, old.reddit.com, the JSON API and every Redlib mirror failed; community cases are now in §6b.5. **What remains genuinely unreachable:** **comment threads were not retrieved** — which is exactly where an inflated self-report gets challenged — and the **Freqtrade Discord, where this community actually talks, remains unarchivable and unaccessed. That is the single largest unreachable evidence source in this report.** Note also that one retrieved case now carries `removal_type: "deleted"`, so the public record is shrinking, not stable.
21. **The eToro / *Journal of Financial Economics* retail-crypto paper** was 403-blocked and unread. **Prop-firm pass rates** were searched for and not verified. **No crypto-specific bot-survival study appears to exist.**
22. **The base rate of backtest survival is genuinely unknown.** The popular "87%" and "90% of backtested strategies fail" figures are **unsourced folklore** — the thread verified this by reading both pages that circulate them (§8.3c). I therefore state the *mechanism* (low IS→OOS R², high PBO under search) and explicitly decline to give a percentage.
23. **The 895-strategy audit is unreplicated and I could not fully reproduce it.** I confirmed the endpoints and the exact survivor figures from `LEDGER.csv` myself (§5.1d), but **not** the intermediate funnel (the thread got 533/192/106 against the author's 496/158/83) because the author's gate thresholds are not published. The README's prose ("66 survive / 4 beat") **contradicts its own ledger**. And of the 55 rows dropped at `G6_lookahead`, **49 have the lookahead column set to "not applicable"** — an internal misalignment I could not resolve. Treat this source as **suggestive, not conclusive**, and note it is a single author's pipeline with 3 stars that nobody has reproduced.
24. **Two figures the delegated thread reported that my own computation contradicts.** The thread stated *"0 of 456 eligible strategies beat buy-and-hold."* My computation from the same CSV gives **496 rows with a `beats_bh` verdict, of which 28 are `True`**. I have used **my own verified numbers** throughout §5.1d and flagged the difference rather than adopting the more dramatic claim.

---

## 10. URLs used in this report

**Fetched and verified this session:**
- <https://support.kraken.com/articles/cross-platform-fee-tier-changes> — Kraken fee tiers, updated 2026-07-09
- <https://support.kraken.com/articles/360030303832-overview-of-fees-on-kraken> — Kraken fee overview
- <https://support.kraken.com/articles/kraken-faq-subscription-service-overview> — Kraken+ ($4.99/mo, excludes Pro/API), updated 2026-09-17
- <https://api.kraken.com/0/public/AssetPairs?pair=XBTCAD,ETHCAD,SOLCAD,XXRPZCAD> — minimum order sizes
- <https://api.kraken.com/0/public/Ticker?pair=XBTCAD,ETHCAD,SOLCAD,XXRPZCAD> — live spreads
- <https://api.kraken.com/0/public/OHLC?pair=XBTCAD&interval=1440> — daily candles (also ETHCAD, SOLCAD, XXRPZCAD)
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html> — CRA crypto income
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html> — CRA books and records
- <https://www.esma.europa.eu/sites/default/files/library/esma50-162-215_product_intervention_analysis_cfds.pdf> — ESMA CFD product intervention analysis
- <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf> — Barber, Lee, Liu, Odean & Zhang (2017 working paper), Taiwan day traders
- <https://www.kraken.com/ca/features/fee-schedule> — Kraken Canada fee schedule (confirms CAD pairs use the same tier table)
- <https://www.esma.europa.eu/press-news/esma-news/esma-adopts-final-product-intervention-measures-cfds-and-binary-options> — ESMA press release (does **not** contain the loss percentage)
- <https://web.stanford.edu/~wfsharpe/art/active/active.htm> — Sharpe (1991)
- <https://www.nber.org/papers/w25882> — Liu, Tsyvinski & Wu, crypto risk factors
- <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf> — Deflated Sharpe Ratio
- <https://www.ams.org/notices/201405/rnoti-p458.pdf> — MinBTL / Pseudo-Mathematics (required a browser User-Agent)

**Cited by this repo and re-verified by me in this session (PDF fetched and text-extracted):** the two López de Prado/Bailey items above. The repo's own `research/strategy-count-and-overfitting-sources.md` contains a much fuller, independently verified treatment of this literature and its URLs.

**Fetched and verified by a delegated research thread in this session (I did not personally re-open these):**
- <https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors> — ESMA press release, **the 74–89% figure**
- <https://www.fca.org.uk/publication/consultation/cp16-40.pdf> — FCA CP16/40, 82% of clients losing; AMF 89%; Ireland 75%
- <https://download.asic.gov.au/media/5241548/rep626-published-22-august-2019.pdf> — ASIC REP 626 (80% binary options, 72% CFD, 63% margin FX)
- <https://www.bis.org/publ/work1049.htm> — BIS WP 1049, 73–81% of retail crypto investors likely lost money
- <https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf> — BIS Bulletin 69, median investor lost $431 of $900
- <https://eprints.qut.edu.au/129185/1/Who%20trades%20cryptocurrencies.pdf> — Hasso, Pelster & Breitmayer (2019), 465,926 accounts
- <https://centaur.reading.ac.uk/85715/8/Hudson-Urquhart2019_Article_TechnicalTradingAndCryptocurre.pdf> — **Hudson & Urquhart (2021), 15,000 technical rules vs buy-and-hold in crypto**
- <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trade%20040330.pdf> — Barber, Lee, Liu & Odean (2004), "eight out of ten day traders lose money"
- <https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf> — JFM (2014), <1% predictably profitable net of fees
- <https://ideas.repec.org/p/fgv/eesptd/525.html> and <https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf> — Chague, De-Losso & Giovannetti, Brazil (97%)
- <https://www.nber.org/system/files/working_papers/w20721/w20721.pdf> — **Novy-Marx & Velikov (2016), the turnover/cost law**
- <https://ideas.repec.org/a/eee/ecofin/v57y2021ics1062940821000590.html> — Borgards (2021), crypto trend following gross vs net
- <https://link.springer.com/content/pdf/10.1007/s11408-025-00474-9.pdf> — Grobys et al. (2025), crypto momentum insignificant
- <https://link.springer.com/content/pdf/10.1007/s11408-022-00419-6.pdf> — El Bernoussi & Rockinger (2023), rebalancing premium ≈1.35bp
- <https://arxiv.org/pdf/2608.21888> — Kitron & Wengrowicz (2026), mean reversion fails on fees
- <https://static.twentyoverten.com/5980d16bbfb1c93238ad9c24/rJpQmY8o7/Dollar-Cost-Averaging-Just-Means-Taking-Risk-Later-Vanguard.pdf> — Vanguard (2012), DCA vs lump sum
- <https://www.nber.org/system/files/working_papers/w24877/w24877.pdf> — Liu & Tsyvinski, crypto time-series momentum

**Verified by delegated threads in this session (further sources):**
- <https://www.freqtrade.io/en/stable/backtesting/> — **Freqtrade's own p-value/SQN warning and its 77-trade "$1,000 account" example with p=0.4768**
- <https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/faq.md> — *"12 trades is just not enough to say anything"*
- <https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF> — Harvey, Liu & Zhu (2016), **t > 3.0 hurdle**, 71.1% of factors discarded
- <https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf> — Minimum Track Record Length (2.73 years for Sharpe 2)
- <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf> — Probability of Backtest Overfitting (8,800 random-walk configs → Sharpe 1.27, PBO 55%)
- <https://community.portfolio123.com/uploads/short-url/3WHpAUOzhCG8QAUez71HpoWnA62.pdf> — **Wiecki et al., 888 Quantopian algorithms, IS→OOS Sharpe R² = 0.02**
- <https://www.nber.org/papers/w19891> — Pástor, Stambaugh & Taylor, "Scale and Skill" (**large-fund diseconomies**)
- <https://www.nber.org/papers/w20700> — Pástor, Stambaugh & Taylor, "Do Funds Make More When They Trade More?" (**turnover positively related to return**)
- <https://eprints.lancs.ac.uk/id/eprint/205305/1/JEF_final_copy.pdf> — Qiao et al. (2023), fee-drag formula and no-trade-band solutions
- <https://support.kraken.com/articles/12425041458708-cost-minimum-for-trading> — Kraken cost minimum (1 CAD)
- <https://support.kraken.com/articles/360000381846> — Kraken Canada deposit fees (**debit card 0.25 + 3.75%**)
- <https://support.kraken.com/articles/360000423043> — Kraken Canada withdrawal fees (**e-Transfer flat 10 CAD**)
- <https://github.com/freqtrade/freqtrade/issues/7120> — maintainer on Kraken minimum stakes *"as high as 60$"*
- <https://github.com/francisx1999/crypto-trading-bot-postmortem> — $2,000 post-mortem, 7 strategies all negative
- <https://raw.githubusercontent.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade/main/README.md> — **the Calmar 73.00 claim I disproved by arithmetic** (also in this repo's `research/gh/`)
- <https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf> — BIS Bulletin 69
- <https://www.fca.org.uk/publication/consultation/cp16-40.pdf> — FCA CP16/40
- <https://download.asic.gov.au/media/5241548/rep626-published-22-august-2019.pdf> — ASIC REP 626
- <https://github.com/Apex-prim/strategy-audit> — **895-strategy audit; I recomputed the endpoints from `LEDGER.csv` myself** (<https://raw.githubusercontent.com/Apex-prim/strategy-audit/main/LEDGER.csv>)
- <https://github.com/farzinb502-jpg/freqtrade/pull/1> — the only community case with published raw artifacts ("TrendRider" → −21.77%, PF 0.64, verdict "do not go live")
- Arctic Shift Reddit archive API (`arctic-shift.photon-reddit.com/api/posts/ids?ids=<id>`) — the route that recovered Reddit posts after reddit.com, the JSON API and every Redlib mirror failed

**Explicitly NOT to be cited (unsourced folklore, verified as such):**
- "**87%** of backtested strategies fail" and "**90%** of trading bots fail" — the pages circulating these cite sources that do not contain the figures (§8.3c)
- "**0.25% maker / 0.40% taker**" as Kraken's base rate — **stale**; the current Tier 1 is 0.40%/0.80% (§1.1)

**Cited by this repo and re-verified by me in this session (PDF fetched and text-extracted):** the two López de Prado/Bailey items above. The repo's own `research/strategy-count-and-overfitting-sources.md` contains a much fuller, independently verified treatment of this literature and its URLs.

**Referenced but NOT verified (do not cite as evidence):**
- <https://www.fullswing.ai/small-account> — vendor tool page surfaced in search
- <https://www.mexc.com/learn/article/kraken-fees-explained-2026-...> — third-party fee summary
- <https://www.datawallet.com/crypto/kraken-fees-explained> — third-party fee summary
- Tzouvanas et al. (2020), "19.396% weekly, significant after transaction costs" — appears **only** in another paper's literature-review table; primary never opened. **Implausible; do not cite.**
- "Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market… under Realistic Assumptions" (*J. Financial Markets* 2024) — **HTTP 403, unread**
- SSRN 3982120 "Rebalancing Premium in Cryptocurrencies" — **HTTP 403, unread**
- <https://pomegra.io> — blog claiming "100 trades/year costs 20%"; its cited studies are unverifiable
