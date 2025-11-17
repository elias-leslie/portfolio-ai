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

  # Capabilities
  echo '"capabilities_health":'
  curl -sf http://localhost:8000/api/capabilities/health/summary || echo '{"error": "unreachable"}'
  echo ','

  # Service status
  echo '"service_status": {'
  echo '"backend": "'$(systemctl is-active portfolio-backend 2>/dev/null || echo "inactive")'",'
  echo '"celery_worker": "'$(systemctl is-active portfolio-celery 2>/dev/null || echo "inactive")'",'
  echo '"celery_beat": "'$(systemctl is-active portfolio-beat 2>/dev/null || echo "inactive")'",'
  echo '"frontend": "'$(systemctl is-active portfolio-frontend 2>/dev/null || echo "inactive")'",'
  echo '"redis": "'$(systemctl is-active redis 2>/dev/null || echo "inactive")'"'
  echo '}'

  echo '}'
} > "$REPORT_FILE"

echo "Health report saved to: $REPORT_FILE" >&2
python3 -m json.tool "$REPORT_FILE"
