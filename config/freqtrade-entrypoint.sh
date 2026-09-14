#!/bin/bash
# =============================================================================
# Freqtrade entrypoint for Docker Swarm secrets
# =============================================================================
# Freqtrade reads credentials from its configuration, and it does NOT support
# the "*_FILE" environment-variable convention (the only env-var override
# mechanism is FREQTRADE__SECTION__KEY with the literal value). So a Swarm
# secret mounted at /run/secrets/kraken_api_key is invisible to freqtrade
# unless something reads that file and turns it into configuration.
#
# This script does exactly that: it reads the secret FILES and writes a single
# ephemeral private config. Nothing is ever written to disk and no secret is
# ever placed in an environment variable:
#
#   /run/secrets/*  (Swarm secret, tmpfs, mode 0444)
#        -> read directly by this script
#        -> /dev/shm/freqtrade-private.json  (RAM only, mode 0600)
#        -> passed to freqtrade via --config
#
# The generated file lives in tmpfs, so it disappears when the container stops
# and is never written to the container filesystem or a mounted volume.
#
# Mount this file into the container via a Swarm *config* (not a secret - it
# contains no secret material) and override the image entrypoint:
#
#   entrypoint: ["/bin/bash", "/etc/freqtrade-entrypoint.sh"]
# =============================================================================

set -euo pipefail

SECRET_DIR="${SECRET_DIR:-/run/secrets}"
PRIVATE_CFG="${PRIVATE_CFG:-/dev/shm/freqtrade-private.json}"

log() {
    echo "[entrypoint] $*"
}

# Returns success when a secret file exists and has non-whitespace content.
# Never echoes the value, so nothing leaks into logs or the process env.
has_secret() {
    local name="$1"
    [ -f "${SECRET_DIR}/${name}" ] || return 1
    [ -n "$(tr -d '\r\n' < "${SECRET_DIR}/${name}")" ]
}

# ---------------------------------------------------------------------------
# 1. Validate required secrets (fail fast rather than trade without keys)
# ---------------------------------------------------------------------------
missing=0
for required in kraken_api_key kraken_api_secret freqtrade_api_password; do
    if has_secret "$required"; then
        log "secret present: ${required}"
    else
        log "ERROR: required secret '${required}' is missing or empty in ${SECRET_DIR}"
        missing=1
    fi
done

if [ "$missing" -ne 0 ]; then
    log "Aborting: required Swarm secrets are not available to this container."
    log "Check that the service declares them under 'secrets:' in the stack."
    exit 1
fi

if ! has_secret freqtrade_encrypt_key; then
    log "WARNING: 'freqtrade_encrypt_key' missing - reusing api password for JWT/ws token"
fi

if ! has_secret discord_webhook; then
    log "WARNING: 'discord_webhook' missing - Discord notifications will not work"
fi

# ---------------------------------------------------------------------------
# 2. Pick an ephemeral location for the generated private config
# ---------------------------------------------------------------------------
if ! ( : > "$PRIVATE_CFG" ) 2>/dev/null; then
    PRIVATE_CFG="/tmp/freqtrade-private.json"
    log "WARNING: ${PRIVATE_CFG} not writable, falling back to ${PRIVATE_CFG}"
fi

# ---------------------------------------------------------------------------
# 3. Generate the private config from the secret files.
#    Python reads the files itself - no secret is passed through the environment.
# ---------------------------------------------------------------------------
SECRET_DIR="$SECRET_DIR" PRIVATE_CFG="$PRIVATE_CFG" python3 - <<'PY'
import json
import os
import sys

secret_dir = os.environ["SECRET_DIR"]
private_cfg = os.environ["PRIVATE_CFG"]


def read_secret(name: str) -> str:
    try:
        with open(os.path.join(secret_dir, name), "r") as fh:
            return fh.read().strip()
    except FileNotFoundError:
        return ""


api_password = read_secret("freqtrade_api_password")

cfg = {
    "exchange": {
        "key": read_secret("kraken_api_key"),
        "secret": read_secret("kraken_api_secret"),
    },
    "api_server": {
        "username": "freqtrade",
        "password": api_password,
    },
    # jwt_secret_key / ws_token authenticate FreqUI and the websocket.
    "jwt_secret_key": read_secret("freqtrade_encrypt_key") or api_password,
    "ws_token": read_secret("freqtrade_encrypt_key") or api_password,
}

webhook = read_secret("discord_webhook")
if webhook:
    cfg["discord"] = {"webhook_url": webhook}

# Write with 0600. fchmod is applied explicitly because the O_CREAT mode is
# ignored when the file already exists (the shell probe above creates it).
fd = os.open(private_cfg, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w") as fh:
    json.dump(cfg, fh, indent=2)

sys.stdout.write("[entrypoint] generated private config at %s\n" % private_cfg)
PY

# ---------------------------------------------------------------------------
# 4. Make sure the freqtrade user can write the database and log directory.
#    Swarm creates named-volume mount points as root, but the freqtrade image
#    runs as an unprivileged user (ftuser, uid 1000).
# ---------------------------------------------------------------------------
CURRENT_UID="$(id -u)"
CURRENT_GID="$(id -g)"

sudo -n /bin/chown -R "${CURRENT_UID}:${CURRENT_GID}" /freqtrade/user_data 2>/dev/null \
    || chown -R "${CURRENT_UID}:${CURRENT_GID}" /freqtrade/user_data 2>/dev/null \
    || true

# ---------------------------------------------------------------------------
# 5. Stage strategies into the shared strategies volume.
#
#    The shared volume 'strategies_shared' is mounted here as
#    /freqtrade/user_data/strategies and into the AI orchestrator as
#    /app/strategies. Two consequences:
#
#      * AI-proposed strategies appear where freqtrade can backtest them, which
#        is what lets a proposal be tested before anyone is asked to approve it.
#      * The operator's strategy lives in a read-only Swarm config, so it is
#        copied in fresh on every start. cp -f overwrites the staged copy but
#        leaves AI proposals (proposal_*.py) alone.
# ---------------------------------------------------------------------------
STRATEGY_DIR="/freqtrade/user_data/strategies"
mkdir -p "${STRATEGY_DIR}"

if [ -d /etc/freqtrade-strategies ]; then
    for strategy in /etc/freqtrade-strategies/*.py; do
        [ -e "${strategy}" ] || continue
        cp -f "${strategy}" "${STRATEGY_DIR}/" \
            && log "staged strategy: $(basename "${strategy}")" \
            || error "failed to stage strategy $(basename "${strategy}")"
    done
fi

# The orchestrator writes proposals into the same volume as uid 1000, so the
# directory must be writable by the freqtrade user.
chmod 0775 "${STRATEGY_DIR}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 6. Hand over to freqtrade (command from the stack becomes "$@")
# ---------------------------------------------------------------------------
log "starting: freqtrade $*"
exec freqtrade "$@"
