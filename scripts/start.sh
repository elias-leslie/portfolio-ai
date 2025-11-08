#!/bin/bash
# Start all Portfolio AI services via systemd
# USE SYSTEMD FOR EVERYTHING - NO MANUAL PROCESS MANAGEMENT

set -e

echo "================================"
echo "Starting Portfolio AI Platform"
echo "================================"
echo ""

echo "Starting all services via systemd..."
echo ""

# Start backend
echo "Starting Backend API..."
sudo systemctl start portfolio-backend.service
sleep 2
if sudo systemctl is-active --quiet portfolio-backend.service; then
    echo "✓ Backend API started"
    echo "  URL: http://localhost:8000"
else
    echo "✗ Failed to start Backend API"
    echo "  Check logs: sudo journalctl -u portfolio-backend -n 50"
    exit 1
fi
echo ""

# Start Celery services
echo "Starting Celery services..."
sudo systemctl start portfolio-celery.service
sudo systemctl start portfolio-beat.service
sleep 2

if sudo systemctl is-active --quiet portfolio-celery.service; then
    echo "✓ Celery worker started"
else
    echo "✗ Failed to start Celery worker"
    exit 1
fi

if sudo systemctl is-active --quiet portfolio-beat.service; then
    echo "✓ Celery beat started"
else
    echo "✗ Failed to start Celery beat"
    exit 1
fi
echo ""

# Start frontend
echo "Starting Frontend..."
sudo systemctl start portfolio-frontend.service
sleep 3

if sudo systemctl is-active --quiet portfolio-frontend.service; then
    echo "✓ Frontend started"
    echo "  URL: http://localhost:3000"
else
    echo "✗ Failed to start Frontend"
    echo "  Check logs: sudo journalctl -u portfolio-frontend -n 50"
    exit 1
fi
echo ""

echo "================================"
echo "✓ All services started!"
echo "================================"
echo ""
echo "Service Status:"
echo "  Backend:      $(sudo systemctl is-active portfolio-backend.service && echo '✓ Running (http://localhost:8000)' || echo '✗ Stopped')"
echo "  Celery Worker:$(sudo systemctl is-active portfolio-celery.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Beat:  $(sudo systemctl is-active portfolio-beat.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:     $(sudo systemctl is-active portfolio-frontend.service && echo '✓ Running (http://localhost:3000)' || echo '✗ Stopped')"
echo ""
echo "Logs:"
echo "  Backend:      sudo journalctl -u portfolio-backend -f"
echo "  Celery Worker:sudo journalctl -u portfolio-celery -f"
echo "  Celery Beat:  sudo journalctl -u portfolio-beat -f"
echo "  Frontend:     sudo journalctl -u portfolio-frontend -f"
echo ""
