#!/bin/bash
# Encryption helper using age

set -euo pipefail

ENCRYPT_KEY_FILE="${BACKUP_ENCRYPT_KEY_FILE:-/run/secrets/backup_encrypt_key}"

if [[ ! -f "$ENCRYPT_KEY_FILE" ]]; then
    echo "ERROR: Encryption key not found at $ENCRYPT_KEY_FILE"
    exit 1
fi

ENCRYPT_KEY=$(cat "$ENCRYPT_KEY_FILE")

# Read from stdin, encrypt to stdout
age -r "$ENCRYPT_KEY" -e