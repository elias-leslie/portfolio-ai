#!/bin/bash
# Configure PostgreSQL to log to stderr (journald) instead of files

set -e

echo "========================================="
echo "Configuring PostgreSQL stderr logging"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

PG_CONF="/etc/postgresql/16/main/postgresql.conf"

# Backup original config
if [ ! -f "$PG_CONF.backup-stderr" ]; then
    cp "$PG_CONF" "$PG_CONF.backup-stderr"
    echo "✓ Backed up original config: $PG_CONF.backup-stderr"
fi

# Update PostgreSQL configuration
echo "Updating PostgreSQL configuration..."

# Ensure logging_collector is off (so logs go to stderr/journald)
sed -i 's/^#\?logging_collector = .*/logging_collector = off/' "$PG_CONF"
echo "  ✓ Set logging_collector = off"

# Set log_destination to stderr
sed -i 's/^#\?log_destination = .*/log_destination = '\''stderr'\''/' "$PG_CONF"
echo "  ✓ Set log_destination = 'stderr'"

# Set reasonable log level
sed -i 's/^#\?log_min_messages = .*/log_min_messages = notice/' "$PG_CONF"
echo "  ✓ Set log_min_messages = notice"

# Restart PostgreSQL
echo ""
echo "Restarting PostgreSQL..."
systemctl restart postgresql@16-main
echo "✓ Restarted PostgreSQL"

# Wait a moment for startup logs
sleep 2

echo ""
echo "========================================="
echo "✓ Configuration Complete!"
echo "========================================="
echo ""
echo "Verification:"
echo "  journalctl -u postgresql@16-main -n 10"
echo ""
echo "To rollback:"
echo "  cp $PG_CONF.backup-stderr $PG_CONF && systemctl restart postgresql@16-main"
echo ""
