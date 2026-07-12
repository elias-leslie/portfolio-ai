#!/usr/bin/env bash

set -euo pipefail

load_portfolio_backup_env() {
    local env_file=""
    local had_db_url=false
    local had_legacy_db_url=false
    local existing_db_url="${PORTFOLIO_DB_URL:-}"
    local existing_legacy_db_url="${PORTFOLIO_AI_DB_URL:-}"
    if [ -n "${PORTFOLIO_DB_URL+x}" ]; then
        had_db_url=true
    fi
    if [ -n "${PORTFOLIO_AI_DB_URL+x}" ]; then
        had_legacy_db_url=true
    fi
    for env_file in "$PORTFOLIO_ROOT/.env" "$PORTFOLIO_ROOT/.env.local"; do
        if [ -f "$env_file" ]; then
            set -a
            # shellcheck disable=SC1090
            . "$env_file"
            set +a
        fi
    done
    if [ "$had_db_url" = true ]; then
        export PORTFOLIO_DB_URL="$existing_db_url"
    fi
    if [ "$had_legacy_db_url" = true ]; then
        export PORTFOLIO_AI_DB_URL="$existing_legacy_db_url"
    fi
}

parse_portfolio_database_url() {
    local database_url="$1"
    python3 - "$database_url" <<'PY'
from urllib.parse import unquote, urlparse
import sys

parsed = urlparse(sys.argv[1])
if parsed.scheme not in {"postgres", "postgresql"}:
    raise SystemExit("Database URL must use postgres:// or postgresql://")
print(unquote(parsed.username or ""))
print(unquote(parsed.password or ""))
print(parsed.hostname or "localhost")
print(parsed.port or 5432)
print(unquote((parsed.path or "/")[1:]))
PY
}

portfolio_compose_service_running() {
    local service="$1"
    local container_id=""
    container_id="$(docker compose -f "$PORTFOLIO_ROOT/docker-compose.yml" ps -q "$service" 2>/dev/null || true)"
    [ -n "$container_id" ] && [ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null || true)" = "true" ]
}

resolve_portfolio_backup_mode() {
    local requested="$1"
    local database_url="$2"
    case "$requested" in
        native|compose)
            printf '%s\n' "$requested"
            ;;
        auto)
            if [ -n "$database_url" ]; then
                printf 'native\n'
            elif command -v docker >/dev/null 2>&1 && portfolio_compose_service_running portfolio-db; then
                printf 'compose\n'
            else
                printf 'native\n'
            fi
            ;;
        *)
            echo "Unsupported deployment mode: $requested" >&2
            return 2
            ;;
    esac
}

portfolio_compose() {
    docker compose -f "$PORTFOLIO_ROOT/docker-compose.yml" "$@"
}
