#!/bin/bash
# Restart all Portfolio AI services via systemd (User Mode)
# ALIGNED WITH PROPER RUNNING PROCEDURE

set -e

START_TIME=$(date +%s)
log_time() {
    local NOW=$(date +%s)
    local ELAPSED=$((NOW - START_TIME))
    echo "[${ELAPSED}s] $1"
}

echo "================================"
echo "Restarting Portfolio AI Platform"
echo "================================"
echo ""

log_time "Cleaning up zombie processes..."
pkill -9 -f "portfolio-ai/frontend.*next dev" || true

log_time "Restarting redis..."
systemctl --user restart portfolio-redis.service
log_time "Restarting backend..."
systemctl --user restart portfolio-backend.service
log_time "Restarting celery..."
systemctl --user restart portfolio-celery.service
log_time "Restarting beat..."
systemctl --user restart portfolio-celery-beat.service
log_time "Restarting frontend..."
systemctl --user restart portfolio-frontend.service
log_time "Restarting dev-companion..."
systemctl --user restart portfolio-dev-companion.service

log_time "Waiting for backend health..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_time "Backend ready"
        break
    fi
    sleep 1
done

log_time "Waiting for frontend port..."
for i in {1..15}; do
    if ss -tlnp | grep -q ':3000'; then
        log_time "Frontend ready"
        break
    fi
    sleep 1
done

# Check status
echo ""
echo "================================"
echo "✓ Restart complete!"
echo "================================"
echo ""
echo "Service Status (User Mode):"
echo "  Redis:        $(systemctl --user is-active portfolio-redis.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Backend:      $(systemctl --user is-active portfolio-backend.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Worker:$(systemctl --user is-active portfolio-celery.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Beat:  $(systemctl --user is-active portfolio-celery-beat.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:     $(systemctl --user is-active portfolio-frontend.service && echo '✓ Running' || echo '✗ Stopped')"
echo "  Dev Companion:$(systemctl --user is-active portfolio-dev-companion.service && echo '✓ Running' || echo '✗ Stopped')"
echo ""
echo "Port Status:"
echo "  Frontend:     $(ss -tlnp | grep -q ':3000' && echo '✓ Port 3000' || echo '✗ Port 3000 not bound')"
echo "  Backend:      $(ss -tlnp | grep -q ':8000' && echo '✓ Port 8000' || echo '✗ Port 8000 not bound')"
echo "  Dev Companion:$(ss -tlnp | grep -q ':9999' && echo '✓ Port 9999' || echo '✗ Port 9999 not bound')"
echo ""
echo "Logs (Unified via Journal):"
echo "  Backend:      journalctl --user -u portfolio-backend -f"
echo "  Celery Worker:journalctl --user -u portfolio-celery -f"
echo "  Celery Beat:  journalctl --user -u portfolio-celery-beat -f"
echo "  Frontend:     journalctl --user -u portfolio-frontend -f"
echo "  Dev Companion:journalctl --user -u portfolio-dev-companion -f"
echo ""
