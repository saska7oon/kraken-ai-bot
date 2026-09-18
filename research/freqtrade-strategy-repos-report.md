# Freqtrade Strategy Repository Inventory (verified via GitHub REST API)

**Verification date:** 2026-09-18 (UTC)
**Method:** `GET /repos/{owner}/{repo}` for metadata; `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1` for file inventories; `raw.githubusercontent.com` for README/LICENSE text. No GitHub token was available, so all calls were unauthenticated (60 req/hr core limit).

**Evidence labels used below:**
- **[API]** = retrieved directly from the GitHub REST API in this session.
- **[RAW]** = retrieved from `raw.githubusercontent.com` in this session.
- **[CLAIM]** = asserted by a README/blog but not independently verified by backtest or code audit.

---

## 1. Summary table

| Repository | URL | Stars | License | Last push | Status |
|---|---|---|---|---|---|
| freqtrade/freqtrade-strategies (official) | https://github.com/freqtrade/freqtrade-strategies | 5,491 | GPL-3.0 | 2026-09-08 | **Maintained**, active |
| iterativv/NostalgiaForInfinity | https://github.com/iterativv/NostalgiaForInfinity | 3,417 | GPL-3.0 | 2026-09-17 | **Maintained**, very active |
| davidzr/freqtrade-strategies | https://github.com/davidzr/freqtrade-strategies | 564 | GPL-3.0 | 2024-02-10 | **ARCHIVED** — dead |
| jonlemofficial/freqtrade-community-strategies | https://github.com/jonlemofficial/freqtrade-community-strategies | 0 | GPL-3.0 | 2024-02-10 (inherited) | **Dead fork**, byte-identical copy |
| TheoBrigitte/freqtrade | https://github.com/TheoBrigitte/freqtrade | 129 | none declared | 2025-04-15 | Maintained-ish (personal collection) |
| stash86/freqtrade-strategies | https://github.com/stash86/freqtrade-strategies | 1 | GPL-3.0 | 2025-04-16 | **Dead fork** of the official repo |
| Rikj000/MoniGoMani | https://github.com/Rikj000/MoniGoMani | 1,025 | GPL-3.0 | 2023-03-11 | **ARCHIVED** — dead |
| paulcpk/freqtrade-strategies-that-work | https://github.com/paulcpk/freqtrade-strategies-that-work | 329 | MIT | 2021-06-14 | **Stale/abandoned** (~5 yrs) |
| jilv220/BB_RPB_TSL | https://github.com/jilv220/BB_RPB_TSL | 214 | GPL-3.0 | 2022-02-21 | **Stale** (~4.5 yrs) |
| brookmiles/freqtrade-stuff | https://github.com/brookmiles/freqtrade-stuff | 212 | none declared | 2021-05-20 | **ARCHIVED** — dead |
| imsatoshi/GeneTrader | https://github.com/imsatoshi/GeneTrader | 201 | MIT | 2026-07-29 | **Maintained**, active |
| Foxel05/freqtrade-stuff | https://github.com/Foxel05/freqtrade-stuff | 127 | none declared | 2021-11-19 | **Stale** |
| keithorange/HUGE_FreqTrade_Strategy_Collection | https://github.com/keithorange/HUGE_FreqTrade_Strategy_Collection | 58 | none declared | 2024-04-09 | Unmaintained dump (no license = legally unusable) |
| mikedigriz/freqtrade-strategy-mikedigriz | https://github.com/mikedigriz/freqtrade-strategy-mikedigriz | 40 | Apache-2.0 | 2024-11-17 | Low activity |
| raphant/freqtrade-strategies | https://github.com/raphant/freqtrade-strategies | 34 | MIT | 2022-06-01 | Stale |
| freqsignals/freqtrade-strategies | https://github.com/freqsignals/freqtrade-strategies | 22 | GPL-3.0 | 2023-02-28 | Stale; signal-provider glue, not real strategies |
| keryc/crypto-bot | https://github.com/keryc/crypto-bot | 99 | GPL-3.0 | 2024-09-20 | **ARCHIVED** |
| Bananajoexxc/RegimeFilterStrategy-Freqtrade | https://github.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade | 3 | MIT (README claim) | 2026-01-20 | New, single strategy |
| OfficialGIGA/freqtrade-ml-strategy | https://github.com/OfficialGIGA/freqtrade-ml-strategy | 1 | MIT (README claim) | 2026-06-11 | New, single strategy |
| darkvolg/trendrider-strategy | https://github.com/darkvolg/trendrider-strategy | 20 | MIT | 2026-04-21 | New, single strategy |

Star counts and `pushed_at` are as returned by the API on 2026-09-18.

---

## 2. freqtrade/freqtrade-strategies — the official repo

- **URL:** https://github.com/freqtrade/freqtrade-strategies
- **Owner:** freqtrade (org) · **Stars:** 5,491 · **Forks:** 1,444 · **License:** GPL-3.0 **[API]**
- **Created:** 2018-01-21 · **Last push:** 2026-09-08T16:42:47Z · **archived: false**, `fork: false`, default branch `main` **[API]**
- **Description:** "Free trading strategies for Freqtrade bot" **[API]**
- **Status: MAINTAINED.** Actively pushed; the canonical, trustworthy starting point.

### 2.1 Complete verified strategy file inventory — 68 strategy `.py` files + 1 hyperopt **[API]**

Repo-wide tree: 86 entries, `truncated: false`. 69 `.py` files total, of which 68 under `user_data/strategies/`.

**`user_data/strategies/` (root) — 27 files:**
```
AlmgrenChrissStrategy.py   Bandtastic.py              BreakEven.py
CustomStoplossWithPSAR.py  Diamond.py                 FixedRiskRewardLoss.py
GodStra.py                 Heracles.py                HourBasedStrategy.py
InformativeSample.py       MultiMa.py                 PatternRecognition.py
PowerTower.py              Strategy001.py             Strategy001_custom_exit.py
Strategy002.py             Strategy003.py             Strategy004.py
Strategy005.py             Supertrend.py              SwingHighToSky.py
TWAPStrategy.py            TrendRiderStrategy.py      UniversalMACD.py
hlhb.py                    mabStra.py                 multi_tf.py
```

**`user_data/strategies/berlinguyinca/` — 30 files:**
```
ADXMomentum.py                  ASDTSRockwellTrading.py
AdxSmas.py                      AverageStrategy.py
AwesomeMacd.py                  BbandRsi.py
BinHV27.py                      BinHV45.py
CCIStrategy.py                  CMCWinner.py
ClucMay72018.py                 CofiBitStrategy.py
CombinedBinHAndCluc.py          DoesNothingStrategy.py
EMASkipPump.py                  Freqtrade_backtest_validation_freqtrade1.py
Low_BB.py                       MACDStrategy.py
MACDStrategy_crossed.py         MultiRSI.py
Quickie.py                      ReinforcedAverageStrategy.py
ReinforcedQuickie.py            ReinforcedSmoothScalp.py
Scalp.py                        Simple.py
SmoothOperator.py               SmoothScalp.py
TDSequentialStrategy.py         TechnicalExampleStrategy.py
```

**`user_data/strategies/futures/` — 7 strategies + 1 Readme:**
```
FAdxSmaStrategy.py   FOttStrategy.py     FReinforcedStrategy.py
FSampleStrategy.py   FSupertrendStrategy.py
TrendFollowingStrategy.py                VolatilitySystem.py
Readme.md            (not a strategy)
```
The `futures/Readme.md` **[RAW]** documents the tested config: Binance **futures**, `trading_mode: futures`, `margin_mode: isolated`, a ~87-pair USDT whitelist, `stake_amount: 100`, `max_open_trades: -1`. It contains **no** market-regime labelling.

