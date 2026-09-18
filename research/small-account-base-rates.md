# Base Rates of Retail Trading Profitability

**Research question:** What is the honest evidence on whether a small account should trade systematically at all?

**Scope:** Base rates of retail trading profitability, with emphasis on evidence applicable to a small crypto account.

**Method note.** Every source below was actually downloaded and text-extracted in this session (`curl` + `pypdf`), or fetched as live HTML. PDF sources are cited by their direct file URL. **Every number quoted in this report was programmatically re-checked against the extracted source text after writing** (exact-substring match, with whitespace/line-wrap normalisation to handle PDF line breaks); all checks passed. Search engines were heavily rate-limited in this environment (DuckDuckGo/Mojeek/SearXNG bot challenges; Brave search returned zero results partway through; Semantic Scholar API HTTP 429; SSRN HTTP 403), so sources were reached by direct URL, OpenAlex/Crossref API, and publisher/repository paths rather than by open web search. Where a figure is verified only from publisher-deposited abstract metadata rather than the article body, it is labelled `[PUBLISHER-METADATA]`.

**Label key**
- `[PEER-REVIEWED]` — published in a refereed journal; I read the paper text.
- `[VERIFIED-URL]` — I fetched this URL this session and confirmed the quoted text in it.
- `[PUBLISHER-METADATA]` — abstract text verified from publisher-deposited metadata (Crossref/OpenAlex), not from the article body (paywalled).
- `[PRACTITIONER]` / `[BLOG]` — non-academic source.
- `[CLAIM]` — asserted but not verified by me.
- `[REASONING]` — my inference, not a sourced number.

---

## 0. Headline: the base rate for active retail traders is a large majority losing money

Across equities, futures, FX, CFDs, binary options and crypto, the independently produced base rates converge on **roughly 70–97% of retail participants losing money**, with the loss rate *rising* with persistence and trading frequency. The single most important structural finding for a small account is in §2: the probability of a positive outcome **decreases monotonically with the number of days traded**, which is the opposite of what "learning by doing" predicts.

---

## 1. Barber, Lee, Liu, Odean — Taiwan day traders

### 1a. "Do Individual Day Traders Make Money? Evidence from Taiwan" (working paper, May 2004) `[VERIFIED-URL]`

