#!/bin/bash
# Unified verification runner for Portfolio AI.
#
# Usage:
#   ./scripts/test-all.sh
#   ./scripts/test-all.sh --slow

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
      echo "Usage: ./scripts/test-all.sh [--slow]" >&2
      exit 1
      ;;
  esac
done

cd "$ROOT_DIR"

echo "== backend: install =="
(
  cd backend
  uv sync --python 3.13 --frozen --extra dev
)

echo ""
echo "== backend: ruff =="
(
  cd backend
  uv run ruff check app tests
)

echo ""
echo "== backend: ty =="
(
  cd backend
  uv run ty check app
)

echo ""
echo "== backend: pytest =="
(
  cd backend
  uv run pytest
)

echo ""
echo "== frontend: install =="
(
  cd frontend
  pnpm install --frozen-lockfile
)

echo ""
echo "== frontend: lint =="
(
  cd frontend
  pnpm lint
)

echo ""
echo "== frontend: typecheck =="
(
  cd frontend
  pnpm exec tsc --noEmit
)

echo ""
echo "== frontend: tests =="
(
  cd frontend
  pnpm test -- --run
)

echo ""
echo "== frontend: build =="
(
  cd frontend
  pnpm build
)

if [ "$RUN_SLOW" = true ]; then
  echo ""
  echo "== backend: slow pytest =="
  (
    cd backend
    uv run pytest tests --runslow
  )
fi
