#!/usr/bin/env bash
# Start Celery Worker and Beat for Portfolio AI
# This script ensures Redis is running and starts both Celery services

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting Portfolio AI Celery Services${NC}\n"

# Check if Redis is running
if ! redis-cli ping >/dev/null 2>&1; then
    echo -e "${YELLOW}Redis not running, starting Redis...${NC}"
    redis-server --daemonize yes
    sleep 2
    if redis-cli ping >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis started${NC}"
    else
        echo -e "${RED}✗ Failed to start Redis${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Redis already running${NC}"
fi

# Change to backend directory
cd ~/portfolio-ai/backend

# Activate virtual environment
source .venv/bin/activate

# Start Celery Worker with concurrency=1 to avoid DuckDB lock conflicts
echo -e "\n${YELLOW}Starting Celery Worker...${NC}"
celery -A app.celery_app worker \
    --loglevel=info \
    --logfile=/tmp/portfolio-ai-celery-worker.log \
    --pidfile=/tmp/portfolio-ai-celery-worker.pid \
    --concurrency=1 \
    --detach

if [ -f /tmp/portfolio-ai-celery-worker.pid ]; then
    echo -e "${GREEN}✓ Celery Worker started (PID: $(cat /tmp/portfolio-ai-celery-worker.pid))${NC}"
else
    echo -e "${RED}✗ Failed to start Celery Worker${NC}"
    exit 1
fi

# Start Celery Beat
echo -e "\n${YELLOW}Starting Celery Beat Scheduler...${NC}"
celery -A app.celery_app beat \
    --loglevel=info \
    --logfile=/tmp/portfolio-ai-celery-beat.log \
    --pidfile=/tmp/portfolio-ai-celery-beat.pid \
    --detach

if [ -f /tmp/portfolio-ai-celery-beat.pid ]; then
    echo -e "${GREEN}✓ Celery Beat started (PID: $(cat /tmp/portfolio-ai-celery-beat.pid))${NC}"
else
    echo -e "${RED}✗ Failed to start Celery Beat${NC}"
    exit 1
fi

echo -e "\n${GREEN}All services started successfully!${NC}"
echo -e "\n${YELLOW}To check status:${NC}"
echo -e "  redis-cli ping"
echo -e "  ps aux | grep celery"
echo -e "\n${YELLOW}To view logs:${NC}"
echo -e "  tail -f /tmp/portfolio-ai-celery-worker.log"
echo -e "  tail -f /tmp/portfolio-ai-celery-beat.log"