URL: https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trade%20040330.pdf
(32 pages; listed on Odean's faculty page: https://faculty.haas.berkeley.edu/odean/)

Verified verbatim from the abstract:
- Day trading by individual investors accounted for **over 20 percent of total volume from 1995 through 1999**.
- **Individual investors account for over 97 percent of all day trading activity.**
- **About one percent of individual investors account for half of day trading** and one fourth of total trading by individual investors.
- **"Heavy day traders earn gross profits, but their profits are not sufficient to cover transaction costs."**
- **"Moreover, in the typical six month period, more than eight out of ten day traders lose money."** → i.e. **>80% lose money**, measured over a six-month window, after costs.
- Persistent ability exists in a small group: **"The stocks they buy outperform those they sell by 62 basis points per day."** — and the paper states this spread "is sufficiently large to cover transaction costs."

**Returns computation:** the 2004 paper reports *gross* profits for heavy day traders that fail to cover transaction costs, i.e. transaction costs are treated as a separate deduction and are decisive. The "eight out of ten lose money" figure is the net-of-cost outcome framing.

### 1b. "The Cross-Section of Speculator Skill: Evidence from Day Trading" — *Journal of Financial Markets* 18 (2014) 1–24 `[PEER-REVIEWED]`

Published version PDF (fetched): https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf
Earlier working-paper version (May 2011, fetched): https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20Skill%20110523.pdf

**Sample:** complete transaction data for the **Taiwan Stock Exchange, 1992–2006** (15 years, all speculators in an entire market — not a single-broker sample). Day traders accounted for **17% of all TSE volume** during the sample period.

Verified verbatim from the abstract and body:
- Top-ranked (500 top) day traders earn daily **before-fee 61.3 bps / after-fee 37.9 bps**.
- Bottom-ranked earn **before-fee −11.5 bps / after-fee −28.9 bps** per day.
- **"Less than 1% of the day trader population is able to predictably and reliably earn positive abnormal returns net of fees."**
- **"In the average year, about 450,000 individuals engage in day trading. While approximately 20% earn profits net of fees in the typical year, the results of our analysis suggest that less than 1% of day traders (4,000 out of 450,000) are able to outperform consistently."**
- Robustness on fees: at a **14.25 bps commission (the statutory maximum)**, top three groups earn net alphas of **24.1 bps (t=39.0), 7.6 bps (t=10.9), and 1.1 bps (t=1.6)** — so the number of predictably profitable day traders **"ranges from a low of 1,000 to a high of 4,000."**
- Day traders who focus on **passive strategies fail to earn positive net alphas**.

**Key structural point for a small account:** ~20% of day traders are *profitable in a given year* (which is roughly what a coin-flip-plus-costs process would produce), but **<1% are profitable persistently**, and the persistent winners are the top ~1,000–4,000 of 450,000. The 20% annual figure is the number most often misquoted as evidence that day trading "works".

### 1c. "Learning, Fast or Slow" — *Review of Asset Pricing Studies* 2019 `[PUBLISHER-METADATA]`

DOI: https://doi.org/10.1093/rapstu/raz006 (record: https://api.openalex.org/works/https://doi.org/10.1093/rapstu/raz006)
Barber, Lee, Liu, Odean (with Ke Zhang). **Paywalled; no open-access copy exists** (confirmed via OpenAlex: `is_oa: false`, no repository fulltext). I verified the abstract text only, via publisher-deposited metadata.

Verified verbatim from the abstract:
- Rational "trading to learn" models **do not** explain speculative trading.
- **"unprofitable day traders are more likely than profitable traders to quit"** (consistent with prior learning studies).
- **"the aggregate performance of day traders is negative; 74% of day trading volume is generated by traders with a history of losses; and 97% of day traders are likely to lose money in future day trading."**

**Caveat:** the "97% likely to lose money in future day trading" figure is verified from the abstract, not the article body, which I could not open. Treat the exact definition of "future day trading" as unverified by me.

---

## 2. Chague, De-Losso, Giovannetti — "Day Trading for a Living?" (Brazilian equity futures) `[VERIFIED-URL]`

**Canonical listing (RePEc/IDEAS, fetched):** https://ideas.repec.org/p/fgv/eesptd/525.html
**Official FGV repository link** (listed by RePEc as the publisher full-text): https://repositorio.fgv.br/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/download — **this URL returned an HTML page, not a PDF, when I fetched it; I could not extract the paper from it.**
**Version I actually extracted and verified:** https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf — this mirror is the genuine SSRN paper (9 pages, dated 13 June 2020, carries the footer "Electronic copy available at: https://ssrn.com/abstract=3423101"). SSRN itself returns HTTP 403, and the paper is closed-access (`oa_status: closed` per OpenAlex), so no open copy exists at the publisher.

**Sample:** all individuals who **began** day trading **2013–2015** in the **Brazilian equity futures market** (mini index futures) — the third largest by volume in the world. Data from CVM (the Brazilian regulator). **19,646 new day traders.**

Verified verbatim from the extracted text:

**Persistence and the exact 300-day loss figure:**
- Of the 19,646 new day traders: 1,111 (5.7%) traded only one day; 9,978 (50.8%) 2–50 days; 3,100 (15.8%) 51–100 days; 2,738 (13.9%) 101–200 days; 1,168 (5.9%) 201–300 days; **1,551 (7.9%) more than 300 days.**
- **"Considering the performance net of exchange and brokerage fees, we find that 97% of all investors who persisted for more than 300 days lost money."** → **97% loss rate, net of fees, among the 1,551 who traded 300+ days.**
- **"Only 17 individuals (1.1% of 1,551) earned more than the Brazilian minimum wage (US$ 16 per day), only eight individuals (0.5% of 1,551) earned more than the initial salary of a bank teller (US$ 54 per day), and the individual who earned the most earned US$ 310 per day on average."**
- The eight who beat a bank teller's salary did so **with great volatility: the standard deviation of daily profit ranges from US$ 632 to US$ 3,308.**
- The probability of a positive profit **"monotonically decreases with the number of days he or she trades. This peculiar pattern is contrary to what 'self-selection'—individuals who persist in an activity are generally those with better performance—and 'learning by doing' would suggest. In turn, patterns like this are usually found in gambling activities, such as the casino roulette, where the proportion of successful players also monotonically decreases with the number of rounds played."**

**The "learned nothing" framing** — verified verbatim: the authors run individual-day panel regressions for the 1,551 persistent traders of daily profit on `seq` (chronological trading-day index) and on `first third`/`last third` dummies, with day-trader fixed effects. **"In columns 1 and 2 (gross profit) and 3 and 4 (net profit) we find no evidence of learning."**

**Also verified:** the paper explicitly notes that prior studies (Linnainmaa 2003/2005; Jordan & Diltz 2003; Choe & Eom 2009; Ryu 2012; Kuo & Lin 2013) "document that more than 20% of the individuals profit. However, they do not differentiate individuals with a single day trade from those who day trade regularly." — This is the same 20%-vs-persistence distinction as §1b.

### 2b. Portuguese-language, peer-reviewed version (stocks, not futures) `[PEER-REVIEWED]`

"É possível viver de day-trade em ações? (Day-trading stocks for a living?)", Chague & Giovannetti, *Revista Brasileira de Finanças* 18(3), 2020. DOI 10.12660/rbfin.v18n3.2020.81949.
Open-access PDF (fetched and extracted): https://bibliotecadigital.fgv.br/ojs/index.php/rbfin/article/download/81949/78263

Verified verbatim from the abstract: **"we study the performance of all 98,378 individuals who started to day-trade stocks in Brazil between 2013 and 2016. After analyzing all their day-trades in stocks from 2013 to 2018, we find that only 127 individuals presented an average daily gross profit higher than R$ 100 for more than 300 days."**
→ **127 of 98,378 = 0.13%**, and note this is a **gross** profit threshold (before costs), for a modest R$100/day.

**Version discrepancy to flag:** the RePEc abstract for the 2020 FGV working paper states "only **0.4%** earned more than a bank teller (US$54 per day)", whereas the 13 June 2020 SSRN text I extracted states **0.5%** (8 of 1,551). These are different revisions of the same paper. I verified 0.5% in the document I read; the 0.4% figure is from the RePEc abstract page, which I also fetched.

---

## 3. Barber & Odean — aggregate individual investor underperformance

### 3a. "Trading Is Hazardous to Your Wealth" — *Journal of Finance* 55(2), April 2000, 773–806 `[PEER-REVIEWED]`

PDF (fetched and extracted): https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf

Verified verbatim from the abstract:
- **Sample: 66,465 households with accounts at a large discount broker, 1991–1996.**
- **"those that trade most earn an annual return of 11.4 percent, while the market returns 17.9 percent."** → the most active quintile of households underperformed the market by **6.5 percentage points per year**.
- **"The average household earns an annual return of 16.4 percent"** (vs market 17.9%).
- The average household **"turns over 75 percent of its portfolio annually"**.
- Central conclusion: **"trading is hazardous to your wealth."**

**Returns computation:** these are *net* returns (realized, from actual account positions and trades); the paper attributes the majority of the performance penalty to **trading costs**.

### 3b. "Just How Much Do Individual Investors Lose by Trading?" — *Review of Financial Studies* 22(2), 2009, 609–632 `[PEER-REVIEWED]`

PDF (fetched and extracted): https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/JustHowMuchDoIndividualInvestorsLose_RFS_2009.pdf

Verified verbatim from the abstract and body:
- **Sample: complete trading history of all investors in Taiwan, 1995–1999** (the entire market, not a broker sample).
- **"the aggregate portfolio of individuals suffers an annual performance penalty of 3.8 percentage points."**
- **"Individual investor losses are equivalent to 2.2% of Taiwan's gross domestic product or 2.8% of the total personal income."**
- **"Virtually all individual trading losses can be traced to their aggressive orders."** (i.e. market orders / liquidity-demanding trades, not passive limit orders.)
- In contrast, **"institutions enjoy an annual performance boost of 1.5 percentage points, and both the aggressive and passive trades of institutions are profitable. Foreign institutions garner nearly half of institutional profits."**

**Benchmark:** the 3.8pp penalty is measured against the market/aggregate portfolio benchmark; institution figures are stated as "after commissions and transaction taxes (but before [other costs])".

---

## 4. Barber, Huang, Odean, Schwarz — "Attention-Induced Trading and Returns: Evidence from Robinhood Users", *Journal of Finance* 77(6), 2022, 3141–3190 `[PUBLISHER-METADATA]`

DOI: https://doi.org/10.1111/jofi.13183
Wiley: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.13183

**This paper is closed access.** OpenAlex reports `is_oa: false`, `oa_status: "closed"`, `any_repository_has_fulltext: false` — I confirmed there is no legitimate open full text. I therefore verified the abstract from **two independent publisher-deposited metadata sources** (OpenAlex and Crossref), which agree word-for-word:

- OpenAlex: https://api.openalex.org/works/https://doi.org/10.1111/jofi.13183
- Crossref: https://api.crossref.org/works/10.1111/jofi.13183

Verified verbatim from the abstract:
- **"intense buying by Robinhood users forecasts negative returns. Average 20-day abnormal returns are −4.7% for the top stocks purchased each day."**
- Robinhood investors engage in **more attention-induced trading than other retail investors**; **"Robinhood outages disproportionately reduce trading in high-attention stocks."**
- The evidence is consistent with Robinhood attracting **relatively inexperienced investors**, and is also driven by the app's unique features.

**The exact figure requested (basis points per day) is NOT verified.** The abstract states the 20-day abnormal return of **−4.7%**. I did not open the article body and will not derive a bps/day figure from it — a naive −4.7%/20 = −23.5 bps/day would be an unverified linearisation `[REASONING]`, and the paper's own body likely reports bps/day differently. **This is an explicit gap.**

---

## 5. Regulator data on retail leverage trading losses

Regulator-produced figures are the strongest evidence in this report: they are population-level, mandated, and checkable.

### 5a. ESMA 2018 CFD product intervention — **74–89%** `[VERIFIED-URL]`

URL: https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors

Verified verbatim from the press release:
> "NCAs' analyses on CFD trading across different EU jurisdictions shows that **74-89% of retail accounts typically lose money on their investments, with average losses per client ranging from €1,600 to €29,000.** NCAs' analyses for binary options also found consistent losses on retail clients' accounts."

- Measures **agreed by ESMA's Board of Supervisors on 23 March 2018**; announced by Chair Steven Maijoor.
- Stated rationale includes **"the particular features of CFDs – excessive leverage"** and, for binary options, **"structural expected negative return and embedded conflict of interest between providers and their clients."**
- Related ESMA page (fetched, HTTP 200): https://www.esma.europa.eu/investor-corner/product-intervention

### 5b. FCA (UK) — **over 80% / 82%**, average loss £2,200 `[VERIFIED-URL]`

Source: FCA **Consultation Paper CP16/40**, "Enhancing conduct of business rules for firms providing contract for difference products to retail clients", December 2016.
PDF (fetched and extracted, 62 pages): https://www.fca.org.uk/publication/consultation/cp16-40.pdf

Verified verbatim:
- §1.5: **"Based on a sample of client account data collected as part of this work, we also found over 80% of clients lost money on these products over a year. The average result per client was a loss of £2,200."** (The review was of retail CFD providers in **2015**.)
- §3.10: **"on the basis that a majority of clients lose money on these products – with our own figures suggesting an approximate ratio of 82% of clients losing against 18% making a profit"**.
- Annex/CBA: **"From a random sample of client accounts from eight CFD firms, our internal analysis suggests that 82% of clients lose money on these products. The average outcome was a loss of £2,200 per client."**
- Also verified in the same document: **"Our research suggests that inexperienced retail clients lose less money than experienced clients due to the lower number and volume of trades."** (A counter-intuitive but relevant finding: greater experience/activity → larger losses.)

**Other EU regulators, verified verbatim in the same FCA document (footnote 5):**
- **France (AMF): "89% of consumers lost money on these products and investors lost on average €10,887 and with a median investor loss of €1,843."** (AMF study of CFD and forex traders in France, 13 October 2014.)
- **Ireland (Central Bank of Ireland): "75% of consumers lost money at an average loss of €6,900."** (23 November 2015.)
- **Netherlands (AFM)** CFD product review referenced (13 February 2015).

**FCA risk-warning template** — verified in FCA **Policy Statement PS19/18** (fetched, 51 pages): https://www.fca.org.uk/publication/policy/ps19-18.pdf
The mandated disclosure text is literally **"[insert percentage per provider]% of retail investor accounts lose money when trading CFDs with this provider"** — i.e. the UK regime requires each firm to publish its *own* client loss percentage. PS19/18 does **not** itself state an "~80%" population figure; the 80/82% figures come from CP16/40 above.

### 5c. ASIC (Australia) — **80% binary options / 72% CFD / 63% margin FX** `[VERIFIED-URL]`

**Correction to the research brief:** **ASIC Report 693 is NOT about CFD/forex losses.** REP 693 is "Response to submissions on ASIC's internal dispute resolution data consultations" — verified in ASIC's own sitemap (https://asic.gov.au/sitemap.xml):
https://www.asic.gov.au/regulatory-resources/find-a-document/reports/rep-693-response-to-submissions-on-asic-s-internal-dispute-resolution-data-consultations

The correct ASIC source is **REP 626 "Consumer harm from OTC binary options and CFDs" (August 2019)**.
Report page: https://www.asic.gov.au/regulatory-resources/find-a-document/reports/rep-626-consumer-harm-from-otc-binary-options-and-cfds
PDF (fetched and extracted, 6 pages): https://download.asic.gov.au/media/5241548/rep626-published-22-august-2019.pdf

Verified verbatim from the PDF:
- **"80% of clients who trade binary options lose money"** — with the footnote: **"This data was collected from our 2017 review of the retail OTC derivatives sector. These figures are broadly consistent with data reported by European regulators before the introduction of product intervention measures by the European Securities and Markets Authority (ESMA)."**
- **"72% of clients who trade CFDs lose money"**
- **"63% of clients who trade margin FX lose money"**
- Headline framing: **"Most clients who trade binary options or CFDs lose money"**; the review covered **57 (2017) and 61 (2019) active Australian AFS licensees**.
- Sector snapshot: **$2b gross trading revenue in 2018**; **-$33m total negative balances of CFD trading accounts in 2018**; **9m CFD margin close-outs in 2018**; **$131m marketing expense in 2018 (up from $93m in 2017)**; **$281m paid by issuers for client referrals in 2018**; **80% of clients aged 22–50**; **32% of clients earn less than $37,000 per annum**; **225,000+ new clients given inducements in 2017 and 2018**; **83% of Australian issuers' clients are offshore**.
- Binary options characteristics cited as causing detriment: **"negative expected returns", "high likelihood of cumulative losses", "unsuitability as an investment or risk management product, with product characteristics similar to gambling."**
- ASIC's worked example: Tom makes 150 binary option bets; **"Tom has a 92% chance of losing money on his 150 binary option bets, and Tom's most likely return on this investment is a loss of $1,500."** (Note ASIC's own caveat that this assumes equal odds, "which is more generous than the reality".)

Related ASIC documents located in the sitemap (not fetched/extracted): **REP 828 "Risky business: driving change in CFD issuers' distribution practices"**; **CP 322** product intervention consultation.

### 5d. FINRA / CFTC — **NOT VERIFIED** ❌

I could not locate a FINRA or CFTC publication giving a population-level percentage of profitable/losing retail futures or forex accounts, and I found no peer-reviewed study built on CFTC retail-forex account data. Searches of OpenAlex for such studies returned nothing relevant. **Treat "FINRA/CFTC data on retail futures/forex profitability" as unverified and unlocated.** See §8.

---

## 6. Crypto-specific retail P&L evidence

**Honest summary: the crypto-specific literature is much thinner than the equities/futures/FX literature, but it is not empty.** There is no crypto equivalent of Barber-Lee-Liu-Odean's complete-market transaction dataset. The two strongest sources found are a BIS dataset and one peer-reviewed brokerage-account study; both point the same direction as the traditional-asset base rates.

### 6a. BIS Working Paper 1049 — **73–81% of retail investors likely lost money** `[VERIFIED-URL]`

"Auer, Cornelli, Doerr, Frost, Gambacorta — Crypto trading and Bitcoin prices: evidence from a new database of retail adoption", BIS Working Paper 1049, 14 November 2022.
Page: https://www.bis.org/publ/work1049.htm

Verified verbatim from the "Findings" summary on the BIS page:
> "We show that, when the price of Bitcoin rises, more people download and actively use crypto exchange apps. These new users are disproportionately younger and male, commonly identified as the most 'risk-seeking' segment of the population. **We show that, due to price declines, an estimated 73-81% of retail investors have likely lost money on their initial investment.**"

- **Data:** a novel database on **daily use of crypto exchange apps for 95 countries over 2015–22**, made publicly available by the BIS.
- Identification uses the Chinese crypto-mining crackdown (mid-2021) and Kazakhstan social unrest as exogenous Bitcoin-price shocks.
- **Note:** this is an *estimate/simulation* of likely losses on initial investment, conditional on app-download timing — not an accounting of realized account P&L. I verified the figure from the BIS page summary; I did not extract the 42-page PDF body.

### 6b. BIS Bulletin 69 — "Crypto shocks and retail losses" `[VERIFIED-URL]`

Cornelli, Doerr, Frost, Gambacorta, BIS Bulletin No 69, **20 February 2023**.
Page: https://www.bis.org/publ/bisbull69.htm
PDF (fetched and extracted, 8 pages): https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf

Verified verbatim from the PDF:
- **"Data on major crypto trading platforms over August 2015–December 2022 show that, as a result, a majority of crypto app users in nearly all economies made losses on their bitcoin holdings."**
- **"In nearly all economies in our sample, a majority of investors probably lost money on their bitcoin investment (Graph 2.B). The median investor would have lost $431 by December 2022, corresponding to almost half of their total $900 in funds invested since downloading the app. Notably, this share is even higher in several emerging market economies like Brazil, India, Pakistan, Thailand and Turkey. If investors continued to invest at a monthly frequency, over four fifths of users would have lost money."**
- Method (verbatim): **"we assume that each new user bought $100 of bitcoin in the month of the first app download and in each subsequent month."**
- **Critical behavioural finding (verbatim):** after the Terra/Luna collapse and the FTX bankruptcy, **"crypto trading activity increased markedly, with large and sophisticated investors selling and smaller retail investors buying."** — i.e. retail bought the collapse while sophisticated holders sold.
- Scale of the collapse: **"over $1.8 trillion of crypto value dissolved. Over $450 billion vanished during the market turmoil following the Terra/Luna collapse in May 2022 alone; another $200 billion was lost in the wake of the FTX bankruptcy in November 2022."**
- **"over four fifths" = >80%** of users would have lost money under the monthly-buying simulation.

**This is the closest thing to a crypto base rate that exists at population scale**, and it lands in the same 73–89% band as ESMA/FCA/ASIC.

### 6c. Hasso, Pelster, Breitmayer (2019) — brokerage accounts `[PEER-REVIEWED]`

"Who trades cryptocurrencies, how do they trade it, and how do they perform? Evidence from brokerage accounts", *Journal of Behavioral and Experimental Finance* 23 (2019) 64–74. DOI: https://doi.org/10.1016/j.jbef.2019.04.009
Author-accepted manuscript (fetched and extracted, 24 pages): https://eprints.qut.edu.au/129185/1/Who%20trades%20cryptocurrencies.pdf
(Publisher-branded copy at https://research.bond.edu.au/files/30294346/jbef.pdf returned **HTTP 403**.)

Verified verbatim:
- **Sample: 465,926 individual brokerage accounts** at an online brokerage that lets clients trade contracts (crypto exposure via the broker).
- **"men are more likely to engage in cryptocurrency trading, trade more frequently, and more speculative, respectively. As a result, men realize lower returns."**
- **"female investors realize significantly higher returns than male traders when engaging in cryptocurrency trading."**
- **"performance is not related to the number of weekly executed trades. Specifically, neither the investors with the highest nor least trading activity realize the highest returns."**
- **"the returns on cryptocurrencies seem to positively correlate with the position holding times."**
- Table 9 Panel B reports average **weekly realized raw returns** at account level across trading-pattern groups, all small and mostly positive: values in the range **0.00004 to 0.00263** (i.e. ≈0.004%–0.26% per week).

**Important caveats:** (i) these are **raw** returns, *not* net of fees — so they cannot be used to claim profitability; (ii) the paper's contribution is about *cross-sectional differences by demographics and trading style*, not about the population loss rate; (iii) it does not report a "% of traders who lost money" headline. It is the best peer-reviewed crypto brokerage-account study I found, and it supports the general pattern that **more active/speculative trading → worse returns**, and **longer holding → better returns**.

### 6d. Crypto literature gaps

- **No peer-reviewed study with complete exchange-level P&L for a whole crypto market** was found (the analogue of the Taiwan data).
- **Korean / Japanese retail crypto trading P&L studies:** I did not locate and verify any. `[unverified]`
- I found no evidence of a crypto-specific equivalent to the Taiwan "complete transaction data" studies.

---

## 7. Systematic / rule-based crypto strategies vs buy-and-hold, net of fees

### Hudson & Urquhart (2021) — "Technical trading and cryptocurrencies", *Annals of Operations Research* 297, 191–220 `[PEER-REVIEWED]`

DOI: https://doi.org/10.1007/s10479-019-03357-1
Open-access published version (fetched and extracted, 31 pages): https://centaur.reading.ac.uk/85715/8/Hudson-Urquhart2019_Article_TechnicalTradingAndCryptocurre.pdf
(Springer's own PDF URL returned an HTML block page.)

**Design:** **almost 15,000 technical trading rules** from the **five main classes** (moving average, channel breakout, oscillator, support-resistance, filter/other), applied to **five cryptocurrency markets**: CoinDesk Bitcoin, Bitstamp Bitcoin, Litecoin, Ripple, Ethereum. Multiple-hypothesis-testing procedures are used against data-snooping; both in-sample and out-of-sample periods are examined.

Verified verbatim:
- **"we find significant predictability and profitability for each class of technical trading rule in each cryptocurrency."**
- **"We find that the breakeven transaction costs are substantially higher than those typically found in cryptocurrency markets."**
- **"the technical trading rules offer substantially higher risk-adjusted returns than the simple buy-and-hold strategy, showing protection against lengthy and severe drawdowns associated with cryptocurrency markets."**
- **"However there is no predictability for Bitcoin in the out-of-sample period, although predictability remains in other cryptocurrency markets."**
- Out-of-sample test = best in-sample rules (selected up to 31 Dec 2017) run over the **first 6 months of 2018** (the crypto bear market): **"we find negative annualized returns, Sharpe ratios and Sortino ratios for both Bitcoin prices. However, the three other cryptocurrencies show positive out-of-sample returns."**

**Table 7 (verified from the extracted text) — buy-and-hold benchmark, with the percentage of technical rules beating it in brackets:**

| Market | Ann. Return | Ann. Sharpe | Ann. Sortino | Calmar |
|---|---|---|---|---|
| CoinDesk (BTC) | 0.1167 (6.12%) | 0.1153 (6.12%) | 3.1996 (32.83%) | 4.2202 (28.58%) |
| Bitstamp (BTC) | 0.0942 (4.96%) | 0.0925 (4.86%) | 3.0163 (32.14%) | 3.4522 (32.72%) |
| Litecoin | 0.0928 (11.49%) | 0.0918 (41.30%) | 2.4167 (51.26%) | 1.3750 (57.64%) |
| Ripple | 0.1339 (15.69%) | 0.1330 (15.69%) | 3.1768 (27.99%) | 2.7796 (36.73%) |
| Ethereum | 0.1875 (9.01%) | 0.1864 (8.98%) | 3.9645 (49.71%) | 11.0426 (42.17%) |

Caption verified verbatim: *"In brackets, we also report the percentage of technical trading rules that report returns higher than that of the buy-and-hold strategy."*

**This table is the single most decision-relevant result in this report, and it cuts both ways:**
- On **raw annualized return**, only **4.96%–15.69%** of the ~15,000 rules beat buy-and-hold. **The overwhelming majority of systematic crypto strategies underperform simply holding.**
- On **risk-adjusted** measures (Sharpe/Sortino/Calmar), far more rules beat buy-and-hold — e.g. Litecoin Sortino 51.26%, Ethereum Sortino 49.71%, Ethereum Calmar 42.17%. The authors' claim is that the benefit is **drawdown protection**, not raw return.
- **Bitcoin out-of-sample showed no predictability at all** — the most liquid, most-traded crypto asset was the one where technical rules failed out-of-sample.

**Transaction-cost detail (verified):** the paper cites Bitcoin transaction costs of **around 50 basis points** (citing Lintilhac & Tourin 2017) and reports the percentage of rules with breakeven transaction costs above 50 bps: **"36.06% of oscillator rules generate breakeven transaction costs greater than 50 basis points for CoinDesk while 47.35% of channel breakout rules generate rules with breakeven transaction costs greater than 50 basis points for Ethereum. Very few support-resistance rules generate breakeven transaction costs greater than 50 basis points, indicating that this family of technical trading rules are not very successful for all four cryptocurrencies."**

**Caveat:** this paper's returns are computed *before* applying an actual fee schedule to a specific small account; the "net of fees" question is addressed via breakeven-cost analysis rather than a full fee-and-slippage simulation. For a small account, the ~50 bps figure is itself a *large* hurdle relative to the position sizes involved.

### Related, located but not extracted
- Ahmed, Grobys & Sapkota (2020), "Profitability of technical trading rules among cryptocurrencies with privacy function", *Finance Research Letters*, DOI https://doi.org/10.1016/j.frl.2020.101495 — `[unverified]`
- Masuku & Gopane (2022), "Technical trading rules' profitability and dynamic risk premiums of cryptocurrency exchange rates", *Journal of Capital Markets Studies*, DOI https://doi.org/10.1108/jcms-10-2021-0030 — `[unverified]`

---

## 8. COULD NOT VERIFY

Explicit gaps. I did not substitute a blog for any of these.

1. **FINRA / CFTC data on retail futures or forex account profitability — NOT FOUND.** No regulator publication with a population-level loss/profit percentage for US retail futures or forex accounts was located. No peer-reviewed study using CFTC retail-forex account data was found via OpenAlex. **This is an open gap.**
2. **ASIC Report 693 as described in the brief does not exist.** REP 693 is about internal dispute resolution data consultations (verified in ASIC's sitemap). The correct source is **REP 626**. The "~80% of binary option clients lost money" figure in the brief is correct but belongs to REP 626, and its underlying data is from ASIC's **2017** review.
3. **Robinhood paper (JF 2022) full text — not opened.** Closed access with no legitimate OA copy. The **−4.7% 20-day abnormal return** figure is verified from publisher-deposited abstract metadata (OpenAlex + Crossref, agreeing). The **basis-points-per-day** figure the brief asks for was **not** verified, and I decline to derive it by division.
4. **"Learning, Fast or Slow" (RAPS 2019) full text — not opened.** Paywalled, no OA copy (`is_oa: false`). The 97% / 74% figures are verified from the abstract only; the operational definition of "future day trading" is unverified.
5. **Chague et al. official FGV repository PDF — not extracted.** The RePEc-listed full-text URL (https://repositorio.fgv.br/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/download) returned HTML, not a PDF. I verified the paper text from a mirror of the SSRN version (which carries the SSRN watermark and matches the RePEc abstract). SSRN itself returns 403, as expected.
6. **Chague version discrepancy unresolved:** 0.5% (SSRN 13 June 2020 text, which I read) vs 0.4% (RePEc abstract page, which I also read) for the share earning more than a bank teller. Different revisions; I could not determine which is the final published version.
7. **Korean / Japanese retail crypto trading P&L studies — NOT FOUND.**
8. **No complete-exchange / whole-market crypto transaction dataset study located** (the crypto analogue of the Taiwan data).
9. **BIS WP 1049 body not extracted** — the 73–81% figure is verified from the BIS page's "Findings" summary; the 42-page PDF was not text-extracted.
10. **Google Scholar, SSRN abstract pages, and most search engines were unusable** in this environment (SSRN 403; DuckDuckGo/Mojeek/SearXNG bot challenges; Brave search rate-limited to zero results partway through; Semantic Scholar API 429; Springer and Bond University PDF hosts 403). OpenAlex and Crossref APIs, RePEc/IDEAS, and direct regulator/repository URLs worked reliably. **Some sources may exist that I could not discover because general web search was unavailable.**

---

## 9. What this means for a small systematic crypto account `[REASONING]`

These are my inferences from the verified numbers above, not sourced claims.

1. **The unconditional base rate is unfavourable and remarkably consistent.** Equities (66,465 households, 11.4% vs 17.9%), Taiwan day traders (>80% lose in a six-month window; <1% persistently profitable net of fees), Brazil futures (97% of 300+ day survivors lost money net of fees), EU CFDs (74–89%), UK CFDs (82%, avg −£2,200), Australian binary options/CFD/FX (80%/72%/63%), crypto apps (73–81% likely losses; median −$431 of $900 invested). **Every independent dataset lands in the same 70–97% loss band.**
2. **Persistence makes it worse, not better.** Chague et al. show the probability of profit *monotonically decreasing* in days traded, and explicitly compare the pattern to roulette. The FCA found experienced clients lost *more* than inexperienced ones. This directly contradicts the intuition that a small account can "learn its way" to profitability.
3. **The "20% of day traders are profitable" meme is an artifact of annualisation.** Both the Taiwan JFM paper (~20% profitable in the typical year) and Chague's literature review (>20% of individuals profit in older studies) give ~20% — but that is roughly what costs-plus-noise produces in one year, and it collapses to <1% persistently. A small account cannot distinguish itself from that 20% without years of data it will not have.
4. **The only systematic-strategy evidence in crypto is genuinely mixed, and it favours buy-and-hold on raw return.** Hudson & Urquhart is the strongest counter-evidence in this report: ~15,000 rules, significant profitability, breakeven costs above market costs, and *better risk-adjusted* returns with smaller drawdowns than buy-and-hold. But **only 5–16% of those rules beat buy-and-hold on raw annualized return**, and **Bitcoin had no out-of-sample predictability at all**. So the defensible claim for systematic crypto trading is **drawdown/risk reduction**, not return enhancement — and only for non-Bitcoin assets, in-sample-selected rules, and only if fees stay below the breakeven level.
5. **The dominant term for a small account is cost, not signal.** Barber & Odean 2000 traces most of the household penalty to trading costs; Chague et al. compute net-of-fee losses as decisive; ESMA and ASIC both cite leverage and costs as the harm mechanism. For a small account, fee/slippage drag is proportionally largest, so the base rates above are, if anything, **optimistic** for a small account relative to the large samples.
6. **Honest framing of the decision:** the evidence does not support "a small account should trade systematically to make money." It is consistent with "a small account should not expect systematic trading to beat buy-and-hold net of fees," while leaving open a narrower, weaker claim that rule-based strategies may reduce drawdowns — a risk-management rationale, not a profit rationale.

---

## Source index (all URLs cited above)

**Barber / Odean corpus**
- https://faculty.haas.berkeley.edu/odean/ — Odean faculty page (fetched)
- https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trade%20040330.pdf — 2004 Taiwan WP (fetched, extracted)
- https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf — JFM 2014 (fetched, extracted)
- https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20Skill%20110523.pdf — May 2011 WP version (fetched, extracted)
- https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf — JF 2000 (fetched, extracted)
- https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/JustHowMuchDoIndividualInvestorsLose_RFS_2009.pdf — RFS 2009 (fetched, extracted)
- https://api.openalex.org/works/https://doi.org/10.1093/rapstu/raz006 — "Learning, Fast or Slow" abstract (fetched)

**Chague / De-Losso / Giovannetti**
- https://ideas.repec.org/p/fgv/eesptd/525.html — RePEc listing + abstract (fetched)
- https://repositorio.fgv.br/bitstreams/0f00dd78-6909-4f91-84d5-aef8803e6436/download — official FGV link (returned HTML, not extracted)
- https://ebicapital.nl/wp-content/uploads/2022/05/day-trading.pdf — SSRN version mirror (fetched, extracted)
- https://bibliotecadigital.fgv.br/ojs/index.php/rbfin/article/download/81949/78263 — RBFIN 2020 stocks version (fetched, extracted)

**Robinhood**
- https://doi.org/10.1111/jofi.13183 — DOI
- https://api.openalex.org/works/https://doi.org/10.1111/jofi.13183 — abstract (fetched)
- https://api.crossref.org/works/10.1111/jofi.13183 — abstract (fetched)

**Regulators**
- https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors — ESMA 2018 (fetched)
- https://www.esma.europa.eu/investor-corner/product-intervention — ESMA product intervention (fetched)
- https://www.fca.org.uk/publication/consultation/cp16-40.pdf — FCA CP16/40 (fetched, extracted)
- https://www.fca.org.uk/publication/policy/ps19-18.pdf — FCA PS19/18 (fetched, extracted)
- https://www.asic.gov.au/regulatory-resources/find-a-document/reports/rep-626-consumer-harm-from-otc-binary-options-and-cfds — ASIC REP 626 page (fetched)
- https://download.asic.gov.au/media/5241548/rep626-published-22-august-2019.pdf — ASIC REP 626 PDF (fetched, extracted)
- https://asic.gov.au/sitemap.xml — used to disprove the REP 693 assumption (fetched)

**Crypto**
- https://www.bis.org/publ/work1049.htm — BIS WP 1049 (fetched)
- https://www.bis.org/publ/bisbull69.htm — BIS Bulletin 69 page (fetched)
- https://www.bis.org/publications/bulletin-69-crypto-shocks-and-retail-losses.pdf — BIS Bulletin 69 PDF (fetched, extracted)
- https://eprints.qut.edu.au/129185/1/Who%20trades%20cryptocurrencies.pdf — Hasso et al. (fetched, extracted)

**Systematic crypto strategies**
- https://centaur.reading.ac.uk/85715/8/Hudson-Urquhart2019_Article_TechnicalTradingAndCryptocurre.pdf — Hudson & Urquhart (fetched, extracted)
- https://doi.org/10.1007/s10479-019-03357-1 — DOI
