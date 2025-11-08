#!/bin/bash
# Restart all Portfolio AI services via systemd
# USE SYSTEMD FOR EVERYTHING - NO MANUAL PROCESS MANAGEMENT

set -e

echo "================================"
echo "Restarting Portfolio AI Platform"
echo "================================"
echo ""

echo "Restarting all services via systemd..."
echo ""

# Restart all services
sudo systemctl restart portfolio-backend.service
sudo systemctl restart portfolio-celery.service
sudo systemctl restart portfolio-beat.service
sudo systemctl restart portfolio-frontend.service

echo "Waiting for services to start..."
sleep 5

# Check status
echo ""
echo "================================"
echo "✓ Restart complete!"
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
