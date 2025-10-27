#!/bin/bash
# Code quality checks for Portfolio AI Platform
# Run this script before committing to catch issues early

set -e  # Exit on first error

echo "================================"
echo "Running Code Quality Checks"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Portfolio AI runs natively (no Docker)
# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    echo "Please run: source backend/.venv/bin/activate"
    exit 1
fi

PYTHON_CMD="python3"
RUFF_CMD="ruff"
MYPY_CMD="mypy"
TARGET_DIRS="backend/app/"

# Track failures
FAILURES=0

echo "1. Running Ruff linter..."
echo "---"
if $RUFF_CMD check $TARGET_DIRS; then
    echo -e "${GREEN}✓ Ruff checks passed${NC}"
else
    echo -e "${RED}✗ Ruff found issues${NC}"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "2. Running Ruff formatter check..."
echo "---"
if $RUFF_CMD format --check $TARGET_DIRS; then
    echo -e "${GREEN}✓ Code formatting is correct${NC}"
else
    echo -e "${YELLOW}⚠ Code formatting issues found. Run '$RUFF_CMD format $TARGET_DIRS' to fix${NC}"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "3. Running mypy type checker..."
echo "---"
if $MYPY_CMD $TARGET_DIRS; then
    echo -e "${GREEN}✓ Type checking passed${NC}"
else
    echo -e "${RED}✗ Type checking found issues${NC}"
    FAILURES=$((FAILURES + 1))
fi
echo ""

echo "================================"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}All checks passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}$FAILURES check(s) failed ✗${NC}"
    echo ""
    echo "To auto-fix some issues, run:"
    echo "  $RUFF_CMD check --fix $TARGET_DIRS"
    echo "  $RUFF_CMD format $TARGET_DIRS"
    exit 1
fi
