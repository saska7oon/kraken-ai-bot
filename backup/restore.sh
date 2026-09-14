#!/bin/bash
# Restore tool - downloads an encrypted backup from Nextcloud (WebDAV) or a
# local path, verifies it, decrypts it with the age PRIVATE key, extracts it and
# checks the restored SQLite databases.
#
# Usage:
#   restore.sh --list
#   restore.sh --archive <name|path> --dest <dir> [--identity <file>] [--force]
#   restore.sh --latest --dest <dir> [--identity <file>] [--force]
#
# Options:
#   --list                 list available archives (size + date) and exit
#   --archive <name|path>  restore this archive (remote name, or a local file)
#   --latest               restore the most recent archive found
#   --dest <dir>           where to extract (created if missing)
#   --identity <file>      age private key (default: $BACKUP_AGE_IDENTITY_FILE)
#   --remote <rclone:path> remote backup directory (default: nextcloud:backups/daily)
#   --local-dir <dir>      read/write archives from a local directory instead of
#                          the Nextcloud remote (useful for restore drills)
#   --force                allow extracting into a non-empty destination
#   -h, --help             show this help

set -euo pipefail

NEXTCLOUD_URL_FILE="${NEXTCLOUD_URL_FILE:-/run/secrets/nextcloud_url}"
NEXTCLOUD_USER_FILE="${NEXTCLOUD_USER_FILE:-/run/secrets/nextcloud_user}"
NEXTCLOUD_PASS_FILE="${NEXTCLOUD_PASS_FILE:-/run/secrets/nextcloud_pass}"
BACKUP_AGE_IDENTITY_FILE="${BACKUP_AGE_IDENTITY_FILE:-/run/secrets/age_identity}"

BACKUP_REMOTE_DIR="${BACKUP_REMOTE_DIR:-nextcloud:backups/daily}"
LOCAL_DIR="${BACKUP_LOCAL_DIR:-}"
LOG_FILE="${LOG_FILE:-/app/logs/backup.log}"
WORK_ROOT="${RESTORE_WORK_ROOT:-/tmp/restore}"
TZ="${TZ:-UTC}"

MODE=""
ARCHIVE=""
DEST=""
IDENTITY=""
FORCE=0
LATEST=0

WORK_DIR=""
SRC_PATH=""       # local path of the downloaded / local archive
SRC_ORIGIN=""     # "local" or "remote"
MANIFEST_PATH=""
DB_CHECK_RESULT="not run"
RESTORED_FILES=0
RESTORED_DBS=0

# Ensure the log directory exists; fall back to stdout-only logging when it
# cannot be created (e.g. running the script outside the container).
if ! mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null; then
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] WARNING: cannot write to $(dirname "$LOG_FILE"); logging to stdout only" >&2
    LOG_FILE=/dev/null
fi

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

warn() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] WARNING: $*" | tee -a "$LOG_FILE"
}

usage() {
    # Print the leading comment block of this script as the help text.
    awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"
}

cleanup() {
    local rc=$?
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR" || true
        log "Temp work dir removed (no decrypted data left behind): $WORK_DIR"
    fi
    return "$rc"
}
trap cleanup EXIT

# ---------------------------------------------------------------- secrets
load_secret() {
    local file="$1"
    if [[ -f "$file" ]]; then
        cat "$file"
    else
        error "Secret file not found: $file"
        return 1
    fi
}

check_secrets() {
    for f in "$NEXTCLOUD_URL_FILE" "$NEXTCLOUD_USER_FILE" "$NEXTCLOUD_PASS_FILE"; do
        if [[ ! -f "$f" ]]; then
            error "Required secret not found: $f"
            return 1
        fi
        log "Secret file found: $f"
    done
    return 0
}

setup_rclone() {
    local url user pass
    url=$(load_secret "$NEXTCLOUD_URL_FILE")
    user=$(load_secret "$NEXTCLOUD_USER_FILE")
    pass=$(load_secret "$NEXTCLOUD_PASS_FILE")

    mkdir -p ~/.config/rclone
    umask 077
    cat > ~/.config/rclone/rclone.conf << EOF
[nextcloud]
type = webdav
url = $url
vendor = nextcloud
user = $user
pass = $(rclone obscure "$pass" 2>/dev/null || echo "$pass")
EOF
    chmod 600 ~/.config/rclone/rclone.conf 2>/dev/null || true
    log "rclone configured for Nextcloud"
}

# ---------------------------------------------------------------- helpers
human_size() {
    numfmt --to=iec "$1" 2>/dev/null || echo "$1 bytes"
}

# backup_20240101_030000.tar.gz.age -> backup_20240101_030000.manifest.json
manifest_name_for() {
    local n="$1"
    n="${n%.age}"
    n="${n%.tar.gz}"
    printf '%s.manifest.json' "$n"
}

