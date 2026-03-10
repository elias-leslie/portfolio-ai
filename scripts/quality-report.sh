#!/bin/bash
# Lightweight quality-report shim for Portfolio AI.
# Usage: scripts/quality-report.sh [--slow]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$ROOT_DIR"

if [ "${1:-}" = "--slow" ]; then
  dt --check
  dt pytest backend/tests --runslow
  exit 0
fi

dt --check
