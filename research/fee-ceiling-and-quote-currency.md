# The fee ceiling, and whether a different quote currency escapes it

Written 2026-09-18. This supersedes the "97% per year" figure quoted in
`README.md` §3, which was wrong. Read the correction in §1 before repeating any
fee number from any file in this directory.

**Research notes, not evidence of profitability.** No strategy claim in this file
was backtested by its author. Every claim carries a label: `[VERIFIED-URL]` was
fetched in this session, `[MEASURED]` was computed from live API data in this
session, `[REASONING]` is inference, `[CLAIM]` is asserted but unverified.

---

## 1. The fee-drag formula, and the correction it forces

With equal-weighted positions across `k` pairs, a round trip is two fills of
`A/k` each, so the annual cost as a **fraction of the account** is:

```
annual fee %  =  round trips per year  ×  (2/k)  ×  maker_rate
```

**The account size cancels out entirely.** [REASONING — algebra, verified by
recomputing the tables below at three account sizes]

This is the most consequential result in this file, and it is a reframing:

> **Fee drag is a function of turnover and rate only. It does not depend on how
> much money you have.**

A $1,000 account and a $1,000,000 account trading monthly at Tier 1 both pay
**3.20%/yr**. So the question *"is there a strategy for a $1–2K account?"* has no
distinct answer: the arithmetic is identical at every size. The binding
constraint is **turnover**, not capital.

At `k = 3` and Tier 1 (maker 0.40%):

| frequency | 30-day volume (USD) | tier reached | maker rate | annual fee | **% of account/yr** |
|---|---|---|---|---|---|
| 1 / month | $476–953 | T1 | 0.40% | — | **3.20%** |
| 1 / week | $2,064–4,128 | T1–T2 | 0.30–0.40% | — | **10.40–13.87%** |
| 1 / day | $14,488–28,977 | T3–T4 | 0.20–0.22% | — | **48.67–53.53%** |

[REASONING from verified fee schedule; volume computed at the live `ZUSDZCAD`
mid of 1.3996]

### Correction to the previously published figure

`README.md` §3 states one trade per day would cost *"roughly 97% of the wallet
per year"*. **That figure held the fee tier fixed at Tier 1.** Daily trading on a
$1,500 account reaches **Tier 3** (0.22% maker), which almost halves the cost.

**Corrected: ~53.5%/yr at one trade per day, not 97%.** The feedback loop is
real and does help — it just does not help nearly enough. Daily trading remains
catastrophic, but the number in `README.md` is wrong and should be read as this
one.

### Cross-check against the shipped bot

14 round trips in 17 months = **0.82 round trips/month** — *below* the 1/month
row. At a $1,500 account: `14 × $1,000 × 0.40% = $56 CAD over 17 months`, i.e.
**$39.53 CAD/yr = 2.64%/yr of the account**. [REASONING]

Independently computed from the position-size direction: `14 trades × 2 ×
0.40% × $333 = $37.30`, i.e. **2.63%/yr**. Two routes, 2.64 vs 2.63 — agreement
to 0.01pp. [MEASURED]

---

## 2. The tier ladder is real but strictly dominated

