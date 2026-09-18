# How many strategies should a small retail bot run — and how real is the overfitting risk?

**Research date:** 2026-09-18
**Verification method:** every URL below was fetched by me. Where a claim is quoted, I downloaded and text-extracted the actual PDF/HTML and read it. HTTP status codes are reported per item. Items I could not verify are listed separately in §7 and are **not** cited as evidence.

## Source-type legend

| Label | Meaning |
|---|---|
| **[PEER-REVIEWED]** | Refereed journal / conference proceedings |
| **[AMS NOTICES]** | *Notices of the AMS* — a professional-society expository magazine, not a standard refereed research journal |
| **[PREPRINT]** | arXiv / SSRN / NBER working paper — **not** peer reviewed |
| **[BOOK]** | Published book (publisher page verified; I did not read the full text) |
| **[PRACTITIONER]** | Identifiable, credentialed practitioner writing on their own site |
| **[PRACTITIONER-BLOG]** | Self-published / vendor blog — low evidentiary weight |

---

## 0. Bottom line up front

1. **The overfitting evidence is strong, quantitative, and peer-reviewed.** The number that matters is not "how many strategies" but "how many *trials* did you run to find this one" — and the published machinery for that (Deflated Sharpe Ratio, PBO/CSCV, Minimum Backtest Length) is real, citable, and has hard numbers attached.
2. **The "how many strategies" question is mostly opinion, not evidence.** I could not find a single study that establishes an optimal strategy count for retail. The best *evidence* is Rob Carver's own disclosed production numbers — one professional running ~11 rule families / ~40 rule variations across 100–200+ instruments. That is a data point about a well-capitalised professional, not a prescription for a small account, and Carver himself argues the opposite priority order (framework and instrument diversification first, extra rules last, with "rapidly diminishing returns").
3. **The AI/LLM evidence is much stronger than I expected, and it is now the single best-documented failure mode.** Multiple independent groups show LLMs leak the future into backtests. The one paper that applies Deflated Sharpe / PBO to LLM-discovered strategies rejects *every* LLM-discovered strategy it tested.
4. **The crypto correlation point is the most under-appreciated of the five.** Giller (2024) measures a 14-coin retail universe and finds the whole portfolio behaves like **~2 independent bets** (N\* = 1.96). Running 20 strategies across BTC/ETH/SOL/XRP is not 20 bets and is arguably not even 4.

---

## 1. Marcos López de Prado and the backtest-overfitting literature

### 1.1 The Deflated Sharpe Ratio (DSR)

**Bailey, D. H., & López de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality." *Journal of Portfolio Management*, 40(5).**
**[PEER-REVIEWED]**

- Full text verified: <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf> — HTTP 200, 1,048,118 bytes, 11 pages, extracted and read. Header states *"Journal of Portfolio Management, Forthcoming, 2014"*.
- SSRN abstract page: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551> — HTTP 403 to automated fetch (SSRN bot-blocks); the ID and title were confirmed via search-result metadata. Prefer the Bailey PDF.

**The central result.** Under the null of zero true skill, the *expected maximum* Sharpe ratio across N independent trials grows without bound:

> E[max{SR}] ≈ E[{SR}] + √V[{SR}] · [ (1−γ)·Z⁻¹(1 − 1/N) + γ·Z⁻¹(1 − 1/(N·e)) ]   *(their Equation 1)*

where γ ≈ 0.5772 is the Euler–Mascheroni constant and Z⁻¹ is the inverse standard-normal CDF. Their Appendix 1 proves this; Appendix 2 validates it numerically; Appendix 3 shows how to convert M *correlated* trials into an equivalent number of independent trials N.

**The concrete worked example (verbatim from the paper):**

> "Should the strategist have made his discovery after running only N=46 independent trials, the investor may have allocated some funds, as [DSR] would have been 0.9505, above the 95% confidence level."

> "If the strategy had exhibited Normal returns, [DSR would have fallen below the threshold] after N=88 independent trials."

So: **the same backtest is investable at 46 trials and not investable at 88.** The backtest itself did not change; only the disclosed trial count did.

**Their answer to "how many strategies should I test?" — the optimal-stopping rule.** The paper devotes a section to this:

> "Multiple testing exercises should be carefully planned in advance, so as to avoid running an unnecessarily large number of trials. Investment theory, not computational power, should motivate what experiments are worth conducting."

> "From the set of strategy configurations that are theoretically justifiable, sample a fraction 1/e (roughly 37%) of them at random and measure their performance. After that, keep drawing and measuring the performance of additional configurations from that set, one by one, until you find one that beats all of the previous. That is the optimal number of trials."

**This is the closest thing in the literature to an answer to your question (1)** — and note what it says: the *optimal* number of trials is not a fixed count. It is a fraction (≈37%) of the set of *theoretically justifiable* configurations, followed by a stopping rule. It also explicitly rejects "just test more."

Two more quotable lines:

> "every additional trial irremediably increases the probability of a false positive"

> "The customary disclaimer that 'past performance does not guarantee future results' is too lenient when in fact adverse outcomes are very likely."

### 1.2 The Probability of Backtest Overfitting (PBO) and CSCV

**Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2015). "The Probability of Backtest Overfitting." Working paper, dated 27 February 2015.**
**[PREPRINT / working paper]** — I could not verify a peer-reviewed journal venue for this specific paper, so I do not claim one.

- Full text verified: <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf> — HTTP 200, 1,145,522 bytes, extracted and read.
- Institutional repository copy: <https://scholarworks.wmich.edu/math_pubs/42/> — HTTP 200, page title verified as *"The Probability of Backtest Overfitting" by David H. Bailey, Jonathan Borwein et al.*
- SSRN: <https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253> — HTTP 403 to automated fetch; ID/title confirmed via search metadata.

**Method — combinatorially symmetric cross-validation (CSCV).** Split the backtest's return matrix into S sub-matrices. For every way of choosing S/2 of them as the in-sample (IS) set (the rest becoming out-of-sample, OOS), select the best strategy IS and record its OOS rank as a logit λ. Then:

> PBO = ∫₋∞⁰ f(λ)dλ

i.e. *the rate at which the IS-optimal strategy underperforms the median of the OOS trials.* Note the crucial property: **each training subset is also reused as a testing subset and vice versa.**

**The combinatorial explosion they cite as motivation:**

> "For instance, if S = 16, we will form 12,780 combinations."

**Their suggested decision threshold:**

> "In accordance with standard applications of the Neyman-Pearson framework, a customary approach would be to reject models for which PBO is estimated to be greater than 0.05."

**The empirical result that should worry anyone with a good-looking backtest (verbatim):**

> "Whereas 100% of the SR IS are positive, about 78% of the SR OOS are negative. Also, Sharpe ratios IS range between 1 and 3, indicating that backtests with high Sharpe ratios tell us nothing regarding the representativeness of that result."

> "We cannot hope escaping the risk of overfitting by exceeding some SR IS threshold. On the contrary, it appears that the higher the SR IS, the lower the SR OOS."

That example's estimated **PBO was 74%** — i.e. a backtest whose in-sample Sharpe ratios ran from 1 to 3, with a 74% probability of being overfit.

**On hold-out and minimum sample sizes:**

> "for example, if a strategy trades on a weekly basis, hold-out should not be used on backtests of less than 20 years."

### 1.3 Pseudo-Mathematics and Financial Charlatanism — the headline numbers

**Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance." *Notices of the American Mathematical Society*, 61(5), May 2014, pp. 458–471.**
**[AMS NOTICES]** — expository society magazine. The authors thank referees who reviewed this and a related article, but I would not label it a standard refereed research paper.

- Full text verified: <https://www.ams.org/notices/201405/rnoti-p458.pdf> — HTTP 200, 3,011,500 bytes, 14 pages, extracted and read. (Note: this URL returns 403 to `web_fetch`-style requests; it succeeded with a browser User-Agent via curl.)
- SSRN: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659> — HTTP 403 to automated fetch.

**Theorem 2 — Minimum Backtest Length (MinBTL):**

> MinBTL ≈ ( [ (1−γ)Z⁻¹(1 − 1/N) + γZ⁻¹(1 − 1/(N·e)) ] / E[max_N SR] )²  <  2·ln[N] / E[max_N SR]²

**The headline claim, verbatim:**

> "For instance, if only five years of data are available, no more than forty-five independent model configurations should be tried or we are almost guaranteed to produce strategies with an annualized Sharpe ratio IS of 1 but an expected Sharpe ratio OOS of zero."

> "After trying only seven independent strategy configurations, the expected maximum SR IS is 1 for a two-year long backtest, while the expected SR OOS is 0."

**And the 20-trials claim:**

> "suppose that a researcher is given a finite sample and told that she needs to come up with a strategy with an SR above 2.0, based on a forecasting equation for which the AIC statistic ... rejects the null hypothesis of overfitting with a 95 percent confidence level (i.e., a false positive rate of 5 percent). After only twenty trials, the researcher is expected to find one specification that passes the AIC criterion."

**And the disclosure demand:**

> "a backtest which does not report the number of trials N used to identify the selected configuration makes it impossible to assess the risk of overfitting."

