#!/bin/bash
#
# PostgreSQL Backup Script
# Creates compressed backup of portfolio_ai database
#
# Usage: ./scripts/postgres-backup.sh [backup_dir]
# Default backup dir: <project-root>/data/backups

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/project-root.sh"

load_portfolio_db_env() {
    local summitflow_root=""
    local env_file=""

    if [ -n "${PORTFOLIO_DB_URL:-}" ] || [ -n "${PORTFOLIO_AI_DB_URL:-}" ]; then
        return 0
    fi

    if [ -f "$HOME/.env.local" ]; then
        env_file="$HOME/.env.local"
    elif command -v st >/dev/null 2>&1; then
        summitflow_root="$(ST_PROGRESS_ONLY=1 st projects root summitflow 2>/dev/null | head -n 1 | tr -d '\r')"
        if [ -n "$summitflow_root" ] && [ -f "$summitflow_root/docker/compose/.env" ]; then
            env_file="$summitflow_root/docker/compose/.env"
        fi
    fi

    if [ -n "$env_file" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$env_file"
        set +a
    fi
}

parse_database_url() {
    local database_url="$1"

    python3 - "$database_url" <<'PY'
from urllib.parse import urlparse
import sys

parsed = urlparse(sys.argv[1])
print(parsed.username or "")
print(parsed.password or "")
print(parsed.hostname or "localhost")
print(parsed.port or 5432)
print((parsed.path or "/")[1:])
PY
}

# Configuration
PORTFOLIO_ROOT="$(resolve_portfolio_root)"
BACKUP_DIR="${1:-$PORTFOLIO_ROOT/data/backups}"
load_portfolio_db_env

DATABASE_URL="${PORTFOLIO_DB_URL:-${PORTFOLIO_AI_DB_URL:-}}"
if [ -n "$DATABASE_URL" ]; then
    mapfile -t DB_PARTS < <(parse_database_url "$DATABASE_URL")
fi

DB_NAME="${DB_NAME:-${DB_PARTS[4]:-portfolio_ai}}"
DB_USER="${DB_USER:-${DB_PARTS[0]:-portfolio_app}}"
DB_PASSWORD="${DB_PASSWORD:-${DB_PARTS[1]:-}}"
DB_HOST="${DB_HOST:-${DB_PARTS[2]:-localhost}}"
DB_PORT="${DB_PORT:-${DB_PARTS[3]:-5432}}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/portfolio_ai_$TIMESTAMP.sql.gz"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Starting PostgreSQL backup...${NC}"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Host: $DB_HOST:$DB_PORT"
echo "Backup file: $BACKUP_FILE"
echo ""

# Perform backup
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}✗ Backup failed${NC}"
    echo "Reason: No database password available from DB env or ~/.env.local" >&2
    exit 1
fi

if PGPASSWORD="$DB_PASSWORD" pg_dump -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✓ Backup completed successfully${NC}"
    echo "  Size: $BACKUP_SIZE"
    echo "  Location: $BACKUP_FILE"

    # Clean up old backups (keep last 30 days)
    echo ""
    echo "Cleaning up old backups (keeping last 30 days)..."
    find "$BACKUP_DIR" -name "portfolio_ai_*.sql.gz" -type f -mtime +30 -delete

    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "portfolio_ai_*.sql.gz" -type f | wc -l)
    echo "  Total backups: $BACKUP_COUNT"
else
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
fi
