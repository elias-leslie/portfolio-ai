#!/usr/bin/env bash
# Stop Celery Worker and Beat for Portfolio AI

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Stopping Portfolio AI Celery Services${NC}\n"

# Stop Celery Beat
if [ -f /tmp/portfolio-ai-celery-beat.pid ]; then
    echo -e "${YELLOW}Stopping Celery Beat...${NC}"
    kill $(cat /tmp/portfolio-ai-celery-beat.pid) 2>/dev/null || true
    rm -f /tmp/portfolio-ai-celery-beat.pid
    echo -e "${GREEN}✓ Celery Beat stopped${NC}"
else
    echo -e "${YELLOW}Celery Beat not running (no PID file)${NC}"
    pkill -f "celery.*beat" 2>/dev/null || true
fi

# Stop Celery Worker
if [ -f /tmp/portfolio-ai-celery-worker.pid ]; then
    echo -e "\n${YELLOW}Stopping Celery Worker...${NC}"
    kill $(cat /tmp/portfolio-ai-celery-worker.pid) 2>/dev/null || true
    rm -f /tmp/portfolio-ai-celery-worker.pid
    echo -e "${GREEN}✓ Celery Worker stopped${NC}"
else
    echo -e "${YELLOW}Celery Worker not running (no PID file)${NC}"
    pkill -f "celery.*worker" 2>/dev/null || true
fi

echo -e "\n${GREEN}All Celery services stopped${NC}"
echo -e "${YELLOW}Note: Redis is still running. To stop Redis: redis-cli shutdown${NC}"
