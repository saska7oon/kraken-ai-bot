# Canadian tax treatment of algorithmic crypto trading, and whether self-hosted bookkeeping makes USDT-quoted pairs viable

**Scope.** A Canadian resident running a self-hosted Freqtrade bot on Kraken Canada, spot only, ~$1,000–2,000 CAD account, currently trading BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD on daily candles with maker orders, ~14 trades in 17 months. Question: does self-hosted tax/bookkeeping software make USDT-quoted pairs viable despite the extra accounting burden?

**This document is not tax advice and contains no recommendation.** It reports what the rules and sources say. A qualified accountant familiar with Canadian crypto taxation should be consulted before acting.

---

## Labels used

| Label | Meaning |
|---|---|
| `[VERIFIED-URL]` | I fetched that exact source in this session and quote/extract from it directly. |
| `[VERIFIED-URL — delegated]` | A researcher I dispatched fetched that exact source this session; I did not open it myself. |
| `[CLAIM]` | Asserted by a source I could not fetch directly (paywalled/blocked), or a secondary/tertiary source. |
| `[REASONING]` | My own inference from verified premises. Not a sourced statement. |
| `[NOT VERIFIED]` | I tried and failed, or did not find, a source. Stated explicitly rather than filled in. |

---

## Headline finding (answers the framing question before the details)

**The premise cannot be executed on Kraken Canada, so the software question is moot on that specific venue.** `[VERIFIED-URL]`

Kraken's own regulatory page, "Where is Kraken licensed or regulated?" (last updated 16 September 2026), lists under **Canada → Cryptocurrency restrictions**: *"Cannot deposit, hold or trade ACA, AIN, AKE, … USDT, USTABLES, …"* — **USDT is explicitly on the prohibited list for Canadian clients.** Source: <https://support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated>

Kraken's support article "Asset delistings in Canada: USDT, DAI, WETH, WBTC and WAXL" (last updated 2 April 2025) states: *"We have suspended deposits, withdrawals and trading in Canada across all trading platforms for Tether (USDT), Dai (DAI), Wrapped Bitcoin (WBTC), Wrapped Ether (WETH), and Wrapped Axelar (WAXL)."* Deposits and trading ceased 30 November 2023 12:00 p.m. EST; withdrawal capability ceased 4 December 2023; and on 5 December 2023 *"any USDT, DAI, WBTC, WETH, WAXL balances remaining in your account were converted to US dollars (USD), at the prevailing market rate and credited to your USD wallet balance."* Source: <https://support.kraken.com/articles/trading-suspension-in-canada-for-usdt-dai-weth-wbtc-and-waxl>

`[REASONING]` So a Canadian resident cannot trade USDT pairs on Kraken Canada at all — not on thin liquidity grounds, but because the asset is blocked. **USDC is not on that prohibited list** and appears to be the available stablecoin; see Q7 for the evidence and its limits.

The tax analysis in Q1–Q5 below still stands as the general answer to "does the quote currency change the number of taxable events", and it applies directly to a USDC/CAD route.

---

## Q1 — Is a crypto-to-crypto trade a taxable disposition in Canada?

**Yes.** This is stated by CRA directly, not inferred from secondary summaries.

`[VERIFIED-URL]` CRA, *Reporting income from crypto-asset transactions* (page date 2025-12-02):
> "A disposition of a crypto-asset may occur when you do any of the following:
> - **Trade or exchange it for government-issued currency or another type of crypto-asset**
> - Use it to buy goods or services
> - Transfer ownership of it by way of gift or donation"

Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html>

Note the wording: **"government-issued currency *or another type of crypto-asset*"** — both legs are dispositions. A crypto-to-crypto swap is a disposition of the asset given up.

`[VERIFIED-URL]` CRA publishes a worked example on that same page titled **"Example – Capital gain or loss from trading one crypto-asset for another"**: the taxpayer buys 100 units of crypto-asset A for $20,600, paying with 2.5061 units of crypto-asset B (FMV $20,600) originally bought for $15,000. CRA computes:
> "$20,600 [fair market value of 2.5061 units of crypto-asset B on July 30, 2025] − $15,000 [adjusted cost base …] = $5,600 capital gain
> $5,600 capital gain taxed at 50% = $2,800 taxable capital gain"

`[VERIFIED-URL]` Two supporting points from the same CRA guide:
- Crypto is **not** government-issued currency. *"Since cryptocurrency is not government-issued currency, using cryptocurrency as payment for goods or services is treated as a barter transaction for income tax purposes."*
- Transfers between wallets you own are **not** dispositions: *"Some transactions do not result in a taxable disposition, such as transfer of crypto-assets between wallets that you own."*

`[VERIFIED-URL]` **Stablecoins are a crypto-asset category for CRA**, listed alongside payment tokens, utility tokens, security tokens and NFTs, and described as *"Crypto-assets that are designed specifically to provide stability within the crypto-asset ecosystem by being pegged to a commodity (like gold), or a government backed currency (such as the US Dollar), or by having its supply regulated by an algorithm."* Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/crypto-assets-tax-obligations.html>

`[REASONING]` The consequence that matters for this question: **CRA does not treat a stablecoin as government-issued currency.** USDT/USDC is a crypto-asset, so disposing of it is a disposition — which is what creates the extra events counted in Q2.

**Confidence:** high. This is CRA's own published position with a worked example, not a practitioner gloss.

---

## Q2 — Does the quote currency change the *number* of taxable events?

**Yes. Trading against a crypto quote currency roughly doubles the number of taxable events per completed trade, plus one extra event per conversion back to CAD.**

### Verified premises

1. `[VERIFIED-URL]` Selling the base asset is a disposition whether you receive CAD or a stablecoin: *"Trade or exchange it for government-issued currency **or another type of crypto-asset**."*
2. `[VERIFIED-URL]` A stablecoin is a crypto-asset, not government-issued currency (Q1). So **spending** a stablecoin to buy something is a disposition of the stablecoin.
3. `[REASONING]` Spending **CAD** (government-issued currency) to acquire a crypto-asset is an *acquisition*, not a disposition — CAD is not a capital property whose disposal is taxed.
4. `[VERIFIED-URL]` Each crypto-asset type is tracked as a separate asset with its own cost: *"If you hold **more than one type** of crypto-asset, each type is considered to be a separate asset and must be valued separately for inventory purposes."* Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/value-crypto.html>

### Event count per completed Freqtrade trade (one buy + one later sell)

