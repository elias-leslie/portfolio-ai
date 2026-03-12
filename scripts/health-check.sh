#!/usr/bin/env bash
# Comprehensive health check - collects all metrics

set -euo pipefail

REPORT_FILE="${1:-/tmp/health-report.json}"

echo "Collecting health metrics..." >&2

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

  # Service status (user services for portfolio, system service for redis)
  echo '"service_status": {'
  echo '"backend": "'$(systemctl --user is-active portfolio-backend 2>/dev/null || echo "inactive")'",'
  echo '"hatchet_worker": "'$(systemctl --user is-active portfolio-hatchet-worker 2>/dev/null || echo "inactive")'",'
  echo '"frontend": "'$(systemctl --user is-active portfolio-frontend 2>/dev/null || echo "inactive")'",'
  echo '"redis": "'$(systemctl --user is-active redis 2>/dev/null || echo "inactive")'"'
  echo '}'

  echo '}'
} > "$REPORT_FILE"

echo "Health report saved to: $REPORT_FILE" >&2
python3 -m json.tool "$REPORT_FILE"
