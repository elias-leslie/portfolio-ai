#!/bin/bash
#
# Portfolio-AI Restore Script
# Restores from backup archive on Davion-Sidar SMB share
#
# Usage:
#   ./scripts/restore.sh --latest              # Restore latest backup
#   ./scripts/restore.sh --list                # List available backups
#   ./scripts/restore.sh <archive-name>        # Restore specific backup
#   ./scripts/restore.sh --db-only <archive>   # Restore database only
#   ./scripts/restore.sh --files-only <archive> # Restore files only (no DB)
#
# WARNING: This will OVERWRITE existing data!

set -euo pipefail

# Load utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/backup-utils.sh"

# Local configuration
RESTORE_DIR="/tmp/portfolio-ai-restore-$$"

# Cleanup function
cleanup() {
    if [ -d "$RESTORE_DIR" ]; then
        rm -rf "$RESTORE_DIR"
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [options] [archive-name]"
    echo ""
    echo "Options:"
    echo "  --latest       Restore the latest backup"
    echo "  --list         List available backups"
    echo "  --db-only      Restore database only"
    echo "  --files-only   Restore files only (no database)"
    echo "  --no-confirm   Skip confirmation prompt"
    echo "  --dry-run      Show what would be restored without doing it"
    echo ""
    echo "Examples:"
    echo "  $0 --latest"
    echo "  $0 --list"
    echo "  $0 portfolio-ai-20251211-143000.tar.gz"
    echo "  $0 --db-only --latest"
}

