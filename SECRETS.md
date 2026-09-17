# Portainer Secrets Inventory

**Create these in Portainer UI → Secrets → Add Secret before deploying the stack.**

| Secret Name | Type | Description | Required | Example Value |
|-------------|------|-------------|----------|---------------|
| `kraken_api_key` | Text | Kraken API Public Key | ✅ Yes | `KRAKEN_API_KEY_ABC123...` |
| `kraken_api_secret` | Text | Kraken API Private Key | ✅ Yes | `private_key_base64_encoded...` |
| `openrouter_api_key` | Text | OpenRouter API Key | ✅ Yes | `sk-or-v1-abc123...` |
| `freqtrade_api_password` | Text | Freqtrade REST API Password | ✅ Yes | `openssl rand -base64 32` |
| `freqtrade_encrypt_key` | Text | Freqtrade Config Encryption Key | ✅ Yes | `openssl rand -base64 32` |
| `orchestrator_api_token` | Text | Bearer token for the AI orchestrator API | ✅ Yes | `openssl rand -base64 48` |
| `discord_webhook` | Text | Discord Webhook URL | ❌ Optional | `https://discord.com/api/webhooks/...` |
| `nextcloud_url` | Text | Nextcloud WebDAV URL — the **account root**, not a backups folder | ❌ Optional | `https://cloud.example.com/remote.php/dav/files/user` |
| `nextcloud_user` | Text | Nextcloud Username | ❌ Optional | `backupuser` |
| `nextcloud_pass` | Text | Nextcloud App Password | ❌ Optional | `app_password_xyz` |
| `backup_encrypt_key` | Text | Age Encryption Public Key | ✅ Yes* | `age1abc123...` |

*Required if backup service is enabled (it is by default).

---

## Quick Setup Commands

Run on your local machine to generate secure values:

```bash
# Generate all required random secrets
openssl rand -base64 32  # freqtrade_api_password
openssl rand -base64 32  # freqtrade_encrypt_key
openssl rand -base64 48  # orchestrator_api_token
openssl rand -base64 32  # backup_encrypt_key (only if not using age-keygen below)

# For Age encryption key (backup):
# Install age: brew install age / apt install age / apk add age
age-keygen -o age_keys.txt
# Public key (put in backup_encrypt_key):
grep "public key:" age_keys.txt | awk '{print $3}'
# Private key (KEEP OFFLINE for restores):
grep "private key:" age_keys.txt | awk '{print $3}'
```

---

## Creating Secrets in Portainer

1. Navigate to **Secrets** in Portainer UI
2. Click **Add Secret**
3. For each secret:
   - **Name**: Exact name from table above (e.g., `kraken_api_key`)
   - **Value**: Paste the secret value
   - **Driver**: `Internal` (default)
4. Click **Create**

---

## Kraken API Key Setup

