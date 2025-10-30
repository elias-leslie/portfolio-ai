#!/bin/bash
# Check status of all Portfolio AI services
#
# Usage: bash ~/portfolio-ai/scripts/status.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "================================"
echo "Portfolio AI Service Status"
echo "================================"
echo ""

ERRORS=0

# Check Redis
echo -n "Redis:         "
if pgrep -x redis-server > /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responding${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Backend
echo -n "Backend API:   "
if pgrep -f "uvicorn.*main:app" > /dev/null; then
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running (http://localhost:8000)${NC}"
    else
        echo -e "${YELLOW}⚠ Running but health check failed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Celery Worker
echo -n "Celery Worker: "
if pgrep -f "celery.*worker" > /dev/null; then
    WORKER_COUNT=$(pgrep -f "celery.*worker" | wc -l)
    echo -e "${GREEN}✓ Running ($WORKER_COUNT processes)${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Celery Beat
echo -n "Celery Beat:   "
if pgrep -f "celery.*beat" > /dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Frontend
echo -n "Frontend:      "
if pgrep -f "next.*dev" > /dev/null; then
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running (http://localhost:3000)${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responding${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "================================"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All services running${NC}"
    echo ""
    echo "URLs:"
    echo "  - Backend API: http://localhost:8000"
    echo "  - API Docs:    http://localhost:8000/docs"
    echo "  - Frontend:    http://localhost:3000"
else
    echo -e "${RED}⚠ $ERRORS service(s) not running properly${NC}"
    echo ""
    echo "To start all services: bash ~/portfolio-ai/scripts/restart.sh"
fi

echo ""
echo "Logs:"
echo "  - Backend:      tail -f /tmp/portfolio-backend.log"
echo "  - Celery Worker:tail -f /tmp/portfolio-celery-worker.log"
echo "  - Celery Beat:  tail -f /tmp/portfolio-celery-beat.log"
echo "  - Frontend:     tail -f /tmp/portfolio-frontend.log"
echo ""

exit $ERRORS
