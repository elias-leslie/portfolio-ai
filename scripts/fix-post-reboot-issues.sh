#!/usr/bin/env bash
#
# fix-post-reboot-issues.sh - Fix issues discovered after service account reboot verification
#
# Issues found during post-reboot verification:
# 1. Frontend .next directory has mixed ownership (kasadis + portfolio-ai)
# 2. HuggingFace transformers cache not configured
# 3. Some frontend subdirectories had restrictive permissions
#
# This script requires sudo for some operations.

set -euo pipefail

echo "==> Post-Reboot Service Account Fixes"
echo ""

# Issue 1: Clean and fix .next directory permissions
echo "1. Fixing frontend .next directory..."
echo "   Stopping frontend service..."
sudo systemctl stop portfolio-frontend

echo "   Removing .next directory (will be recreated)..."
rm -rf /home/kasadis/portfolio-ai/frontend/.next

echo "   Frontend will recreate .next on next start with correct ownership"
echo ""

# Issue 2: Fix frontend app/ directory permissions
echo "2. Fixing frontend app/ and components/ permissions..."
chmod -R g+rX /home/kasadis/portfolio-ai/frontend/app
chmod -R g+rX /home/kasadis/portfolio-ai/frontend/components
echo "   ✓ Group read+execute permissions added"
echo ""

# Issue 3: Create HuggingFace cache directory
echo "3. Creating HuggingFace transformers cache..."
sudo mkdir -p /var/cache/portfolio-ai/huggingface
sudo chown -R portfolio-ai:portfolio-ai /var/cache/portfolio-ai/huggingface
sudo chmod 755 /var/cache/portfolio-ai/huggingface
echo "   ✓ Created /var/cache/portfolio-ai/huggingface"
ls -ld /var/cache/portfolio-ai/huggingface
echo ""

# Issue 4: Update systemd service files with TRANSFORMERS_CACHE
echo "4. Updating systemd service files..."

# Backend service
echo "   Updating portfolio-backend.service..."
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-backend.service

# Celery worker service
echo "   Updating portfolio-celery.service..."
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-celery.service

# Celery beat service (also uses transformers for sentiment analysis)
echo "   Updating portfolio-beat.service..."
sudo sed -i '/Environment="NUMBA_CACHE_DIR/a Environment="TRANSFORMERS_CACHE=/var/cache/portfolio-ai/huggingface"' \
    /etc/systemd/system/portfolio-beat.service

echo "   ✓ Added TRANSFORMERS_CACHE environment variable"
echo ""

# Reload systemd
echo "5. Reloading systemd configuration..."
sudo systemctl daemon-reload
echo "   ✓ Systemd reloaded"
echo ""

# Restart services
echo "6. Restarting services..."
sudo systemctl restart portfolio-backend
sudo systemctl restart portfolio-celery
sudo systemctl restart portfolio-beat
sudo systemctl start portfolio-frontend
echo "   ✓ All services restarted"
echo ""

# Verify services
echo "7. Verifying service status..."
sleep 5
systemctl is-active portfolio-backend portfolio-celery portfolio-beat portfolio-frontend

echo ""
echo "==> Verification complete!"
echo ""
echo "Next steps:"
echo "1. Check logs: tail -f /var/log/portfolio-ai/*.log"
echo "2. Test backend: curl http://localhost:8000/health"
echo "3. Test frontend: curl -I http://localhost:3000"
echo "4. Verify no HuggingFace cache errors in logs"
echo ""