**⚠️ Important caveat they state themselves:** the N trials are assumed **independent**, "which leads to a quite conservative estimate. If the trials performed were not independent, the number of independent trials N involved could be derived using a dimension-reduction procedure, such as Principal Component Analysis."

I independently reproduced their formula and it matches their published figures exactly — see §2.2.

### 1.4 "The 10 Reasons Most Machine Learning Funds Fail"

**López de Prado, M. "The 10 Reasons Most Machine Learning Funds Fail." GARP white paper.** **[PRACTITIONER / industry white paper]** — not peer reviewed.

- Landing page verified: <https://www.garp.org/white-paper/the-10-reasons-most-machine-learning-funds-fail> — HTTP 200, title verified.
- PDF verified: <https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf> — HTTP 200, 1,317,652 bytes, 21 pages, extracted and read.
- SSRN: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104816> — HTTP 403 to automated fetch.

**The 10 pitfalls (verbatim from Exhibit 1):**

| # | Category | Pitfall | Solution |
|---|---|---|---|
| 1 | Epistemological | The Sisyphus paradigm | The meta-strategy paradigm |
| 2 | Epistemological | Research through backtesting | Feature importance analysis |
| 3 | Data processing | Chronological sampling | The volume clock |
| 4 | Data processing | Integer differentiation | Fractional differentiation |
| 5 | Classification | Fixed-time horizon labeling | The triple-barrier method |
| 6 | Classification | Learning side and size simultaneously | Meta-labeling |
| 7 | Classification | Weighting of non-IID samples | Uniqueness weighting; sequential bootstrapping |
| 8 | Evaluation | Cross-validation leakage | Purging and embargoing |
| 9 | Evaluation | Walk-forward (historical) backtesting | Combinatorial purged cross-validation |
| 10 | **Evaluation** | **Backtest overfitting** | **Backtesting on synthetic data; the deflated Sharpe ratio** |

Note pitfall #9: López de Prado regards **walk-forward backtesting itself as a pitfall**, because WF exhibits high variance and "a large portion of the decisions are based on a small portion of the dataset," which "leads to false discoveries, because researchers will select the backtest with the maximum estimated Sharpe ratio, even if the true Sharpe ratio is zero."

**Pitfall #10 states the null-maximum result directly:**

> E[max{xᵢ}] ≈ (1−γ)Z⁻¹[1 − 1/I] + γZ⁻¹[1 − 1/(I·e⁻¹)] ≤ √(2·log[I])

> "Even though the true Sharpe ratio is zero, we expect to find one strategy with a Sharpe ratio of E[max{yᵢ}] = E[max{xᵢ}]·σ[yᵢ]"

> "it is imperative to control for the number of trials (I) in the context of WF backtesting. Without this information, it is not possible to determine the Family-Wise Error Rate (FWER), False Discovery Rate (FDR), Probability of Backtest Overfitting (PBO) or similar."

### 1.5 *Advances in Financial Machine Learning* (the book)

**López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.**
**[BOOK]**

- Publisher page verified: <https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086> — HTTP 200.

**Honest disclosure: I did not read this book.** I cite it only as the book reference. Every specific quantitative claim in this report is sourced from the papers above (which are freely available and which I did read), not from the book. If you need a book-level citation, note that the book's relevant content is the expanded version of the papers in §1.1–§1.3 and §1.4.

---

## 2. Quantifying "N trials → spurious winner"

### 2.1 Sourced claims

All from the papers in §1:

| Claim | Number | Source |
|---|---|---|
| Expected max Sharpe under the null, given N independent trials | E[max SR] ≈ σ_SR · [(1−γ)Z⁻¹(1−1/N) + γZ⁻¹(1−1/(N·e))] | DSR paper Eq. 1 **[PEER-REVIEWED]** |
| Upper bound on the same | ≤ σ_SR · √(2 ln N) | AMS 2014 Eq. 6; GARP Pitfall #10 |
| Independent configurations defensible on 5 years of data (for E[max SR]=1) | **45** | AMS 2014, Fig. 2 |
| Independent configurations defensible on 2 years of data | **7** | AMS 2014, Fig. 2 |
| Trials before a 5%-false-positive AIC test yields an SR>2.0 spec | **20** | AMS 2014 |
| Trials at which a real discovery becomes non-investable (DSR < 95%) | **46 → 88** | DSR paper |
| PBO rejection threshold | **> 0.05** | PBO paper |
| CSCV combinations at S=16 | **12,780** | PBO paper |
| Minimum hold-out length for a weekly strategy | **20 years** | PBO paper |
| Technical trading rules tested on the DJIA over 100 years | *universe expanded from Brock/Lakonishok/LeBaron's 26; I could not verify the commonly cited "7,846" figure — see §7* | Sullivan/Timmermann/White **[PEER-REVIEWED]** |
| Technical trading rules tested in FX | **2,127** | Qi & Wu (2006) **[PEER-REVIEWED]** |
| t-statistic hurdle for a newly discovered factor | **> 3.0** (vs. the usual 2.0) | Harvey, Liu & Zhu **[PEER-REVIEWED]** |

**Harvey, C. R., Liu, Y., & Zhu, H. (2016). "…and the Cross-Section of Expected Returns." *Review of Financial Studies*.** **[PEER-REVIEWED]**
Accepted-manuscript PDF verified: <https://faculty.fuqua.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.pdf> — HTTP 200, 969,629 bytes, 27 pages, extracted and read (PDF header reads "Received October 22, 2014; accepted June 15, 2015 by Editor Andrew Karolyi"). NBER WP version verified at <https://www.nber.org/papers/w20592> — HTTP 200, with title, authors (Campbell R. Harvey, Yan Liu, Heqing Zhu), date 2014-10-20 and DOI 10.3386/w20592 confirmed from the page. Note: the third author is **Heqing** Zhu (some secondary sources misstate this as "Caroline"). Verbatim from the abstract:

> "Given this extensive data mining, it does not make sense to use the usual criteria for establishing significance. Which hurdle should be used for current research? Our paper introduces a new multiple testing framework and provides historical cutoffs from the first empirical tests in 1967 to today. A new factor needs to clear a much higher hurdle, with a t-statistic greater than 3.0. We argue that most claimed research findings in financial economics are likely false."

Also verified: NBER Working Paper w20592, <https://www.nber.org/papers/w20592> — HTTP 200, title/authors/DOI (10.3386/w20592) confirmed. The paper also states (p. 1502) "we believe the minimum threshold t-statistic for 5% significance is about 2.8" and reports BHY-implied thresholds of ~3.05–3.18.

**Sullivan, Timmermann & White (1999), "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap," *Journal of Finance* 54(5), 1647–1691.** **[PEER-REVIEWED]**
DOI: <https://doi.org/10.1111/0022-1082.00163> — **HTTP 403 to automated fetch** (Wiley bot-block). Metadata (title, three authors, venue, year, DOI) verified via the OpenAlex API. Abstract verified verbatim:

> "we utilize White's Reality Check bootstrap methodology to evaluate simple technical trading rules while quantifying the data-snooping bias and fully adjusting for its effect in the context of the full universe from which the trading rules were drawn. ... We consider the study of Brock, Lakonishok, and LeBaron (1992), expand their universe of 26 trading rules, apply the rules to 100 years of daily data on the Dow Jones Industrial Average, and determine the effects of data-snooping."

**⚠️ I could not read the full text** (paywalled, 403). I therefore do **not** state the paper's headline conclusion, and I do **not** cite the widely repeated "7,846 rules" figure, because I could not verify either. The abstract alone is what I am willing to stand behind.

**White, H. (2000), "A Reality Check for Data Snooping," *Econometrica* 68(5).** **[PEER-REVIEWED]**
DOI: <https://doi.org/10.1111/1468-0262.00152> — HTTP 403 to automated fetch; metadata verified via OpenAlex (1,887 citations). This is the method Sullivan et al. apply. Content unread by me.

**Qi, M., & Wu, Y. (2006), "Technical Trading-Rule Profitability, Data Snooping, and Reality Check: Evidence from the Foreign Exchange Market," *Journal of Money, Credit and Banking*.** **[PEER-REVIEWED]**
DOI: <https://doi.org/10.1353/mcb.2007.0006> — HTTP 200. Abstract verified verbatim via OpenAlex:

> "We report evidence on the profitability and statistical significance among 2,127 technical trading rules. The best rules are found to be significantly profitable based on standard tests. We then employ White's (2000) Reality Check to evaluate these rules and find that data-snooping biases do not change the basic conclusions for the full sample. A sub-sample analysis indicates that the data-snooping problem is more serious in the second half of the sample. Profitability becomes much weaker in the more recent period, suggesting that the foreign exchange market becomes more efficient over time."

This is a useful **counterweight**: it shows the data-snooping correction does not always kill the result — but it also shows profitability decaying over time as markets adapt, which is the same practical outcome.

### 2.2 My own calculation (⚠️ not a sourced claim — clearly labelled)

I implemented the published formula from the DSR paper (Eq. 1) and the AMS MinBTL Theorem 2 to produce the tables below. **These numbers are my computation, not a quotation.** They are included only because the papers give the formula but not a convenient table.

**Validation first** — my implementation reproduces the AMS paper's Figure 2 exactly, which is why I trust it:

