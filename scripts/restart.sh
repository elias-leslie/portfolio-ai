#!/bin/bash
#
# Restart script for Portfolio AI Platform
# Stops and restarts all services (Frontend, Backend API, Celery worker)
# Does not stop Redis (leaves it running)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Function to kill process gracefully, with force-kill fallback
kill_process() {
    local pattern="$1"
    local name="$2"
    local timeout=5

    # Try graceful kill
    if pkill -f "$pattern" 2>/dev/null; then
        # Wait for process to die
        for i in $(seq 1 $timeout); do
            if ! pgrep -f "$pattern" > /dev/null 2>&1; then
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
        fi
    fi
}

echo "================================"
echo "Restarting Portfolio AI Platform"
echo "================================"
echo ""

# Stop services (but not Redis)
echo "Stopping services..."
kill_process "next.*dev" "Frontend"
kill_process "celery.*worker" "Celery"
kill_process "uvicorn.*main:app" "Backend"
sleep 1
echo "✓ Services stopped"
echo ""

# Check if Redis is available and running (optional)
if command -v redis-server &> /dev/null; then
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "⚠ Redis is not running. Starting Redis..."
        redis-server --daemonize yes
        sleep 1
    fi
else
    echo "ℹ Redis not found (optional - only needed for background jobs)"
fi
echo ""

# Start Backend API
echo "Starting Backend API..."
cd "$BACKEND_DIR"
source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/portfolio-backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

if pgrep -f "uvicorn.*main:app" > /dev/null; then
    echo "✓ Backend API started (PID: $BACKEND_PID)"
    echo "  URL: http://localhost:8000"
else
    echo "✗ Failed to start Backend API"
    echo "  Check logs: tail -f /tmp/portfolio-backend.log"
    exit 1
fi
echo ""

# Start Celery Worker
echo "Starting Celery worker..."
cd "$BACKEND_DIR"
nohup celery -A app.celery_app worker --loglevel=info > /tmp/portfolio-celery.log 2>&1 &
CELERY_PID=$!
sleep 2

if pgrep -f "celery.*worker" > /dev/null; then
    echo "✓ Celery worker started (PID: $CELERY_PID)"
else
    echo "⚠ Warning: Celery worker may not have started properly"
    echo "  Check logs: tail -f /tmp/portfolio-celery.log"
fi
echo ""

# Start Frontend
echo "Starting Frontend..."
cd "$FRONTEND_DIR"

# Ensure .env.local exists
if [ ! -f ".env.local" ]; then
    echo "⚠ Creating .env.local with API URL..."
    cat > .env.local << 'EOF'
# API base URL
# When empty, uses relative URLs (works for Tailscale)
# Set to http://localhost:8000 for local development with separate backend
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
fi

nohup npm run dev > /tmp/portfolio-frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 3

if pgrep -f "next.*dev" > /dev/null; then
    echo "✓ Frontend started (PID: $FRONTEND_PID)"
    echo "  URL: http://localhost:3000"
else
    echo "✗ Failed to start Frontend"
    echo "  Check logs: tail -f /tmp/portfolio-frontend.log"
    exit 1
fi
echo ""

echo "================================"
echo "✓ Restart complete!"
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
