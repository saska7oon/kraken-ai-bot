# RegimeFilterStrategy for Freqtrade

A high-performance trading strategy for Freqtrade that adapts to market regimes using EMA crossovers.

## Backtested Performance (Jul 2022 - Jan 2026, 3.5 years)

| Metric | Value |
|--------|-------|
| **Total Return** | +1,450% |
| **Sharpe Ratio** | 0.37 |
| **Sortino Ratio** | 0.87 |
| **Calmar Ratio** | 73.00 |
| **Max Drawdown** | 29.24% |
| **Profit Factor** | 1.40 |
| **Total Trades** | 204 |
| **Win Rate** | 40.2% |
| **Long Profit** | +610% |
| **Short Profit** | +840% |

**Settings:** 95% stake, 1x leverage, 12% TP, 5% SL
**Pair:** SOL/USDT Futures on Binance
**Timeframe:** 1 hour

## Strategy Logic

The strategy detects market regimes and only trades in the direction of the prevailing trend:

- **Bull Regime** (EMA50 > EMA100): Only takes long positions
- **Bear Regime** (EMA50 < EMA100): Only takes short positions

### Entry Conditions

**Long Entry (Bull Regime):**
1. EMA50 > EMA100 (bull regime)
2. Price breaks above 20-period high
3. Price is above EMA100
4. Volume surge (2.3x 20-period average)
5. Positive momentum (2% gain in 5 candles)

**Short Entry (Bear Regime):**
1. EMA50 < EMA100 (bear regime)
2. Price breaks below 20-period low
3. Price is below EMA100
4. Volume surge (2.3x 20-period average)
5. Negative momentum (2% drop in 5 candles)

### Exit Conditions
- Take Profit: 12%
- Stop Loss: 5%

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Binance Futures account with API keys

### Setup

1. **Clone this repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/RegimeFilterStrategy-Freqtrade.git
   cd RegimeFilterStrategy-Freqtrade
   ```

2. **Add your Binance API keys to `config.json`:**
   ```json
   "exchange": {
       "name": "binance",
       "key": "YOUR_API_KEY",
       "secret": "YOUR_API_SECRET",
       ...
   }
   ```

3. **Change the default passwords in `config.json`:**
   ```json
   "api_server": {
       "jwt_secret_key": "YOUR_RANDOM_SECRET",
       "ws_token": "YOUR_RANDOM_TOKEN",
       "username": "your_username",
       "password": "your_password"
   }
   ```

4. **Start the bot:**
   ```bash
   docker-compose up -d
   ```

5. **View logs:**
   ```bash
   docker-compose logs -f
   ```

### Dry Run Mode

The bot starts in **dry run mode** by default (`"dry_run": true` in config.json). This simulates trades without using real money.

To switch to live trading, change:
```json
"dry_run": false
```

## File Structure

```
RegimeFilterStrategy-Freqtrade/
├── config.json                 # Bot configuration
├── docker-compose.yml          # Docker setup
├── strategies/
│   └── RegimeFilterStrategy.py # The strategy file
└── user_data/
    ├── strategies/            # Strategy files (copied here by Docker)
    ├── data/                  # Downloaded candle data
    ├── logs/                  # Bot logs
    └── backtest_results/      # Backtest output
```

## Running Backtests

To run your own backtest:

```bash
# Download data first
docker-compose run --rm freqtrade download-data \
    --pairs SOL/USDT:USDT \
    --exchange binance \
    --timeframe 1h \
    --days 1300

# Run backtest
docker-compose run --rm freqtrade backtesting \
    --config /freqtrade/config.json \
    --strategy RegimeFilterStrategy \
    --timeframe 1h \
    --timerange 20220701-20260120
```

## Customization

### Change Trading Pair

Edit `config.json`:
```json
"pair_whitelist": [
    "BTC/USDT:USDT"
]
```

### Adjust Take Profit / Stop Loss

Edit `strategies/RegimeFilterStrategy.py`:
```python
minimal_roi = {"0": 0.12}  # 12% take profit
stoploss = -0.05           # 5% stop loss
```

### Enable Leverage

Edit `config.json`:
```json
"leverage": {
    "default_leverage": 2  # Change from 1 to 2x, 3x, etc.
}
```

## Risk Warning

Trading cryptocurrencies involves substantial risk of loss. Past performance does not guarantee future results. This strategy was backtested on historical data and may perform differently in live markets. Only trade with money you can afford to lose.

## License

MIT License - Use at your own risk.