| Leg | CAD-quoted route | USDT/USDC-quoted route |
|---|---|---|
| Convert CAD → stablecoin | — | Acquisition of stablecoin. **0 dispositions** |
| Buy base asset | Buy BTC with CAD → acquisition only. **0 dispositions** | Buy BTC with stablecoin → **dispose of the stablecoin (1)** + acquire BTC |
| Sell base asset | Sell BTC for CAD → **dispose of BTC (1)** | Sell BTC for stablecoin → **dispose of BTC (1)** + acquire stablecoin |
| **Per completed trade** | **1 taxable event** | **2 taxable events** |
| Convert stablecoin → CAD (on exit/withdrawal only) | — | **dispose of stablecoin (1)** per exit |

`[REASONING]` **The USDT/USDC route adds exactly one extra taxable event per completed trade** — the disposal of the quote stablecoin when it is spent to buy the base asset — **plus one extra event each time you convert the stablecoin back to CAD.** It does not add an event for the initial CAD→stablecoin funding leg (that is an acquisition).

At the observed rate of ~14 trades in 17 months (≈10/year):
- CAD-quoted: ≈ **10 taxable events/year**
- Stablecoin-quoted: ≈ **20 taxable events/year**, plus one per exit/withdrawal to CAD

### The critical nuance: more events ≠ proportionally more tax

`[REASONING]` The *incremental* events are disposals of a stablecoin whose ACB is approximately its CAD value, so their gain/loss is normally near zero. So:
- **Liability:** roughly unchanged from the extra events themselves (except for small peg-driven gains/losses and the fees/spread on the extra legs).
- **Burden:** roughly doubled — each extra event must be identified, valued in CAD at the transaction date, matched against pooled ACB, and included in the return.

`[REASONING]` One further consequence: CRA requires per-date CAD conversion, so each extra event creates an additional CAD-valuation point. `[VERIFIED-URL]` CRA: *"When calculating the capital gain or loss on the sale of capital property that was made in a foreign currency, you must convert: the proceeds of disposition to Canadian dollars using the exchange rate in effect at the time of the sale; the ACB of the property to Canadian dollars using the exchange rate in effect at the time the property was acquired; the outlays and expenses to Canadian dollars using the exchange rate in effect at the time they were incurred."* Source: <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/calculating-reporting-your-capital-gains-losses.html>

**Confidence:** the premises are `[VERIFIED-URL]`; **the arithmetic conclusion is `[REASONING]`.** CRA has not published a worked example of this paired structure, and I did not find any CRA statement specifically about the number of dispositions in a stablecoin-quoted bot.

---

## Q3 — Business income vs capital gain

### CRA's listed factors

`[VERIFIED-URL]` CRA's crypto guide states the general test and then lists **six** factors:
> "As introduced by Interpretation Bulletin IT-479R, you are generally considered to be carrying on a business if your course of conduct indicates that you are disposing of crypto-assets in a way capable of producing gains, with that object in view, and the transactions are carried out in a manner similar to a trader or dealer in securities.
> The following factors may indicate that you are carrying on a business:
> - **Frequency of transactions** – You have a history of extensive buying and selling of crypto-assets
> - **Period of ownership** – You hold your crypto-assets for a short period of time, and you turn them over quickly
> - **Knowledge of crypto-asset markets** – You have knowledge of, or experience in, crypto-asset markets
> - **Time spent** – You spend a substantial part of your time studying crypto-asset markets
> - **Financing** – You finance your crypto-asset purchases by some form of debt
> - **Advertising** – You advertise that you are willing to buy crypto-assets"

Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html>

`[VERIFIED-URL]` CRA explicitly qualifies that this is not a bright-line test: *"Whether you are carrying on a business or not must be determined on a case-by-case basis and consider all the factors of your transaction. However, an isolated crypto-asset transaction could be determined to be on account of business income when it is considered an adventure or concern in the nature of trade."* And: *"Generally, if a crypto-asset transaction is not made on account of business income, it would be considered capital in nature."*

`[VERIFIED-URL]` **CRA does not treat crypto as a security.** *"The information in these paragraphs may be relevant in determining whether your crypto-asset transactions are on account of income or capital depending on the nature of those assets. However, you should keep in mind that this does not mean that crypto-assets are necessarily securities (for example, shares and bonds) for income tax purposes."*

### The underlying bulletin (CRA points to it, and it lists 8 factors)

`[VERIFIED-URL]` Archived IT-479R, *Transactions in securities*, paragraph 11 lists **eight** factors (a)–(h): frequency of transactions; period of ownership; knowledge of securities markets; **security transactions form a part of a taxpayer's ordinary business**; time spent; financing; advertising; and, **in the case of shares, their nature** (normally speculative or non-dividend). Source: <https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html>

Two further passages from IT-479R matter:

`[VERIFIED-URL]` ¶12 — combination, not any single factor:
> "Although none of the individual factors in 11 above may be sufficient to characterize the activities of a taxpayer as a business, the combination of a number of those factors may well be sufficient for that purpose."

`[VERIFIED-URL]` ¶33 — an important default presumption:
> "Normally, however, such situations would be rare and the initial presumption will be that gains or losses made or incurred by a particular taxpayer or transactions in securities, having regard to the taxpayer's circumstances, are either all of a capital nature or are all of an income nature, as the case may be, and evidence will be required in support of any contrary reporting of such gains or losses."

`[VERIFIED-URL]` IT-479R ¶13 also notes that mere intention to profit is not enough: *"A taxpayer's intention to sell at a gain is not sufficient, by itself, to establish that the taxpayer was involved in an adventure or concern in the nature of trade."*

### Practical difference in tax owed

`[VERIFIED-URL]` **Capital treatment** — include half the gain:
> "If you have disposed of a crypto-asset on account of capital, you must include **half** of your capital gains (known as taxable capital gains) in your income for the year."
> "You are allowed to deduct half of your capital losses (known as allowable capital losses), but **only against your taxable capital gain**. As such, you cannot deduct your allowable capital losses against income from other sources, like employment income."

`[VERIFIED-URL]` CRA's 2025 capital gains calculation page repeats it with a number: *"Fifty percent of the capital gain would be taxable and you would report $1,220 as your taxable capital gain on line 12700."*

`[VERIFIED-URL]` **Business treatment** — include the full amount:
> "If you have disposed of a crypto-asset on account of business income, you must report the **full amount** of your profits (or loss) from the disposition in your tax return."

`[VERIFIED-URL]` **Inclusion rate, verified against CRA's own table.** CRA's capital-losses page carries a table "Inclusion rates by period of net capital loss incurred" whose final row reads **"From 2001 to 2025 | 1/2 (50%)"**, and its definitions page states *"Generally, the IR for 2025 is 1/2."* CRA's "New for 2025 for capital gains" page lists AMT, capital gains deferral and a co-op conversion deduction — **it does not list any inclusion-rate increase.** Sources: <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html>, <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/definitions-capital-gains.html>, <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/whats-new-capital-gains.html>

