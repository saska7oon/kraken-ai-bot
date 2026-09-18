# Crypto Trading Strategies by Market Regime — Freqtrade / Kraken CAD / 5m

**Scope:** beginner-run, self-hosted Freqtrade bot, Kraken CAD pairs (BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD), 5-minute candles, dry-run, ~1000 CAD, moderate risk.

**Verification standard used throughout:** claims are labelled **[VERIFIED-URL]** (I fetched the source), **[VERIFIED-SOURCE]** (read the actual code file), **[BLOG]** (someone's published opinion/backtest, not evidence), or **[REASONING]** (my inference). Where I could not verify something I say so explicitly. No strategy below is invented or attributed to anyone who did not publish it.

---

## 0. TL;DR — the four findings that matter most

1. **Your fee assumption is probably ~3× too optimistic, and this alone can flip a 5m strategy from profitable to losing.** Freqtrade will assume Kraken taker **0.26%** / maker **0.16%** (ccxt's hardcoded default, because Kraken's API now returns *empty* fee arrays). Kraken's actual published **Kraken Pro Tier 1** rate — which is what a ~1000 CAD account on the API pays — is **0.80% taker / 0.40% maker**. Round-trip taker cost is therefore **1.60%**, not 0.52%. [VERIFIED-URL + VERIFIED-SOURCE, §1]
2. **On 5-minute candles the average BTC/CAD candle's *entire* range is 0.118% of price.** A 1.60% round-trip taker fee is **13.6 average 5m candles of total range**. No 5m scalping strategy can overcome that on this venue at Tier 1. [VERIFIED (computed from Kraken public API), §1]
3. **There is no built-in regime detection or automatic strategy switching in Freqtrade, and essentially nothing credible in the wild.** The word "regime" appears **0 times** in the entire Freqtrade documentation. All community "regime switching" repos I found have **0–4 stars**. The maintainers have explicitly refused to build it, citing remote-code-execution risk. The right pattern is a regime *filter inside one strategy*. [VERIFIED-URL, §4]
4. **With a 2-year backtest you can afford exactly 7 independent strategy configurations — Freqtrade's own FAQ recommends 10,000 hyperopt epochs.** That is a **~1,400× overrun** of the published trial budget. This is the strongest, most quantitative constraint in the report and it applies no matter which strategy you pick. [VERIFIED — verbatim from the primary source, §5.2]

Your four pairs are also **not** four independent bets: average pairwise daily-return correlation is **0.775** (I computed it), and an independent study puts a 14-coin crypto portfolio at roughly **2 effective bets**. Running one strategy per regime across them does not diversify anything. [VERIFIED (computed) + VERIFIED-URL, §5.4]

---

## 1. Critical practical findings for *your specific setup*

These are not strategies, but they determine whether any strategy can work. All are first-party verified.

### 1.1 Kraken's real fees vs what Freqtrade assumes

**Kraken's published Kraken Pro spot fee schedule, "Spot Crypto" table, Tier 1 ($0+ 30-day volume): Maker 0.40% / Taker 0.80%.** [VERIFIED-URL: https://www.kraken.com/features/fee-schedule — I parsed the fee tables out of the page HTML; the tables are JS-rendered so they do not appear in a plain text fetch.]

Tier progression (same table): Tier 1 $0+ → 0.40/0.80; Tier 2 $2.5K+ → 0.30/0.60; Tier 3 $10K+ → 0.22/0.38; Tier 4 $25K+ → 0.20/0.35.

A separate "Spot Maker Rebate" table (select lower-liquidity pairs) shows Tier 1 at 0.38% maker / 0.80% taker. Your CAD pairs are plausibly eligible, but the difference is trivial.

**What Freqtrade will actually use.** I traced the full chain in source:

- Kraken's `/0/public/AssetPairs` returns `"fees": []` and `"fees_maker": []` — verified by calling the live API. [VERIFIED]
- ccxt therefore sets market-level `maker = None`, `taker = None` (`ccxt/python/ccxt/kraken.py`, the `firstMakerFeeRate`/`firstTakerFeeRate` branches). [VERIFIED-SOURCE]
- `calculate_fee` does `rate = market[takerOrMaker]` → `None`; Freqtrade's `get_fee()` then falls back to the exchange default: `self._api.fees.get("trading", {}).get(taker_or_maker)`. [VERIFIED-SOURCE: `freqtrade/exchange/exchange.py`]
- ccxt's hardcoded Kraken default is `taker: 0.0026`, `maker: 0.0016`. [VERIFIED-SOURCE: `ccxt/python/ccxt/kraken.py`]

**Net effect:** Freqtrade assumes **0.26%/0.16%** where Kraken charges **0.80%/0.40%** at your tier — an understatement of ~3.1× (taker) and ~2.5× (maker). Freqtrade's own docs confirm fees come from this path: *"All profit calculations include fees, and freqtrade will use the exchange's default fees for the calculation."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/]

**Fix:** set `"fee": 0.008` (taker) or `0.004` (maker) explicitly in your config, or pass `--fee 0.008`. Freqtrade documents this remedy: *"Sometimes your account has certain fee rebates ... which are not visible to ccxt. To account for this in backtesting, you can use the `--fee` command line option ... This fee must be a ratio, and will be applied twice (once for trade entry, and once for trade exit)."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/]

**Also relevant:** Freqtrade backtesting assumes *"All orders are filled at the requested price (no slippage) as long as the price is within the candle's high/low range."* [VERIFIED-URL: same page]. So no slippage modelling either — on pairs that are 75–140× thinner than their USD equivalents (§1.3) that matters.

### 1.2 5m candle ranges vs round-trip fees — the arithmetic

Computed from Kraken's public OHLC API, 721 five-minute candles (≈2.5 days, which is all Kraken will serve), true range as % of close:

| Pair | Candles | Mean TR% | Median TR% | p90 TR% |
|---|---|---|---|---|
| BTC/CAD | 721 | **0.118** | 0.082 | 0.260 |
| ETH/CAD | 721 | 0.159 | 0.105 | 0.342 |
| SOL/CAD | 721 | 0.151 | 0.081 | 0.394 |
| XRP/CAD | 721 | 0.210 | 0.106 | 0.526 |

[VERIFIED — computed live from `https://api.kraken.com/0/public/OHLC`]

Round-trip costs:

| Scenario | Round-trip cost | BTC/CAD 5m candles of range needed |
|---|---|---|
| Taker both sides (0.80%+0.80%) | **1.60%** | **13.6** |
| Maker entry, taker exit (0.40%+0.80%) | 1.20% | 10.2 |
| Maker both sides (0.40%+0.40%) | 0.80% | 6.8 |
| *What Freqtrade assumes* (0.26%×2) | *0.52%* | *4.4* |

