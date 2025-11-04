#!/bin/bash
# fresh-start.sh - Achieve clean state for Portfolio AI
#
# Purpose: Kill non-whitelisted processes, clean temp files, restart services
#
# Features:
# - Interactive mode: Add processes to whitelist during execution
# - Safety checks: Skip root-owned and low-PID system processes
# - Graceful kill: Try SIGTERM first, fallback to SIGKILL
# - Comprehensive cleanup: Remove temp files
# - Auto-restart: Start services cleanly after cleanup
# - Verification: Check services are healthy after restart
#
# Usage:
#   bash scripts/fresh-start.sh              # Interactive mode (default)
#   bash scripts/fresh-start.sh --auto       # Auto mode (no prompts)
#   bash scripts/fresh-start.sh --help       # Show help
#
# Requirements:
# - Whitelist must exist: scripts/baseline/whitelist.conf
# - Start script must exist: scripts/start.sh
# - User must own the portfolio-ai processes (non-root)
#
# See: docs/reference/baseline-whitelist-system.md for details

set -e
set -u
set -o pipefail

# ================================================
# CONFIGURATION
# ================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASELINE_DIR="${SCRIPT_DIR}/baseline"
WHITELIST_FILE="${BASELINE_DIR}/whitelist.conf"
LOG_FILE="/tmp/fresh-start.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
INTERACTIVE_MODE=true

# ================================================
# UTILITY FUNCTIONS
# ================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "${LOG_FILE}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*" | tee -a "${LOG_FILE}"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "${LOG_FILE}"
}

# ================================================
# WHITELIST MANAGEMENT
# ================================================

read_whitelist() {
    # Read whitelist patterns from config file
    # Returns: Array of patterns (one per line, comments stripped)

    if [ ! -f "${WHITELIST_FILE}" ]; then
        log_error "Whitelist file not found: ${WHITELIST_FILE}"
        log_error "Run: bash scripts/capture-baseline.sh first"
        exit 1
    fi

    # Read non-comment, non-empty lines
    grep -v '^#' "${WHITELIST_FILE}" | grep -v '^[[:space:]]*$' || true
}

add_to_whitelist() {
    # Add a pattern to whitelist.conf
    # Args: $1 = pattern to add

    local pattern="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # Append to whitelist with timestamp
    echo "" >> "${WHITELIST_FILE}"
    echo "# Added by fresh-start.sh on ${timestamp}" >> "${WHITELIST_FILE}"
    echo "${pattern}" >> "${WHITELIST_FILE}"

    log_success "Added to whitelist: ${pattern}"
}

# ================================================
# PROCESS DISCOVERY
# ================================================

find_non_whitelisted() {
    # Find all non-whitelisted user processes
    # Returns: List of PIDs (one per line)

    local whitelist_patterns
    local current_user
    current_user=$(whoami)

    # Read whitelist patterns
    whitelist_patterns=$(read_whitelist)

    # Get all processes owned by current user
    # Format: PID USER %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
    local all_processes
    all_processes=$(ps aux | grep "^${current_user}" | awk '{print $2,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20}')

    # Filter out whitelisted processes
    local non_whitelisted_pids=()

    while IFS= read -r line; do
        local pid
        pid=$(echo "${line}" | awk '{print $1}')
        local cmd
        cmd=$(echo "${line}" | cut -d' ' -f2-)

        # Skip low PIDs (system processes)
        if [ "${pid}" -lt 1000 ]; then
            continue
        fi

        # Skip this script
        if echo "${cmd}" | grep -q "fresh-start.sh"; then
            continue
        fi

        # Check if matches any whitelist pattern
        local is_whitelisted=false
        while IFS= read -r pattern; do
            if [ -z "${pattern}" ]; then
                continue
            fi

            if echo "${cmd}" | grep -E -q "${pattern}"; then
                is_whitelisted=true
                break
            fi
        done <<< "${whitelist_patterns}"

        # If not whitelisted, add to kill list
        if [ "${is_whitelisted}" = false ]; then
            non_whitelisted_pids+=("${pid}:${cmd}")
        fi
    done <<< "${all_processes}"

    # Return PIDs
    printf "%s\n" "${non_whitelisted_pids[@]}"
}

# ================================================
# INTERACTIVE MENU
# ================================================