**`user_data/strategies/lookahead_bias/` — 4 strategies + 1 readme (deliberately biased):**
```
DevilStra.py   GodStraNew.py   Zeus.py   wtc.py
readme.md      (not a strategy)
```

**`user_data/hyperopts/` — 1 file:** `GodStraHo.py`

### 2.2 README disclaimer — profitability / educational purpose **[RAW]**

Yes. The current `README.md` (102 lines, fetched from `main`) carries an explicit **Disclaimer** section. Verbatim quote:

> ## Disclaimer
>
> These strategies are for educational purposes only. Do not risk money
> which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE
> AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING
> RESULTS.
>
> Always start by testing strategies with a backtesting then run the
> trading bot in Dry-run. Do not engage money before you understand how
> it works and what profit/loss you should expect.
>
> We strongly recommend you to have coding and Python knowledge. Do not
> hesitate to read the source code and understand the mechanism of this
> bot.

And in the "Free trading strategies" section, verbatim:

> Strategies from this repo are free to use, though they are provided as-is and without any warranty.
> They also mostly should serve as a starting point for your own strategies, not as "ready to use" strategies.

> Please keep in mind, results will heavily depend on the pairs, timeframe and timerange used to backtest - so please run your own backtests that mirror your usecase, to evaluate each strategy for yourself.

> The results above should serve as a general outline to demonstrate the number of trades to expect. Actual performance will be different based on various factors.

**Note:** the phrase "The results above…" is a **leftover** — the current README contains **no** results/backtest table. I verified this: the README has no markdown table and no per-strategy performance figures. (The old 2018-era table survives only in the stale `stash86` fork — see §5.)

### 2.3 Does the official repo document deliberate lookahead bias? — **Yes** **[RAW]**

Yes, but **only inside the subfolder readme**, *not* in the top-level README. I grepped the top-level `README.md` for `lookahead`/`look-ahead`/`regime`/`trending`/`ranging`/`volatil` — **no matches**. The top-level README never mentions lookahead bias.

`user_data/strategies/lookahead_bias/readme.md` (43 lines) opens verbatim:

> Warning, Strategies in this folder do have a lookahead bias.
>
> Please see these as practice to see if you can spot the lookahead bias.

It then gives per-file spoilers inside collapsed `<details>` blocks, quoting the offending code. Verified file-by-file:

| File | Documented cause of lookahead bias **[RAW]** |
|---|---|
| `DevilStra.py` | `normalize()` uses `.min()` and `.max()` — uses the full dataframe, not just past data |
| `GodStraNew.py` | `normalize()` uses `.min()` and `.max()` — uses the full dataframe, not just past data |
| `Zeus.py` | uses `.min()`/`.max()` to normalize `trend_ichimoku_base` and `trend_kst_diff` |
| `wtc.py` | `preprocessing.MinMaxScaler()` + `fit_transform(x)` — takes absolute max/min of the series |

So: **4 strategies are explicitly documented as deliberately lookahead-biased**, intended as practice exercises, and the repo provides the solutions. They must not be traded.

### 2.4 Market-regime labelling in the official repo — **partial, and only in one strategy's code**

The README does **not** label strategies by regime. Its only regime-adjacent statement is a general hedge **[RAW]**:

> Some may only work in specific market conditions, while others are more "general purpose" strategies.

I scanned all 68 official strategy `.py` files (fetched via raw) for `regime|trending market|ranging|sideways|market condition|bull market|bear market|volatile market`. **11 files matched**, but 9 are trivial boilerplate comments ("adjust based on market conditions"). The genuinely regime-aware ones:

- **`user_data/strategies/TrendRiderStrategy.py`** — the only official strategy with a real regime classifier **[RAW]**. It defines `_get_market_regime(self, last: dict) -> str` with the docstring `"""Detect market regime from ADX + EMA200 + BB width."""` and returns exactly these five labels:
  - `"Ranging"` (ADX < 20)
  - `"Ranging (High Vol)"` (ADX < 20 and BB width > 1.5× its SMA)
  - `"Trending Bull"` (`is_bull` and close > EMA200)
  - `"Trending Bear"` (otherwise)
  - `"Trending Bear (High Vol)"` (otherwise and high BB width)
  
  The regime is then used to gate entries: `min_conf = 6 if "Bear" in regime else 5`.
- `berlinguyinca/CCIStrategy.py` and `berlinguyinca/ReinforcedQuickie.py` — comment only: *"resampled dataframe to establish if we are in an uptrend, downtrend or sideways trend"* (no explicit regime labels exposed).
- `berlinguyinca/EMASkipPump.py` — docstring: *"basic strategy, which trys to avoid pump and dump market conditions."*
- `berlinguyinca/SmoothOperator.py` — comment: *"This helps with very long, sideways trends, to get out of a market before…"*

**Bottom line for the official repo:** no per-strategy trending/ranging/volatile labels in documentation; exactly **one** strategy (`TrendRiderStrategy.py`) computes explicit trending/ranging/volatility regime states in code.

---

## 3. NostalgiaForInfinity — `netanelben/NostalgiaForInfinity` vs `iterativv/NostalgiaForInfinity`

### 3.1 `netanelben/NostalgiaForInfinity` — **does not exist**

`GET /repos/netanelben/NostalgiaForInfinity` returns **404 Not Found** **[API]**. The user `netanelben` does exist (62 public repos), and I enumerated all 62 via `GET /users/netanelben/repos` **[API]** — **no** repository named `NostalgiaForInfinity` (or anything freqtrade-related) is present. Conclusion: that path is dead; it was deleted or renamed and **no canonical successor exists under that owner**. I could not verify what it once contained, and I am not guessing. Treat any link to `netanelben/NostalgiaForInfinity` as broken.

### 3.2 `iterativv/NostalgiaForInfinity` — the real, maintained one

- **URL:** https://github.com/iterativv/NostalgiaForInfinity
- **Owner:** iterativv · **Stars:** 3,417 · **Forks:** 755 · **License:** GPL-3.0 (confirmed by fetching `LICENSE`: GNU GPL v3, 29 June 2007) **[API][RAW]**
- **Created:** 2021-07-14 · **Last push:** 2026-09-17T10:44:36Z · **archived: false** **[API]**
- **Status: MAINTAINED, very active.** Pushed one day before this audit.
- **Docs site:** https://iterativv.github.io/NostalgiaForInfinity/

**What it actually is:** not a "collection" — it is a **single large multi-mode production trading strategy** (NFI-X lineage) plus configs, docs, tests and tooling. Tree: 341 entries, `truncated: false` **[API]**.

**Verified strategy files [API]:**

Root-level (the current generation):
```
NostalgiaForInfinityX.py    NostalgiaForInfinityX2.py   NostalgiaForInfinityX3.py
NostalgiaForInfinityX4.py   NostalgiaForInfinityX5.py   NostalgiaForInfinityX6.py
NostalgiaForInfinityX7.py   NostalgiaForInfinityX8.py
```

`user_data/strategies/` (deployable copies, 10 files):
```
NostalgiaForInfinityNext.py      NostalgiaForInfinityNextGen.py
NostalgiaForInfinityX.py         NostalgiaForInfinityX2.py
NostalgiaForInfinityX3.py        NostalgiaForInfinityX4.py
NostalgiaForInfinityX5.py        NostalgiaForInfinityX6.py
NostalgiaForInfinityX7.py        NostalgiaForInfinityX8.py
```

`legacy/` (superseded, 2 strategies): `NostalgiaForInfinityNext.py`, `NostalgiaForInfinityNextGen.py` (+ `__init__.py`)

