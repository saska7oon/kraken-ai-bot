# Backup Sidecar Dockerfile
FROM alpine:3.19

# Install rclone, age, sqlite3 and utilities
#   rclone     - WebDAV upload/download to Nextcloud
#   age        - encryption / decryption
#   sqlite     - sqlite3 CLI, used for consistent ".backup" snapshots of live DBs
#   coreutils  - stat/numfmt/sha256sum with GNU behaviour
#   tar, gzip  - archive creation and extraction
RUN apk add --no-cache \
    rclone \
    age \
    sqlite \
    bash \
    coreutils \
    tar \
    gzip \
    curl \
    ca-certificates \
    tzdata

# Create app user
RUN adduser -D -u 1000 appuser

WORKDIR /app

# Copy scripts
COPY backup.sh restore.sh encrypt.sh ./
RUN chmod +x backup.sh restore.sh encrypt.sh

# Create directories
RUN mkdir -p /data/source /tmp/backup /tmp/restore /app/logs && \
    chown -R appuser:appuser /app /tmp/backup /tmp/restore

USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD test -f /app/backup.sh && test -x /app/restore.sh || exit 1

# Run backup script
ENTRYPOINT ["/app/backup.sh"]
