#!/bin/bash
# Restart all Portfolio AI services via systemd (User Mode)
# ALIGNED WITH PROPER RUNNING PROCEDURE

set -e

echo "================================"
echo "Restarting Portfolio AI Platform"
echo "================================"
echo ""

echo "Cleaning up zombie processes..."
pkill -9 -f "portfolio-ai/frontend.*next dev" || true
sleep 2

echo "Restarting all services via systemd --user..."
echo ""

# Restart all services (user mode)
systemctl --user restart portfolio-backend.service
systemctl --user restart portfolio-celery.service
systemctl --user restart portfolio-celery-beat.service
systemctl --user restart portfolio-frontend.service

echo "Waiting for services to start..."
sleep 5

# Check status
echo ""
echo "================================"
echo "✓ Restart complete!"
echo "================================"
echo ""
echo "Service Status (User Mode):"
echo "  Backend:      $(systemctl --user is-active portfolio-backend.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Worker:$(systemctl --user is-active portfolio-celery.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Beat:  $(systemctl --user is-active portfolio-celery-beat.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:     $(systemctl --user is-active portfolio-frontend.service && echo '✓ Running' || echo '✗ Stopped')"
echo ""
echo "Port Status:"
echo "  Frontend:     $(lsof -ti :3000 > /dev/null 2>&1 && echo '✓ Port 3000' || echo '✗ Port 3000 not bound')"
echo "  Backend:      $(lsof -ti :8000 > /dev/null 2>&1 && echo '✓ Port 8000' || echo '✗ Port 8000 not bound')"
echo ""
echo "Logs (Unified via Journal):"
echo "  Backend:      journalctl --user -u portfolio-backend -f"
echo "  Celery Worker:journalctl --user -u portfolio-celery -f"
echo "  Celery Beat:  journalctl --user -u portfolio-beat -f"
echo "  Frontend:     journalctl --user -u portfolio-frontend -f"
echo ""