#!/bin/bash
# Stop all Portfolio AI services via systemd (User Mode)
# All services run as user services (systemctl --user)

set -e

echo "================================"
echo "Stopping Portfolio AI Platform"
echo "================================"
echo ""

echo "Stopping all services via systemd --user..."

systemctl --user stop portfolio-frontend.service
systemctl --user stop portfolio-celery-beat.service
systemctl --user stop portfolio-celery.service
systemctl --user stop portfolio-backend.service

echo ""
echo "✓ All services stopped"
echo ""
echo "Service Status (User Mode):"
echo "  Backend:      $(systemctl --user is-active portfolio-backend.service 2>/dev/null || echo 'stopped')"
echo "  Celery Worker:$(systemctl --user is-active portfolio-celery.service 2>/dev/null || echo 'stopped')"
echo "  Celery Beat:  $(systemctl --user is-active portfolio-celery-beat.service 2>/dev/null || echo 'stopped')"
echo "  Frontend:     $(systemctl --user is-active portfolio-frontend.service 2>/dev/null || echo 'stopped')"
echo ""
echo "Note: Redis and PostgreSQL are still running (system services)"
echo ""
