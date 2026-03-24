#!/usr/bin/env bash
# Aggregated pre-flight checks for the News surface QA flow.

set -euo pipefail

BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3000}
WATCHLIST_ACCOUNT=${WATCHLIST_ACCOUNT:-default}

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

warned=0
failed=0

heading() {
  echo -e "\n${BLUE}▶${NC} $1"
}

ok() {
  echo -e "  ${GREEN}✓${NC} $1"
}

warn() {
  echo -e "  ${YELLOW}⚠${NC} $1"
  warned=$((warned + 1))
}

fail() {
  echo -e "  ${RED}✗${NC} $1"
  failed=$((failed + 1))
}

heading "Configuration"
echo "  Backend URL:  $BACKEND_URL"
echo "  Frontend URL: $FRONTEND_URL"
echo "  Watchlist account: $WATCHLIST_ACCOUNT"

heading "Service processes"
if pgrep -f "uvicorn.*main:app" >/dev/null; then
  ok "Backend API (uvicorn) detected"
else
  fail "Backend API process not found"
fi

if systemctl --user is-active portfolio-hatchet-worker.service >/dev/null 2>&1; then
  ok "Hatchet worker (systemd) active"
else
  fail "Hatchet worker not running"
fi

if systemctl --user is-active portfolio-frontend.service >/dev/null 2>&1; then
  ok "Frontend (systemd) active"
else
  fail "Frontend service not running"
fi

heading "Core dependencies"
if command -v pg_isready >/dev/null; then
  if pg_isready >/dev/null 2>&1; then
    ok "PostgreSQL reachable"
  else
    fail "PostgreSQL ping failed"
  fi
else
  warn "pg_isready not installed; skipping Postgres check"
fi

if command -v redis-cli >/dev/null; then
  if redis-cli ping >/dev/null 2>&1; then
    ok "Redis reachable"
  else
    fail "Redis ping failed"
  fi
else
  warn "redis-cli not installed; skipping Redis check"
fi

heading "Frontend environment"
frontend_tmp_env=$(mktemp)
env_status=$(fetch_with_status "$FRONTEND_URL" "$frontend_tmp_env")
rm -f "$frontend_tmp_env"
if [[ "$env_status" == "200" ]]; then
  ok "Frontend reachable at $FRONTEND_URL"
else
  warn "Frontend returned status $env_status"
fi

fetch_with_status() {
  local url=$1
  local outfile=$2
  set +e
  local status
  status=$(curl -sS -o "$outfile" -w "%{http_code}" "$url")
  local exit_code=$?
  set -e
  if [[ $exit_code -ne 0 ]]; then
    echo "000"
  else
    echo "$status"
  fi
}

heading "API smoke checks"
market_json=$(mktemp)
watchlist_json=$(mktemp)
market_status=$(fetch_with_status "$BACKEND_URL/api/news/market" "$market_json")
watchlist_status=$(fetch_with_status "$BACKEND_URL/api/news/watchlist?account_id=$WATCHLIST_ACCOUNT" "$watchlist_json")
market_result=$(python3 - "$market_json" <<'PY'
import json, sys, pathlib
path = pathlib.Path(sys.argv[1])
try:
    data = json.loads(path.read_text())
except json.JSONDecodeError:
    print("decode_error")
    sys.exit(0)
headlines = data.get("articles") or data.get("headlines") or []
model = data.get("summary", {}).get("model_breakdown", {}).get("finbert")
delta = data.get("summary", {}).get("sentiment_delta")
print(f"{len(headlines)}|{model}|{delta}")
PY
)

watchlist_result=$(python3 - "$watchlist_json" <<'PY'
import json, sys, pathlib
path = pathlib.Path(sys.argv[1])
try:
    data = json.loads(path.read_text())
except json.JSONDecodeError:
    print("decode_error")
    sys.exit(0)
headlines = 0
if isinstance(data, dict):
    for entry in data.get("items") or []:
        headlines += len(entry.get("articles") or entry.get("headlines") or [])
print(headlines)
PY
)

rm -f "$market_json" "$watchlist_json"

if [[ "$market_status" == "200" && "$market_result" != "decode_error" ]]; then
  IFS='|' read -r market_headline_count market_finbert market_delta <<<"$market_result"
  if [[ "$market_headline_count" -gt 0 ]]; then
    ok "Market news returned $market_headline_count headlines (FinBERT=${market_finbert:-n/a}, Δ=${market_delta:-n/a})"
  else
    warn "Market news returned no headlines"
  fi
else
  fail "Market news endpoint returned status $market_status"
fi

if [[ "$watchlist_status" == "200" && "$watchlist_result" != "decode_error" ]]; then
  if [[ "$watchlist_result" -gt 0 ]]; then
    ok "Watchlist news returned $watchlist_result headlines (account=$WATCHLIST_ACCOUNT)"
  else
    warn "Watchlist news returned empty headline sets"
  fi
elif [[ "$watchlist_status" == "204" ]]; then
  warn "Watchlist news returned 204 (likely preferences disabled)"
else
  fail "Watchlist news endpoint returned status $watchlist_status"
fi

heading "Frontend route check"
frontend_tmp=$(mktemp)
home_status=$(fetch_with_status "$FRONTEND_URL/" "$frontend_tmp")
rm -f "$frontend_tmp"
if [[ "$home_status" == "200" ]]; then
  ok "Frontend home page reachable (HTTP 200)"
else
  warn "Frontend home page returned status $home_status"
fi

echo -e "\n${BLUE}Summary${NC}"
echo "  Warnings: $warned"
echo "  Failures: $failed"

if [[ $failed -ne 0 ]]; then
  exit 1
fi

exit 0
