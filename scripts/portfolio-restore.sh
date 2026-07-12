#!/usr/bin/env bash
# Restore PostgreSQL plus private uploads from a verified complete artifact.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/lib/project-root.sh"
PORTFOLIO_ROOT="$(resolve_portfolio_root)"
. "$SCRIPT_DIR/lib/portfolio-backup-common.sh"

usage() {
    cat <<'EOF'
Usage: scripts/portfolio-restore.sh ARTIFACT [options]

Options:
  --confirm                   Required for a destructive restore
  --verify-only               Verify structure and every checksum, then exit
  --mode auto|native|compose  Deployment target (default: auto)
  --database-url URL          Native target PostgreSQL URL override
  --target-database NAME      Target DB name override (primarily for drills)
  --upload-dir DIR            Native/local upload directory override
  --skip-database             Restore uploads only
  --skip-uploads              Restore PostgreSQL only
  -h, --help                  Show this help
EOF
}

if [ "$#" -eq 0 ]; then
    usage >&2
    exit 2
fi

ARTIFACT=""
MODE="${PORTFOLIO_BACKUP_MODE:-auto}"
DATABASE_URL=""
TARGET_DATABASE=""
UPLOAD_DIR=""
CONFIRM=false
VERIFY_ONLY=false
RESTORE_DATABASE=true
RESTORE_UPLOADS=true

while [ "$#" -gt 0 ]; do
    case "$1" in
        --confirm)
            CONFIRM=true
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --mode)
            MODE="${2:?--mode requires a value}"
            shift 2
            ;;
        --database-url)
            DATABASE_URL="${2:?--database-url requires a URL}"
            shift 2
            ;;
        --target-database)
            TARGET_DATABASE="${2:?--target-database requires a name}"
            shift 2
            ;;
        --upload-dir)
            UPLOAD_DIR="${2:?--upload-dir requires a directory}"
            shift 2
            ;;
        --skip-database)
            RESTORE_DATABASE=false
            shift
            ;;
        --skip-uploads)
            RESTORE_UPLOADS=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [ -n "$ARTIFACT" ]; then
                echo "Only one backup artifact may be restored" >&2
                exit 2
            fi
            ARTIFACT="$1"
            shift
            ;;
    esac
done

if [ -z "$ARTIFACT" ]; then
    echo "A backup artifact path is required" >&2
    exit 2
fi
if [ "$RESTORE_DATABASE" = false ] && [ "$RESTORE_UPLOADS" = false ]; then
    echo "Nothing to restore: both payloads were skipped" >&2
    exit 2
fi

ARTIFACT="$(realpath "$ARTIFACT")"
MANIFEST_JSON="$(python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" verify --artifact "$ARTIFACT" --json)"
if [ "$VERIFY_ONLY" = true ]; then
    python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" verify --artifact "$ARTIFACT"
    exit 0
fi
if [ "$CONFIRM" != true ]; then
    echo "Restore is destructive; rerun with --confirm after verifying the target" >&2
    exit 2
fi

MANIFEST_DATABASE="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["database"]["name"])' <<<"$MANIFEST_JSON")"
load_portfolio_backup_env
DATABASE_URL="${DATABASE_URL:-${PORTFOLIO_DB_URL:-${PORTFOLIO_AI_DB_URL:-}}}"
MODE="$(resolve_portfolio_backup_mode "$MODE" "$DATABASE_URL")"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/portfolio-restore.XXXXXX")"
chmod 700 "$WORK_DIR"
RUNNING_COMPOSE_SERVICES=()
COMPOSE_SERVICES_STOPPED=false
NATIVE_UPLOAD_STAGE=""

cleanup() {
    local status=$?
    if [ "$status" -ne 0 ] && [ "$COMPOSE_SERVICES_STOPPED" = true ]; then
        portfolio_compose stop "${RUNNING_COMPOSE_SERVICES[@]}" >/dev/null 2>&1 || true
        echo "RESTORE FAILED. Compose app services remain stopped: ${RUNNING_COMPOSE_SERVICES[*]}." >&2
        echo "Resolve the reported error and rerun this restore. Do not restart app services until the restore completes successfully." >&2
    fi
    if [ -n "$NATIVE_UPLOAD_STAGE" ] && [ -d "$NATIVE_UPLOAD_STAGE" ]; then
        rm -rf -- "$NATIVE_UPLOAD_STAGE"
    fi
    rm -rf "$WORK_DIR"
    exit "$status"
}
trap cleanup EXIT

DATABASE_DUMP="$WORK_DIR/database.dump"
if [ "$RESTORE_DATABASE" = true ]; then
    python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" extract-database \
        --artifact "$ARTIFACT" \
        --output "$DATABASE_DUMP"
