#!/bin/bash
# Restart individual Portfolio AI service
# Usage: ./restart-service.sh <service-name>
#
# IMPORTANT: This script now uses systemd for service management (production-ready)
# Services are restarted via systemctl (requires passwordless sudo setup)

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
            log_info "Restarting backend service via systemd..."
            if sudo systemctl restart portfolio-backend.service 2>/dev/null; then
                sleep 2
                if systemctl is-active --quiet portfolio-backend.service; then
                    log_info "Backend restarted successfully (systemd)"
                else
                    log_error "Backend failed to start after restart"
                    return 1
                fi
            else
                log_warning "Systemd restart failed, falling back to manual restart..."
                pkill -f "uvicorn app.main:app" || true
                sleep 1
                cd "$(dirname "$0")/../backend"
                nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/portfolio-backend.log 2>&1 &
                sleep 2
                log_info "Backend restarted (manual fallback)"
            fi
            ;;

        "celery")
            log_info "Restarting Celery worker via systemd..."
            if sudo systemctl restart portfolio-celery.service 2>/dev/null; then
                sleep 2
                if systemctl is-active --quiet portfolio-celery.service; then
                    log_info "Celery worker restarted successfully (systemd)"
                else
                    log_error "Celery worker failed to start after restart"
                    return 1
                fi
            else
                log_warning "Systemd restart failed, falling back to manual restart..."
                SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
                "$SCRIPT_DIR/stop-celery.sh" 2>/dev/null || pkill -f "celery.*worker" || true
                sleep 1
                "$SCRIPT_DIR/start-celery.sh"
                log_info "Celery worker restarted (manual fallback via start-celery.sh)"
            fi
            ;;

        "beat")
            log_info "Restarting Celery beat via systemd..."
            if sudo systemctl restart portfolio-beat.service 2>/dev/null; then
                sleep 2
                if systemctl is-active --quiet portfolio-beat.service; then
                    log_info "Celery beat restarted successfully (systemd)"
                else
                    log_error "Celery beat failed to start after restart"
                    return 1
                fi
            else
                log_warning "Systemd restart failed, falling back to manual restart..."
                SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
                "$SCRIPT_DIR/stop-celery.sh" 2>/dev/null || pkill -f "celery.*beat" || true
                sleep 1
                "$SCRIPT_DIR/start-celery.sh"
                log_info "Celery beat restarted (manual fallback via start-celery.sh)"
            fi
            ;;

        "frontend")
            log_info "Restarting frontend service via systemd..."
            if sudo systemctl restart portfolio-frontend.service 2>/dev/null; then
                sleep 3
                if systemctl is-active --quiet portfolio-frontend.service; then
                    log_info "Frontend restarted successfully (systemd)"
                else
                    log_error "Frontend failed to start after restart"
                    return 1
                fi
            else
                log_warning "Systemd restart failed, falling back to manual restart..."
                pkill -f "next dev" || true
                sleep 1
                cd "$(dirname "$0")/../frontend"
                nohup npm run dev > /tmp/portfolio-frontend.log 2>&1 &
                sleep 3
                log_info "Frontend restarted (manual fallback)"
            fi
            ;;

        "redis")
            log_info "Restarting Redis via systemd..."
            if sudo systemctl restart redis-server.service 2>/dev/null; then
                log_info "Redis restarted successfully (systemd)"
            else
                log_error "Failed to restart Redis. Please run: sudo systemctl restart redis-server"
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
