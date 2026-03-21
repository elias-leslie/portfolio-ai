#!/usr/bin/env bash

set -euo pipefail

PORTFOLIO_SCRIPTS_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTFOLIO_ROOT_FALLBACK="$(cd "$PORTFOLIO_SCRIPTS_LIB_DIR/../.." && pwd)"

resolve_portfolio_root() {
    local root=""

    if command -v st >/dev/null 2>&1; then
        root="$(ST_PROGRESS_ONLY=1 st projects root portfolio-ai 2>/dev/null | head -n 1 | tr -d '\r')"
    fi

    if [ -n "$root" ] && [ -d "$root" ]; then
        printf '%s\n' "$root"
        return 0
    fi

    printf '%s\n' "$PORTFOLIO_ROOT_FALLBACK"
}