# List available backups
list_backups() {
    echo ""
    echo "Available backups on //$SMB_HOST/$SMB_SHARE/$SMB_PATH:"
    echo ""

    ensure_smb_credentials

    if ! test_smb_connection 2>/dev/null; then
        log_error "Cannot connect to SMB share"
        exit 1
    fi

    local backups=($(smb_list_backups))
    local count=${#backups[@]}

    if [ "$count" -eq 0 ]; then
        echo "  No backups found"
    else
        # Show backups in reverse order (newest first)
        for ((i=count-1; i>=0; i--)); do
            local backup="${backups[$i]}"
            # Extract timestamp from filename
            local ts=$(echo "$backup" | sed 's/portfolio-ai-\([0-9-]*\)\.tar\.gz/\1/')
            local date_part="${ts:0:8}"
            local time_part="${ts:9:6}"
            local formatted="${date_part:0:4}-${date_part:4:2}-${date_part:6:2} ${time_part:0:2}:${time_part:2:2}:${time_part:4:2}"

            if [ $i -eq $((count-1)) ]; then
                echo -e "  ${GREEN}$backup${NC} ($formatted) [LATEST]"
            else
                echo "  $backup ($formatted)"
            fi
        done
    fi

    echo ""
    echo "Total: $count backups"
    echo ""
}

# Get latest backup name
get_latest_backup() {
    local backups=($(smb_list_backups))
    local count=${#backups[@]}

    if [ "$count" -eq 0 ]; then
        echo ""
        return 1
    fi

    # Return last (newest) backup
    echo "${backups[$((count-1))]}"
}

# Download backup
download_backup() {
    local archive_name="$1"
    local local_path="$RESTORE_DIR/$archive_name"

    mkdir -p "$RESTORE_DIR"

    smb_download "$archive_name" "$local_path"
    echo "$local_path"
}

# Extract archive
extract_archive() {
    local archive_path="$1"
    local extract_dir="$RESTORE_DIR/extracted"

    mkdir -p "$extract_dir"

    log "Extracting archive..."
    tar --extract --gzip --file="$archive_path" --directory="$extract_dir"
    log_success "Extraction complete"

    echo "$extract_dir"
}

# Restore database
restore_database() {
    local extract_dir="$1"

    # Find database dump
    local db_dump=""
    if [ -f "$extract_dir/portfolio-ai/database.sql.gz" ]; then
        db_dump="$extract_dir/portfolio-ai/database.sql.gz"
    elif [ -f "$extract_dir/database.sql.gz" ]; then
        db_dump="$extract_dir/database.sql.gz"
    else
        log_error "Database dump not found in archive"
        return 1
    fi

    log "Stopping services..."
    bash "$PROJECT_DIR/scripts/shutdown.sh" 2>/dev/null || true

    log "Restoring database..."

    # Create temporary SQL file for restore
    local restore_sql="$RESTORE_DIR/restore.sql"
    gunzip -c "$db_dump" > "$restore_sql"

    # Restore using psql
    log "  Importing data (this may take a minute)..."
    if psql -U "$DB_USER" -h localhost -d "$DB_NAME" -f "$restore_sql" >/dev/null 2>&1; then
        log_success "Database restored"
    else
        log_warn "Some restore warnings occurred (this is often normal)"
    fi

    rm -f "$restore_sql"
}

# Restore files
restore_files() {
    local extract_dir="$1"

    # Find source directory
    local source_dir=""
    if [ -d "$extract_dir/portfolio-ai" ]; then
        source_dir="$extract_dir/portfolio-ai"
    else
        source_dir="$extract_dir"
    fi

    log "Restoring files..."

    # Restore data directory
    if [ -d "$source_dir/data" ]; then
        log "  Restoring data/..."
        rsync -a "$source_dir/data/" "$PROJECT_DIR/data/"
    fi

    # Restore backups directory
    if [ -d "$source_dir/backups" ]; then
        log "  Restoring backups/..."
        rsync -a "$source_dir/backups/" "$PROJECT_DIR/backups/"
    fi

    # Restore solution_state
    if [ -d "$source_dir/solution_state" ]; then
        log "  Restoring solution_state/..."
        rsync -a "$source_dir/solution_state/" "$PROJECT_DIR/solution_state/"
    fi

    # Restore reports
    if [ -d "$source_dir/reports" ]; then
        log "  Restoring reports/..."
        rsync -a "$source_dir/reports/" "$PROJECT_DIR/reports/"
    fi

    # Restore .claude (selective - don't overwrite commands/rules)
    if [ -f "$source_dir/.claude/settings.local.json" ]; then
        log "  Restoring .claude/settings.local.json..."
        cp "$source_dir/.claude/settings.local.json" "$PROJECT_DIR/.claude/" 2>/dev/null || true
    fi
    if [ -d "$source_dir/.claude/state" ]; then
        log "  Restoring .claude/state/..."
        rsync -a "$source_dir/.claude/state/" "$PROJECT_DIR/.claude/state/" 2>/dev/null || true
    fi
    if [ -d "$source_dir/.claude/backups" ]; then
        log "  Restoring .claude/backups/..."
        rsync -a "$source_dir/.claude/backups/" "$PROJECT_DIR/.claude/backups/" 2>/dev/null || true
    fi

    # Restore .env files (CRITICAL)
    if [ -f "$source_dir/.env" ]; then
        log "  Restoring .env..."
        cp "$source_dir/.env" "$PROJECT_DIR/.env"
    fi
    if [ -f "$source_dir/backend/.env" ]; then
        log "  Restoring backend/.env..."
        cp "$source_dir/backend/.env" "$PROJECT_DIR/backend/.env"
    fi
    if [ -f "$source_dir/frontend/.env.local" ]; then
        log "  Restoring frontend/.env.local..."
        cp "$source_dir/frontend/.env.local" "$PROJECT_DIR/frontend/.env.local"
    fi

    log_success "Files restored"
}

# Confirmation prompt
confirm_restore() {
    local archive_name="$1"

    echo ""
    echo "========================================"
    echo -e "${RED}WARNING: DESTRUCTIVE OPERATION${NC}"
    echo "========================================"
    echo ""
    echo "This will restore from: $archive_name"
    echo ""
    echo "The following may be OVERWRITTEN:"
    echo "  - PostgreSQL database ($DB_NAME)"
    echo "  - data/ directory"
    echo "  - .env files (API keys)"
    echo "  - .claude/ settings and state"
    echo "  - solution_state/ directory"
    echo "  - reports/ directory"
    echo ""
    read -p "Type 'RESTORE' to confirm: " confirm

    if [ "$confirm" != "RESTORE" ]; then
        log_error "Restore cancelled"
        exit 1
    fi
}

# Main function
main() {
    local archive_name=""
    local restore_db=true
    local restore_files_flag=true
    local skip_confirm=false
    local list_only=false
    local use_latest=false
    local dry_run=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --latest)
                use_latest=true
                shift
                ;;
            --list)
                list_only=true
                shift
                ;;
            --db-only)
                restore_files_flag=false
                shift
                ;;
            --files-only)
                restore_db=false
                shift
                ;;
            --no-confirm)
                skip_confirm=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
            *)
                archive_name="$1"
                shift
                ;;
        esac
    done

    # Handle --list
    if [ "$list_only" = true ]; then
        list_backups
        exit 0
    fi

    # Ensure SMB credentials
    ensure_smb_credentials

    # Get archive name
    if [ "$use_latest" = true ]; then
        archive_name=$(get_latest_backup)
        if [ -z "$archive_name" ]; then
            log_error "No backups found"
            exit 1
        fi
        log "Latest backup: $archive_name"
    fi

    if [ -z "$archive_name" ]; then
        show_usage
        exit 1
    fi

    # Dry run
    if [ "$dry_run" = true ]; then
        echo ""
        echo "DRY RUN - Would restore from: $archive_name"
        echo ""
        echo "Would restore:"
        [ "$restore_db" = true ] && echo "  - Database ($DB_NAME)"
        [ "$restore_files_flag" = true ] && echo "  - Files (data/, .env, .claude/, etc.)"
        echo ""
        exit 0
    fi

    # Confirm
    if [ "$skip_confirm" = false ]; then
        confirm_restore "$archive_name"
    fi

    echo ""
    echo "========================================"
    echo "Portfolio-AI Restore"
    echo "========================================"
    echo ""

    # Setup cleanup trap
    trap cleanup EXIT

    # Download
    log "Downloading backup..."
    local archive_path=$(download_backup "$archive_name")

    # Extract
    local extract_dir=$(extract_archive "$archive_path")

    # Restore database
    if [ "$restore_db" = true ]; then
        restore_database "$extract_dir"
    else
        log "Skipping database restore (--files-only)"
    fi

    # Restore files
    if [ "$restore_files_flag" = true ]; then
        restore_files "$extract_dir"
    else
        log "Skipping file restore (--db-only)"
    fi

    # Start services
    log "Starting services..."
    bash "$PROJECT_DIR/scripts/start.sh"

    echo ""
    echo "========================================"
    log_success "Restore complete!"
    echo "========================================"
    echo ""
    echo "  Restored from: $archive_name"
    echo "  Database: $([ "$restore_db" = true ] && echo 'Yes' || echo 'No')"
    echo "  Files: $([ "$restore_files_flag" = true ] && echo 'Yes' || echo 'No')"
    echo ""
    echo "  Verify with: bash ~/portfolio-ai/scripts/status.sh"
    echo ""
}

main "$@"