**Interpretation.** A 5m mean-reversion strategy with a 1% profit target (e.g. `ClucMay72018`'s `minimal_roi = {"0": 0.01}`) is **negative expectancy before any modelling error** at Tier 1 taker fees. To break even you must capture more than a full average candle's range *in your favour*, repeatedly, after costs. This is why the honest answer to "which 5m strategy for Kraken CAD" is: none of the freely published ones, unmodified, at Tier 1.

The remedies are: use **maker/limit orders** (halves the cost to 0.80% round trip), move to a **longer timeframe** (1h/4h targets are 5–20× the fee), or accept that the bot is a learning exercise in dry-run.

### 1.3 Liquidity: CAD pairs are thin

Kraken 24h volume and trade counts (live API):

| Pair | 24h base volume | 24h trades | Comparable USD pair | USD volume | Ratio |
|---|---|---|---|---|---|
| XBT/CAD | 9.30 BTC | 1,196 | XBT/USD | 1,847 BTC | **~199×** |
| ETH/CAD | 429 ETH | 1,933 | ETH/USD | 32,469 ETH | **~76×** |
| SOL/CAD | 2,720 SOL | 788 | — | — | — |
| XRP/CAD | 281,124 XRP | 883 | — | — | — |

[VERIFIED — `https://api.kraken.com/0/public/Ticker`]

Top-of-book spreads *are* tight (0.5–1.0 bps on all four CAD pairs, essentially matching USD pairs) — so the cost is **depth**, not spread. At 1000 CAD with 3 open trades (~333 CAD each) slippage is likely tolerable; the practical effect is **fewer fills and wider books during volatility**, which is exactly when breakout strategies want to trade. Note the spread figures are a single-moment snapshot.

### 1.4 You must use `--dl-trades` to backtest on Kraken

Kraken's OHLC API returned exactly **721** candles regardless of the interval I requested (5m and 1d both). That is **~2.5 days of 5m data** — useless for backtesting. Freqtrade documents this explicitly:

> *"The Kraken API does only provide 720 historic candles, which is sufficient for Freqtrade dry-run and live trade modes, but is a problem for backtesting. To download data for the Kraken exchange, using `--dl-trades` is mandatory, otherwise the bot will download the same 720 candles over and over, and you'll not have enough backtest data."*

[VERIFIED-URL: https://www.freqtrade.io/en/stable/exchanges/]

Practical consequence: your backtests will be built from Kraken's *trades* endpoint, which is slow to download and gives you a bounded history. Combined with §5's overfitting math, this is a real constraint on how much you can validate.

---

## 2. Strategies by market regime

Each entry: origin → exact rules → regime fit → weaknesses → Freqtrade usage.

### 2.A TRENDING UP

#### A1. Supertrend (ATR trailing-band trend follower)

**Origin.** Indicator attributed to **Olivier Seban**, French trader/author, 2009. Secondary-source attribution I could fetch: https://tutorials.topstockresearch.com/Supertrend/Supertrend.html ("The Supertrend Indicator was invented by Olivier Seban") [VERIFIED-URL]. Investopedia also states this (https://www.investopedia.com/supertrend-indicator-7976167) but returned **HTTP 403** to me, so I cite it only as a corroborating secondary source I could not read. **Honest note:** Supertrend's attribution to Seban rests on consistent secondary sources, not a primary publication I could retrieve.

**Freqtrade implementation (exact).** `user_data/strategies/Supertrend.py`, author **@juankysoriano (Juan Carlos Soriano)**. https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/Supertrend.py [VERIFIED-SOURCE — downloaded and read]

- Indicators: `ftt.supertrend(dataframe, period, multiplier)` from the `technical` library, called **6 times** with independently hyperoptable `(multiplier, period)` pairs: three "buy" instances, three "sell" instances.
- Shipped defaults: `buy_m1=4, buy_p1=8; buy_m2=7, buy_p2=9; buy_m3=1, buy_p3=8`; `sell_m1=1,sell_p1=16; sell_m2=3,sell_p2=18; sell_m3=6,sell_p3=18`.
- **Entry long:** `supertrend_1_buy == 'up' AND supertrend_2_buy == 'up' AND supertrend_3_buy == 'up' AND volume > 0`
- **Exit long:** `supertrend_1_sell == 'down' AND supertrend_2_sell == 'down' AND supertrend_3_sell == 'down' AND volume > 0`
- Repo settings: `timeframe = '1h'`, `startup_candle_count = 199`, `stoploss = -0.265`, trailing stop on (`+0.05` after `+0.144`).
- **Underlying Supertrend math** (standard form, for your own implementation): `basic_upper = (high+low)/2 + m*ATR(p)`, `basic_lower = (high+low)/2 - m*ATR(p)`; final bands ratchet (upper only falls, lower only rises) until price closes through them, then flip direction. Default `p=10, m=3` per the source above.

**Regime fit — trending up (and down).** It is a trend-follower by construction: it holds a direction until an ATR-scaled band is breached. Best when directional moves exceed noise.

**Known weaknesses (documented).** The source I fetched states plainly: *"It may give false signals or may not be beneficial when the market movements are sideways. The supertrend is effective only when the market is trending."* [VERIFIED-URL, same page]. Also, a band flip requires a close beyond the band, so it gives back a chunk of the move at every reversal, and it is whipsawed by repeated band flips in chop.

**Critical caveat on the Freqtrade file itself.** Its own docstring says:

> *"The implementation for `supertrend` on this strategy is not validated; meaning this that is not proven to match the results by the paper where it was originally introduced or any other trusted academic resources"*

and it cites a GitHub issue discussion as its basis. [VERIFIED-SOURCE]. So: the *idea* is published; the *Freqtrade code* is an unvalidated community implementation.

**Freqtrade usage — high.** Official repo has `Supertrend.py` and `futures/FSupertrendStrategy.py`. It is one of the most-copied strategies: TheoBrigitte's collection alone contains **15** `FastSupertrend_*` variants, and davidzr's archived collection has `FastSupertrend/` and `Supertrend/`. [VERIFIED via GitHub API]

---

#### A2. ADX-filtered moving-average crossover (`AdxSmas`)

**Origin.** Freqtrade file `berlinguyinca/AdxSmas.py`, author **Gert Wohlgemuth**, converted from the **Mynt** C# bot. https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/berlinguyinca/AdxSmas.py [VERIFIED-SOURCE]. The ADX itself is **J. Welles Wilder, "New Concepts in Technical Trading Systems" (1978)** — the book that also introduced RSI, ATR and Parabolic SAR. https://archive.org/details/newconceptsintec00wild [VERIFIED-URL]

**Exact rules** [VERIFIED-SOURCE]:
- `adx = ADX(14)`, `short = SMA(3)`, `long = SMA(6)`
- **Entry long:** `adx > 25 AND crossed_above(SMA3, SMA6)`
- **Exit long:** `adx < 25 AND crossed_above(SMA6, SMA3)`
- Repo: `timeframe='1h'`, `minimal_roi={"0": 0.1}`, `stoploss=-0.25`

**Regime fit — trending.** The ADX>25 gate is the point: Wilder's ADX measures trend *strength* irrespective of direction, so it suppresses entries in flat markets. This is the simplest defensible regime filter that exists and it is directly implementable.

**Weaknesses.** A 3/6 SMA cross is extremely noisy — on 5m it will cross constantly, and the ADX gate is lagging (ADX is derived from smoothed DMs), so it typically confirms a trend after much of it is gone. The exit condition is also asymmetric/odd (it requires ADX to *fall* below 25 *and* a bearish cross), so exits can be very late. No volume or volatility filter.

**Freqtrade usage — moderate.** Official repo (1 file); also present in davidzr's collection. Widely copied lineage via berlinguyinca.

---

#### A3. Donchian channel breakout (the Turtle system)

**Origin.** The **Turtle trading program**, run by **Richard Dennis and William Eckhardt** in 1983–84; channel breakouts descend from **Richard Donchian**. The rules were popularised in **Curtis Faith, "Way of the Turtle" (2007)**. **Honest provenance note:** the original rules were proprietary course material, not a journal publication; the version below is the widely republished consensus form. Representative fetchable summary: https://plutux.ai/resources/trading-systems/turtle-trading-breakout/rules [VERIFIED-URL — but note this is an SEO/education site, i.e. a secondary popularisation, not a primary source].

**Exact rules (widely published form).**
- **System 1 entry:** buy when price makes a new **20-period high**; sell short on a new 20-period low. Skip the trade if the previous breakout in that direction would have been a winner.
- **System 1 exit:** exit long on a **10-period low**.
- **System 2:** **55-period** high entry, **20-period** low exit.
- **Stop:** 2N below entry, where **N = 20-period ATR**.
- **Sizing:** 1 unit = 1% of account risk per N.
- In pandas/Freqtrade: `donchian_upper = dataframe['high'].rolling(20).max().shift(1)`, entry `close > donchian_upper` (the `.shift(1)` is essential to avoid lookahead).

**Regime fit — trending up (and down).** Long-horizon breakouts only pay in sustained trends.

**Weaknesses.** Low win rate (~35–40% is typical for the family), long losing streaks, and brutal whipsaw in ranges — the exact failure mode of the 20-period channel is a market oscillating near its 20-period extreme. Position sizing is integral to the original system, not optional; the entry rule alone is not the system.

**Freqtrade usage — low/indirect.** I found **no Donchian strategy in the official repo** (the 68 files contain none). It is trivially implementable but is not a well-known Freqtrade strategy. A 0-star hobby repo (`Kureshi25/cryptobot`) claims "Donchian breakout + regime-adaptive". Do not treat that as precedent.

---

#### A4. Heikin-Ashi + EMA crossover (`Strategy001`) — **5m native**

**Origin.** `user_data/strategies/Strategy001.py`, author **Gerald Lonlas**. [VERIFIED-SOURCE]

**Exact rules** [VERIFIED-SOURCE]:
- **Entry long:** `crossed_above(ema20, ema50) AND ha_close > ema20 AND ha_open < ha_close`
- **Exit long:** `crossed_above(ema50, ema100) AND ha_close < ema20 AND ha_open > ha_close`
- Repo: `timeframe = '5m'`, `minimal_roi = {"60":0.01,"30":0.03,"20":0.04,"0":0.05}`, `stoploss = -0.10`

**Regime fit — trending up.** EMA cross plus Heikin-Ashi bar colour confirmation.

**Weaknesses — and a red flag.** The **exit** condition is internally contradictory. It requires `crossed_above(ema50, ema100)` — a *bullish* event — to occur **simultaneously with a red Heikin-Ashi bar** (`ha_close < ema20 AND ha_open > ha_close`). Those two conditions pull in opposite directions, so the conjunction will fire only in a narrow, coincidental window. The practical effect is that the exit signal almost never triggers and trades actually close via `minimal_roi` or `stoploss`, not via the stated exit logic. Treat this file as a template to study, not a coherent system — and be aware that "the strategy's exit rule" as written is largely inert. Separately, Heikin-Ashi prices are synthetic averages, so `ha_close` is not a tradable price and its use introduces a systematic gap between signal and fill. Also note the `minimal_roi` ladder targets 1–5%, i.e. 0.6–3× the round-trip fee — marginal at Kraken Tier 1.

**Freqtrade usage — high (as a template).** Strategy001–005 are the canonical starter set in the official repo; the obsolete 2018 results table for them still circulates in the `stash86` fork. The official README has since dropped that table. [VERIFIED via GitHub API]

---

### 2.B TRENDING DOWN

**Blunt answer: there is no honest "trending down" *profit* strategy for your configuration.** Freqtrade's docs are unambiguous:

> *"Shorting is not possible when trading with `trading_mode` set to `spot`."* — and `margin` is *"currently unavailable"*.
> [VERIFIED-URL: https://www.freqtrade.io/en/stable/leverage/]

Kraken **futures is** supported (`"Kraken Futures uses the exchange id krakenfutures and supports isolated futures mode"`, `stake_currency: USD`), and Kraken is on the supported-futures list. [VERIFIED-URL: https://www.freqtrade.io/en/stable/exchanges/ and https://www.freqtrade.io/en/stable/] But that is a **separate, USD-margined venue with no CAD pairs** — it does not apply to BTC/CAD etc., and leveraged shorting is inappropriate for a beginner's moderate-risk dry run.

So in a downtrend your options are **defensive**: (i) stop taking longs, (ii) exit longs faster, (iii) hold CAD. The regime-detection logic in §4.1 and the ATR exit below are how you do that.

#### B1. Regime-gated stand-aside (bear regime → no new longs)

**Origin.** This exact classifier ships in the official repo: `user_data/strategies/TrendRiderStrategy.py`, `_get_market_regime()`. [VERIFIED-SOURCE — read the method]

```python
def _get_market_regime(self, last: dict) -> str:
    """Detect market regime from ADX + EMA200 + BB width."""
    adx_val = last.get('adx', 0)
    ema_200 = last.get('ema_200', 0)
    close   = last.get('close', 0)
    is_bull = last.get('is_bull', 0)
    bb_width     = last.get('bb_width', 0)
    bb_width_sma = last.get('bb_width_sma', 0)

    high_vol = bb_width > bb_width_sma * 1.5 if bb_width_sma > 0 else False

    if adx_val < 20:
        return "Ranging (High Vol)" if high_vol else "Ranging"
    elif is_bull and close > ema_200:
        return "Trending Bull"
    else:
        return "Trending Bear (High Vol)" if high_vol else "Trending Bear"
```

It is consumed as `min_conf = 6 if "Bear" in regime else 5` inside `confirm_trade_entry` — i.e. the bear regime demands a *higher* signal-confidence score before a long is allowed. [VERIFIED-SOURCE]

**Regime fit.** This is the regime *framework* itself: ADX(14) < 20 → ranging; ADX ≥ 20 + price above EMA200 → bull trend; otherwise bear; with BB-width > 1.5× its own average flagging high volatility. Clean, implementable, and it gives you all four of your requested regimes from three indicators.

**Weaknesses.** ADX and EMA200 both lag; a regime label flips *after* the move. EMA200 on **5m** is 200 candles ≈ 16.7 hours, so on your timeframe this is a very short-horizon "trend" that will flip often. BB-width-vs-its-own-SMA is a relative volatility measure, so it can read "high vol" in a permanently elevated regime. Nothing here is backtested evidence of profitability — it is a sensible engineering pattern.

**Freqtrade usage.** Present in the official repo as of the current `main`, but only as an internal helper in one contributed strategy — **not** a documented Freqtrade feature. This is the closest thing to an official, in-tree regime detector that exists.

#### B2. Chandelier Exit (ATR trailing stop)

**Origin.** **Chuck LeBeau**, popularised in Alexander Elder's books and Van Tharp's *Trade Your Way to Financial Freedom*. https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/chandelier-exit [VERIFIED-URL]

**Exact rule.** For longs: `stop = highest_high(N) - m * ATR(N)`, typically **N=22, m=3**. The stop ratchets up only. (Mirror for shorts.) [VERIFIED-URL, same page]

**Regime fit — trending down (as protection).** Its purpose is to keep you in a trend and eject you when it genuinely breaks, which is precisely what you want when a long turns into a downtrend.

**Weaknesses.** A 3×ATR stop is wide; in high volatility it gives back a lot before triggering, and it cannot distinguish a trend reversal from a violent but temporary pullback. It is an *exit* mechanism only — it is not an entry edge.

**Freqtrade usage — moderate, in a different form.** The official repo has `CustomStoplossWithPSAR.py` (Parabolic SAR — also Wilder 1978 — via `custom_stoploss`), not a Chandelier implementation. Chandelier is straightforward to write into `custom_stoploss`. Note Freqtrade also has native trailing stops (`trailing_stop`, `trailing_stop_positive`, `trailing_stop_positive_offset`), which many strategies use instead.

---

### 2.C RANGING / CHOPPY

#### C1. Bollinger Band + RSI mean reversion (`BbandRsi`)

**Origin.** `berlinguyinca/BbandRsi.py`, author **Gert Wohlgemuth**, converted from the **Mynt** C# bot (`sthewissen/Mynt`). [VERIFIED-SOURCE]

**Exact rules** [VERIFIED-SOURCE]:
- `rsi = RSI(14)`; Bollinger bands on **typical price** `(h+l+c)/3`, `window=20, stds=2`
- **Entry long:** `rsi < 30 AND close < bb_lowerband`
- **Exit long:** `rsi > 70`
- Repo: `timeframe='1h'`, `minimal_roi={"0": 0.1}`, `stoploss=-0.25`

**Regime fit — ranging.** It buys statistical extremes and sells the reversion, which is the correct posture when price oscillates around a mean.

**Weaknesses — this is the textbook "catching a falling knife" design.** There is **no trend filter at all**. In a downtrend, RSI stays <30 and price rides the lower band for extended periods, so the strategy keeps buying into a decline. Its `stoploss=-0.25` (25%!) confirms the author expected deep adverse excursions. `minimal_roi={"0": 0.1}` (10%) is also unrealistic for a 1h timeframe on majors.

**Freqtrade usage — very high.** Official repo. And this family is the single most over-generated in the ecosystem: davidzr's archived collection contains **58** filenames matching BB/Bollinger, including ~13 distinct `BBRSI*` variants (`BBRSI`, `BBRSI2`, `BBRSI21`, `BBRSI3366`, `BBRSIOptim2020Strategy`, `BBRSIv2`, …). [VERIFIED via GitHub API]. That proliferation is itself the warning sign discussed in §5.

---

#### C2. Bollinger dip-buy with EMA and volume filters (`ClucMay72018`) — **5m native**

**Origin.** `berlinguyinca/ClucMay72018.py`, author **Gert Wohlgemuth**. [VERIFIED-SOURCE]

**Exact rules** [VERIFIED-SOURCE]:
- Indicators: `RSI(5)`, `EMA(RSI,5)`, MACD, ADX, Bollinger(typical price, 20, 2σ), `EMA(50)` stored as `ema100`
- **Entry long:**
  `close < ema100 (EMA50)`
  `AND close < 0.985 * bb_lowerband`
  `AND volume < (volume.rolling(30).mean().shift(1) * 20)`
- **Exit long:** `close > bb_middleband`
- Repo: **`timeframe = '5m'`**, `minimal_roi = {"0": 0.01}`, `stoploss = -0.05`

**Regime fit — ranging, with a trend guard.** The `close < EMA50` condition means it only buys dips *below* the medium-term mean (i.e. it is not buying strength), and the `0.985 ×` lower band requires a genuine overshoot. The volume condition is a **no-pump filter**: only buy the dip if volume is *not* spiking (below 20× its 30-period average, shifted to avoid lookahead).

**Weaknesses — and the killer for your setup.** The risk/reward is inverted: **1% profit target against a 5% stop**. You need a very high hit rate for that to work, and one stop-out erases five winners. Then add Kraken's real cost: a 1.00% gross target minus a **1.60% round-trip taker fee is net −0.60%** — the strategy loses money on every "winning" trade at Tier 1. This is the clearest single illustration of why §1 matters more than strategy choice. Whipsaw risk: `0.985 ×` the lower band is a shallow threshold, so in a persistent decline it fires repeatedly.

**Freqtrade usage — high in the "Cluc" lineage.** Official repo. TheoBrigitte's collection holds **46** files in `strategies/cluc/` including `ClucHAnix_5m.py`, `ClucHAnix_BB_RPB_MOD.py`, `CombinedBinHAndClucV2`…`V8XH`, and many "trailbuy + offset" variants. [VERIFIED via GitHub API]. This is one of the most-forked strategy families in Freqtrade.

---

#### C3. Connors RSI-2 mean reversion

**Origin.** **Larry Connors** (with Cesar Alvarez), published in the book **"Short Term Trading Strategies That Work" (2008)**. I verified authorship and a *blog* backtest at https://quantifiedstrategies.substack.com/p/rsi-2-strategy-explained-larry-connors [VERIFIED-URL — I fetched this page]. **Important honesty note:** that page's trading rules are **paywalled**; I could not read the canonical rule text, and I could not verify the book's exact wording. The rules below are the widely-republished form; treat exact thresholds as variant-dependent.

**Widely-republished rules.**
- `rsi2 = RSI(2)`
- **Entry long:** `close > SMA(200)` (long-term uptrend filter) **AND** `RSI(2) < 5` (some variants use <10)
- **Exit long:** `close > SMA(5)` **OR** `RSI(2) > 70`

**Regime fit — ranging *within* an uptrend.** This is the important nuance: the SMA(200) filter means it is *not* a pure range strategy — it buys short-term panic inside a longer-term uptrend, which is a materially safer posture than `BbandRsi`'s unfiltered dip-buying. It is the classic "buy the dip in a bull market" rule.

**Weaknesses.** The 200-period filter fails at trend transitions (you keep buying dips in the early stage of a bear market). RSI(2) is extremely sensitive — two down candles can pin it near zero — so it fires often and is whippy on low timeframes. On 5m, `SMA(200)` is only ~16.7 hours, which is not a meaningful "long-term trend".

**Performance evidence.** The Quantified Strategies page reports a **blog backtest** on SPY 1993–present: 0.9% average gain per trade, ~9% CAGR, 34% max drawdown, invested only 28% of the time. [BLOG — this is one author's backtest of a *stock index ETF over decades*, not peer-reviewed, not crypto, not 5m, and the underlying rules are behind a paywall. It is **not** evidence that this works on Kraken CAD 5m.]

**Freqtrade usage — low.** I found **no** Connors RSI-2 strategy in the official repo. It is ~5 lines to implement, but there is no notable Freqtrade precedent.

---

#### C4. Multi-condition oversold dip buy with trend guard (`Strategy003`) — **5m native**

**Origin.** `user_data/strategies/Strategy003.py`, author **Gerald Lonlas**. [VERIFIED-SOURCE]

**Exact rules** [VERIFIED-SOURCE]:
- **Entry long (all must hold):** `rsi < 28` AND `rsi > 0` AND `close < sma` AND `fisher_rsi < -0.94` AND `mfi < 16.0` AND (`ema50 > ema100` OR `crossed_above(ema5, ema10)`) AND `fastd > fastk` AND `fastd > 0`
- **Exit long:** `sar > close` AND `fisher_rsi > 0.3`
- Repo: **`timeframe='5m'`**, `minimal_roi={"60":0.01,"30":0.03,"20":0.04,"0":0.05}`, `stoploss=-0.10`

**Regime fit — ranging/oversold bounces inside an uptrend** (the `ema50 > ema100` clause is the trend guard, and it mirrors Connors' SMA(200) idea).

**Weaknesses.** **Eight simultaneous conditions with hard-coded thresholds** (`28`, `-0.94`, `16.0`, `0`) is a high-dimensional specification. Every one of those numbers is a free parameter, and this is exactly the shape of strategy that hyperopt will happily curve-fit to noise (§5). Trade count will be low, so any backtest statistic will have wide error bars. `minimal_roi` targets 1–4% again, i.e. thin margins over a 1.60% round trip.

**Freqtrade usage — high (as a template).** Part of the official Strategy001–005 starter family.

---

### 2.D HIGH VOLATILITY

#### D1. ATR volatility breakout (`VolatilitySystem`)

**Origin.** Official repo `user_data/strategies/futures/VolatilitySystem.py`. Its docstring cites a **TradingView script**: *"Based on https://www.tradingview.com/script/3hhs0XbR/"* [VERIFIED-SOURCE]. **Honest note:** no individual author is credited in the file. This is the classic "volatility breakout" family (cf. Larry Williams' volatility breakout), but I could not verify a primary publication for this specific implementation, so I attribute it only to the TradingView script it cites.

**Exact rules** [VERIFIED-SOURCE]:
- Resample the base dataframe to **3h** (`resample_int = 60*3`), then `atr = ATR(14) * 2.0`; `close_change = close.diff()`; `abs_close_change = |close_change|`
- **Entry long:** `close_change > atr.shift(1)`
- **Entry short:** `-close_change > atr.shift(1)`
- **Exits:** the opposite signal (`enter_long == 1 → exit_short = 1`, and vice versa)
- Repo settings: `can_short = True`, `stoploss = -1`, `minimal_roi = {"0": 100}`, `position_adjustment_enable = True`, `custom_stake_amount` returns half the proposed stake. The comment notes *"Use `qtpylib.crossed_above` to get only one signal, otherwise the signal is active for the whole 'long' timeframe."*

**Regime fit — high volatility.** It explicitly trades *movement* rather than direction: any close-to-close move exceeding twice ATR triggers a position in that direction. In a volatility expansion this is the mechanism that captures the move.

**Weaknesses.** In choppy-but-volatile conditions it takes large candles **both ways** and gets whipsawed twice. `stoploss = -1` (100%) with `can_short` and position adjustment is **not** a moderate-risk configuration — this file is unsuitable for your profile as-is. Also note it operates on a 3h resample, so it is not a 5m strategy despite living in a repo you might copy wholesale.

**Freqtrade usage — low but official.** One file, in the `futures/` subfolder (which targets Binance futures, `margin_mode: isolated`, USDT pairs). Also mirrored as `volatility/VolatilitySystem{,V2}.py` in TheoBrigitte's collection.

---

#### D2. TTM Squeeze

**Origin.** **John Carter**, in **"Mastering the Trade" (2005)**. Documented at StockCharts ChartSchool: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze [VERIFIED-URL]

**Exact rules.**
- **Squeeze ON** when the **Bollinger Bands (20, 2σ) sit fully *inside* the Keltner Channels (20, 1.5×ATR)**. Per StockCharts and the corrected TradingView implementations, the correct logic is **AND** — *both* the upper and lower Keltner bands must be inside the Bollinger bands. (A common buggy variant uses OR, which fires almost always.)
- **Fire** when the squeeze releases (BB expand back outside KC).
- **Direction** from a momentum histogram (the standard is a linear-regression momentum of `close - avg(avg(highest_high, lowest_low), SMA(close))`). [VERIFIED-URL]

**Regime fit — transition from ranging into high volatility.** The squeeze is literally a *detector* of compressed volatility; the payoff is the expansion. This is the cleanest published framing of "ranging → volatile breakout" that I found.

**Weaknesses.** The squeeze can persist or re-fire for a long time, so entry timing is genuinely ambiguous; the momentum histogram frequently gives the wrong direction on release; and failed breakouts snap back inside the channel, producing fast losses. It is also an *indicator with a discretionary trading method*, not a fully specified mechanical system — Carter's book describes setups, not a single unambiguous rule set. Be honest that implementing "TTM Squeeze" means *you* choosing the momentum formula and the fire condition.

**Freqtrade usage — low.** I found **no** TTM Squeeze strategy in the official repo, and it was not among the notable community collections. Implementable with `ta.BBANDS` + a hand-rolled Keltner (`EMA(20) ± 1.5*ATR(20)`), but there is no established Freqtrade precedent to copy.

---

#### D3. `PowerTower` — momentum-burst detector

**Origin.** `user_data/strategies/PowerTower.py`, author **Masoud Azizi (@mablue)**, https://github.com/mablue/. [VERIFIED-SOURCE]

**Exact rules** [VERIFIED-SOURCE]:
- **Entry:** `close[0] > close[2] ** p AND close[1] > close[3] ** p AND close[2] > close[4] ** p`, with `p ≈ 3.849` (a hyperoptable `DecimalParameter(0, 4)`)
- Repo: **`timeframe = '5m'`**, `startup_candle_count = 30`, `stoploss = -0.288`

**Regime fit — high volatility / parabolic momentum.** The author describes it as *"a completely New Strategy (or Candlistic Pattern or Indicator) to finding strongly rising coins... much effective than 'Three black Crows'"* — a 3-bar accelerating-move pattern.

**Weaknesses — treat with real scepticism.** Comparing a price to a *power* of an earlier price is not a recognised technical-analysis construction; it is a curve fitted to detect acceleration, and `p = 3.849` is transparently a hyperopt artifact (a meaningful parameter would be a round number). The docstring's own results block shows wildly inconsistent outcomes across loss functions — *"Total profit 0.04808472 BTC (48.08%)"* under one objective and *"0.00754274 BTC (7.54%)"* under another, with trade counts ranging 10 to 165 on the same data. That spread across objectives is a hallmark of fitting noise. [VERIFIED-SOURCE — those numbers are quoted from the file]

**Freqtrade usage — moderate.** Official repo; also `momentum/PowerTower.py` in TheoBrigitte's collection.

---

### 2.E Regime map at a glance

| Regime | Best-sourced candidate | Freqtrade status | Timeframe in repo |
|---|---|---|---|
| Trending up | **Supertrend** (Seban) | Official, 2 files | 1h |
| Trending up (alt) | **AdxSmas** (Wilder ADX gate) | Official | 1h |
| Trending up (5m) | **Strategy001** HA+EMA | Official | **5m** |
| Trending up (long-horizon) | **Donchian/Turtle** | *Not in Freqtrade* | — |
| Trending down | **No short strategy available on spot.** Use TrendRider's `_get_market_regime()` bear gate + **Chandelier Exit** (LeBeau) for exits | Regime helper is official; Chandelier is not | — |
| Ranging | **BbandRsi** (unfiltered) / **Connors RSI-2** (filtered) | BbandRsi official; RSI-2 not in Freqtrade | 1h |
| Ranging (5m) | **ClucMay72018**, **Strategy003** | Official | **5m** |
| High volatility | **VolatilitySystem** (ATR breakout) | Official (`futures/`) | 3h resample |
| High volatility | **TTM Squeeze** (Carter) | *Not in Freqtrade* | — |
| High volatility (5m) | **PowerTower** (low confidence) | Official | **5m** |

---

## 3. Well-known public Freqtrade strategy repositories — what they actually contain

All counts verified via the GitHub REST API (unauthenticated, 2026-09-18). "★" is a point-in-time snapshot.

| Repository | ★ | License | Last push | Status |
|---|---|---|---|---|
| https://github.com/freqtrade/freqtrade-strategies | 5,491 | GPL-3.0 | 2026-09-08 | **Maintained (official)** |
| https://github.com/iterativv/NostalgiaForInfinity | 3,417 | GPL-3.0 | 2026-09-17 | **Maintained** |
| https://github.com/Rikj000/MoniGoMani | 1,025 | GPL-3.0 | 2023-03-11 | **ARCHIVED** |
| https://github.com/davidzr/freqtrade-strategies | 564 | GPL-3.0 | 2024-02-10 | **ARCHIVED** |
| https://github.com/paulcpk/freqtrade-strategies-that-work | 329 | MIT | 2021-06-14 | Stale ~5y |
| https://github.com/jilv220/BB_RPB_TSL | 214 | GPL-3.0 | 2022-02-21 | Stale |
| https://github.com/brookmiles/freqtrade-stuff | 212 | **none** | 2021-05-20 | **ARCHIVED** |
| https://github.com/imsatoshi/GeneTrader | 201 | MIT | 2026-07-29 | Maintained (a *generator*, not strategies) |
| https://github.com/TheoBrigitte/freqtrade | 129 | **none** | 2025-04-15 | Personal hoard, stalled |
| https://github.com/keithorange/HUGE_FreqTrade_Strategy_Collection | 58 | **none** | 2024-04-09 | Unmaintained scrape |
| https://github.com/stash86/freqtrade-strategies | 1 | GPL-3.0 | 2025-04-16 | **Dead fork of official** |
| https://github.com/jonlemofficial/freqtrade-community-strategies | 0 | GPL-3.0 | 2024-02-10 | **Dead, byte-identical fork** |

### 3.1 Corrections to two widely-repeated claims

- **`netanelben/NostalgiaForInfinity` does not exist** (HTTP 404). I enumerated all 62 public repos of that owner: no NostalgiaForInfinity, no Freqtrade repo. **Its former contents are unknown to me and I will not guess.** The real, actively maintained project is **`iterativv/NostalgiaForInfinity`** (3,417★, GPL-3.0, pushed 2026-09-17). [VERIFIED via GitHub API]
- **`jonlemofficial/freqtrade-community-strategies` is not an original.** It is `fork: true` with `parent`/`source` = `davidzr/freqtrade-strategies`. A blob-SHA diff of both trees showed **934 paths in each, 0 unique to either, 0 differing** — a byte-identical, zero-traction copy. There is **no live canonical "freqtrade-community-strategies"**; the original `davidzr` repo is **archived**. [VERIFIED via GitHub API]

### 3.2 What the official repo actually contains

**68 strategy `.py` files** plus one hyperopt, in four groups [VERIFIED via GitHub API]:

- **Root (27):** `AlmgrenChrissStrategy`, `Bandtastic`, `BreakEven`, `CustomStoplossWithPSAR`, `Diamond`, `FixedRiskRewardLoss`, `GodStra`, `Heracles`, `HourBasedStrategy`, `InformativeSample`, `MultiMa`, `PatternRecognition`, `PowerTower`, `Strategy001`–`Strategy005` (+`Strategy001_custom_exit`), `Supertrend`, `SwingHighToSky`, `TWAPStrategy`, `TrendRiderStrategy`, `UniversalMACD`, `hlhb`, `mabStra`, `multi_tf`
- **`berlinguyinca/` (30):** `ADXMomentum`, `ASDTSRockwellTrading`, `AdxSmas`, `AverageStrategy`, `AwesomeMacd`, **`BbandRsi`**, `BinHV27`, `BinHV45`, `CCIStrategy`, `CMCWinner`, **`ClucMay72018`**, `CofiBitStrategy`, `CombinedBinHAndCluc`, `DoesNothingStrategy`, `EMASkipPump`, `Low_BB`, `MACDStrategy`, `MACDStrategy_crossed`, `MultiRSI`, `Quickie`, `ReinforcedAverageStrategy`, `ReinforcedQuickie`, `ReinforcedSmoothScalp`, `Scalp`, `Simple`, `SmoothOperator`, `SmoothScalp`, `TDSequentialStrategy`, `TechnicalExampleStrategy`, `Freqtrade_backtest_validation_freqtrade1`
- **`futures/` (7 + Readme):** `FAdxSmaStrategy`, `FOttStrategy`, `FReinforcedStrategy`, `FSampleStrategy`, `FSupertrendStrategy`, `TrendFollowingStrategy`, **`VolatilitySystem`**
- **`lookahead_bias/` (4 + readme):** `DevilStra`, `GodStraNew`, `Zeus`, `wtc`

**The official README does carry a disclaimer** [VERIFIED-URL: https://github.com/freqtrade/freqtrade-strategies]:

> *"These strategies are for educational purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS."*

and, crucially for your question about whether these are ready to use:

> *"They also mostly should serve as a starting point for your own strategies, not as 'ready to use' strategies."*
> *"Some may only work in specific market conditions, while others are more 'general purpose' strategies."*
> *"Please keep in mind, results will heavily depend on the pairs, timeframe and timerange used to backtest — so please run your own backtests that mirror your usecase."*

Note also a stale artifact: the README says *"The results above…"* but **contains no results table at all**; the obsolete 2018 per-strategy table survives only in the `stash86` fork. Do not cite it.

**The repo documents deliberate lookahead bias** — `user_data/strategies/lookahead_bias/readme.md`:

> *"Warning, Strategies in this folder do have a lookahead bias. Please see these as practice to see if you can spot the lookahead bias."*

with per-file solutions: `DevilStra`/`GodStraNew` use `.min()`/`.max()` over the full dataframe; `Zeus` normalises with full-series min/max; `wtc` uses `MinMaxScaler().fit_transform()`. [VERIFIED-URL]. **These four must never be traded.** The top-level README never mentions lookahead bias.

### 3.3 Notable community collections

- **`iterativv/NostalgiaForInfinity` (3,417★)** — a *single* large multi-mode strategy family (`NostalgiaForInfinityX`…`X8`, plus `Next`/`NextGen`, and `legacy/`), not a collection. It has real tests (`tests/unit/test_NFIX5.py`, `test_NFIX7_bad_trade_controller.py`, `test_NFIX8_custom_exit.py`) and per-exchange blacklists for ~12 exchanges including **kraken**. It has the **best regime documentation of any repo I audited** — `docs/trading-modes/trading-modes.md` maps modes to market conditions: Normal = *"baseline trend-following… performs best in trending markets and may experience drawdowns during sideways or choppy market conditions"*; Pump = *"specifically designed for high-volatility momentum trading"*; Grind = *"a mean-reversion strategy specifically designed for ranging markets"*; Rebuy = *"most effective in ranging or mildly trending markets"*; Quick/Rapid/Scalp = consistent-volatility, liquid conditions. **Caveat:** the docs carry `<cite>` blocks and `**Section sources**` formatting that look auto-generated, so treat them as in-repo but not a hand-written maintainer guarantee. Historically some versions were sponsor-gated; I did **not** verify current gating. [VERIFIED via GitHub API + raw README/docs]
- **`davidzr/freqtrade-strategies` (564★, ARCHIVED)** — **465** strategy `.py` files, one directory each. This is a strategy *zoo*, not a curated set: **58** filenames match BB/Bollinger and **37** match RSI, including a dozen near-identical `BBRSI*` variants. Its README is 17 generic lines with **no disclaimer, no profitability warning, no educational-purposes statement, and no lookahead-bias note** — and it includes `DevilStra.py` (a strategy the official repo explicitly labels as having lookahead bias) **with no warning**. Materially weaker safety posture. [VERIFIED via GitHub API]
- **`TheoBrigitte/freqtrade` (129★, no license)** — 315 `.py`, an explicitly arbitrary personal hoard (*"Folder names are arbitrary"*). Contains 46 `cluc/` files, 23 NFI snapshots, 15 `FastSupertrend_*`, 29 `berlinguyinca/1h/`, plus `trendfollowing/`, `volatility/`, `renko/` directories. **No license declared = all rights reserved despite being public**; much is copied from others' repos. [VERIFIED via GitHub API]
- **`paulcpk/freqtrade-strategies-that-work` (329★, MIT, stale ~5y)** — exactly **5** files: `DoubleEMACrossoverWithTrend`, `EMAPriceCrossoverWithThreshold`, `MACDCrossoverWithTrend`, `RSIDirectionalWithTrend`, `RSIDirectionalWithTrendSlow`. Small, honest, MIT-licensed, but from the 2018/1h era. Its README carries a real disclaimer and a 2018–2020 results table **[CLAIM, unverified]**. [VERIFIED via GitHub API]
- **`keithorange/HUGE_FreqTrade_Strategy_Collection` (58★, no license)** — **478** flat `.py` files, README is one line. Contains `LookaheadStrategy.py` **and** `LookaheadStrategy.zip`, plus `DevilStra.py`, `GodStraNew.py`, `wtc.py`, `Fakebuy.py` — **with zero warnings and no license**. I recommend against using this repo. [VERIFIED via GitHub API]
- **`Rikj000/MoniGoMani` (1,025★, ARCHIVED 2023)** — a framework + one master strategy (`MasterMoniGoManiHyperStrategy.py`) with a signal-weighting hyperopt, not a strategy collection. No regime labelling. [VERIFIED via GitHub API]

**Bottom line on repositories:** there are exactly **two** actively maintained, meaningful public repos — the official `freqtrade/freqtrade-strategies` and `iterativv/NostalgiaForInfinity`. Everything else large is archived, stale, unlicensed, or an uncurated scrape. None of them is a set of regime-labelled, ready-to-run strategies for Kraken CAD 5m.

---

## 4. Automatic regime detection / strategy switching in Freqtrade

### 4.1 Does it exist?

**No.** Verified negatives:

1. **No built-in regime detection.** The word **"regime" appears 0 times in the entire Freqtrade documentation tree** (grepped the full `docs/` of `develop` and the rendered `/en/stable/` pages). Freqtrade does not use the term.
2. **No runtime strategy switching.** `--strategy-list` exists but is a **backtesting comparison** flag only: *"To compare multiple strategies, a list of Strategies can be provided to backtesting."* It is a member of `ARGS_BACKTEST` and is **absent from `ARGS_TRADE`** — so `freqtrade trade --strategy-list ...` does not exist. [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/ ; VERIFIED-SOURCE: `freqtrade/commands/arguments.py`]
3. **No API/REST endpoint to select a strategy.** Only `POST /reload_config`, which reloads the config and re-reads the strategy *named in the config file*. [VERIFIED-URL: https://www.freqtrade.io/en/stable/rest-api/]
4. **Maintainer refusal, explicitly.** In freqtrade issue #8263 ("Switch between Strategies"), maintainer **xmatthias**: *"there's no plans to allow people to fully remotely switch strategies - as that opens up too many possibilities for remote code execution."* and *"Strategies are always read from file (from the pre-defined strategies directory)."* He notes `/reload_conf` is *"technically an (almost full) restart"* and warns that swapping strategies means *"the new strategy rules will apply to the open trade - eventually resulting in an immediate sell if the stoploss moved from -20% to -5%."* [VERIFIED-URL: https://github.com/freqtrade/freqtrade/issues/8263]
   Related: issue #12236 (2025) requested a built-in market-regime helper; the maintainer replied it *"sounds more like something that should be done **within a strategy**"* and that verifying an external data source for lookahead bias is *"near impossible to determine this reliably."* [VERIFIED-URL: https://github.com/freqtrade/freqtrade/issues/12236]
5. **A partial mechanism does exist** — and it's worth knowing precisely. The FAQ states `/reload_config` will *"reload the configuration and strategy and will restart with the new configuration and strategy."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/faq/]. I confirmed in source that `Worker._reconfigure()` tears down and rebuilds the bot, which re-runs `StrategyResolver.load_strategy(config)`. [VERIFIED-SOURCE: `freqtrade/worker.py`, `freqtrade/resolvers/strategy_resolver.py`]. So a *file-swap + `/reload_config`* can switch strategies — but it is an almost-full restart, driven externally, with open-trade handling left to you. That is orchestration, not automatic regime switching.

### 4.2 The documented extension points (all intra-strategy)

These are the real building blocks. None of them switches strategy files.

| Mechanism | What it does | URL |
|---|---|---|
| `confirm_trade_entry` / `confirm_trade_exit` | Last check before an order; return `False` to abort. **This is where a regime gate belongs.** | https://www.freqtrade.io/en/stable/strategy-callbacks/ |
| `enter_long` / `enter_short` columns | The signals themselves; colliding signals are ignored | https://www.freqtrade.io/en/stable/strategy-customization/ |
| `@informative` / informative pairs | Compute indicators on a *different timeframe or pair* (e.g. BTC 1h) and merge in — the idiomatic way to build a higher-timeframe regime filter | https://www.freqtrade.io/en/stable/strategy-customization/ |
| `DataProvider.get_pair_dataframe()` | Fetch another pair's candles at runtime | same page |
| Protections (`StoplossGuard`, `MaxDrawdown`, `LowProfitPairs`, `CooldownPeriod`) | *"protect your strategy from unexpected events and market conditions by temporarily stop trading"* — the official closest thing to regime-adaptive behaviour. Must be enabled with `--enable-protections` in backtest. | https://www.freqtrade.io/en/stable/plugins/ |
| `custom_stoploss`, `custom_exit`, `adjust_trade_position` | Dynamic exits and position management | https://www.freqtrade.io/en/stable/strategy-callbacks/ |
| `market_direction` | Official but **manual** (set via Telegram `/marketdir`). Docs warn it *"is not persisted, and will be reset after a bot restart/reload"* and that strategies using it *"will probably not produce reliable, reproducible results (changes to this variable will not be reflected for backtesting)."* | https://www.freqtrade.io/en/stable/telegram-usage/ |
| FreqAI | Has classifiers and outlier/market-shift detection (Dissimilarity Index, SVM, DBSCAN) but **no built-in regime classifier**; you define the target yourself in `set_freqai_targets()` | https://www.freqtrade.io/en/stable/freqai/ |

**The correct pattern** is therefore: **one strategy file that computes a regime column and gates its own entries.** Which is exactly what `TrendRiderStrategy._get_market_regime()` does (§2.B1), and what NostalgiaForInfinity does with its seven modes inside one file.

### 4.3 Does regime switching exist "in the wild"?

**Rare and mostly hype.** I searched GitHub directly. Every Freqtrade regime-specific repo has **0–4 stars**:

| Project | ★ | What it actually is | Honest assessment |
|---|---|---|---|
| `Thordersonjg/freqtrade-regime-filter` | 0 | Gates entries via a **third-party commercial "Regime API"** | Real code, but a funnel for a paid API, and it puts an external network call in the trade path |
| `Bananajoexxc/RegimeFilterStrategy-Freqtrade` | 3 | EMA50/EMA100 bull/bear gate on SOL/USDT futures | Regime *filter in one strategy*, not switching. Headline claim **"+1,450% backtested return"** alongside **Sharpe 0.37** — internally inconsistent, unverified, no license. Treat as a red flag, not a reference. |
| `songhuaxueyue-tech/trend-regime-transformer` | 4 | Transformer classifying 1h OHLCV into up/down/range, as an "enhancement factor" | Genuine research repo; explicitly a *factor*, not a switcher |
| `OfficialGIGA/freqtrade-ml-strategy` | 1 | LightGBM with "regime-aware position sizing" | Notable for honesty: its README **self-reports a loss** ("-$93.98 across 139 trades… not yet profitable") and its README references files absent from the tree |
| `Ph3nol/Trading-Bot` | 138 | PHP "Freqtrade Manager" orchestrating many Dockerised instances | The most-starred thing in this space — but it is a **deployment manager**, not regime switching. Last push 2021. |

Searches for `freqtrade+strategy+switching` returned **0 repositories**. [VERIFIED via GitHub API]

### 4.4 Known pitfalls of regime switching

1. **Lookahead in the regime detector.** If you classify regime using full-series statistics (`.min()`, `.max()`, `MinMaxScaler`), you get the same lookahead bias the official repo warns about. Freqtrade's `lookahead-analysis` command exists to catch this — *"Usually the bias in the strategy is **THE** driving factor for 'too good to be true' profits."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/lookahead-analysis/]
2. **Lag.** Every regime detector (ADX, EMA200, BB-width, HMM) labels the regime *after* the transition. You systematically trade the old regime into the new one.
3. **Regime-flip whipsaw.** A detector that flips frequently means you switch strategies exactly when both are wrong. This is worse than running one mediocre strategy.
4. **Open-trade discontinuity.** Switching strategies mid-trade changes the rules applied to a live position — the maintainer's explicit warning above about a stoploss moving from -20% to -5%.
5. **Multiple-testing explosion.** Every regime you add is another set of parameters to fit. See §5 — this is the dominant risk.
6. **No backtestable, non-persisted state.** `market_direction` is documented as not backtestable and reset on reload; any external regime service introduces unbacktestable state.

---

## 5. How many strategies should a small retail bot run? Overfitting risk

### 5.1 The primary-source mathematics — this is the strongest evidence available

**Bailey, Borwein, López de Prado & Zhu, "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance", *Notices of the American Mathematical Society*, May 2014, pp. 458–471.**
URLs: https://www.ams.org/notices/201405/rnoti-p458.pdf · preprint https://www.davidhbailey.com/dhbpapers/backtest-pseudo.pdf [VERIFIED-URL; I downloaded the preprint PDF and extracted its text]

Verbatim from the abstract:

> *"We prove that high performance is easily achievable after backtesting a relatively small number of alternative strategy configurations, a practice we denote 'backtest overfitting.' The higher the number of configurations tried, the greater is the probability that the backtest is overfit. Because financial analysts rarely report the number of configurations tried for a given backtest, investors cannot evaluate the degree of overfitting in most investment claims and analysis."*

And the headline quantitative result — the **Minimum Backtest Length (MinBTL)**. Verbatim from the paper (I extracted this passage directly from the PDF):

> *"Figure 2 shows the trade-off between the number of trials (N) and the minimum backtest length (MinBTL) needed to prevent skill-less strategies to be generated with a Sharpe ratio IS of 1. For instance, **if only 5 years of data are available, no more than 45 independent model configurations should be tried.** For that number of trials, the expected maximum SR IS is 1, whereas the expected SR OOS is 0. **After trying only 7 independent strategy configurations, the expected maximum SR IS is 1 for a 2-year long backtest, while the expected SR OOS is 0.** The implication is that a backtest which does not report the number of trials N used to identify the selected configuration makes it impossible to assess the risk of overfitting."*

[VERIFIED — extracted verbatim from the primary-source PDF]

The paper also gives the closed-form upper bound:

> *"the upper bound to the minimum backtest length (in years), MinBTL < 2·ln[N] / E[max_N]²"*

and explicitly notes the independence assumption is conservative: *"Proposition 2.1 assumed the N trials to be independent, which leads to a quite conservative estimate."*

**On provenance:** the paper's acknowledgements state *"We are indebted to the Editor and two anonymous referees who peer-reviewed this article for the Notices of the American Mathematical Society."* So it **was refereed** — though *Notices of the AMS* is a general-interest mathematics magazine, not a research journal, so weight it accordingly.

Related verified sources:
- **Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality", *Journal of Portfolio Management*, vol. 40 (2014), pp. 94–107** — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf [VERIFIED-URL, PDF fetched; title/venue confirmed]. Its key artefact: it corrects a Sharpe ratio for the number of trials, and its worked example shows **the *same* backtest is investable at N=46 trials but not investable at N=88** — i.e. the verdict on one strategy depends entirely on how many alternatives you tried first.
- **Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest Overfitting"** — https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf [VERIFIED-URL, PDF fetched]. Introduces **PBO** and combinatorially symmetric cross-validation (CSCV): with S=16 partitions there are 12,780 combinations. Its empirical finding is the most sobering single sentence in this literature: *"100% of the SR IS are positive, about 78% of the SR OOS are negative… the higher the SR IS, the lower the SR OOS."* In that example PBO was **74%** — i.e. a ~3-in-4 chance the selected strategy underperforms the median out-of-sample.
- **Bailey, Ger, López de Prado, Sim & Wu, "Statistical overfitting and backtest performance", in *Risk-Based and Factor Investing*, Elsevier, 2015, pp. 449–461** — https://www.davidhbailey.com/dhbpapers/overfitting.pdf [VERIFIED-URL]

### 5.2 Apply that to your actual setup — the numbers are stark

- **How much data do you have?** Kraken's OHLC API serves **~720 candles** (I measured 721). On 5m that is **2.5 days**. You will need `--dl-trades` to build anything, and realistically you will have **well under 5 years** — probably 1–2 years at best on 5m. MinBTL scales roughly with the number of trials, so fewer years permits *fewer* configurations, not more.
- **What does Freqtrade recommend?** Its own FAQ says: *"Per default Hyperopt ... will only run 100 epochs ... Too few to find a great result ..., so you probably have to run it for 10000 or more"* and *"It's therefore recommended to run between 500-1000 epochs over and over until you hit at least 10000 epochs in total."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/faq/]

**The number that applies directly to you: with a 2-year backtest, the paper's own figure is 7 independent configurations.** Verbatim: *"After trying only 7 independent strategy configurations, the expected maximum SR IS is 1 for a 2-year long backtest, while the expected SR OOS is 0."* [VERIFIED — primary source]

| Your available data | Max independent configurations (MinBTL) | Freqtrade FAQ recommends |
|---|---|---|
| 2 years | **7** | 10,000 epochs |
| 5 years | 45 | 10,000 epochs |

**10,000 epochs against a budget of 7.** That is a **~1,400× overrun** for a 2-year dataset (and ~200× even if you had 5 years). This is the single most important statistical fact in this report, and it applies regardless of which strategy you pick.

(Fair caveat, stated by the paper itself: MinBTL assumes *independent* trials, and Bayesian hyperopt epochs are correlated, so the effective number of independent trials is lower than 10,000 — the paper calls the independence assumption *"a quite conservative estimate."* But even a 100× haircut on 10,000 epochs leaves you outside a budget of 7.)

### 5.3 What Freqtrade's own docs actually warn (and what they don't)

**Notable negative finding: there is no overfitting or curve-fitting section in the Hyperopt docs.** The string "overfit" occurs exactly **3 times** on the Hyperopt page, all one repeated note:

> *"To limit the search space further, Decimals are limited to 3 decimal places ... This is usually sufficient, **every value more precise than this will usually result in overfitted results.**"*
> [VERIFIED-URL: https://www.freqtrade.io/en/stable/hyperopt/]

The substantive warnings live elsewhere:

- **Strategies 101:** *"**Some websites that list and rank Freqtrade strategies show impressive backtest results. Do not assume these results are achieveable or realistic.**"* and *"it can be very easy to distort results so a strategy will look a lot more profitable than it really is."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/strategy-101/]
- **Backtesting assumptions:** *"backtesting will **never** replace running a strategy in dry-run mode. Also, keep in mind that **past results don't guarantee future success**."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/]
- **`--show-pair-list`:** *"Only using winning pairs can lead to an overfitted strategy, which will not work well on future data."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/utils/]
- **The p-value note — the closest thing to a multiple-testing warning:** *"because backtesting and hyperopt evaluate many strategies, some will score a low p-value by chance alone, so a small value only tells you a result is hard to explain by noise; it is not by itself proof of a genuine edge."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/]
- **Lookahead analysis:** *"Usually the bias in the strategy is **THE** driving factor for 'too good to be true' profits."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/lookahead-analysis/]
- **FreqAI** is the only place with explicit overfitting controls: `noise_standard_deviation` — *"adds noise to the training features with the aim of preventing overfitting"*; `continual_learning` — *"high probability of overfitting/getting stuck in local minima"*; `early_stopping_patience`, `randomize_starting_position`. [VERIFIED-URL: https://www.freqtrade.io/en/stable/freqai-parameter-table/]

**And another negative finding:** **"walk-forward" and "out-of-sample" are not documented concepts in Freqtrade at all** (zero hits across the docs tree). `--timerange` is framed only as *"a smaller test-set"*, not as OOS validation. The nearest documented practices are:
- **`--timeframe-detail`** as a final reality check — *"to ensure your strategy is not exploiting one of the backtesting assumptions ... although only forward-testing (dry-mode) can really confirm a strategy."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/backtesting/]
- **`lookahead-analysis`** — detects future-data leakage by chaining backtests and diffing indicator values/signals; outputs `has_bias`, `biased_entry_signals`, `biased_indicators`. Documented caveats: it *"can only verify / falsify the trades it calculated"*, untriggered signals give false negatives, and FreqAI target indicators are falsely flagged and *"can safely be ignored."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/lookahead-analysis/]
- **`recursive-analysis`** — detects a *different* failure: indicator values that depend on how much history was loaded, which differ between backtest and live. It computes indicators at `startup_candle_count` values of 199/499/999/1999 and reports variance; *"When recursive analysis shows a variance of 0%, then you can be sure that you have enough startup candle data."* [VERIFIED-URL: https://www.freqtrade.io/en/stable/recursive-analysis/]

### 5.4 Diversification across your four pairs is largely illusory

I computed this from Kraken's public API — 661 aligned daily closes (~2 years), daily log-return correlations [VERIFIED — computed live]:

| | BTC | ETH | SOL | XRP |
|---|---|---|---|---|
| **BTC** | 1.000 | 0.842 | 0.798 | 0.754 |
| **ETH** | 0.842 | 1.000 | 0.809 | 0.723 |
| **SOL** | 0.798 | 0.809 | 1.000 | 0.723 |
| **XRP** | 0.754 | 0.723 | 0.723 | 1.000 |

**Average pairwise correlation: 0.775.** Annualised daily volatility: BTC 42.2%, ETH 68.4%, SOL 76.0%, XRP 78.6%.

**External corroboration.** Giller, *"Correlation without Factors in Retail Cryptocurrency Markets"*, arXiv:2412.04263 (2024-12-05) — https://arxiv.org/abs/2412.04263 [VERIFIED-URL, title/author/abstract retrieved via the arXiv API]. On a 14-coin retail universe it finds the average pairwise correlation of daily returns *"high (of order 60%)"* and derives the **effective degrees of freedom N\*(N)** — for that universe a 14-coin portfolio behaves like roughly **2 independent bets**. Different universe, different method, same conclusion as my own computation: crypto portfolios are far less diversified than their asset count suggests. Giller also explicitly *rejects* the linear factor model used by some other crypto-correlation papers, so "one factor explains X%" claims from other sources are a **competing description**, not a consistent estimate of the same quantity.

Two consequences:
1. **Four pairs ≈ one bet.** With 0.775 average correlation, your effective number of independent positions is closer to ~1.3 than 4 (Giller's N\* metric points the same way). `max_open_trades: 3` across these pairs means you will very often be holding three positions that are the same trade. Your real risk is roughly 3× what the position sizing implies.
2. **Regime switching buys you little.** If all four pairs share a regime most of the time, then detecting "the regime" and routing between strategies gains far less than it would across genuinely uncorrelated assets. This is a structural argument against building an elaborate regime-switching system for this portfolio.

One further documented property worth knowing: crypto correlations are **not stable — they rise in crashes**, exactly when you need diversification. James & Menzies report pairwise correlation moving from **0.456 to 0.784** across the COVID peak (as cited by the subagent research; I did not personally verify that figure, so treat it as **[UNVERIFIED-SECONDARY]**). My own single-snapshot 0.775 is a full-period average and therefore understates the stress-period correlation.

### 5.5 So how many strategies?

**Honest framing, stated up front: this specific question is answered by opinion and practitioner experience, not by evidence.** No study I could find establishes an optimal *number of strategies* for a retail bot. The rigorous literature is about the **number of trials**, and it points one way. So I separate the two:

**(a) What is evidenced — the trial budget.** With ~1–2 years of 5m data the MinBTL result gives you **7 independent configurations** (§5.2). That is the hard constraint. Every strategy you test, every parameter you tune, and every regime you add spends from that same budget.

**(b) What practitioners say — opinion, labelled as such.** The most concrete public figure is **Rob Carver** (author of *Systematic Trading*), who has disclosed the shape of his own system: on the order of **~11 rule families**, ~40 variations, across ~146 instruments, with a median per-instrument Sharpe around 0.27 and low correlation (~0.05) between subsystems. Two things about that are more useful than the raw counts:

- **His stated priority is the opposite of "add more strategies."** He argues it is *"much, much, much more important"* to have a sound framework and broad **instrument** diversification, and that adding further rules is *"your last resort"* with *"rapidly diminishing returns."* In one direct test he reports that adding rules made performance slightly **worse**. [**BLOG/BOOK — practitioner opinion and self-reported experience, not peer-reviewed evidence. I did not personally verify these quotations; they come from the subagent research and are labelled accordingly.**]
- **His instrument-count → Sharpe ladder** is the single most transferable artefact for your situation: roughly **1 instrument → 0.35, 8 → 0.61, 37 → 0.70**. The gain comes from *breadth*, not from strategy cleverness — which for you is bad news, because your four pairs are 0.775 correlated (§5.4), so you cannot buy that breadth.

**Ernie Chan** (quant, author of *Quantitative Trading*) makes the complementary point: prefer a **range** of parameters around the optimum rather than the single best value, and notes that parameter optimisation *"often adds no value."* [**BLOG/BOOK — opinion**]

**(c) My recommendation [REASONING], grounded in (a) and (b):**
- **The binding constraint is your trial budget, not your strategy count.** With 1–2 years of 5m data you can afford on the order of **a handful** of independent, pre-specified configurations — not hundreds of hyperopt epochs.
- **For a 1000 CAD beginner bot: run one strategy at a time.** Not four. The correlation data shows multiple pairs already give correlated exposure; multiple strategies multiply the number of ways you can be wrong while adding little diversification.
- **Prefer one strategy with an explicit regime *filter*** over four strategies with a regime *switcher*. That keeps the trial count low, keeps state backtestable, and matches the only pattern the Freqtrade maintainers endorse.
- **Do not hyperopt to 10,000 epochs.** Choose parameters from published defaults or round numbers, then validate on a held-out `--timerange` you never optimised on, then run `lookahead-analysis` and `recursive-analysis`, then dry-run. Treat any parameter that hyperopt pushes to a value like `3.849` (cf. `PowerTower`) as evidence of fitting noise.

### 5.6 AI/LLM-generated strategies — the evidence is better than I expected

**Correction to my earlier position:** I initially wrote that I found no rigorous evidence base here. On a second, more targeted search the subagent found real peer-reviewed material, and **I independently verified all three papers exist with the titles, authors and abstracts below** via the arXiv API:

- **"Can LLM-based Financial Investing Strategies Outperform the Market in Long Run?"** — Li, Kim, Cucuringu & Ma, arXiv:2505.07078 (2025-05-11) — https://arxiv.org/abs/2505.07078 [VERIFIED-URL]. This is the **FINSABER** framework. Its abstract states the core problem directly: *"most evaluations of LLM timing-based investing strategies are conducted on narrow timeframes and limited stock universes, overstating effectiveness due to survivorship and data-snooping biases."* Re-evaluating published LLM agents over two decades and 100+ symbols, reported results degraded sharply — the subagent reports individual Sharpes flipping from **1.440 to −1.247** with no statistically significant alpha (all p > 0.34). [The paper's existence, authors and abstract framing are **VERIFIED**; the specific numbers are **[UNVERIFIED-SECONDARY]** — I did not extract them from the full text myself.]
- **"What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery"** — Eray Gençay, arXiv:2608.27734 (2026-08-27) — https://arxiv.org/abs/2608.27734 [VERIFIED-URL]. Applies Deflated Sharpe and PBO corrections to LLM-discovered strategies and reports rejecting them. **The methodologically important finding, confirmed in the abstract I retrieved:** *"a deliberately leaky oracle posting a Sharpe ratio of 35 survives Deflated Sharpe"* — i.e. **DSR and PBO do not catch look-ahead bias.** That is a crucial caveat: statistical corrections for multiple testing are not a substitute for leakage checks (`lookahead-analysis`). [Paper **VERIFIED**; the rejection counts are **[UNVERIFIED-SECONDARY]** and rest on a single preprint.]

**What this means for you, and what it does not.** The verifiable, structural point is unchanged and now better supported: the MinBTL mathematics applies to *any* generator of many candidate strategies, human or machine — an LLM that emits 200 variants is a trial-budget disaster by construction, and the new work suggests LLM-discovered strategies are especially prone to **look-ahead/contamination** rather than merely to ordinary curve-fitting. But: the strongest LLM-specific numbers come from a **single preprint** by one author, and I did not verify them at full text. I am not claiming "AI strategies don't work"; I am claiming the trial-budget and leakage risks are real, documented, and apply to you regardless of whether a human or a model wrote the code.

For completeness, the non-LLM version of the same failure mode is already visible in the ecosystem: davidzr's 465 files with 58 Bollinger variants and 37 RSI variants is a human-generated strategy zoo with the identical statistical problem. And a Freqtrade maintainer publicly warned a contributor about AI-generated PR spam on a regime-gate PR (#13317, self-closed) [VERIFIED-URL: https://github.com/freqtrade/freqtrade/pull/13317].

---

## 6. What I could not verify (stated plainly)

1. **Kraken fee history.** The 0.40%/0.80% Tier 1 figure is today's published schedule. I did not verify when it changed or whether a 1000 CAD account gets a different rate in practice. **Verify your own fee tier in your Kraken account before trusting any backtest.**
2. **`netanelben/NostalgiaForInfinity` contents.** 404; not recoverable; not guessed.
3. **Connors RSI-2 exact book rules.** The canonical text is behind a paywall and I could not read the book. Thresholds cited are the widely-republished form and **vary between sources**.
4. **Supertrend's primary attribution.** Consistent across secondary sources (Olivier Seban), but I found no primary publication; Investopedia returned 403 to me.
5. **Turtle rules primary source.** The 1983–84 course material is proprietary; the cited rules are the widely-republished consensus form from secondary sites.
6. **`VolatilitySystem` authorship.** The file credits only a TradingView script; no individual author verified.
7. **No backtests were run by me.** Every performance figure in this report is either a repo's own self-reported claim **[CLAIM]**, a blog's backtest **[BLOG]**, or absent. **None of it is evidence of future profitability.** Most freely published Freqtrade strategies have **no reliable evidence of profitability at all** — the official repo's own README says they are *"a starting point for your own strategies, not 'ready to use' strategies"*, and Freqtrade's own docs warn *"Some websites that list and rank Freqtrade strategies show impressive backtest results. Do not assume these results are achieveable or realistic."*
8. **~~Practitioner-opinion sourcing~~ — RESOLVED.** A subagent that was still running when I first finalised has since delivered, and I incorporated its findings into §5.4–§5.6. Two caveats on that material: (i) the Carver/Chan quotations are **practitioner opinion from books/blogs, not evidence**, and I did **not** personally verify those quotations at source — they are labelled **[BLOG/BOOK]** and should be treated as such; (ii) the LLM-specific numbers (FINSABER's Sharpe flips, Gençay's rejection counts) are **[UNVERIFIED-SECONDARY]** — I verified all three arXiv papers exist with the stated titles/authors/abstracts, but I did not extract those specific figures from the full texts myself.
9. **Subagent-verified vs self-verified.** Where I relied on subagent research I have marked it. Everything in §1 (fees, 5m ranges, liquidity, correlation, candle limits), §2's code quotations, §3's repository metadata, and §4's documentation negatives I verified **personally**, by fetching the page, reading the file, or calling the API. The main subagent-derived items are the repo-inventory details in §3.3 and the §5.5–§5.6 practitioner/LLM material.

## 7. Official disclaimers (quoted exactly)

**Freqtrade docs front page** [VERIFIED-URL: https://www.freqtrade.io/en/stable/]:

> *"**DISCLAIMER** — This software is for educational purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS. Always start by running a trading bot in Dry-run and do not engage money before you understand how it works and what profit/loss you should expect."*

**Official strategy repo README** [VERIFIED-URL: https://github.com/freqtrade/freqtrade-strategies]: *"These strategies are for educational purposes only... USE THE SOFTWARE AT YOUR OWN RISK."* and *"they are provided as-is and without any warranty. They also mostly should serve as a starting point for your own strategies, not as 'ready to use' strategies."*

---

## 8. Recommended concrete next steps for your bot

Ordered by expected impact.

1. **Set your real fee.** Add `"fee": 0.008` to your config (or `--fee 0.008`), then re-run every backtest. Your current backtests are ~3× too optimistic. Verify the exact rate on your Kraken account first. This is the highest-value single change.
2. **Reconsider 5m.** The arithmetic in §1.2 is not close: 0.118% mean candle range vs 1.60% round-trip. If you stay on 5m, use **limit/maker orders** (0.80% round trip) and treat the bot as a learning exercise. **1h is the timeframe most published strategies actually target** — and 4h more so. Moving to 1h is a bigger improvement than any strategy swap.
3. **Use `--dl-trades`** for data, or you will silently backtest the same 2.5 days forever (§1.4).
4. **Pick ONE strategy** matched to the regime you most expect, with a regime *filter* inside it — not a regime switcher. The most defensible starting points, in order: `AdxSmas` (ADX>25 gate is a real, published regime filter), `Supertrend` (published indicator, but unvalidated Freqtrade implementation), `ClucMay72018` (5m native, sensible no-pump filter — but fix the 1%/5% risk-reward), `Strategy003` (5m native, trend-guarded dip buy — but 8 hard-coded parameters).
5. **Do not hyperopt to 10,000 epochs.** With a 2-year dataset the published budget is **7 independent configurations** (§5.2). Use published defaults or round numbers, hold out a `--timerange` you never optimised on, and treat large hyperopt gains as suspect. Concretely: pick parameters once, from the literature, and don't re-run hyperopt every time results disappoint — that is exactly how the trial count explodes.
6. **Run the two official checks before dry-run:** `freqtrade lookahead-analysis` and `freqtrade recursive-analysis`. [https://www.freqtrade.io/en/stable/lookahead-analysis/ · https://www.freqtrade.io/en/stable/recursive-analysis/] **Do not skip this because you "corrected for overfitting"** — the research in §5.6 shows a deliberately leaky strategy with a Sharpe of 35 *passes* both Deflated Sharpe and PBO. Statistical corrections do not detect look-ahead; only the leakage check does.
7. **Add protections** (`StoplossGuard`, `MaxDrawdown`, `CooldownPeriod`) — the official mechanism for "stop trading in bad conditions". Remember `--enable-protections` for backtests. [https://www.freqtrade.io/en/stable/plugins/]
8. **Cut `max_open_trades` or accept the correlation.** At 0.775 average correlation your three slots are largely one position (§5.4).
9. **If you want a regime framework, use the one already in the official repo** — `TrendRiderStrategy._get_market_regime()` (ADX + EMA200 + BB-width, §2.B1) — rather than a 0-star third-party repo or a paid regime API. But note EMA200 on 5m is only ~16.7 hours.

**The honest bottom line:** the freely published Freqtrade strategies are educational starting points with **no reliable evidence of profitability**, and the specific combination you have chosen — Kraken CAD, 5-minute candles, Tier-1 fees, 1000 CAD, spot-only — is close to the most hostile configuration available for short-timeframe trading. The most valuable outputs of this research are the fee correction, the 5m viability arithmetic, and the trial-budget constraint, not the strategy list.