Full ladder, fetched from Kraken's own pages. Since **9 July 2026** the tier is
the **best of** spot 30-day volume **or Assets on Platform (AoP)**.
[VERIFIED-URL: <https://support.kraken.com/articles/cross-platform-fee-tier-changes>]

| Tier | Spot 30-day vol (USD) OR | AoP (USD) | Maker | Taker |
|---|---|---|---|---|
| 1 | $0+ | **N/A** | 0.40% | 0.80% |
| 2 | $2.5K+ | **N/A** | 0.30% | 0.60% |
| 3 | $10K+ | $20k | 0.22% | 0.38% |
| 4 | $25K+ | $50k | 0.20% | 0.35% |
| 5 | $50K+ | $100k | 0.15% | 0.30% |
| 6 | $100K+ | $200k | 0.12% | 0.25% |
| 7–12 | $250K+ → $10M+ | $400k → $10M | 0.10% → **0.0%** | 0.22% → 0.10% |
| Pro 1–5 | $50M+ → $500M+ | $20M → $100M | 0.0% | 0.09% → 0.05% |

**Tiers 1 and 2 have no AoP route at all.** The first AoP threshold is $20,000
USD ≈ $27,992 CAD, which is **14–28× this account's size**. Holding assets cannot
buy a tier here. [VERIFIED-URL, confirmed on both the support article and
<https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers>]

### Why climbing the ladder cannot pay

Moving T1 → T2 requires **3.5× the volume** to earn a **25% rate cut**. The
volume multiplier exceeds the rate multiplier at every tier reachable by this
account, so **fee cost is monotonically increasing in trade frequency**:

| frequency | fee per 30 days (A=$1,500) |
|---|---|
| 1 / month | $2.86 USD (≈$4.00 CAD) |
| 1 / week | $9.29 USD (≈$13.00 CAD) |
| 1 / day | $47.81 USD (≈$66.92 CAD) |

Trading daily buys a 45% rate cut and requires **30.4× the volume**. Net fee cost
rises **16.7×**. [REASONING]

### Volume is denominated in USD regardless of the pair's quote

`[VERIFIED-URL]` All 1,450 pairs on Kraken's `AssetPairs` endpoint return
`fee_volume_currency = "ZUSD"` — **including every CAD pair**, whose quote is
`ZCAD`:

```
XXBTZCAD: quote=ZCAD  fee_volume_currency=ZUSD
SOLCAD:   quote=ZCAD  fee_volume_currency=ZUSD
```

So a BTC/CAD bot's tier volume is computed in USD. Only **fills** count — *"Trading
fees are applied only when an order is executed. (Fully or partially)"* — and
cancelled/untouched post-only orders contribute nothing.
[VERIFIED-URL: <https://support.kraken.com/articles/360030303832-overview-of-fees-on-kraken>]

**Not verified:** whether one side or both sides of a fill count toward volume.
Kraken has never stated this in words — an exhaustive search of the fee-schedule
FAQ, all nine Fees-section articles, the Exchange Trading Rules, the **Canadian
Terms of Service**, the blog, the API/OpenAPI specs, and Wayback archives from
2019–2022 found no statement in either direction. The one-side reading is
**inference** from singular phrasing in the conversion-rate article plus a single
`volume` scalar in the API. A both-sides sensitivity run leaves **every
conclusion in this file unchanged** (it would shift 1/day from T3 to T4, and
$1,000/weekly from T1 to T2 — the daily drag stays ~49–54%).

---

## 3. Every fee-reduction avenue is closed

| avenue | finding | verdict |
|---|---|---|
| **Post-only maker orders** | Maker 0.40% vs taker 0.80% at T1 — halves the cost | ✅ **Already in use.** The only material lever available. |
| **Kraken+** (zero fees to $10k/mo) | *"does not include Spot, Futures, **API**, or OTC trades on Kraken Pro"* | ❌ [VERIFIED-URL: <https://www.kraken.com/kraken-plus>] — explicitly excludes bots |
| **Assets on Platform** | First threshold $20,000 USD; **no AoP route into T2** | ❌ 14–28× out of reach |
| **Spot Maker Rebate pairs** | 628 eligible pairs, of which only **`XDC/CAD` and `XDG/CAD`** are CAD-quoted. `XBT/CAD`, `ETH/CAD`, `SOL/CAD`, `XRP/CAD` are **not** eligible | ❌ worth $2.40/yr, and the bot's pairs don't qualify |
| **Volume tiers** | see §2 | ❌ value-destroying |
| **Token-hold discount** | Kraken has no BNB-style scheme; staking counts toward AoP only | ❌ no discount below $20k AoP |
| **KFEE credits** | discretionary, not purchasable | ❌ not a lever |

[VERIFIED-URL: <https://www.kraken.com/features/fee-schedule>,
<https://support.kraken.com/articles/pairs-eligible-for-maker-fee-rebates>]

**One documentation inconsistency:** Kraken's VIP support page publishes a
conflicting table (`< $10K: 0.25% / 0.4%`) that contradicts the fee-schedule
page. Treat the fee schedule as authoritative; the VIP page table appears stale.

**Conclusion: the account is already at the floor.** The remaining lever is
**reducing turnover**, and at 0.82 round trips/month the bot is already near it.

---

## 4. Quote currency: what a Canadian account can actually use

### USDT is prohibited in Canada — the original premise is dead

`[VERIFIED-URL]` Kraken's regulatory page (updated 16 Sep 2026), Canada →
*Cryptocurrency restrictions*: *"Cannot deposit, hold or trade ACA, AIN, …,
**USDT**, …"*

Tether was suspended for Canadian clients on **30 Nov 2023**, with residual
balances **force-converted to USD** on 5 Dec 2023. So "USDT pairs have more
liquidity" is not actionable on this venue, at any price.

**This is a trap worth recording:** the public `AssetPairs` endpoint *does* list
a `USDT/CAD` market. Asking *"does Kraken list it?"* gives the wrong answer.
The question is *"can a Canadian client trade it?"*

The same list also prohibits **DAI, PYUSD, RLUSD, USDD, USDE, USDG, USDS, WBTC,
WETH, XAUT, PAXG, XMR** and ~150 other assets. **USDC is not on the list**, and
USD is a fiat currency, so the *"Cryptocurrency restrictions"* heading does not
reach it.

### Available options, ranked by liquidity

`[MEASURED]` — live `Ticker` trade counts, 24h:

| asset | CAD | USDC | **USD** | USDC/CAD | **USD/CAD** |
|---|---|---|---|---|---|
| BTC | 2,742 | 11,345 | **128,593** | 4.1× | **46.9×** |
| ETH | 2,380 | 8,521 | **68,840** | 3.6× | **28.9×** |
| SOL | 1,399 | 7,828 | **60,639** | 5.6× | **43.3×** |
| XRP | 1,051 | 4,960 | **46,336** | 4.7× | **44.1×** |

Pairs available per quote: **USD 668, USDC 47, CAD 11.** [MEASURED]

**Ranking: USD ≫ USDC > CAD.** USD has 29–47× the trade activity and 60× the
pair count of CAD.

### ⚠️ The spread measurements in this session are unreliable

Top-of-book spreads were sampled twice, **20 seconds apart**:

| pair | snapshot 1 | snapshot 2 | change |
|---|---|---|---|
| BTC/CAD | 0.0029% | 0.0108% | **3.7×** |
| SOL/CAD | 0.0381% | 0.0127% | **3×** |
| SOL/USDC | 0.0178% | 0.0534% | **3×** |
| BTC/USD | 0.0001% | 0.0001% | **0** |
| ETH/USD | 0.0004% | 0.0004% | **0** |

`[MEASURED]` **Thin books swing 3–4× within twenty seconds.** Any single-snapshot
spread comparison between CAD, USDC and USD is therefore **not evidence**, and
earlier drafts of this analysis drew conclusions from exactly such snapshots
before this test was run. Do not repeat them.

The USD spreads are the exception — they did not move at all, which is itself
the depth signal. If spread data is needed, it must be **time-averaged over many
samples**, not sampled once.

**Trade counts are the robust signal** and are what the ranking above rests on.

### Cost of moving the account off CAD

`[MEASURED]` + `[VERIFIED-URL]` Kraken's Stablecoin/Pegged/FX schedule is
0.20%/0.20%, but *"If the stablecoin is the quote currency only (BTC/DAI), the
fee schedule in the 'Spot Crypto' tab applies."* Therefore:

- **BTC/USDC maker = 0.40% — identical to BTC/CAD.** No fee benefit.
- **USDC/CAD = 0.20% each way** → CAD→USDC round trip ≈ **0.43%** on $1,000
  ($2.14 one way). Only needed at funding and at withdrawal, not per trade.

A one-time 0.43% is **not** a blocker: against a bot whose entire fee drag is
2.64%/yr, it is roughly two months of fees, paid once.

---

## 5. What the quote choice costs in tax

`[VERIFIED-URL]` CRA names crypto-to-crypto explicitly: *"Trade or exchange it
for government-issued currency **or another type of crypto-asset**."*

| per completed trade | CAD quote | **USDC quote** | **USD quote** |
|---|---|---|---|
| buy base | 0 dispositions | 1 (dispose USDC) | 0 (USD is fiat) |
| sell base | 1 | 1 | 1 |
| **total** | **1** | **2** | **1** |

**This is the argument that separates USD from USDC.** Because USD is
government-issued currency, a BTC/USD trade is one disposition — exactly like
BTC/CAD. A BTC/USDC trade is two, because the USDC spent is itself disposed.

So **USD doubles nothing**, while USDC doubles the event count. At ~10 trades/yr
that is ~10 events vs ~20, each requiring its own CAD valuation at the
transaction date.

Two further rules that constrain any tooling:

- **CRA requires average-cost pooling, not FIFO.** *"Dispositions of identical
  properties do not affect the ACB."* A FIFO-default tool produces a **wrong**
  number — a compliance risk, not a saving.
- **T5008 does not cover crypto** (closed ITR 230(1) "security" list), and
  **T1135 is not triggered** at this size (threshold is $100,000 *cost amount*).

Self-hosted software (e.g. Rotki: AGPLv3, supports ACB) reduces the reporting
**burden**, never the **liability** — the liability is fixed by the ITA, CRA's
interpretation, the facts, the ACB and the inclusion rate. Rotki's own docs say
it *"is not tax advice"*. Its defaults are German rules + FIFO + *"tax-free
after 1 year"*, **all three wrong for Canada**. Whether CAD is selectable as its
profit currency is unverified.

**Not tax advice. A qualified Canadian accountant should be consulted.**

---

## 6. Bottom line

1. **Fee drag = turnover × rate. Account size cancels.** There is no
   small-account-specific strategy question — the constraint is identical at
   every size. The shipped bot is already at 0.82 round trips/month, near the
   floor, at 2.64%/yr.
2. **The "97%/yr" figure in `README.md` is wrong** — corrected to ~53.5%/yr
   (Tier 3 is reached, halving the rate). Still catastrophic; the conclusion
   survives, the number does not.
3. **No fee-reduction avenue is open.** Kraken+ excludes API trading; AoP needs
   $20k; the maker-rebate pairs don't include ours. Post-only maker — already
   used — is the only lever.
4. **USDT is not available in Canada.** The real choice is CAD vs **USDC** vs
   **USD**, and USD is the strongest on liquidity (29–47× CAD) *and* on tax
   (no extra dispositions), with USDC second.
5. **Switching is not free and not obviously profitable.** It buys more
   opportunities and better maker fill probability — but the maker fee is
   identical, more pairs means more trades means more fees, and **the strategy's
   edge on those pairs is untested**, which spends trial budget (§2 of
   `README.md`).

## What could not be verified

- Whether Kraken counts **one side or both sides** of a fill toward tier volume
  (exhaustive negative; conclusions hold either way).
- Whether **CAD is selectable as Rotki's profit currency**.
- **Whether USD funding/conversion is available to Canadian clients** — the
  force-conversion of USDT balances to USD strongly implies it, but no Kraken
  page states it affirmatively for CAD→USD. **Verify before acting on §4.**
- Whether the average-cost rule applies to crypto *in terms* (CRA's published
  examples name shares and mutual funds).
- Any **time-averaged** spread or order-book-depth data for CAD, USDC or USD
  pairs. None exists in this archive; §4's warning stands until it does.
