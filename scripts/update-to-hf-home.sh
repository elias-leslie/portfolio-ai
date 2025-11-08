#!/usr/bin/env bash
# Update from TRANSFORMERS_CACHE to HF_HOME (recommended by transformers library)

set -euo pipefail

echo "==> Updating to HF_HOME (future-proof)"
echo ""

# 1. Update systemd service files
echo "1. Updating systemd service files..."

# Backend - replace TRANSFORMERS_CACHE with HF_HOME
sudo sed -i 's/Environment="TRANSFORMERS_CACHE=/Environment="HF_HOME=/' \
    /etc/systemd/system/portfolio-backend.service

# Celery worker
sudo sed -i 's/Environment="TRANSFORMERS_CACHE=/Environment="HF_HOME=/' \
    /etc/systemd/system/portfolio-celery.service

# Celery beat
sudo sed -i 's/Environment="TRANSFORMERS_CACHE=/Environment="HF_HOME=/' \
    /etc/systemd/system/portfolio-beat.service

echo "   ✓ Replaced TRANSFORMERS_CACHE with HF_HOME in all services"
echo ""

# 2. Verify changes
echo "2. Verifying changes..."
grep "HF_HOME" /etc/systemd/system/portfolio-backend.service
grep "HF_HOME" /etc/systemd/system/portfolio-celery.service
grep "HF_HOME" /etc/systemd/system/portfolio-beat.service
echo ""

# 3. Reload systemd
echo "3. Reloading systemd..."
sudo systemctl daemon-reload
echo "   ✓ Reloaded"
echo ""

# 4. Restart backend services only
echo "4. Restarting backend services..."
sudo systemctl restart portfolio-backend portfolio-celery portfolio-beat
echo "   ✓ Restarted"
echo ""

# 5. Verify
echo "5. Waiting for backend to start..."
sleep 5
curl -s http://localhost:8000/health | jq '.status'
echo ""

echo "==> ✅ Updated to HF_HOME successfully!"
