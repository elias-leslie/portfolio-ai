#!/bin/bash
# capture-baseline.sh - Capture baseline process snapshot after reboot
#
# Purpose: Record all processes running after a clean system reboot
# to create a whitelist baseline for the fresh-start.sh script.
#
# Usage: bash scripts/capture-baseline.sh
#
# Output: scripts/baseline/processes.txt (timestamped snapshot)
#
# When to run:
# - Immediately after system reboot (before starting portfolio-ai services)
# - After major system changes (new services, configuration updates)
# - When updating the whitelist baseline

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE_DIR="${SCRIPT_DIR}/baseline"
OUTPUT_FILE="${BASELINE_DIR}/processes.txt"

# Ensure baseline directory exists
mkdir -p "${BASELINE_DIR}"

# Capture system information
echo "==================================="
echo "Portfolio AI - Process Baseline Capture"
echo "==================================="
echo ""
echo "Capturing baseline process snapshot..."
echo ""

# Create timestamped output
{
    echo "========================================="
    echo "Process Baseline Snapshot"
    echo "========================================="
    echo ""
    echo "Captured: $(date '+%Y-%m-%d %H:%M:%S %Z')"
    echo "Hostname: $(hostname)"
    echo "System: $(uname -a)"
    echo "Uptime: $(uptime)"
    echo ""
    echo "========================================="
    echo "Process List (ps aux)"
    echo "========================================="
    echo ""

    # Capture full process list
    ps aux

    echo ""
    echo "========================================="
    echo "Process Tree (pstree)"
    echo "========================================="
    echo ""

    # Capture process tree (if available)
    if command -v pstree &> /dev/null; then
        pstree -a
    else
        echo "(pstree not installed - skipping)"
    fi

    echo ""
    echo "========================================="
    echo "Scheduled Processes"
    echo "========================================="
    echo ""

    # User crontab
    echo "--- User Crontab ---"
    crontab -l 2>/dev/null || echo "(no user crontab)"
    echo ""

    # System timers
    echo "--- Systemd Timers (User) ---"
    systemctl --user list-timers --all 2>/dev/null || echo "(no user timers or systemd not available)"
    echo ""

    echo "--- Systemd Timers (System) ---"
    systemctl list-timers --all 2>/dev/null || echo "(no system timers or insufficient permissions)"
    echo ""

    # Celery beat schedule (if backend is set up)
    echo "--- Celery Beat Schedule ---"
    BACKEND_DIR="${SCRIPT_DIR}/../backend"
    if [ -f "${BACKEND_DIR}/app/celery_app.py" ]; then
        echo "Found celery_app.py - scheduled tasks defined in code:"
        grep -E "beat_schedule|task|'schedule':" "${BACKEND_DIR}/app/celery_app.py" 2>/dev/null | head -20 || echo "(could not extract schedule)"
    else
        echo "(celery_app.py not found)"
    fi
    echo ""

    echo "========================================="
    echo "Network Listeners (listening ports)"
    echo "========================================="
    echo ""

    # Show listening services
    if command -v ss &> /dev/null; then
        ss -tulpn 2>/dev/null || ss -tuln
    elif command -v netstat &> /dev/null; then
        netstat -tulpn 2>/dev/null || netstat -tuln
    else
        echo "(neither ss nor netstat available)"
    fi
    echo ""

    echo "========================================="
    echo "End of Baseline Snapshot"
    echo "========================================="

} > "${OUTPUT_FILE}"

echo "✓ Baseline captured successfully!"
echo ""
echo "Output saved to: ${OUTPUT_FILE}"
echo ""
echo "Next steps:"
echo "1. Review the baseline: cat ${OUTPUT_FILE}"
echo "2. Identify processes to whitelist"
echo "3. Create whitelist.conf with patterns"
echo "4. Implement fresh-start.sh script"
echo ""
echo "To view captured processes:"
echo "  less ${OUTPUT_FILE}"
echo ""
