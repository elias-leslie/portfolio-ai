#!/bin/bash
# Run the verification harness using dev-companion's venv (has claude-agent-sdk)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/portfolio-ai/services/dev-companion/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: dev-companion venv not found at $VENV_DIR"
    echo "Install claude-agent-sdk: pip install claude-agent-sdk"
    exit 1
fi

source "$VENV_DIR/bin/activate"
cd "$SCRIPT_DIR"
python verify_devvision.py "$@"