Supporting `.py` **[API]**: `tools/benchmark_merge_informative_pair.py`, `tools/bot_report.py`, `tools/compare_backtest_results.py`, `tools/ho_to_raw_codemod.py`, `tools/ho_to_raw_codemod_nfi4.py`, plus a real test suite (`tests/unit/test_NFIX5.py`, `test_NFIX7_bad_trade_controller.py`, `test_NFIX8_custom_exit.py`, `test_caches.py`, `tests/backtests/test_winrate_and_drawdown*.py`).

Non-strategy assets **[API]**: `configs/` with ~75 JSON files — per-exchange blacklists (binance, bitget, bitmart, bitvavo, bybit, gateio, htx, hyperliquid, kraken, kucoin, mexc, okx), example configs, and static/volume pairlists per exchange+market. Docker Compose, `pyproject.toml`, `pytest.ini`, mkdocs docs.

**Availability / licensing caveat:** the source is GPL-3.0 and freely downloadable. However the README **[RAW]** points to a docs site and describes automatic-update mechanisms (`tools/checkupdates.sh`, an `nfi-updater` Docker sidecar). Historically NFI has had a **sponsor/early-access tier** for the newest versions (this is why forks such as `TheoBrigitte` carry many version-numbered snapshots — see §4). I did **not** verify current sponsor gating in this session, so I state it as unverified rather than as fact. The README itself contains no explicit commercial-restriction notice that I found.

### 3.3 Market-regime labelling in NostalgiaForInfinity — **YES, explicitly documented**

This is the strongest regime documentation of any repo audited. `docs/trading-modes/trading-modes.md` **[RAW]** documents a multi-mode system and explicitly ties modes to market conditions:

| Mode | Regime / condition stated in the doc **[RAW]** |
|---|---|
| **Normal** (tags 1–13) | *"the baseline trend-following strategy… designed for standard market conditions where price movements follow established trends with moderate volatility"*; *"It performs best in trending markets and may experience drawdowns during sideways or choppy market conditions."* |
| **Pump** (tags 21–26) | *"specifically designed for high-volatility momentum trading, targeting rapid price increases often seen during market pumps or strong breakout events"*; *"most effective during periods of high market volatility"* |
| **Quick** (tags 41–53) | *"performs best in markets with consistent volatility and clear short-term trends, but may struggle during periods of low volatility or choppy price action"* |
| **Rebuy** (tags 61–62) | *"most effective in ranging or mildly trending markets where price frequently retraces before continuing in the primary direction"* |
| **Rapid** (tags 101–110) | *"performs best in highly liquid markets with consistent volatility"* |
| **Grind** (tag 120) | *"a mean-reversion strategy specifically designed for ranging markets where prices oscillate between support and resistance levels"* |
| **Scalp** (tags 161–163) | *"most effective in highly liquid markets with tight bid-ask spreads and consistent volatility"* |

The doc also states: *"This modular design enables traders to fine-tune their approach based on market regime, volatility levels, and risk tolerance"* and, under troubleshooting, *"Each mode is optimized for specific market conditions… Regular market regime analysis is recommended to select the most appropriate mode."*

**Caveat on provenance:** this `docs/` tree is in-repo markdown (verified present in the API tree and fetched raw), but its formatting — `<cite>Referenced Files in This Document</cite>` blocks and `**Section sources**` citations — is characteristic of **auto-generated documentation** (DeepWiki-style). I therefore treat it as **in-repo but likely machine-generated documentation**, i.e. stronger evidence than a blog post but not a hand-written maintainer guarantee. The mode tag lists it quotes (`long_normal_mode_tags`, `long_pump_mode_tags`, etc.) are consistent with the strategy's own naming, but I did not diff them against `NostalgiaForInfinityX6.py` line-by-line.

---

## 4. `TheoBrigitte/freqtrade`

- **URL:** https://github.com/TheoBrigitte/freqtrade · **Stars:** 129 · **Forks:** 34
- **License: NONE declared** (`license: null`) **[API]** — legally all-rights-reserved despite being a public scrape of other people's strategies.
- **Created:** 2024-12-03T20:57:01Z · **Last push:** 2025-04-15T20:40:15Z · **archived: false** **[API]**
- **Description:** "Freqtrade strategies, configurations and dry-runs" **[API]**
- **Status:** Personal collection; pushed ~17 months ago at audit time. Not archived, but low/stopped activity. **Not a fork.**

Tree: 2,675 entries, `truncated: false`; **315 `.py` files** (292 under `strategies/`, 23 under `sources/`) **[API]**. Full list saved to `research/gh/theobrigitte_py_files.txt`.

README **[RAW]** is explicit that this is a hoard, not an original project:
> This repository is a collection of strategies, configurations, dry-run and backtest results I collected overtime.
> ## Disclaimer
> I am not a financial advisor and I am not responsible for any financial loss you might incur using this repository.
> `strategies/` - Contains all strategies I found and played with. **Folder names are arbitrary** and each folder might contain additional configurations for the specific strategy(ies)

**Verified directory grouping with real filenames [API]** (292 strategy files):

