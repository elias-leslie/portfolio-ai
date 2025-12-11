#!/bin/bash
#
# Portfolio-AI Backup Script
# Creates compressed backup archive and transfers to Davion-Sidar SMB share
#
# Usage:
#   ./scripts/backup.sh              # Full backup
#   ./scripts/backup.sh --quick      # Skip DB dump (use existing daily)
#   ./scripts/backup.sh --local      # Local only (no transfer)
#   ./scripts/backup.sh --status     # Show status only
#
# Destination: //192.168.8.128/davion-gem/project-backups/portfolio-ai/
# Retention: 30 versions (newest kept, oldest deleted)

set -euo pipefail

# Load utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/backup-utils.sh"

# Local configuration
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="portfolio-ai-${TIMESTAMP}.tar.gz"
STAGING_DIR="/tmp/portfolio-ai-backup-$$"

# Parse arguments
QUICK_MODE=false
LOCAL_ONLY=false
STATUS_ONLY=false

for arg in "$@"; do
    case $arg in
        --quick) QUICK_MODE=true ;;
        --local) LOCAL_ONLY=true ;;
        --status) STATUS_ONLY=true ;;
        --help|-h)
            echo "Usage: $0 [--quick] [--local] [--status]"
            echo ""
            echo "Options:"
            echo "  --quick   Skip fresh DB dump, use existing daily backup"
            echo "  --local   Create archive locally only, skip transfer"
            echo "  --status  Show backup status only, don't create new backup"
            echo ""
            echo "Destination: //$SMB_HOST/$SMB_SHARE/$SMB_PATH"
            echo "Retention: $MAX_BACKUPS backups"
            exit 0
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
}
trap cleanup EXIT

# Show status function
show_status() {
    echo ""
    echo "========================================"
    echo "Backup Status"
    echo "========================================"
    echo ""

    # Check local index
    if [ -f "$BACKUP_INDEX" ]; then
        local count=$(jq '.backups | length' "$BACKUP_INDEX")
        local latest=$(jq -r '.backups[0].name // "none"' "$BACKUP_INDEX")
        local latest_date=$(jq -r '.backups[0].timestamp // "never"' "$BACKUP_INDEX")
        local latest_size=$(jq -r '.backups[0].size_bytes // 0' "$BACKUP_INDEX")

        echo "Index file: $BACKUP_INDEX"
        echo "Total backups: $count"
        echo "Latest: $latest"
        echo "Date: $latest_date"
        echo "Size: $(numfmt --to=iec $latest_size 2>/dev/null || echo "$latest_size bytes")"
    else
        echo "No backup index found"
    fi

    echo ""

    # Check SMB connection if credentials exist
    if [ -f "$CREDENTIALS_FILE" ]; then
        echo "SMB Destination: //$SMB_HOST/$SMB_SHARE/$SMB_PATH"
        if test_smb_connection 2>/dev/null; then
            echo "Connection: OK"
            echo ""
            echo "Remote backups:"
            smb_list_backups | tail -5 | while read backup; do
                echo "  $backup"
            done
        else
            echo "Connection: FAILED"
        fi
    else
        echo "SMB credentials not configured"
        echo "Run backup once to set up credentials"
    fi

    echo ""
}

# Database dump function
dump_database() {
    local dump_file="$1"

    if [ "$QUICK_MODE" = true ]; then
        log "Quick mode: Using existing daily backup"
        local daily_backup="$PROJECT_DIR/backups/portfolio_ai_daily.sql.gz"

        if [ -f "$daily_backup" ]; then
            cp "$daily_backup" "$dump_file"
            log_success "Copied existing daily backup ($(du -h "$dump_file" | cut -f1))"
        else
            log_warn "No daily backup found at $daily_backup, creating fresh dump..."
            pg_dump -U "$DB_USER" -h localhost "$DB_NAME" | gzip > "$dump_file"
        fi
    else
        log "Creating fresh PostgreSQL dump..."
        if pg_dump -U "$DB_USER" -h localhost "$DB_NAME" | gzip > "$dump_file"; then
            log_success "Database dump created ($(du -h "$dump_file" | cut -f1))"
        else
            log_error "Database dump failed"
            return 1
        fi
    fi
}

