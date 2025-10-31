#!/usr/bin/env bash
# Check Python file sizes meet project guidelines
#
# Purpose: Enforce file size limits to maintain code quality
# Usage: ./scripts/check-file-sizes.sh
# Limits: 500 lines (soft, warning), 800 lines (hard, error)
# Exceptions: *schema*.py, test_*.py, *cli*.py
#
# Exit codes:
#   0 - All files within limits
#   1 - One or more files exceed hard limit

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

SOFT_LIMIT=500
HARD_LIMIT=800

echo "=== File Size Check ==="
echo "Soft limit: $SOFT_LIMIT lines (warning)"
echo "Hard limit: $HARD_LIMIT lines (error)"
echo "Exceptions: *schema*.py, test_*.py, *cli*.py"
echo ""

# Find all Python files in app/ directory
cd "$BACKEND_DIR"
WARNINGS=0
ERRORS=0
ERROR_FILES=()

while IFS= read -r file; do
    # Skip exceptions
    basename=$(basename "$file")
    if [[ "$basename" == *schema*.py ]] || [[ "$basename" == test_*.py ]] || [[ "$basename" == *cli*.py ]]; then
        continue
    fi

    # Count lines
    line_count=$(wc -l < "$file")

    # Check limits
    if [ "$line_count" -gt "$HARD_LIMIT" ]; then
        echo "❌ ERROR: $file has $line_count lines (hard limit: $HARD_LIMIT)"
        ERRORS=$((ERRORS + 1))
        ERROR_FILES+=("$file")
    elif [ "$line_count" -gt "$SOFT_LIMIT" ]; then
        echo "⚠️  WARNING: $file has $line_count lines (soft limit: $SOFT_LIMIT)"
        WARNINGS=$((WARNINGS + 1))
    fi
done < <(find app/ -name "*.py" -type f)

echo ""
echo "Summary:"
echo "  Warnings: $WARNINGS files exceed soft limit ($SOFT_LIMIT lines)"
echo "  Errors: $ERRORS files exceed hard limit ($HARD_LIMIT lines)"
echo ""

if [ "$ERRORS" -gt 0 ]; then
    echo "❌ FAIL: $ERRORS files exceed hard limit"
    echo ""
    echo "Files exceeding hard limit ($HARD_LIMIT lines):"
    for file in "${ERROR_FILES[@]}"; do
        echo "  - $file"
    done
    exit 1
else
    echo "✅ PASS: All files within hard limit ($HARD_LIMIT lines)"
    if [ "$WARNINGS" -gt 0 ]; then
        echo ""
        echo "Note: $WARNINGS files exceed soft limit but are acceptable"
    fi
    exit 0
fi
