#!/bin/bash
# Unified verification runner for Portfolio AI.
#
# Usage:
#   bash ~/portfolio-ai/scripts/test-all.sh
#   bash ~/portfolio-ai/scripts/test-all.sh --slow

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
RUN_SLOW=false

for arg in "$@"; do
  case "$arg" in
    --slow)
      RUN_SLOW=true
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: bash ~/portfolio-ai/scripts/test-all.sh [--slow]" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT_DIR"

echo "== dt --check =="
dt --check

if [ "$RUN_SLOW" = true ]; then
  echo ""
  echo "== dt pytest backend/tests --runslow =="
  dt pytest backend/tests --runslow
fi
