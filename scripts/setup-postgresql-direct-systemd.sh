#!/bin/bash
# Configure PostgreSQL to run directly under systemd (bypassing pg_ctlcluster)
# This ensures logs go to journald

set -e

echo "========================================="
echo "Configuring PostgreSQL Direct Systemd"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

SERVICE_DIR="/etc/systemd/system/postgresql@16-main.service.d"

# Create complete override that calls postgres directly
cat > "${SERVICE_DIR}/direct-exec.conf" <<'EOF'
[Service]
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

echo "✓ Created systemd override: ${SERVICE_DIR}/direct-exec.conf"

# Reload systemd
systemctl daemon-reload
echo "✓ Reloaded systemd"

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
echo "PostgreSQL now runs directly under systemd"
echo "All logs go to journald with unified timestamps"
echo ""
echo "View logs:"
echo "  journalctl -u postgresql@16-main -f"
echo "  journalctl -u postgresql@16-main | grep -E 'INSERT|UPDATE|DELETE'"
echo ""
echo "To rollback:"
echo "  rm ${SERVICE_DIR}/direct-exec.conf"
echo "  systemctl daemon-reload"
echo "  systemctl restart postgresql@16-main"
echo ""
