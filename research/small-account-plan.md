# Plan: maximum-expected-value Kraken CAD bot at $1,000–$2,000

Produced by a research subagent on 2026-09-18, archived verbatim in substance.
**This is a plan, not a result.** It has not been implemented or tested.

> **Critique appended at the end by the archiving agent.** Three claims in this
> plan are marked as not accepted as written. Read §C before acting on §1–§6.

---

## 1. The quantified finding the plan rests on

New computation, not present in the two prior reports:

| Lever | Annual value on $1,500 | Basis |
|---|---|---|
| **Tax characterization** (capital gains 50% vs business 100% inclusion) | **$74 (4.94% of account)** | [REASONING] from [VERIFIED-URL] CRA 50% inclusion + ~29.65% marginal |
| **Fee drag** at current turnover | **$40 (2.70%)** | [VERIFIED-URL] Kraken Tier 1 0.40/0.80 |
| **Superficial-loss denials** (~3 stop-outs/yr) | **$16** | [REASONING] from [VERIFIED-URL] 30-day rule |

**Tax characterization is worth 1.83× the entire fee drag.**

The keystone claim: **a minimum dwell time of ≥30 days plus a 30-day cooldown
after any loss exit fixes fees, taxes, superficial losses, AND statistical power
simultaneously.** See §C.2 — the fourth of those does not follow.

Second shaping finding: the 895-strategy audit's bulletproof edge (p = 8.4e-15)
still lost to buy-and-hold by 239pp → **the bot's job is capturing beta with
lower drawdown, not alpha.**

## 2. Architecture: core–satellite + regime state machine

- **CORE (~50–60%)**: BTC + ETH, buy-only, DCA on schedule, **never sold by the
  bot**. Captures beta.
- **SATELLITE (~40–50%)**: the bot. Regime-gated trend following; participates
  in uptrends, stands aside in downtrends.

**New integration trap (in neither prior report):** the ACB pool is **per-asset
across the whole account**, so core BTC and bot BTC are **one pool**. If the core
DCA buys within 30 days of a bot loss exit, **that loss is denied.** DCA schedule
and bot exits must be coordinated.

## 3. Phases

**Phase 0 — Guardrails (~1wk).**
1. `tools/benchmark/` — buy-and-hold harness on identical windows across
   multiple start dates. *The #1 gap; nothing is interpretable without it.*
2. `tools/evidence/trial_ledger.json` — hard stop at the published
   **7-configuration** budget.
3. `tools/evidence/dashboard.py` — power gauge (SQN / t / p / CI / distance
   from significance).
4. **Back up the trade SQLite DB — it *is* the CRA record.**
5. Pre-register the kill criterion **before** results exist.

**Phase 1 — Regime architecture (~1–2wk).** Regime switching = **a state machine
inside ONE strategy, not strategy swapping.** Verified reasons: Freqtrade has no
built-in regime switching; maintainers refused (RCE risk); community
regime-switch repos have 0–4 stars; `ai_orchestrator/core/strategy_switch.py`
documents that mid-position swaps apply new exit logic to old positions; and
multiple strategies blow the trial budget.

States: **RISK-ON** (BTC/CAD > 200d MA **and** ≥2/4 pairs above own MA) /
**NEUTRAL** / **RISK-OFF** (no new entries, hold CAD).
Controls: hysteresis ±2%; **min dwell 30 days** (~6 round trips/yr, the
Novy-Marx breakeven); **30-day post-loss cooldown**; vol targeting (crypto ran
43–84% annualised); **correlation-aware sizing** — 0.775 correlation ≈ 1.3
effective bets, so inverse-vol/risk-parity rather than equal weight.

Strategy set deliberately small: keep the pre-specified Turtle Donchian 20/10;
at most one 12-month TSMOM variant if budget allows. **Rejected:** mean
reversion (~60× too small), intraday, leverage.

Add **buy-only DCA with regime multiplier** — described as the most robust
available "alpha": no dispositions (no superficial loss, no tax event),
fee-cheap, mechanically buys low, and it is the core's accumulation mechanism.

**Phase 2 — Canadian tax helper (~2wk).** `tools/tax/`, self-hosted and
deterministic. Rotki supports ACB but defaults to **German rules + FIFO, and
FIFO is wrong for Canada** — purpose-built avoids that error class.

Engines: ingest (Freqtrade SQLite + REST + Kraken ledger CSV + **manual core/DCA
entries**); CAD valuation via Kraken CAD OHLC; **pooled average-cost ACB**;
**superficial-loss detector** (61-day test, deny and capitalise into the
substituted property's ACB, flag all occurrences **including core/bot
cross-contamination**); **characterization analyzer** scoring CRA's listed
factors and outputting **both** outcomes with the dollar spread.

Outputs: `capital_gains_ledger.csv` (date **and time** per CRA),
`schedule3_summary.csv`, `t2125_business_summary.csv`, `tax_summary.md` (both
scenarios + difference), `cra_records_package/` (6-yr retention),
`t1135_check.txt`.

**Honesty caveat carried by the plan:** Wealthsimple ingests CRA auto-fill +
T5008/T3/T5, but **T5008 does not cover crypto**, and whether Wealthsimple
accepts a capital-gains CSV import is **unverified**. If no import exists, the
deliverable is a field-by-field entry guide plus the ledger as CRA backup.

