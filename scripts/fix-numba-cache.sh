#!/bin/bash
# Fix numba caching issue for portfolio-ai service user
# Run as: sudo bash fix-numba-cache.sh

set -e

echo "========================================="
echo "Fix Numba Cache for Service User"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Create cache directory for numba
echo "1. Creating numba cache directory..."
mkdir -p /var/cache/portfolio-ai/numba
chown portfolio-ai:portfolio-ai /var/cache/portfolio-ai/numba
chmod 755 /var/cache/portfolio-ai/numba
echo "   ✓ Created /var/cache/portfolio-ai/numba"
echo ""

# Update backend service file
echo "2. Updating backend service file..."
cat > /etc/systemd/system/portfolio-backend.service << 'EOF'
[Unit]
Description=Portfolio AI Backend (FastAPI)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=portfolio-ai
Group=portfolio-ai
WorkingDirectory=/home/kasadis/portfolio-ai/backend
Environment="PATH=/home/kasadis/portfolio-ai/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="DB_POOL_SIZE=3"
Environment="DB_MAX_OVERFLOW=2"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
EnvironmentFile=-/home/kasadis/portfolio-ai/backend/.env
RuntimeDirectory=portfolio-ai
ExecStart=/home/kasadis/portfolio-ai/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/backend.log
StandardError=append:/var/log/portfolio-ai/backend-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-backend.service"

# Update celery worker service file
echo "3. Updating celery worker service file..."
cat > /etc/systemd/system/portfolio-celery.service << 'EOF'
[Unit]
Description=Portfolio AI Celery Worker
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=portfolio-ai
Group=portfolio-ai
WorkingDirectory=/home/kasadis/portfolio-ai/backend
Environment="PATH=/home/kasadis/portfolio-ai/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
EnvironmentFile=-/home/kasadis/portfolio-ai/backend/.env
RuntimeDirectory=portfolio-ai
ExecStart=/home/kasadis/portfolio-ai/backend/.venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/celery-worker.log
StandardError=append:/var/log/portfolio-ai/celery-worker-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-celery.service"

# Update celery beat service file
echo "4. Updating celery beat service file..."
cat > /etc/systemd/system/portfolio-beat.service << 'EOF'
[Unit]
Description=Portfolio AI Celery Beat Scheduler
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=portfolio-ai
Group=portfolio-ai
WorkingDirectory=/home/kasadis/portfolio-ai/backend
Environment="PATH=/home/kasadis/portfolio-ai/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="NUMBA_CACHE_DIR=/var/cache/portfolio-ai/numba"
EnvironmentFile=-/home/kasadis/portfolio-ai/backend/.env
RuntimeDirectory=portfolio-ai
ExecStart=/home/kasadis/portfolio-ai/backend/.venv/bin/celery -A app.celery_app beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=append:/var/log/portfolio-ai/celery-beat.log
StandardError=append:/var/log/portfolio-ai/celery-beat-error.log

[Install]
WantedBy=multi-user.target
EOF
echo "   ✓ Updated portfolio-beat.service"
echo ""

# Reload systemd
echo "5. Reloading systemd daemon..."
systemctl daemon-reload
echo "   ✓ Systemd reloaded"
echo ""

# Start services
echo "6. Starting services..."
systemctl start portfolio-backend.service
sleep 3
systemctl start portfolio-celery.service
systemctl start portfolio-beat.service
systemctl start portfolio-frontend.service
sleep 3
echo "   ✓ Services started"
echo ""

# Check status
echo "7. Verifying services..."
BACKEND_STATUS=$(systemctl is-active portfolio-backend.service || echo "inactive")
CELERY_STATUS=$(systemctl is-active portfolio-celery.service || echo "inactive")
BEAT_STATUS=$(systemctl is-active portfolio-beat.service || echo "inactive")
FRONTEND_STATUS=$(systemctl is-active portfolio-frontend.service || echo "inactive")

echo "   Backend:       $BACKEND_STATUS"
echo "   Celery Worker: $CELERY_STATUS"
echo "   Celery Beat:   $BEAT_STATUS"
echo "   Frontend:      $FRONTEND_STATUS"
echo ""

if [ "$BACKEND_STATUS" = "active" ] && [ "$CELERY_STATUS" = "active" ] && [ "$BEAT_STATUS" = "active" ] && [ "$FRONTEND_STATUS" = "active" ]; then
    echo "========================================="
    echo "✓ All services running successfully!"
    echo "========================================="
else
    echo "========================================="
    echo "⚠ Some services failed to start"
    echo "========================================="
    echo ""
    echo "Check logs with:"
    echo "  tail -50 /var/log/portfolio-ai/backend-error.log"
    echo "  sudo journalctl -u portfolio-backend.service -n 50"
    exit 1
fi
