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
| Freqtrade can't decrypt config | `freqtrade_encrypt_key` mismatch — restore from backup |
| AI Orchestrator 401 errors | `freqtrade_api_password` mismatch between secrets |
| Portainer shows "ConfigMap not found" | Secret name in stack ≠ secret name in Portainer |