# Kraken AI Trading Bot

> **Self-hosted, AI-enhanced crypto trading bot for Kraken Canada (CAD markets)**
> Built with **Freqtrade** + **Custom AI Orchestrator** (OpenRouter)
> Designed for **security-first** credential isolation via Docker secrets

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Exchange** | Kraken Canada (Spot only - CAD markets) |
| **Trading Engine** | Freqtrade (stable, 54k+ ⭐) |
| **AI Orchestration** | Custom Python service via OpenRouter |
| **AI Model** | `nvidia/nemotron-3-ultra-550b-a55b:free` (configurable) |
| **Stake Currency** | CAD (native, tax-friendly) |
| **Pairs** | BTC/CAD, ETH/CAD, SOL/CAD, XRP/CAD |
| **Risk Profile** | Moderate (configurable: conservative/moderate/aggressive) |
| **Security** | Docker secrets - **no credentials on disk** |
| **UI** | FreqUI (port 8081, Basic Auth) |
| **Notifications** | Discord webhook |
| **Backups** | Encrypted (age) → Nextcloud (WebDAV) |
| **Control** | Natural language via REST API |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Freqtrade   │  │   FreqUI     │  │   AI Orchestrator    │  │
│  │  (Core Bot)  │  │  (Web UI)    │  │  (OpenRouter + AI)   │  │
│  │  Port 8080   │  │  Port 8081   │  │  Port 8082           │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                       │              │
│         └─────────────────┼───────────────────────┘              │
│                           ▼                                      │
│              ┌────────────────────────┐                          │
│              │    Docker Secrets      │                          │
│              │  (Keys NEVER on disk)  │                          │
│              └────────────────────────┘                          │
│                           │                                      │
│                           ▼                                      │
│              ┌────────────────────────┐                          │
│              │  Backup Sidecar        │                          │
│              │  (age → Nextcloud)     │                          │
│              └────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose v2+
- Kraken Canada account with API keys
- OpenRouter API key (free tier available)
- Discord webhook (optional)
- Nextcloud with WebDAV (optional)

### 1. Clone & Setup
```bash
git clone <repo> kraken-ai-bot
cd kraken-ai-bot
```

### 2. Create Secrets (ONE TIME - NEVER COMMIT)

Secrets are **Docker Swarm secrets created in Portainer**, not files in this
repository. See [SECRETS.md](SECRETS.md) for the full inventory and the
Portainer steps. In short:

```bash
# Generate the values locally, then paste each one into
# Portainer -> Secrets -> Add secret
openssl rand -base64 32   # freqtrade_api_password
openssl rand -base64 32   # freqtrade_encrypt_key
openssl rand -base64 48   # orchestrator_api_token
openssl rand -base64 32   # backup_encrypt_key (or use age-keygen)
# Kraken + OpenRouter keys come from those providers
```

> There is no `secrets/` directory in the deployment path, and no `.env` file.
> Credentials exist only as Swarm secrets, mounted read-only at `/run/secrets/`
> and never placed in the environment or on disk.

