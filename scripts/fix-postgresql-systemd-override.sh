#!/bin/bash
# Fix PostgreSQL systemd override conflict

set -e

echo "========================================="
echo "Fixing PostgreSQL Systemd Override"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

SERVICE_DIR="/etc/systemd/system/postgresql@16-main.service.d"

# Remove conflicting journald.conf (direct-exec.conf already has everything)
if [ -f "${SERVICE_DIR}/journald.conf" ]; then
    mv "${SERVICE_DIR}/journald.conf" "${SERVICE_DIR}/journald.conf.disabled"
    echo "✓ Disabled conflicting journald.conf"
fi

# Reload systemd
systemctl daemon-reload
echo "✓ Reloaded systemd"

# Restart PostgreSQL
echo ""
echo "Restarting PostgreSQL..."
systemctl restart postgresql@16-main
sleep 2
echo "✓ Restarted PostgreSQL"

# Show actual ExecStart command
echo ""
echo "Verifying configuration..."
systemctl show postgresql@16-main -p ExecStart | head -1

echo ""
echo "========================================="
echo "✓ Fix Complete!"
echo "========================================="
echo ""
echo "Test logging:"
echo "  journalctl -u postgresql@16-main -f"
echo ""
