#!/bin/bash
# Install Portfolio AI systemd USER services for auto-start
#
# Services run in user context (systemctl --user) which:
# - Don't require sudo for management
# - Persist across reboots via loginctl enable-linger
# - Store logs in user journal

set -e

echo "Installing Portfolio AI systemd USER services..."

# Create user systemd directory if it doesn't exist
mkdir -p ~/.config/systemd/user

# Create symlinks to service files (allows updates to take effect automatically)
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-backend.service ~/.config/systemd/user/
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-celery.service ~/.config/systemd/user/
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-celery-beat.service ~/.config/systemd/user/
ln -sf ~/portfolio-ai/scripts/systemd/portfolio-frontend.service ~/.config/systemd/user/

# Reload user systemd daemon
systemctl --user daemon-reload

# Enable services to start on login/boot
systemctl --user enable portfolio-backend.service
systemctl --user enable portfolio-celery.service
systemctl --user enable portfolio-celery-beat.service
systemctl --user enable portfolio-frontend.service

# Enable lingering so services start on boot without login
echo ""
echo "Enabling lingering for user $(whoami)..."
echo "  (This requires sudo - services will still work without it, but won't auto-start on boot)"
sudo loginctl enable-linger $(whoami) 2>/dev/null || echo "  Note: Run 'sudo loginctl enable-linger $(whoami)' manually for boot persistence"

echo ""
echo "✓ User services installed and enabled"
echo ""
echo "Service management commands (no sudo needed!):"
echo "  Start all:   bash ~/portfolio-ai/scripts/start.sh"
echo "  Stop all:    bash ~/portfolio-ai/scripts/shutdown.sh"
echo "  Restart all: bash ~/portfolio-ai/scripts/restart.sh"
echo "  Status:      bash ~/portfolio-ai/scripts/status.sh"
echo ""
echo "Individual service management:"
echo "  systemctl --user start portfolio-backend"
echo "  systemctl --user stop portfolio-celery"
echo "  systemctl --user restart portfolio-frontend"
echo "  systemctl --user status portfolio-celery-beat"
echo ""
echo "Logs:"
echo "  journalctl --user -u portfolio-backend -f"
echo "  journalctl --user -u portfolio-celery -f"
echo ""
echo "Services will auto-start on boot (via lingering) or on login."
