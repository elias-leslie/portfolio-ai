#!/usr/bin/env bash
# End-to-end drill using disposable PostgreSQL databases and upload directories.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/project-root.sh"
PORTFOLIO_ROOT="$(resolve_portfolio_root)"
. "$SCRIPT_DIR/lib/portfolio-backup-common.sh"
load_portfolio_backup_env

BASE_URL="${BACKUP_DRILL_DATABASE_URL:-${PORTFOLIO_DB_URL:-${PORTFOLIO_AI_DB_URL:-}}}"
RUN_ID="$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
SOURCE_DB="portfolio_backup_source_$RUN_ID"
TARGET_DB="portfolio_backup_target_$RUN_ID"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/portfolio-backup-drill.XXXXXX")"
chmod 700 "$WORK_DIR"
DRILL_CONTAINER=""
DB_USER_RESOLVED=""
DB_PASSWORD_RESOLVED=""
DB_HOST_RESOLVED=""
DB_PORT_RESOLVED=""
PG_ADMIN_ARGS=()

configure_database_connection() {
    mapfile -t DB_PARTS < <(parse_portfolio_database_url "$BASE_URL")
    DB_USER_RESOLVED="${DB_PARTS[0]}"
    DB_PASSWORD_RESOLVED="${DB_PARTS[1]}"
    DB_HOST_RESOLVED="${DB_PARTS[2]}"
    DB_PORT_RESOLVED="${DB_PARTS[3]}"
    PG_ADMIN_ARGS=(--host "$DB_HOST_RESOLVED" --port "$DB_PORT_RESOLVED")
    if [ -n "$DB_USER_RESOLVED" ]; then
        PG_ADMIN_ARGS+=(--username "$DB_USER_RESOLVED")
    fi
}

drop_drill_databases() {
    if [ "${#PG_ADMIN_ARGS[@]}" -eq 0 ]; then
        return
    fi
    PGPASSWORD="$DB_PASSWORD_RESOLVED" dropdb --if-exists --force \
        "${PG_ADMIN_ARGS[@]}" "$SOURCE_DB" >/dev/null 2>&1 || true
    PGPASSWORD="$DB_PASSWORD_RESOLVED" dropdb --if-exists --force \
        "${PG_ADMIN_ARGS[@]}" "$TARGET_DB" >/dev/null 2>&1 || true
}

cleanup() {
    drop_drill_databases
    if [ -n "$DRILL_CONTAINER" ]; then
        docker rm -f "$DRILL_CONTAINER" >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

start_ephemeral_postgres() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "The configured database role cannot create drill databases and Docker is unavailable" >&2
        return 1
    fi
    local image="${BACKUP_DRILL_POSTGRES_IMAGE:-pgvector/pgvector:pg16@sha256:1d533553fefe4f12e5d80c7b80622ba0c382abb5758856f52983d8789179f0fb}"
    local password="portfolio_drill_$RUN_ID"
    local binding=""
    local health=""
    DRILL_CONTAINER="portfolio-backup-drill-${RUN_ID//_/-}"
    docker run --detach --rm \
        --name "$DRILL_CONTAINER" \
        --publish 127.0.0.1::5432 \
        --env POSTGRES_USER=portfolio_drill \
        --env "POSTGRES_PASSWORD=$password" \
        --env POSTGRES_DB=postgres \
        --health-cmd='pg_isready -U portfolio_drill -d postgres' \
        --health-interval=1s \
        --health-timeout=3s \
        --health-retries=30 \
        "$image" >/dev/null
    for _attempt in $(seq 1 35); do
        health="$(docker inspect -f '{{.State.Health.Status}}' "$DRILL_CONTAINER" 2>/dev/null || true)"
        if [ "$health" = "healthy" ]; then
            break
        fi
        if [ "$health" = "unhealthy" ]; then
            docker logs "$DRILL_CONTAINER" >&2 || true
            return 1
        fi
        sleep 1
    done
    if [ "$health" != "healthy" ]; then
        echo "Ephemeral drill PostgreSQL did not become healthy" >&2
        return 1
    fi
    binding="$(docker port "$DRILL_CONTAINER" 5432/tcp | head -n 1)"
    DB_PORT_RESOLVED="${binding##*:}"
    BASE_URL="postgresql://portfolio_drill:$password@127.0.0.1:$DB_PORT_RESOLVED/postgres"
    configure_database_connection
}