| N trials | My MinBTL (years) | AMS paper's stated value |
|---|---|---|
| 7 | 1.92 | "two-year long backtest" |
| 45 | 5.00 | "five years of data" |

**Expected maximum Sharpe ratio under the null (true skill = 0):**

| N trials | Multiplier E[max]/σ_SR | If σ_SR = 0.3 | If σ_SR = 0.5 | If σ_SR = 1.0 |
|---|---|---|---|---|
| 10 | 1.57 | 0.47 | 0.79 | 1.57 |
| 20 | 1.90 | 0.57 | 0.95 | 1.90 |
| 45 | 2.24 | 0.67 | 1.12 | 2.24 |
| 100 | 2.53 | 0.76 | 1.27 | 2.53 |
| 1,000 | 3.26 | 0.98 | 1.63 | 3.26 |

**How to read this:** σ_SR is the *dispersion of Sharpe ratios across your trials*. If you optimise a strategy over 100 parameter/rule combinations and the trial Sharpe ratios scatter with a standard deviation of 0.5, you should **expect the winner to show an annualised Sharpe of ~1.27 even if no version has any edge at all.** That is the single most important number in this report.

**Minimum backtest length needed to keep E[max SR] at 1.0:**

| N trials | MinBTL (years) | Loose bound 2·ln(N) |
|---|---|---|
| 5 | 1.4 | 3.2 |
| 10 | 2.5 | 4.6 |
| 20 | 3.6 | 6.0 |
| 45 | 5.0 | 7.6 |
| 100 | 6.4 | 9.2 |
| 1,000 | 10.6 | 13.8 |

**My honest read:** for a retail crypto bot with, say, 3 years of usable hourly data and more than ~20 genuinely independent trials, the literature says you are in the zone where an SR-1 backtest is expected even with zero edge. Crypto's very short usable history makes this worse, not better — MinBTL is measured in *years of backtest*, and 3 years of BTC data is a hard ceiling you cannot buy your way out of.

---

## 3. Practitioner consensus on portfolio/strategy count

### 3.1 ⚠️ The blunt verdict first

**There is no evidence-based answer to "how many strategies should a retail trader run."** I searched for it specifically. What exists is:

- **One source with real disclosed numbers**: Rob Carver's own production system (§3.2).
- **General diversification mathematics** that is universally accepted but says nothing about strategy count specifically (§3.3).
- **Opinion** from practitioners, which is coherent and worth reading but is not evidence.

Anyone who quotes you a specific number ("run 5–10 strategies", "run 3–5") is expressing a preference. I found no study supporting any such figure. Treat any specific count as opinion.

### 3.2 Rob Carver — the best available evidence (still not a prescription)

Carver is a former AHL/Man Group systematic trader; author of *Systematic Trading*, *Advanced Futures Trading Strategies*, and *Leveraged Trading*. His site and blog are the primary source. All URLs below verified HTTP 200.

**His priority ordering — extra strategies come LAST:**

Source: "Some more trading rules" (7 June 2017), <https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html> **[PRACTITIONER]**

> "It is a common misconception that the most important thing to have when you're trading, or investing, systematically is good trading rules. In fact it is much, much, much more important to have a good position management framework ... and to trade a diversified set of instruments. **Combine those with a couple of simple trading rules, and you'll have a pretty decent system. Adding additional rules will improve your expected return, but with rapidly diminishing returns.**"

> "Adding trading rules should be your last resort once you have a decent framework, and have done as much instrument diversification as your capital can cope with."

> "Does adding these rules improve the performance of a basic trend following using EWMAC on price, plus carry strategy? **It doesn't** (I did warn you right at the start of the post!)"

That last one is striking: when he actually tested adding a batch of new rules, measured performance got *slightly worse*, not better.

**His actual disclosed system — the closest thing to a real answer:**

Source: "My trading system" (2 Dec 2021), <https://qoppac.blogspot.com/2021/12/my-trading-system.html> **[PRACTITIONER]**

He lists **11 rule families**: EWMAC momentum, breakout, relative (cross-sectional) momentum, asset-class trend, normalised momentum, acceleration, slow mean reversion within an asset class, carry, relative carry, skew (absolute and RV), and mean reversion in the wings — and ~40 individual rule *variations* (breakout10/20/40/80/160/320, carry10/30/60/125, momentum4–64, etc.).

Key disclosed figures from that post:

> "Of the 146 instruments in the dataset, 109 have positive Sharpe Ratios, with the median Sharpe Ratio coming in at 0.27."

> "The average correlation between subsystem returns is basically zero: 0.05."

> "Fun fact: If you could only trade one rule, I guess it would be carry. If you could trade two, well that would be carry and a slowish momentum"

And on the rules that lose money — he keeps them anyway:

> "In bold are the rules that are genuine money losers ... What these all have in common is they are non trendy, mean reverting, and hence highly diversifying rules. I haven't dropped them, because a proper handcrafting process would give them a positive weight: they are strongly negatively correlated to the trendy rules, and whilst their negative Sharpe Ratio tilts their allocation down a little, the uncertainty about backtested Sharpes means they are still justified a positive weighting."

**His instrument-count / Sharpe ladder, with only 2–3 rules:**

Source: "Diversification and small account size" (9 Mar 2016), <https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html> **[PRACTITIONER]**

> "The average Sharpe ratio of each individual instrument is around 0.42. This is pretty high given we only have two trading rules: Carry and three slow variations of EWMAC. However many instruments are only recent arrivers in the porfolio, during a period in which the system did very well indeed. This will be biasing results upwards. If we time weight the returns to correct for this then the average is a more reasonable 0.35."

His stated rules of thumb for the number of **instruments** (not rules):

| Instruments | Expected SR |
|---|---|
| 1 | 0.35 |
| 2 | 0.45 |
| 3 | 0.50 |
| 4 | 0.54 |
| 5 | 0.57 |
| 6 | 0.58 |
| 7 | 0.60 |
| 8 (one per asset class) | 0.61 |
| 15 (two per asset class) | 0.65 |
| 37 (all) | 0.70 |

**This table is the most useful single artefact for your question.** It shows the marginal value of *breadth*: going from 1 to 8 instruments adds ~0.26 SR; going from 8 to 37 adds ~0.09. The curve flattens hard. Carver's point in the same post is that a small account cannot buy this ladder at all — with small capital you are forced into binary (all-or-nothing) positions, which he measures as ~20% worse than normal sizing.

**Carver on how little rule diversification there actually is:**

- "Historic and recent performance by trading rule" (11 May 2022), <https://qoppac.blogspot.com/2022/05/historic-and-recent-performance-by.html> — on a group of divergent rules: *"With the exception of relative momentum, all very good, but also all very similar so not much diversification there."* And of three others: *"Notice how correlated these last 3 rules are."*
- "Clustering trading rule p&l" (12 May 2023), <https://qoppac.blogspot.com/2023/05/clustering-trading-rule-p.html> — clustering the rule-return correlation matrix reveals: *"fast momentum like trading rules have more in common with other fast momentum trading rules, than they do with slow variations of themselves."* I.e. **"momentum at 10 days" and "momentum at 20 days" are near-duplicates**, not diversifiers. This is the rule-level version of the crypto-correlation problem in §5.

**Carver's overfitting taxonomy — the single best practitioner treatment I found:**

Source: "The three kinds of (over) fitting" (2 Sept 2021; drafted 2015), <https://qoppac.blogspot.com/2015/11/the-three-kinds-of-overfitting.html> **[PRACTITIONER]**

He distinguishes:
1. **Explicit fitting** — automated parameter search / grid search / neural nets. "The good news about explicit fitting is that it's possible to do it properly."
2. **Implicit fitting** — "occurs when you make any decision having seen the results of testing with both in and out of sample data." He ranks examples from worst to least bad, and the mildest is: *"Run a single backtest to try out an idea. The idea doesn't work, so you forget about it completely."*
3. **Tacit fitting** — the one almost nobody accounts for. His worked example ("Barbara") restricts a moving-average rule to momentum only (A<B) because she knows momentum works. He argues that decision *itself* is a time-machine violation: *"Had she really been at the start of her backtest data ... would she have known that momentum is more likely to be profitable than mean reversion? Strictly speaking the answer is no."* The tacit knowledge came from papers, conferences, a boss, or her Uber driver.

He is explicit about the incentive problem:

> "if you're an academic then you get paid for publishing papers with nice results: papers that predict the past. If you're working for a quant hedge fund then you may be getting paid for coming up with nice backtests that also predict the past. And even as a humble independent trader, we get a kick out of a nice backtest. ... **Basically: our incentives make us prone to overfitting**"

He also dismisses the naive fix, which is directly relevant to anyone planning to correct for trial count:

> "They include correcting your significance level for the number of trials you have done (**which I don't like**, since it treats a major case of parameter cheating the same as a tiny hyper parameter tweak), and testing on multiple paths to catch especially egregious over fitting (something like CPCV)"

**Carver demonstrating overfitting empirically:**

Source: "Quickies #1: Overfitting and EWMAC forecast scalars" (2 June 2025), <https://qoppac.blogspot.com/2025/06/quickies-1-overfitting-and-ewmac.html> **[PRACTITIONER]**

