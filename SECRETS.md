# Portainer Secrets Inventory

**Create these in Portainer UI → Secrets → Add Secret before deploying the stack.**

| Secret Name | Type | Description | Required | Example Value |
|-------------|------|-------------|----------|---------------|
| `kraken_api_key` | Text | Kraken API Public Key | ✅ Yes | `KRAKEN_API_KEY_ABC123...` |
| `kraken_api_secret` | Text | Kraken API Private Key | ✅ Yes | `private_key_base64_encoded...` |
| `openrouter_api_key` | Text | OpenRouter API Key | ✅ Yes | `sk-or-v1-abc123...` |
| `freqtrade_api_password` | Text | Freqtrade REST API Password | ✅ Yes | `openssl rand -base64 32` |
| `freqtrade_encrypt_key` | Text | Freqtrade Config Encryption Key | ✅ Yes | `openssl rand -base64 32` |
| `discord_webhook` | Text | Discord Webhook URL | ❌ Optional | `https://discord.com/api/webhooks/...` |
| `nextcloud_url` | Text | Nextcloud WebDAV Backup URL | ❌ Optional | `https://cloud.example.com/remote.php/dav/files/user/backups` |
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
openssl rand -base64 32  # backup_encrypt_key

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
3. **WebDAV URL format**: `https://your-nextcloud.com/remote.php/dav/files/USERNAME/backups`
   - Replace `USERNAME` with your Nextcloud username
   - `backups` folder will be created automatically
4. Test: `curl -u "username:app_password" "https://your-nextcloud.com/remote.php/dav/files/username/backups/"`

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
`/run/secrets/freqtrade_api_password` and `/run/secrets/discord_webhook`
directly in `main.py`. It never receives Kraken credentials.

**Non-secret config is delivered as Swarm configs** (not bind mounts), because
Portainer's repository mode resolves relative bind paths under
`/data/compose/<id>/`, and Swarm never auto-creates a missing bind-mount source
directory.

| Swarm config | Source file | Mounted at |
|--------------|-------------|------------|
| `freqtrade_base_config` | `config/base.yaml` | `/freqtrade/user_data/base.yaml` |
| `freqtrade_canada_config` | `config/canada_kraken.yaml` | `/freqtrade/user_data/canada_kraken.yaml` |
| `freqtrade_strategy` | `config/strategies/moderate_multi.py` | `/freqtrade/user_data/moderate_multi.py` |
| `freqtrade_entrypoint` | `config/freqtrade-entrypoint.sh` | `/etc/freqtrade-entrypoint.sh` |
| `freqtrade_ai_config` | `config/ai_orchestrator.yaml` | `/app/config/ai_orchestrator.yaml` |

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
| Freqtrade Encrypt Key | Annually | **Warning**: Re-encrypts config. Backup first! |
| Backup Encrypt Key | Annually | Generate new age key → Update secret → Old backups need old key |
| Discord/Nextcloud | As needed | Update when credentials change |

---

## Security Checklist

- [ ] All secrets created in Portainer (not in `.env` or files)
- [ ] Kraken API has IP allowlist enabled
- [ ] Kraken API has **no withdrawal permissions**
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
| Bot runs but has no exchange key | You used a `*_FILE` env var. freqtrade ignores those — use `config/freqtrade-entrypoint.sh` (see "How Secrets Reach the Containers") |
| `bind source path does not exist` | You used a bind mount. Swarm does not create bind sources — use a Swarm config instead |
| `ModuleNotFoundError: ai_orchestrator` | The orchestrator image was built with the wrong context. It must be built from the repo root with `file: ai_orchestrator/Dockerfile` |
| `429` / `EAPI:Rate limit exceeded` from Kraken | Raise `exchange.ccxt_async_config.rateLimit` in `config/canada_kraken.yaml` (default 3500 ms) |
| AI Orchestrator 401 errors | `freqtrade_api_password` mismatch between secrets |
| Portainer shows "ConfigMap not found" | Secret name in stack ≠ secret name in Portainer |