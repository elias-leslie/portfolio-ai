#!/bin/bash
# Update PostgreSQL logging config to use journald while keeping audit settings

set -e

echo "========================================="
echo "Updating PostgreSQL Logging for Journald"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

CONF_FILE="/etc/postgresql/16/main/conf.d/postgresql-logging.conf"

# Backup original
cp "$CONF_FILE" "${CONF_FILE}.backup-journald"
echo "✓ Backed up: ${CONF_FILE}.backup-journald"

# Create new config that keeps audit settings but uses journald
cat > "$CONF_FILE" <<'EOF'
# PostgreSQL Statement Logging Configuration for Journald
#
# CRITICAL: Enables forensic audit trail for data modifications
# Updated: 2025-11-10 (Unified Journald Logging)
#
# All logs now go to systemd journald for unified timeline
# View with: journalctl -u postgresql@16-main -f
#

# Log all data modification statements (INSERT, UPDATE, DELETE, TRUNCATE)
log_statement = 'mod'

# Log queries taking longer than 1 second (helps identify performance issues)
log_min_duration_statement = 1000

# Log line prefix: timestamp [PID] user@database
# Example: 2025-11-09 20:00:00 EST [12345] portfolio_app@portfolio_ai
log_line_prefix = '%t [%p] %u@%d '

# JOURNALD SETTINGS: logging_collector must be OFF for journald
logging_collector = off
log_destination = 'stderr'

# Additional useful settings for debugging
log_connections = on          # Log new connections
log_disconnections = on       # Log disconnections
log_duration = off            # Don't log duration of every statement (too verbose)
log_lock_waits = on          # Log when queries wait for locks (helps debug deadlocks)
log_temp_files = 10240       # Log temp files >10MB (helps identify inefficient queries)

# Performance impact: LOW (only logs modifications, not SELECTs)
# View logs: journalctl -u postgresql@16-main -f
# Filter for modifications: journalctl -u postgresql@16-main | grep -E "DELETE|UPDATE|INSERT|TRUNCATE"
EOF

echo "✓ Updated $CONF_FILE for journald"

# Restart PostgreSQL
echo ""
echo "Restarting PostgreSQL..."
systemctl restart postgresql@16-main
sleep 2
echo "✓ Restarted PostgreSQL"

echo ""
echo "========================================="
echo "✓ Configuration Complete!"
echo "========================================="
echo ""
echo "Audit Logging Features:"
echo "  - All INSERT, UPDATE, DELETE, TRUNCATE logged"
echo "  - Slow queries (>1s) logged"
echo "  - Connections/disconnections logged"
echo "  - Lock waits logged"
echo ""
echo "View logs:"
echo "  journalctl -u postgresql@16-main -f"
echo "  journalctl -u postgresql@16-main | grep -E 'DELETE|UPDATE|TRUNCATE'"
echo ""
echo "To rollback:"
echo "  cp ${CONF_FILE}.backup-journald $CONF_FILE && systemctl restart postgresql@16-main"
echo ""
