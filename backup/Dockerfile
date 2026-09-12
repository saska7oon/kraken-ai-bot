# Backup Sidecar Dockerfile
FROM alpine:3.19

# Install rclone, age, and utilities
RUN apk add --no-cache \
    rclone \
    age \
    bash \
    curl \
    ca-certificates \
    tzdata

# Create app user
RUN adduser -D -u 1000 appuser

WORKDIR /app

# Copy scripts
COPY backup.sh encrypt.sh ./
RUN chmod +x backup.sh encrypt.sh

# Create directories
RUN mkdir -p /data/source /tmp/backup /app/logs && \
    chown -R appuser:appuser /app /tmp/backup

USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD test -f /app/backup.sh || exit 1

# Run backup script
ENTRYPOINT ["/app/backup.sh"]