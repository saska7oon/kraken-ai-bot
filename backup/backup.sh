#!/bin/bash
# Backup Sidecar - Encrypted, verified backup to Nextcloud via WebDAV
#
# Hardening notes:
#   * Live SQLite databases are snapshotted with the SQLite online backup API
#     (sqlite3 ".backup") instead of being tarred while in use, so the backup is
#     never torn. Falls back to a plain copy (with a loud warning) when sqlite3
#     is unavailable or the file is not a real SQLite database.
#   * The encrypted archive is checked for well-formedness, hashed (sha256) and
#     verified to be decryptable when an age private key is available.
#   * A JSON manifest (no secrets) is written and uploaded next to the archive.
#   * Temp files are only deleted after a confirmed successful upload; the temp
#     work dir is always removed on exit via a trap.

set -euo pipefail

# ---------------------------------------------------------------- configuration
NEXTCLOUD_URL_FILE="${NEXTCLOUD_URL_FILE:-/run/secrets/nextcloud_url}"
NEXTCLOUD_USER_FILE="${NEXTCLOUD_USER_FILE:-/run/secrets/nextcloud_user}"
NEXTCLOUD_PASS_FILE="${NEXTCLOUD_PASS_FILE:-/run/secrets/nextcloud_pass}"
BACKUP_ENCRYPT_KEY_FILE="${BACKUP_ENCRYPT_KEY_FILE:-/run/secrets/backup_encrypt_key}"
# Optional: age PRIVATE key, used only for the restore-verification self-check.
BACKUP_AGE_IDENTITY_FILE="${BACKUP_AGE_IDENTITY_FILE:-/run/secrets/age_identity}"

BACKUP_SCHEDULE="${BACKUP_SCHEDULE:-0 3 * * *}"  # Daily at 3 AM
BACKUP_RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-30}"
BACKUP_RETENTION_MONTHLY="${BACKUP_RETENTION_MONTHLY:-12}"
BACKUP_RUN_ONCE="${BACKUP_RUN_ONCE:-0}"          # 1 = back up once and exit (cron use)
TZ="${TZ:-UTC}"

BACKUP_REMOTE_DIR="${BACKUP_REMOTE_DIR:-nextcloud:backups/daily}"
BACKUP_ROOT="${BACKUP_ROOT:-/tmp/backup}"
LOG_FILE="${LOG_FILE:-/app/logs/backup.log}"

# Source directories to backup (override with BACKUP_SOURCE_DIRS, colon-separated)
SOURCE_DIRS=(
    "/data/freqtrade"
    "/data/logs"
)
if [[ -n "${BACKUP_SOURCE_DIRS:-}" ]]; then
    IFS=':' read -r -a SOURCE_DIRS <<< "$BACKUP_SOURCE_DIRS"
fi

# ---------------------------------------------------------------- globals
WORK_DIR=""
FAILED_DIR="$BACKUP_ROOT/failed"
ARCHIVE_PATH=""        # uncompressed .tar.gz produced by build_archive
SQLITE_METHOD=""       # method used by the most recent snapshot_sqlite call
DB_METHODS=()          # "member|method|bytes" for every snapshotted database

# Ensure log directory; fall back to stdout-only logging if it is not writable.
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

# Never print secret values - only the fact that a secret file was found.
#
# The trailing newline that secret-creation tooling leaves behind is NOT a
# problem here: every caller assigns through $(...), which strips trailing
# newlines already. This strips a trailing CR and any leading/trailing spaces
# as well, which $(...) does not do - a CRLF-formatted secret file, or a value
# pasted with an accidental trailing space, produces an rclone config that is
# wrong in a way nothing displays. It is cheap insurance, not the fix for the
# upload failure that prompted it.
load_secret() {
    local file="$1"
    if [[ -f "$file" ]]; then
        tr -d '\r' < "$file" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
    else
        error "Secret file not found: $file"
        return 1
    fi
}

