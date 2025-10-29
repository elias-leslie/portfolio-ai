#!/bin/bash
#
# Shutdown script for Portfolio AI Platform
# Stops Frontend, Celery worker, Backend API, and optionally Redis
#

set -e

# Function to kill process gracefully, with force-kill fallback
kill_process() {
    local pattern="$1"
    local name="$2"
    local timeout=5

    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo "Stopping $name..."
        # Try graceful kill
        pkill -f "$pattern" 2>/dev/null || true

        # Wait for process to die
        for i in $(seq 1 $timeout); do
            if ! pgrep -f "$pattern" > /dev/null 2>&1; then
                echo "✓ $name stopped"
                return 0
            fi
            sleep 1
        done

        # Process didn't die, force kill
        echo "⚠ $name didn't stop gracefully, force killing..."
        pkill -9 -f "$pattern" 2>/dev/null || true
        sleep 1

        # Check if we need sudo
        if pgrep -f "$pattern" > /dev/null 2>&1; then
            echo "⚠ Need elevated permissions to kill $name"
            sudo pkill -9 -f "$pattern" 2>/dev/null || true
            if ! pgrep -f "$pattern" > /dev/null 2>&1; then
                echo "✓ $name stopped (with sudo)"
            fi
        else
            echo "✓ $name stopped (force killed)"
        fi
    else
        echo "⚠ $name was not running"
    fi
    echo ""
}

echo "================================"
echo "Shutting down Portfolio AI Platform"
echo "================================"
echo ""

# Stop services
kill_process "next.*dev" "Frontend"
kill_process "celery.*worker" "Celery worker"
kill_process "uvicorn.*main:app" "Backend API"

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