He fits a pattern-based method on Microsoft using 16 periods of 4 days, up to 2015, then tests on the last ten years:

> "after 2015 when it is trading on price history it hasn't seen, its performance radically deteriorates."

> "The light gray line shows what happens if use the 2015 Microsoft method to subsequently trade Apple (AAPL). You can clearly see that the performance is terrible. This method is too closely fitted to the returns of Microsoft pre-2015; it does not perform well in later years, especially with a different stock."

And the control: a much simpler model (one 64-day period) fits identically whether trained to 2015 or on all data, and "does very well on Apple stock, which it hadn't seen before." **Simple survives, complex dies.** Amusing footnote: he used ChatGPT to fit one scaling formula ("I used..... chatgpt!").

**Carver on diversification mathematics (the general case):**

Source: "How to write a tweet that gets over 300k views; and why diversification is probably good" (17 Mar 2026), <https://qoppac.blogspot.com/2026/03/how-to-write-tweet-that-gets-over-300k.html> **[PRACTITIONER]**

> "My third favourite formula is that risk will be reduced by sqrt(N) if you increase the number of assets in your portfolio by N, and all your assets are independent; **higher correlations will lead to smaller reductions.**"

> "Let's make some assumptions ... We have a choice between N=3 assets, and N=48 assets ... The correlation of those assets is 0.5 ... the expected SR is 0.25 on each asset ... The Sharpe Ratios on those should be 1.22\*0.25 = 0.306 and 1.4\*0.25 = 0.35."

> "the key number in all of the above is the average correlation between stocks; **if it's 0.7 then the CAGR improvement falls from 70bp to 42 bp unleveraged**"

Note that this is *asset* diversification at correlation 0.5–0.7. Crypto correlations are in that range or worse (§5), and strategy-level diversification is weaker still because strategies on the same instrument share the instrument's return.

- Book references: <https://www.systematicmoney.org/systematic-trading-information> and <https://www.systematicmoney.org/advanced-futures-trading-strategies> — both HTTP 200. **[BOOK]**

### 3.3 Ernie Chan

Chan ran QTS Capital Management; author of *Quantitative Trading*, *Algorithmic Trading*, and *Machine Trading*. **[PRACTITIONER]**

**"Optimizing Trading Strategies Without Overfitting" (Chan & Ng, QTS Capital Management).** Presentation slides, verified: <https://epchan.com/img/links/Optimizing-Trading-Strategies-Without-Overfitting.pdf> — HTTP 200, 1,094,548 bytes, 21 pages, extracted and read.

Key slides:

> "Optimize trading strategy ≈ Optimize sum(PLs) by tweaking trading signals. ... Easy to cherry-pick trading signals for optimization. – Overfitting/data Snooping Bias. – No predictive power on unseen/out-of-sample data!"

> "**Conclusion:** Optimizing trading strategy parameters on historical data invites overfitting. More robust to fit time series (not trading) models on historical data instead."

And on the specific "how many strategies" question, from the slide titled "Suboptimal > optimal?":

> "Backtest of 'optimal' parameter underperforms that of 'suboptimal' parameter out-of-sample. ... **It is worth trading a range of k in the vicinity of the optimal for diversification.**"

So Chan's answer is not a count either — it's "run a *range* around the optimum, because you can't trust which point is best."

**Blog version with the argument in full:** <https://epchan.blogspot.com/2017/11/optimizing-trading-strategies-without.html> — HTTP 200. Verbatim:

> "Optimizing the parameters of a trading strategy via backtesting has one major problem: **there are typically not enough historical trades to achieve statistical significance.** Whatever optimal parameters one found are likely to suffer from data snooping bias, and there may be nothing optimal about them in the out-of-sample period. **That's why parameter optimization of trading strategies often adds no value.**"

His remedy is to fit a *time-series model* (AR/GARCH) to prices — where you have many observations — then simulate thousands of price paths and pick parameters that win most often across paths, rather than the parameter that won on the single realised path.

### 3.4 QuantStart (Michael Halls-Moore)

**[PRACTITIONER-BLOG]** — long-running, widely read retail-quant education site, but not peer reviewed and I found no disclosed track record.

- "Successful Backtesting of Algorithmic Trading Strategies – Part I": <https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-I/> — HTTP 200. Verbatim:

> "Optimisation bias is hard to eliminate as algorithmic strategies often involve many parameters. ... Optimisation bias can be minimised by **keeping the number of parameters to a minimum** and increasing the quantity of data points in the training set. In fact, one must also be careful of the latter as older training points can be subject to a prior regime ... and thus may not be relevant to your current strategy."

- "Simple versus Advanced Systematic Trading Strategies – Which is Better?": <https://www.quantstart.com/articles/simple-versus-advanced-systematic-trading-strategies-which-is-better/> — HTTP 200. Verbatim, on the risks of simple strategies:

> "While not specifically an issue with simple trading strategies it is common to see little or no robust statistical analysis carried out on simpler strategies. Hence many such strategies that show high performance in a backtest may simply be due to overfitting to the in-sample data."

**On Quantocracy specifically:** it is a **link aggregator** (a feed of quant blog posts). It publishes no claims and no research of its own, so there is nothing in it to cite as evidence. I mention this because it is often listed as a source; it is a discovery tool, not a source.

---

## 4. Evidence on LLM/AI-generated strategies being overfit or failing

**This is where the evidence turned out to be strongest — much stronger than I expected when I started.** It is also the most actively moving area, so treat the specifics as provisional.

### 4.1 The headline peer-reviewed negative result

**Li, W. W., Kim, H., Cucuringu, M., & Ma, T. "Can LLM-based Financial Investing Strategies Outperform the Market in Long Run?" — KDD '26 (32nd ACM SIGKDD), DOI 10.1145/3770854.3785702.** **[PEER-REVIEWED]**

- Preprint verified: <https://arxiv.org/abs/2505.07078> — HTTP 200 (v6, 26 Jun 2026). The arXiv page itself lists DOI `10.1145/3770854.3785702`, confirming the KDD '26 acceptance.
- ACM DL DOI page returns 403 to automated fetch; the DOI/title/venue were verified via Crossref metadata and the arXiv record.

Abstract, verbatim:

> "most evaluations of LLM timing-based investing strategies are conducted on narrow timeframes and limited stock universes, overstating effectiveness due to survivorship and data-snooping biases. We critically assess their generalizability and robustness by proposing FINSABER, a backtesting framework ... Systematic backtests over two decades and 100+ symbols reveal that previously reported LLM advantages deteriorate significantly under broader cross-section and over a longer-term evaluation. Our market regime analysis further demonstrates that LLM strategies are overly conservative in bull markets, underperforming passive benchmarks, and overly aggressive in bear markets, incurring heavy losses."

The paper re-evaluates published LLM agents (FinMem, FinAgent) over 2004–2024. Reported figures (as relayed by my research pass, quoted from the full text): FinMem's MSFT Sharpe fell from a reported 1.440 to −1.247 and NFLX from 2.017 to −0.478; "neither LLM agent generates statistically significant alpha, with all measured p-values exceeding 0.34."

**This is the strongest single citation for "AI-generated strategies can fail out-of-sample."** Caveats: it tests two agents from the 2023–24 generation, on a framework built by its own authors.

### 4.2 The paper that applies Deflated Sharpe + PBO to LLM-discovered strategies

**Gençay, E. "What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery."** **[PREPRINT]** — single author, arXiv only, **not peer reviewed.**

- Verified: <https://arxiv.org/abs/2608.27734> — HTTP 200 (27 Aug 2026). Abstract and full text read.

This is the most directly on-point paper for your question. Its thesis:

> "many candidate strategies are generated, the best is reported, and neither look-ahead bias nor the intensity of the search behind the reported result is corrected for."

Key reported results:

- **A deliberately leaky oracle survives the standard corrections.** A planted look-ahead strategy posting a Sharpe ratio of 35 **passes Deflated Sharpe and PBO testing completely** — the author's conclusion being that "leakage-safety and search-deflation are therefore complementary guardrails rather than substitutes." This is a genuinely important methodological point: **DSR and PBO do not protect you against look-ahead bias.**
- Across a 453-stock point-in-time US equity universe and a 39-ETF multi-asset universe with realistic costs: "honest evaluation certifies passive benchmarks (out-of-sample confidence intervals excluding zero), **rejects every LLM-discovered strategy** (across two frontier models, search budgets up to one hundred candidates, and five repeated runs)."
- The best discovery with one frontier model posted a design Sharpe of 1.69 (better in-sample than buy-and-hold) but "the deflation threshold reaches 1.21 and the DSR stops at 0.86, short of the 0.95 level" — and then collapsed to an evaluation Sharpe of 0.18 while buy-and-hold returned +40.8%.
- A random-weights null returned **+23%** over the nine-year evaluation window.

**⚠️ Weight this appropriately: it is ONE unreviewed preprint using the author's own harness.** It is the only paper I found that does the full DSR/PBO/trial-ledger treatment on LLM-discovered strategies. Do not present "the literature shows DSR rejects LLM strategies" — the literature here is one paper. What makes it credible is that its passive benchmarks *are* certified, i.e. the harness is not rigged to fail everything.

### 4.3 The look-ahead / contamination evidence — this part IS well established