is_sqlite_file() {
    # SQLite databases (including WAL snapshots written by sqlite3 .backup)
    # always start with the magic header "SQLite format 3\0".
    [[ "$(head -c 15 "$1" 2>/dev/null || true)" == "SQLite format 3" ]]
}

sha256_of() {
    sha256sum "$1" | awk '{print $1}'
}

# Fill the global ARCHIVE_LISTING with "<size> <date> <time> <name>" lines,
# sorted oldest first. Sets globals only - it never writes to stdout, so it can
# be used from contexts that capture output (log() itself writes to stdout).
ARCHIVE_LISTING=""
list_archives() {
    ARCHIVE_LISTING=""
    if [[ -n "$LOCAL_DIR" ]]; then
        [[ -d "$LOCAL_DIR" ]] || { error "Local dir not found: $LOCAL_DIR"; return 1; }
        ARCHIVE_LISTING=$(find "$LOCAL_DIR" -maxdepth 1 -type f -name '*.age' \
            -printf '%s %TY-%Tm-%Td %TH:%TM:%TS %f\n' 2>/dev/null | sort -k2,3 || true)
    else
        command -v rclone >/dev/null 2>&1 || { error "Required program not found: rclone"; return 1; }
        check_secrets || return 1
        setup_rclone
        ARCHIVE_LISTING=$(rclone lsl "$BACKUP_REMOTE_DIR/" 2>>"$LOG_FILE" \
            | awk 'NF>=4 {print $1, $2, $3, $4}' | grep '\.age$' | sort -k2,3 || true)
    fi
    return 0
}

# Fetch a file into $WORK_DIR; sets FOUND_PATH. Works remote or local.
fetch_file() {
    local name="$1"
    FOUND_PATH=""
    if [[ -n "$LOCAL_DIR" ]]; then
        [[ -f "$LOCAL_DIR/$name" ]] || return 1
        cp -p "$LOCAL_DIR/$name" "$WORK_DIR/$name"
        FOUND_PATH="$WORK_DIR/$name"
        return 0
    fi
    if rclone copyto "$BACKUP_REMOTE_DIR/$name" "$WORK_DIR/$name" 2>>"$LOG_FILE"; then
        [[ -s "$WORK_DIR/$name" ]] || return 1
        FOUND_PATH="$WORK_DIR/$name"
        return 0
    fi
    return 1
}

# Resolve the requested archive into a verified local path (SRC_PATH).
resolve_archive() {
    local want="$1"

    # 1. an explicit local file path
    if [[ -f "$want" ]]; then
        SRC_PATH="$want"
        SRC_ORIGIN="local file"
        return 0
    fi
    # 2. a local backup directory (--local-dir)
    if [[ -n "$LOCAL_DIR" && -f "$LOCAL_DIR/$want" ]]; then
        cp -p "$LOCAL_DIR/$want" "$WORK_DIR/$want"
        SRC_PATH="$WORK_DIR/$want"
        SRC_ORIGIN="local dir $LOCAL_DIR"
        return 0
    fi
    # 3. the Nextcloud remote
    if ! command -v rclone >/dev/null 2>&1; then
        error "Required program not found: rclone"
        return 1
    fi
    check_secrets || return 1
    setup_rclone
    log "Downloading $want from $BACKUP_REMOTE_DIR ..."
    if ! fetch_file "$want"; then
        error "Archive not found on the remote: $BACKUP_REMOTE_DIR/$want (try --list)"
        return 1
    fi
    SRC_PATH="$FOUND_PATH"
    SRC_ORIGIN="remote $BACKUP_REMOTE_DIR"
    return 0
}

# Find the newest remote/local archive into LATEST_NAME.
resolve_latest() {
    list_archives || return 1
    if [[ -z "$ARCHIVE_LISTING" ]]; then
        error "No archives found to restore"
        return 1
    fi
    LATEST_NAME=$(printf '%s\n' "$ARCHIVE_LISTING" | tail -n 1 | awk '{print $4}')
    if [[ -z "$LATEST_NAME" ]]; then
        error "Could not determine the newest archive"
        return 1
    fi
    log "Newest archive: $LATEST_NAME"
    return 0
}

