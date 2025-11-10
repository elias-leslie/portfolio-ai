#!/bin/bash
# Configure Portfolio AI services to log to journald instead of files

set -e

SERVICES=(
    "portfolio-backend"
    "portfolio-celery"
    "portfolio-beat"
    "portfolio-frontend"
)

echo "Configuring Portfolio AI services for journald logging..."
echo ""

for service in "${SERVICES[@]}"; do
    echo "Updating $service.service..."

    # Create override directory if it doesn't exist
    sudo mkdir -p "/etc/systemd/system/${service}.service.d"

    # Create override file to remove file logging and enable journald
    sudo tee "/etc/systemd/system/${service}.service.d/journald-logging.conf" > /dev/null <<EOF
[Service]
# Override file logging with journald
StandardOutput=journal
StandardError=journal

# Optional: Set log level identifier for filtering
SyslogIdentifier=${service}
EOF

    echo "  ✓ Created override: /etc/systemd/system/${service}.service.d/journald-logging.conf"
done

echo ""
echo "Reloading systemd configuration..."
sudo systemctl daemon-reload

echo ""
echo "Configuration complete!"
echo ""
echo "To apply changes, restart services:"
echo "  bash ~/portfolio-ai/scripts/restart.sh"
echo ""
echo "To verify journald logging:"
echo "  journalctl -u portfolio-backend -n 20 --no-pager"
echo "  journalctl -u portfolio-celery -n 20 --no-pager"
echo ""
echo "To rollback (restore file logging):"
echo "  sudo rm -rf /etc/systemd/system/portfolio-*.service.d/journald-logging.conf"
echo "  sudo systemctl daemon-reload"
echo "  bash ~/portfolio-ai/scripts/restart.sh"
