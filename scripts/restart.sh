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

# Function to kill process tree (parent + all children) gracefully, with force-kill fallback
kill_process() {
    local pattern="$1"
    local name="$2"
    local timeout=5

    # Get all matching PIDs
    local pids=$(pgrep -f "$pattern" 2>/dev/null || true)

    if [ -z "$pids" ]; then
        return 0  # No processes to kill
    fi

    # Try graceful kill (SIGTERM)
    for pid in $pids; do
        # Kill the process and all its children
        pkill -TERM -P "$pid" 2>/dev/null || true
        kill -TERM "$pid" 2>/dev/null || true
    done

    # Wait for processes to die
    for i in $(seq 1 $timeout); do
        if ! pgrep -f "$pattern" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    # Processes didn't die, force kill (SIGKILL)
    echo "⚠ $name didn't stop gracefully, force killing..."
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    for pid in $pids; do
        # Kill the process tree
        pkill -9 -P "$pid" 2>/dev/null || true
        kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1

    # Final check
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo "⚠ Some $name processes may still be running (check manually)"
    fi
}

echo "================================"
echo "Restarting Portfolio AI Platform"
echo "================================"
echo ""

# Stop services (but not Redis)
echo "Stopping services..."
kill_process "next.*dev" "Frontend"
"$SCRIPT_DIR/stop-celery.sh" 2>/dev/null || kill_process "celery" "Celery"
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
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/portfolio-backend.log 2>&1 &
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

# Start Celery Worker and Beat using dedicated script
"$SCRIPT_DIR/start-celery.sh"
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
echo "  Redis:        $(pgrep -x redis-server > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Backend:      $(pgrep -f 'uvicorn.*main:app' > /dev/null && echo '✓ Running (http://localhost:8000)' || echo '✗ Stopped')"
echo "  Celery Worker:$(pgrep -f 'celery.*worker' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Celery Beat:  $(pgrep -f 'celery.*beat' > /dev/null && echo '✓ Running' || echo '✗ Stopped')"
echo "  Frontend:     $(pgrep -f 'next.*dev' > /dev/null && echo '✓ Running (http://localhost:3000)' || echo '✗ Stopped')"
echo ""
echo "Logs:"
echo "  Backend:      tail -f /tmp/portfolio-backend.log"
echo "  Celery Worker:tail -f /tmp/portfolio-celery-worker.log"
echo "  Celery Beat:  tail -f /tmp/portfolio-celery-beat.log"
echo "  Frontend:     tail -f /tmp/portfolio-frontend.log"
echo ""
