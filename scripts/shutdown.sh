#!/bin/bash
# Stop all Portfolio AI services via systemd
# USE SYSTEMD FOR EVERYTHING - NO MANUAL PROCESS MANAGEMENT

set -e

echo "================================"
echo "Stopping Portfolio AI Platform"
echo "================================"
echo ""

echo "Stopping all services via systemd..."

sudo systemctl stop portfolio-frontend.service
sudo systemctl stop portfolio-beat.service
sudo systemctl stop portfolio-celery.service
sudo systemctl stop portfolio-backend.service

echo ""
echo "✓ All services stopped"
echo ""
echo "Note: Redis is still running. To stop Redis: sudo systemctl stop redis-server"
echo ""