check_secrets() {
    for f in "$NEXTCLOUD_URL_FILE" "$NEXTCLOUD_USER_FILE" "$NEXTCLOUD_PASS_FILE" "$BACKUP_ENCRYPT_KEY_FILE"; do
        if [[ ! -f "$f" ]]; then
            error "Required secret not found: $f"
            return 1
        fi
        log "Secret file found: $f"
    done
    return 0
}

# Required binaries must exist before we start; sqlite3 is optional (fallback).
check_tools() {
    local missing=0 tool
    for tool in age rclone tar gzip sha256sum; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            error "Required program not found: $tool"
            missing=1
        fi
    done
    if ! command -v sqlite3 >/dev/null 2>&1; then
        log "WARNING: sqlite3 is not installed - live databases will be plain-copied (may be torn)"
    fi
    [[ $missing -eq 0 ]]
}

# ---------------------------------------------------------------- cleanup
cleanup() {
    local rc=$?
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR" || true
        log "Temp work dir removed: $WORK_DIR"
    fi
    return "$rc"
}

# Keep artifacts of a failed upload for inspection/retry instead of deleting them.
preserve_artifacts() {
    mkdir -p "$FAILED_DIR"
    local f
    for f in "$@"; do
        [[ -f "$f" ]] && cp -p "$f" "$FAILED_DIR/" 2>/dev/null || true
    done
    error "Artifacts preserved in $FAILED_DIR (upload did not succeed, nothing deleted)"
}

# ---------------------------------------------------------------- rclone
setup_rclone() {
    local url user pass
    url=$(load_secret "$NEXTCLOUD_URL_FILE")
    user=$(load_secret "$NEXTCLOUD_USER_FILE")
    pass=$(load_secret "$NEXTCLOUD_PASS_FILE")

    mkdir -p ~/.config/rclone
    chmod 700 ~/.config/rclone 2>/dev/null || true

    # NOTE: the config file holds credentials; it is never logged or printed.
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

    # Probe the remote before doing any work, and report what rclone actually
    # says when it fails.
    #
    # Both mkdir calls used to discard stderr and force success with
    # `|| true`, so a bad URL or wrong app password produced no message at all.
    # The first sign of trouble was the copy failing minutes later with
    # "Failed to upload archive to Nextcloud" and no reason. An operator cannot
    # fix a credential problem they cannot see, and "it failed" is not a
    # diagnosis.
    #
    # The URL is deliberately not printed: it can embed a username. The shape
    # is echoed instead, which is enough to spot the common mistake of pointing
    # nextcloud_url at a folder that already ends in /backups while
    # BACKUP_REMOTE_DIR also starts with backups/.
    log "WebDAV target shape: $(printf '%s' "$url" | sed -e 's#^\(https\?://\)#\1#' -e 's#/[^/]*$#/...#') + $BACKUP_REMOTE_DIR"

    local probe_err
    if ! probe_err=$(rclone lsd "nextcloud:" 2>&1); then
        error "Cannot reach the Nextcloud remote at all."
        error "rclone said: ${probe_err}"
        error "Check the nextcloud_url, nextcloud_user and nextcloud_pass secrets."
        error "nextcloud_pass must be a Nextcloud APP password, not the account password."
        return 1
    fi

    if ! probe_err=$(rclone mkdir "$BACKUP_REMOTE_DIR" 2>&1); then
        error "Reached Nextcloud but could not create $BACKUP_REMOTE_DIR"
        error "rclone said: ${probe_err}"
        error "A 409 Conflict here usually means the parent folder does not exist."
        return 1
    fi

    log "Remote reachable and $BACKUP_REMOTE_DIR is ready"
    return 0
}

# ---------------------------------------------------------------- sqlite helpers
# Candidate databases are found by filename, then validated by magic header.
find_sqlite_candidates() {
    local dir="$1"
    find "$dir" -type f \( -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name '*.db3' \) \
        2>/dev/null | sort || true
}

# A real SQLite database starts with "SQLite format 3\0".
is_sqlite_file() {
    [[ "$(head -c 15 "$1" 2>/dev/null || true)" == "SQLite format 3" ]]
}