fi

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
    DB_NAME_RESOLVED="${TARGET_DATABASE:-${DB_PARTS[4]}}"
    if [ -z "$DB_NAME_RESOLVED" ]; then
        echo "Native target database name is missing" >&2
        exit 2
    fi
    if [ "$RESTORE_UPLOADS" = true ]; then
        UPLOAD_DIR="${UPLOAD_DIR:-${HOUSEHOLD_UPLOAD_DIR:-$PORTFOLIO_ROOT/data/household_uploads}}"
        UPLOAD_PARENT="$(dirname "$UPLOAD_DIR")"
        UPLOAD_NAME="$(basename "$UPLOAD_DIR")"
        NATIVE_UPLOAD_STAGE="$UPLOAD_PARENT/.${UPLOAD_NAME}.restore-${WORK_DIR##*.}"
        echo "Pre-staging private uploads on the target filesystem..."
        python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" restore-uploads \
            --artifact "$ARTIFACT" \
            --target "$NATIVE_UPLOAD_STAGE"
    fi
    if [ "$RESTORE_DATABASE" = true ]; then
        echo "Restoring PostgreSQL into '$DB_NAME_RESOLVED' (native)..."
        PG_ARGS=(--host "$DB_HOST_RESOLVED" --port "$DB_PORT_RESOLVED" --dbname "$DB_NAME_RESOLVED")
        if [ -n "$DB_USER_RESOLVED" ]; then
            PG_ARGS+=(--username "$DB_USER_RESOLVED")
        fi
        PGPASSWORD="$DB_PASSWORD_RESOLVED" pg_restore \
            --exit-on-error \
            --single-transaction \
            --clean \
            --if-exists \
            --no-owner \
            --no-privileges \
            "${PG_ARGS[@]}" \
            "$DATABASE_DUMP"
    fi
    if [ "$RESTORE_UPLOADS" = true ]; then
        echo "Restoring private uploads into '$UPLOAD_DIR'..."
        python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" install-staged-uploads \
            --source "$NATIVE_UPLOAD_STAGE" \
            --target "$UPLOAD_DIR"
        NATIVE_UPLOAD_STAGE=""
    fi
else
    if ! command -v docker >/dev/null 2>&1 || ! portfolio_compose_service_running portfolio-db; then
        echo "Compose restore requires the portfolio-db service to be running" >&2
        exit 1
    fi
    for service in portfolio-web portfolio-worker portfolio-api; do
        if portfolio_compose_service_running "$service"; then
            RUNNING_COMPOSE_SERVICES+=("$service")
        fi
    done
    if [ "${#RUNNING_COMPOSE_SERVICES[@]}" -gt 0 ]; then
        COMPOSE_SERVICES_STOPPED=true
        portfolio_compose stop "${RUNNING_COMPOSE_SERVICES[@]}"
    fi
    DB_USER_RESOLVED="$(portfolio_compose exec -T portfolio-db printenv POSTGRES_USER)"
    DB_NAME_RESOLVED="${TARGET_DATABASE:-$(portfolio_compose exec -T portfolio-db printenv POSTGRES_DB)}"
    if [ "$RESTORE_UPLOADS" = true ]; then
        RESTORED_UPLOADS="$WORK_DIR/household_uploads"
        python3 "$SCRIPT_DIR/portfolio_backup_artifact.py" restore-uploads \
            --artifact "$ARTIFACT" \
            --target "$RESTORED_UPLOADS"
        echo "Pre-staging the Docker Compose private-upload volume..."
        tar -C "$RESTORED_UPLOADS" -cf - . | portfolio_compose run \
            --rm -T --no-deps --entrypoint /bin/sh \
            -e PORTFOLIO_RESTORE_STAGE_NAME=.portfolio-restore-stage \
            portfolio-api -c '
                set -eu
                root=/app/data/household_uploads
                stage="$root/$PORTFOLIO_RESTORE_STAGE_NAME"
                rm -rf "$stage"
                mkdir -p "$stage"
                chmod 700 "$root" "$stage"
                tar -C "$stage" -xf -
                find "$stage" -type d -exec chmod 700 {} +
                find "$stage" -type f -exec chmod 600 {} +
            '
    fi
    if [ "$RESTORE_DATABASE" = true ]; then
        echo "Restoring PostgreSQL into '$DB_NAME_RESOLVED' (Docker Compose)..."
        portfolio_compose exec -T portfolio-db \
            pg_restore --exit-on-error --single-transaction --clean --if-exists \
            --no-owner --no-privileges \
            --username "$DB_USER_RESOLVED" --dbname "$DB_NAME_RESOLVED" < "$DATABASE_DUMP"
    fi
    if [ "$RESTORE_UPLOADS" = true ]; then
        echo "Restoring the Docker Compose private-upload volume..."
        portfolio_compose run \
            --rm -T --no-deps --entrypoint /bin/sh \
            -e PORTFOLIO_RESTORE_STAGE_NAME=.portfolio-restore-stage \
            portfolio-api -c '
                set -eu
                root=/app/data/household_uploads
                stage="$root/$PORTFOLIO_RESTORE_STAGE_NAME"
                bundle=/tmp/portfolio-restore-uploads.tar
                test -d "$stage"
                tar -C "$stage" -cf "$bundle" .
                find "$root" -mindepth 1 -maxdepth 1 \
                    ! -name "$PORTFOLIO_RESTORE_STAGE_NAME" -exec rm -rf -- {} +
                tar -C "$root" -xf "$bundle"
                rm -rf "$stage" "$bundle"
                find "$root" -type d -exec chmod 700 {} +
                find "$root" -type f -exec chmod 600 {} +
            '
    fi
    if [ "${#RUNNING_COMPOSE_SERVICES[@]}" -gt 0 ]; then
        if ! portfolio_compose up -d "${RUNNING_COMPOSE_SERVICES[@]}"; then
            portfolio_compose stop "${RUNNING_COMPOSE_SERVICES[@]}" >/dev/null 2>&1 || true
            exit 1
        fi
        COMPOSE_SERVICES_STOPPED=false
    fi
fi

echo "Restore complete from: $ARTIFACT"
echo "Source database recorded in manifest: $MANIFEST_DATABASE"
