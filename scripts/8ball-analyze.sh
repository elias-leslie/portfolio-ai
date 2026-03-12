#!/bin/bash
# 8ball-analyze.sh - Gather system state for intelligent command selection
# Outputs JSON summary for /8ball command decision making

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
PROJECT_DIR="${PROJECT_DIR:-/home/kasadis/portfolio-ai}"

# Initialize result object
result="{}"

# Helper to add to result
add_result() {
    local key="$1"
    local value="$2"
    result=$(echo "$result" | jq --arg k "$key" --argjson v "$value" '. + {($k): $v}')
}

# 1. Check fix-* tasks (PRIORITY)
fix_tasks=$(curl -s "$BACKEND_URL/api/capabilities/features/?limit=500" 2>/dev/null | \
    jq '[.features[] | .tasks[]? | select(.task_id | startswith("fix-")) | select(.completed == false)] | length' 2>/dev/null || echo "0")
add_result "incomplete_fix_tasks" "$fix_tasks"

# 2. Check task files in tasks/ folder
task_files=$(find "$PROJECT_DIR/tasks" -name "*.md" -type f 2>/dev/null | grep -v archive | wc -l | tr -d ' ')
add_result "pending_task_files" "${task_files:-0}"

# 3. Get feature summary
feature_summary=$(curl -s "$BACKEND_URL/api/capabilities/features/summary" 2>/dev/null || echo '{}')
total_features=$(echo "$feature_summary" | jq '.total // 0')
unreviewed=$(echo "$feature_summary" | jq '.passes_breakdown.unreviewed // 0')
passing=$(echo "$feature_summary" | jq '.passes_breakdown.passing // 0')
failing=$(echo "$feature_summary" | jq '.passes_breakdown.failing // 0')
add_result "total_features" "$total_features"
add_result "unreviewed_features" "$unreviewed"
add_result "passing_features" "$passing"
add_result "failing_features" "$failing"

# 4. Features lacking acceptance criteria
no_criteria=$(curl -s "$BACKEND_URL/api/capabilities/features/?limit=500" 2>/dev/null | \
    jq '[.features[] | select(.acceptance_criteria == null or (.acceptance_criteria | length) == 0)] | length' 2>/dev/null || echo "0")
add_result "features_no_criteria" "$no_criteria"

# 5. Cleanup candidates
cleanup=$(curl -s "$BACKEND_URL/api/capabilities/cleanup-candidates" 2>/dev/null || echo '{}')
cleanup_db=$(echo "$cleanup" | jq '.database | length // 0')
cleanup_celery=$(echo "$cleanup" | jq '.celery | length // 0')
cleanup_total=$((cleanup_db + cleanup_celery))
add_result "cleanup_candidates" "$cleanup_total"

# 6. Completed fix tasks (can be cleaned)
completed_fix=$(curl -s "$BACKEND_URL/api/capabilities/features/?limit=500" 2>/dev/null | \
    jq '[.features[] | .tasks[]? | select(.task_id | startswith("fix-")) | select(.completed == true)] | length' 2>/dev/null || echo "0")
add_result "completed_fix_tasks" "$completed_fix"

# 7. Data freshness (check for stale tables)
stale_tables=$(curl -s "$BACKEND_URL/api/capabilities/db-capabilities" 2>/dev/null | \
    jq '[.tables[] | select(.freshness_status == "critical" or .freshness_status == "stale")] | length' 2>/dev/null || echo "0")
add_result "stale_data_tables" "${stale_tables:-0}"

# 9. Recent progress log entries (session context)
recent_commits=$(curl -s "$BACKEND_URL/api/claude/progress?limit=5" 2>/dev/null | \
    jq '[.entries[] | select(.action_type == "commit")] | length' 2>/dev/null || echo "0")
add_result "recent_commits" "${recent_commits:-0}"

# 10. Git status (uncommitted changes)
uncommitted=$(cd "$PROJECT_DIR" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
add_result "uncommitted_files" "${uncommitted:-0}"

# 11. Check for FEAT-DEBT entries
feat_debt=$(curl -s "$BACKEND_URL/api/capabilities/features/?limit=500" 2>/dev/null | \
    jq '[.features[] | select(.feature_id | startswith("FEAT-DEBT"))] | length' 2>/dev/null || echo "0")
add_result "feat_debt_entries" "$feat_debt"

# 12. Dead imports (quick ruff check)
dead_imports=$(cd "$PROJECT_DIR/backend" && ruff check app/ --select F401 --output-format json 2>/dev/null | jq 'length' || echo "0")
add_result "dead_imports" "${dead_imports:-0}"

# Output final JSON
echo "$result" | jq .
