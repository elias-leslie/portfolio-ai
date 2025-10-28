#!/bin/bash
# Validate that pre-commit hook versions match installed venv versions
# Usage: ./scripts/validate-versions.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Validating pre-commit hook versions match venv..."
echo ""

# Activate venv if not already activated
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ -f "$PROJECT_ROOT/backend/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/backend/.venv/bin/activate"
    else
        echo -e "${RED}ERROR: Virtual environment not found at backend/.venv${NC}"
        exit 1
    fi
fi

# Get installed versions from venv
VENV_RUFF=$(ruff --version | awk '{print $2}')
VENV_MYPY=$(mypy --version | awk '{print $2}')

echo "Installed versions (venv):"
echo "  ruff: $VENV_RUFF"
echo "  mypy: $VENV_MYPY"
echo ""

# Get versions from .pre-commit-config.yaml
PRECOMMIT_CONFIG="$PROJECT_ROOT/.pre-commit-config.yaml"

if [ ! -f "$PRECOMMIT_CONFIG" ]; then
    echo -e "${RED}ERROR: .pre-commit-config.yaml not found${NC}"
    exit 1
fi

# Extract ruff version
PRECOMMIT_RUFF=$(grep -A 2 "ruff-pre-commit" "$PRECOMMIT_CONFIG" | grep "rev:" | sed 's/.*v\([0-9.]*\).*/\1/')

# Extract mypy version
PRECOMMIT_MYPY=$(grep -A 2 "mirrors-mypy" "$PRECOMMIT_CONFIG" | grep "rev:" | sed 's/.*v\([0-9.]*\).*/\1/')

echo "Pre-commit hook versions:"
echo "  ruff: $PRECOMMIT_RUFF"
echo "  mypy: $PRECOMMIT_MYPY"
echo ""

# Compare versions
MISMATCH=0

if [ "$VENV_RUFF" != "$PRECOMMIT_RUFF" ]; then
    echo -e "${YELLOW}WARNING: ruff version mismatch${NC}"
    echo "  venv: $VENV_RUFF"
    echo "  pre-commit: $PRECOMMIT_RUFF"
    echo "  Fix: Update rev in .pre-commit-config.yaml to v$VENV_RUFF"
    echo ""
    MISMATCH=1
fi

if [ "$VENV_MYPY" != "$PRECOMMIT_MYPY" ]; then
    echo -e "${YELLOW}WARNING: mypy version mismatch${NC}"
    echo "  venv: $VENV_MYPY"
    echo "  pre-commit: $PRECOMMIT_MYPY"
    echo "  Fix: Update rev in .pre-commit-config.yaml to v$VENV_MYPY"
    echo ""
    MISMATCH=1
fi

if [ $MISMATCH -eq 0 ]; then
    echo -e "${GREEN}✓ All versions match!${NC}"
    exit 0
else
    echo -e "${YELLOW}Version drift detected. Run 'pre-commit autoupdate' or manually update .pre-commit-config.yaml${NC}"
    exit 1
fi
# Version validation script
