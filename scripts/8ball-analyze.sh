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

# 1. Action queue posture
action_queue=$(curl -s "$BACKEND_URL/api/home/action-queue" 2>/dev/null || echo '{}')
prioritized_actions=$(echo "$action_queue" | jq '.actions | length // 0' 2>/dev/null || echo "0")
urgent_actions=$(echo "$action_queue" | jq '[.actions[]? | select(.priority == "critical" or .priority == "high")] | length' 2>/dev/null || echo "0")
quick_actions=$(echo "$action_queue" | jq '[.actions[]? | select(.execution != null)] | length' 2>/dev/null || echo "0")
add_result "prioritized_actions" "$prioritized_actions"
add_result "urgent_actions" "$urgent_actions"
add_result "quick_actions" "$quick_actions"

# 2. Check task files in tasks/ folder
task_files=$(find "$PROJECT_DIR/tasks" -name "*.md" -type f 2>/dev/null | grep -v archive | wc -l | tr -d ' ')
add_result "pending_task_files" "${task_files:-0}"

# 3. Automation posture
automation=$(curl -s "$BACKEND_URL/api/home/automation-center" 2>/dev/null || echo '{}')
guardrails=$(echo "$automation" | jq '.guardrails | length // 0' 2>/dev/null || echo "0")
automation_warnings=$(echo "$automation" | jq '.warnings | length // 0' 2>/dev/null || echo "0")
recent_runs=$(echo "$automation" | jq '.recent_runs | length // 0' 2>/dev/null || echo "0")
add_result "automation_guardrails" "$guardrails"
add_result "automation_warnings" "$automation_warnings"
add_result "recent_runs" "$recent_runs"

# 4. Detailed health snapshot
detailed_health=$(curl -s "$BACKEND_URL/health/detailed" 2>/dev/null || echo '{}')
stale_runs=$(echo "$detailed_health" | jq '.stale_maintenance_runs | length // 0' 2>/dev/null || echo "0")
watchlist_total=$(echo "$detailed_health" | jq '.watchlist_stats.total_items // 0' 2>/dev/null || echo "0")
watchlist_scored=$(echo "$detailed_health" | jq '.watchlist_stats.items_with_scores // 0' 2>/dev/null || echo "0")
data_freshness_status=$(echo "$detailed_health" | jq -r '.data_freshness_status.status // "unknown"' 2>/dev/null || echo "unknown")
add_result "stale_maintenance_runs" "$stale_runs"
add_result "watchlist_total_items" "$watchlist_total"
add_result "watchlist_scored_items" "$watchlist_scored"
result=$(echo "$result" | jq --arg v "$data_freshness_status" '. + {data_freshness_status: $v}')

# 5. News pipeline
news_health=$(curl -s "$BACKEND_URL/api/news/health" 2>/dev/null || echo '{}')
headlines_24h=$(echo "$news_health" | jq '.headlines_24h // 0' 2>/dev/null || echo "0")
fallback_headlines_24h=$(echo "$news_health" | jq '.fallback_headlines_24h // 0' 2>/dev/null || echo "0")
fallback_rate_24h=$(echo "$news_health" | jq '.fallback_rate_24h // 0' 2>/dev/null || echo "0")
add_result "headlines_24h" "$headlines_24h"
add_result "fallback_headlines_24h" "$fallback_headlines_24h"
add_result "fallback_rate_24h" "$fallback_rate_24h"

# 6. Recent local commits
recent_local_commits=$(cd "$PROJECT_DIR" && git log --since="7 days ago" --oneline 2>/dev/null | wc -l | tr -d ' ')
add_result "recent_local_commits" "${recent_local_commits:-0}"

# 7. Git status (uncommitted changes)
uncommitted=$(cd "$PROJECT_DIR" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
add_result "uncommitted_files" "${uncommitted:-0}"

# 8. Task inventory on disk
open_task_files=$(find "$PROJECT_DIR/tasks" -name "*.md" -type f 2>/dev/null | grep -v archive | wc -l | tr -d ' ')
add_result "open_task_files" "${open_task_files:-0}"

# Output final JSON
echo "$result" | jq .
