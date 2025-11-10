#!/bin/bash
# Fix PostgreSQL systemd Type for direct postgres execution

set -e

echo "========================================="
echo "Fixing PostgreSQL Systemd Type"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

SERVICE_DIR="/etc/systemd/system/postgresql@16-main.service.d"

# Create correct override with Type=exec
cat > "${SERVICE_DIR}/direct-exec.conf" <<'EOF'
[Service]
# Change from Type=forking to Type=exec for direct postgres execution
Type=exec

# Override ExecStart completely to call postgres directly (not via pg_ctlcluster)
# This ensures stderr goes to journald
ExecStart=
ExecStart=/usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main -c config_file=/etc/postgresql/16/main/postgresql.conf

# Override ExecStop to use pg_ctl directly
ExecStop=
ExecStop=/usr/lib/postgresql/16/bin/pg_ctl stop -D /var/lib/postgresql/16/main -m fast

# Override ExecReload to use pg_ctl directly
ExecReload=
ExecReload=/usr/lib/postgresql/16/bin/pg_ctl reload -D /var/lib/postgresql/16/main

# Ensure stdout/stderr go to journald
StandardOutput=journal
StandardError=journal

# Run as postgres user
User=postgres
Group=postgres

# Working directory
WorkingDirectory=/var/lib/postgresql/16/main
EOF

echo "✓ Updated systemd override with Type=exec"

# Reload systemd
systemctl daemon-reload
echo "✓ Reloaded systemd"

# Stop any stuck postgres processes
echo ""
echo "Stopping PostgreSQL..."
systemctl stop postgresql@16-main || true
sleep 2

# Start PostgreSQL
echo "Starting PostgreSQL..."
systemctl start postgresql@16-main
sleep 2
echo "✓ Started PostgreSQL"

echo ""
echo "========================================="
echo "✓ Configuration Complete!"
echo "========================================="
echo ""
systemctl status postgresql@16-main --no-pager | head -15
echo ""
