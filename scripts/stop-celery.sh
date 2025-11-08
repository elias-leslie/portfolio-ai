#!/usr/bin/env bash
# Stop Celery Worker and Beat via systemd
# USE SYSTEMD - NO MANUAL PROCESS MANAGEMENT

set -euo pipefail

echo "Stopping Celery services via systemd..."

sudo systemctl stop portfolio-celery.service
sudo systemctl stop portfolio-beat.service

echo "✓ Celery services stopped"
