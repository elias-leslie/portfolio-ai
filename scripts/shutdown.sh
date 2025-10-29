#!/bin/bash
#
# Shutdown script for Portfolio AI Platform
# Stops Frontend, Celery worker, Backend API, and optionally Redis
#

set -e

echo "================================"
echo "Shutting down Portfolio AI Platform"
echo "================================"
echo ""

# Stop Frontend
echo "Stopping Frontend..."
if pkill -f "next.*dev"; then
    sleep 1
    echo "✓ Frontend stopped"
else
    echo "⚠ Frontend was not running"
fi
echo ""

# Stop Celery Worker
echo "Stopping Celery worker..."
if pkill -f "celery.*worker"; then
    sleep 1
    echo "✓ Celery worker stopped"
else
    echo "⚠ Celery worker was not running"
fi
echo ""

# Stop Backend API
echo "Stopping Backend API..."
if pkill -f "uvicorn.*main:app"; then
    sleep 1
    echo "✓ Backend API stopped"
else
    echo "⚠ Backend API was not running"
fi
echo ""

# Ask about Redis
echo "Stop Redis server? (y/N)"
read -r -p "> " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Stopping Redis..."
    if pkill -x redis-server; then
        sleep 1
        echo "✓ Redis stopped"
    else
        echo "⚠ Redis was not running"
    fi
else
    echo "✓ Redis left running"
fi
echo ""

echo "================================"
echo "✓ Shutdown complete"
echo "================================"
echo ""
echo "Service Status:"
echo "  Redis:    $(pgrep -x redis-server > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Backend:  $(pgrep -f 'uvicorn.*main:app' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery:   $(pgrep -f 'celery.*worker' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend: $(pgrep -f 'next.*dev' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo ""
