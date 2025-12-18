#!/bin/bash
#
# PostgreSQL Backup Script
# Creates compressed backup of portfolio_ai database
#
# Usage: ./scripts/postgres-backup.sh [backup_dir]
# Default backup dir: ~/portfolio-ai/data/backups

set -euo pipefail

# Configuration
DB_NAME="${DB_NAME:-portfolio_ai}"
DB_USER="${DB_USER:-portfolio_app}"
BACKUP_DIR="${1:-$HOME/portfolio-ai/data/backups}"
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
echo "Backup file: $BACKUP_FILE"
echo ""

# Perform backup
if pg_dump -U "$DB_USER" -h localhost "$DB_NAME" | gzip > "$BACKUP_FILE"; then
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
