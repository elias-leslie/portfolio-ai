#!/bin/bash
# Setup DuckDNS + Let's Encrypt for Portfolio AI
# Run with: sudo bash ~/portfolio-ai/scripts/setup-duckdns-https.sh

set -e

echo "=== Portfolio AI DuckDNS + Let's Encrypt Setup ==="
echo ""

# Check for required arguments
if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: sudo bash $0 <duckdns-subdomain> <duckdns-token>"
    echo ""
    echo "Steps to get these:"
    echo "1. Go to https://www.duckdns.org"
    echo "2. Sign in with Google/GitHub/etc"
    echo "3. Create a subdomain (e.g., 'portfolio-ai' gives you portfolio-ai.duckdns.org)"
    echo "4. Copy your token from the DuckDNS page"
    echo ""
    echo "Example: sudo bash $0 portfolio-ai xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    exit 1
fi

SUBDOMAIN="$1"
TOKEN="$2"
DOMAIN="${SUBDOMAIN}.duckdns.org"
LOCAL_IP="192.168.8.233"

ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(getent passwd "$ACTUAL_USER" | cut -d: -f6)
CERTS_DIR="$ACTUAL_HOME/portfolio-ai/certs"

echo "Subdomain: $DOMAIN"
echo "Local IP: $LOCAL_IP"
echo ""

# Install certbot if needed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update -qq
    apt-get install -y certbot
fi

# Update DuckDNS to point to local IP
echo "Updating DuckDNS to point $DOMAIN -> $LOCAL_IP..."
RESPONSE=$(curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${TOKEN}&ip=${LOCAL_IP}")
if [ "$RESPONSE" != "OK" ]; then
    echo "ERROR: DuckDNS update failed. Response: $RESPONSE"
    echo "Check your subdomain and token."
    exit 1
fi
echo "DuckDNS updated successfully!"

# Create hook scripts for DNS challenge
HOOKS_DIR="$CERTS_DIR/hooks"
mkdir -p "$HOOKS_DIR"

# Auth hook - adds TXT record
cat > "$HOOKS_DIR/auth-hook.sh" << 'AUTHEOF'
#!/bin/bash
SUBDOMAIN="__SUBDOMAIN__"
TOKEN="__TOKEN__"
curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${TOKEN}&txt=${CERTBOT_VALIDATION}" > /dev/null
# Wait for DNS propagation
sleep 30
AUTHEOF
sed -i "s/__SUBDOMAIN__/$SUBDOMAIN/g" "$HOOKS_DIR/auth-hook.sh"
sed -i "s/__TOKEN__/$TOKEN/g" "$HOOKS_DIR/auth-hook.sh"
chmod +x "$HOOKS_DIR/auth-hook.sh"

# Cleanup hook - clears TXT record
cat > "$HOOKS_DIR/cleanup-hook.sh" << 'CLEANEOF'
#!/bin/bash
SUBDOMAIN="__SUBDOMAIN__"
TOKEN="__TOKEN__"
curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${TOKEN}&txt=removed&clear=true" > /dev/null
CLEANEOF
sed -i "s/__SUBDOMAIN__/$SUBDOMAIN/g" "$HOOKS_DIR/cleanup-hook.sh"
sed -i "s/__TOKEN__/$TOKEN/g" "$HOOKS_DIR/cleanup-hook.sh"
chmod +x "$HOOKS_DIR/cleanup-hook.sh"

# Get Let's Encrypt certificate via DNS challenge
echo ""
echo "Requesting Let's Encrypt certificate..."
certbot certonly \
    --manual \
    --preferred-challenges dns \
    --manual-auth-hook "$HOOKS_DIR/auth-hook.sh" \
    --manual-cleanup-hook "$HOOKS_DIR/cleanup-hook.sh" \
    --agree-tos \
    --no-eff-email \
    --register-unsafely-without-email \
    -d "$DOMAIN" \
    --non-interactive

# Copy certs to portfolio-ai directory
echo "Copying certificates..."
cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERTS_DIR/localhost-key.pem"
cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERTS_DIR/localhost.pem"
chown "$ACTUAL_USER:$ACTUAL_USER" "$CERTS_DIR/localhost-key.pem" "$CERTS_DIR/localhost.pem"
chmod 600 "$CERTS_DIR/localhost-key.pem"
chmod 644 "$CERTS_DIR/localhost.pem"

# Save domain config for renewal
cat > "$CERTS_DIR/duckdns.conf" << EOF
SUBDOMAIN=$SUBDOMAIN
TOKEN=$TOKEN
DOMAIN=$DOMAIN
EOF
chown "$ACTUAL_USER:$ACTUAL_USER" "$CERTS_DIR/duckdns.conf"
chmod 600 "$CERTS_DIR/duckdns.conf"

# Create renewal script
cat > "$ACTUAL_HOME/portfolio-ai/scripts/renew-cert.sh" << 'RENEWEOF'
#!/bin/bash
# Renew Let's Encrypt certificate
sudo certbot renew --quiet
CERTS_DIR="$HOME/portfolio-ai/certs"
source "$CERTS_DIR/duckdns.conf"
sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$CERTS_DIR/localhost-key.pem"
sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$CERTS_DIR/localhost.pem"
sudo chown $USER:$USER "$CERTS_DIR/localhost-key.pem" "$CERTS_DIR/localhost.pem"
bash ~/portfolio-ai/scripts/restart.sh
RENEWEOF
chmod +x "$ACTUAL_HOME/portfolio-ai/scripts/renew-cert.sh"
chown "$ACTUAL_USER:$ACTUAL_USER" "$ACTUAL_HOME/portfolio-ai/scripts/renew-cert.sh"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Your domain: https://$DOMAIN:3000"
echo "Certificate valid for 90 days (auto-renewal via certbot)"
echo ""
echo "Next steps:"
echo "1. Run: bash ~/portfolio-ai/scripts/restart.sh"
echo "2. Access: https://$DOMAIN:3000"
echo ""
echo "To renew manually: bash ~/portfolio-ai/scripts/renew-cert.sh"
