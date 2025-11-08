#!/bin/bash
# Setup passwordless sudo for Portfolio AI service management
# Run this as: sudo bash setup-sudo-permissions.sh

set -e

SUDOERS_FILE="/etc/sudoers.d/portfolio-ai-services"
BACKUP_FILE="${SUDOERS_FILE}.backup.$(date +%Y%m%d-%H%M%S)"

echo "========================================="
echo "Portfolio AI - Sudo Permissions Setup"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

echo "User: kasadis"
echo "Target file: $SUDOERS_FILE"
echo ""

# Backup existing file if it exists
if [ -f "$SUDOERS_FILE" ]; then
    echo "Backing up existing sudoers file to: $BACKUP_FILE"
    cp "$SUDOERS_FILE" "$BACKUP_FILE"
    echo "✓ Backup created"
    echo ""
fi

# Create new sudoers file
echo "Creating sudoers configuration..."
cat > "$SUDOERS_FILE" << 'EOF'
# Portfolio AI - Passwordless sudo for service management
# User: kasadis
# Services: backend, celery, beat, frontend
# Created: 2025-11-07

# Status commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status portfolio-frontend.service

# Start commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start portfolio-frontend.service

# Stop commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop portfolio-frontend.service

# Restart commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart portfolio-frontend.service

# Reload commands
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl reload portfolio-frontend.service

# is-active commands (for status checking)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-backend.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-celery.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-beat.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active portfolio-frontend.service

# Journalctl commands (for log viewing)
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-backend.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-celery.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-beat.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u portfolio-frontend.service*

# Daemon reload (for service file updates)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl daemon-reload

# Redis service (optional - Portfolio AI may need to restart Redis)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status redis-server.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart redis-server.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop redis-server.service
EOF

echo "✓ Sudoers file created"
echo ""

# Set correct permissions (CRITICAL - sudoers files must be 0440)
chmod 0440 "$SUDOERS_FILE"
echo "✓ Permissions set to 0440"
echo ""

# Validate sudoers file syntax
echo "Validating sudoers syntax..."
if visudo -c -f "$SUDOERS_FILE"; then
    echo "✓ Sudoers file is valid"
    echo ""
    echo "========================================="
    echo "✓ Setup complete!"
    echo "========================================="
    echo ""
    echo "Granted passwordless sudo for kasadis:"
    echo "  - systemctl start/stop/restart/reload/status/is-active"
    echo "  - journalctl -u <service>"
    echo "  - systemctl daemon-reload"
    echo ""
    echo "Services: portfolio-backend, portfolio-celery, portfolio-beat, portfolio-frontend"
    echo ""
    echo "Test with:"
    echo "  sudo systemctl status portfolio-backend.service"
    echo "  sudo systemctl is-active portfolio-celery.service"
    echo ""
else
    echo "✗ ERROR: Sudoers file has syntax errors!"
    echo "Restoring backup..."
    if [ -f "$BACKUP_FILE" ]; then
        mv "$BACKUP_FILE" "$SUDOERS_FILE"
        echo "✓ Backup restored"
    else
        rm -f "$SUDOERS_FILE"
        echo "✓ Invalid file removed"
    fi
    exit 1
fi
