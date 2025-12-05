#!/bin/bash
# Start all Portfolio AI services via systemd (User Mode)
# All services run as user services (systemctl --user)

set -e

echo "================================"
echo "Starting Portfolio AI Platform"
echo "================================"
echo ""

echo "Starting all services via systemd --user..."
echo ""

# Start backend
echo "Starting Backend API..."
systemctl --user start portfolio-backend.service
sleep 2
if systemctl --user is-active --quiet portfolio-backend.service; then
    echo "✓ Backend API started"
    echo "  URL: http://localhost:8000"
else
    echo "✗ Failed to start Backend API"
    echo "  Check logs: journalctl --user -u portfolio-backend -n 50"
    exit 1
fi
echo ""

# Start Celery services
echo "Starting Celery services..."
systemctl --user start portfolio-celery.service
systemctl --user start portfolio-celery-beat.service
sleep 2

if systemctl --user is-active --quiet portfolio-celery.service; then
    echo "✓ Celery worker started"
else
    echo "✗ Failed to start Celery worker"
    exit 1
fi

if systemctl --user is-active --quiet portfolio-celery-beat.service; then
    echo "✓ Celery beat started"
else
    echo "✗ Failed to start Celery beat"
    exit 1
fi
echo ""

# Start frontend
echo "Starting Frontend..."
systemctl --user start portfolio-frontend.service
sleep 3

if systemctl --user is-active --quiet portfolio-frontend.service; then
    echo "✓ Frontend started"
    echo "  URL: http://localhost:3000"
else
    echo "✗ Failed to start Frontend"
    echo "  Check logs: journalctl --user -u portfolio-frontend -n 50"
    exit 1
fi
echo ""

echo "================================"
echo "✓ All services started!"
echo "================================"
echo ""
echo "Service Status (User Mode):"
echo "  Backend:      $(systemctl --user is-active portfolio-backend.service && echo '✓ Running (http://localhost:8000)' || echo '✗ Stopped')"
echo "  Celery Worker:$(systemctl --user is-active portfolio-celery.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Beat:  $(systemctl --user is-active portfolio-celery-beat.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:     $(systemctl --user is-active portfolio-frontend.service && echo '✓ Running (http://localhost:3000)' || echo '✗ Stopped')"
echo ""
echo "Logs:"
echo "  Backend:      journalctl --user -u portfolio-backend -f"
echo "  Celery Worker:journalctl --user -u portfolio-celery -f"
echo "  Celery Beat:  journalctl --user -u portfolio-celery-beat -f"
echo "  Frontend:     journalctl --user -u portfolio-frontend -f"
echo ""