# ---------------------------------------------------------------- list
do_list() {
    log "Listing archives..."
    list_archives || return 1
    if [[ -z "$ARCHIVE_LISTING" ]]; then
        echo "No archives found."
        return 0
    fi
    echo
    printf '%-12s %-12s %-10s %s\n' "SIZE" "DATE" "TIME" "ARCHIVE"
    printf '%-12s %-12s %-10s %s\n' "------------" "------------" "----------" "-------"
    local size date time name manifest_flag
    while read -r size date time name; do
        [[ -z "${name:-}" ]] && continue
        manifest_flag=""
        [[ -n "$LOCAL_DIR" && -f "$LOCAL_DIR/$(manifest_name_for "$name")" ]] && manifest_flag=" [manifest]"
        printf '%-12s %-12s %-10s %s%s\n' "$(human_size "$size")" "$date" "${time%%.*}" "$name" "$manifest_flag"
    done <<< "$ARCHIVE_LISTING"
    echo
    echo "Restore one of them with:"
    echo "  $0 --archive <ARCHIVE> --dest <DIR> [--identity <age-private-key-file>]"
    echo "  $0 --latest --dest <DIR> [--identity <age-private-key-file>]"
    echo
    return 0
}

# ---------------------------------------------------------------- integrity
check_restored_sqlite() {
    local dir="$1"
    local dbs=() f
    while IFS= read -r f; do
        [[ -n "$f" ]] && dbs+=("$f")
    done < <(find "$dir" -type f \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name '*.db3' \) 2>/dev/null | sort)

    local real=()
    for f in "${dbs[@]}"; do
        is_sqlite_file "$f" && real+=("$f")
    done
    RESTORED_DBS=${#real[@]}

    if [[ $RESTORED_DBS -eq 0 ]]; then
        DB_CHECK_RESULT="skipped (no SQLite databases in the archive)"
        warn "No SQLite database found in the restored data - integrity check skipped"
        return 0
    fi
    if ! command -v sqlite3 >/dev/null 2>&1; then
        DB_CHECK_RESULT="SKIPPED (sqlite3 is not installed)"
        warn "sqlite3 is not available - database integrity could NOT be verified"
        return 0
    fi

    local ok=0 bad=0 res
    for f in "${real[@]}"; do
        res=$(sqlite3 -cmd ".timeout 10000" "$f" "PRAGMA integrity_check;" 2>&1 | head -n 1 || true)
        if [[ "$res" == "ok" ]]; then
            ok=$((ok + 1))
            log "Integrity check OK: $f"
        else
            bad=$((bad + 1))
            error "Integrity check FAILED for $f: $res"
        fi
    done
    if [[ $bad -eq 0 ]]; then
        DB_CHECK_RESULT="PASSED ($ok database(s) checked with PRAGMA integrity_check)"
        return 0
    fi
    DB_CHECK_RESULT="FAILED ($bad of $((ok + bad)) database(s) are corrupt)"
    return 1
}

