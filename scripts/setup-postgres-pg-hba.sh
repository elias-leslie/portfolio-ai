#!/usr/bin/env bash
# Script to configure pg_hba.conf for local development (Task 0.4)
# Run with: sudo ./scripts/setup-postgres-pg-hba.sh

set -e

# Find the correct pg_hba.conf location
PG_HBA_CONF=$(find /etc/postgresql -name pg_hba.conf 2>/dev/null | head -1)

if [ -z "$PG_HBA_CONF" ]; then
    echo "ERROR: Could not find pg_hba.conf"
    exit 1
fi

echo "Found pg_hba.conf at: $PG_HBA_CONF"

# Backup the original file
cp "$PG_HBA_CONF" "$PG_HBA_CONF.backup-$(date +%Y%m%d)"
echo "Backup created: $PG_HBA_CONF.backup-$(date +%Y%m%d)"

# Add trust rules for local development (insert at the top of the rules section)
# Using sed to insert after the comment section
sed -i '/^# TYPE/a\
# Portfolio AI local development trust rules\
local   portfolio_ai    portfolio_ai_user                            trust\
host    portfolio_ai    portfolio_ai_user   127.0.0.1/32            trust\
host    portfolio_ai    portfolio_ai_user   ::1/128                 trust' "$PG_HBA_CONF"

echo "Added trust rules to pg_hba.conf"

# Reload PostgreSQL to apply changes
systemctl reload postgresql

echo "PostgreSQL reloaded successfully"
echo ""
echo "Configuration complete! Test with:"
echo "  psql -U portfolio_ai_user -d portfolio_ai -c \"SELECT 1;\""
