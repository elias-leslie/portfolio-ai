#!/bin/bash
# Fix Tailscale frontend 500 error - Clear Turbopack cache and restart
# Run with: sudo bash scripts/fix-tailscale-frontend.sh

set -e

echo "================================"
echo "Fixing Tailscale Frontend Error"
echo "================================"
echo ""

# Stop frontend service
echo "1. Stopping frontend service..."
systemctl stop portfolio-frontend
sleep 2

# Clear .next cache as portfolio-ai user
echo "2. Clearing Turbopack cache (.next directory)..."
sudo -u portfolio-ai bash -c "cd /home/kasadis/portfolio-ai/frontend && rm -rf .next"
echo "   ✓ Cache cleared"

# Clear node_modules cache (optional but helpful)
echo "3. Clearing node module cache..."
sudo -u portfolio-ai bash -c "cd /home/kasadis/portfolio-ai/frontend && npm cache clean --force" || echo "   (cache clean failed, continuing...)"

# Fix any permission issues on frontend directory
echo "4. Fixing frontend directory permissions..."
chown -R portfolio-ai:portfolio-ai /home/kasadis/portfolio-ai/frontend
chmod -R 755 /home/kasadis/portfolio-ai/frontend
echo "   ✓ Permissions fixed"

# Start frontend service
echo "5. Starting frontend service..."
systemctl start portfolio-frontend
sleep 8

# Check status
echo ""
echo "================================"
echo "Service Status Check"
echo "================================"
systemctl is-active portfolio-frontend && echo "✓ Frontend is active" || echo "✗ Frontend failed to start"

echo ""
echo "Testing Tailscale URL..."
sleep 5
curl -I http://100.123.190.81:3000 2>&1 | head -3

echo ""
echo "================================"
echo "Fix Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Wait 10 seconds for Turbopack to fully compile"
echo "  2. Test in your browser: http://100.123.190.81:3000"
echo "  3. Check logs if still broken: tail -f /var/log/portfolio-ai/frontend-error.log"
echo ""