# Snapshot one database consistently into $2. Sets SQLITE_METHOD.
snapshot_sqlite() {
    local db="$1"
    local dest="$2"
    mkdir -p "$(dirname "$dest")"

    if command -v sqlite3 >/dev/null 2>&1; then
        if sqlite3 -cmd ".timeout 10000" "$db" ".backup '$dest'" >>"$LOG_FILE" 2>&1 && [[ -s "$dest" ]]; then
            if sqlite3 "$dest" "PRAGMA quick_check;" 2>>"$LOG_FILE" | grep -qx "ok"; then
                SQLITE_METHOD="sqlite3 .backup"
                return 0
            fi
            error "SQLite quick_check FAILED on snapshot of $db - refusing to ship a bad database"
            return 1
        fi
        log "WARNING: sqlite3 online backup failed for $db; falling back to a plain copy (backup MAY BE TORN)"
    else
        log "WARNING: sqlite3 not available; falling back to a plain copy of $db (backup MAY BE TORN)"
    fi

    rm -f "$dest"
    if ! cp -p "$db" "$dest" 2>>"$LOG_FILE"; then
        error "Fallback copy failed for $db"
        return 1
    fi
    SQLITE_METHOD="plain file copy (sqlite3 unavailable)"
    return 0
}

# ---------------------------------------------------------------- archive
json_escape() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