# Create archive function
create_archive() {
    local archive_path="$1"
    local db_dump="$2"
    local tar_path="${archive_path%.gz}"  # Remove .gz for initial tar

    log "Creating archive..."

    cd "$PROJECT_DIR"

    # Build list of files/dirs to include (only those that exist)
    local include_list=()

    [ -d "data/artifacts" ] && include_list+=("data/artifacts")
    for f in data/*.json; do [ -f "$f" ] && include_list+=("$f"); done
    for f in backups/*.sql.gz; do [ -f "$f" ] && include_list+=("$f"); done
    [ -d "reports" ] && include_list+=("reports")
    [ -d "solution_state" ] && include_list+=("solution_state")
    [ -f ".claude/settings.local.json" ] && include_list+=(".claude/settings.local.json")
    [ -d ".claude/state" ] && include_list+=(".claude/state")
    [ -d ".claude/backups" ] && include_list+=(".claude/backups")
    [ -f ".env" ] && include_list+=(".env")
    [ -f "backend/.env" ] && include_list+=("backend/.env")
    [ -f "frontend/.env.local" ] && include_list+=("frontend/.env.local")

    # Ensure database dump is in staging dir with proper name
    if [ "$db_dump" != "$STAGING_DIR/database.sql.gz" ]; then
        cp "$db_dump" "$STAGING_DIR/database.sql.gz"
    fi

    # Create tar archive (uncompressed first)
    tar --create \
        --file="$tar_path" \
        --exclude='*.db' \
        --exclude='*.db.backup.*' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        --exclude='*.log' \
        --transform='s|^|portfolio-ai/|' \
        "${include_list[@]}" 2>/dev/null || true

    # Add database dump to archive
    tar --append \
        --file="$tar_path" \
        --transform="s|^|portfolio-ai/|" \
        -C "$STAGING_DIR" "database.sql.gz"

    # Now gzip the archive
    gzip -f "$tar_path"

    log_success "Archive created: $(du -h "$archive_path" | cut -f1)"
}

# Main function
main() {
    # Handle --status
    if [ "$STATUS_ONLY" = true ]; then
        show_status
        exit 0
    fi

    echo ""
    echo "========================================"
    echo "Portfolio-AI Backup"
    echo "========================================"
    echo ""

    # Setup
    mkdir -p "$STAGING_DIR"
    local db_dump="$STAGING_DIR/database.sql.gz"
    local archive_path="$STAGING_DIR/$ARCHIVE_NAME"

    # Dump database
    dump_database "$db_dump"
    local db_size=$(stat -c%s "$db_dump" 2>/dev/null || stat -f%z "$db_dump" 2>/dev/null || echo "0")

    # Create archive
    create_archive "$archive_path" "$db_dump"
    local archive_size=$(stat -c%s "$archive_path" 2>/dev/null || stat -f%z "$archive_path" 2>/dev/null || echo "0")

    # Local only mode
    if [ "$LOCAL_ONLY" = true ]; then
        local final_path="$PROJECT_DIR/backups/$ARCHIVE_NAME"
        cp "$archive_path" "$final_path"
        log_success "Local backup created: $final_path"
        echo ""
        echo "Archive: $final_path"
        echo "Size: $(du -h "$final_path" | cut -f1)"
        return 0
    fi

    # Setup SMB credentials if needed
    ensure_smb_credentials

    # Test connection
    if ! test_smb_connection; then
        log_error "Cannot connect to SMB share. Check credentials and network."
        exit 1
    fi

    # Upload to remote
    smb_upload "$archive_path" "$SMB_PATH" "$ARCHIVE_NAME"

    # Apply retention policy
    apply_retention

    # Update backup index
    update_backup_index "$ARCHIVE_NAME" "$archive_size" "$db_size" "ok"

    echo ""
    echo "========================================"
    log_success "Backup complete!"
    echo "========================================"
    echo ""
    echo "  Archive: $ARCHIVE_NAME"
    echo "  Size: $(numfmt --to=iec $archive_size 2>/dev/null || echo "$archive_size bytes")"
    echo "  DB Size: $(numfmt --to=iec $db_size 2>/dev/null || echo "$db_size bytes")"
    echo "  Location: //$SMB_HOST/$SMB_SHARE/$SMB_PATH/$ARCHIVE_NAME"
    echo ""
    echo "  Index updated: $BACKUP_INDEX"
    echo ""
}

main "$@"
