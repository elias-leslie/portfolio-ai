#!/bin/bash
# Check for files with restrictive permissions that could break systemd services

echo "======================================"
echo "Portfolio AI - Permission Check"
echo "======================================"
echo ""

BACKEND_DIR="$(cd "$(dirname "$0")/../backend" && pwd)"

echo "Checking for files with 600 permissions (owner-only)..."
echo ""

# Check Python files
echo "Python files (.py):"
PYTHON_FILES=$(find "$BACKEND_DIR" -type f -name "*.py" -perm 600 2>/dev/null)
if [ -z "$PYTHON_FILES" ]; then
    echo "  ✓ No restrictive Python files found"
else
    echo "  ✗ Found files with 600 permissions:"
    echo "$PYTHON_FILES" | sed 's/^/    /'
fi
echo ""

# Check SQL files
echo "SQL migration files (.sql):"
SQL_FILES=$(find "$BACKEND_DIR/migrations" -type f -name "*.sql" -perm 600 2>/dev/null)
if [ -z "$SQL_FILES" ]; then
    echo "  ✓ No restrictive SQL files found"
else
    echo "  ✗ Found files with 600 permissions:"
    echo "$SQL_FILES" | sed 's/^/    /'
fi
echo ""

# Check JSON files
echo "JSON config files (.json):"
JSON_FILES=$(find "$BACKEND_DIR" -type f -name "*.json" -perm 600 2>/dev/null)
if [ -z "$JSON_FILES" ]; then
    echo "  ✓ No restrictive JSON files found"
else
    echo "  ✗ Found files with 600 permissions:"
    echo "$JSON_FILES" | sed 's/^/    /'
fi
echo ""

# Summary
TOTAL=$(find "$BACKEND_DIR" -type f \( -name "*.py" -o -name "*.sql" -o -name "*.json" \) -perm 600 2>/dev/null | wc -l)

echo "======================================"
if [ "$TOTAL" -eq 0 ]; then
    echo "✓ All files have correct permissions"
else
    echo "✗ Found $TOTAL file(s) with restrictive permissions"
    echo ""
    echo "To fix all at once:"
    echo "  find $BACKEND_DIR -type f \( -name '*.py' -o -name '*.sql' -o -name '*.json' \) -perm 600 -exec chmod 664 {} +"
fi
echo "======================================"
