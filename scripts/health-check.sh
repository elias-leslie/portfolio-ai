#!/usr/bin/env bash
# Comprehensive health check - collects all metrics

set -euo pipefail

REPORT_FILE="${1:-/tmp/health-report.json}"

echo "Collecting health metrics..." >&2

service_status() {
  local unit="$1"
  systemctl --user is-active "$unit" 2>/dev/null || echo "inactive"
}

safe_curl() {
  curl -sf "$1" 2>/dev/null || echo '{"error": "unreachable"}'
}

# Collect all health data using jq for safe JSON composition
jq -n \
  --argjson main_health "$(safe_curl http://localhost:8000/health)" \
  --argjson detailed_health "$(safe_curl http://localhost:8000/health/detailed)" \
  --argjson news_health "$(safe_curl http://localhost:8000/api/news/health)" \
  --argjson automation_center "$(safe_curl http://localhost:8000/api/home/automation-center)" \
  --argjson action_queue "$(safe_curl http://localhost:8000/api/home/action-queue)" \
  --arg backend "$(service_status portfolio-backend)" \
  --arg hatchet_worker "$(service_status portfolio-hatchet-worker)" \
  --arg frontend "$(service_status portfolio-frontend)" \
  --arg redis "$(service_status portfolio-redis)" \
  '{
    main_health: $main_health,
    detailed_health: $detailed_health,
    news_health: $news_health,
    automation_center: $automation_center,
    action_queue: $action_queue,
    service_status: {
      backend: $backend,
      hatchet_worker: $hatchet_worker,
      frontend: $frontend,
      redis: $redis
    }
  }' > "$REPORT_FILE"

echo "Health report saved to: $REPORT_FILE" >&2
python3 -m json.tool "$REPORT_FILE"
