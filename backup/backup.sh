#!/bin/bash
# Backup Sidecar - Encrypted backup to Nextcloud via WebDAV

set -euo pipefail

# Configuration from environment
NEXTCLOUD_URL_FILE="${NEXTCLOUD_URL_FILE:-/run/secrets/nextcloud_url}"
NEXTCLOUD_USER_FILE="${NEXTCLOUD_USER_FILE:-/run/secrets/nextcloud_user}"
NEXTCLOUD_PASS_FILE="${NEXTCLOUD_PASS_FILE:-/run/secrets/nextcloud_pass}"
BACKUP_ENCRYPT_KEY_FILE="${BACKUP_ENCRYPT_KEY_FILE:-/run/secrets/backup_encrypt_key}"
BACKUP_SCHEDULE="${BACKUP_SCHEDULE:-0 3 * * *}"  # Daily at 3 AM
BACKUP_RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-30}"
BACKUP_RETENTION_MONTHLY="${BACKUP_RETENTION_MONTHLY:-12}"
TZ="${TZ:-UTC}"

# Source directories to backup
SOURCE_DIRS=(
    "/data/freqtrade"
    "/data/logs"
)

BACKUP_ROOT="/tmp/backup"
LOG_FILE="/app/logs/backup.log"

# Ensure log directory
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date -u +"%Y-%m-%d %H:%M:%S")] ERROR: $*" | tee -a "$LOG_FILE" >&2
}

# Load secrets
load_secret() {
    local file="$1"
    if [[ -f "$file" ]]; then
        cat "$file"
    else
        error "Secret file not found: $file"
        return 1
    fi
}

# Check required secrets
check_secrets() {
    for f in "$NEXTCLOUD_URL_FILE" "$NEXTCLOUD_USER_FILE" "$NEXTCLOUD_PASS_FILE" "$BACKUP_ENCRYPT_KEY_FILE"; do
        if [[ ! -f "$f" ]]; then
            error "Required secret not found: $f"
            return 1
        fi
    done
    return 0
}

# Create rclone config
setup_rclone() {
    local url user pass
    url=$(load_secret "$NEXTCLOUD_URL_FILE")
    user=$(load_secret "$NEXTCLOUD_USER_FILE")
    pass=$(load_secret "$NEXTCLOUD_PASS_FILE")

    mkdir -p ~/.config/rclone

    cat > ~/.config/rclone/rclone.conf << EOF
[nextcloud]
type = webdav
url = $url
vendor = nextcloud
user = $user
pass = $(rclone obscure "$pass" 2>/dev/null || echo "$pass")
EOF

    log "rclone configured for Nextcloud"

    # Create remote backup directory if it doesn't exist
    rclone mkdir "nextcloud:backups" 2>/dev/null || true
    rclone mkdir "nextcloud:backups/daily" 2>/dev/null || true
}

# Encrypt and upload a directory
backup_directory() {
    local src_dir="$1"
    local dest_name="$2"

    if [[ ! -d "$src_dir" ]]; then
        log "Source directory not found: $src_dir"
        return 0
    fi

    local timestamp=$(date -u +"%Y%m%d_%H%M%S")
    local archive_name="${dest_name}_${timestamp}.tar.gz"
    local encrypted_name="${archive_name}.age"
    local temp_archive="$BACKUP_ROOT/${archive_name}"
    local temp_encrypted="$BACKUP_ROOT/${encrypted_name}"

    log "Creating archive: $archive_name"

    # Create tar.gz
    if ! tar -czf "$temp_archive" -C "$(dirname "$src_dir")" "$(basename "$src_dir")" 2>>"$LOG_FILE"; then
        error "Failed to create archive for $src_dir"
        return 1
    fi

    local archive_size=$(stat -c%s "$temp_archive" 2>/dev/null || stat -f%z "$temp_archive")
    log "Archive size: $(numfmt --to=iec $archive_size 2>/dev/null || echo "$archive_size bytes")"

    # Encrypt
    log "Encrypting archive..."
    if ! age -r "$(cat "$BACKUP_ENCRYPT_KEY_FILE")" -e -o "$temp_encrypted" "$temp_archive" 2>>"$LOG_FILE"; then
        error "Failed to encrypt archive"
        rm -f "$temp_archive"
        return 1
    fi

    local encrypted_size=$(stat -c%s "$temp_encrypted" 2>/dev/null || stat -f%z "$temp_encrypted")
    log "Encrypted size: $(numfmt --to=iec $encrypted_size 2>/dev/null || echo "$encrypted_size bytes")"

    # Upload to Nextcloud
    log "Uploading to Nextcloud..."
    if ! rclone copy "$temp_encrypted" "nextcloud:backups/daily/" --progress 2>>"$LOG_FILE"; then
        error "Failed to upload to Nextcloud"
        rm -f "$temp_archive" "$temp_encrypted"
        return 1
    fi

    # Cleanup temp files
    rm -f "$temp_archive" "$temp_encrypted"

    log "Backup completed: $encrypted_name"
    return 0
}

# Retention policy
apply_retention() {
    log "Applying retention policy..."

    # Keep daily backups for BACKUP_RETENTION_DAILY days
    rclone delete "nextcloud:backups/daily/" --min-age "${BACKUP_RETENTION_DAILY}d" 2>>"$LOG_FILE" || true

    # Monthly backups (first day of month) - keep for BACKUP_RETENTION_MONTHLY months
    # This is handled by a separate monthly backup job or manual tagging
    # For simplicity, we'll just keep the daily retention

    log "Retention policy applied"
}

# Run full backup
run_backup() {
    log "=== Starting backup ==="

    if ! check_secrets; then
        error "Missing secrets, aborting backup"
        return 1
    fi

    setup_rclone

    local failed=0
    for src in "${SOURCE_DIRS[@]}"; do
        local name=$(basename "$src")
        if ! backup_directory "$src" "$name"; then
            failed=1
        fi
    done

    apply_retention

    if [[ $failed -eq 0 ]]; then
        log "=== Backup completed successfully ==="
        return 0
    else
        error "=== Backup completed with errors ==="
        return 1
    fi
}

# Parse cron schedule (simplified - only supports "minute hour * * *")
parse_schedule() {
    local schedule="$1"
    local parts=($schedule)
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

    # Set timezone
    export TZ

    # Run initial backup
    run_backup

    # Parse schedule for cron-like execution
    local schedule_time=$(parse_schedule "$BACKUP_SCHEDULE")
    local schedule_minute=$(echo "$schedule_time" | awk '{print $1}')
    local schedule_hour=$(echo "$schedule_time" | awk '{print $2}')

    log "Next scheduled run: ${schedule_hour}:${schedule_minute} UTC daily"

    # Simple scheduler loop
    while true; do
        local now_hour=$(date -u +"%H")
        local now_minute=$(date -u +"%M")

        # Check if it's time to run (with 1-minute window)
        if [[ "$now_hour" -eq "$schedule_hour" && "$now_minute" -eq "$schedule_minute" ]]; then
            run_backup
            # Sleep 60 seconds to avoid double-run
            sleep 60
        fi

        sleep 30
    done
}

# Handle signals
trap 'log "Shutdown signal received"; exit 0' SIGTERM SIGINT

main