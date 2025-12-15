#!/bin/bash
# Setup nginx reverse proxy for Portfolio AI with proper SSL
# This replaces the iptables hack with a production-ready solution
#
# Architecture:
#   Browser (HTTPS:443) → nginx (SSL termination)
#       ├── / → Next.js (HTTP:3000)
#       ├── /api/* → FastAPI (HTTP:8000)
#       └── /_next/webpack-hmr → WebSocket to Next.js
#
# Run with: sudo bash ~/portfolio-ai/scripts/setup-nginx-ssl.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ACTUAL_USER="${SUDO_USER:-$USER}"

echo "=== Portfolio AI - nginx SSL Setup ==="
echo ""
echo "This script will:"
echo "  1. Install nginx"
echo "  2. Remove iptables port forwarding (if present)"
echo "  3. Configure nginx as reverse proxy"
echo "  4. Update frontend to use plain HTTP"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run with sudo"
   exit 1
fi

# Step 1: Install nginx
echo "[1/6] Installing nginx..."
apt-get update -qq
apt-get install -y -qq nginx

# Step 2: Remove iptables port forwarding rules
echo "[2/6] Removing iptables port forwarding..."
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 3000 2>/dev/null || true
iptables -t nat -D OUTPUT -o lo -p tcp --dport 443 -j REDIRECT --to-port 3000 2>/dev/null || true

# Save iptables (remove the rules permanently)
if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save 2>/dev/null || true
fi

# Step 3: Verify SSL certificates exist
echo "[3/6] Checking SSL certificates..."
CERT_FILE="$PROJECT_DIR/certs/localhost.pem"
KEY_FILE="$PROJECT_DIR/certs/localhost-key.pem"

if [[ ! -f "$CERT_FILE" ]] || [[ ! -f "$KEY_FILE" ]]; then
    echo "Error: SSL certificates not found at $PROJECT_DIR/certs/"
    echo "Run 'sudo bash $PROJECT_DIR/scripts/setup-https.sh' first to generate certificates"
    exit 1
fi

# Make certs readable by nginx
chmod 644 "$CERT_FILE"
chmod 640 "$KEY_FILE"
chown root:root "$CERT_FILE" "$KEY_FILE"

# Step 4: Configure nginx
echo "[4/6] Configuring nginx..."

# Remove default site
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Link our config
ln -sf "$PROJECT_DIR/nginx/portfolio-ai.conf" /etc/nginx/sites-available/portfolio-ai
ln -sf /etc/nginx/sites-available/portfolio-ai /etc/nginx/sites-enabled/portfolio-ai

# Test nginx config
nginx -t

# Step 5: Update frontend systemd service to use plain HTTP
echo "[5/6] Updating frontend service..."
FRONTEND_SERVICE="/home/$ACTUAL_USER/.config/systemd/user/portfolio-frontend.service"

if [[ -f "$FRONTEND_SERVICE" ]]; then
    # Check if currently using experimental-https
    if grep -q "experimental-https" "$FRONTEND_SERVICE"; then
        # Create backup
        cp "$FRONTEND_SERVICE" "$FRONTEND_SERVICE.bak"

        # Update to plain HTTP (remove --experimental-https flags)
        sed -i 's/--experimental-https --experimental-https-key [^ ]* --experimental-https-cert [^ ]* //' "$FRONTEND_SERVICE"

        echo "   Updated frontend service to use plain HTTP"
        echo "   (nginx will handle SSL termination)"

        # Reload systemd
        sudo -u "$ACTUAL_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $ACTUAL_USER)" systemctl --user daemon-reload
    else
        echo "   Frontend service already configured for plain HTTP"
    fi
else
    echo "   Warning: Frontend service file not found at $FRONTEND_SERVICE"
fi

# Step 6: Start/restart services
echo "[6/6] Starting services..."

# Start nginx
systemctl enable nginx
systemctl restart nginx

# Restart frontend as user (without HTTPS flags)
echo "   Restarting frontend service..."
sudo -u "$ACTUAL_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $ACTUAL_USER)" systemctl --user restart portfolio-frontend || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "nginx is now handling:"
echo "  - SSL termination on port 443"
echo "  - Routing /api/* to backend (port 8000)"
echo "  - Routing /* to frontend (port 3000)"
echo "  - WebSocket for HMR (hot reload)"
echo ""
echo "Access: https://192.168.8.233"
echo ""
echo "Check status:"
echo "  sudo systemctl status nginx"
echo "  sudo nginx -t"
echo ""
echo "View logs:"
echo "  sudo tail -f /var/log/nginx/portfolio-ai-error.log"
echo ""