1. Log into [Kraken Pro](https://pro.kraken.com)
2. **Settings → API → Generate New Key**
3. **Permissions** (enable only these):
   - ✅ Query Funds
   - ✅ Query Open Orders & Trades
   - ✅ Query Closed Orders & Trades
   - ✅ Create & Modify Orders
   - ✅ Cancel Orders
   - ❌ Withdraw Funds (NEVER)
   - ❌ Deposit Funds
4. **IP Allowlist**: Add your server's public IP (highly recommended)
5. **Copy both Key and Private Key** immediately (Private Key shown once)

---

## OpenRouter API Key

1. Go to [OpenRouter](https://openrouter.ai/keys)
2. Create new key
3. **Free tier**: 20 requests/minute, 200 requests/day
4. Model `nvidia/nemotron-3-ultra-550b-a55b:free` is free

---

## Discord Webhook (Optional)

1. Server Settings → Integrations → Webhooks → New Webhook
2. Channel: `#trading-bot` (or your choice)
3. Copy Webhook URL
4. Paste as `discord_webhook` secret

---

## Nextcloud Backup (Optional)

1. **Nextcloud** → Settings → Security → Devices & Sessions → App Passwords
2. Create app password: `kraken-bot-backup`
3. **WebDAV URL format**: `https://your-nextcloud.com/remote.php/dav/files/USERNAME`

   Point this at your **account root**. Do not append `/backups`: the backup
   sidecar creates `backups/daily` underneath whatever you give it, so a URL
   ending in `/backups` produces `.../backups/backups/daily`. That folder is
   wrong, surprising, and — because Nextcloud answers a bad WebDAV path with
   "directory not found" — looks exactly like a credentials failure when it is
   not one.
   - Replace `USERNAME` with your Nextcloud username
   - `backups` folder will be created automatically
4. Test: `curl -u "username:app_password" "https://your-nextcloud.com/remote.php/dav/files/username/"`
   A `207 Multi-Status` reply means the URL and app password are both right.

---

## Environment-Specific Secrets

| Environment | Secret Suffix | Example |
|-------------|---------------|---------|
| Development | `_dev` | `kraken_api_key_dev` |
| Staging | `_staging` | `kraken_api_key_staging` |
| Production | (none) | `kraken_api_key` |

**Stack modification needed**: Update `portainer-stack.yml` secret `name:` fields per environment.

---

## How Secrets Reach the Containers

Secrets are **Swarm secrets** and are mounted read-only at `/run/secrets/<name>`.

**Important:** freqtrade does **not** support the `*_FILE` environment-variable
convention. `FREQTRADE__EXCHANGE__API_KEY_FILE=/run/secrets/kraken_api_key`
would be interpreted as the (invalid) config key `exchange.api_key_file` and
silently ignored — the API key would never load. Freqtrade's only env-var
override mechanism is `FREQTRADE__SECTION__KEY` with the literal value, which
would put the secret into the container's environment.

Instead, `config/freqtrade-entrypoint.sh` (deployed as the Swarm **config**
`freqtrade_entrypoint`, mounted at `/etc/freqtrade-entrypoint.sh`) reads the
secret *files* and writes a single private config:

```
/run/secrets/{kraken_api_key,kraken_api_secret,freqtrade_api_password,
              freqtrade_encrypt_key,discord_webhook}   (Swarm secret, mode 0444)
        |
        v  read by /etc/freqtrade-entrypoint.sh
/dev/shm/freqtrade-private.json                        (tmpfs, RAM only, mode 0600)
        |
        v  passed as the last --config (highest precedence)
freqtrade
```

Consequences:

- No secret is ever written to disk, a bind mount, a volume, or a `.env` file.
- No secret is ever placed in an environment variable.
- The private config disappears when the container stops.
- `docker inspect` on the task shows only the env vars listed in the stack,
  which never contain credentials.

The AI orchestrator reads `/run/secrets/openrouter_api_key`,
`/run/secrets/freqtrade_api_password`, `/run/secrets/discord_webhook` and
`/run/secrets/orchestrator_api_token` directly in `main.py`. It never receives
Kraken credentials.

**Non-secret config is delivered as Swarm configs** (not bind mounts), because
Portainer's repository mode resolves relative bind paths under
`/data/compose/<id>/`, and Swarm never auto-creates a missing bind-mount source
directory.

| Swarm config | Source file | Mounted at |
|--------------|-------------|------------|
| `freqtrade_base_config` | `config/base.json` | `/freqtrade/user_data/base.json` |
| `freqtrade_canada_config` | `config/canada_kraken.json` | `/freqtrade/user_data/canada_kraken.json` |
| `freqtrade_strategy` | `config/strategies/moderate_multi.py` | `/etc/freqtrade-strategies/moderate_multi.py` |
| `freqtrade_entrypoint` | `config/freqtrade-entrypoint.sh` | `/etc/freqtrade-entrypoint.sh` |
| `freqtrade_ai_config` | `config/ai_orchestrator.yaml` | `/app/config/ai_orchestrator.yaml` |

> The strategy is staged to `/etc/freqtrade-strategies/` rather than directly
> into the strategies directory, because Swarm configs are **read-only** and
> freqtrade needs a writable strategies directory (see below). The entrypoint
> copies it into place on every start.

### The shared strategies volume

`strategies_shared` (Docker volume `kraken-strategies-shared`) is mounted at:

| Container | Path |
|-----------|------|
| `freqtrade` | `/freqtrade/user_data/strategies` |
| `ai_orchestrator` | `/app/strategies` |

This is what allows a proposed strategy to be **backtested before the operator
is asked to approve it**. The orchestrator writes candidates there; freqtrade
reads them and runs the backtest over the REST API.

AI proposals are named `proposal_<timestamp>_<name>.py`, so they can never
overwrite or shadow `moderate_multi.py`. Both containers run as uid 1000, so
file ownership is consistent. **Activating** a proposed strategy still means
editing the Swarm config and redeploying — that is intentionally outside the
AI's reach.

---

## Orchestrator API Authentication

The AI orchestrator's HTTP API is authenticated with a **bearer token** read from
the `orchestrator_api_token` Swarm secret.

```
Orchestrator routes
-------------------
/health                  -> public (liveness probe; reveals nothing)
everything under         -> require "Authorization: Bearer <token>"
  /api/v1/...
```

If `orchestrator_api_token` does not exist, the service **fails closed**: every
authenticated route returns `503` with an explanation, and it logs a
`SECURITY:` line at startup. It will not run open by accident.

Create it with:

```bash
openssl rand -base64 48
```

and store the output as the `orchestrator_api_token` Swarm secret. Then:

```bash
curl -H "Authorization: Bearer <token>" http://<host>:8082/api/v1/status
```

The orchestrator port **is published on the host** as `8082`, so the operator UI
is reachable at `http://<pi-ip>:8082` and the API at the same address.

It used to be unpublished, because the approval endpoint would apply a change
list supplied in the request body — so anything that could reach the host could
approve changes that were never proposed. That is fixed: approval now requires a
`proposal_id` this process issued, is single-use, expires after 30 minutes, and
is re-validated before anything is applied. Every route except `/health` and the
static UI page still requires the bearer token.

On a local network that is a reasonable trade. If the Pi is ever reachable from
outside your LAN, put it behind a VPN or a TLS reverse proxy rather than relying
on the token alone. To go back to tunnel-only access, remove the `ports:` entry
from the `ai-orchestrator` service and tunnel in:

```bash
ssh -L 8082:localhost:8082 <user>@<pi-host>
```

Or reach it from inside the swarm network without publishing anything:

```bash
docker run --rm -it --network kraken-bot-network curlimages/curl \
  -H "Authorization: Bearer <token>" http://ai_orchestrator:8082/api/v1/status
```

### What the token does and does not gate

| Action | Requires token | Requires a second human step |
|--------|----------------|------------------------------|
| Read status, trades, performance | yes | no |
| Pause / resume trading | yes | no |
| Restrict traded pairs (runtime) | yes | no |
| Propose a configuration change | yes | **yes** — edit the Swarm config |
| Apply a configuration change | — | **not possible via the API** |
| Switch dry-run to live | — | **not possible via the API** |
| Enable autonomous AI trading | — | **yes** — edit `ai_orchestrator.yaml` |

Configuration changes can only be *proposed* and *approved*. Applying one means
editing the relevant Swarm config and redeploying, so no API token — or bug in
the API — can silently reconfigure the bot.


> When you change any of these files, update the corresponding Portainer config
> and redeploy the stack. Swarm configs are immutable — edit the config (or
> delete and recreate it) rather than expecting the file to update in place.

---

## Secret Rotation Schedule

| Secret | Frequency | Procedure |
|--------|-----------|-----------|
| Kraken API | Quarterly | 1. Generate new on Kraken 2. Update Portainer secret 3. Redeploy stack |
| OpenRouter | Quarterly | Same as above |
| Freqtrade API Password | Semi-annually | Generate new → Update secret → Redeploy |
| Orchestrator API Token | Semi-annually | Generate new → Update secret → Redeploy → Update any saved client configs |
| Freqtrade Encrypt Key | Annually | **Warning**: Re-encrypts config. Backup first! |
| Backup Encrypt Key | Annually | Generate new age key → Update secret → Old backups need old key |
| Discord/Nextcloud | As needed | Update when credentials change |

---

## Security Checklist

- [ ] All secrets created in Portainer (not in `.env` or files)
- [ ] Kraken API has IP allowlist enabled
- [ ] Kraken API has **no withdrawal permissions**
- [ ] `orchestrator_api_token` created and set to a random value
- [ ] Orchestrator port is **not** published to the host
- [ ] Nextcloud uses app password (not main password)
- [ ] Age private key stored offline (password manager, USB, paper)
- [ ] Secrets not logged in any CI/CD output
- [ ] Portainer audit logging enabled
- [ ] Access to Portainer Secrets limited to admins

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Secret not found" on deploy | Verify exact name match in Portainer Secrets |
| Backup fails authentication | Check Nextcloud app password + WebDAV URL format |
| `rclone ... directory not found` on upload | The WebDAV URL is wrong, not the password. It must be the **account root** (`.../dav/files/USERNAME`), with no `/backups` suffix. Nextcloud reports a bad path as "directory not found", which reads like a credentials error. The sidecar logs `WebDAV target:` with the account name masked to `...` so you can see which path it is actually using |
| Bot runs but has no exchange key | You used a `*_FILE` env var. freqtrade ignores those — use `config/freqtrade-entrypoint.sh` (see "How Secrets Reach the Containers") |
| `bind source path does not exist` | You used a bind mount. Swarm does not create bind sources — use a Swarm config instead |
| `ModuleNotFoundError: ai_orchestrator` | The orchestrator image was built with the wrong context. It must be built from the repo root with `file: ai_orchestrator/Dockerfile` |
| Orchestrator returns `503` on every route | `orchestrator_api_token` is missing. This is intentional fail-closed behaviour — create the secret and redeploy (see "Orchestrator API Authentication") |
| Orchestrator returns `401` | Missing or wrong `Authorization: Bearer <token>` header |
| `429` / `EAPI:Rate limit exceeded` from Kraken | Raise `exchange.ccxt_async_config.rateLimit` in `config/canada_kraken.json` (default 3500 ms) |
| AI features stop mid-day | OpenRouter free-tier daily budget (200/day) is spent. The bot keeps trading; AI resumes at 00:00 UTC. Check `/api/v1/explain/digest` for the remaining count |
| `freqtrade_strategy` config not visible in the strategies dir | Expected — it is staged at `/etc/freqtrade-strategies/` and copied in by the entrypoint, because Swarm configs are read-only |
| AI Orchestrator 401 errors | `freqtrade_api_password` mismatch between secrets |
| Portainer shows "ConfigMap not found" | Secret name in stack ≠ secret name in Portainer |