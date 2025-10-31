#!/usr/bin/env bash
# Check mypy type coverage meets minimum threshold
#
# Purpose: Enforce mypy type coverage across the codebase
# Usage: ./scripts/check-mypy-coverage.sh
# Threshold: 98% (max 2% of files can have type errors)
#
# Exit codes:
#   0 - Coverage meets threshold
#   1 - Coverage below threshold or mypy failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
THRESHOLD=98

echo "=== Mypy Type Coverage Check ==="
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

# Run mypy and capture output
cd "$BACKEND_DIR"
echo "Running: mypy app/ --strict"
MYPY_OUTPUT=$(mypy app/ --strict 2>&1) || MYPY_EXIT=$?

# Display output
echo "$MYPY_OUTPUT"
echo ""

# Check if mypy succeeded
if [ "${MYPY_EXIT:-0}" -eq 0 ]; then
    echo "✅ SUCCESS: No mypy errors found (100% coverage)"
    exit 0
fi

# Count total Python files
TOTAL_FILES=$(find app/ -name "*.py" | wc -l)

# Count files with errors (extract from mypy output)
ERROR_FILES=$(echo "$MYPY_OUTPUT" | grep -oP '^[^:]+\.py' | sort -u | wc -l)

# Calculate error percentage
ERROR_PCT=$((ERROR_FILES * 100 / TOTAL_FILES))
COVERAGE_PCT=$((100 - ERROR_PCT))

echo "Files checked: $TOTAL_FILES"
echo "Files with errors: $ERROR_FILES"
echo "Coverage: ${COVERAGE_PCT}%"
echo ""

# Check threshold
if [ "$COVERAGE_PCT" -ge "$THRESHOLD" ]; then
    echo "✅ PASS: Coverage ${COVERAGE_PCT}% meets threshold ${THRESHOLD}%"
    exit 0
else
    echo "❌ FAIL: Coverage ${COVERAGE_PCT}% below threshold ${THRESHOLD}%"
    exit 1
fi