| Directory | Files (verified filenames) |
|---|---|
| `strategies/AutoArimaTripleV1/` | `AutoArimaTripleV1.py` |
| `strategies/BinHV45/` | `BinHV27.py`, `BinHV27_werkkrew.py`, `BinHV45.py`, `BinHV45HO.py`, `BinHV45_kanaxe.py`, `BinHV45_stash.py`, `BinHV45_werkkrew.py`, `BinMfiBTCv5003.py` + 8 dry-run copies under `dry-run/<date>/…` |
| `strategies/ElliotV5_SMA/` | `ElliotV5_SMA.py` (+1 dry-run copy) |
| `strategies/FVGAdvancedStrategy_V2/` | `FVGAdvancedStrategy_V2.py` |
| `strategies/GeneTrader/` | `GeneStrategy.py`, `GeneStrategy_v2.py`, `GeneTrader_gen10_1734895087_6007.py`, `GeneTrader_gen5_1735014093_4541.py`, `NewStrategy53_22.py`, `newstrategy53.py` (+1 dry-run) |
| `strategies/MACDStrategy/` | `MACDStrategy.py`, `MACDStrategy_crossed.py` |
| `strategies/Zaratustra/` | `ZaratustraDCA2_06.py` |
| `strategies/arima/` | `ARIMA_15.py`, `ARIMA_5.py` |
| `strategies/bb/` | `BB_RPB_TSL_SMA_Tranz_1.py` |
| `strategies/berlinguyinca/` | `1h/` with 29 files (`ADXMomentum.py`, `ASDTSRockwellTrading.py`, `AdxSmas.py`, `AverageStrategy.py`, `AwesomeMacd.py`, `BbandRsi.py`, `BinHV27.py`, `BinHV45.py`, `CCIStrategy.py`, `CMCWinner.py`, `ClucMay72018.py`, `CofiBitStrategy.py`, `CombinedBinHAndCluc.py`, `DoesNothingStrategy.py`, `EMASkipPump.py`, `Freqtrade_backtest_validation_freqtrade1.py`, `Low_BB.py`, `MACDStrategy.py`, `MACDStrategy_crossed.py`, `Quickie.py`, `ReinforcedAverageStrategy.py`, `ReinforcedQuickie.py`, `ReinforcedSmoothScalp.py`, `Scalp.py`, `Simple.py`, `SmoothOperator.py`, `SmoothScalp.py`, `TDSequentialStrategy.py`, `TechnicalExampleStrategy.py`) + `MultiRSI.py` |
| `strategies/bigz/` | `BigZ04_TSL4.py` |
| `strategies/cenderawasih/` | `Cenderawasih_30m.py` |
| `strategies/cenderawasih3/` | `Cenderawasih_3_kucoin.py`, `NotAnotherSMAOffsetStrategyHOv3.py` |
| `strategies/cluc/` | 46 files incl. `BinClucHyperOpt.py`, `BinClucMadDevelop.py`, `BinClucMadSMACore.py`, `BinClucMadSMADevelop.py`, `Cluc4werk.py`, `Cluc5werk.py`, `Cluc6werk.py`, `Cluc7werk.py`, `ClucFiatROI.py`, `ClucFiatSlow.py`, `ClucHAnix.py`, `ClucHAnix2.py`, `ClucHAnix_5m.py`, `ClucHAnix_5m_old.py`, `ClucHAnix_BB_RPB_HO2.py`, `ClucHAnix_BB_RPB_MOD.py`, `ClucHAnix_BB_RPB_MOD2.py`, `ClucHAnix_BB_RPB_MOD2_TB.py`, `ClucHAwerk.py`, `ClucMay72018.py`, `CombinedBinHAndCluc.py`, `CombinedBinHAndCluc2021.py`, `CombinedBinHAndCluc2021Bull.py`, `CombinedBinHAndClucV2.py`…`V8XH.py`, `CombinedBinHClucAndMADV3.py`/`V6.py`/`V9.py`, `TrailingBuyStratCluc.py`, `TrailingBuyStratClucBBRPBMODE.py`, plus files with spaces: `ClucHAnix (3).py`, `ClucHAnix 5m trailbuy2 + BBRSIV5 offsets.py`, `ClucHAnix 5m trailbuy2 + dynamic offset.py`, `ClucHAnix E01VE Offsets.py`, `ClucHAnix_5mTB1 (1).py`, `ClucHAnix_BB_RPB_MOD_E0V1E_DYNAMIC_TB (1).py`, `ClucHAnix_hhll (1).py`, `TrailingBuy_ClucHAnix_5m_E0V1E_by_TraNz (1).py`, `TrailingBuy_ClucHAnix_5m_E0V1E_by_TraNz.py` |
| `strategies/cryptofrog-strategies/` | `CryptoFrog.py`, `CryptoFrog_nateema.py`, `custom_indicators.py` |
| `strategies/danke/` | `Danke.py` |
| `strategies/dwt/` | `DWT.py`, `DWT_Leveraged.py`, `DWT_LongShort.py`, `DWT_short.py`, `custom_indicators.py` |
| `strategies/e0v1e/` | `E0V1E.py`, `E0V1E2.py`, `E0V1E_DCA.py`, `E0V1E_DCA2.py`, `E0V1E_DCA3.py`, `E0V1E_DCA_strs.py`, `E0V1E_ewo.py`, `E0V1E_protections.py`, `E0V1E_strs.py` (+1 dry-run) |
| `strategies/e0v1e_stash/` | `E0V1E.py` |
| `strategies/ei/` | `Auto_EI_t4c0s.py`, `EI4_t4c0s_V2.py`, `EI4_t4c0s_V2_2.py` (+3 dry-run copies) |
| `strategies/eiv4/` | `EI1_t4c0s_V4.py` |
| `strategies/eliot/` | `ElliotV8_original_ichiv2.py`, `ElliotV8_original_ichiv2OH.py` |
| `strategies/falcon/` | `falconTrader.py` |
| `strategies/fastsupertrend/` | `FastSupertrend_optim3.py`, `_optim3_rsi_70.py`, `_optim3_rsi_75.py`, `_optim3_rsi_752.py`, `_optim3_rsi_75fix.py`, `_optim3_rsi_75fix_signal.py`, `_optim3_rsi_75lev.py`, `_optim3_rsi_75sell.py`, `_optim3_rsi_80.py`, `_optim_quick.py`, `_optim_quick2.py`, `_optim_quick3.py`, `_optim_quick4.py`, `_optim_quick5.py`, `_ts_origstop_fix.py` |
| `strategies/freqtrade-strategies/` | **24 files mirrored from the official repo** (no `berlinguyinca/`, no `futures/`, no `lookahead_bias/`): `Bandtastic.py`, `BreakEven.py`, `CustomStoplossWithPSAR.py`, `Diamond.py`, `FixedRiskRewardLoss.py`, `GodStra.py`, `Heracles.py`, `HourBasedStrategy.py`, `InformativeSample.py`, `MultiMa.py`, `PatternRecognition.py`, `PowerTower.py`, `Strategy001.py`, `Strategy001_custom_exit.py`, `Strategy002.py`, `Strategy003.py`, `Strategy004.py`, `Strategy005.py`, `Supertrend.py`, `SwingHighToSky.py`, `UniversalMACD.py`, `hlhb.py`, `mabStra.py`, `multi_tf.py` |
| `strategies/freqtrade-strategies-that-work/` | `DoubleEMACrossoverWithTrend.py`, `EMAPriceCrossoverWithThreshold.py`, `MACDCrossoverWithTrend.py`, `RSIDirectionalWithTrend.py`, `RSIDirectionalWithTrendSlow.py` (mirror of paulcpk repo) |
| `strategies/harmonic-divergence/` | `HarmonicDivergence.py`, `HarmonicDivergence-fix.py` (+1 dry-run) |
| `strategies/insomnia/` | `Insomnia_short.py` |
| `strategies/juicy/` | `JuicyTrend.py` |
| `strategies/lambo/` | `MiniLambo.py` |
| `strategies/momentum/` | `PowerTower.py`, `momentum.py`, `momentum_long.py`, `momentum_rsi.py`, `momentum_wick.py` |
| `strategies/moon/` | `ToTheMoon.py` |
| `strategies/nasos/` | `NASOSv4.py`, `NASOSv5.py`, `NASOSv5_antipump.py`, `NASOSv5_mod1.py`, `NASOSv5_mod2.py`, `NASOSv5_mod3.py` (+3 dry-run) |
| `strategies/nfix/` | **23 NFI snapshots**: `NostalgiaForInfinity772martinsk3.py`, `NostalgiaForInfinityX.py`, `X13107.py`, `X1337.py`, `X2488.py`, `X2616.py`, `X2616_nosell.py`, `X2626.py`, `X2640.py`, `X3121.py`, `X3182.py`, `X3187.py`, `X3199.py`, `X3208.py`, `X3211.py`, `X3221.py`, `X3243.py`, `X3253.py`, `X3259.py`, `X3468.py`, `X4003.py`, `X4113.py`, `X4334.py` |
| `strategies/notankai/` | `NOTankAi_15.py`, `NOTankAi_15_Cleaned.py`, `NOTankAi_15_Cleaned_v2.py` (+3 dry-run) |
| `strategies/profiters/` | `AlligatorStrategy.py`, `BigTrader.py`, `CrossEMAStrategy.py`, `NormalizerStrategyHO2.py`, `SqueezeMomentum.py`, `SupertrendStrategy.py`, `TrixStrategy.py` |
| `strategies/quick_buy/` | `quick_buy_strategy.py` |
| `strategies/quickadapter/` | `QuickAdapterV3.py` |
| `strategies/renko/` | `AdaptiveRenkoStrategy.py`, `pyrenko.py` |
| `strategies/rsiqui/` | `Rsiqui.py`, `RsiquiV2.py`, `RsiquiV5.py`, `RsiquiV5_long_only.py` |
| `strategies/simple/` | `Simple.py` |
| `strategies/slownsteady/` | `slownsteady_v2.py` |
| `strategies/smas/` | `NotAnotherSMAOffSetStrategy_V2.py`, `NotAnotherSMAOffsetStrategyHOv3_b.py`, `NotAnotherSMAOffsetStrategyLite.py`, `NotAnotherSMAOffsetStrategyModHO.py`, `NotAnotherSMAOffsetStrategy_uzi.py`, `NotAnotherSMAOffsetStrategy_uzi3.py`, `SMAOffsetProtectOptV0.py`, `SMAOffsetProtectOptV1.py`, `SMAOffsetProtectOptV1HO1.py`, `SMAOffsetProtectOptV1Mod2_antipump.py`, `SMAOffsetV2.py`, `SMAOffset_Hippocritical_dca.py`, `SMAOffset_Hippocritical_dca_old.py`, `SMAOffset_Hippocritical_dca_protections.py` (+5 dry-run incl. `SMAOffset_Hippocritical_dca_leverage.py`) |
| `strategies/sponsors/` | `BinMfiBTCv5003.py`, `CombinedBinHAndClucHyper.py`, `zorkv7_0_0.py` |
| `strategies/squeezemomentum/` | `SqueezeMomentum.py` |
| `strategies/starrise/` | `StarRise.py`, `StarRise_V2.py`, `StarRise_V3.py` |
| `strategies/tank/` | `Tank1Modulus.py`, `Tank5ModulusDCA.py`, `Tank5ModulusDCAV3.py` |
| `strategies/trendfollowing/` | `TrendFollowingStrategy.py` |
| `strategies/turtle/` | `new_turtle.py`, `new_turtle_roi.py` |
| `strategies/twinturbov8/` | `twinturboV8.py`, `twinturboV8_2.py` |
| `strategies/volatility/` | `VolatilitySystem.py`, `VolatilitySystemV2.py` |
| `strategies/wave/` | `TRIWAVE.py`, `dualwave.py` |
| `strategies/wtx3/` | `scalpv3.py` |
| `strategies/yodo/` | `simple_patterns.py` |