`[REASONING]` Because CRA's 2025 guidance still states 50% and its "what's new" page omits any rate change, the previously proposed two-thirds inclusion rate does not appear to be in effect for the 2025 tax year. **`[NOT VERIFIED]`** I could not independently fetch the Department of Finance announcement on that proposal — the URL I tried returned HTTP 404. Treat "the 2/3 increase was cancelled" as not independently confirmed by me; the *operative 50% rate* is `[VERIFIED-URL]`.

### Other practical differences

| | Capital | Business |
|---|---|---|
| Amount included | 50% of gain | 100% of profit |
| Losses | Only against taxable capital gains; carry back 3 yrs / forward indefinitely | Deductible against other income (non-capital loss rules) |
| Superficial loss rule | Applies (see Q4) | `[REASONING]` Appears not to apply — CRA frames it on "capital property" |
| Inventory valuation | n/a | Lower of cost/FMV, or FMV; must be consistent `[VERIFIED-URL]` |
| Reporting | Schedule 3 → line 12700 | Business income (T4002 / T2125) |

`[VERIFIED-URL]` Business inventory methods, CRA: *"Method 1: Value each item in the inventory at the cost when it was acquired or its fair market value at the end of the year, whichever is lower. Method 2: Value the entire inventory at its fair market value at the end of the year."* And for an adventure or concern in the nature of trade: *"you should value your inventory using the total cost at acquisition."* Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/value-crypto.html>

`[REASONING]` On the facts as described (≈10 trades/year, daily candles, no debt, no advertising, margin prohibited on Kraken Canada), the **frequency** and **financing** factors point away from business income, while **knowledge/time spent** could be argued either way for someone operating an automated bot. CRA's own framing is case-by-case. I am not characterising this taxpayer.

---

## Q4 — Actual annual reporting burden

### Records CRA requires

`[VERIFIED-URL]` CRA's exact list (page date 2025-11-10):
> "Crypto-asset transaction information includes:
> - The number of units and type of crypto-asset for each transaction
> - **The date and time of each transaction**
> - **The value of the crypto-asset (in Canadian dollars) at the time of each transaction**
> - A description of the nature of each transaction and the other party to the transaction (even if it is just their crypto-asset address)
> - The addresses associated with each digital wallet used
> - The beginning wallet balance (and its cost) and ending wallet balance for each crypto-asset for each year
>
> Associated receipts include: Accounting costs; Legal costs; **Third-party software costs**"
>
> "**If you use crypto-asset exchanges or other custodial platforms**, you should keep books and records of the following information:
> - Trade ledgers (buy, sell and swaps)
> - Transfer ledgers (deposits and withdrawals of crypto-assets and traditional, government issued currency)
> - Records supporting any other types of transactions that took place on the exchange"

Also from that page: retention *"at least six years from the end of the last taxation year"*; CRA *"encourages taxpayers to keep their records electronically"* and *"does not endorse specific products, but recommends exporting your transaction records regularly"*; and a warning aimed squarely at platform risk — *"regularly export a history of your activity to make sure you have adequate books and records in case the exchange ceases operating, stops offering services in Canada, or you lose access to your account."*

Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html>

`[REASONING]` Note that the CAD value requirement is **per transaction** — so the burden scales with the event count, which is exactly what the stablecoin route doubles (Q2).

### Adjusted cost base — CRA requires average-cost pooling, not FIFO

`[VERIFIED-URL]` This is the single most consequential accounting rule, and it is frequently got wrong:
> "Properties of a group are considered to be identical if each property in the group is the same as all the others. …
> You may buy and sell several identical properties at different prices over a period of time. If you do this, **you have to calculate the average cost of each property in the group at the time of each purchase to determine your adjusted cost base (ACB). Dispositions of identical properties do not affect the ACB.**
> The average cost is calculated by dividing the total cost of identical properties purchased (this is usually the cost of the property plus any expenses involved in acquiring it) by the total number of identical properties owned."

Source: <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/special-rules-other-transactions.html>

`[REASONING]` CRA's examples on that page are shares and mutual-fund units; crypto is not named there. However, CRA's crypto guide treats each crypto-asset type as a separate asset with its own cost (Q2, premise 4), which is consistent with pooling per asset. **`[NOT VERIFIED]`** I did not find a CRA statement saying in terms that the identical-properties averaging rule applies to crypto-assets.

`[REASONING]` **FIFO is not the CRA method for identical capital property.** A tool defaulting to FIFO will produce a different gain figure than CRA's required pooled average cost. This matters directly for Q5.

### Valuation method

`[VERIFIED-URL]` CRA does not mandate a specific rate source:
> "**In all cases, you must use a reasonable method for determining the value of your crypto-assets, even when a direct value is not readily available.** Generally, whichever method you choose, use it consistently from year to year and keep a record of how it was used to calculate a value. For example, you could choose an exchange rate taken from the same exchange broker you are using or an average of high/low/open/close values across a number of high-volume exchange brokers to determine the value and repeat that every year."

Source: <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/value-crypto.html>

`[REASONING]` This is permissive but demands documented consistency — which is an argument in favour of a deterministic tool over ad-hoc manual rates.

### T5008

`[VERIFIED-URL — delegated]` CRA's T5008 "securities mean" list and ITR 230(1) define "security" as a closed list (publicly traded shares, publicly traded debt obligations, government debt, prescribed debt obligations, publicly traded interests in partnerships/trusts, and options/contracts on those). **Crypto-assets and stablecoins are not in that list.** The T5008 box 15 type codes contain **no crypto code** — only a generic "MSC – Miscellaneous" — and CRA's T5008 pages contain zero mentions of crypto/virtual/digital currency/stablecoin. T5008 slips are due *"on or before the last day of February following the calendar year."* Box 20 carries CRA's own caveat: *"This amount may or may not reflect the investor's ACB."*

Sources (fetched by my delegated researcher this session): <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/completing-slips-summaries/financial-slips-summaries/return-securities-transactions-t5008/general-information.html>, <https://laws-lois.justice.gc.ca/eng/regulations/C.R.C.,_c._945/section-230.html>

`[REASONING]` So a T5008 is not the record that carries your crypto cost base even where one is issued, and its absence does not remove the reporting duty.

### T1135 (foreign property reporting)

