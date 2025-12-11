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

# Database config
export DB_NAME="${DB_NAME:-portfolio_ai}"
export DB_USER="${DB_USER:-portfolio_ai_user}"

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
    local timestamp=$(date -Iseconds)

    log "Updating backup index..."

    # Create index if it doesn't exist
    if [ ! -f "$BACKUP_INDEX" ]; then
        cat > "$BACKUP_INDEX" << EOF
{
  "version": 1,
  "retention": $MAX_BACKUPS,
  "destination": "//$SMB_HOST/$SMB_SHARE/$SMB_PATH",
  "backups": [],
  "last_updated": "$timestamp"
}
EOF
    fi

    # Add new backup entry using jq
    local temp_file=$(mktemp)
    jq --arg name "$backup_name" \
       --arg ts "$timestamp" \
       --argjson size "$backup_size" \
       --argjson dbsize "$db_size" \
       --arg status "$status" \
       '.backups = [{"name": $name, "timestamp": $ts, "size_bytes": $size, "db_size_bytes": $dbsize, "status": $status}] + .backups | .last_updated = $ts' \
       "$BACKUP_INDEX" > "$temp_file"

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

# Export functions for subshells
export -f log log_success log_warn log_error log_info
export -f ensure_smb_credentials test_smb_connection
export -f smb_upload smb_download smb_delete smb_list_backups
export -f update_backup_index get_backup_count remove_oldest_from_index
export -f apply_retention backup_checkpoint
