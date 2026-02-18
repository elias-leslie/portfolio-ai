#!/bin/bash
# Lightweight quality-report shim for Portfolio AI
# Usage: scripts/quality-report.sh [backend/app]

set -euo pipefail

TARGET_PATH=${1:-backend/app}
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
REPORT_FILE="$LOG_DIR/quality-report-$(date +%Y%m%d-%H%M%S).log"

exec > >(tee "$REPORT_FILE") 2>&1

echo "========================================"
echo " Portfolio AI Quality Report"
echo " Target: $TARGET_PATH"
echo " Timestamp: $(date)"
echo " Logs: $REPORT_FILE"
echo "========================================"

declare -a missing_tools=()

if command -v ruff >/dev/null 2>&1; then
  echo "\n[ruff] Checking lint..."
  (cd "$ROOT_DIR" && ruff check "$TARGET_PATH") || true
else
  missing_tools+=("ruff")
  echo "⚠ ruff not found; skipping lint"
fi

if command -v ty >/dev/null 2>&1; then
  echo "\n[ty] Type checking..."
  (cd "$ROOT_DIR" && ty check "$TARGET_PATH") || true
else
  missing_tools+=("ty")
  echo "⚠ ty not found; skipping type checks"
fi

if command -v pytest >/dev/null 2>&1; then
  echo "\n[pytest] Smoke test collection..."
  (cd "$ROOT_DIR/backend" && pytest --maxfail=1 --disable-warnings -q) || true
else
  missing_tools+=("pytest")
  echo "⚠ pytest not found; skipping tests"
fi

if [ ${#missing_tools[@]} -gt 0 ]; then
  echo "\nMissing tools: ${missing_tools[*]}"
  echo "Install the listed tools to run the full report."
fi

echo "\nQuality report complete."
