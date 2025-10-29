#!/bin/bash
#
# Start script for Portfolio AI Platform
# Starts Redis, Backend API, Celery worker, and Frontend in the background
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "================================"
echo "Starting Portfolio AI Platform"
echo "================================"
echo ""

# Check if Redis is running
if pgrep -x "redis-server" > /dev/null; then
    echo "✓ Redis is already running"
else
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 1
    if pgrep -x "redis-server" > /dev/null; then
        echo "✓ Redis started successfully"
    else
        echo "✗ Failed to start Redis"
        exit 1
    fi
fi
echo ""

# Start Backend API
echo "Starting Backend API..."
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
    echo "✗ Virtual environment not found. Please run setup first."
    exit 1
fi

# Stop any existing backend processes
pkill -f "uvicorn.*main:app" 2>/dev/null || true
sleep 1

source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/portfolio-backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

if pgrep -f "uvicorn.*main:app" > /dev/null; then
    echo "✓ Backend API started (PID: $BACKEND_PID)"
    echo "  Log: /tmp/portfolio-backend.log"
    echo "  URL: http://localhost:8000"
else
    echo "✗ Failed to start Backend API"
    echo "  Check logs: tail -f /tmp/portfolio-backend.log"
    exit 1
fi
echo ""

# Start Celery Worker
echo "Starting Celery worker..."
pkill -f "celery.*worker" 2>/dev/null || true
sleep 1

cd "$BACKEND_DIR"
nohup celery -A app.celery_app worker --loglevel=info > /tmp/portfolio-celery.log 2>&1 &
CELERY_PID=$!
sleep 2

if pgrep -f "celery.*worker" > /dev/null; then
    echo "✓ Celery worker started (PID: $CELERY_PID)"
    echo "  Log: /tmp/portfolio-celery.log"
else
    echo "⚠ Warning: Celery worker may not have started properly"
    echo "  Check logs: tail -f /tmp/portfolio-celery.log"
fi
echo ""

# Start Frontend
echo "Starting Frontend..."
cd "$FRONTEND_DIR"

# Check .env.local exists
if [ ! -f ".env.local" ]; then
    echo "⚠ Warning: .env.local not found. Creating with default API URL..."
    cat > .env.local << 'EOF'
# API base URL
# When empty, uses relative URLs (works for Tailscale)
# Set to http://localhost:8000 for local development with separate backend
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
fi

# Stop any existing frontend processes
pkill -f "next.*dev" 2>/dev/null || true
sleep 1

nohup npm run dev > /tmp/portfolio-frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 3

if pgrep -f "next.*dev" > /dev/null; then
    echo "✓ Frontend started (PID: $FRONTEND_PID)"
    echo "  Log: /tmp/portfolio-frontend.log"
    echo "  URL: http://localhost:3000"
else
    echo "✗ Failed to start Frontend"
    echo "  Check logs: tail -f /tmp/portfolio-frontend.log"
    exit 1
fi
echo ""

echo "================================"
echo "✓ All services started successfully!"
echo "================================"
echo ""
echo "Service Status:"
echo "  Redis:    $(pgrep -x redis-server > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Backend:  $(pgrep -f 'uvicorn.*main:app' > /dev/null && echo '✓ Running (http://localhost:8000)' || echo '✗ Stopped')"
echo "  Celery:   $(pgrep -f 'celery.*worker' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend: $(pgrep -f 'next.*dev' > /dev/null && echo '✓ Running (http://localhost:3000)' || echo '✗ Stopped')"
echo ""
echo "Logs:"
echo "  Backend:  tail -f /tmp/portfolio-backend.log"
echo "  Celery:   tail -f /tmp/portfolio-celery.log"
echo "  Frontend: tail -f /tmp/portfolio-frontend.log"
echo ""
echo "To stop all services: ./scripts/shutdown.sh"
echo ""