`[VERIFIED-URL]` Threshold and basis — CRA's Q&A:
> "Is the $100,000 threshold based on the fair market value of the property? **No, it is based on the cost amount.** The cost amount is defined in subsection 248(1) of the *Income Tax Act* and generally is the adjusted cost base and not the fair market value."
> "Assume I held specified foreign property during the year with a cost amount of more than $100,000, but held less than $100,000 at the end of the year (or no longer held the property). Do I still have to file Form T1135? **Yes.** As long as you met the reporting requirement threshold of $100,000 **at any time in the year**, you must report on Form T1135 all specified foreign properties held during the year."
> Two-tier: Part A simplified for holdings under $250,000 throughout the year; Part B detailed for $250,000 or more at any time.

Source: <https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/information-been-moved/foreign-reporting/questions-answers-about-form-t1135.html>

`[VERIFIED-URL — delegated]` The statutory test (ITA s. 233.3(1)) is the **aggregate** cost amount of all specified foreign property exceeding $100,000 at any time in the year; penalties include s. 162(7) $25/day up to 100 days (min $100, max $2,500) and s. 162(10)(a)/(b) $500–$1,000/month up to 24 months. Source: <https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-233.3.html>

`[VERIFIED-URL]` **Situs test for intangible property**, from CRA's own Q&A: *"Shares of a corporation are intangible property and will be specified foreign property if they are situated, deposited or held outside Canada."*

**Crypto specifically — the position is not on canada.ca.** `[VERIFIED-URL]` CRA's crypto guide (all pages) contains **no** mention of T1135, T5008, s. 233.3, "specified foreign property" or "superficial"; and CRA's T1135 guidance pages contain no mention of crypto. The crypto/T1135 position exists only in CRA technical interpretations and roundtable answers:

- `[CLAIM]` CRA T.I. 2014-0561061E5 (16 April 2015): *"Digital currency is funds or intangible property and 'specified foreign property' includes funds or intangible property held outside of Canada"* — Position: yes.
- `[CLAIM]` 2022 IFA Roundtable Q.7 (2022-0926451C6): crypto *"would be specified foreign property … to the extent that it is situated, deposited or held outside of Canada"*; the situs question was described as *"currently under review"* pending OECD work.
- `[CLAIM]` 2023 CPA Canada Roundtable Q.22 (2023-0984901C6): *"where CTPs are resident in Canada and comply with Canadian regulations, cryptocurrency held through such CTPs for the benefit of Canadian clients will typically not be considered as 'situated, deposited or held' outside Canada."*

