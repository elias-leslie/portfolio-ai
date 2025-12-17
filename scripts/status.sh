#!/bin/bash
# Check status of all Portfolio AI services (User Mode)
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

# Check Redis (system service)
echo -n "Redis:         "
if systemctl is-active --quiet redis-server 2>/dev/null || pgrep -x redis-server > /dev/null; then
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

# Check PostgreSQL (system service)
echo -n "PostgreSQL:    "
if systemctl is-active --quiet postgresql 2>/dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "--- Portfolio AI Services (User Mode) ---"
echo ""

# Check Backend (user service)
echo -n "Backend API:   "
if systemctl --user is-active --quiet portfolio-backend.service; then
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

# Check Celery Worker (user service)
echo -n "Celery Worker: "
if systemctl --user is-active --quiet portfolio-celery.service; then
    WORKER_COUNT=$(pgrep -f "celery.*worker" | wc -l)
    echo -e "${GREEN}✓ Running ($WORKER_COUNT processes)${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Celery Beat (user service)
echo -n "Celery Beat:   "
if systemctl --user is-active --quiet portfolio-celery-beat.service; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Frontend (user service)
echo -n "Frontend:      "
if systemctl --user is-active --quiet portfolio-frontend.service; then
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
echo "Logs (via journalctl):"
echo "  Backend:       journalctl --user -u portfolio-backend -f"
echo "  Celery Worker: journalctl --user -u portfolio-celery -f"
echo "  Celery Beat:   journalctl --user -u portfolio-celery-beat -f"
echo "  Frontend:      journalctl --user -u portfolio-frontend -f"
echo ""

exit $ERRORS
