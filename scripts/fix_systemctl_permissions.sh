#!/bin/bash
# Permanent fix for systemctl permissions on portfolio-ai services
# This allows Claude Code to autonomously manage all services via scripts

set -e

echo "================================"
echo "Fixing Portfolio AI Service Permissions"
echo "================================"

# Ensure user is in portfolio-ai group
if ! groups kasadis | grep -q portfolio-ai; then
    echo "Adding kasadis to portfolio-ai group..."
    sudo usermod -a -G portfolio-ai kasadis
else
    echo "✓ User already in portfolio-ai group"
fi

# Create sudoers file for portfolio services (NOPASSWD for all systemctl commands)
echo "Creating sudoers configuration..."
sudo tee /etc/sudoers.d/portfolio-ai > /dev/null <<'EOF'
# Portfolio AI - Allow kasadis to manage services without password
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl start portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl stop portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl restart portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl reload portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl status portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl is-active portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl enable portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl disable portfolio-*
kasadis ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
EOF

# Set correct permissions on sudoers file
sudo chmod 0440 /etc/sudoers.d/portfolio-ai

# Verify sudoers syntax
if sudo visudo -c -f /etc/sudoers.d/portfolio-ai; then
    echo "✓ Sudoers configuration valid"
else
    echo "✗ Sudoers configuration invalid - removing"
    sudo rm /etc/sudoers.d/portfolio-ai
    exit 1
fi

# Ensure all project scripts are executable
echo "Setting script permissions..."
chmod +x ~/portfolio-ai/scripts/*.sh 2>/dev/null || true

# Ensure log directory permissions
if [ -d /var/log/portfolio-ai ]; then
    sudo chown -R kasadis:portfolio-ai /var/log/portfolio-ai
    sudo chmod -R 775 /var/log/portfolio-ai
    echo "✓ Log directory permissions fixed"
fi

# Ensure systemd service files are readable
if [ -d /etc/systemd/system ]; then
    sudo chmod 644 /etc/systemd/system/portfolio-*.service 2>/dev/null || true
    echo "✓ Service files readable"
fi

echo ""
echo "================================"
echo "✓ Permissions Fixed!"
echo "================================"
echo ""
echo "Testing autonomous service control..."
echo ""

# Test that sudo works without password
if sudo -n systemctl is-active portfolio-backend &>/dev/null; then
    echo "✓ Backend service control: WORKING"
else
    echo "⚠ Backend service control: Needs testing"
fi

if sudo -n systemctl is-active portfolio-celery &>/dev/null; then
    echo "✓ Celery service control: WORKING"
else
    echo "⚠ Celery service control: Needs testing"
fi

if sudo -n systemctl is-active portfolio-frontend &>/dev/null; then
    echo "✓ Frontend service control: WORKING"
else
    echo "⚠ Frontend service control: Needs testing"
fi

echo ""
echo "Claude Code can now autonomously manage all services via:"
echo "  - bash ~/portfolio-ai/scripts/start.sh"
echo "  - bash ~/portfolio-ai/scripts/restart.sh"
echo "  - bash ~/portfolio-ai/scripts/shutdown.sh"
echo ""
echo "No sudo password required!"
echo ""