database_url_for() {
    python3 - "$BASE_URL" "$1" <<'PY'
from urllib.parse import quote, urlsplit, urlunsplit
import sys

parsed = urlsplit(sys.argv[1])
print(urlunsplit(parsed._replace(path="/" + quote(sys.argv[2], safe=""))))
PY
}

if [ -n "$BASE_URL" ]; then
    configure_database_connection
fi
if [ -z "$BASE_URL" ] || \
   ! PGPASSWORD="$DB_PASSWORD_RESOLVED" createdb "${PG_ADMIN_ARGS[@]}" "$SOURCE_DB" 2>"$WORK_DIR/createdb.error" || \
   ! PGPASSWORD="$DB_PASSWORD_RESOLVED" createdb "${PG_ADMIN_ARGS[@]}" "$TARGET_DB" 2>>"$WORK_DIR/createdb.error"; then
    if [ -s "$WORK_DIR/createdb.error" ]; then
        echo "Configured role cannot create disposable drill databases; using ephemeral PostgreSQL." >&2
    fi
    drop_drill_databases
    start_ephemeral_postgres
    PGPASSWORD="$DB_PASSWORD_RESOLVED" createdb "${PG_ADMIN_ARGS[@]}" "$SOURCE_DB"
    PGPASSWORD="$DB_PASSWORD_RESOLVED" createdb "${PG_ADMIN_ARGS[@]}" "$TARGET_DB"
fi
PGPASSWORD="$DB_PASSWORD_RESOLVED" psql "${PG_ADMIN_ARGS[@]}" --dbname "$SOURCE_DB" \
    --set ON_ERROR_STOP=1 \
    --command "CREATE TABLE backup_restore_marker (value text NOT NULL); INSERT INTO backup_restore_marker VALUES ('verified');" \
    >/dev/null

SOURCE_UPLOADS="$WORK_DIR/source_uploads"
TARGET_UPLOADS="$WORK_DIR/target_uploads"
mkdir -m 700 "$SOURCE_UPLOADS"
printf 'private upload restored\n' > "$SOURCE_UPLOADS/document-test.pdf"
chmod 600 "$SOURCE_UPLOADS/document-test.pdf"
ARTIFACT="$WORK_DIR/portfolio-ai-drill.tar.gz"

PORTFOLIO_DB_URL="$(database_url_for "$SOURCE_DB")" \
"$SCRIPT_DIR/portfolio-backup.sh" \
    --mode native \
    --upload-dir "$SOURCE_UPLOADS" \
    --output "$ARTIFACT" \
    --no-prune
PORTFOLIO_DB_URL="$(database_url_for "$TARGET_DB")" \
"$SCRIPT_DIR/portfolio-restore.sh" "$ARTIFACT" \
    --confirm \
    --mode native \
    --upload-dir "$TARGET_UPLOADS"

MARKER="$(PGPASSWORD="$DB_PASSWORD_RESOLVED" psql "${PG_ADMIN_ARGS[@]}" \
    --dbname "$TARGET_DB" --tuples-only --no-align \
    --command 'SELECT value FROM backup_restore_marker;')"
if [ "$MARKER" != "verified" ]; then
    echo "Database restore marker was not recovered" >&2
    exit 1
fi
cmp "$SOURCE_UPLOADS/document-test.pdf" "$TARGET_UPLOADS/document-test.pdf"
if [ "$(stat -c '%a' "$TARGET_UPLOADS")" != "700" ] || \
   [ "$(stat -c '%a' "$TARGET_UPLOADS/document-test.pdf")" != "600" ]; then
    echo "Restored upload permissions are not private" >&2
    exit 1
fi

echo "Backup/restore drill passed: database marker, upload bytes, and permissions verified"