### 3. Configure Kraken API
1. Log into [Kraken Pro](https://pro.kraken.com)
2. Create API key with permissions:
   - ✅ Query Funds
   - ✅ Query Open Orders & Trades
   - ✅ Query Closed Orders & Trades
   - ✅ Create & Modify Orders
   - ✅ Cancel Orders
   - ❌ Withdraw Funds (NEVER enable)
3. Set IP allowlist to your server IP (recommended)

### 4. Deploy
```bash
docker compose up -d
```

### 5. Verify
```bash
# Check all services
docker compose ps

# View logs
docker compose logs -f

# Test endpoints
curl -u freqtrade:PASSWORD http://localhost:8081/api/v1/ping  # FreqUI / freqtrade

# The AI orchestrator is NOT published to the host. Reach it over the swarm
# network instead (see SECRETS.md -> Orchestrator API Authentication):
docker run --rm -it --network kraken-bot-network curlimages/curl \
  http://ai_orchestrator:8082/health
```

### 6. Access Web UI
Open http://localhost:8081 (FreqUI, served by the freqtrade container)
- Username: `freqtrade`
- Password: (from the `freqtrade_api_password` Swarm secret)

---

## 💬 Natural Language Control

All routes require the bearer token from the `orchestrator_api_token` Swarm
secret, and the orchestrator port is not published to the host. See
[SECRETS.md](SECRETS.md#orchestrator-api-authentication) for how to reach it.

```bash
export ORCHESTRATOR_TOKEN=...   # your orchestrator_api_token secret
# Assumes an SSH tunnel:  ssh -L 8082:localhost:8082 <user>@<pi-host>
# The orchestrator port is not published on the host by design.
export API=http://localhost:8082

# Check status
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" $API/api/v1/status

# Ask a plain-language question
curl -X POST $API/api/v1/explain/ask \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "How am I doing so far?"}'

# Plain-language digest (works even with no AI available)
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" $API/api/v1/explain/digest

# Confirm the safety posture: dry-run, protections, autonomous trading
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" $API/api/v1/safety

# Pause trading (this one really executes)
curl -X POST $API/api/v1/command \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "pause trading"}'

# Explain a trade decision
curl -X POST $API/api/v1/command \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "why did the bot sell ETH?"}'

# Ask for a change (returns a PROPOSAL - see below)
curl -X POST $API/api/v1/command \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "Switch to conservative mode"}'
```

### Two kinds of command

**Runtime actions execute for real.** These map onto things Freqtrade genuinely
supports at runtime:

| Command | What happens |
|---------|--------------|
| "pause trading" / "resume trading" | Bot stops/starts opening new trades. Open positions are still managed. |
| "only trade BTC/CAD" | Runtime pair restriction (does not survive a restart) |
| "show my status" / "how am I doing?" | Reads real data and explains it |
| "why did it sell ETH?" | Explains the exit reason in plain language |

**Configuration changes produce a proposal, never an application.** Freqtrade
reads its configuration at startup and exposes no runtime config-write endpoint;
the orchestrator cannot write the Swarm config either. So a proposal like
"switch to conservative" comes back with the exact values to apply and
`"proposals_applied": false`.

To actually apply it: update the `freqtrade_canada_config` Swarm config in
Portainer with those values and redeploy. Nothing changes until you do.

### Approval flow

Commands that alter behaviour come back as `pending_approval` with a
**`proposal_id`**. Approving names that id — you never send the change list back:

```bash
# 1. Ask
curl -X POST $API/api/v1/command \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "make it more conservative"}'
# -> {"status": "pending_approval", "proposal_id": "Kf3...", "expires_in_seconds": 1800, ...}

# 2. See what is waiting (optional)
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" $API/api/v1/proposals

# 3. Approve by id
curl -X POST $API/api/v1/approve \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": "Kf3...", "approve": true}'
```

To decline, send the same body with `"approve": false`.

**Why the id matters.** The orchestrator stores the proposal it generated and
applies *that stored list* — the request body cannot supply its own. This closes
a real hole: previously `/api/v1/approve` applied whatever changes you posted, so
a request containing `{"key": "dry_run", "value": false}` would be accepted,
recorded as human-approved, and handed back with instructions to put it in your
Swarm config — for a proposal that was never made.

Additional properties, all of which are deliberate:

| Behaviour | Why |
|-----------|-----|
| Proposals **expire after 30 minutes** | An approval should be a decision about something you just read, not a standing permission |
| Each id works **once** | No replaying an approval you already used |
| A changed list is **refused** (409) | The stored list is fingerprinted; tampering is detected, not applied |
| Approving **re-validates** the stored changes | Frozen keys and safety bounds are enforced on approval too, not only when proposing |
| A proposal **cannot trigger a plugin run** | Use `POST /api/v1/plugins/{name}/control` for that, explicitly |
| Pending proposals live **in memory** | A restart discards them — it fails closed, never open |

If you are labelling a shared deployment, send `X-Operator-Name: your-name` so
the audit log records *who* approved, rather than a generic `operator`.

> Two older behaviours are gone and will be refused rather than silently ignored:
> the `force: true` flag on `/api/v1/command` (HTTP 422), and posting a `changes`
> array to `/api/v1/approve` (HTTP 400, with a message telling you to use
> `proposal_id`).

### Frozen settings

Some things can never be changed through chat or the API, at any confidence
level. `dry_run` is the most important:

> "Switching between simulation and live trading cannot be done through the AI
> interface. This is deliberate: live mode places real orders with real money.
> To go live you must edit the `freqtrade_canada_config` Swarm config in
> Portainer, change `dry_run` to false, and redeploy — and you should have weeks
> of satisfactory dry-run results first."

Also frozen: `exchange.*`, `api_server.*`, `jwt_secret_key`, `ws_token`.

Everything else is bounds-checked. A stop loss wider than -15% or tighter than
-2%, or more than 5 simultaneous trades, is refused with an explanation of why.

---
```bash
curl -X POST http://localhost:8082/api/v1/plugins/strategy_generator/control \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  -d '{"action": "disable"}'
```

---

## 🔐 Security Model

### Credential Isolation
```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER SECRETS                            │
├─────────────────────────────────────────────────────────────┤
│  kraken_api_key         → Only Freqtrade container           │
│  kraken_api_secret      → Only Freqtrade container           │
│  openrouter_api_key     → Only AI Orchestrator               │
│  freqtrade_api_password → Freqtrade + AI Orchestrator        │
│  orchestrator_api_token → Only AI Orchestrator               │
│  discord_webhook        → Freqtrade + AI Orchestrator        │
│  nextcloud_*            → Only Backup sidecar                │
│  backup_encrypt_key     → Only Backup sidecar                │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles
- ✅ **No credentials in images, configs, logs, or environment**
- ✅ **AI Orchestrator NEVER sees Kraken keys** - only talks to Freqtrade REST API
- ✅ **All secrets mounted as files at `/run/secrets/`**
- ✅ **Orchestrator API requires a bearer token; fails closed if unconfigured**
- ✅ **Orchestrator port is not published to the host**
- ✅ **Audit log tracks every AI action with hash chaining**
- ✅ **Human approval required for all config changes**
- ✅ **Switching to live trading cannot be done through the API** - it requires
  editing a Swarm config and redeploying, outside the AI's reach
- ✅ **The AI cannot activate a strategy** - it can only propose one that has
  passed a safety validator and a real backtest

### What the bot will not do
These are enforced in code, not just documented:

| Action | Enforced by |
|--------|-------------|
| Change `dry_run` via API or chat | Frozen-key refusal in `nl_config.py` |
| Apply a config change automatically | No Freqtrade runtime config-write endpoint exists; `update_config()` raises |
| Trade without human approval | `autonomous_agent` disabled and unreachable via API |
| Activate a generated strategy | Activation requires a Swarm config edit |
| Exceed the AI budget | Daily request cap in `openrouter_client.py` |
| Run an unsafe generated strategy | `proposal_validator.py` + backtest gate |

### Freqtrade protections (circuit breakers)

These live on the **strategy**, in `config/strategies/moderate_multi.py`, as a
`protections` property. They are **not** in `config/base.json` — Freqtrade 2026.x
rejects a `protections` key there outright and refuses to start:

```
Configuration error: DEPRECATED: Setting 'protections' in the configuration is deprecated.
```

So if you want to change a circuit breaker, edit the strategy, not the config.

| Protection | Setting | Effect |
|------------|---------|--------|
| `MaxDrawdown` | 288 candles (~24h), 10% | Stops trading for ~24h if the account loses >10% from its peak |
| `StoplossGuard` | 96 candles (~8h), 3 trades | Pauses all trading if 3 trades hit their stop loss within ~8h |
| `CooldownPeriod` | 12 candles (~1h) | Waits ~1h after an exit before opening a new trade |

Candle counts are on the 5m timeframe, so 288 candles ≈ 24h, 96 ≈ 8h, 12 ≈ 1h.

**Any strategy the AI generates must define all three.** The safety validator
rejects a proposal without them (`protections_missing`), because a strategy with
no circuit breakers looks perfectly healthy right up until a bad streak empties
the account. You can confirm what is actually armed at any time:

```bash
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  http://<pi-ip>:8082/api/v1/safety
```

### AI failure is not a trading failure

If OpenRouter is unreachable, the API key is missing, or the daily free-tier
budget is spent, the orchestrator degrades to deterministic output. It never
blocks or influences order execution — signals come from the strategy, not the
model. `/api/v1/explain/digest` still returns a plain-language summary computed
in Python.

---

## 🤖 What the AI is actually for

The AI **explains, and writes strategies for you**. It does not decide trades,
and it cannot change the *running* bot's configuration.

That last point is a limitation of Freqtrade, not a policy choice: Freqtrade has
no API for changing its configuration while running, and these config files are
mounted read-only from Docker Swarm configs. So there are exactly two things the
AI can genuinely change, and both are deliberate:

1. **Strategies.** It can write a new one for you to review and activate. This is
   the "configuration" it is really for — see the workflow below.
2. **Which pairs trade** (narrowing only). It can restrict trading to fewer of
   your approved pairs. It can never add a pair that is not already approved.

Everything else — risk settings, stop loss, position size — comes back as a
**proposal with exact values** that you apply yourself by editing the Swarm
config and redeploying. Nothing changes until you do.

| Plugin | Schedule | Cost | What it does |
|--------|----------|------|--------------|
| **explainer** | Daily 08:00 | 1/day | Plain-language digest: what the bot did, what the numbers mean, what needs attention. Never predicts prices or gives advice. |
| **strategy_generator** | Weekly | ~1/week | Proposes strategies; each must pass the safety validator **and** a real backtest before it is shown to you. |
| **market_analyst** | Hourly | 0 | Computes indicators in Python. Reports facts; the explainer narrates them on demand. |
| **param_optimizer** | Every 6h | ~4/day | Reviews real trade statistics and suggests parameter changes for you to apply manually. |
| **nl_config** | On-demand | per command | Runtime actions (pause/resume/restrict pairs/status) execute for real. Everything else is a proposal. |
| **autonomous_agent** | **DISABLED** | — | Would trade without asking. Deliberately unreachable via the API. |

Total scheduled AI usage is well under the 200 requests/day free-tier cap. The
`market_analyst` plugin previously ran every 15 minutes and asked a model to
re-derive indicators Python had already computed — roughly 96 requests/day for
no additional signal. That is now zero.

---

## 🧭 Getting the AI to adjust your strategy

This is the part to actually use. You do not need to read or write Python.

### "What is it doing right now?"

```bash
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  http://<pi-ip>:8082/api/v1/explain/digest
```

Plain-language summary of what the bot did, what the numbers mean, and whether
anything needs attention. Costs nothing — it is computed in Python and only
narrated by the model.

### "What are the market conditions?"

```bash
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  http://<pi-ip>:8082/api/v1/plugins/market_analyst/control \
  -H 'Content-Type: application/json' \
  -d '{"action": "run"}'
```

Computes RSI, MACD, Bollinger Bands, ATR, trend and a market regime
(`trending_up` / `trending_down` / `ranging` / `volatile`) across 5m, 1h, 4h and
1d candles, per pair. No AI cost.

### "Make me a strategy for these conditions"

```bash
curl -H "Authorization: Bearer $ORCHESTRATOR_TOKEN" \
  http://<pi-ip>:8082/api/v1/plugins/strategy_generator/control \
  -H 'Content-Type: application/json' \
  -d '{"action": "run"}'
```

The model writes candidate strategies from the live market data and your actual
trade history. **Every candidate must clear three gates before you ever see it:**

1. The safety validator — correct interface, plain numeric stop loss, sane risk
   bounds, no dangerous code, and all three circuit breakers present.
2. A real backtest over ~180 days.
3. Minimum trades, profit, Sharpe and maximum drawdown thresholds.

A proposal that fails any gate is discarded and never shown to you. Survivors are
written to `proposal_<timestamp>_<name>.py` with a header explaining what they do.

### Turning a proposal on

Activating one is a deliberate two-step, and it should be:

1. **Read the header** of the proposal file. It states in plain language what the
   strategy does and that a backtest is a simulation against *past* prices — a
   good backtest is not a promise.
2. Point the Swarm config at it: change `--strategy` in the `freqtrade` service
   (and `freqtrade_strategy` config) from `ModerateMultiPairStrategy` to the new
   class name, then redeploy.

If you are unsure, leave it. The running strategy already has circuit breakers.

### Adjusting the running strategy without the AI

Edit `config/strategies/moderate_multi.py`, recreate the `freqtrade_strategy`
Swarm config, and redeploy. The settings worth knowing:

| Setting | What it means |
|---------|---------------|
| `stoploss` | How much one trade can lose before it closes automatically. `-0.08` = 8%. |
| `minimal_roi` | Take profit at these levels, e.g. `{"0": 0.04}` = sell at +4%. |
| `timeframe` | Candle size. `5m` = decisions every 5 minutes. |
| `protections` | The circuit breakers. Keep all three. |

### A note on honesty

The bot will not tell you it can predict prices, because it cannot and neither
can anything else. Its job is to follow deterministic rules you can inspect,
explain them in plain language, and stop trading when things go wrong. Treat the
dry-run period as the lesson: watch what it does, read the digest, and only
consider live money once you understand *why* it makes the trades it makes.

---

## 📊 Configuration

### Risk Profiles
```yaml
conservative:
  max_open_trades: 2
  stoploss: -0.05
  tradable_balance_ratio: 0.80

moderate:  # DEFAULT
  max_open_trades: 3
  stoploss: -0.08
  tradable_balance_ratio: 0.90

aggressive:
  max_open_trades: 4
  stoploss: -0.12
  tradable_balance_ratio: 0.95
```

Switch via: `"Switch to aggressive mode"`

### Pairs (Kraken Canada 2026)
| Pair | Volume | Min Order | Notes |
|------|--------|-----------|-------|
| BTC/CAD | 17.3 BTC | 0.00005 | Deep liquidity |
| ETH/CAD | 420 ETH | 0.001 | Excellent |
| SOL/CAD | 6,098 SOL | 0.06 | Excellent |
| XRP/CAD | 503k XRP | 1.65 | Good |

---

## 🛡 Canadian Compliance Notes

**Kraken Canada Restrictions (2026):**
- ❌ No margin trading
- ❌ No futures/derivatives
- ❌ No xStocks (tokenized equities)
- ❌ Limited staking (no GRT, FLR)
- ✅ Spot trading fully available
- ✅ Interac e-Transfer & Wire funding

**Tax:** All gains/losses in CAD - simplifies CRA reporting.

---

## 📁 Project Structure

```
kraken-ai-bot/
├── docker-compose.yml
├── .env.example
├── config/
│   ├── base.json              # Freqtrade base config
│   ├── canada_kraken.json     # Canada-specific overrides
│   ├── ai_orchestrator.yaml   # AI plugin config
│   └── strategies/
│       └── moderate_multi.py  # Main strategy
├── ai_orchestrator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                # FastAPI service
│   ├── core/                  # OpenRouter, Freqtrade API, Audit, Plugin Manager
│   └── plugins/               # 5 AI plugins
├── backup/
│   ├── Dockerfile
│   ├── backup.sh              # rclone + age encryption
│   └── encrypt.sh
├── secrets/                   # USER CREATES - NEVER IN REPO
│   ├── kraken_api_key.txt
│   ├── kraken_api_secret.txt
│   ├── openrouter_api_key.txt
│   ├── freqtrade_api_password.txt
│   ├── freqtrade_encrypt_key.txt
│   ├── discord_webhook.txt
│   ├── nextcloud_url.txt
│   ├── nextcloud_user.txt
│   ├── nextcloud_pass.txt
│   └── backup_encrypt_key.txt
└── README.md
```

---

## 🔧 Operations

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f freqtrade
docker compose logs -f ai_orchestrator
docker compose logs -f backup
```

### Update Bot
```bash
docker compose pull
docker compose up -d
```

### Backup Now (Manual)
```bash
docker compose exec backup /app/backup.sh
```

### Restore from Backup
```bash
# Download from Nextcloud, decrypt:
age -d -i backup_encrypt_key.txt backup_file.tar.gz.age > backup_file.tar.gz
tar -xzf backup_file.tar.gz
```

### Dry-run → Live

**This is the one irreversible step in the whole system, and it is deliberately
awkward.** No AI, no API token and no chat command can do it — if any of those
could, a bug or a bad prompt could put real money at risk.

1. Run in dry-run for **weeks**, not days. Confirm the protections work: check
   that `MaxDrawdown` and `StoplossGuard` actually paused trading at least once.
2. Confirm you understand what the digest is telling you. If you cannot explain
   why a trade closed, do not go live.
3. In Portainer: **Configs → `freqtrade_canada_config` → edit** and set
   `dry_run: false`. (Swarm configs are immutable, so this means recreating the
   config with a new name or a new version and updating the stack reference.)
4. Redeploy the stack.
5. Verify: `curl -H "Authorization: Bearer $TOKEN" $API/api/v1/safety` must show
   `"dry_run": false` and list your protections. The digest will switch from
   "SIMULATION" to "LIVE — real money".

To go back to simulation, reverse step 3. Do that immediately if anything looks
wrong: pausing the bot stops new trades but leaves existing positions managed.

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Freqtrade can't connect to Kraken | Check API key permissions, IP allowlist |
| "Rate limit exceeded" | Increase `rateLimit` in config (3100→5000) |
| Bot runs but places no trades | Check the Kraken key actually loaded — a `*_FILE` env var is silently ignored (see SECRETS.md) |
| AI Orchestrator unhealthy | Check OpenRouter key, model availability |
| Orchestrator returns 503 | `orchestrator_api_token` secret missing — intentional fail-closed |
| Orchestrator returns 401 | Missing/wrong `Authorization: Bearer <token>` header |
| AI stopped mid-day | Free-tier daily budget spent (200/day). Trading unaffected; resets 00:00 UTC |
| Discord notifications not working | Verify webhook URL in secrets |
| Backup failing | Check Nextcloud WebDAV URL, credentials |
| Generated strategy rejected | Read the reason — the validator explains it in plain English via the audit log |

### Debug Commands
```bash
# Check Freqtrade API
curl -u freqtrade:PASS http://localhost:8080/api/v1/status

# Check AI Orchestrator (from inside the swarm network)
docker run --rm -it --network kraken-bot-network curlimages/curl \
  -H "Authorization: Bearer $TOKEN" http://ai_orchestrator:8082/api/v1/safety

# Verify secrets mounted
docker compose exec freqtrade ls /run/secrets/

# Test Kraken connection
docker compose exec freqtrade freqtrade test-pairlist -c /freqtrade/user_data/config/canada_kraken.json
```

---

## 📝 License

MIT License - See LICENSE file

---

## ⚠️ Disclaimer

**This software is for educational and research purposes.**
- Trading cryptocurrencies carries substantial risk
- Past performance ≠ future results
- Never trade more than you can afford to lose
- The AI components are experimental - always review suggestions
- **Autonomous agent is DISABLED by default for safety**

**You are responsible for your own trading decisions.**
---

## 🐳 Portainer Deployment (Production Recommended)

### Prerequisites
- Portainer Business/CE with Agent connected
- GitHub Container Registry (ghcr.io) or Docker Hub for custom images
- Repository secrets configured (see below)

### 1. Configure Repository Secrets (GitHub)
Go to **Repository → Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `PORTAINER_API_URL` | Your Portainer API endpoint (e.g., `https://portainer.yourdomain.com`) |
| `PORTAINER_API_TOKEN` | Portainer API token with Stack write permissions |
| `PORTAINER_STACK_ID` | Stack ID from Portainer URL (after deploying once) |

### 2. Create Portainer Secrets (One-Time)
In Portainer UI → **Secrets → Add Secret** (see [SECRETS.md](SECRETS.md)):
```
kraken_api_key, kraken_api_secret, openrouter_api_key,
freqtrade_api_password, freqtrade_encrypt_key, backup_encrypt_key,
orchestrator_api_token, discord_webhook (optional), nextcloud_* (optional)
```

### 3. Initial Deploy
```bash
# Option A: Via Portainer UI
# Stacks → Add Stack → Name: kraken-ai-bot → Repository → Select this repo → portainer-stack.yml

# Option B: Via Portainer API (after pushing)
curl -X POST "https://portainer.yourdomain.com/api/stacks" \
  -H "Authorization: Bearer $PORTAINER_API_TOKEN" \
  -F "Name=kraken-ai-bot" \
  -F "RepositoryURL=https://github.com/youruser/kraken-ai-bot" \
  -F "RepositoryReference=refs/heads/main" \
  -F "ComposeFile=portainer-stack.yml" \
  -F "Env=[{\"name\":\"GITHUB_REPOSITORY_OWNER\",\"value\":\"youruser\"}]"
```

### 4. Updates (Automatic via GitOps)

| Change Type | Workflow |
|-------------|----------|
| **Config** (`config/*.yaml`) | Push to main → Portainer detects → "Update Stack" |
| **Code** (`ai_orchestrator/`, `backup/`) | Push to main → GitHub Actions builds images → Portainer pulls new tags |
| **Secrets** | Portainer UI → Secrets → Update → "Update Stack" |
| **Freqtrade Version** | Edit `portainer-stack.yml` image tag → Push → "Update Stack" |

### 5. Manual Stack Update
```bash
# Via GitHub Actions (if configured)
gh workflow run portainer-notify.yml -f stack_id=1 -f environment=production

# Via Portainer UI
# Stacks → kraken-ai-bot → Update Stack → Re-pull images and redeploy
```

### 6. Rollback
Portainer UI → Stacks → kraken-ai-bot → **Rollback** → Select version → Confirm

---

## 🔧 Portainer-Specific Configuration

### Environment Variables (in stack)
```yaml
# In portainer-stack.yml, customize per environment:
environment:
  - AI_ORCHESTRATOR_IMAGE=ghcr.io/youruser/kraken-ai-orchestrator:latest
  - BACKUP_IMAGE=ghcr.io/youruser/kraken-backup:latest
```

### Resource Limits (Already Configured)
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1G
  restart_policy:
    condition: on-failure
    delay: 10s
    max_attempts: 3
```

### Health Checks (Portainer Monitors)
- `freqtrade`: `http://localhost:8080/api/v1/ping` (in-container)
- `ai_orchestrator`: `http://localhost:8082/health` (in-container; `/health` is
  the only unauthenticated route, and it returns no configuration)

---

## 📋 Portainer Operations Checklist

### Daily
- [ ] Check stack status (all green)
- [ ] Review Discord notifications
- [ ] Verify backup completed (Nextcloud)

### Weekly
- [ ] Review AI audit log (`GET /api/v1/audit/recent`)
- [ ] Check Freqtrade performance (`GET /api/v1/performance`)
- [ ] Verify dry-run P&L trends

### Monthly
- [ ] Rotate API keys (see SECRETS.md schedule)
- [ ] Review generated strategies (`config/strategies/generated/`)
- [ ] Test backup restore (decrypt + verify)

### Quarterly
- [ ] Full secret rotation
- [ ] Update Freqtrade version
- [ ] Review AI model performance (consider switching models)
- [ ] Audit Portainer access logs
