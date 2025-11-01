#!/bin/bash
# Install Portfolio AI systemd services for auto-start on boot

set -e

echo "Installing Portfolio AI systemd services..."

# Copy service files to systemd directory
sudo cp /home/kasadis/portfolio-ai/scripts/systemd/portfolio-backend.service /etc/systemd/system/
sudo cp /home/kasadis/portfolio-ai/scripts/systemd/portfolio-celery.service /etc/systemd/system/
sudo cp /home/kasadis/portfolio-ai/scripts/systemd/portfolio-celery-beat.service /etc/systemd/system/
sudo cp /home/kasadis/portfolio-ai/scripts/systemd/portfolio-frontend.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable portfolio-backend.service
sudo systemctl enable portfolio-celery.service
sudo systemctl enable portfolio-celery-beat.service
sudo systemctl enable portfolio-frontend.service

echo "✓ Services installed and enabled for auto-start"
echo ""
echo "Service management commands:"
echo "  Start all:   sudo systemctl start portfolio-backend portfolio-celery portfolio-celery-beat portfolio-frontend"
echo "  Stop all:    sudo systemctl stop portfolio-backend portfolio-celery portfolio-celery-beat portfolio-frontend"
echo "  Status:      sudo systemctl status portfolio-backend portfolio-celery portfolio-celery-beat portfolio-frontend"
echo "  Logs:        sudo journalctl -u portfolio-backend -f"
echo ""
echo "Services will now start automatically on boot."