**`sources/` (23 files) [API]** — vendored upstream copies, not deployable strategies:
- `sources/nfix/`: `NostalgiaForInfinityNext.py`, `NostalgiaForInfinityNext772.py`, `NostalgiaForInfinityNextGen.py`, `NostalgiaForInfinityX.py`, `NostalgiaForInfinityX2488.py`, `NostalgiaForInfinityX2616.py`, `NostalgiaForInfinityX2616_stop3.py`, `NostalgiaForInfinityX2616_stop4.py`, `NostalgiaForInfinityX2_stop1.py`, `NostalgiaForInfinityX2_stop2.py`, `NostalgiaForInfinityX2_stop3.py`, `NostalgiaForInfinityX2_stop4.py`, `NostalgiaForInfinityX3.py`, `NostalgiaForInfinityX3_v143.py`
- `sources/sponsors/`: `BadStreak.py`, `BinHV45.py`, `BinMfiBTCv5003.py`, `CombinedBinHAndClucHyper.py`, `Matrix.py`, `Obelisk_Ichimoku_Slow_v1_3.py`, `Solipsis_v5.py`, `resample_and_btc_info.py`, `zorkv7_0_0.py`

**Regime labelling:** **No documented regime labelling.** Two directory names (`strategies/trendfollowing/`, `strategies/volatility/`) and one `sources/sponsors/Solipsis_v5.py` are *suggestive*, but the README explicitly warns "folder names are arbitrary" and contains **no** per-strategy regime documentation. Do not treat those names as verified regime labels.

**Provenance warning:** much of this content is copied from other people's repos (`sources/` are described as "git submodules to other repositories"), yet the repo declares **no license**. Reuse rights are unclear.

---

## 5. `davidzr/freqtrade-strategies` and `jonlemofficial/freqtrade-community-strategies`

### 5.1 The canonical-URL question — resolved

There is **no repository named `freqtrade-community-strategies` other than the fork.** I searched `q=freqtrade-community-strategies in:name fork:true` and got `total_count: 1` **[API]**. (A plain `in:name` search returned 0 because GitHub repo search excludes forks by default.)

The chain, verified by API **[API]**:
- `jonlemofficial/freqtrade-community-strategies` → `fork: true`, `parent: davidzr/freqtrade-strategies`, `source: davidzr/freqtrade-strategies`.
- `davidzr/freqtrade-strategies` → `fork: false`, **`archived: true`**.

**So the original is `davidzr/freqtrade-strategies`, and it is archived. The `jonlemofficial` repo is a downstream fork, not a canonical successor.**

### 5.2 They are byte-identical

I diffed the two recursive trees by blob SHA **[API]**:
```
davidzr paths: 934 | jonlem paths: 934
only in davidzr: []          only in jonlem: []
differing content: 0
```
**All 934 paths present in both, with zero differing blob SHAs.** The `jonlemofficial` fork adds nothing.

### 5.3 Metadata

| | davidzr/freqtrade-strategies | jonlemofficial/freqtrade-community-strategies |
|---|---|---|
| URL | https://github.com/davidzr/freqtrade-strategies | https://github.com/jonlemofficial/freqtrade-community-strategies |
| Stars / forks | 564 / 259 | **0 / 0** |
| License | GPL-3.0 | GPL-3.0 |
| Created | 2023-11-05 | 2025-08-10 |
| Last push | 2024-02-10T20:25:41Z | 2024-02-10T20:25:41Z (inherited; no commits since fork) |
| Archived | **TRUE** | false (but dead) |
| Fork | false | **true** (parent = davidzr) |
| Homepage | — | https://freqst.com |

**Verdict: `davidzr` is ABANDONED (archived, ~2.6 years without a push). `jonlemofficial` is a DEAD, unmodified fork with zero traction.** Both are snapshots of a ~2021–2023-era strategy dump.

### 5.4 Verified contents

**`davidzr` tree:** 934 entries, `truncated: false`; **465 `.py` files**, all under `strategies/`, laid out as **one directory per strategy** (`strategies/<Name>/<Name>.py`), plus `LICENSE` and `README.md`. One non-Python asset: `strategies/MultiMA_TSL/LookaheadStrategy.zip` **[API]**. Full filename list saved to `research/gh/davidzr_py_files.txt` (465 lines).

Representative verified directories and files **[API]** (the dump is a near-superset of the other collections — it contains the `berlinguyinca` corpus, the `Cluc*`/`CombinedBinHAndCluc*` lineage, `BB_RPB_TSL*`, `NASOS*`, `NotAnotherSMAOffsetStrategy*`, `FastSupertrend*`, `NostalgiaForInfinity*` snapshots, `Elliot*`, `BigZ*`, `CryptoFrog*`, `Ichimoku*`, `Obelisk*`, `Schism*`, `SMAOffset*`, `Trix*`, `Strategy00x`, etc.):
```
strategies/ADXMomentum/ADXMomentum.py
strategies/ADX_15M_USDT/ADX_15M_USDT.py
strategies/ASDTSRockwellTrading/ASDTSRockwellTrading.py
strategies/ActionZone/ActionZone.py
strategies/AlligatorStrat/AlligatorStrat.py
strategies/AlwaysBuy/AlwaysBuy.py
strategies/Apollo11/Apollo11.py
strategies/AwesomeMacd/AwesomeMacd.py
strategies/BBRSI/BBRSI.py           strategies/BBRSI21/BBRSI21.py
strategies/BBRSI3366/BBRSI3366.py   strategies/BBRSIOptimStrategy/BBRSIOptimStrategy.py
strategies/BB_RPB_TSL/BB_RPB_TSL.py
strategies/BB_RPB_TSL_RNG/BB_RPB_TSL_RNG.py
strategies/BB_RPB_TSL_RNG_TBS_GOLD/BB_RPB_TSL_RNG_TBS_GOLD.py
strategies/BB_RPB_TSL_SMA_Tranz/BB_RPB_TSL_SMA_Tranz.py
strategies/BinHV27/BinHV27.py       strategies/BinHV45/BinHV45.py
strategies/BigZ04/BigZ04.py         strategies/BigZ07Next/BigZ07Next.py
strategies/BreakEven/BreakEven.py   strategies/ClucHAnix/ClucHAnix.py
strategies/CombinedBinHAndCluc/CombinedBinHAndCluc.py
strategies/CombinedBinHAndClucV8/CombinedBinHAndClucV8.py
strategies/CryptoFrog/CryptoFrog.py strategies/DevilStra/DevilStra.py
strategies/Diamond/Diamond.py       strategies/ElliotV8/ElliotV8.py
strategies/FastSupertrend/FastSupertrend.py
strategies/Freqtrade_backtest_validation_freqtrade1/…
strategies/GodStraNew/GodStraNew.py strategies/Heracles/Heracles.py
strategies/Ichimoku/Ichimoku.py     strategies/MultiMA_TSL/MultiMA_TSL.py
strategies/NASOSv5/NASOSv5.py       strategies/NFI46/NFI46.py
strategies/NostalgiaForInfinityNext/NostalgiaForInfinityNext.py
strategies/NostalgiaForInfinityV7/NostalgiaForInfinityV7.py
strategies/NostalgiaForInfinityX/NostalgiaForInfinityX.py
strategies/NotAnotherSMAOffsetStrategyHOv3/…
strategies/Obelisk_Ichimoku_Slow_v1_3/…
strategies/Strategy001/Strategy001.py … strategies/Strategy005/Strategy005.py
strategies/Supertrend/Supertrend.py strategies/SwingHighToSky/SwingHighToSky.py
strategies/UniversalMACD/UniversalMACD.py
strategies/multi_tf/multi_tf.py     strategies/hlhb/hlhb.py
```
(2 directories hold more than one file: `strategies/MultiMA_TSL/` and the `LookaheadStrategy.zip` asset.)

