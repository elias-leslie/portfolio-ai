#!/bin/bash
# Setup trusted local HTTPS certificates using mkcert
# Run with: sudo bash ~/portfolio-ai/scripts/setup-https.sh

set -e

echo "=== Portfolio AI Local HTTPS Setup ==="
echo ""

ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
CERTS_DIR="$ACTUAL_HOME/portfolio-ai/certs"

# Install dependencies
echo "[1/4] Installing dependencies..."
apt-get update -qq
apt-get install -y -qq libnss3-tools curl

# Install mkcert
if ! command -v mkcert &> /dev/null; then
    echo "[2/4] Installing mkcert..."
    curl -sJLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
    chmod +x mkcert-v*-linux-amd64
    mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
else
    echo "[2/4] mkcert already installed"
fi

# Install local CA (as actual user)
echo "[3/4] Installing local CA..."
sudo -u "$ACTUAL_USER" mkcert -install

# Generate certificates
echo "[4/4] Generating certificates..."
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"
rm -f localhost-key.pem localhost.pem 2>/dev/null || true
sudo -u "$ACTUAL_USER" mkcert -key-file localhost-key.pem -cert-file localhost.pem \
    192.168.8.233 localhost 127.0.0.1

# Export CA cert for Windows
CA_CERT=$(sudo -u "$ACTUAL_USER" mkcert -CAROOT)/rootCA.pem
cp "$CA_CERT" "$CERTS_DIR/rootCA.pem"
chown "$ACTUAL_USER:$ACTUAL_USER" "$CERTS_DIR/rootCA.pem"

# Setup port forwarding: 443 -> 3000 (so no port needed in URL)
echo "[5/5] Setting up port forwarding (443 -> 3000)..."
iptables -t nat -D PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 3000 2>/dev/null || true
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 3000
iptables -t nat -D OUTPUT -o lo -p tcp --dport 443 -j REDIRECT --to-port 3000 2>/dev/null || true
iptables -t nat -A OUTPUT -o lo -p tcp --dport 443 -j REDIRECT --to-port 3000

# Make iptables rules persistent
if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save
else
    apt-get install -y -qq iptables-persistent
    netfilter-persistent save
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Linux browser: Restart browser, then https://192.168.8.233 works"
echo ""
echo "Windows browser setup:"
echo "  1. Copy this file to Windows: $CERTS_DIR/rootCA.pem"
echo "  2. Double-click it -> Install Certificate"
echo "  3. Choose 'Local Machine' -> 'Trusted Root Certification Authorities'"
echo "  4. Restart browser"
echo ""
echo "Access: https://192.168.8.233 (no port needed!)"
echo ""
echo "Next: bash ~/portfolio-ai/scripts/restart.sh"
