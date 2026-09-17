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
# 1. Validate secrets (fail fast rather than trade without keys)
#
#    Required secrets are fatal when absent: a bot with no Kraken keys cannot
#    trade, so it is better to stop immediately and say so.
#
#    Optional secrets are reported for BOTH presence and absence. An earlier
#    version printed "secret present" only for the required three and stayed
#    silent when an optional secret was found, so the log for a healthy Discord
#    setup was identical to the log for a missing one - you could only tell the
#    difference by the absence of a warning. That is a bad log. Every secret the
#    container is given is now named explicitly, and the resulting notification
#    state is stated outright at the end.
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

DISCORD_ENABLED=0

if has_secret freqtrade_encrypt_key; then
    log "secret present: freqtrade_encrypt_key (optional)"
else
    log "WARNING: 'freqtrade_encrypt_key' missing - reusing the api password for JWT/ws token"
fi

if has_secret discord_webhook; then
    log "secret present: discord_webhook (optional)"
    DISCORD_ENABLED=1
else
    log "WARNING: 'discord_webhook' missing - Discord notifications are DISABLED"
    log "         (the bot will still start; add the secret and redeploy to enable)"
fi

# State the outcome outright, so nobody has to infer it from a missing line.
if [ "$DISCORD_ENABLED" = "1" ]; then
    log "Discord notifications: ENABLED"
else
    log "Discord notifications: DISABLED (no webhook_url available)"
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
encrypt_key = read_secret("freqtrade_encrypt_key") or api_password


