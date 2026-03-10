#!/usr/bin/env bash
# Check ty type coverage meets minimum threshold.
#
# Legacy filename retained for existing automation entrypoints.
# Purpose: Enforce type coverage across the codebase using ty.
# Usage: ./scripts/check-mypy-coverage.sh
# Threshold: 98% (max 2% of files can have type errors)
#
# Exit codes:
#   0 - Coverage meets threshold
#   1 - Coverage below threshold or ty failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
THRESHOLD=98

echo "=== Type Coverage Check ==="
echo "Threshold: ${THRESHOLD}% (max 2% error rate)"
echo ""

# Activate virtual environment
if [ -f "$BACKEND_DIR/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
else
    echo "ERROR: Virtual environment not found at $BACKEND_DIR/.venv"
    exit 1
fi

# Run ty and capture output
cd "$BACKEND_DIR"
echo "Running: ty check app/"
TY_OUTPUT=$(ty check app/ 2>&1) || TY_EXIT=$?

# Display output
echo "$TY_OUTPUT"
echo ""

# Check if ty succeeded
if [ "${TY_EXIT:-0}" -eq 0 ]; then
    echo "SUCCESS: No type errors found (100% coverage)"
    exit 0
fi

# Count total Python files
TOTAL_FILES=$(find app/ -name "*.py" | wc -l)

# Count files with errors (extract from ty output)
ERROR_FILES=$(echo "$TY_OUTPUT" | grep -oP '^[^:]+\.py' | sort -u | wc -l)

# Calculate error percentage
ERROR_PCT=$((ERROR_FILES * 100 / TOTAL_FILES))
COVERAGE_PCT=$((100 - ERROR_PCT))

echo "Files checked: $TOTAL_FILES"
echo "Files with errors: $ERROR_FILES"
echo "Coverage: ${COVERAGE_PCT}%"
echo ""

# Check threshold
if [ "$COVERAGE_PCT" -ge "$THRESHOLD" ]; then
    echo "PASS: Coverage ${COVERAGE_PCT}% meets threshold ${THRESHOLD}%"
    exit 0
else
    echo "FAIL: Coverage ${COVERAGE_PCT}% below threshold ${THRESHOLD}%"
    exit 1
fi
