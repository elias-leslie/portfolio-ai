#!/usr/bin/env bash
# Create one verified backup artifact containing PostgreSQL plus private uploads.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/project-root.sh"
PORTFOLIO_ROOT="$(resolve_portfolio_root)"
. "$SCRIPT_DIR/lib/portfolio-backup-common.sh"

usage() {
    cat <<'EOF'
Usage: scripts/portfolio-backup.sh [options]

Options:
  --mode auto|native|compose  Deployment source (default: auto)
  --backup-dir DIR           Artifact directory (default: data/backups)
  --output FILE              Exact artifact path
  --database-url URL         Native PostgreSQL URL override
  --upload-dir DIR           Native/local upload directory override
  --keep-days DAYS           Prune complete artifacts older than DAYS (default: 30)
  --no-prune                 Do not prune old complete artifacts
  -h, --help                 Show this help
EOF
}

MODE="${PORTFOLIO_BACKUP_MODE:-auto}"
BACKUP_DIR="$PORTFOLIO_ROOT/data/backups"
OUTPUT=""
DATABASE_URL=""
UPLOAD_DIR=""
KEEP_DAYS=30
PRUNE=true

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mode)
            MODE="${2:?--mode requires a value}"
            shift 2
            ;;
        --backup-dir)
            BACKUP_DIR="${2:?--backup-dir requires a directory}"
            shift 2
            ;;
        --output)
            OUTPUT="${2:?--output requires a file}"
            shift 2
            ;;
        --database-url)
            DATABASE_URL="${2:?--database-url requires a URL}"
            shift 2
            ;;
        --upload-dir)
            UPLOAD_DIR="${2:?--upload-dir requires a directory}"
            shift 2
            ;;
        --keep-days)
            KEEP_DAYS="${2:?--keep-days requires a number}"
            shift 2
            ;;
        --no-prune)
            PRUNE=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! [[ "$KEEP_DAYS" =~ ^[0-9]+$ ]]; then
    echo "--keep-days must be a non-negative integer" >&2
    exit 2
fi

load_portfolio_backup_env
DATABASE_URL="${DATABASE_URL:-${PORTFOLIO_DB_URL:-${PORTFOLIO_AI_DB_URL:-}}}"
MODE="$(resolve_portfolio_backup_mode "$MODE" "$DATABASE_URL")"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUTPUT" ]; then
    OUTPUT="$BACKUP_DIR/portfolio_ai_complete_$TIMESTAMP.tar.gz"
else
    BACKUP_DIR="$(dirname "$OUTPUT")"
fi
mkdir -p -m 700 "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

WORK_DIR="$(mktemp -d "$BACKUP_DIR/.portfolio-backup.XXXXXX")"
chmod 700 "$WORK_DIR"
PAUSED_COMPOSE_SERVICES=()
cleanup() {
    local status=$?
    if [ "${#PAUSED_COMPOSE_SERVICES[@]}" -gt 0 ]; then
        portfolio_compose unpause "${PAUSED_COMPOSE_SERVICES[@]}" >/dev/null || true
    fi
    rm -rf "$WORK_DIR"
    exit "$status"
}
trap cleanup EXIT
DATABASE_DUMP="$WORK_DIR/database.dump"
UPLOAD_SNAPSHOT=""
DB_NAME=""