Multiple independent groups, independent methods, convergent results:

**Glasserman, P., & Lin, C. "Assessing Look-Ahead Bias in Stock Return Predictions Generated by GPT Sentiment Analysis," *The Journal of Financial Data Science* 6(1), 2023.** **[PEER-REVIEWED]**
- Preprint verified: <https://arxiv.org/abs/2309.17322> — HTTP 200. Abstract read.
- The paper states the core problem: "backtesting such strategies poses a challenge because LLMs are trained on many years of data, and backtesting produces biased results if the training and backtesting periods overlap."
- **But note the finding is subtler than the folklore.** In-sample, *anonymized* headlines (company identifiers stripped) **outperformed** originals — meaning the "distraction effect" of general company knowledge mattered more than direct look-ahead. Anyone citing this paper as simple proof that "LLMs leak the future and inflate backtests" is misreading it.

**Li, X., Zeng, Y., Xing, X., Xu, J., & Xu, X. "Profit Mirage: Revisiting Information Leakage in LLM-based Financial Agents."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2510.07920> — HTTP 200 (9 Oct 2025). Abstract read.
- Abstract, verbatim: "most systems exhibit a 'profit mirage': dazzling back-tested returns evaporate once the model's knowledge window ends, because of the inherent information leakage in LLMs."
- Re-evaluates five published LLM trading agents with deliberately **matched market returns** across two periods so that market direction cannot explain the difference. Reported: Sharpe decay of 51.5%–62.2%, total-return decay of 50.2%–71.9%. Also reports 85–93% accuracy on historical price/event recall questions — direct evidence of memorisation.

**Gao, Z., Jiang, W., & Yan, Y. "Detecting Lookahead Bias in LLM Forecasts."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2512.23847> — HTTP 200 (29 Dec 2025).
- Introduces "Lookahead Propensity" (LAP), a reusable diagnostic. Reported: LAP "is materially positive throughout the in-sample period and **collapses essentially to zero right after the training-data cutoff**" — the clean pre/post discontinuity you would want from a contamination test.

**Kong, Y., et al. (incl. Lopez-Lira, Zohren). "Evaluating LLMs in Finance Requires Explicit Bias Consideration."** **[PREPRINT]** — position paper, strong author list.
- Verified: <https://arxiv.org/abs/2602.14233> — HTTP 200 (15 Feb 2026). Abstract read.
- Verbatim: "We identify five recurring biases in financial LLM applications. They include look-ahead bias, survivorship bias, narrative bias, objective bias, and cost bias. These biases break financial tasks in distinct ways and they often compound to create an illusion of validity. **We reviewed 164 papers from 2023 to 2025 and found that no single bias is discussed in more than 28 percent of studies.**"

**Benhenda, M. "Look-Ahead-Bench: a Standardized Benchmark of Look-ahead Bias in Point-in-Time LLMs for Finance."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2601.13770> — HTTP 200 (20 Jan 2026). Abstract read.
- Reports "significant lookahead bias in standard LLMs" (Llama 3.1, DeepSeek 3.2) versus a family of "Point-in-Time" models.
- **⚠️ Flagged: the comparison group is a commercial product family ("Pitinf" from PiT-Inference), and the paper's conclusion favours that product.** This is the benchmark most practitioner blogs cite. Do not treat it as neutral evidence.

**Yao, J., & Zheng, Z. "Beyond Agent Architecture: Execution Assumptions and Reproducibility in LLM-Based Trading Systems."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2606.08285> — HTTP 200 (6 Jun 2026).
- Independent reproducibility audit of 30 trade-relevant studies, coded on point-in-time controls, split transparency, held-out evaluation, cost/turnover, and execution semantics. Conclusion: "architecture reporting is generally clearer than the evaluation assumptions needed to judge whether a trading result is economically interpretable or reproducible."

**Zhang, W., et al. "AlphaForgeBench: Benchmarking End-to-End Trading Strategy Design with Large Language Models."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2602.18481> — HTTP 200. Abstract read.
- Documents a different failure mode — behavioural instability: LLMs "exhibit extreme run-to-run variance, generate inconsistent action sequences even under deterministic decoding, and frequently produce irrational action flipping across adjacent time steps." The authors attribute this to the "stateless autoregressive nature of LLMs."

**Shi, J., & Hollifield, B. "Predictive Power of LLMs in Financial Markets."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2411.16569> — HTTP 200 (25 Nov 2024).
- An early blunt verdict: "the GPT model has too much look-ahead bias and that traditional models still triumph."

**The positive counterexample, with its controls documented:**
**Tang, Z., et al. "AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay," KDD '25.** **[PEER-REVIEWED]**
- Preprint verified: <https://arxiv.org/abs/2502.16789> — HTTP 200.
- Uses three structural anti-overfitting regularizers (AST-based originality enforcement vs. an existing alpha library, hypothesis–factor alignment scoring, AST complexity control), with a clean split (train 2015-01→2019-12, validate 2020, test 2021-01→2025-01). Reported ~11.0% (IR 1.5) and 8.74% (IR 1.05) annual excess return after costs.
- **Caveats: it does not deflate for the number of factors its search evaluated, and its GPT-3.5-turbo backbone's knowledge cutoff overlaps its test window** — i.e. it is exposed to exactly the contamination problem in §4.3.

### 4.4 My honest assessment of the LLM evidence

- **Well established:** LLMs leak future information into financial backtests. Multiple independent methods (memorisation probes, a formal pre/post-cutoff statistical test, counterfactual perturbation, matched-return period comparison, and a peer-reviewed study of the mechanism) converge. **Treat this as settled.**
- **Moderately established:** LLM-generated *trading strategies* fail out-of-sample. There is one strong peer-reviewed result (FINSABER) plus one strong preprint (Gençay), plus an audit literature showing the field's evaluation practice is poor.
- **Genuinely thin:** the specific claim "LLM-discovered strategies fail Deflated Sharpe / PBO correction" rests on **exactly one preprint**.
- **Not found at all:** any rigorous, quantitative critique from a well-known practitioner specifically about AI-generated strategy backtests. That layer is self-published blogs and vendor content, some of it plausibly AI-written and recycling the preprints. If someone cites a figure like "90% of AI-generated strategies fail," I found no verified source for it.

---

## 5. Many strategies on a few highly-correlated crypto pairs — the diversification illusion

### 5.0 Summary of verified correlation evidence

| Measure | Value | Source | Type |
|---|---|---|---|
| Mean pairwise correlation, 14 coins, daily, Aug–Dec 2024 | **54.17%** (isotropic fit ρ = 47.25%) | Giller 2024 | [PREPRINT] |
| Floor on all pairwise correlations, 8 majors, hourly | **all pairs > 0.53** | Katsiampa, Corbet & Lucey 2019 | **[PEER-REVIEWED]** |
| Avg. correlation matrix entry, 52 coins, calm regimes | **0.38 – 0.46** | James & Menzies 2021 | [PREPRINT] |
| Avg. correlation matrix entry, 52 coins, COVID peak (Mar–May 2020) | **0.784** | James & Menzies 2021 | [PREPRINT] |
| Share of variance in leading factor, 1 coin → 10 sectors × 4 coins | **0.759 → 0.552** | James & Menzies 2023 | [PREPRINT] |
| Effective independent bets in a 14-coin equal-weighted portfolio | **N\* = 1.96** | Giller 2024 | [PREPRINT] |
| Official-sector statement on diversification | "limited portfolio diversification benefits" | ECB FSR May 2025 | **[OFFICIAL INSTITUTIONAL]** |

### 5.1 The number that matters most

**Giller, G. L. "Correlation without Factors in Retail Cryptocurrency Markets."** **[PREPRINT]** — arXiv, single author, not peer reviewed.
Verified: <https://arxiv.org/abs/2412.04263> — HTTP 200 (5 Dec 2024). PDF downloaded and full text read.

He studies **14 cryptocurrencies tradable at Robinhood**, daily returns, 31 Jul 2024 – 2 Dec 2024, and computes a model-free statistic: the number of **"effective" degrees of freedom** N\*(N) — how many genuinely independent bets an N-asset portfolio actually contains.

**Verified findings from the full text:**

- **Mean pairwise correlation = 54.17%** across all 91 pairs. "There are only three pairs of cryptocurrencies with correlations below 20% and four above 80%."
- Fitting an isotropic correlation model gives **ρ = 47.25%**.
- **The headline result: for the full 14-coin equal-weighted portfolio, N\*(14) = 1.96.**

**Read that again: a 14-coin portfolio behaves like about TWO independent bets.** Diversification across a broad crypto universe is largely an illusion — you own roughly one bet on "crypto goes up" plus a small residual.

Note the discrepancy to be careful about: the abstract says average pairwise correlation is "of order 60%", the histogram mean is 54.17%, and the isotropic fit is 47.25%. I quote all three rather than picking one.

