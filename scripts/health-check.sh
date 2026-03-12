#!/usr/bin/env bash
# Comprehensive health check - collects all metrics

set -euo pipefail

REPORT_FILE="${1:-/tmp/health-report.json}"

echo "Collecting health metrics..." >&2

service_status() {
  local unit="$1"
  local status

  status=$(systemctl --user is-active "$unit" 2>/dev/null || true)
  if [ -z "$status" ]; then
    echo "inactive"
    return
  fi

  echo "$status"
}

# Collect all health data
{
  echo '{'

  # Main health
  echo '"main_health":'
  curl -sf http://localhost:8000/health || echo '{"error": "unreachable"}'
  echo ','

  # Detailed health
  echo '"detailed_health":'
  curl -sf http://localhost:8000/health/detailed || echo '{"error": "unreachable"}'
  echo ','

  # News health
  echo '"news_health":'
  curl -sf http://localhost:8000/api/news/health || echo '{"error": "unreachable"}'
  echo ','

  # Home automation snapshot
  echo '"automation_center":'
  curl -sf http://localhost:8000/api/home/automation-center || echo '{"error": "unreachable"}'
  echo ','

  # Home action queue
  echo '"action_queue":'
  curl -sf http://localhost:8000/api/home/action-queue || echo '{"error": "unreachable"}'
  echo ','

  # Service status for portfolio user units
  echo '"service_status": {'
  echo '"backend": "'$(service_status portfolio-backend)'",'
  echo '"hatchet_worker": "'$(service_status portfolio-hatchet-worker)'",'
  echo '"frontend": "'$(service_status portfolio-frontend)'",'
  echo '"redis": "'$(service_status portfolio-redis)'"'
  echo '}'

  echo '}'
} > "$REPORT_FILE"

echo "Health report saved to: $REPORT_FILE" >&2
python3 -m json.tool "$REPORT_FILE"
