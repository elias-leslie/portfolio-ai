#!/bin/bash
# Setup Cloudflare Zero Trust Tunnel for Portfolio AI
# Run with: sudo bash ~/portfolio-ai/scripts/setup-cloudflare-zero-trust.sh <team-name> <tunnel-name>
#
# Prerequisites:
# 1. Create free Cloudflare account at https://dash.cloudflare.com/sign-up
# 2. Go to Zero Trust dashboard: https://one.dash.cloudflare.com
# 3. Create a team (pick a team name like "kasadis" -> kasadis.cloudflareaccess.com)

set -e

echo "=== Portfolio AI Cloudflare Zero Trust Setup ==="
echo ""

if [ -z "$1" ]; then
    echo "Usage: sudo bash $0 <tunnel-name>"
    echo ""
    echo "Prerequisites (do these first):"
    echo "1. Create free Cloudflare account: https://dash.cloudflare.com/sign-up"
    echo "2. Go to Zero Trust: https://one.dash.cloudflare.com"
    echo "3. Create your team (e.g., 'kasadis' -> kasadis.cloudflareaccess.com)"
    echo ""
    echo "Then run: sudo bash $0 portfolio-ai"
    exit 1
fi

TUNNEL_NAME="$1"
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)

# Install cloudflared if not present
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared.deb
    rm cloudflared.deb
fi
echo "cloudflared version: $(cloudflared --version)"

# Check if already logged in
CRED_DIR="$ACTUAL_HOME/.cloudflared"
if [ ! -f "$CRED_DIR/cert.pem" ]; then
    echo ""
    echo "=== Step 1: Login to Cloudflare ==="
    echo "A browser window will open. Log in to your Cloudflare account."
    echo ""
    sudo -u "$ACTUAL_USER" cloudflared tunnel login
fi

# Create tunnel if it doesn't exist
echo ""
echo "=== Step 2: Create Tunnel ==="
TUNNEL_ID=$(sudo -u "$ACTUAL_USER" cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}' || true)

if [ -z "$TUNNEL_ID" ]; then
    echo "Creating tunnel: $TUNNEL_NAME"
    sudo -u "$ACTUAL_USER" cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(sudo -u "$ACTUAL_USER" cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
else
    echo "Tunnel already exists: $TUNNEL_NAME ($TUNNEL_ID)"
fi

# Create config file
echo ""
echo "=== Step 3: Configure Tunnel ==="
CONFIG_FILE="$CRED_DIR/config.yml"

cat > "$CONFIG_FILE" << EOF
tunnel: $TUNNEL_ID
credentials-file: $CRED_DIR/$TUNNEL_ID.json

ingress:
  # Frontend (Next.js)
  - hostname: portfolio.$TUNNEL_NAME.cloudflareaccess.com
    service: http://localhost:3000
  # Backend API (optional, if you want direct API access)
  - hostname: api.$TUNNEL_NAME.cloudflareaccess.com
    service: http://localhost:8000
  # Catch-all (required)
  - service: http_status:404
EOF
chown "$ACTUAL_USER:$ACTUAL_USER" "$CONFIG_FILE"

echo "Config written to: $CONFIG_FILE"

# Create DNS routes
echo ""
echo "=== Step 4: Create DNS Routes ==="
echo "Creating DNS record for portfolio.$TUNNEL_NAME.cloudflareaccess.com..."
sudo -u "$ACTUAL_USER" cloudflared tunnel route dns "$TUNNEL_NAME" "portfolio.$TUNNEL_NAME" 2>/dev/null || echo "(Route may already exist)"

echo "Creating DNS record for api.$TUNNEL_NAME.cloudflareaccess.com..."
sudo -u "$ACTUAL_USER" cloudflared tunnel route dns "$TUNNEL_NAME" "api.$TUNNEL_NAME" 2>/dev/null || echo "(Route may already exist)"

# Install as system service
echo ""
echo "=== Step 5: Install Service ==="
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared

# Save info
INFO_FILE="$ACTUAL_HOME/portfolio-ai/certs/tunnel-info.txt"
mkdir -p "$(dirname "$INFO_FILE")"
cat > "$INFO_FILE" << EOF
Cloudflare Zero Trust Tunnel
============================
Tunnel Name: $TUNNEL_NAME
Tunnel ID: $TUNNEL_ID

URLs:
  Frontend: https://portfolio.$TUNNEL_NAME.cloudflareaccess.com
  Backend:  https://api.$TUNNEL_NAME.cloudflareaccess.com

Config: $CONFIG_FILE

Commands:
  Status:  sudo systemctl status cloudflared
  Logs:    sudo journalctl -u cloudflared -f
  Restart: sudo systemctl restart cloudflared
EOF
chown "$ACTUAL_USER:$ACTUAL_USER" "$INFO_FILE"

echo ""
echo "=== Setup Complete ==="
echo ""
cat "$INFO_FILE"
echo ""
echo "Access your app at the Frontend URL above!"