I could only read these via a **third-party republication** (<https://taxinterpretations.com>), not from canada.ca. They also carry CRA's standard disclaimer that they *"may not represent the current position of the CRA."*

`[REASONING]` **For this taxpayer, T1135 is not triggered.** The account is $1,000–2,000 CAD; the threshold is a $100,000 *cost amount* at any time in the year. Even holding the entire account in a stablecoin on a foreign venue would be two orders of magnitude below the threshold. T1135 only becomes a consideration if the portfolio grows by roughly 50×.

### Audit exposure

`[VERIFIED-URL — delegated]` CRA's own "Unnamed persons requirements" page states: *"Recently, the CRA issued UPRs to detect non-compliance in the construction, crypto-assets, e-commerce, and real estate industries."* The Coinsquare UPR (2020–21) was negotiated down to accounts valued at CAD$20,000+ on 31 December in 2014–2020 and the 16,500 largest accounts by trading volume. Source: <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/changes-your-business/unnamed-persons-requirements.html>

`[REASONING]` A ~$2,000 account is far below the historical disclosure thresholds, but the record-keeping duty applies regardless of size.

---

## Q5 — THE CRUX: does self-hosted software reduce tax **liability** or only **reporting burden**?

**It reduces reporting burden only. It does not and cannot reduce tax liability.**

### Why liability cannot change

`[REASONING]` Liability is determined by (a) the *Income Tax Act*, (b) CRA's interpretation of it, (c) the facts (notably capital vs income character), (d) the ACB, and (e) the inclusion rate. A bookkeeping program is a calculator and a record store. It has no effect on any of those five inputs. Specifically, software cannot:
- make a disposition not a disposition (Q1 — CRA's rule is statutory/administrative, not tool-dependent);
- change the 50% inclusion rate (Q3);
- change whether the activity is business income or capital (Q3 — a facts-and-circumstances determination);
- make the extra stablecoin dispositions in Q2 disappear.

`[VERIFIED-URL]` Rotki states this itself, in its own words:
> "rotki gives you accurate, auditable accounting and a clear report of taxable events. **It does not pre-fill your country's specific government forms, and it is not tax advice.**"
> "You or your accountant use that to file. **It is not a replacement for professional tax advice.**"

Source: <https://rotki.com/features/open-source-crypto-tax>

### What Rotki actually is and does

`[VERIFIED-URL]` Open-source and self-hosted. The GitHub README describes it as *"rotki: The Opensource, Self-Hosted Portfolio Manager"* and states *"rotki is open-source and distributed under the **AGPLv3 License**."* The GitHub API confirms `spdx_id: AGPL-3.0`, language Python, ~4,027 stars. Sources: <https://github.com/rotki/rotki>, <https://api.github.com/repos/rotki/rotki>

`[VERIFIED-URL]` Cost-basis methods — **it does support average cost**:
> "rotki supports four cost-basis methods: FIFO (first in, first out), LIFO (last in, first out), HIFO (highest in, first out) and **ACB (average cost basis)**. You pick the method and the accounting period in settings, and rotki applies it locally when it builds the report."

`[VERIFIED-URL]` Its documented settings include:
- **Cost Basis Method:** `FIFO`, `LIFO`, `HIFO`, or `ACB`
- **Crypto to crypto trades:** *"Whether swapping one crypto for another is a taxable event (it is in most jurisdictions)."*
- **Profit currency:** *"The fiat currency your taxes are denominated in (e.g., EUR, USD, GBP)."*
- **Include Fees in Cost Basis:** default `True`
- **Use Asset Collections in Cost Basis:** default `True`

Sources: <https://docs.rotki.com/usage-guides/settings/accounting.html>, <https://docs.rotki.com/usage-guides/tax-accounting/guide>

`[VERIFIED-URL]` **Its defaults are wrong for Canada and must be changed:**
> "Current Default Settings: **Based on German tax rules**; Uses first-in/first-out (FIFO) method for calculating profits/losses; **Treats crypto sales as tax-free after holding for 1 year**"

That last default is materially wrong for Canada (there is no Canadian holding-period exemption for crypto), and the FIFO default conflicts with CRA's average-cost pooling rule (Q4).

`[VERIFIED-URL]` Free local tier with limits; premium subscription raises limits. Reports export as CSV. CSV import is available for exchanges without API support. Source: <https://rotki.com/features/open-source-crypto-tax>

### The important subtlety: software can change the number you *report* — in both directions

`[REASONING]` This is where conflating liability and burden gets dangerous:

1. **A misconfigured tool can produce a *wrong* number.** With Rotki's default FIFO, the computed gain will differ from CRA's required pooled average cost. That is a compliance risk, not a tax saving. `[VERIFIED-URL]` CRA requires average cost (Q4); `[VERIFIED-URL]` Rotki defaults to FIFO.
2. **A correctly configured tool may cause you to report *more* gain than sloppy manual tracking**, because it captures events you would otherwise have missed. Correct reporting is not the same as a lower number.
3. **Correct ACB tracking can legitimately *lower* reported gain** versus a naive "proceeds minus original purchase price" approach — but that is correction of an error, not a reduction of the underlying liability.
4. **Nothing in the tool affects the Q2 event count.** Doubling the taxable events doubles the lines to compute and report; the extra stablecoin dispositions remain dispositions.

### What it genuinely buys

`[REASONING]` Real, but limited to burden and risk:
- replaces manual ACB pooling arithmetic, which is the most error-prone part;
- makes the per-transaction CAD valuation requirement (Q4) systematic rather than ad hoc;
- produces a defensible audit trail — and `[VERIFIED-URL]` CRA's records list explicitly names **"Third-party software costs"** as a receipt to keep, implying CRA expects tool use;
- reduces the chance of missing an event entirely;
- keeps data local (privacy) and keeps working if a venue delists an asset — relevant given Kraken's USDT delisting.

### What it does not do

`[VERIFIED-URL]` / `[REASONING]`
- No CRA e-filing or form pre-fill (Rotki says so explicitly).
- No Canadian-specific logic: I found no evidence of CRA/Schedule 3/T1135/T5008-specific handling. `[NOT VERIFIED]` I could not verify whether Rotki supports **CAD** as the profit currency — the documentation's examples name EUR, USD and GBP only. If CAD is unavailable, the CAD-denominated reporting CRA requires would still need a separate conversion step.
- `[REASONING]` No superficial-loss adjustment awareness for the 30-day rule; no capital-vs-income characterisation; no judgment about whether the activity is a business.
- You still complete Schedule 3 (or business-income forms) and the T1 yourself.

**Direct answer to the crux:** automating the bookkeeping makes the *reporting burden* of a stablecoin-quoted route tractable — the doubled event count in Q2 becomes an engineering problem rather than a spreadsheet nightmare. It does **nothing** to the *liability*, because the liability was never a function of how the records were kept. The concern that "crypto-to-crypto trades create extra tax accounting burden" is a **burden** concern, and software genuinely addresses it. It is not, and cannot be, a **liability** concern that software addresses.

---

## Q6 — Risks of holding USDT between trades, and Canadian stablecoin regulation

*(Note: on Kraken Canada this is largely moot — USDT cannot be held at all. Included because the user asked, and because the same analysis transfers to USDC.)*

### Depegging history

`[VERIFIED-URL]` CNBC, 12 May 2022 — *"The world's biggest stablecoin has dropped below its $1 peg"*:
> "Tether, the world's largest stablecoin, broke below its $1 peg Thursday amid panic in the crypto market. **The token sank to as low as 95 cents on some exchanges at around 3:15 a.m. ET.** It's meant to be pegged 1-to-1 to the U.S. dollar. **In the afternoon it traded at $0.998, according to Coin Metrics.** Tether's initial decline came after terraUSD, another stablecoin, plummeted below 30 cents Wednesday, which led to fears of a possible market contagion."

Source: <https://www.cnbc.com/2022/05/12/tether-usdt-stablecoin-drops-below-1-peg.html>

`[CLAIM]` Reuters, 12 May 2022, corroborates: *"Tether, a reserve-backed stablecoin which is supposed to be pegged 1:1 to the U.S. dollar, dropped to as low as 95 cents earlier in the global session, according to CoinMarketCap price data."* — <https://www.reuters.com/markets/us/crypto-collapse-intensifies-stablecoin-tether-slides-below-dollar-peg-2022-05-12/> (Reuters returned **HTTP 401** to my fetch, so this is a search-result citation, not a verified fetch.)

`[REASONING]` Character of the event: a **brief, shallow, intraday** depeg to ~$0.95 that recovered to ~$0.998 the same afternoon. It was not a permanent break of the peg and not a loss of principal. For a bot holding a stablecoin as a quote currency between trades, the practical exposure is mark-to-market slippage at the moment of a trade, not capital loss.

`[NOT VERIFIED]` I could **not** verify any October 2023, 2024 or 2025 USDT depeg episode with a primary source. I make no claim about those.

### Issuer / counterparty risk

All of the following are `[CLAIM]` — sourced from the Wikipedia article on Tether, which is a tertiary source citing primary reporting; I did not fetch the underlying enforcement documents. Source: <https://en.wikipedia.org/wiki/Tether_(cryptocurrency)>

- **CFTC fine, 15 October 2021: US$41.6 million** — for inaccurately claiming minted USDT were 100% backed by fiat USD when, even by Tether's own April 2019 affidavit, they were backed by a combination of fiat USD and *"unsecured receivables, commercial papers, funds held by third parties, and other non-fiat assets."* The CFTC action also concerned Tether maintaining full reserves only 27.6% of days from 2016–2018.
- **NY Attorney General settlement, 17 February 2021: US$18.5 million**, with no admission of wrongdoing.
- **Terms changed 25 February 2019.** Before that date the terms said *"Every tether is always backed 1-to-1, by traditional currency held in our reserves."* After, they said *"Tether Tokens are 100% backed by Tether's Reserves,"* with reserves defined as *"traditional currency and cash equivalents and, from time to time, may include other assets and receivables from loans made by Tether to third parties, which may include affiliated entities."*
- **April 2019 affidavit:** USDT was 74% backed by a narrow definition of cash and cash equivalents, with 26% in other assets.
- **Attestations, not audits.** Quarterly attestations by BDO Italia began July 2022. The *Wall Street Journal* characterised them as *"snapshots of a company's assets held at one moment in time with less rigorous standards than audits."* Tether has said it has never submitted to a full independent audit until recently.
- **Recent audit status.** March 2026: KPMG announced it would conduct Tether's first full financial audit. August 2026: Tether stated KPMG US completed the audit and issued an unqualified opinion under US GAAP — but **Tether did not publicly release the audit report.**
- **Direct redemption is not available to retail.** Tether can be *"newly issued by purchase for dollars or redeemed by exchanges and qualified corporate customers, excluding U.S.-based customers."* `[REASONING]` A retail Canadian holder therefore cannot redeem USDT at par directly with Tether; the exit is a secondary-market sale, which is where a depeg would actually bite.

`[NOT VERIFIED]` I did not verify Tether's current reserve composition from tether.to directly, nor the exact redemption minimums in Tether's current terms of service.

### Canadian regulatory treatment of stablecoins

`[VERIFIED-URL]` **Tax:** CRA treats stablecoins as a category of crypto-asset, with no separate regime (see Q1). CRA's guide describes them as *"pegged to a commodity (like gold), or a government backed currency (such as the US Dollar), or by having its supply regulated by an algorithm."* `[REASONING]` CRA does not treat a stablecoin as government-issued currency, so disposing of one is a disposition.

`[VERIFIED-URL]` **Securities regulation — CSA Staff Notice 21-333** (5 October 2023), *Crypto Asset Trading Platforms: Terms and Conditions for Trading Value-Referenced Crypto Assets with Clients*. Key content:
- A VRCA is *"a crypto asset that is designed to maintain a stable value over time by referencing the value of a fiat currency or any other value or right, or combination thereof."*
- The CSA would consent to platforms continuing to offer **Fiat-Backed Crypto Assets** (FBCAs) on an interim basis, subject to terms and conditions in Appendix A, including a requirement that the **issuer file an undertaking acceptable to the CSA**.
- Timetable: platforms not intending to continue had to stop by **29 December 2023**; non-FBCA VRCAs had to be removed by 29 December 2023; **non-compliant FBCAs by 30 April 2024.**
- The CSA's own warning: *"We caution users of VRCAs and VRCA holders that VRCAs, including any FBCAs that satisfy the conditions in the Appendices, are subject to various risks and **are not the same as fiat currency**. The fact that a VRCA satisfies the conditions in the Appendices, should not be viewed as our endorsement or approval of the VRCA, **nor an indication that the VRCA is risk-free** or that all risks associated with VRCAs are adequately mitigated."*

Source: <https://www.osc.ca/en/securities-law/instruments-rules-policies/2/21-333/csa-staff-notice-21-333-crypto-asset-trading-platforms-terms-and-conditions-trading-value>

`[VERIFIED-URL]` **Which stablecoin complied.** Circle's pressroom, 4 December 2024, *"Circle is the First Stablecoin Issuer to Meet New Canadian Listing Rules"*:
> "Today, Circle Internet Group, Inc. … announced that its regulated subsidiary is the first stablecoin issuer to commit to comply with the Ontario Securities Commission (OSC) and Canadian Securities Administrators' (CSA) Value-Referenced Crypto Asset (VRCAs) requirements. This facilitates Circle's U.S. dollar-denominated stablecoin, USDC, being offered on registered crypto asset trading platforms in the Canadian market. USDC is the first stablecoin to achieve this milestone …
> **Registered crypto asset trading platforms that operate in Canada and comply with VRCA requirements can continue to offer USDC after the CSA's December 31, 2024 cutoff for delisting non-compliant stablecoins.**"

Source: <https://www.circle.com/pressroom/circle-is-the-first-stablecoin-issuer-to-meet-new-canadian-listing-rules>

`[REASONING]` This is the regulatory mechanism behind Kraken's USDT delisting: the CSA framework required issuer undertakings, and a stablecoin without one had to be removed. USDC obtained compliance; USDT did not (as evidenced by its presence on Kraken Canada's prohibited list and the Nov/Dec 2023 suspension). **`[NOT VERIFIED]`** I did not find a CSA page stating in terms that Tether failed to file an undertaking — the CSA "crypto undertakings" list page did not render for my fetch. The inference is from Kraken's prohibition plus Circle's compliance statement.

`[NOT VERIFIED]` **Federal stablecoin framework.** I did not verify the status of the Bank of Canada / Department of Finance consultation on stablecoins or any federal legislative proposal. I make no claim about it.

`[VERIFIED-URL]` **Kraken Canada's other product restrictions** (same licensing page): *"Clients residing in Canada cannot trade using margin"* and *"Clients residing in Canada cannot trade derivatives."* Kraken operates in Canada as a registered Restricted Dealer with the OSC and the securities regulators of each province and territory, and maintains FINTRAC MSB registration (Payward Canada, Inc., MSB Registration No. M19343731).

---

## Q7 — Does Kraken Canada offer USDT pairs and a USDT/CAD market?

**No. USDT is blocked outright for Canadian clients — not merely illiquid.**

`[VERIFIED-URL]` Kraken's regulatory page, Canada section, *Cryptocurrency restrictions*: *"Cannot deposit, hold or trade ACA, AIN, AKE, ALCH, ALICE, ALIGN, ALLO, APXUSD, ARC, ATLAS, AUDX, AUGUR, AUSD, AVAAI, BASED, BDXN, BILL, BKS, BLESS, BLUAI, BNKR, BODEN, BRL1, C98, CASH, CHECK, CHEX, CLOUD, CMETH, COOKIE, COPM, CORN, CTC, DAI, DBR, DCR, DMC, DOLO, DUCK, EDGE, EPT, ESX, EURC, EUROP, EURQ, EURR, EV, EVAA, FF, FIDD, FLOCK, FOLKS, FOREST, FRNT, GAIA, GENIUS, GMX, GRASS, HDX, HMSTR, HOLO, HSK, IR, JITOSOL, KERNEL, KIN, KMNO, KNTQ, KOBAN, L3, LAYER, LINEA, LMWR, LSETH, MAT, METH, MOCA, MXNB, NMR, NOCK, NODE, OBOL, OMNI, ONE, OPN, ORDER, PACT, PARTI, PAXG, PIPE, PORTAL, PRCL, PWT, PYUSD, REQ, REZ, RLUSD, RNBW, RVV, SCA, SIDEKICK, SN44, SN51, SN62, SN64, SN75, SN8, SOFID, SOMI, ST, STABLE, STBL, SWARMS, TAC, TBTC, TCS, TEA, TGBP, TMX, TNSR, TREE, TREMP, U, U2U, UAI, UMXM, UNITAS, USAT, USD1, USDD, USDE, USDG, USDGO, USDPT, USDQ, USDR, USDS, USDSM, **USDT**, USTABLES, VELVET, VOOI, WAR, WAXL, WBTC, WEMIX, WEN, WFB, XAUT, XMR, YALA, YB, YGG, and ZEX."* (last updated 16 September 2026)

`[VERIFIED-URL]` The delisting article confirms the mechanism and the aftermath: suspension of deposits/withdrawals/trading for USDT, DAI, WBTC, WETH, WAXL across all trading platforms in Canada; forced conversion of residual balances to **USD** (not CAD) on 5 December 2023.

`[VERIFIED-URL]` **Other stablecoins are also blocked:** DAI, PYUSD, RLUSD, USDE, USD1, USDS, USDD, USAT, USDG and others all appear on the Canada prohibited list. Kraken separately published *"PYUSD delisting for Canadian clients"* (last updated 31 March 2025), delisting all PYUSD markets for Canadian clients on 5 February 2025.

`[VERIFIED-URL]` **USDC is the notable exception.** "USDC" appears **zero times** in Kraken's Canada cryptocurrency-restrictions list (I extracted the page text and counted). Combined with `[VERIFIED-URL]` Circle's statement that USDC is CSA-VRCA compliant and `[VERIFIED-URL]` Kraken's markets table listing a `USDC/CAD` market, `[REASONING]` **USDC/CAD appears to be the stablecoin route actually available to a Canadian on Kraken.** I did not find a Kraken page that says in terms "USDC is available to Canadian residents", so the positive claim rests on the absence from the prohibition list plus these two corroborating sources.

`[VERIFIED-URL]` **CAD-quoted pairs that do exist.** Parsing the CAD column of Kraken's markets table, exactly nine assets have a CAD market: **BTC, DOGE, ETH, PEPE, XRP, SOL, USDT, USDC, XDC**. So BTC/CAD, ETH/CAD, SOL/CAD and XRP/CAD all exist as the user describes. The same page warns: *"Some currencies listed below are not available in specific countries."* Sources: <https://support.kraken.com/ca/articles/kraken-markets>, <https://support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated>

`[REASONING]` **The user's premise is inverted.** The premise was that "USDT pairs on Kraken have far more liquidity than the thin CAD pairs." Even if true of the global order books, it is irrelevant: the USDT market on Kraken Canada is closed to Canadian residents, and USDT cannot be deposited, held, or traded. The comparison that actually matters for this taxpayer is **BTC/CAD vs BTC/USDC**, not BTC/CAD vs BTC/USDT.

`[NOT VERIFIED]` I found **no authoritative data** on Kraken's CAD or USDC/CAD bid-ask spreads or order-book depth. The claim that CAD pairs are "thin" is plausible but I could not quantify or confirm it, and I am not asserting it.

---

## Q8 — Cost of the CAD ↔ stablecoin conversion, and how often it happens

### Fee schedule (verified)

`[VERIFIED-URL]` **Spot Crypto** maker-taker tiers, Tier 1 (30-day volume $0+):

| Tier | 30-Day Vol (USD) | Maker | Taker |
|---|---|---|---|
| Tier 1 | $0+ | **0.40%** | **0.80%** |
| Tier 2 | $2.5K+ | 0.30% | 0.60% |
| Tier 3 | $10K+ | 0.22% | 0.38% |

`[VERIFIED-URL]` **Stablecoin, Pegged Token & FX Pairs** schedule:

| 30-Day Volume (USD) | Maker | Taker |
|---|---|---|
| $0+ | **0.20%** | **0.20%** |
| $50,000+ | 0.16% | 0.16% |
| $100,000+ | 0.12% | 0.12% |

`[VERIFIED-URL]` The scope rule that determines which schedule applies — this is the key line:
> "This fee schedule applies to FX pairs (EUR/USD), **stablecoins in the base currency** (USDT/USD, DAI/USDT, etc.) and pegged tokens (TBTC/BTC, WBTC/BTC, etc.). **If the stablecoin is the quote currency only (BTC/DAI), the fee schedule in the 'Spot Crypto' tab applies.**"

Source: <https://www.kraken.com/features/fee-schedule>

`[REASONING]` Applying that rule to this taxpayer:
- **BTC/CAD** → Spot Crypto schedule → **0.40% maker** at Tier 1.
- **BTC/USDC** (USDC is quote only) → Spot Crypto schedule → **0.40% maker** at Tier 1. **Identical per-side fee to BTC/CAD.**
- **USDC/CAD** (USDC is base) → stablecoin schedule → **0.20% maker / 0.20% taker**.
- Therefore a full CAD → USDC → CAD round trip costs roughly **0.40% in explicit fees**, plus whatever the spread is.

`[REASONING]` Note that a $1,000–2,000 account sits firmly in Tier 1 on every measure — it is far from the $2,500 threshold for Tier 2, and volume-based discounts are irrelevant at this size.

### Spread

`[NOT VERIFIED]` **I could not find any published Kraken data on CAD or USDC/CAD bid-ask spreads, nor on CAD order-book depth.** I will not estimate this. The user should measure it directly from Kraken's live order book for the specific pairs, since it is likely to be the dominant cost on thin CAD books and is not something the fee schedule discloses.

### How often the conversion would happen

`[REASONING]` This depends on whether the bot parks in the quote currency, which is the normal Freqtrade configuration:

- **If the bot parks in the stablecoin between trades** (the case the question describes): the CAD → stablecoin conversion happens **once when you fund the account**, and the stablecoin → CAD conversion happens **only when you withdraw profits or shut down**. That is on the order of **1–2 conversions per year**, not per trade. The recurring cost is not a conversion at all — it is the *extra taxable event* of spending the stablecoin to buy the base asset (Q2), which carries the ordinary 0.40% maker fee already paid on any Kraken spot trade.
- **If the bot converts back to CAD after every trade**: that would add 2 × 0.20% ≈ 0.40% per completed trade, on top of the trade fee, and would add a further taxable event per trade. This would be the expensive configuration and is presumably not intended.

`[REASONING]` So on the fee side, the stablecoin route is roughly cost-neutral per trade versus CAD pairs, plus ~0.40% once or twice a year for the funding/withdrawal conversions — **provided** the CAD book spread is not materially wider than the stablecoin book spread. That proviso is exactly what I could not measure.

---

## Summary table

| Question | Answer | Key source |
|---|---|---|
| Q1 crypto-to-crypto taxable? | **Yes** — CRA names "another type of crypto-asset" as a disposition, with a worked example | CRA crypto guide |
| Q2 quote currency changes event count? | **Yes** — +1 event per completed trade, +1 per exit. Liability ≈ flat, burden ≈ doubled | `[REASONING]` from CRA premises |
| Q3 business vs capital factors | CRA lists 6 factors (IT-479R lists 8); case-by-case; 50% vs 100% inclusion | CRA crypto guide, IT-479R |
| Q4 reporting burden | Per-transaction CAD value, date **and time**, ledgers, 6-year retention, **average-cost pooling not FIFO**; T5008 does not cover crypto; T1135 threshold $100k cost amount — not triggered at this account size | CRA guide + T1135 Q&A |
| Q5 software: liability or burden? | **Burden only.** Rotki says so itself. Defaults are German/FIFO and must be changed. | Rotki docs + CRA rules |
| Q6 USDT risk | Intraday depeg to ~$0.95 on 12 May 2022 (recovered to $0.998 same day); CFTC $41.6M and NYAG $18.5M; attestations not audits; CSA VRCA regime required issuer undertakings | CNBC, CSA 21-333, Circle |
| Q7 Kraken Canada USDT? | **No — cannot deposit, hold, or trade USDT.** USDC appears to be the available stablecoin | Kraken licensing + delisting pages |
| Q8 conversion cost | 0.20% each way on USDC/CAD; BTC/USDC maker 0.40%, same as BTC/CAD; ~1–2 conversions/year if parking in the stablecoin | Kraken fee schedule |

---

## Exact URLs used

**CRA / canada.ca (fetched directly by me):**
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide.html>
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/crypto-assets-tax-obligations.html>
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/income-crypto-transactions.html>
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/books-records-crypto.html>
- <https://www.canada.ca/en/revenue-agency/programs/about-canada-revenue-agency-cra/compliance/cryptocurrency-guide/value-crypto.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/calculating-reporting-your-capital-gains-losses.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/special-rules-other-transactions.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/capital-losses-deductions.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/definitions-capital-gains.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12700-capital-gains/whats-new-capital-gains.html>
- <https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/it479r/archived-transactions-securities.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/information-been-moved/foreign-reporting/questions-answers-about-form-t1135.html>
- <https://www.canada.ca/en/revenue-agency/services/forms-publications/forms/t1135.html>

**Kraken:**
- <https://support.kraken.com/ca/articles/where-is-kraken-licensed-or-regulated>
- <https://support.kraken.com/articles/trading-suspension-in-canada-for-usdt-dai-weth-wbtc-and-waxl>
- <https://support.kraken.com/ca/articles/pyusd-delisting-canadian-clients>
- <https://support.kraken.com/ca/articles/kraken-markets>
- <https://www.kraken.com/features/fee-schedule>

**Regulators / other:**
- <https://www.osc.ca/en/securities-law/instruments-rules-policies/2/21-333/csa-staff-notice-21-333-crypto-asset-trading-platforms-terms-and-conditions-trading-value>
- <https://www.circle.com/pressroom/circle-is-the-first-stablecoin-issuer-to-meet-new-canadian-listing-rules>
- <https://www.cnbc.com/2022/05/12/tether-usdt-stablecoin-drops-below-1-peg.html>
- <https://en.wikipedia.org/wiki/Tether_(cryptocurrency)>
- <https://rotki.com/features/open-source-crypto-tax>
- <https://docs.rotki.com/usage-guides/settings/accounting.html>
- <https://docs.rotki.com/usage-guides/tax-accounting/guide>
- <https://github.com/rotki/rotki>
- <https://api.github.com/repos/rotki/rotki>

**Fetched by delegated researcher (not by me):**
- <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/completing-slips-summaries/financial-slips-summaries/return-securities-transactions-t5008/general-information.html>
- <https://laws-lois.justice.gc.ca/eng/regulations/C.R.C.,_c._945/section-230.html>
- <https://laws-lois.justice.gc.ca/eng/acts/I-3.3/section-233.3.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/changes-your-business/unnamed-persons-requirements.html>
- <https://www.canada.ca/en/revenue-agency/services/tax/international-non-residents/information-been-moved/foreign-reporting/foreign-income-verification-statement.html>

**Cited but NOT successfully fetched (blocked or 404):**
- <https://www.reuters.com/markets/us/crypto-collapse-intensifies-stablecoin-tether-slides-below-dollar-peg-2022-05-12/> — HTTP 401
- <https://www.securities-administrators.ca/crypto-platforms-regulation-and-enforcement-actions/crypto-undertakings/> — did not render
- CRA pages that 404'd during this session: the `line-12700-capital-gains/identical-properties.html` path, `line-12700-capital-gains/capital-gains-inclusion-rate.html`, `publications/t1135.html`, `line-12700-capital-gains/superficial-losses.html`
- A Department of Finance news release URL for the cancelled capital-gains inclusion-rate increase — HTTP 404

---

## What I could NOT verify

Stated explicitly rather than filled in:

1. **The exact number of dispositions in a stablecoin-quoted bot.** Q2's count is my reasoning from CRA's verified premises. CRA has published no worked example of this structure.
2. **That the proposed two-thirds capital gains inclusion rate was formally cancelled.** CRA's 2025 guidance states 50% and its "what's new" page omits any increase, but I could not fetch the Department of Finance announcement. The *operative 50% rate for 2025* is verified.
3. **That the identical-properties average-cost rule applies to crypto-assets in terms.** CRA's examples name shares and mutual-fund units; CRA's crypto guide treats each asset type separately but does not invoke the averaging rule.
4. **Whether Rotki supports CAD as the "profit currency."** Its docs name EUR, USD and GBP only. If CAD is unavailable, the CAD reporting CRA requires would still need a separate conversion step. I also did not verify Rotki's Kraken Canada integration or whether it ingests Kraken ledger exports specifically.
5. **Any authoritative data on Kraken's CAD or USDC/CAD bid-ask spreads or order-book depth.** I did not estimate this, and I do not confirm the premise that CAD pairs are "thin."
6. **That USDC is affirmatively available to Canadian residents on Kraken.** Established by absence from the prohibition list plus Circle's CSA compliance statement plus the USDC/CAD market listing — but I found no Kraken page stating it directly.
7. **That Tether failed to file a CSA undertaking.** Inferred from Kraken's USDT prohibition and Circle's "first to comply" statement; the CSA undertakings list page did not render.
8. **USDT depegs in October 2023, 2024 or 2025.** Not verified with any primary source. I make no claim.
9. **Tether's current reserve composition and redemption minimums** from tether.to directly. The enforcement history, reserve-terms history and attestation character are `[CLAIM]` from a tertiary source.
10. **Any federal (Bank of Canada / Finance Canada) stablecoin framework status.** Not investigated successfully.
11. **CRA's requirement for a specific exchange rate source for crypto.** CRA prescribes only a "reasonable method, consistently applied, documented." No fallback hierarchy was found.
12. **Platform-by-platform T5008 behaviour** — which Canadian exchanges issue crypto T5008s, and with what box 20 contents.

---

## Closing note

Nothing in this document is tax advice or a recommendation about which pairs to trade. The tax characterisation of an automated trading bot (capital vs business income), the correct ACB computation under CRA's pooling rule, and the reporting positions for any given year are all fact-specific determinations. **A qualified Canadian accountant — ideally one with crypto-asset experience — should be consulted before acting on any of this.**
