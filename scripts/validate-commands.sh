#!/usr/bin/env bash
#
# Command Validation Script
#
# Purpose: Discover and validate commands documented in *.md files
#
# Usage:
#   ./scripts/validate-commands.sh              # Run validation
#   ./scripts/validate-commands.sh --help       # Show help
#
# Dependencies:
#   - jq (for JSON parsing)
#   - docker (for validating docker commands)
#   - git (for validating git commands)
#
# Output:
#   - Validation report to stdout
#   - Validation state saved to .validation-state.json
#
# Exit Codes:
#   0 - All commands validated successfully
#   1 - One or more commands failed validation
#   2 - Missing dependencies or usage error

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# State file
STATE_FILE=".validation-state.json"

# Usage help
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Discover and validate commands documented in Markdown files.

OPTIONS:
    --help          Show this help message
    -v, --verbose   Verbose output (show all validation details)

EXAMPLES:
    # Run validation
    ./scripts/validate-commands.sh

    # Run with verbose output
    ./scripts/validate-commands.sh --verbose

VALIDATION:
    Scans all *.md files for code blocks containing commands:
    - docker compose run/exec
    - git commands
    - scripts/*.sh references
    - curl commands

    Validates each command:
    - Docker: Check service exists, basic syntax
    - Git: Check command is valid git subcommand
    - Shell scripts: Check file exists and is executable

    Skips destructive commands (push --force, rm -rf, etc.)

OUTPUT:
    - Validation report to stdout
    - State saved to .validation-state.json

EXIT CODES:
    0 - All commands valid
    1 - One or more commands failed
    2 - Missing dependencies or error

EOF
}

# Check dependencies
check_dependencies() {
    local missing=()

    if ! command -v jq &> /dev/null; then
        missing+=("jq")
    fi

    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi

    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}Error: Missing required dependencies:${NC}"
        printf '  - %s\n' "${missing[@]}"
        echo ""
        echo "Install missing dependencies and try again."
        exit 2
    fi
}

# Parse command line arguments
VERBOSE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            usage
            exit 0
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            usage
            exit 2
            ;;
    esac
done

# Check dependencies
check_dependencies

# Initialize counters
TOTAL_COMMANDS=0
PASSED_COMMANDS=0
FAILED_COMMANDS=0
NEW_COMMANDS=0
REMOVED_COMMANDS=0

# Arrays to store results
declare -a FAILED_COMMAND_DETAILS
declare -a NEW_COMMAND_DETAILS
declare -a REMOVED_COMMAND_DETAILS

# Load previous validation state
load_previous_state() {
    if [ -f "$STATE_FILE" ]; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}Loading previous validation state from $STATE_FILE${NC}"
        fi
        # Previous state will be used for diffing
        return 0
    else
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}No previous validation state found (first run)${NC}"
        fi
        echo '{}' > "$STATE_FILE"
        return 0
    fi
}

# Discover commands in markdown files
discover_commands() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Discovering commands in *.md files...${NC}"
    fi

    # Find all .md files
    local md_files
    mapfile -t md_files < <(find . -name "*.md" -type f | grep -v node_modules | grep -v ".venv")

    # Temporary file for discovered commands
    local temp_commands=$(mktemp)

    # Extract commands from code blocks
    for file in "${md_files[@]}"; do
        # Extract code blocks and look for commands
        # Pattern: docker compose, git, scripts/*.sh, curl
        # Note: Using POSIX-compliant regex for mawk compatibility
        awk '
            BEGIN { in_block = 0 }
            /^```bash/ { in_block = 1; next }
            /^```$/ { in_block = 0; next }
            in_block == 1 {
                # Remove leading/trailing whitespace
                gsub(/^[ 	]+/, "");
                gsub(/[ 	]+$/, "");
                # Skip empty lines and comments
                if ($0 ~ /^#/ || length($0) == 0) next;
                # Check if it matches our patterns
                if ($0 ~ /^docker compose (run|exec)/ ||
                    $0 ~ /^git / ||
                    $0 ~ /scripts\/.*\.sh/ ||
                    $0 ~ /^curl /) {
                    # Print command with file location
                    print FILENAME "||" NR "||" $0
                }
            }
        ' FILENAME="$file" "$file" >> "$temp_commands"
    done

    # Count discovered commands
    if [ -s "$temp_commands" ]; then
        TOTAL_COMMANDS=$(wc -l < "$temp_commands")
        if [ "$VERBOSE" = true ]; then
            echo -e "${GREEN}Discovered $TOTAL_COMMANDS commands${NC}"
        fi
    else
        echo -e "${YELLOW}No commands found in documentation${NC}"
        rm "$temp_commands"
        return 1
    fi

    echo "$temp_commands"
}

# Check if command is destructive (should skip validation)
is_destructive() {
    local cmd="$1"

    # Patterns for destructive commands
    if [[ "$cmd" =~ "git push --force" ]] || \
       [[ "$cmd" =~ "git push -f" ]] || \
       [[ "$cmd" =~ "git reset --hard" ]] || \
       [[ "$cmd" =~ "rm -rf" ]] || \
       [[ "$cmd" =~ "docker compose down -v" ]] || \
       [[ "$cmd" =~ "DROP " ]] || \
       [[ "$cmd" =~ "TRUNCATE " ]] || \
       [[ "$cmd" =~ "DELETE FROM" ]]; then
        return 0  # Is destructive
    fi

    return 1  # Not destructive
}

# Validate a docker command
validate_docker_command() {
    local cmd="$1"

    # Extract service name from "docker compose run/exec <flags> <service>"
    local service
    # Use POSIX-compliant regex (no [:space:], use literal space/tab)
    if [[ "$cmd" =~ docker\ compose\ (run|exec)\ (--rm\ )?([a-z]+) ]]; then
        service="${BASH_REMATCH[3]}"
    else
        echo "Could not parse service name"
        return 1
    fi

    # Check if service exists in docker-compose.yml
    if ! docker compose config --services 2>/dev/null | grep -q "^${service}$"; then
        echo "Service '$service' not found in docker-compose.yml"
        return 1
    fi

    # Basic syntax check passed
    return 0
}

# Validate a git command
validate_git_command() {
    local cmd="$1"

    # Extract git subcommand
    local subcommand
    # Use POSIX-compliant regex
    if [[ "$cmd" =~ ^git\ ([a-z-]+) ]]; then
        subcommand="${BASH_REMATCH[1]}"
    else
        echo "Could not parse git subcommand"
        return 1
    fi

    # Check if it's a valid git command
    if ! git help -a 2>/dev/null | grep -q " $subcommand"; then
        echo "Invalid git subcommand: $subcommand"
        return 1
    fi

    return 0
}

# Validate a shell script reference
validate_shell_script() {
    local cmd="$1"

    # Extract script path
    local script_path
    if [[ "$cmd" =~ (scripts/[^[:space:]]+\.sh) ]]; then
        script_path="${BASH_REMATCH[1]}"
    else
        echo "Could not parse script path"
        return 1
    fi

    # Check if file exists
    if [ ! -f "$script_path" ]; then
        echo "Script not found: $script_path"
        return 1
    fi

    # Check if executable
    if [ ! -x "$script_path" ]; then
        echo "Script not executable: $script_path"
        return 1
    fi

    return 0
}

# Validate a single command
validate_command() {
    local file="$1"
    local line="$2"
    local cmd="$3"

    # Check if destructive
    if is_destructive "$cmd"; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${YELLOW}Skipping destructive command: $cmd${NC}"
        fi
        return 0  # Skip destructive commands
    fi

    # Validate based on command type
    local error_msg=""
    # Use POSIX-compliant regex (literal space instead of [:space:])
    if [[ "$cmd" =~ ^docker\ compose ]]; then
        error_msg=$(validate_docker_command "$cmd" 2>&1)
        result=$?
    elif [[ "$cmd" =~ ^git\  ]]; then
        error_msg=$(validate_git_command "$cmd" 2>&1)
        result=$?
    elif [[ "$cmd" =~ scripts/.*\.sh ]]; then
        error_msg=$(validate_shell_script "$cmd" 2>&1)
        result=$?
    elif [[ "$cmd" =~ ^curl\  ]]; then
        # Curl commands are OK (we don't actually execute them)
        result=0
    else
        # Unknown command type - skip
        result=0
    fi

    if [ $result -eq 0 ]; then
        ((PASSED_COMMANDS++)) || true
        if [ "$VERBOSE" = true ]; then
            echo -e "${GREEN}✓${NC} $file:$line: $cmd"
        fi
    else
        ((FAILED_COMMANDS++)) || true
        FAILED_COMMAND_DETAILS+=("$file:$line: $cmd|$error_msg")
        if [ "$VERBOSE" = true ]; then
            echo -e "${RED}✗${NC} $file:$line: $cmd"
            echo -e "  ${RED}Error: $error_msg${NC}"
        fi
    fi

    return $result
}

# Detect new/removed commands (compare to previous state)
detect_changes() {
    local commands_file="$1"

    if [ ! -f "$STATE_FILE" ] || [ ! -s "$STATE_FILE" ] || [ "$(cat "$STATE_FILE")" = "{}" ]; then
        # First run - all commands are "new"
        NEW_COMMANDS=$TOTAL_COMMANDS
        return 0
    fi

    # Extract previous commands
    local prev_commands=$(mktemp)
    jq -r 'keys[]' "$STATE_FILE" 2>/dev/null > "$prev_commands" || true

    # Extract current commands
    local curr_commands=$(mktemp)
    awk -F'||' '{print $3}' "$commands_file" | sort -u > "$curr_commands"

    # Find new commands (in current but not in previous)
    local new_cmds=$(mktemp)
    comm -13 "$prev_commands" "$curr_commands" > "$new_cmds"
    NEW_COMMANDS=$(wc -l < "$new_cmds")

    if [ "$NEW_COMMANDS" -gt 0 ]; then
        while IFS= read -r cmd; do
            NEW_COMMAND_DETAILS+=("$cmd")
        done < "$new_cmds"
    fi

    # Find removed commands (in previous but not in current)
    local removed_cmds=$(mktemp)
    comm -23 "$prev_commands" "$curr_commands" > "$removed_cmds"
    REMOVED_COMMANDS=$(wc -l < "$removed_cmds")

    if [ "$REMOVED_COMMANDS" -gt 0 ]; then
        while IFS= read -r cmd; do
            REMOVED_COMMAND_DETAILS+=("$cmd")
        done < "$removed_cmds"
    fi

    # Cleanup
    rm -f "$prev_commands" "$curr_commands" "$new_cmds" "$removed_cmds"
}

# Save validation state
save_state() {
    local commands_file="$1"

    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Saving validation state to $STATE_FILE${NC}"
    fi

    # Create JSON state
    local state_json=$(mktemp)
    echo "{" > "$state_json"

    local first=true
    while IFS='||' read -r file line cmd; do
        if [ "$first" = true ]; then
            first=false
        else
            echo "," >> "$state_json"
        fi

        # Escape quotes in command
        local escaped_cmd=$(echo "$cmd" | sed 's/"/\\"/g')

        # Add entry
        cat >> "$state_json" <<EOF
  "$escaped_cmd": {
    "file": "$file",
    "line": $line,
    "last_validated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "passed"
  }
EOF
    done < "$commands_file"

    echo "" >> "$state_json"
    echo "}" >> "$state_json"

    # Save state
    jq '.' "$state_json" > "$STATE_FILE" 2>/dev/null || cp "$state_json" "$STATE_FILE"
    rm -f "$state_json"
}

# Generate validation report
generate_report() {
    echo ""
    echo "Command Validation Report"
    echo "========================="
    echo "Last Validated: $(date -u +%Y-%m-%d\ %H:%M:%S)"
    echo ""

    # Summary
    echo -e "${GREEN}✓${NC} Passed: $PASSED_COMMANDS commands"
    if [ "$FAILED_COMMANDS" -gt 0 ]; then
        echo -e "${RED}✗${NC} Failed: $FAILED_COMMANDS commands"
    fi
    if [ "$NEW_COMMANDS" -gt 0 ]; then
        echo -e "${BLUE}⊕${NC} New: $NEW_COMMANDS commands (need verification)"
    fi
    if [ "$REMOVED_COMMANDS" -gt 0 ]; then
        echo -e "${YELLOW}⊗${NC} Removed: $REMOVED_COMMANDS commands (from docs)"
    fi
    echo ""

    # Failed commands
    if [ "$FAILED_COMMANDS" -gt 0 ]; then
        echo "Failed Commands:"
        for detail in "${FAILED_COMMAND_DETAILS[@]}"; do
            IFS='|' read -r location error <<< "$detail"
            echo -e "${RED}- $location${NC}"
            echo -e "  Error: $error"
        done
        echo ""
    fi

    # New commands
    if [ "$NEW_COMMANDS" -gt 0 ]; then
        echo "New Commands (verify these):"
        for cmd in "${NEW_COMMAND_DETAILS[@]}"; do
            echo -e "${BLUE}- $cmd${NC}"
        done
        echo ""
    fi

    # Removed commands
    if [ "$REMOVED_COMMANDS" -gt 0 ]; then
        echo "Removed Commands:"
        for cmd in "${REMOVED_COMMAND_DETAILS[@]}"; do
            echo -e "${YELLOW}- $cmd${NC}"
        done
        echo ""
    fi

    # Overall status
    if [ "$FAILED_COMMANDS" -eq 0 ]; then
        echo -e "${GREEN}✓ All commands validated successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ Validation failed - fix commands in documentation${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo "Command Validation Script"
    echo "========================="
    echo ""

    # Load previous state
    load_previous_state

    # Discover commands
    commands_file=$(discover_commands)
    if [ $? -ne 0 ]; then
        exit 0  # No commands found, exit cleanly
    fi

    # Detect changes
    detect_changes "$commands_file"

    # Validate each command
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}Validating $TOTAL_COMMANDS commands...${NC}"
        echo ""
    fi

    while IFS='||' read -r file line cmd; do
        validate_command "$file" "$line" "$cmd"
    done < "$commands_file"

    # Save state
    save_state "$commands_file"

    # Cleanup temp file
    rm -f "$commands_file"

    # Generate report
    generate_report
    result=$?

    exit $result
}

# Run main
main "$@"