- **My inference (not sourced):** running 20 strategies over BTC/ETH/SOL/XRP does not give you 20 independent bets, and probably does not give you 4 either. If those 4 coins behave like ~1.5–2 effective bets (Giller's 14-coin result, applied conservatively to a 4-coin subset), then 20 strategies over them is closer to **2–4 real bets**, and *strategy* correlation sits on top of that. This compounds directly with §2: your effective trial count is lower than your nominal one (bad for MinBTL), and your effective diversification is far lower than your nominal one (bad for expected Sharpe).

### 5.2 Official-sector statement — the ECB

**European Central Bank, *Financial Stability Review*, May 2025, Special Feature A: "Just another crypto boom? Mind the blind spots."** **[OFFICIAL INSTITUTIONAL]**
Verified: <https://www.ecb.europa.eu/press/financial-stability-publications/fsr/special/html/ecb.fsrart202505_01~62255f2625.en.html> — HTTP 200. Passage extracted and read verbatim:

> "What matters for portfolio diversification is the correlation of returns, and in this respect they appear to be closely correlated with the returns of risky assets. Indeed, Bitcoin prices have historically co-moved closely with the market values of (leveraged) investments in technology stocks. At the same time, Bitcoin returns have shown almost no historical correlation with those of gold (Chart A.2, panel a). **This means Bitcoin has shown limited portfolio diversification benefits for equity portfolios.**"

Same section, verbatim:

> "In 2024 Bitcoin prices were twice as volatile as gold prices and nearly three times as volatile as the S&P 500."

**This is the strongest institutional citation available**, and it is recent. Note the scope: it is about Bitcoin vs *equity portfolios*, not about BTC vs ETH. It supports "crypto is a risky-asset beta, not a diversifier."

### 5.3 Peer-reviewed crypto correlation evidence

**Katsiampa, P., Corbet, S., & Lucey, B. (2019). "High frequency volatility co-movements in cryptocurrency markets," *Journal of International Financial Markets, Institutions and Money*.** **[PEER-REVIEWED]**
- DOI verified: <https://doi.org/10.1016/j.intfin.2019.05.003> — HTTP 200.
- Open-access accepted manuscript verified: <https://doras.dcu.ie/25045/1/High_frequency_volatility_co_movements_in_cryptocurrency_markets%5B1%5D.pdf> — HTTP 200, 2,718,443 bytes, downloaded and text-extracted.
- Universe: eight coins — Bitcoin, Ethereum, Litecoin, Dash, Ethereum Classic, Monero, Neo, OmiseGO — intraday (hourly) data.
- Verbatim from the results section discussing their Table 3: *"Table 3 reports the correlation matrix between the different pairs of cryptocurrency price returns. We notice that all the correlations are positive… It can also be noticed that **all the correlations are above 0.53** suggesting a rather strong positive linear relationship."* I confirmed the underlying table values include 0.533959, 0.536131, 0.532199 — consistent with a floor just above 0.53.
- Stress finding, verbatim: *"at the start of Q1 2018, the correlation between Bitcoin and all investigated cryptocurrencies sharply increases to levels that remain elevated and far more stable throughout 2018."*
- **This is the one genuinely peer-reviewed intra-crypto correlation source in this report, and it includes both BTC and ETH in its panel — so "BTC and ETH are correlated above 0.53" is a supportable statement from this source. It is NOT a BTC–ETH point estimate; see §5.7.**

**James, N., & Menzies, M. "Collective correlations, dynamics, and behavioural inconsistencies of the cryptocurrency market over time," *Nonlinear Dynamics* 107, 4001–4017 (2022).** **[PEER-REVIEWED]** — journal version; I read the preprint.
- DOI verified: <https://doi.org/10.1007/s11071-021-07166-9> — HTTP 200.
- Preprint verified: <https://arxiv.org/abs/2107.13926> — HTTP 200; arXiv lists the journal ref and DOI, confirming publication.
- Studies the 52 largest cryptocurrencies, Jan 2019 – Jun 2021. I downloaded the PDF and read Table 1. **Regime means of correlation-matrix entries, verified verbatim from the table:**

| Regime | Mean correlation | SD |
|---|---|---|
| Pre-COVID (01-01-2019 → 28-02-2020) | **0.456** | 0.164 |
| **Peak COVID (01-03-2020 → 30-05-2020)** | **0.784** | 0.166 |
| Post-COVID | 0.421 | 0.182 |
| Bull | 0.383 | 0.135 |
| Bear | 0.421 | 0.182 |

- Verbatim commentary: *"mean value of 0.78 - highlighting the spike in correlations during the COVID-19 crisis."* And: *"This reflects the highly correlated behaviours of cryptocurrencies and indiscriminate selling during the COVID-19 pandemic."*
- **This is the cleanest "correlation rises in stress" quantification I verified: average pairwise correlation roughly doubles, from ~0.42–0.46 in normal regimes to 0.78 at the peak of the March 2020 crash.** Note the caveat their own table shows: the *"Bear"* window sits at 0.421 — so the elevation is specific to acute crisis, not to all down markets.

**Kwapień, J., Wątorek, M., & Drożdż, S. "Cryptocurrency Market Consolidation in 2020–2021."** **[PREPRINT]** — published version is *Entropy* 23(12), 1674 (2021), DOI 10.3390/e23121674 (the MDPI DOI resolves but mdpi.com returns HTTP 403 to automated fetch; I verified content via the arXiv PDF).
- Preprint verified: <https://arxiv.org/abs/2112.06552> — HTTP 200.
- Verbatim: *"The cryptocurrencies become more strongly cross-correlated among themselves than they used to be before. The average cross-correlations increase with time on a specific time scale..."* — i.e. intra-crypto correlation has been **trending upward** over time, which is the opposite of what a diversification-seeking retail bot wants to hear.

**Wątorek, M., Kwapień, J., & Drożdż, S. "Cryptocurrencies Are Becoming Part of the World Global Financial Market," *Entropy* 25(2), 377 (2023).** **[PEER-REVIEWED]**
- Preprint verified: <https://arxiv.org/abs/2303.00495> — HTTP 200; arXiv lists journal ref *Entropy* 25(2) 377 and DOI 10.3390/e25020377. (The MDPI DOI page returns 403 to automated fetch; use the arXiv URL.)
- High-frequency (10-second) data, Jan 2020 – Oct 2022. Abstract verbatim: "There is a strong indication that the dynamics of the bitcoin and ethereum price changes since the March 2020 Covid-19 panic is no longer independent. Instead, it is related to the dynamics of the traditional financial markets, which is especially evident now in 2022, when the bitcoin and ethereum coupling to the US tech stocks is observed during the market bear phase. ... Our results indicate that the cryptocurrencies cannot be considered as a safe haven for the financial investments."
- **Caveat: this is about crypto-vs-traditional-markets correlation, not crypto-vs-crypto.** It supports "BTC and ETH move together and with tech stocks," which is relevant but not the same claim as Giller's.

**Grobys, K., Ahmed, S., & Sapkota, N. "Technical trading rules in the cryptocurrency market," *Finance Research Letters* (2019).** **[PEER-REVIEWED]**
- DOI verified: <https://doi.org/10.1016/j.frl.2019.101396> — HTTP 200.
- Abstract verbatim: "This paper studies simple moving average trading strategies employing daily price data on the eleven most-traded cryptocurrencies in the 2016–2018 period. Our results indicate a variable moving average strategy is successful when using the 20 days moving average trading strategy. Specifically, **excluding Bitcoin** the technical trading rule generates an excess return of 8.76% p.a. after controlling for the average market return."
- Note the "excluding Bitcoin" qualifier — the result is fragile and the paper is a positive claim, not a warning. I include it for completeness and because it shows the crypto technical-rule literature exists but is thin and period-specific.

**Gort, B. J. D., et al. "Deep Reinforcement Learning for Cryptocurrency Trading: Practical Approach to Address Backtest Overfitting."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2209.05559> — via OpenAlex metadata and arXiv listing (2022).
- Relevant because it is crypto-specific and explicitly about overfitting: it formulates overfitting detection as a hypothesis test and rejects overfitted DRL agents. Reported that "the less overfitted deep reinforcement learning agents have a higher return than that of more overfitted agents" on 10 cryptocurrencies over a period including two crashes. Small sample (testing period 05/2022–06/2022) — treat as suggestive.

### 5.4 How much of crypto's variance is one factor?

**James, N., & Menzies, M. (2023). "Collective dynamics, diversification and optimal portfolio construction for cryptocurrencies."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2304.08902> — HTTP 200. PDF downloaded; I read the table values directly.
- They compute the **normalized leading eigenvalue** of the rolling correlation matrix (normalized by asset count, so it reads directly as the share of variance in the dominant mode), 90-day rolling windows.
- **Verified values from their Table 2** (median normalized first eigenvalue, by portfolio composition):

| Composition (sectors × coins) | Normalized leading eigenvalue |
|---|---|
| 1 × 1 | **0.759** |
| 2 × 1 | **0.774** |
| 1 × 2 | 0.668 |
| 1 × 3 | 0.645 |
| 10 × 4 | **0.552** |

- **Reading: a single common factor carries roughly 55–77% of cross-sectional crypto return variance**, and even a 40-coin portfolio spread over 10 sectors leaves the dominant factor at ~55%.
- Their own conclusion, verbatim: *"We see incrementally greater benefit in diversifying across sectors rather than within them, and we see significant reduction in marginal diversification benefit once a portfolio reaches a critical mass of securities… This leads to the existence of a 'best value' cryptocurrency portfolio."*
- **⚠️ Framework tension worth knowing:** Giller (2024) explicitly *rejects* the linear factor model in favour of an isotropic correlation model — *"the data collected supports description of the cross-section of returns by a simple isotropic correlation model distinct from a decomposition into a linear factor model with additive noise with high confidence."* So "one factor explains 55–77%" and "all pairs correlate at ~54%" are **competing descriptions**, not two measurements of the same thing. Both point to the same practical conclusion (little real diversification), but do not present them as if they were consistent estimates of one quantity.

### 5.5 The strategy-level version of the illusion — a cross-domain analogue

**Khandani, A. E., & Lo, A. W. (2008). "What Happened To The Quants In August 2007?: Evidence from Factors and Transactions Data." NBER Working Paper No. 14465.** **[ACADEMIC WORKING PAPER — NBER explicitly states it has "not been peer-reviewed"]**
- Verified: <https://www.nber.org/papers/w14465> — HTTP 200. PDF verified: <https://www.nber.org/system/files/working_papers/w14465/w14465.pdf> — HTTP 200, 727,901 bytes, downloaded and read. A journal version exists in *Journal of Financial Markets* (2010); I did not read it.
- Verbatim, on how badly separately-built strategies can move together:

> "The volatility and drawdowns would have been substantially higher for leveraged portfolios—for example, **a portfolio with 8:1 leverage and constructed based on the Price Momentum factor would have lost about 31% of its value over the two-day period from August 8th to the 9th!** And as argued by Khandani and Lo (2007), **the use of leverage ratios ranging from 4:1 to 10:1 was quite common among quantitative equity market-neutral strategies**"

> "During the week of August 6, 2007, a number of quantitative long/short equity hedge funds experienced unprecedented losses."

- **Why it matters:** this is the canonical demonstration that *N* separately-designed strategies trading *different* signals can behave as **one bet** when a shared factor is hit. Dozens of market-neutral funds, built independently, lost together in two days.
- **⚠️ Label it honestly: this is US equity statistical arbitrage in 2007, not crypto.** It is an analogue, not crypto evidence. But the mechanism — a shared common factor underneath nominally distinct strategies — is exactly the mechanism that would bite a crypto bot running many strategies over BTC/ETH/SOL/XRP.

### 5.6 Where a "genuinely diversified" book sits, for comparison

Carver's PCA analysis of his cross-asset futures universe gives the contrast case:

Source: "PCA analysis of Futures returns for fun and profit, part #1" (1 Jul 2025), <https://qoppac.blogspot.com/2025/07/pca-analysis-of-futures-returns-for-fun.html> **[PRACTITIONER]**

> "We can see that the first PCA for the last 12 months at least explains 18% of the variance, the second 12.5% and so on. In contrast if we did this for US equities we'd find the first PCA explained 50%, and for US bonds it would be 70%. There is a lot more going on here."

**My inference (not a sourced claim):** at 55–77% in the leading factor (James & Menzies 2023), crypto sits at or beyond the "US bonds: 70%" end of that scale and nowhere near a cross-asset futures book at 18%. Giller's N\*(14) = 1.96 is the direct measurement of the same phenomenon.

### 5.7 ⚠️ The honest gap: no verified BTC–ETH pairwise coefficient

**I could not verify a single citable source that prints a specific BTC–ETH correlation coefficient for recent years.** The commonly assumed "0.7–0.9 daily" range is *consistent* with everything I verified — Giller's mean of 54% with four pairs above 80%, Katsiampa's floor of 0.53 across a panel containing both BTC and ETH, James & Menzies' 0.78 crisis-regime mean — but **no source I could reach states that pair**.

- Wu (2025), <https://arxiv.org/abs/2501.09911> — HTTP 200, **[PREPRINT]** — reports correlations "peaking at 0.87 in 2024", but this is **BTC vs Nasdaq 100, not BTC vs ETH**. Its internal year labels are also inconsistent (elsewhere it says 0.89 in 2022 and ~0.76 in 2023–24), so I would not lean on it.
- The two most likely homes for a real BTC–ETH figure were both HTTP 403-blocked from this environment: *Financial Innovation* (2020), <https://jfin-swufe.springeropen.com/counter/pdf/10.1186/s40854-020-00213-1>, and *Data Science and Management* (2021), <https://www.sciencedirect.com/science/article/pii/S2666764921000461/pdf>.

**Recommendation: either (a) cite the panel-level averages in §5.0, which are sourced, or (b) compute the BTC–ETH pair correlation yourself from exchange data and label it explicitly as your own calculation.** Do not attribute a BTC–ETH coefficient to any of the sources above.

### 5.8 On "effective number of bets" as a technique

The general concept — that a portfolio's true diversification is measured by the effective number of independent bets rather than the nominal asset count — is standard in quantitative portfolio construction. Giller's N\*(N) is a clean, model-free, distribution-free implementation and is the one I verified. The Choueifaty–Coignard diversification ratio is another; a preprint using it notes that **under equicorrelated assets, "maximum diversification" is mathematically equivalent to risk parity** — i.e. when everything is equally correlated, the diversification machinery adds no independent information:

**Cesarone, F., Giacometti, R., Martino, M. L., & Tardella, F. (2023). "A return-diversification approach to portfolio selection."** **[PREPRINT]**
- Verified: <https://arxiv.org/abs/2312.09707> — HTTP 200.
- Verbatim: *"we focus on maximizing a diversification measure recently proposed by Choueifaty and Coignard... We first show that the maximum diversification approach is actually equivalent to the Risk Parity approach using volatility under the assumption of equicorrelated assets."*
- I did **not** verify citable URLs for the original Choueifaty & Coignard papers, so I do not cite them.

---

## 6. Answers to the two headline questions

### (1) How many trading strategies should a small retail bot run?

**The honest answer: no source establishes a number, and the question is probably malformed.**

- **Sourced:** López de Prado's optimal-stopping rule says the right count is ~37% of your *theoretically justifiable* configurations, plus a stopping rule — a fraction, not a fixed number **[PEER-REVIEWED]**.
- **Sourced:** Carver runs ~11 rule families / ~40 variations across 146+ instruments, but explicitly says the framework and instrument diversification matter "much, much, much more," that extra rules are "your last resort," and that they deliver "rapidly diminishing returns" — and in one direct test, adding rules made measured performance slightly *worse* **[PRACTITIONER]**.
- **Sourced:** Chan says trade a *range* of parameters around the optimum for diversification, and that parameter optimization "often adds no value" **[PRACTITIONER]**.
- **Sourced:** QuantStart says minimise the number of parameters **[PRACTITIONER-BLOG]**.
- **Not sourced:** every specific count you will see recommended ("run 3–5", "run 10–20") is opinion. I found no study supporting any of them. **Say this plainly if asked.**
- **My reasoning (not sourced):** for a small retail account, the binding constraints are (a) the number of *independent* trials you can afford to run without inflating your false-discovery rate, and (b) your capital, which forces binary position sizing. Both argue for **few** strategies — on the order of 2–5 genuinely distinct rules — combined with as many *instruments* as your capital can support, and with the trial count honestly recorded. The AMS paper's "7 configurations on 2 years of data" is a reasonable mental anchor for a small bot.

### (2) How real is the overfitting risk?

**Very real, quantified, and the single biggest threat to a crypto bot.**

- **Sourced:** with N=46 independent trials the DSR can still clear 95%; at N=88 the same backtest does not **[PEER-REVIEWED]**.
- **Sourced:** on 5 years of data, more than **45** independent configurations means you are "almost guaranteed" to produce an in-sample SR of 1 with an expected out-of-sample SR of **zero**; on 2 years, the limit is **7** **[AMS NOTICES]**.
- **Sourced:** 100% of in-sample Sharpes positive, ~78% of out-of-sample Sharpes negative in a worked PBO example; and "the higher the SR IS, the lower the SR OOS" **[PREPRINT/working paper]**.
- **Sourced:** a new factor needs **t > 3.0**, not 2.0 **[PEER-REVIEWED]**.
- **Sourced:** 2,127 FX technical rules tested; profitability weakens materially in the more recent subsample **[PEER-REVIEWED]**.
- **My calculation (not sourced):** with 100 trials and a trial-Sharpe dispersion of 0.5, expect an SR of ~1.27 from pure chance.
- **The LLM-specific addition:** if your strategies are LLM-generated, add **look-ahead/contamination risk on top of** overfitting — and note that DSR and PBO **do not protect you from it** (Gençay's leaky oracle with SR 35 passes both).
- **The crypto-specific addition:** your diversification is far weaker than your strategy count suggests. Average pairwise crypto correlation is ~0.54 (Giller) with a floor above 0.53 (Katsiampa), a single factor carries 55–77% of variance (James & Menzies 2023), a 14-coin portfolio behaves like ~2 independent bets (Giller), and correlations roughly double in an acute crash (0.456 → 0.784). Correlation rising in a crisis is precisely when you need diversification most.

---

## 6b. Suggested citation shortlist

If you want the minimum defensible set:

**On overfitting / trial count:**
1. Bailey & López de Prado (2014), DSR — <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf> **[PEER-REVIEWED]**
2. Bailey, Borwein, López de Prado & Zhu (2014), Pseudo-Mathematics, *Notices of the AMS* 61(5) — <https://www.ams.org/notices/201405/rnoti-p458.pdf> **[AMS NOTICES]** ← the 45-trials/5-years and 7-trials/2-years numbers
3. Bailey, Borwein, López de Prado & Zhu (2015), PBO/CSCV — <https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf> **[WORKING PAPER]**
4. Harvey, Liu & Zhu (2016), RFS — <https://faculty.fuqua.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.pdf> **[PEER-REVIEWED]** ← the t > 3.0 hurdle

**On strategy count:**
5. Carver, "Some more trading rules" — <https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html> **[PRACTITIONER]**
6. Carver, "Diversification and small account size" — <https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html> **[PRACTITIONER]** ← the SR-vs-instrument-count table
7. Carver, "The three kinds of (over) fitting" — <https://qoppac.blogspot.com/2015/11/the-three-kinds-of-overfitting.html> **[PRACTITIONER]**
8. Chan & Ng, "Optimizing Trading Strategies Without Overfitting" — <https://epchan.com/img/links/Optimizing-Trading-Strategies-Without-Overfitting.pdf> **[PRACTITIONER]**

**On LLM/AI strategies:**
9. Li, Kim, Cucuringu & Ma, FINSABER, KDD '26 — <https://arxiv.org/abs/2505.07078> **[PEER-REVIEWED]**
10. Gençay (2026) — <https://arxiv.org/abs/2608.27734> **[PREPRINT]** ← DSR/PBO applied to LLM strategies
11. Kong et al. (2026) — <https://arxiv.org/abs/2602.14233> **[PREPRINT]**
12. Glasserman & Lin, *JFDS* 6(1) 2023 — <https://arxiv.org/abs/2309.17322> **[PEER-REVIEWED]**

**On crypto correlation:**
13. ECB, *Financial Stability Review*, May 2025, Special Feature A — <https://www.ecb.europa.eu/press/financial-stability-publications/fsr/special/html/ecb.fsrart202505_01~62255f2625.en.html> **[OFFICIAL INSTITUTIONAL]**
14. Katsiampa, Corbet & Lucey (2019), *JIFMIM* — <https://doras.dcu.ie/25045/1/High_frequency_volatility_co_movements_in_cryptocurrency_markets%5B1%5D.pdf> **[PEER-REVIEWED]**
15. Giller (2024) — <https://arxiv.org/abs/2412.04263> **[PREPRINT]** ← the N\* = 1.96 result
16. James & Menzies (2021/2022), *Nonlinear Dynamics* — <https://arxiv.org/abs/2107.13926> **[PEER-REVIEWED]** ← 0.456 → 0.784
17. James & Menzies (2023) — <https://arxiv.org/abs/2304.08902> **[PREPRINT]** ← 0.759 → 0.552

---

## 7. Separating the three kinds of content in this report

### (a) Sourced claims — safe to cite with the URL given

Everything in the tables and block quotes in §1, §2.1, §3.2, §3.3, §3.4, §4, §5.1–§5.3.

### (b) General technique descriptions — standard, but not "evidence" for anything

- Deflated Sharpe Ratio / Probabilistic Sharpe Ratio / Minimum Track Record Length.
- CSCV and PBO as model-free, non-parametric backtest-overfitting estimators.
- White's Reality Check bootstrap; Harvey–Liu–Zhu multiple-testing framework; BHY/Bonferroni/Holm thresholds.
- Combinatorial purged cross-validation (CPCV) and purging/embargoing.
- The √N risk-reduction rule for uncorrelated assets, and the effective-number-of-bets concept.
- The fundamental law of active management (IR grows with √breadth). I did **not** verify a citable URL for Grinold's original paper, so I describe the idea without citing it.

### (c) My own reasoning — clearly not sourced

- The §2.2 tables (computed from the published formulas; validated against the AMS paper's own Figure 2 values).
- The reading that crypto's short history makes MinBTL constraints unusually binding.
- The inference that 20 strategies over 4 highly-correlated coins is closer to 2–4 real bets.
- The recommendation of 2–5 genuinely distinct rules for a small retail account.
- The judgement that the "how many strategies" question is malformed and mostly answered by opinion.

---

## 8. URLs I could NOT verify — do not cite these

**Blocked to automated fetch (403/302), so I verified metadata only via OpenAlex/Crossref/arXiv and did not read the page:**
- `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551` (DSR)
- `https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253` (PBO)
- `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659` (Pseudo-Mathematics)
- `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104816` (10 Reasons)
- `https://doi.org/10.1111/0022-1082.00163` (Sullivan/Timmermann/White — paywalled)
- `https://doi.org/10.1111/1468-0262.00152` (White 2000 — paywalled)
- `https://doi.org/10.1145/3770854.3785702` (FINSABER at ACM DL)
- `https://doi.org/10.3390/e25020377` (Entropy — MDPI bot-block; use the arXiv URL instead)
- `https://escholarship.org/uc/item/4w1110bb` (PBO at eScholarship — bot challenge; use the WMU or Bailey URL instead)
- `https://www.imf.org/en/Blogs/Articles/2022/01/11/crypto-prices-move-more-in-sync-with-stocks-posing-new-risks` (IMF — "Access Denied" for the entire `imf.org` host; I could **not** verify this page or any IMF GFSR chapter, so I make **no IMF claim**)
- `https://www.mdpi.com/1099-4300/23/12/1674` and `https://doi.org/10.3390/e23121674` (MDPI bot-block; Kwapień et al. verified via its arXiv preprint instead)
- `https://jfin-swufe.springeropen.com/counter/pdf/10.1186/s40854-020-00213-1` (*Financial Innovation* 2020 — 403; a likely home for a real BTC–ETH coefficient)
- `https://www.sciencedirect.com/science/article/pii/S2666764921000461/pdf` (*Data Science and Management* 2021 — 403; the other likely home for a BTC–ETH coefficient)
- `https://www.tandfonline.com/doi/full/10.1080/1351847X.2022.2033806` (Taylor & Francis — 403)
- `https://www.bankofengland.co.uk/-/media/boe/files/financial-stability-report/2022/december-2022.pdf` (404 — wrong path; I did not locate the correct BoE FSR PDF, so **no BoE claim** is made)
- `https://www.ecb.europa.eu/pub/financial-stability/fsr/special/html/ecb.fsrart202211_02~b47e1a8c9f.en.html` (resolves 200 but serves the generic special-features index, **not** a specific article — do not cite as an article)
- BIS: I could **not** retrieve any BIS publication stating an intra-crypto correlation coefficient. The one BIS document verified — Aramonte, Huang & Schrimpf, "DeFi risks and the decentralisation illusion," *BIS Quarterly Review*, Dec 2021, <https://www.bis.org/publ/qtrpdf/r_qt2112b.htm> (HTTP 200) — is about **DeFi decentralisation, not correlation**. **Do not cite BIS for a correlation number.**
- Federal Reserve: the November 2024 *Financial Stability Report*, <https://www.federalreserve.gov/publications/files/financial-stability-report-20241122.pdf> (HTTP 200), was checked and contains **no** crypto return-correlation claim. It is not cited for one.

**Specific figures I saw repeated but could NOT verify, and therefore did NOT use:**
- The "**7,846 trading rules**" figure commonly attributed to Sullivan/Timmermann/White — full text is paywalled and the abstract only says they expanded Brock/Lakonishok/LeBaron's universe of **26** rules.
- Sullivan/Timmermann/White's headline *conclusion* (that the best rules' profits vanish after data-snooping adjustment) — widely repeated, but I could not read the full text to confirm it.
- Any "X% of AI-generated strategies fail" statistic.
- **A BTC–ETH pairwise correlation coefficient for recent years** — see §5.7. The 0.7–0.9 range is plausible and consistent with everything verified, but no reachable source prints that specific pair. Do not cite one.
- Meucci's "Managing Diversification" URL; Choueifaty & Coignard's original papers.
- Grinold's original "Fundamental Law of Active Management" URL.

**Source-type notes to keep straight:**
- *Notices of the AMS* is an expository society magazine. I label it **[AMS NOTICES]**, not **[PEER-REVIEWED]**, even though the authors thank referees.
- The PBO paper is a **working paper**; I could not verify a refereed journal venue for it, so I do not assert one.
- Giller (2024), Gençay (2026), James & Menzies (2023) and Cesarone et al. (2023) are **preprints**, not peer reviewed.
- Khandani & Lo (2008) is an **NBER working paper**; the NBER states on its face that it has "not been peer-reviewed."
- James & Menzies (2021) has a *Nonlinear Dynamics* journal version (verified via the arXiv journal-ref/DOI); I read the preprint. Kwapień et al. (2021) has an *Entropy* journal version; I read the preprint.
- Katsiampa, Corbet & Lucey (2019) is the one **genuinely peer-reviewed intra-crypto correlation** source here.
- Benhenda's Look-Ahead-Bench benchmarks a commercial product favourably — flagged in §4.3.
- The look-ahead-bias evidence rests on **preprints**; the FINSABER result is the peer-reviewed anchor.
- I did **not** read *Advances in Financial Machine Learning*; no claim in this report rests on it.
