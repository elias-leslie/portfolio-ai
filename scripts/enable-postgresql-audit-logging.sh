#!/bin/bash
# Enable PostgreSQL audit logging for destructive actions (DELETE, UPDATE, etc.)

set -e

echo "========================================="
echo "Enabling PostgreSQL Audit Logging"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

PG_CONF="/etc/postgresql/16/main/postgresql.conf"

echo "Configuring audit logging for destructive actions..."

# Enable logging of all data-modifying statements (INSERT, UPDATE, DELETE, TRUNCATE)
sed -i 's/^#\?log_statement = .*/log_statement = '\''mod'\''/' "$PG_CONF"
echo "  ✓ Set log_statement = 'mod' (logs INSERT, UPDATE, DELETE, TRUNCATE)"

# Also log all DDL statements (CREATE, ALTER, DROP)
# If you want DDL too, use 'ddl' or 'all'
# For now keeping 'mod' to focus on data modifications

# Log duration of statements taking longer than 250ms (helps identify slow queries)
sed -i 's/^#\?log_min_duration_statement = .*/log_min_duration_statement = 250/' "$PG_CONF"
echo "  ✓ Set log_min_duration_statement = 250ms (logs slow queries)"

# Ensure we log enough context
sed -i 's/^#\?log_line_prefix = .*/log_line_prefix = '\''%m [%p] %q%u@%d '\''/' "$PG_CONF"
echo "  ✓ Ensured log_line_prefix includes timestamp, pid, user, database"

echo ""
echo "Restarting PostgreSQL to apply changes..."
systemctl restart postgresql@16-main
sleep 2
echo "✓ Restarted PostgreSQL"

echo ""
echo "========================================="
echo "✓ Audit Logging Enabled!"
echo "========================================="
echo ""
echo "What's logged:"
echo "  - All INSERT, UPDATE, DELETE, TRUNCATE statements"
echo "  - All queries taking >250ms"
echo "  - User and database context for each statement"
echo ""
echo "View audit logs:"
echo "  journalctl -u postgresql@16-main --since today | grep -E 'DELETE|UPDATE|TRUNCATE'"
echo ""
echo "To see all PostgreSQL activity:"
echo "  journalctl -u postgresql@16-main -f"
echo ""
