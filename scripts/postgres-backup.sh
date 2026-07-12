#!/usr/bin/env bash
# Backward-compatible entry point for the complete PostgreSQL + uploads backup.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -gt 0 ] && [[ "$1" != --* ]]; then
    BACKUP_DIR="$1"
    shift
    exec "$SCRIPT_DIR/portfolio-backup.sh" --backup-dir "$BACKUP_DIR" "$@"
fi

exec "$SCRIPT_DIR/portfolio-backup.sh" "$@"
