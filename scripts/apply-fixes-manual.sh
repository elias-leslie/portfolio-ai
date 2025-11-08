#!/usr/bin/env bash
# Manual fix application (requires sudo)
# Run this script to complete the post-reboot fixes

set -euo pipefail

echo "==> Applying Post-Reboot Fixes (Manual)"
echo ""

# 1. Stop frontend service
echo "1. Stopping frontend service..."
sudo systemctl stop portfolio-frontend
echo "   ✓ Frontend stopped"
echo ""

# 2. Create HuggingFace cache directory
echo "2. Creating HuggingFace cache directory..."
sudo mkdir -p /var/cache/portfolio-ai/huggingface
sudo chown portfolio-ai:portfolio-ai /var/cache/portfolio-ai/huggingface
sudo chmod 755 /var/cache/portfolio-ai/huggingface
echo "   ✓ Cache directory created:"
ls -ld /var/cache/portfolio-ai/huggingface
echo ""

# 3. Update systemd service files
echo "3. Updating systemd service files..."

# Backend service
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-backend.service

# Celery worker service
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-celery.service

# Celery beat service
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-beat.service

echo "   ✓ Added TRANSFORMERS_CACHE to all 3 services"
echo ""

# 4. Reload systemd
echo "4. Reloading systemd configuration..."
sudo systemctl daemon-reload
echo "   ✓ Systemd reloaded"
echo ""

# 5. Restart services
echo "5. Restarting services..."
sudo systemctl restart portfolio-backend
sudo systemctl restart portfolio-celery
sudo systemctl restart portfolio-beat
sudo systemctl start portfolio-frontend
echo "   ✓ All services restarted"
echo ""

# 6. Wait for services to start
echo "6. Waiting for services to start..."
sleep 10
echo ""

# 7. Verify services
echo "7. Verifying service status..."
systemctl is-active portfolio-backend portfolio-celery portfolio-beat portfolio-frontend
echo ""

# 8. Test backend
echo "8. Testing backend health..."
curl -s http://localhost:8000/health | jq '.status'
echo ""

# 9. Test frontend (may take a moment to compile)
echo "9. Testing frontend (waiting 15 seconds for Next.js compilation)..."
sleep 15
curl -sI http://localhost:3000 | head -3
echo ""

# 10. Check for cache errors
echo "10. Checking logs for cache errors..."
echo "Backend errors:"
grep -i "cache" /var/log/portfolio-ai/backend-error.log | tail -5 || echo "   No cache errors"
echo ""
echo "Celery errors:"
grep -i "cache" /var/log/portfolio-ai/celery-worker-error.log | tail -5 || echo "   No cache errors"
echo ""

echo "==> ✅ Fixes Applied Successfully!"
echo ""
echo "Verification:"
echo "- Services active: $(systemctl is-active portfolio-backend portfolio-celery portfolio-beat portfolio-frontend | tr '\n' ' ')"
echo "- Backend health: $(curl -s http://localhost:8000/health | jq -r '.status')"
echo ""
echo "Next steps:"
echo "1. Browse to http://192.168.8.233:3000 to verify frontend loads"
echo "2. Check watchlist page for functionality"
echo "3. Monitor logs for any remaining errors"
echo ""