**README [RAW]:** 17 lines, generic contributor instructions. It contains **no** disclaimer, **no** profitability warning, **no** educational-purposes statement, **no** lookahead-bias note, and **no** strategy table. This is a materially weaker legal/safety posture than the official repo.

**Regime labelling:** **None.** No README documentation, no regime-named directories. Note `strategies/DevilStra/DevilStra.py` appears here — that is one of the official repo's **documented lookahead-bias** strategies, present here with **no warning**.

---

## 6. `stash86/freqtrade-strategies` — a stale fork of the official repo

- **URL:** https://github.com/stash86/freqtrade-strategies · **Stars:** 1 · **Forks:** 0
- **License:** GPL-3.0 · **Default branch:** `master`
- **Created:** 2021-07-02 · **Last push:** 2025-04-16T09:46:16Z · **archived: false** **[API]**
- **`fork: true` — parent and source are both `freqtrade/freqtrade-strategies`** **[API]**
- **Status: DEAD FORK.** Zero traction (1 star, 0 forks), and no commits for ~17 months while upstream pushes monthly.

Tree: 83 entries; **66 `.py` files** vs the official repo's **69** **[API]**. Diff:
```
In official, MISSING from stash86 (3):
  user_data/strategies/AlmgrenChrissStrategy.py
  user_data/strategies/TWAPStrategy.py
  user_data/strategies/TrendRiderStrategy.py
In stash86, not in official: (none)
```
So it is a near-complete **2025-04** snapshot of the official repo. It **does** include `user_data/strategies/futures/` (7 futures strategies + `Readme.md`) and `user_data/strategies/lookahead_bias/` (`DevilStra.py`, `GodStraNew.py`, `Zeus.py`, `wtc.py`, `readme.md`), and the full 30-file `berlinguyinca/` directory **[API]**. It is missing exactly the three newest root strategies — including `TrendRiderStrategy.py`, which is the only official strategy with an explicit market-regime classifier.

**README [RAW]:** a 112-line **older revision** of the official README. It carries the same "educational purposes only" disclaimer and the same "Some only work in specific market conditions…" line, **but it also retains the obsolete 2018 backtest results table** that the official repo has since dropped:
> Value below are result from backtesting from 2018-01-10 to 2018-01-30 and `exit_profit_only` enabled.

with rows for Strategy 001–005 (e.g. Strategy 001: 55 buys, 0.05% avg profit, 0.00012102 total profit; Strategy 005: 180 buys, 1.16% avg, 0.00827589 total). **These figures are 8+ years stale and are not in the current official README** — do not cite them as current.

**Regime labelling:** none beyond the inherited generic sentence.

---

## 7. Other notable collections found via GitHub search

Search queries run **[API]**: `topic:freqtrade-strategies` (32 results), `topic:freqtrade` (157 results), `freqtrade strategy in:name` (69 results), `freqtrade-community-strategies in:name fork:true` (1 result).

### 7.1 Rikj000/MoniGoMani — the biggest framework, now dead
https://github.com/Rikj000/MoniGoMani · **1,025 stars** · GPL-3.0 · last push **2023-03-11** · **`archived: true`** **[API]**
A Freqtrade *framework + strategy* (signal weighting, hyperoptable "Total Overall Signal"), not a collection. Tree: 229 entries, 10 `.py` files **[API]**:
```
user_data/strategies/MasterMoniGoManiHyperStrategy.py
user_data/strategies/MoniGoManiHyperStrategy.py
user_data/hyperopts/UncloggedWinRatioAndProfitRatioLoss.py
user_data/hyperopts/WinRatioAndProfitRatioLoss.py
user_data/mgm_tools/Binance-Retrieve-All-Tradable-StaticPairList.py
user_data/mgm_tools/Total-Overall-Signal-Importance-Calculator.py
Legacy MoniGoMani/user_data/strategies/MoniGoMani.py
Legacy MoniGoMani/user_data/strategies/MoniGoManiHyperOpted.py
Legacy MoniGoMani/user_data/hyperopts/MoniGoManiHyperOpt.py
.github/scripts/disco.py
```
README **[RAW]**: I grepped for `regime|trending|ranging|volatil` — **no matches**. No regime labelling. **Dead** (archived 3.5 years).

### 7.2 paulcpk/freqtrade-strategies-that-work — small, clean, stale
https://github.com/paulcpk/freqtrade-strategies-that-work · **329 stars** · **MIT** · last push **2021-06-14** · not archived **[API]**
Tree: 8 entries; exactly **5 strategies**, flat at repo root **[API]**: `DoubleEMACrossoverWithTrend.py`, `EMAPriceCrossoverWithThreshold.py`, `MACDCrossoverWithTrend.py`, `RSIDirectionalWithTrend.py`, `RSIDirectionalWithTrendSlow.py`.
README **[RAW]** carries an explicit disclaimer: *"WARNING These strategies are highly experimental and for educational purposes only. Use at your own risk."* and a backtest table (1h, 2018-03-01→2020-03-01, 8 pairs) with total-profit figures from 16.16% to 122.50% **[CLAIM]**. Four of the five filenames contain "WithTrend" — trend-oriented by construction, but the README has **no** explicit regime labelling (grep for `regime|trending|ranging|volatil` → no matches). **Stale ~5 years**; freqtrade has changed substantially since (INTERFACE_VERSION 3, config schema).

### 7.3 jilv220/BB_RPB_TSL — historically influential, stale
https://github.com/jilv220/BB_RPB_TSL · **214 stars** · GPL-3.0 · last push **2022-02-21** · not archived **[API]**
Tree: 48 entries, 3 `.py` **[API]**: `BB_RPB_TSL.py`, `BB_RPB_TSL_BI.py`, `NFIX_BB_RPB.py`. The `BB_RPB_TSL` lineage is widely forked/copied into other collections (e.g. `TheoBrigitte/strategies/bb/`, `davidzr`, `keithorange`). **Stale ~4.5 years.**