# Build $WORK_DIR/<name>.tar.gz. Sets ARCHIVE_PATH and DB_METHODS.
# Archive members are paths relative to / (e.g. data/freqtrade/...), so a
# restore into a directory recreates <dest>/data/freqtrade/...
build_archive() {
    local name="$1"
    local tar_plain="$WORK_DIR/$name.tar"
    local targz="$WORK_DIR/$name.tar.gz"
    local exclude_file="$WORK_DIR/exclude.list"
    local stage_dir="$WORK_DIR/stage"

    : > "$exclude_file"
    mkdir -p "$stage_dir"

    # Sidecars are meaningless without the live database: never ship them.
    printf '%s\n' '*sqlite-wal' '*sqlite-shm' '*sqlite-journal' >> "$exclude_file"

    local members=()
    local src
    for src in "${SOURCE_DIRS[@]}"; do
        if [[ ! -d "$src" ]]; then
            log "Source directory not found, skipping: $src"
            continue
        fi
        members+=("${src#/}")
    done

    if [[ ${#members[@]} -eq 0 ]]; then
        error "No source directories exist; nothing to back up"
        return 1
    fi

    # Discover live databases and exclude them from the plain tar.
    local db_found=()
    while IFS= read -r db; do
        [[ -z "$db" ]] && continue
        if is_sqlite_file "$db"; then
            db_found+=("$db")
            local rel="${db#/}"
            printf '%s\n' "$rel" "$rel-wal" "$rel-shm" "$rel-journal" >> "$exclude_file"
        else
            log "WARNING: $db looks like a database but is not a valid SQLite file; copying it as-is"
        fi
    done < <(for src in "${members[@]}"; do find_sqlite_candidates "/$src"; done)

    local tar_status=0
    tar --warning=no-file-changed --warning=no-file-removed \
        --exclude-from="$exclude_file" \
        -cf "$tar_plain" -C / "${members[@]}" 2>>"$LOG_FILE" || tar_status=$?
    # Exit code 1 = "some files changed/vanished while reading" (normal for live
    # log files). Anything above that is a real failure.
    if [[ $tar_status -gt 1 ]]; then
        error "tar failed while creating the archive (exit $tar_status)"
        return 1
    fi

    # Append consistent SQLite snapshots at their original archive paths.
    DB_METHODS=()
    if [[ ${#db_found[@]} -gt 0 ]]; then
        local staged=()
        local db rel dest
        for db in "${db_found[@]}"; do
            rel="${db#/}"
            dest="$stage_dir/$rel"
            SQLITE_METHOD=""
            if ! snapshot_sqlite "$db" "$dest"; then
                return 1
            fi
            staged+=("$rel")
            DB_METHODS+=("$rel|$SQLITE_METHOD|$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest")")
            log "Consistent SQLite snapshot: $db -> $rel (method: $SQLITE_METHOD)"
        done
        if ! tar -rf "$tar_plain" -C "$stage_dir" "${staged[@]}" 2>>"$LOG_FILE"; then
            error "Failed to append SQLite snapshots to the archive"
            return 1
        fi
    else
        log "No SQLite databases found in the source directories"
    fi

    if ! gzip -f "$tar_plain" 2>>"$LOG_FILE"; then
        error "Failed to compress the archive"
        return 1
    fi

    ARCHIVE_PATH="$targz"
    if [[ ! -s "$ARCHIVE_PATH" ]]; then
        error "Archive is empty: $ARCHIVE_PATH"
        return 1
    fi
    local size
    size=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || stat -f%z "$ARCHIVE_PATH")
    log "Archive created: $name.tar.gz ($(human_size "$size"))"
    return 0
}

human_size() {
    numfmt --to=iec "$1" 2>/dev/null || echo "$1 bytes"
}

# ---------------------------------------------------------------- manifest
write_manifest() {
    local manifest="$1" name="$2" recipient="$3" sha="$4" plain_sha="$5" \
          enc_size="$6" plain_size="$7" identity_available="$8" restore_verified="$9"

    local src_json="" db_json="" sep=""
    local src member files bytes
    for src in "${SOURCE_DIRS[@]}"; do
        [[ -d "$src" ]] || continue
        member="${src#/}"
        files=$(find "$src" -type f 2>/dev/null | wc -l | tr -d ' ')
        bytes=$(du -sb "$src" 2>/dev/null | awk '{print $1}' || echo 0)
        src_json+="${sep}{\"path\": \"$(json_escape "$src")\", \"member\": \"$(json_escape "$member")\", \"files\": ${files:-0}, \"bytes\": ${bytes:-0}}"
        sep=","
    done

    # Emit real JSON booleans, not 0/1.
    local identity_json="false" verified_json="false"
    [[ "$identity_available" == "1" ]] && identity_json="true"
    [[ "$restore_verified" == "1" ]] && verified_json="true"

    sep=""
    local rec rel method dbytes
    if [[ ${#DB_METHODS[@]} -gt 0 ]]; then
        for rec in "${DB_METHODS[@]}"; do
            rel="${rec%%|*}"
            method="${rec#*|}"
            dbytes="${method##*|}"
            method="${method%%|*}"
            db_json+="${sep}{\"member\": \"$(json_escape "$rel")\", \"bytes\": ${dbytes:-0}, \"backup_method\": \"$(json_escape "$method")\"}"
            sep=","
        done
    fi

    cat > "$manifest" << EOF
{
  "manifest_version": 1,
  "archive": "$(json_escape "$name.tar.gz.age")",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "timestamp_unix": $(date -u +%s),
  "hostname": "$(json_escape "$(hostname 2>/dev/null || echo unknown)")",
  "sources": [${src_json}],
  "sqlite_databases": [${db_json}],
  "encrypted_archive_bytes": ${enc_size},
  "encrypted_archive_sha256": "$(json_escape "$sha")",
  "unencrypted_archive_bytes": ${plain_size},
  "unencrypted_archive_sha256": "$(json_escape "$plain_sha")",
  "age_recipient": "$(json_escape "$recipient")",
  "age_identity_available": ${identity_json},
  "restore_verified": ${verified_json}
}
EOF
    log "Manifest written: $(basename "$manifest")"
}

# ---------------------------------------------------------------- backup run
run_backup() {
    log "=== Starting backup run ==="

    if ! check_secrets; then
        error "Missing secrets, aborting backup"
        return 1
    fi

    if ! check_tools; then
        error "Missing required programs, aborting backup"
        return 1
    fi

    # Stop here if the remote is unreachable. Previously this was unchecked, so
    # a wrong URL or app password was discovered only when the upload failed at
    # the very end - after the databases had been snapshotted and encrypted -
    # and the message said nothing about the cause. Failing before the work
    # means the operator gets the diagnosis immediately and nothing is left
    # half-done.
    if ! setup_rclone; then
        error "Cannot use the Nextcloud remote; aborting before touching any data"
        return 1
    fi

    WORK_DIR="$BACKUP_ROOT/work"
    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR"

    local ts name
    ts=$(date -u +"%Y%m%d_%H%M%S")
    name="backup_${ts}"

    DB_METHODS=()
    if ! build_archive "$name"; then
        error "Archive creation failed"
        return 1
    fi

    local plain_sha plain_size
    plain_sha=$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')
    plain_size=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || stat -f%z "$ARCHIVE_PATH")
    log "Unencrypted archive sha256: $plain_sha"

    # Recipient file must contain an age PUBLIC key. Never log the value.
    local recipient
    recipient=$(load_secret "$BACKUP_ENCRYPT_KEY_FILE")
    if [[ "$recipient" == AGE-SECRET-KEY* ]]; then
        error "BACKUP_ENCRYPT_KEY_FILE contains a PRIVATE key - refusing to continue (use the public key)"
        return 1
    fi
    if [[ "$recipient" != age1* ]]; then
        error "BACKUP_ENCRYPT_KEY_FILE does not contain a valid age public key (expected age1...)"
        return 1
    fi

    local enc="$WORK_DIR/$name.tar.gz.age"
    log "Encrypting archive..."
    if age -R "$BACKUP_ENCRYPT_KEY_FILE" -e -o "$enc" "$ARCHIVE_PATH" 2>>"$LOG_FILE"; then
        :
    else
        # Older age builds may not support -R (recipients file); retry with the
        # public key inline. The recipient is a PUBLIC key, never a secret.
        rm -f "$enc"
        log "age -R failed; retrying with an inline recipient"
        if ! age -r "$recipient" -e -o "$enc" "$ARCHIVE_PATH" 2>>"$LOG_FILE"; then
            error "Failed to encrypt archive"
            return 1
        fi
    fi

    # --- integrity: age header + sha256 -------------------------------------
    local header
    header=$(head -c 21 "$enc" 2>/dev/null || true)
    if [[ "$header" != "age-encryption.org/v1" ]]; then
        error "Encrypted archive is not a valid age file (bad header)"
        return 1
    fi
    local sha enc_size
    sha=$(sha256sum "$enc" | awk '{print $1}')
    enc_size=$(stat -c%s "$enc" 2>/dev/null || stat -f%z "$enc")
    log "Encrypted archive sha256: $sha"
    log "Encrypted size: $(human_size "$enc_size")"

    # --- integrity: restore-verification against the private key ------------
    local identity_available=0 restore_verified=0
    if [[ -f "$BACKUP_AGE_IDENTITY_FILE" ]]; then
        identity_available=1
        log "age identity file found; verifying the archive can actually be decrypted"
        if age -d -i "$BACKUP_AGE_IDENTITY_FILE" -o "$WORK_DIR/verify.tar.gz" "$enc" 2>>"$LOG_FILE"; then
            local verify_sha
            verify_sha=$(sha256sum "$WORK_DIR/verify.tar.gz" | awk '{print $1}')
            if [[ "$verify_sha" == "$plain_sha" ]]; then
                restore_verified=1
                log "Restore-verification PASSED (decrypted content matches the original archive)"
            else
                error "Restore-verification FAILED: decrypted content does not match the original archive"
                return 1
            fi
            rm -f "$WORK_DIR/verify.tar.gz"
        else
            error "Restore-verification FAILED: the archive could not be decrypted with $BACKUP_AGE_IDENTITY_FILE"
            return 1
        fi
    else
        log "RESTORE-VERIFICATION SKIPPED: no age identity at $BACKUP_AGE_IDENTITY_FILE"
        log "RISK: this backup has NOT been proven decryptable. Provide the age private key to enable self-checks."
    fi

    local manifest="$WORK_DIR/$name.manifest.json"
    write_manifest "$manifest" "$name" "$recipient" "$sha" "$plain_sha" \
        "$enc_size" "$plain_size" "$identity_available" "$restore_verified"

    # --- upload (delete temp files ONLY after a confirmed success) ----------
    log "Uploading archive to $BACKUP_REMOTE_DIR ..."
    if ! rclone copy "$enc" "$BACKUP_REMOTE_DIR/" 2>>"$LOG_FILE"; then
        error "Failed to upload archive to Nextcloud"
        preserve_artifacts "$enc" "$manifest"
        return 1
    fi

    log "Uploading manifest..."
    if ! rclone copy "$manifest" "$BACKUP_REMOTE_DIR/" 2>>"$LOG_FILE"; then
        error "Failed to upload manifest to Nextcloud"
        preserve_artifacts "$enc" "$manifest"
        return 1
    fi

    log "Upload confirmed; removing local temp files"
    rm -f "$enc" "$ARCHIVE_PATH" "$manifest"

    apply_retention

    log "Backup completed: $name.tar.gz.age"
    return 0
}

# Retention policy
apply_retention() {
    log "Applying retention policy (daily: ${BACKUP_RETENTION_DAILY}d)..."

    rclone delete "$BACKUP_REMOTE_DIR/" --min-age "${BACKUP_RETENTION_DAILY}d" 2>>"$LOG_FILE" || true

    # Monthly backups (first day of month) - keep for BACKUP_RETENTION_MONTHLY months
    # This is handled by a separate monthly backup job or manual tagging
    # For simplicity, we'll just keep the daily retention

    log "Retention policy applied"
}

# Parse cron schedule (simplified - only supports "minute hour * * *")
parse_schedule() {
    local schedule="$1"
    local -a parts
    read -r -a parts <<< "$schedule"
    if [[ ${#parts[@]} -eq 5 ]]; then
        echo "${parts[0]} ${parts[1]}"
    else
        echo "3 3"  # Default 3:03 AM
    fi
}

# Main loop
main() {
    log "Backup sidecar starting..."
    log "Schedule: $BACKUP_SCHEDULE"
    log "Source dirs: ${SOURCE_DIRS[*]}"
    log "Timezone: $TZ"

    export TZ

    # Run initial backup
    local rc=0
    run_backup || rc=$?

    if [[ "$BACKUP_RUN_ONCE" == "1" ]]; then
        log "BACKUP_RUN_ONCE=1 - exiting after a single run (status $rc)"
        exit "$rc"
    fi

    # Parse schedule for cron-like execution
    local schedule_time schedule_minute schedule_hour
    schedule_time=$(parse_schedule "$BACKUP_SCHEDULE")
    schedule_minute=$(echo "$schedule_time" | awk '{print $1}')
    schedule_hour=$(echo "$schedule_time" | awk '{print $2}')

    # BACKUP_SCHEDULE is interpreted in the container's local time (TZ).
    # Previously this compared UTC hour/minute while the stack sets
    # TZ=America/Toronto, so "0 3 * * *" actually ran at 23:00 local time.
    log "Next scheduled run: ${schedule_hour}:${schedule_minute} local time (TZ=${TZ:-UTC})"

    # Simple scheduler loop
    local now_hour now_minute
    while true; do
        now_hour=$(date +"%H")
        now_minute=$(date +"%M")

        # Check if it's time to run (with 1-minute window)
        if [[ "$now_hour" -eq "$schedule_hour" && "$now_minute" -eq "$schedule_minute" ]]; then
            run_backup || error "Scheduled backup run failed; will retry at the next scheduled time"
            # Sleep 60 seconds to avoid double-run
            sleep 60
        fi

        sleep 30
    done
}

# Handle signals (EXIT trap is registered after log() is defined)
trap 'log "Shutdown signal received"; exit 0' SIGTERM SIGINT
trap cleanup EXIT

main
