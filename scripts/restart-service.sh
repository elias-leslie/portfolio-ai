#!/bin/bash
# Restart individual Portfolio AI service
# Usage: ./restart-service.sh <service-name>

set -euo pipefail

# Valid service names (whitelist)
VALID_SERVICES=("backend" "celery" "beat" "frontend" "redis")

SERVICE_NAME="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

# Validate service name
validate_service() {
    local service="$1"
    for valid in "${VALID_SERVICES[@]}"; do
        if [ "$service" = "$valid" ]; then
            return 0
        fi
    done
    return 1
}

# Restart service based on name
restart_service() {
    local service="$1"

    case "$service" in
        "backend")
            log_info "Restarting backend service..."
            # Manual process restart (no sudo required for web UI)
            log_info "Stopping backend..."
            pkill -f "uvicorn app.main:app" || true
            sleep 1
            log_info "Starting backend..."
            cd "$(dirname "$0")/../backend"
            nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/portfolio-backend.log 2>&1 &
            sleep 2
            log_info "Backend restarted (manual)"
            ;;

        "celery")
            log_info "Restarting Celery worker..."
            # Manual process restart (no sudo required for web UI)
            log_info "Stopping Celery worker..."
            pkill -f "celery -A app.celery_app worker" || true
            sleep 1
            log_info "Starting Celery worker..."
            cd "$(dirname "$0")/../backend"
            nohup .venv/bin/celery -A app.celery_app worker --loglevel=info > /tmp/portfolio-celery-worker.log 2>&1 &
            sleep 2
            log_info "Celery worker restarted (manual)"
            ;;

        "beat")
            log_info "Restarting Celery beat..."
            # Manual process restart (no sudo required for web UI)
            log_info "Stopping Celery beat..."
            pkill -f "celery -A app.celery_app beat" || true
            sleep 1
            log_info "Starting Celery beat..."
            cd "$(dirname "$0")/../backend"
            nohup .venv/bin/celery -A app.celery_app beat --loglevel=info > /tmp/portfolio-celery-beat.log 2>&1 &
            sleep 2
            log_info "Celery beat restarted (manual)"
            ;;

        "frontend")
            log_info "Restarting frontend service..."
            # Manual process restart (no sudo required for web UI)
            log_info "Stopping frontend..."
            pkill -f "next dev" || true
            sleep 1
            log_info "Starting frontend..."
            cd "$(dirname "$0")/../frontend"
            nohup npm run dev > /tmp/portfolio-frontend.log 2>&1 &
            sleep 3
            log_info "Frontend restarted (manual)"
            ;;

        "redis")
            log_info "Restarting Redis..."
            if systemctl is-enabled redis-server.service >/dev/null 2>&1; then
                sudo systemctl restart redis-server.service
                log_info "Redis restarted (systemd)"
            else
                # Redis typically runs as system service, manual restart not supported
                log_error "Redis not running under systemd and manual restart not supported"
                log_error "Please restart Redis manually: sudo systemctl restart redis-server"
                return 1
            fi
            ;;

        *)
            log_error "Unknown service: $service"
            return 1
            ;;
    esac
}

# Main
if [ $# -ne 1 ]; then
    log_error "Usage: $0 <service-name>"
    log_info "Valid services: ${VALID_SERVICES[*]}"
    exit 1
fi

if ! validate_service "$SERVICE_NAME"; then
    log_error "Invalid service name: $SERVICE_NAME"
    log_info "Valid services: ${VALID_SERVICES[*]}"
    exit 1
fi

restart_service "$SERVICE_NAME"
