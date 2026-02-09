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

# Start Hatchet worker
echo "Starting Hatchet worker..."
systemctl --user start portfolio-hatchet-worker.service
sleep 2

if systemctl --user is-active --quiet portfolio-hatchet-worker.service; then
    echo "✓ Hatchet worker started"
else
    echo "✗ Failed to start Hatchet worker"
    echo "  Check logs: journalctl --user -u portfolio-hatchet-worker -n 50"
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
echo "  Backend:        $(systemctl --user is-active portfolio-backend.service && echo '✓ Running (http://localhost:8000)' || echo '✗ Stopped')"
echo "  Hatchet Worker: $(systemctl --user is-active portfolio-hatchet-worker.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:       $(systemctl --user is-active portfolio-frontend.service && echo '✓ Running (http://localhost:3000)' || echo '✗ Stopped')"
echo ""
echo "Logs:"
echo "  Backend:        journalctl --user -u portfolio-backend -f"
echo "  Hatchet Worker: journalctl --user -u portfolio-hatchet-worker -f"
echo "  Frontend:       journalctl --user -u portfolio-frontend -f"
echo ""
