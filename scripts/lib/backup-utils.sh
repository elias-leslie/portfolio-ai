#!/bin/bash
#
# Backup Utilities
# Shared functions for backup and restore scripts
#

# Colors
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export RED='\033[0;31m'
export BLUE='\033[0;34m'
export NC='\033[0m'

# Configuration
export PROJECT_DIR="${PROJECT_DIR:-$HOME/portfolio-ai}"
export SMB_HOST="192.168.8.128"
export SMB_SHARE="davion-gem"
export SMB_PATH="project-backups/portfolio-ai"
export SMB_USER="${SMB_USER:-backup-svc}"
export CREDENTIALS_FILE="$HOME/.smbcredentials"
export BACKUP_INDEX="$PROJECT_DIR/backup-index.json"
export MAX_BACKUPS=30

# Database config - load from ~/.env.local if available
if [ -f "$HOME/.env.local" ]; then
    # Parse DATABASE_URL from env.local to extract password
    # Format: postgresql://user:password@host:port/dbname
    _db_url=$(grep "^PORTFOLIO_DB_URL=" "$HOME/.env.local" | cut -d'=' -f2-)
    if [ -n "$_db_url" ]; then
        # Extract components using bash parameter expansion
        _db_userpass=$(echo "$_db_url" | sed -n 's|postgresql://\([^@]*\)@.*|\1|p')
        export DB_USER=$(echo "$_db_userpass" | cut -d':' -f1)
        export DB_PASSWORD=$(echo "$_db_userpass" | cut -d':' -f2)
        export DB_NAME=$(echo "$_db_url" | sed -n 's|.*/\([^?]*\).*|\1|p')
    fi
fi

# Fallback defaults if not loaded from env.local
export DB_NAME="${DB_NAME:-portfolio_ai}"
export DB_USER="${DB_USER:-portfolio_app}"
export DB_PASSWORD="${DB_PASSWORD:-}"

# Exclusions - things that should NEVER be backed up (reproducible/cached/redundant)
BACKUP_EXCLUDES=(
    # Virtual environments (reproducible via pip install)
    "backend/.venv"
    "services/*/.venv"

    # Frontend build artifacts (reproducible via npm install/build)
    "frontend/node_modules"
    "frontend/.next"
    "frontend/playwright-report"
    "frontend/test-results"

    # Git (already version controlled separately)
    ".git"

    # Python caches (regenerated automatically)
    ".mypy_cache"
    "backend/.mypy_cache"
    "__pycache__"
    "*.pyc"
    "*.pyo"
    "backend/.ruff_cache"
    ".ruff_cache"
    "backend/.pytest_cache"
    ".pytest_cache"
    "services/*/.pytest_cache"
    "backend/pytestdebug.log"

    # Redundant database backups (main backup already has database.sql.gz)
    "./backups"
    "./data/backups"
    "backend/data/*.backup*"

    # Claude transient data (memory snapshots not needed)
    ".claude/backups/memory"
    ".claude/plans"

    # Evidence screenshots (6700+ files, 500MB - regenerable via /verify_it)
    "data/artifacts"
)