# ---------------------------------------------------------------- restore
do_restore() {
    if [[ -z "$DEST" ]]; then
        error "--dest <dir> is required"
        return 2
    fi

    WORK_DIR="$WORK_ROOT/work.$$"
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"

    local archive_name="$ARCHIVE"
    if [[ "$LATEST" -eq 1 ]]; then
        resolve_latest || return 1
        archive_name="$LATEST_NAME"
    fi
    if [[ -z "$archive_name" ]]; then
        error "Nothing to restore: pass --archive <name> or --latest"
        return 2
    fi

    resolve_archive "$archive_name" || return 1

    # --- private key -------------------------------------------------------
    if [[ -z "$IDENTITY" ]]; then
        IDENTITY="$BACKUP_AGE_IDENTITY_FILE"
    fi
    if [[ ! -f "$IDENTITY" ]]; then
        error "age private key not found: $IDENTITY"
        error "Without the private key the backup cannot be decrypted. Pass --identity <file>"
        error "or place the key at $BACKUP_AGE_IDENTITY_FILE."
        return 1
    fi
    log "age identity file found: $IDENTITY"

    # --- manifest + checksum ----------------------------------------------
    # Manifest sits next to the archive and shares its base name:
    #   backup_20240101_030000.tar.gz.age -> backup_20240101_030000.manifest.json
    local manifest_name
    manifest_name=$(manifest_name_for "$(basename "$archive_name")")
    MANIFEST_PATH=""
    local local_manifest
    local_manifest="$(dirname "$SRC_PATH")/$manifest_name"
    if [[ -f "$local_manifest" ]]; then
        MANIFEST_PATH="$local_manifest"
    elif [[ -n "$LOCAL_DIR" && -f "$LOCAL_DIR/$manifest_name" ]]; then
        MANIFEST_PATH="$LOCAL_DIR/$manifest_name"
    elif [[ -z "$LOCAL_DIR" ]] && fetch_file "$manifest_name"; then
        MANIFEST_PATH="$FOUND_PATH"
    fi

    local expected_sha=""
    if [[ -n "$MANIFEST_PATH" && -f "$MANIFEST_PATH" ]]; then
        expected_sha=$(grep -o '"encrypted_archive_sha256"[[:space:]]*:[[:space:]]*"[0-9a-f]\{64\}"' "$MANIFEST_PATH" \
            | grep -o '[0-9a-f]\{64\}' | head -n 1 || true)
        log "Manifest found: $manifest_name"
    else
        warn "No manifest found for $archive_name - checksum cannot be verified"
    fi

    local actual_sha
    actual_sha=$(sha256_of "$SRC_PATH")
    log "Archive sha256: $actual_sha"

    if [[ -n "$expected_sha" ]]; then
        if [[ "$expected_sha" != "$actual_sha" ]]; then
            error "CHECKSUM MISMATCH - the downloaded archive does not match its manifest."
            error "expected $expected_sha"
            error "actual   $actual_sha"
            error "Refusing to restore a possibly corrupted/tampered archive."
            return 1
        fi
        log "Checksum verified against the manifest"
    fi

    # --- destination -------------------------------------------------------
    if [[ -e "$DEST" && ! -d "$DEST" ]]; then
        error "--dest exists and is not a directory: $DEST"
        return 1
    fi
    if [[ -d "$DEST" && -n "$(ls -A "$DEST" 2>/dev/null || true)" && "$FORCE" -ne 1 ]]; then
        error "Destination is not empty: $DEST"
        error "Refusing to overwrite existing data. Re-run with --force, or choose an empty directory."
        return 1
    fi
    mkdir -p "$DEST"

    # --- decrypt -----------------------------------------------------------
    if ! command -v age >/dev/null 2>&1; then
        error "Required program not found: age"
        return 1
    fi

    local plain="$WORK_DIR/restore.tar.gz"
    log "Decrypting with the age private key..."
    if ! age -d -i "$IDENTITY" -o "$plain" "$SRC_PATH" 2>>"$LOG_FILE"; then
        error "Decryption failed - wrong private key, or the archive is damaged"
        return 1
    fi
    log "Decrypted OK ($(human_size "$(stat -c%s "$plain" 2>/dev/null || stat -f%z "$plain")"))"

    # --- extract -----------------------------------------------------------
    if ! tar -tzf "$plain" >/dev/null 2>>"$LOG_FILE"; then
        error "The decrypted archive is not a readable tar.gz file"
        return 1
    fi

    log "Extracting into $DEST ..."
    if ! tar -xzf "$plain" -C "$DEST" --no-same-owner 2>>"$LOG_FILE"; then
        error "Extraction failed"
        return 1
    fi

    RESTORED_FILES=$(find "$DEST" -type f 2>/dev/null | wc -l | tr -d ' ')

    # --- integrity ---------------------------------------------------------
    local integrity_rc=0
    check_restored_sqlite "$DEST" || integrity_rc=1

    # --- report ------------------------------------------------------------
    echo
    echo "======================================================================"
    echo " RESTORE REPORT"
    echo "======================================================================"
    echo " Archive restored : $archive_name"
    echo " Source           : $SRC_ORIGIN"
    echo " Extracted to     : $DEST"
    echo " Files restored   : $RESTORED_FILES (tree starts at $DEST/data/...)"
    echo " Checksum         : $([[ -n "$expected_sha" ]] && echo 'VERIFIED against manifest' || echo 'NOT verified (no manifest)')"
    echo " SQLite databases : $DB_CHECK_RESULT"
    if [[ $integrity_rc -eq 0 ]]; then
        echo " Result           : OK - the backup extracted successfully and checks passed."
    else
        echo " Result           : ATTENTION REQUIRED - a database failed its integrity check."
        echo "                    Do NOT point the bot at this data before investigating."
    fi
    echo
    echo " Next steps: stop the bot service before copying restored data back into"
    echo " place (for example: $DEST/data/freqtrade -> the freqtrade data volume)."
    echo "======================================================================"
    echo

    return "$integrity_rc"
}

# ---------------------------------------------------------------- main
main() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --list)        MODE="list"; shift ;;
            --archive)     MODE="restore"; ARCHIVE="${2:-}"; shift 2 ;;
            --latest)      MODE="restore"; LATEST=1; shift ;;
            --dest)        DEST="${2:-}"; shift 2 ;;
            --identity)    IDENTITY="${2:-}"; shift 2 ;;
            --remote)      BACKUP_REMOTE_DIR="${2:-}"; shift 2 ;;
            --local-dir)   LOCAL_DIR="${2:-}"; shift 2 ;;
            --force)       FORCE=1; shift ;;
            -h|--help)     usage; exit 0 ;;
            *)             error "Unknown argument: $1"; usage >&2; exit 2 ;;
        esac
    done

    export TZ

    case "$MODE" in
        list)    do_list ;;
        restore) do_restore ;;
        *)       usage >&2; exit 2 ;;
    esac
}

main "$@"
