#!/bin/bash
# Add passwordless sudo for backup services
# Run as: sudo bash setup-backup-sudo.sh

set -e

SUDOERS_FILE="/etc/sudoers.d/portfolio-ai-backups"
BACKUP_FILE="${SUDOERS_FILE}.backup.$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================="
echo "Portfolio AI - Backup Sudo Permissions"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root (use sudo)${NC}"
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
echo "Creating sudoers configuration for backups..."
cat > "$SUDOERS_FILE" << 'EOF'
# Portfolio AI - Passwordless sudo for backup management
# User: kasadis
# Created: 2025-11-07

# CRITICAL: Allow sudo without TTY (needed for Claude Code Bash tool)
Defaults:kasadis !requiretty

# Veeam backup service (system service)
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl start veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl stop veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl restart veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl status veeam-smart-backup.service
kasadis ALL=(root) NOPASSWD: /usr/bin/systemctl is-active veeam-smart-backup.service

# Veeam backup commands
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job start *
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job stop *
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig job list
kasadis ALL=(root) NOPASSWD: /usr/bin/veeamconfig session list

# Veeam logs
kasadis ALL=(root) NOPASSWD: /usr/bin/journalctl -u veeam-smart-backup.service*
kasadis ALL=(root) NOPASSWD: /usr/bin/cat /var/log/veeam-smart-backup.log

# SMB/mount checks (for troubleshooting)
kasadis ALL=(root) NOPASSWD: /usr/bin/smbclient *
EOF

chmod 0440 "$SUDOERS_FILE"
echo "✓ Sudoers file created"
echo ""

# Validate sudoers syntax
echo "Validating sudoers syntax..."
if visudo -c -f "$SUDOERS_FILE"; then
    echo "✓ Sudoers file is valid"
    echo ""
    echo "========================================="
    echo -e "${GREEN}✓ Setup complete!${NC}"
    echo "========================================="
    echo ""
    echo "Granted passwordless sudo for kasadis:"
    echo "  - systemctl start/stop/restart/status veeam-smart-backup.service"
    echo "  - veeamconfig job start/stop/list"
    echo "  - journalctl -u veeam-smart-backup.service"
    echo "  - cat /var/log/veeam-smart-backup.log"
    echo ""
    echo "Restic backups (user service - no sudo needed):"
    echo "  - systemctl --user start restic-smart-backup.service"
    echo ""
    echo "Test with:"
    echo "  sudo systemctl status veeam-smart-backup.service"
    echo "  sudo veeamconfig job list"
    echo ""
else
    echo -e "${RED}✗ ERROR: Sudoers file has syntax errors!${NC}"
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