def jwt_key_from(secret: str) -> str:
    """Return a jwt_secret_key that satisfies the schema's 32-character minimum.

    freqtrade's config schema declares api_server.jwt_secret_key with
    minLength 32, so a shorter secret fails config validation and the bot will
    not start. Repeating the secret is enough to satisfy the length rule, but it
    adds NO entropy - an 8-character secret repeated four times is still an
    8-character secret to anyone attacking it. So this is a compatibility shim,
    not a security measure, and it says so out loud rather than quietly making a
    weak key look strong.
    """
    if not secret:
        # Both secrets were empty. The required-secret check upstream should
        # already have aborted, but never emit an empty signing key.
        import secrets as _secrets

        sys.stderr.write(
            "[entrypoint] WARNING: no encrypt key or api password available; "
            "generated a random jwt_secret_key. Sessions will not survive a "
            "restart.\n"
        )
        return _secrets.token_urlsafe(48)

    if len(secret) < 32:
        sys.stderr.write(
            "[entrypoint] WARNING: freqtrade_encrypt_key is only %d characters, "
            "but freqtrade requires at least 32 for api_server.jwt_secret_key. "
            "It has been repeated to satisfy the schema, which does NOT make it "
            "stronger - please replace the secret with a longer random value.\n"
            % len(secret)
        )
        repeats = (32 // len(secret)) + 1
        return (secret * repeats)[:64]

    return secret[:64]


cfg = {
    "exchange": {
        "key": read_secret("kraken_api_key"),
        "secret": read_secret("kraken_api_secret"),
    },
    # jwt_secret_key and ws_token live INSIDE api_server, not at the top level.
    # freqtrade reads them from the api_server section:
    #
    #     api_auth.py:  secret_jwt_key = api_config["jwt_secret_key"]
    #                   api_config = config["api_server"]
    #
    # and the config schema lists jwt_secret_key under api_server's required
    # keys. A top-level jwt_secret_key therefore does both wrong things at once:
    # it fails schema validation during startup, and it leaves
    # api_config["jwt_secret_key"] to raise KeyError when FreqUI or the
    # orchestrator authenticates.
    "api_server": {
        "username": "freqtrade",
        "password": api_password,
        "jwt_secret_key": jwt_key_from(encrypt_key),
        "ws_token": encrypt_key,
    },
}

webhook = read_secret("discord_webhook")
if webhook:
    cfg["discord"] = {"webhook_url": webhook}
else:
    # Fail safe. The base config sets discord.enabled = true, and freqtrade's
    # RPC manager instantiates Discord whenever that flag is set:
    #
    #     if config.get("discord", {}).get("enabled", False):
    #         self.registered_modules.append(Discord(self._rpc, config))
    #
    # Discord.__init__ then does an unguarded lookup:
    #
    #     self._url = config["discord"]["webhook_url"]
    #
    # so an enabled Discord with no webhook_url raises KeyError and kills the
    # bot at startup. Since this private config is merged last, it has the
    # highest precedence, so explicitly disabling Discord here overrides the
    # config file and the bot starts without notifications instead of not
    # starting at all. Notifications are optional; trading is not.
    cfg["discord"] = {"enabled": False}

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
# 4b. Ensure the operator settings file exists.
#
#     The stack passes /freqtrade/user_data/runtime/runtime_settings.json as the
#     LAST --config, so it overrides the read-only Swarm configs. Freqtrade
#     raises OperationalException('File "<path>" not found!') for a missing
#     --config file, so this file must exist even when the operator has never
#     opened the settings page.
#
#     Seeded as {} rather than with a copy of the effective settings. An empty
#     object means "nothing overridden", so the Swarm configs stay in charge and
#     there is exactly one source of truth for every value until the operator
#     deliberately changes one. Seeding it with real values would create a second
#     copy that could drift, and a drifted copy of `dry_run` is the specific bug
#     that put simulated and real trades in one database.
#
#     Never overwritten if it already exists - that would discard the operator's
#     settings on every restart.
# ---------------------------------------------------------------------------
SETTINGS_DIR="/freqtrade/user_data/runtime"
SETTINGS_FILE="${SETTINGS_DIR}/runtime_settings.json"

mkdir -p "${SETTINGS_DIR}" 2>/dev/null || true

if [ ! -f "${SETTINGS_FILE}" ]; then
    printf '{}\n' > "${SETTINGS_FILE}" 2>/dev/null || true
    echo "[entrypoint] created empty operator settings at ${SETTINGS_FILE}"
else
    echo "[entrypoint] operator settings present at ${SETTINGS_FILE}"
fi

# A malformed settings file would stop freqtrade from starting at all, and the
# operator would have no way to fix it from the UI. Validate, and fall back to
# empty with the bad file kept aside for inspection.
if [ -f "${SETTINGS_FILE}" ] && ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "${SETTINGS_FILE}" 2>/dev/null; then
    echo "[entrypoint] WARNING: operator settings file is not valid JSON."
    echo "[entrypoint] Moving it aside to ${SETTINGS_FILE}.broken and starting with defaults."
    mv -f "${SETTINGS_FILE}" "${SETTINGS_FILE}.broken" 2>/dev/null || true
    printf '{}\n' > "${SETTINGS_FILE}" 2>/dev/null || true
fi

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
# 6. Sanitise the mounted configs.
#
#    Freqtrade parses every config file with rapidjson - see
#    freqtrade/configuration/load_config.py. There is no YAML support, and the
#    file extension is ignored entirely. rapidjson reports failures as
#    "Parse error at offset N: <message>", which freqtrade then presents as
#    "please verify the following segment of your configuration" - often
#    pointing at a line that looks completely correct.
#
#    These files are authored in Portainer's web editor, and pasting through a
#    browser or word processor routinely introduces characters that are
#    invisible on screen but fatal to the parser:
#
#      * a UTF-8 BOM (\xef\xbb\xbf) at byte 0 - fails at offset 0 while the
#        reported line looks fine;
#      * "smart" quotes (U+201C/U+201D/U+2018/U+2019) instead of straight
#        quotes - the cause documented in freqtrade/freqtrade#3244;
#      * non-breaking spaces (U+00A0) instead of ordinary spaces;
#      * CRLF line endings, which rapidjson tolerates but which are normalised
#        here for consistency.
#
#    Rather than making the operator hunt for an invisible byte, normalise the
#    files into tmpfs and hand freqtrade the clean copies. Anything changed is
#    logged loudly, because a silently rewritten config would be worse than a
#    loud one.
#
#    This does NOT make an invalid config valid: it only removes characters
#    that cannot be seen. A config written in YAML syntax is still rejected,
#    correctly, because freqtrade cannot read YAML.
# ---------------------------------------------------------------------------
sanitise_config() {
    local src="$1"
    local dst="$2"

    python3 - "$src" "$dst" <<'PY'
import sys

src, dst = sys.argv[1], sys.argv[2]

with open(src, "rb") as fh:
    raw = fh.read()

original = raw
problems = []

# Byte-level fixes first.
if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]
    problems.append("UTF-8 BOM at start of file")
if b"\r\n" in raw:
    raw = raw.replace(b"\r\n", b"\n")
    problems.append("CRLF line endings")

try:
    text = raw.decode("utf-8")
except UnicodeDecodeError as exc:
    sys.stderr.write(
        "[entrypoint] ERROR: %s is not valid UTF-8 (%s). It cannot be repaired "
        "automatically - re-create this config in Portainer by pasting plain "
        "text.\n" % (src, exc)
    )
    sys.exit(1)

# Character-level fixes: the "smart punctuation" family.
replacements = {
    "\u201c": '"', "\u201d": '"',   # curly double quotes
    "\u2018": "'", "\u2019": "'",   # curly single quotes
    "\u00a0": " ",                  # non-breaking space
    "\u2007": " ", "\u202f": " ",   # other exotic spaces
    "\u2013": "-", "\u2014": "-",   # en/em dash
    "\ufeff": "",                   # stray BOM mid-file
    "\u200b": "",                   # zero-width space
}
for bad, good in replacements.items():
    if bad in text:
        text = text.replace(bad, good)
        problems.append(
            "U+%04X (%s)" % (ord(bad), repr(bad)[1:-1] or "zero-width")
        )

with open(dst, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(text)

if problems:
    sys.stderr.write(
        "[entrypoint] WARNING: %s contained invisible or non-ASCII characters "
        "that would have broken freqtrade's config parser. A cleaned copy was "
        "written to %s.\n" % (src, dst)
    )
    for problem in problems:
        sys.stderr.write("[entrypoint]   - repaired: %s\n" % problem)
    sys.stderr.write(
        "[entrypoint]   The config in Portainer is still wrong - this fix is "
        "applied at every start. Please re-paste it as plain text.\n"
    )
else:
    sys.stdout.write("[entrypoint] config clean: %s\n" % src)
PY
}

SANITISED_ARGS=()
for arg in "$@"; do
    case "${arg}" in
        # Skip anything already in tmpfs: that is our own generated private
        # config, which is written clean by this script.
        /dev/shm/*)
            SANITISED_ARGS+=("${arg}")
            ;;
        # Catch the single most confusing freqtrade misconfiguration: configs
        # written in YAML. Freqtrade has no YAML support and ignores the file
        # extension, so it parses the file as JSON and fails with an error
        # pointing at the first line - which is almost always a comment that
        # looks perfectly valid. Say so plainly instead of letting the operator
        # decode "Parse error at offset 0: Invalid value."
        *.yaml|*.yml)
            echo "[entrypoint] ERROR: ${arg} has a YAML extension, but freqtrade" >&2
            echo "[entrypoint]   parses every config file as JSON (rapidjson) and" >&2
            echo "[entrypoint]   ignores the file extension. YAML is not supported:" >&2
            echo "[entrypoint]   '#' comments and 'key: value' syntax are invalid." >&2
            echo "[entrypoint]   Convert this file to JSON. Comments must be // or" >&2
            echo "[entrypoint]   /* */, and freqtrade will fail to start until it is." >&2
            if [ -f "${arg}" ]; then
                out="/dev/shm/config-$(basename "${arg}")"
                if sanitise_config "${arg}" "${out}"; then
                    SANITISED_ARGS+=("${out}")
                else
                    SANITISED_ARGS+=("${arg}")
                fi
            else
                SANITISED_ARGS+=("${arg}")
            fi
            ;;
        *.json)
            if [ -f "${arg}" ]; then
                out="/dev/shm/config-$(basename "${arg}")"
                if sanitise_config "${arg}" "${out}"; then
                    SANITISED_ARGS+=("${out}")
                else
                    # Repair failed; fall back to the original so the operator
                    # sees freqtrade's own error rather than silence.
                    SANITISED_ARGS+=("${arg}")
                fi
            else
                SANITISED_ARGS+=("${arg}")
            fi
            ;;
        *)
            SANITISED_ARGS+=("${arg}")
            ;;
    esac
done
set -- "${SANITISED_ARGS[@]}"

# ---------------------------------------------------------------------------
# 7. Hand over to freqtrade (command from the stack becomes "$@")
# ---------------------------------------------------------------------------
log "starting: freqtrade $*"
exec freqtrade "$@"
