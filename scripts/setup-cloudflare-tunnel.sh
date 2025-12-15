#!/bin/bash
# Setup Cloudflare Tunnel for Portfolio AI
# Run with: sudo bash ~/portfolio-ai/scripts/setup-cloudflare-tunnel.sh

set -e

echo "=== Portfolio AI Cloudflare Tunnel Setup ==="
echo ""

ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)

# Install cloudflared if not present
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    dpkg -i cloudflared.deb
    rm cloudflared.deb
    echo "cloudflared installed: $(cloudflared --version)"
else
    echo "cloudflared already installed: $(cloudflared --version)"
fi

# Create systemd service for the tunnel
echo "Creating systemd service..."

cat > /etc/systemd/system/cloudflare-tunnel.service << EOF
[Unit]
Description=Cloudflare Tunnel for Portfolio AI
After=network.target portfolio-frontend.service
Wants=portfolio-frontend.service

[Service]
Type=simple
User=$ACTUAL_USER
ExecStart=/usr/bin/cloudflared tunnel --url http://localhost:3000 --metrics localhost:33333
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cloudflare-tunnel

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable service
systemctl daemon-reload
systemctl enable cloudflare-tunnel.service
systemctl start cloudflare-tunnel.service

# Wait for tunnel to establish and get URL
echo ""
echo "Starting tunnel (waiting for URL)..."
sleep 5

# Get the tunnel URL from metrics endpoint
TUNNEL_URL=""
for i in {1..10}; do
    TUNNEL_URL=$(curl -s http://localhost:33333/metrics 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 2
done

# Also try to get from journal if metrics didn't work
if [ -z "$TUNNEL_URL" ]; then
    TUNNEL_URL=$(journalctl -u cloudflare-tunnel.service -n 50 --no-pager 2>/dev/null | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1 || true)
fi

echo ""
echo "=== Setup Complete ==="
echo ""

if [ -n "$TUNNEL_URL" ]; then
    echo "Your public URL: $TUNNEL_URL"
    echo ""
    # Save URL for reference
    echo "$TUNNEL_URL" > "$ACTUAL_HOME/portfolio-ai/certs/tunnel-url.txt"
    chown "$ACTUAL_USER:$ACTUAL_USER" "$ACTUAL_HOME/portfolio-ai/certs/tunnel-url.txt"
else
    echo "Tunnel is starting... Get URL with:"
    echo "  journalctl -u cloudflare-tunnel.service | grep trycloudflare"
fi

echo ""
echo "The tunnel runs as a system service and survives reboots."
echo ""
echo "Commands:"
echo "  Status:  sudo systemctl status cloudflare-tunnel"
echo "  Logs:    sudo journalctl -u cloudflare-tunnel -f"
echo "  Restart: sudo systemctl restart cloudflare-tunnel"
echo "  Stop:    sudo systemctl stop cloudflare-tunnel"
echo ""
echo "Note: The URL changes each time the tunnel restarts."
echo "For a permanent URL, create a free Cloudflare account and"
echo "set up a named tunnel (still free, just needs login)."