### 7.4 brookmiles/freqtrade-stuff — archived
https://github.com/brookmiles/freqtrade-stuff · **212 stars** · **no license** · last push **2021-05-20** · **`archived: true`** **[API]**
Tree: 25 entries, 15 `.py` **[API]** — the "Obelisk" family plus examples:
```
strategies/Obelisk_Ichimoku_Slow_v1.py, _v1_1.py, _v1_3.py
strategies/archive/ObeliskIM_v1_1.py, ObeliskRSIHyperOpt.py, ObeliskRSI_v6_1.py,
                   Obelisk_Ichimoku_Slow_v1_2.py, Obelisk_TradePro_Ichi_v1_1.py,
                   Obelisk_TradePro_Ichi_v2.py, Obelisk_TradePro_Ichi_v2_2.py
strategies/examples/EMA_Trailing_Stoploss.py, EMA_Trailing_Stoploss_LessMagic.py,
                    Magic_Trailing_Stoploss.py
strategies/experimental/Obelisk_3EMA_StochRSI_ATR.py, Obelisk_Ichimoku_ZEMA_v1.py
```
**No license → not legally reusable.** Dead.

### 7.5 imsatoshi/GeneTrader — actively maintained tooling, not a strategy collection
https://github.com/imsatoshi/GeneTrader · **201 stars** · **MIT** · last push **2026-07-29** · not archived **[API]**
Tree: 87 entries, 49 `.py` **[API]**. A **genetic-algorithm / Optuna optimizer that generates** Freqtrade strategies, not a curated set. Only strategy-shaped files: `strategies/GeneStrategy.py`, `daily_results/20241223/gen10/GeneTrader_gen10_1734895087_6007.py`. The rest is a real Python package (`genetic_algorithm/{individual,operators,population}.py`, `optimization/{genetic_optimizer,optuna_optimizer}.py`, `strategy/{backtest,evaluation,walk_forward,robustness}.py`, `scripts/`, `tests/`). **Maintained.**

### 7.6 keithorange/HUGE_FreqTrade_Strategy_Collection — a scrape, no license
https://github.com/keithorange/HUGE_FreqTrade_Strategy_Collection · **58 stars** · **no license declared** · last push **2024-04-09** **[API]**
Tree: 481 entries; **478 `.py` files, all flat in the repo root** (plus a stray `.DS_Store`) **[API]**. README **[RAW]** is a **one-line title only** — no disclaimer, no provenance, no license, no attribution. Full list saved to `research/gh/huge_py_files.txt`.

Verified sample of real filenames **[API]**: `ADXMomentum.py`, `BB_RPB_TSL_RNG_TBS_GOLD.py`, `BigZ04_TSL4.py`, `ClucHAnix.py`, `CombinedBinHAndCluc2021Bull.py`, `Combined_NFIv7_SMA.py`, `CryptoFrogNFI.py`, `ElliotV8_original_ichiv2.py`, `FastSupertrend.py`, `GodStraNew.py`, `NASOSv5_mod3.py`, `NostalgiaForInfinityV7.py`, `NostalgiaForInfinityX.py`, `NostalgiaForInfinityNext.py`, `NotAnotherSMAOffsetStrategyHOv3.py`, `SMAOffset_Hippocritical`-style files, `Strategy001.py`…`Strategy005.py`, `Trend_Strength_Directional.py`, `Uptrend.py`, `WaveTrendStra.py`, `MarketChyperHyperStrategy.py`.

Regime-adjacent filenames **[API]**: `CombinedBinHAndCluc2021Bull.py`, `Uptrend.py`, `Trend_Strength_Directional.py`, `DoubleEMACrossoverWithTrend.py`, `MACDCrossoverWithTrend.py`, `RSIDirectionalWithTrend.py`, `RSIDirectionalWithTrendSlow.py`, `SuperTrendPure.py`, `Supertrend.py`, `SupertrendStrategy.py`, `FastSupertrend.py`, `FastSupertrendOpt.py`, `WaveTrendStra.py`. **These are names only — the README documents nothing, so none of these count as documented regime labelling.**

**Important safety note:** this dump includes `LookaheadStrategy.py` **and** `LookaheadStrategy.zip` at repo root, plus `DevilStra.py`, `GodStraNew.py`, `wtc.py` — i.e. lookahead-biased strategies **with no warning of any kind**. There is also a `Fakebuy.py` and an `EXPERIMENTAL_STRATEGY.py`. Combined with **no license**, I recommend against using this repo.

### 7.7 raphant/freqtrade-strategies
https://github.com/raphant/freqtrade-strategies · **34 stars** · **MIT** · last push **2022-06-01** · not archived **[API]**
Tree: 25 entries, 10 `.py` **[API]**: `user_data/strategies/conductor/conductor.py`, `user_data/strategies/custom_indicators.py`, `user_data/strategies/gumbo1.py`, `user_data/strategies/im_test.py`, `user_data/strategies/indicator_mix.py`, `user_data/strategies/indicatormix/entities/{__init__,indicator}.py`, `user_data/strategies/indicatormix/helpers/custom_indicators.py`, `user_data/strategies/indicatormix/indicator_opt.py`, `user_data/strategies/indicatormix/indicators.py`. **Stale.** Note `conductor.py` is a strategy-*selector* pattern.

### 7.8 freqsignals/freqtrade-strategies — not actually strategies
https://github.com/freqsignals/freqtrade-strategies · **22 stars** · GPL-3.0 · last push **2023-02-28** **[API]**
Tree: 12 entries, 7 `.py` **[API]**: `strategies/FreqSignalsAiDataProvider.py`, `FreqSignalsAiWebhookDataProvider.py`, `FreqSignalsDataProvider.py`, `FreqSignalsFollower.py`, `FreqSignalsProvider.py`, `FreqSignalsWebhookDataProvider.py`, `freqsignals.py`. These are **data-provider adapters that consume an external commercial signal feed**, not standalone strategies. **Stale.**

### 7.9 mikedigriz/freqtrade-strategy-mikedigriz
https://github.com/mikedigriz/freqtrade-strategy-mikedigriz · **40 stars** · **Apache-2.0** · last push **2024-11-17** **[API]**
Tree: 15 entries, 6 `.py` **[API]**: `strategies/BuyOrDie.py`, `strategies/CCI_BB.py`, `strategies/EasyInEasyOut.py`, `strategies/FisherHull.py`, `strategies/RSI_BB.py`, `strategies/smart_money_strategy.py`. Low activity.

### 7.10 keryc/crypto-bot — archived NFI wrapper
https://github.com/keryc/crypto-bot · **99 stars** · GPL-3.0 · last push **2024-09-20** · **`archived: true`** **[API]**
Tree: 30 entries, 3 `.py` **[API]**: `user_data/strategies/NostalgiaForInfinityX.py`, `user_data/strategies/SampleStrategy.py`, `user_data/hyperopts/sample_hyperopt_loss.py`. It is a **deployment repo that vendors NFI**, not an original strategy. Dead.

### 7.11 darkvolg/trendrider-strategy
https://github.com/darkvolg/trendrider-strategy · **20 stars** · **MIT** · last push **2026-04-21** **[API]**
Tree (branch `master`): 6 entries, **1** `.py` **[API]**: `TrendRiderStrategy.py`. This is the open-source release of a commercial bot's strategy and is related to the `TrendRiderStrategy.py` that later landed in the official repo.

### 7.12 Bananajoexxc/RegimeFilterStrategy-Freqtrade — **explicit regime strategy**
https://github.com/Bananajoexxc/RegimeFilterStrategy-Freqtrade · **3 stars** · MIT claimed in README **[API]**
Last push **2026-01-20** **[API]**. Tree: 6 blobs, 2 `.py` **[API]**: `strategies/RegimeFilterStrategy.py` and `user_data/strategies/RegimeFilterStrategy.py` (identical copies). Plus `config.json`, `docker-compose.yml`, `README.md`, `.gitignore`.

README **[RAW]** documents regime logic verbatim:
> A high-performance trading strategy for Freqtrade that adapts to market regimes using EMA crossovers.
> - **Bull Regime** (EMA50 > EMA100): Only takes long positions
> - **Bear Regime** (EMA50 < EMA100): Only takes short positions