show_interactive_menu() {
    # Display interactive menu for whitelist management
    # Returns: User choice (k=kill, a=add, q=quit)

    local non_whitelisted=("$@")

    if [ ${#non_whitelisted[@]} -eq 0 ]; then
        log_success "No non-whitelisted processes found!"
        return 0
    fi

    # Display all output to stderr so it's not captured by command substitution
    echo "" >&2
    echo "=========================================" >&2
    echo "Non-Whitelisted Processes Found" >&2
    echo "=========================================" >&2
    echo "" >&2

    local idx=1
    for entry in "${non_whitelisted[@]}"; do
        local pid
        pid=$(echo "${entry}" | cut -d: -f1)
        local cmd
        cmd=$(echo "${entry}" | cut -d: -f2-)
        printf "%3d. PID %-6s %s\n" "${idx}" "${pid}" "${cmd}" >&2
        idx=$((idx + 1))
    done

    echo "" >&2
    echo "=========================================" >&2
    echo "Options:" >&2
    echo "  [k] Kill all listed processes" >&2
    echo "  [a] Add process(es) to whitelist" >&2
    echo "  [q] Quit without killing" >&2
    echo "=========================================" >&2
    echo "" >&2

    # Read from terminal, display prompt to stderr
    read -r -p "Your choice [k/a/q]: " choice </dev/tty >&2
    # Return choice to stdout (captured by command substitution)
    echo "${choice}"
}

process_whitelist_additions() {
    # Handle adding processes to whitelist
    # Args: $@ = array of "PID:COMMAND" entries

    local non_whitelisted=("$@")

    echo "" >&2
    read -r -p "Enter numbers to whitelist (comma-separated, e.g., 1,3,5): " selections </dev/tty >&2

    # Parse selections
    IFS=',' read -ra selected_indices <<< "${selections}"

    for idx_str in "${selected_indices[@]}"; do
        # Trim whitespace
        idx_str=$(echo "${idx_str}" | xargs)

        # Validate number
        if ! [[ "${idx_str}" =~ ^[0-9]+$ ]]; then
            log_warning "Invalid selection: ${idx_str} (skipping)"
            continue
        fi

        # Convert to array index (1-based to 0-based)
        local arr_idx=$((idx_str - 1))

        if [ "${arr_idx}" -lt 0 ] || [ "${arr_idx}" -ge ${#non_whitelisted[@]} ]; then
            log_warning "Out of range: ${idx_str} (skipping)"
            continue
        fi

        # Extract command from entry
        local entry="${non_whitelisted[$arr_idx]}"
        local cmd
        cmd=$(echo "${entry}" | cut -d: -f2-)

        # Ask for pattern (default: full command)
        echo "" >&2
        echo "Command: ${cmd}" >&2
        read -r -p "Enter pattern to whitelist (default: first word): " pattern </dev/tty >&2

        if [ -z "${pattern}" ]; then
            # Default: extract first word (executable name)
            pattern=$(echo "${cmd}" | awk '{print $1}')
        fi

        # Add to whitelist
        add_to_whitelist "${pattern}"
    done

    log_info "Whitelist updated. Re-scanning for non-whitelisted processes..."
}

# ================================================
# PROCESS KILLING
# ================================================

kill_processes() {
    # Kill processes gracefully (SIGTERM) then forcefully (SIGKILL)
    # Args: $@ = array of "PID:COMMAND" entries

    local processes=("$@")

    if [ ${#processes[@]} -eq 0 ]; then
        log_info "No processes to kill"
        return 0
    fi

    log_info "Killing ${#processes[@]} non-whitelisted processes..."

    # Phase 1: Graceful kill (SIGTERM)
    log_info "Phase 1: Graceful shutdown (SIGTERM)..."

    local pids_to_force_kill=()

    for entry in "${processes[@]}"; do
        local pid
        pid=$(echo "${entry}" | cut -d: -f1)
        local cmd
        cmd=$(echo "${entry}" | cut -d: -f2-)

        # Check if process still exists
        if ! ps -p "${pid}" > /dev/null 2>&1; then
            log_info "PID ${pid} already gone"
            continue
        fi

        # Try graceful kill
        if kill "${pid}" 2>/dev/null; then
            log_info "Sent SIGTERM to PID ${pid}: ${cmd}"
            pids_to_force_kill+=("${entry}")
        else
            log_warning "Failed to send SIGTERM to PID ${pid} (may require sudo)"
        fi
    done

    # Wait 5 seconds for graceful shutdown
    if [ ${#pids_to_force_kill[@]} -gt 0 ]; then
        log_info "Waiting 5 seconds for graceful shutdown..."
        sleep 5
    fi

    # Phase 2: Force kill (SIGKILL) any survivors
    log_info "Phase 2: Force kill (SIGKILL) any survivors..."

    local kill_count=0

    for entry in "${pids_to_force_kill[@]}"; do
        local pid
        pid=$(echo "${entry}" | cut -d: -f1)
        local cmd
        cmd=$(echo "${entry}" | cut -d: -f2-)

        # Check if still running
        if ps -p "${pid}" > /dev/null 2>&1; then
            if kill -9 "${pid}" 2>/dev/null; then
                log_success "Force killed PID ${pid}: ${cmd}"
                kill_count=$((kill_count + 1))
            else
                log_error "Failed to force kill PID ${pid} (may require sudo)"
            fi
        else
            log_success "PID ${pid} exited gracefully"
            kill_count=$((kill_count + 1))
        fi
    done

    log_success "Killed ${kill_count} processes"
}

# ================================================
# CLEANUP
# ================================================

clean_temp_files() {
    # Remove temporary files created by portfolio-ai

    log_info "Cleaning temporary files..."

    local patterns=(
        "/tmp/portfolio-*.log"
        "/tmp/portfolio-*.txt"
        "/tmp/*.png"
        "/tmp/ui-*.png"
    )

    local removed_count=0

    for pattern in "${patterns[@]}"; do
        # Use find to safely handle patterns
        local files
        files=$(eval "ls ${pattern} 2>/dev/null" || true)

        if [ -n "${files}" ]; then
            while IFS= read -r file; do
                if [ -f "${file}" ]; then
                    rm -f "${file}"
                    log_info "Removed: ${file}"
                    removed_count=$((removed_count + 1))
                fi
            done <<< "${files}"
        fi
    done

    if [ ${removed_count} -eq 0 ]; then
        log_info "No temp files to clean"
    else
        log_success "Removed ${removed_count} temp files"
    fi
}

stop_systemd_services() {
    # Stop portfolio-ai systemd services if they exist

    log_info "Checking for systemd services..."

    local services=("portfolio-backend" "portfolio-celery" "portfolio-beat" "portfolio-frontend")
    local stopped_count=0

    for service in "${services[@]}"; do
        if systemctl is-active --quiet "${service}.service" 2>/dev/null; then
            log_info "Stopping systemd service: ${service}.service"
            if sudo systemctl stop "${service}.service" 2>/dev/null; then
                log_success "Stopped ${service}.service"
                stopped_count=$((stopped_count + 1))
            else
                log_warning "Failed to stop ${service}.service (may require sudo)"
            fi
        fi
    done

    if [ ${stopped_count} -gt 0 ]; then
        log_success "Stopped ${stopped_count} systemd services"
        sleep 2  # Allow services to fully stop
    else
        log_info "No systemd services found (services may be manually managed)"
    fi
}

verify_clean_state() {
    # Verify no portfolio-ai processes remain

    log_info "Verifying clean state..."

    local remaining_processes
    remaining_processes=$(pgrep -f "uvicorn.*main:app|celery.*portfolio|node.*next.*dev" || true)

    if [ -z "${remaining_processes}" ]; then
        log_success "Clean state verified - no portfolio-ai processes remain"
        return 0
    else
        log_error "Found remaining portfolio-ai processes:"
        ps -p "${remaining_processes}" -o pid,user,cmd
        return 1
    fi
}

# ================================================
# SERVICE MANAGEMENT
# ================================================

start_services() {
    # Start portfolio-ai services (systemd or manual)

    log_info "Starting portfolio-ai services..."

    # Check if systemd services exist
    local has_systemd=false
    if systemctl list-unit-files | grep -q "portfolio-backend.service"; then
        has_systemd=true
    fi

    if [ "${has_systemd}" = true ]; then
        log_info "Starting services via systemd..."
        local services=("portfolio-backend" "portfolio-celery" "portfolio-beat" "portfolio-frontend")
        local started_count=0

        for service in "${services[@]}"; do
            if sudo systemctl start "${service}.service" 2>/dev/null; then
                log_success "Started ${service}.service"
                started_count=$((started_count + 1))
            else
                log_warning "Failed to start ${service}.service"
            fi
        done

        log_success "Started ${started_count} systemd services"
    else
        # Fallback to start.sh script
        if [ ! -f "${SCRIPT_DIR}/start.sh" ]; then
            log_error "Start script not found: ${SCRIPT_DIR}/start.sh"
            return 1
        fi

        bash "${SCRIPT_DIR}/start.sh"
        log_success "Services started via start.sh"
    fi
}

verify_startup() {
    # Verify services started successfully

    log_info "Verifying service startup (waiting 10 seconds)..."
    sleep 10

    # Check health endpoint
    local health_check
    health_check=$(curl -s http://localhost:8000/health || echo "FAILED")

    # Accept both "healthy" and "degraded" statuses
    # (degraded = external sources inactive, but backend functional)
    if echo "${health_check}" | grep -qE '"status":"(healthy|degraded)"'; then
        local status
        status=$(echo "${health_check}" | grep -oP '"status":"\K[^"]+' | head -1)
        if [ "${status}" = "degraded" ]; then
            log_warning "Backend status: degraded (external sources inactive, but functional)"
        else
            log_success "Backend health check passed"
        fi
    else
        log_error "Backend health check failed: ${health_check}"
        return 1
    fi

    # Check frontend
    local frontend_check
    frontend_check=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ || echo "000")

    if [ "${frontend_check}" = "200" ] || [ "${frontend_check}" = "304" ]; then
        log_success "Frontend health check passed"
    else
        log_error "Frontend health check failed (HTTP ${frontend_check})"
        return 1
    fi

    log_success "All services verified healthy"
}

# ================================================
# MAIN EXECUTION
# ================================================

show_help() {
    cat << EOF
Usage: bash scripts/fresh-start.sh [OPTIONS]

Achieve clean state for Portfolio AI by killing non-whitelisted processes,
cleaning temp files, and restarting services.

Options:
  --auto        Run in automatic mode (no prompts)
  --help        Show this help message

Examples:
  bash scripts/fresh-start.sh          # Interactive mode (default)
  bash scripts/fresh-start.sh --auto   # Auto mode

Interactive Mode:
  - Shows list of non-whitelisted processes
  - Allows adding processes to whitelist before killing
  - Prompts for confirmation

Auto Mode:
  - Kills all non-whitelisted processes immediately
  - No prompts or confirmation
  - Suitable for scripts/automation

See: docs/reference/baseline-whitelist-system.md for details
EOF
}

main() {
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            --auto)
                INTERACTIVE_MODE=false
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Initialize log
    echo "" > "${LOG_FILE}"
    log_info "========================================"
    log_info "Portfolio AI - Fresh Start"
    log_info "========================================"
    log_info "Mode: $([ "${INTERACTIVE_MODE}" = true ] && echo "Interactive" || echo "Auto")"
    log_info "Started: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info ""

    # Step 1: Stop systemd services first (if they exist)
    stop_systemd_services

    # Step 2: Find remaining non-whitelisted processes
    log_info "Step 2: Finding remaining non-whitelisted processes..."
    local non_whitelisted
    mapfile -t non_whitelisted < <(find_non_whitelisted)

    if [ ${#non_whitelisted[@]} -eq 0 ]; then
        log_success "No non-whitelisted processes found!"
    else
        log_info "Found ${#non_whitelisted[@]} non-whitelisted processes"

        # Step 3: Interactive menu (if enabled)
        if [ "${INTERACTIVE_MODE}" = true ]; then
            while true; do
                local choice
                choice=$(show_interactive_menu "${non_whitelisted[@]}")

                case "${choice}" in
                    k|K)
                        log_info "User chose to kill all processes"
                        break
                        ;;
                    a|A)
                        process_whitelist_additions "${non_whitelisted[@]}"
                        # Re-scan after whitelist update
                        mapfile -t non_whitelisted < <(find_non_whitelisted)
                        if [ ${#non_whitelisted[@]} -eq 0 ]; then
                            log_success "All processes now whitelisted!"
                            break
                        fi
                        ;;
                    q|Q)
                        log_info "User chose to quit without killing"
                        exit 0
                        ;;
                    *)
                        log_warning "Invalid choice: ${choice}"
                        ;;
                esac
            done
        fi

        # Step 4: Kill remaining processes
        if [ ${#non_whitelisted[@]} -gt 0 ]; then
            kill_processes "${non_whitelisted[@]}"
        fi
    fi

    # Step 5: Clean temp files
    clean_temp_files

    # Step 6: Verify clean state
    verify_clean_state || {
        log_error "Clean state verification failed"
        log_error "Manual intervention may be required"
        exit 1
    }

    # Step 7: Start services
    start_services

    # Step 8: Verify startup
    verify_startup || {
        log_warning "Service verification failed - check logs"
        log_info "Run: bash scripts/status.sh"
        exit 1
    }

    # Success!
    log_info ""
    log_info "========================================"
    log_success "Fresh start complete!"
    log_info "========================================"
    log_info "Completed: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Log saved to: ${LOG_FILE}"
    log_info ""
    log_info "Next steps:"
    log_info "  - Check status: bash scripts/status.sh"
    log_info "  - View logs: tail -f ${LOG_FILE}"
    log_info ""
}

# Run main function
main "$@"