# Logging functions
log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_success() {
    printf "${GREEN}[%s] ✓ %s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_warn() {
    printf "${YELLOW}[%s] ⚠ %s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_error() {
    printf "${RED}[%s] ✗ %s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

log_info() {
    printf "${BLUE}[%s] ℹ %s${NC}\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

# Check if SMB credentials file exists, create if needed
ensure_smb_credentials() {
    if [ ! -f "$CREDENTIALS_FILE" ]; then
        log_warn "SMB credentials file not found at $CREDENTIALS_FILE"
        log "Creating credentials file..."

        # Prompt for password
        read -s -p "Enter SMB password for $SMB_USER@$SMB_HOST: " smb_password
        echo

        cat > "$CREDENTIALS_FILE" << EOF
username=$SMB_USER
password=$smb_password
domain=WORKGROUP
EOF
        chmod 600 "$CREDENTIALS_FILE"
        log_success "Credentials file created"
    fi
}

# Test SMB connectivity
test_smb_connection() {
    log "Testing SMB connection to //$SMB_HOST/$SMB_SHARE..."

    if smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" -c "ls $SMB_PATH" &>/dev/null; then
        log_success "SMB connection OK"
        return 0
    else
        log_error "SMB connection failed"
        return 1
    fi
}

# Upload file via smbclient
smb_upload() {
    local local_file="$1"
    local remote_dir="$2"
    local remote_name="${3:-$(basename "$local_file")}"

    log "Uploading $(basename "$local_file") to //$SMB_HOST/$SMB_SHARE/$remote_dir..."

    # Create remote directory if needed and upload
    smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" << EOF
mkdir $remote_dir
cd $remote_dir
put $local_file $remote_name
EOF

    if [ $? -eq 0 ]; then
        log_success "Upload complete"
        return 0
    else
        log_error "Upload failed"
        return 1
    fi
}

# List remote backups
smb_list_backups() {
    smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" -c "cd $SMB_PATH; ls portfolio-ai-*.tar.gz" 2>/dev/null | \
        grep "portfolio-ai-" | awk '{print $1}' | sort
}

# Download file via smbclient
smb_download() {
    local remote_file="$1"
    local local_path="$2"

    log "Downloading $remote_file..."

    smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" << EOF
cd $SMB_PATH
get $remote_file $local_path
EOF

    if [ $? -eq 0 ]; then
        log_success "Download complete"
        return 0
    else
        log_error "Download failed"
        return 1
    fi
}

# Delete remote file
smb_delete() {
    local remote_file="$1"

    log "Deleting remote file: $remote_file"

    smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" << EOF
cd $SMB_PATH
rm $remote_file
EOF
}

# Update backup index JSON
update_backup_index() {
    local backup_name="$1"
    local backup_size="$2"
    local db_size="$3"
    local status="${4:-ok}"
    local verification_json="${5:-null}"
    local timestamp=$(date -Iseconds)

    log "Updating backup index..."

    # Create index if it doesn't exist
    if [ ! -f "$BACKUP_INDEX" ]; then
        cat > "$BACKUP_INDEX" << EOF
{
  "version": 2,
  "retention": $MAX_BACKUPS,
  "destination": "//$SMB_HOST/$SMB_SHARE/$SMB_PATH",
  "backups": [],
  "last_updated": "$timestamp"
}
EOF
    fi

    # Add new backup entry using jq (with or without verification)
    local temp_file=$(mktemp)
    if [ "$verification_json" != "null" ] && [ -n "$verification_json" ]; then
        jq --arg name "$backup_name" \
           --arg ts "$timestamp" \
           --argjson size "$backup_size" \
           --argjson dbsize "$db_size" \
           --arg status "$status" \
           --argjson verification "$verification_json" \
           '.version = 2 | .backups = [{"name": $name, "timestamp": $ts, "size_bytes": $size, "db_size_bytes": $dbsize, "status": $status, "verification": $verification}] + .backups | .last_updated = $ts' \
           "$BACKUP_INDEX" > "$temp_file"
    else
        jq --arg name "$backup_name" \
           --arg ts "$timestamp" \
           --argjson size "$backup_size" \
           --argjson dbsize "$db_size" \
           --arg status "$status" \
           '.version = 2 | .backups = [{"name": $name, "timestamp": $ts, "size_bytes": $size, "db_size_bytes": $dbsize, "status": $status}] + .backups | .last_updated = $ts' \
           "$BACKUP_INDEX" > "$temp_file"
    fi

    mv "$temp_file" "$BACKUP_INDEX"
    log_success "Backup index updated"
}

# Get backup count from index
get_backup_count() {
    if [ -f "$BACKUP_INDEX" ]; then
        jq '.backups | length' "$BACKUP_INDEX"
    else
        echo "0"
    fi
}

# Remove oldest backup entry from index
remove_oldest_from_index() {
    local temp_file=$(mktemp)
    jq 'del(.backups[-1])' "$BACKUP_INDEX" > "$temp_file"
    mv "$temp_file" "$BACKUP_INDEX"
}

# Apply retention policy
apply_retention() {
    log "Applying retention policy (keep newest $MAX_BACKUPS)..."

    local backups=($(smb_list_backups))
    local count=${#backups[@]}

    if [ "$count" -le "$MAX_BACKUPS" ]; then
        log_success "Retention OK: $count/$MAX_BACKUPS backups"
        return 0
    fi

    local to_delete=$((count - MAX_BACKUPS))
    log "Deleting $to_delete old backup(s)..."

    # Delete oldest backups (array is sorted, oldest first)
    for ((i=0; i<to_delete; i++)); do
        local old_backup="${backups[$i]}"
        smb_delete "$old_backup"
        remove_oldest_from_index
    done

    log_success "Retention applied: now $MAX_BACKUPS backups"
}

# Build manifest by scanning entire project (dynamic discovery)
build_backup_manifest() {
    local manifest_file="$1"

    cd "$PROJECT_DIR"

    # Build find exclusion args
    local exclude_args=()
    for ex in "${BACKUP_EXCLUDES[@]}"; do
        if [[ "$ex" == *"*"* ]]; then
            # Glob pattern (e.g., *.pyc)
            exclude_args+=(-not -name "$ex")
        else
            # Directory/path pattern
            exclude_args+=(-not -path "./$ex" -not -path "./$ex/*")
        fi
    done

    # Discover all files (excluding above)
    local all_files
    all_files=$(find . -type f "${exclude_args[@]}" 2>/dev/null | sed 's|^\./||' | sort)

    # Build tree: group by top-level directory
    local manifest_json
    manifest_json=$(cat <<EOF
{"generated_at":"$(date -Iseconds)","total_files":0,"total_size":0,"tree":{}}
EOF
)

    # Get unique top-level paths (first component of each path)
    local top_levels
    top_levels=$(echo "$all_files" | cut -d'/' -f1 | sort -u)

    for path in $top_levels; do
        local count size
        if [ -d "$path" ]; then
            count=$(echo "$all_files" | grep -c "^$path/" || echo 0)
            # Calculate size excluding the exclusions
            size=$(find "$path" -type f "${exclude_args[@]}" -exec stat -c%s {} + 2>/dev/null | awk '{s+=$1}END{print s+0}')
        else
            count=1
            size=$(stat -c%s "$path" 2>/dev/null || echo 0)
        fi

        manifest_json=$(echo "$manifest_json" | jq --arg p "$path" \
            --argjson c "$count" --argjson s "${size:-0}" \
            '.tree[$p] = {"file_count": $c, "size_bytes": $s}')
    done

    # Add totals
    local total_count total_size
    total_count=$(echo "$all_files" | wc -l)
    total_size=$(echo "$all_files" | tr '\n' '\0' | xargs -0 stat -c%s 2>/dev/null | awk '{s+=$1}END{print s+0}')

    manifest_json=$(echo "$manifest_json" | jq \
        --argjson tc "$total_count" --argjson ts "${total_size:-0}" \
        '.total_files = $tc | .total_size = $ts')

    echo "$manifest_json" > "$manifest_file"
}

# Verify backup archive - check integrity and build tree from actual contents
verify_backup() {
    local archive_path="$1"

    # Test archive integrity first
    if ! tar -tzf "$archive_path" > /dev/null 2>&1; then
        echo '{"verified":false,"verified_at":"'"$(date -Iseconds)"'","errors":["Archive integrity check failed"],"tree":{}}'
        return 1
    fi

    # Build tree using awk (single pass, fast)
    # Count files per top-level directory
    local tree_json
    tree_json=$(tar -tzf "$archive_path" 2>/dev/null | \
        sed 's|^portfolio-ai/\./||;s|^portfolio-ai/||' | \
        grep -v '/$' | grep -v '^$' | \
        awk -F'/' '
        {
            if (NF == 1) {
                # Root-level file
                files[$1] = 1
            } else {
                # File in directory
                dirs[$1]++
            }
        }
        END {
            printf "{"
            first = 1
            for (d in dirs) {
                if (!first) printf ","
                printf "\"%s\":{\"count\":%d}", d, dirs[d]
                first = 0
            }
            for (f in files) {
                if (!first) printf ","
                printf "\"%s\":{\"count\":1}", f
                first = 0
            }
            printf "}"
        }')

    # Count total files and calculate checksum
    local total_files checksum has_db
    total_files=$(tar -tzf "$archive_path" | grep -v '/$' | wc -l | tr -d ' ')
    checksum=$(sha256sum "$archive_path" | cut -d' ' -f1)
    has_db=$(tar -tzf "$archive_path" | grep -c "database.sql.gz" || echo "0")

    # Build final result
    local verified="true"
    local errors="[]"
    if [ "$has_db" -eq 0 ]; then
        verified="false"
        errors='["Critical: database.sql.gz missing"]'
    fi

    echo "{\"verified\":$verified,\"verified_at\":\"$(date -Iseconds)\",\"errors\":$errors,\"tree\":$tree_json,\"total_files\":$total_files,\"checksum\":\"sha256:$checksum\"}"
}

# Pre-backup checkpoint hook for use by other commands
backup_checkpoint() {
    local description="${1:-pre-operation}"

    log_info "Creating backup checkpoint: $description"

    # Quick backup with existing DB dump
    if bash "$PROJECT_DIR/scripts/backup.sh" --quick 2>&1 | tail -5; then
        log_success "Checkpoint created"
        return 0
    else
        log_warn "Checkpoint failed, continuing anyway"
        return 1
    fi
}

# Sync local index with SMB - self-healing function
# Adds missing backups, removes orphans, preserves existing verification data
sync_index_from_smb() {
    log "Syncing backup index with SMB..."

    # Ensure index exists
    if [ ! -f "$BACKUP_INDEX" ]; then
        cat > "$BACKUP_INDEX" << EOF
{
  "version": 2,
  "retention": $MAX_BACKUPS,
  "destination": "//$SMB_HOST/$SMB_SHARE/$SMB_PATH",
  "backups": [],
  "last_updated": "$(date -Iseconds)"
}
EOF
    fi

    # Get list from SMB
    local smb_backups
    smb_backups=$(smb_list_backups)
    if [ -z "$smb_backups" ]; then
        log_warn "No backups found on SMB or connection failed"
        return 1
    fi

    # Get list from index
    local index_backups
    index_backups=$(jq -r '.backups[].name' "$BACKUP_INDEX" 2>/dev/null)

    local added=0
    local removed=0

    # Add missing backups (on SMB but not in index)
    for backup in $smb_backups; do
        if ! echo "$index_backups" | grep -q "^${backup}$"; then
            log "Adding missing backup: $backup"

            # Extract timestamp from filename (portfolio-ai-YYYYMMDD-HHMMSS.tar.gz)
            local ts_part=$(echo "$backup" | sed -n 's/portfolio-ai-\([0-9]*\)-\([0-9]*\)\.tar\.gz/\1-\2/p')
            local year=${ts_part:0:4}
            local month=${ts_part:4:2}
            local day=${ts_part:6:2}
            local hour=${ts_part:9:2}
            local min=${ts_part:11:2}
            local sec=${ts_part:13:2}
            local timestamp="${year}-${month}-${day}T${hour}:${min}:${sec}-05:00"

            # Get file size from SMB
            local size
            size=$(smbclient "//$SMB_HOST/$SMB_SHARE" -A "$CREDENTIALS_FILE" \
                -c "cd $SMB_PATH; ls $backup" 2>/dev/null | grep "$backup" | awk '{print $3}')
            size=${size:-0}

            # Add to index (will be sorted later)
            local temp_file=$(mktemp)
            jq --arg name "$backup" \
               --arg ts "$timestamp" \
               --argjson size "$size" \
               '.backups += [{"name": $name, "timestamp": $ts, "size_bytes": $size, "db_size_bytes": 0, "status": "ok", "verification": null}]' \
               "$BACKUP_INDEX" > "$temp_file"
            mv "$temp_file" "$BACKUP_INDEX"
            ((added++))
        fi
    done

    # Remove orphaned entries (in index but not on SMB)
    for backup in $index_backups; do
        if ! echo "$smb_backups" | grep -q "^${backup}$"; then
            log "Removing orphaned entry: $backup"
            local temp_file=$(mktemp)
            jq --arg name "$backup" '.backups = [.backups[] | select(.name != $name)]' \
               "$BACKUP_INDEX" > "$temp_file"
            mv "$temp_file" "$BACKUP_INDEX"
            ((removed++))
        fi
    done

    # Sort by timestamp (newest first) and update last_updated
    local temp_file=$(mktemp)
    local now_ts=$(date -Iseconds)
    jq --arg ts "$now_ts" '.backups = (.backups | sort_by(.timestamp) | reverse) | .last_updated = $ts' \
       "$BACKUP_INDEX" > "$temp_file"
    mv "$temp_file" "$BACKUP_INDEX"

    if [ $added -gt 0 ] || [ $removed -gt 0 ]; then
        log_success "Index synced: +$added added, -$removed removed"
    else
        log_success "Index already in sync"
    fi
}

# Export functions for subshells
export -f log log_success log_warn log_error log_info
export -f ensure_smb_credentials test_smb_connection
export -f smb_upload smb_download smb_delete smb_list_backups
export -f update_backup_index get_backup_count remove_oldest_from_index
export -f apply_retention backup_checkpoint
export -f build_backup_manifest verify_backup sync_index_from_smb