if [ "$MODE" = "native" ]; then
    if [ -n "$DATABASE_URL" ]; then
        mapfile -t DB_PARTS < <(parse_portfolio_database_url "$DATABASE_URL")
    else
        DB_PARTS=(
            "${DB_USER:-portfolio_app}"
            "${DB_PASSWORD:-}"
            "${DB_HOST:-localhost}"
            "${DB_PORT:-5432}"
            "${DB_NAME:-portfolio_ai}"
        )
    fi
    DB_USER_RESOLVED="${DB_PARTS[0]}"
    DB_PASSWORD_RESOLVED="${DB_PARTS[1]}"
    DB_HOST_RESOLVED="${DB_PARTS[2]}"
    DB_PORT_RESOLVED="${DB_PARTS[3]}"
    DB_NAME="${DB_PARTS[4]}"
    if [ -z "$DB_NAME" ]; then
        echo "Native database URL must include a database name" >&2
        exit 2
    fi
    PG_ARGS=(--host "$DB_HOST_RESOLVED" --port "$DB_PORT_RESOLVED" --dbname "$DB_NAME")
    if [ -n "$DB_USER_RESOLVED" ]; then
        PG_ARGS+=(--username "$DB_USER_RESOLVED")
    fi
    echo "Backing up PostgreSQL database '$DB_NAME' (native)..."
    PGPASSWORD="$DB_PASSWORD_RESOLVED" pg_dump \
        --format=custom \
        --compress=6 \
        --no-owner \
        --no-privileges \
        --file "$DATABASE_DUMP" \
        "${PG_ARGS[@]}"
    UPLOAD_SNAPSHOT="${UPLOAD_DIR:-${HOUSEHOLD_UPLOAD_DIR:-$PORTFOLIO_ROOT/data/household_uploads}}"
else
    if ! command -v docker >/dev/null 2>&1 || ! portfolio_compose_service_running portfolio-db; then
        echo "Compose backup requires the portfolio-db service to be running" >&2
        exit 1
    fi
    UPLOAD_CONTAINER=""
    if [ -z "$UPLOAD_DIR" ]; then
        for service in portfolio-api portfolio-worker; do
            if portfolio_compose_service_running "$service"; then
                UPLOAD_CONTAINER="$(portfolio_compose ps -q "$service")"
                break
            fi
        done
        if [ -z "$UPLOAD_CONTAINER" ]; then
            echo "Compose backup requires portfolio-api or portfolio-worker to snapshot uploads" >&2
            exit 1
        fi
    fi
    for service in portfolio-api portfolio-worker; do
        if portfolio_compose_service_running "$service"; then
            PAUSED_COMPOSE_SERVICES+=("$service")
        fi
    done
    if [ "${#PAUSED_COMPOSE_SERVICES[@]}" -gt 0 ]; then
        echo "Pausing write-capable app services for a consistent DB/upload snapshot..."
        portfolio_compose pause "${PAUSED_COMPOSE_SERVICES[@]}"
    fi
    DB_NAME="$(portfolio_compose exec -T portfolio-db printenv POSTGRES_DB)"
    DB_USER_RESOLVED="$(portfolio_compose exec -T portfolio-db printenv POSTGRES_USER)"
    echo "Backing up PostgreSQL database '$DB_NAME' (Docker Compose)..."
    portfolio_compose exec -T portfolio-db \
        pg_dump --format=custom --compress=6 --no-owner --no-privileges \
        --username "$DB_USER_RESOLVED" --dbname "$DB_NAME" > "$DATABASE_DUMP"
    if [ -n "$UPLOAD_DIR" ]; then
        UPLOAD_SNAPSHOT="$UPLOAD_DIR"
    else
        UPLOAD_SNAPSHOT="$WORK_DIR/household_uploads"
        mkdir -m 700 "$UPLOAD_SNAPSHOT"
        docker cp "$UPLOAD_CONTAINER:/app/data/household_uploads/." "$UPLOAD_SNAPSHOT/"
    fi
fi

python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" create \
    --database-dump "$DATABASE_DUMP" \
    --upload-root "$UPLOAD_SNAPSHOT" \
    --output "$OUTPUT" \
    --deployment-mode "$MODE" \
    --database-name "$DB_NAME" >/dev/null
python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" verify --artifact "$OUTPUT"

if [ "$PRUNE" = true ]; then
    find "$BACKUP_DIR" \
        -name 'portfolio_ai_complete_*.tar.gz' \
        -type f \
        -mtime "+$KEEP_DAYS" \
        -delete
fi

chmod 600 "$OUTPUT"
echo "Backup complete: $OUTPUT"