It reports **[CLAIM]** (not verified here): +1,450% total return, Sharpe 0.37, max DD 29.24%, profit factor 1.40, 204 trades, 40.2% win rate, over Jul 2022–Jan 2026 on SOL/USDT futures 1h. It does carry a Risk Warning. **Very low star count and unverified self-reported numbers** — treat with caution.

### 7.13 OfficialGIGA/freqtrade-ml-strategy — **regime-aware ML strategy**
https://github.com/OfficialGIGA/freqtrade-ml-strategy · **1 star** · MIT claimed in README badge **[API]**
Last push **2026-06-11** **[API]**. Tree: 12 blobs, 2 `.py` **[API]**: `ultimate_alpha_v16.py` (the strategy, ~1000 lines) and `features.py`. Docs: `README.md`, `ARCHITECTURE.md`, `METHODOLOGY.md`, `RESULTS.md`, `CHANGELOG.md`, `config.example.json`, `requirements.txt`.

README **[RAW]** states: *"Includes regime-aware position sizing, ATR-based volatility-scaled stops"* and *"Regime-conditional entry threshold — base threshold is 0.58, lowered by 0.05 in risk-on regimes, raised by 0.08 in risk-off."* It also **self-reports a loss**: *"Real dry-run result: -$93.98 across 139 trades (Apr–May 2026, Kraken paper trading)… The strategy is not yet profitable."* Notably honest. Note the README references `train_model.py` and `backtest_notebooks/` which are **not present** in the tree — the repo is incomplete relative to its own README.

### 7.14 Other named results (metadata only, trees not fetched)
From `topic:freqtrade` / name searches **[API]**: `just-nilux/awesome-freqtrade` (97★, link list, not strategies, last push 2023-08-16), `Foxel05/freqtrade-stuff` (127★, no license, 2021-11-19 — stale), `titouannwtt/freqtrade-ultimate` (22★, GPL-3.0, 2026-09-12 — verified to be a **full freqtrade fork**, 4,351 blobs / 598 `.py`, with only `user_data/strategies/{kac_index_v1,kac_index_v2,simple_vwap_v1}.py` as its own strategies), `Ph3nol/FT-Trading-Bot` (61★, 2023-01-13), `joaorafaelm/freqtrade-heroku` (55★, 2021-09-04), `anakein/beastbotXB` (32★, 2022-05-23), `miwtoo/ft-action-zone` (23★, 2022-05-07), `freqstart/freqstart` (20★, MIT, 2023-03-13). I attempted `anakein/beastbotXB` and `miwtoo/ft-action-zone` on branch `master` and got **404** on the tree **[API]**, so their default branches differ; I did not spend further rate limit on them and their contents remain **unverified**.

---

## 8. Direct answers to the specific questions

**Q: Which repos contain strategies explicitly documented as SUITABLE FOR, or labelled by, market regime (trending / ranging / volatile)?**

| Repo | Regime documentation? | Evidence |
|---|---|---|
| **iterativv/NostalgiaForInfinity** | **YES — strongest.** 7 modes each documented against a market condition (Normal=trending, Pump=high volatility, Grind=ranging mean-reversion, Rebuy=ranging/mildly trending, Quick=consistent volatility, Rapid/Scalp=highly liquid/consistent volatility) | `docs/trading-modes/trading-modes.md` **[RAW]**; caveat: doc appears auto-generated |
| **freqtrade/freqtrade-strategies** (official) | **PARTIAL — code only, one strategy.** `TrendRiderStrategy.py` has `_get_market_regime()` returning `Ranging` / `Ranging (High Vol)` / `Trending Bull` / `Trending Bear` / `Trending Bear (High Vol)`. README has no per-strategy regime labels | `user_data/strategies/TrendRiderStrategy.py` lines 574–590 **[RAW]** |
| **Bananajoexxc/RegimeFilterStrategy-Freqtrade** | **YES — explicit** "Bull Regime (EMA50 > EMA100)" / "Bear Regime" | README **[RAW]** |
| **OfficialGIGA/freqtrade-ml-strategy** | **YES — explicit** "regime-aware position sizing", "risk-on / risk-off" thresholds | README **[RAW]** |
| paulcpk/freqtrade-strategies-that-work | **NO documented labelling** (4 of 5 names contain "WithTrend"; grep found no regime terms) | README **[RAW]** |
| Rikj000/MoniGoMani | **NO** (grep found no regime terms) | README **[RAW]** |
| TheoBrigitte/freqtrade | **NO** — has dirs named `trendfollowing/` and `volatility/`, but README says "folder names are arbitrary" and documents no regimes | README **[RAW]** + tree **[API]** |
| davidzr / jonlemofficial | **NO** — README documents nothing at all | README **[RAW]** |
| stash86 | **NO** beyond the inherited generic sentence | README **[RAW]** |
| keithorange/HUGE… | **NO** — README is one line; regime-sounding names only | README **[RAW]** + tree **[API]** |
| brookmiles, jilv220, raphant, freqsignals, mikedigriz, keryc | **NO documented regime labelling** (not individually grepped for regime terms beyond what is noted) | — |

**Q: Does the official `freqtrade-strategies` README carry a disclaimer about profitability / educational examples?**
**YES**, both. Verbatim (see §2.2 for full text): *"These strategies are for educational purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK…"* and *"they are provided as-is and without any warranty. They also mostly should serve as a starting point for your own strategies, not as 'ready to use' strategies."* Plus *"results will heavily depend on the pairs, timeframe and timerange used to backtest"* and *"Actual performance will be different based on various factors."* **[RAW]**

**Q: Does the official repo document that some strategies deliberately contain lookahead bias for testing purposes?**
**YES — but only in the subfolder readme, not the top-level README.** `user_data/strategies/lookahead_bias/readme.md` says *"Warning, Strategies in this folder do have a lookahead bias. Please see these as practice to see if you can spot the lookahead bias."* and then provides per-file solutions for all four: `DevilStra.py`, `GodStraNew.py`, `Zeus.py`, `wtc.py`. **[RAW]**

---

## 9. Explicit limitations of this audit

1. **No GitHub token** was available; all API calls were unauthenticated (60/hr). I used 28 core calls. Everything reported as **[API]** was fetched live on 2026-09-18.
2. **`netanelben/NostalgiaForInfinity` could not be inspected** — it returns 404 and the owner has no such repo. I did **not** locate a mirror of whatever it once was, so its former contents are **unverified and unknown**.
3. **Star counts are a point-in-time snapshot** and drift.
4. **`davidzr`'s 465 and `keithorange`'s 478 flat filenames** are saved in full to `research/gh/davidzr_py_files.txt` and `research/gh/huge_py_files.txt`; only representative subsets are inlined here to keep the report readable. Counts, directories and all inlined names are API-verified.
5. **Strategy quality/profitability was NOT evaluated.** No backtests were run. All performance numbers cited are marked **[CLAIM]** and come from the repos' own READMEs.
6. **Regime-term grepping was exhaustive for the official repo** (all 68 files fetched) and for the NFI docs, MoniGoMani, paulcpk and keithorange READMEs. It was **not** run file-by-file across `TheoBrigitte` (315 files), `davidzr` (465), or `keithorange` (478) — for those I rely on filenames plus their READMEs, and I say so above.
7. **License fields are GitHub's own detection.** `TheoBrigitte/freqtrade`, `brookmiles/freqtrade-stuff`, `keithorange/HUGE_…`, `Foxel05/freqtrade-stuff` and others report `license: null` — public but **all rights reserved** by default. The MIT/GPL claims for `Bananajoexxc` and `OfficialGIGA` come from their READMEs/badges, not from a `LICENSE` file confirmed present in their trees.
8. **Default branches not resolved for** `anakein/beastbotXB`, `miwtoo/ft-action-zone` (404 on `master`); contents unverified.
