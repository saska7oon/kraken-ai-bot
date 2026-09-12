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
```bash
mkdir -p secrets
chmod 700 secrets

# REQUIRED
echo "YOUR_KRAKEN_API_KEY" > secrets/kraken_api_key.txt
echo "YOUR_KRAKEN_API_SECRET" > secrets/kraken_api_secret.txt
echo "YOUR_OPENROUTER_KEY" > secrets/openrouter_api_key.txt

# Generate secure passwords
openssl rand -base64 32 > secrets/freqtrade_api_password.txt
openssl rand -base64 32 > secrets/freqtrade_encrypt_key.txt
openssl rand -base64 32 > secrets/backup_encrypt_key.txt

# OPTIONAL
echo "https://discord.com/api/webhooks/..." > secrets/discord_webhook.txt
echo "https://cloud.yoursite.com/remote.php/dav/files/user/backups" > secrets/nextcloud_url.txt
echo "your_username" > secrets/nextcloud_user.txt
echo "your_app_password" > secrets/nextcloud_pass.txt

chmod 600 secrets/*
```

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
curl http://localhost:8082/health          # AI Orchestrator
curl -u freqtrade:PASSWORD http://localhost:8081/api/v1/ping  # FreqUI
```

### 6. Access Web UI
Open http://localhost:8081
- Username: `freqtrade`
- Password: (from `secrets/freqtrade_api_password.txt`)

---

## 💬 Natural Language Control

**Talk to your bot via REST API:**

```bash
# Switch risk profile
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Switch to conservative mode"}'

# Add pair to whitelist
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Add DOGE/CAD to whitelist"}'

# Check status
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Show me the last 10 trades with P&L in CAD"}'

# Explain a trade
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Why did the bot sell ETH at 3600 CAD?"}'

# Pause trading
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Pause trading for 2 hours"}'

# Optimize parameters
curl -X POST http://localhost:8082/api/v1/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Optimize parameters for current market conditions"}'
```

**Approval flow:** Commands that change risk/whitelist/strategy return `pending_approval`. Approve with:
```bash
curl -X POST http://localhost:8082/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true, "changes": [...]}'
```

---

## 🤖 AI Plugins (All Optional)

| Plugin | Schedule | Description |
|--------|----------|-------------|
| **strategy_generator** | Weekly (Sun 2AM) | Generates new strategies via LLM |
| **market_analyst** | Every 15 min | Technical + sentiment analysis |
| **param_optimizer** | Every 6 hours | Suggests hyperparameter tweaks |
| **nl_config** | On-demand | Natural language → config |
| **autonomous_agent** | **DISABLED** | Direct AI trading (opt-in only) |

Enable/disable via config or API:
```bash
curl -X POST http://localhost:8082/api/v1/plugins/strategy_generator/control \
  -H "Content-Type: application/json" \
  -d '{"action": "disable"}'
```

---

## 🔐 Security Model

### Credential Isolation
```
┌─────────────────────────────────────────────────────────────┐
│                    DOCKER SECRETS                            │
├─────────────────────────────────────────────────────────────┤
│  kraken_api_key       → Only Freqtrade container             │
│  kraken_api_secret    → Only Freqtrade container             │
│  openrouter_api_key   → Only AI Orchestrator                 │
│  freqtrade_api_password → Freqtrade + AI Orchestrator        │
│  discord_webhook      → Freqtrade + AI Orchestrator          │
│  nextcloud_*          → Only Backup sidecar                  │
│  backup_encrypt_key   → Only Backup sidecar                  │
└─────────────────────────────────────────────────────────────┘
```

### Key Principles
- ✅ **No credentials in images, configs, logs, or environment**
- ✅ **AI Orchestrator NEVER sees Kraken keys** - only talks to Freqtrade REST API
- ✅ **All secrets mounted as files at `/run/secrets/`**
- ✅ **Audit log tracks every AI action with hash chaining**
- ✅ **Human approval required for all config changes**

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
│   ├── base.yaml              # Freqtrade base config
│   ├── canada_kraken.yaml     # Canada-specific overrides
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
1. Verify dry-run performance for 1-2 weeks
2. Edit `config/canada_kraken.yaml`: `dry_run: false`
3. `docker compose restart freqtrade freqtrade_ui`

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Freqtrade can't connect to Kraken | Check API key permissions, IP allowlist |
| "Rate limit exceeded" | Increase `rateLimit` in config (3100→5000) |
| AI Orchestrator unhealthy | Check OpenRouter key, model availability |
| Discord notifications not working | Verify webhook URL in secrets |
| Backup failing | Check Nextcloud WebDAV URL, credentials |

### Debug Commands
```bash
# Check Freqtrade API
curl -u freqtrade:PASS http://localhost:8080/api/v1/status

# Check AI Orchestrator
curl http://localhost:8082/health

# Verify secrets mounted
docker compose exec freqtrade ls /run/secrets/

# Test Kraken connection
docker compose exec freqtrade freqtrade test-pairlist -c /freqtrade/user_data/config/canada_kraken.yaml
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
discord_webhook (optional), nextcloud_* (optional)
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
- `freqtrade`: `http://localhost:8080/api/v1/ping`
- `freqtrade_ui`: `http://localhost:8081/api/v1/ping`
- `ai_orchestrator`: `http://localhost:8082/health`

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