**Phase 3 — Cost/ops (days).** Fill-quality monitor (maker fill rate + adverse
selection — **the largest unquantified assumption; backtests assume zero
slippage**); e-Transfer only (debit = $56.50 on $1,500 ≈ 4 round trips); never
trade for a tier (4.5× self-defeating); **no stablecoins**; keep post-only
(~2.4%/yr ≈ a quarter of reported CAGR); verify effective minimum stakes
(maintainer reports *"as high as 60$"*; failure mode = **silently skipped
trades**).

**Phase 4 — Validation ladder.** backtest → dry-run → live-small → scale, with
numeric exit criteria set in advance. **Won't scale on a backtest.**

**Phase 5 — Two high-value research items (~1wk).**
1. **Staking yield on core** — ~3–4% APY with no trading skill; taxable as
   income at FMV in Canada; needs Kraken-Canada availability/rates/lock-up
   verification.
2. **Asset location: crypto ETF in a TFSA = entirely tax-free gains**, versus
   bot gains which can never be sheltered (Freqtrade cannot run in a TFSA).
   Needs ETF eligibility/MER (0.4–1.0% eats much of it)/tracking verification.
   CRA can deem *active* TFSA trading a business — passive ETF holding is fine,
   another reason the bot stays outside.

**Phase 6 — Annual review.** One question: **did the bot beat holding the same
coins?** Plus tax-loss harvesting candidates that do not trigger superficial
loss, no-trade-band rebalance, kill-criterion check.

## 4. Out of scope

No hyperopt. No >7 trials. No mean reversion. No leverage/futures. No market
orders except emergency stops. No trading for tiers. **No new strategy when
performance dips** (the persistence trap).

## 5. Must verify before building

1. Wealthsimple Tax crypto/capital-gains import options.
2. Kraken Canada staking (availability / rates / lock-ups).
3. Crypto ETF TFSA/RRSP eligibility + MERs.
4. Whether Freqtrade `CooldownPeriod` can be **loss-triggered and per-pair**
   (central to the 30-day rule) or needs a custom protection.
5. Real maker fill rates on the four CAD pairs.

## 6. The plan's own bottom line

> Won't promise more than buy-and-hold — five independent datasets say that
> promise is usually false. Can deliver: own the beta that drives returns, cut
> the drawdown that hurts, ~⅓ less fees, ~half the tax bill via correct
> characterization, avoid the superficial-loss trap, and never fool the
> operator. Absolute dollars stay small (~$12/mo at reported CAGR), so the real
> return is a well-instrumented system and an unbroken tax record, positioned to
> be worth more on a larger account.

---

# C. Critique by the archiving agent

The plan is the most useful artifact produced in this research effort, and its
core–satellite idea is the right shape. Three claims are not accepted as
written.

## C.1 The $74 tax "lever" is not a lever the bot can pull

The plan presents tax characterization as the **largest single lever**, worth
1.83× the fee drag. But characterization is not chosen — it is **determined by
CRA on the facts**, and the plan's own research (`canadian-crypto-tax-usdt-report.md`)
found CRA lists **frequency, time spent, knowledge and intent** among the
factors, and that an automated bot plausibly leans toward **business income**.

So the $74 is not a saving to be captured; it is **the size of the downside if
characterization goes against you.** The plan's own analyzer is honest — it
outputs both outcomes and refuses to characterize the taxpayer — but the summary
table converts a **risk** into a **lever**, which overstates the case. Treat
$74 as *"the most this could cost if it goes the wrong way"*, not as available
upside.

## C.2 Minimum dwell does not improve statistical power

The keystone claim is that a ≥30-day dwell plus a 30-day cooldown fixes "fees,
taxes, superficial losses, **AND statistical power** simultaneously."

The first three follow. **The fourth does not.** Longer dwell means *fewer*
trades, and §4 of the README establishes that this strategy already has too few
samples (14 trades; needs ~200–1,000). A dwell floor **caps** the trade count; it
cannot raise it.

It is defensible as a *constraint* — it keeps you inside the fee and tax
envelope so that the trades you do take are affordable — but that is not the
same as improving power. **Three of four, not four.**

## C.3 Phase 5 item 2 may dominate the entire plan

If a **crypto ETF held in a TFSA is entirely tax-free**, then for the stated goal
— *"help someone make money on crypto"* — the comparison is not bot-vs-buy-and-hold
in a taxable account. It is:

| | bot (taxable) | ETF in TFSA |
|---|---|---|
| tax on gains | taxable (50% or 100% inclusion) | **zero** |
| skill required | yes, unproven | none |
| fee drag | ~2.7%/yr | MER only |
| drawdown | lower (the bot's one real edge) | full |

The bot's **only** surviving advantage is drawdown reduction — and it pays for
that with tax, fees, and unproven skill. That trade-off deserves to be stated at
the **top** of the plan, not as Phase 5 item 2. It may be the whole answer.

## C.4 What is right, and should be built regardless

- **The buy-and-hold benchmark harness (Phase 0.1).** Nothing else is
  interpretable without it. Highest-value item in the plan.
- **The trial ledger with a hard stop at 7 configurations (Phase 0.2).** The
  budget is the binding statistical constraint and nothing currently enforces it.
- **Backing up the trade SQLite DB as the CRA record (Phase 0.4).** It is the
  legal record; losing it is unrecoverable.
- **Core–satellite (Phase 2 architecture).** An honest admission that beta does
  the work, consistent with all five datasets.
- **The core/bot ACB cross-contamination trap.** Genuinely subtle, in neither
  prior report, and it silently denies losses.
- **Superficial-loss detection and ACB (not FIFO).** Correct, and the FIFO
  default is a compliance trap.
- **Refusing to characterize the taxpayer.** Right call.
