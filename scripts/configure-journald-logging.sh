#!/bin/bash
# Configure PostgreSQL and Redis to log to journald (stdout)
# This enables unified log monitoring across all services

set -e

echo "========================================="
echo "Configuring Journald Logging"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# 1. Configure PostgreSQL to log to journald
echo "1. Configuring PostgreSQL..."
mkdir -p /etc/systemd/system/postgresql@16-main.service.d

cat > /etc/systemd/system/postgresql@16-main.service.d/journald.conf <<'EOF'
[Service]
# Override ExecStart to remove --skip-systemctl-redirect
# This allows PostgreSQL to log to journald instead of files only
ExecStart=
ExecStart=/usr/bin/pg_ctlcluster %i start

# Ensure stdout/stderr go to journald
StandardOutput=journal
StandardError=journal
EOF

echo "   ✓ Created systemd override: /etc/systemd/system/postgresql@16-main.service.d/journald.conf"

# 2. Configure Redis to log to stdout (journald)
echo "2. Configuring Redis..."

# Backup original config
if [ ! -f /etc/redis/redis.conf.backup-journald ]; then
    cp /etc/redis/redis.conf /etc/redis/redis.conf.backup-journald
    echo "   ✓ Backed up original config: /etc/redis/redis.conf.backup-journald"
fi

# Change logfile to empty string (stdout)
sed -i 's/^logfile .*$/logfile ""/' /etc/redis/redis.conf
echo "   ✓ Updated /etc/redis/redis.conf: logfile = \"\""

# Also ensure daemonize is off (systemd manages this)
sed -i 's/^daemonize yes/daemonize no/' /etc/redis/redis.conf
echo "   ✓ Updated /etc/redis/redis.conf: daemonize = no"

# 3. Reload systemd and restart services
echo ""
echo "3. Reloading systemd and restarting services..."
systemctl daemon-reload
echo "   ✓ Reloaded systemd"

systemctl restart postgresql@16-main
echo "   ✓ Restarted PostgreSQL"

systemctl restart redis-server
echo "   ✓ Restarted Redis"

# 4. Verify logging to journald
echo ""
echo "========================================="
echo "✓ Configuration Complete!"
echo "========================================="
echo ""
echo "Verification:"
echo "  PostgreSQL: journalctl -u postgresql@16-main -n 5"
echo "  Redis:      journalctl -u redis-server -n 5"
echo ""
echo "To rollback:"
echo "  PostgreSQL: rm -rf /etc/systemd/system/postgresql@16-main.service.d && systemctl daemon-reload && systemctl restart postgresql@16-main"
echo "  Redis:      cp /etc/redis/redis.conf.backup-journald /etc/redis/redis.conf && systemctl restart redis-server"
echo ""
