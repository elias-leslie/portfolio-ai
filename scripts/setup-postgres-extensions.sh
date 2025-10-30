#!/usr/bin/env bash
# Script to enable pg_stat_statements extension (Task 0.5)
# Run with: sudo ./scripts/setup-postgres-extensions.sh

set -e

# Find the correct postgresql.conf location
PG_CONF=$(find /etc/postgresql -name postgresql.conf 2>/dev/null | head -1)

if [ -z "$PG_CONF" ]; then
    echo "ERROR: Could not find postgresql.conf"
    exit 1
fi

echo "Found postgresql.conf at: $PG_CONF"

# Backup the original file
cp "$PG_CONF" "$PG_CONF.backup-$(date +%Y%m%d)"
echo "Backup created: $PG_CONF.backup-$(date +%Y%m%d)"

# Check if shared_preload_libraries is already set
if grep -q "^shared_preload_libraries.*pg_stat_statements" "$PG_CONF"; then
    echo "pg_stat_statements already configured in shared_preload_libraries"
else
    # Check if the line exists but is commented
    if grep -q "^#shared_preload_libraries" "$PG_CONF"; then
        # Uncomment and add pg_stat_statements
        sed -i "s/^#shared_preload_libraries.*/shared_preload_libraries = 'pg_stat_statements'/" "$PG_CONF"
        echo "Uncommented and configured shared_preload_libraries"
    else
        # Add new line
        echo "shared_preload_libraries = 'pg_stat_statements'" >> "$PG_CONF"
        echo "Added shared_preload_libraries to postgresql.conf"
    fi
fi

# Add pg_stat_statements.track setting
if grep -q "^pg_stat_statements.track" "$PG_CONF"; then
    echo "pg_stat_statements.track already configured"
else
    echo "pg_stat_statements.track = all" >> "$PG_CONF"
    echo "Added pg_stat_statements.track setting"
fi

echo ""
echo "Configuration updated. Restarting PostgreSQL..."

# Restart PostgreSQL to load the extension
systemctl restart postgresql

echo "PostgreSQL restarted successfully"
echo ""
echo "Now run this command to create the extension (no sudo needed):"
echo "  psql -U portfolio_ai_user -d portfolio_ai -c \"CREATE EXTENSION IF NOT EXISTS pg_stat_statements;\""
