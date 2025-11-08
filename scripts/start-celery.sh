#!/usr/bin/env bash
# Start Celery Worker and Beat via systemd
# USE SYSTEMD - NO MANUAL PROCESS MANAGEMENT

set -euo pipefail

echo "Starting Celery services via systemd..."

# Start worker
sudo systemctl start portfolio-celery.service
# Start beat
sudo systemctl start portfolio-beat.service

sleep 2

# Check status
if sudo systemctl is-active --quiet portfolio-celery.service; then
    echo "✓ Celery worker started"
else
    echo "✗ Failed to start Celery worker"
    exit 1
fi

if sudo systemctl is-active --quiet portfolio-beat.service; then
    echo "✓ Celery beat started"
else
    echo "✗ Failed to start Celery beat"
    exit 1
fi

echo ""
echo "Celery services running via systemd"
echo "View logs: sudo journalctl -u portfolio-celery -f"
