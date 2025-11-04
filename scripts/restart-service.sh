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
            if systemctl is-active --quiet portfolio-backend.service 2>/dev/null; then
                sudo systemctl restart portfolio-backend.service
                log_info "Backend restarted (systemd)"
            else
                log_error "Backend service not found or not running"
                return 1
            fi
            ;;

        "celery")
            log_info "Restarting Celery worker..."
            if systemctl is-active --quiet portfolio-celery.service 2>/dev/null; then
                sudo systemctl restart portfolio-celery.service
                log_info "Celery worker restarted (systemd)"
            else
                log_error "Celery worker service not found or not running"
                return 1
            fi
            ;;

        "beat")
            log_info "Restarting Celery beat..."
            if systemctl is-active --quiet portfolio-beat.service 2>/dev/null; then
                sudo systemctl restart portfolio-beat.service
                log_info "Celery beat restarted (systemd)"
            else
                log_error "Celery beat service not found or not running"
                return 1
            fi
            ;;

        "frontend")
            log_info "Restarting frontend service..."
            if systemctl is-active --quiet portfolio-frontend.service 2>/dev/null; then
                sudo systemctl restart portfolio-frontend.service
                log_info "Frontend restarted (systemd)"
            else
                log_error "Frontend service not found or not running"
                return 1
            fi
            ;;

        "redis")
            log_info "Restarting Redis..."
            if systemctl is-active --quiet redis-server.service 2>/dev/null; then
                sudo systemctl restart redis-server.service
                log_info "Redis restarted (systemd)"
            else
                log_error "Redis service not found or not running"
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
