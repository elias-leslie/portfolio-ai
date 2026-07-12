#!/usr/bin/env bash
set -euo pipefail

api_image="${1:?Usage: docker-image-smoke.sh API_IMAGE WEB_IMAGE}"
web_image="${2:?Usage: docker-image-smoke.sh API_IMAGE WEB_IMAGE}"
run_id="${GITHUB_RUN_ID:-local}-$$"
network="portfolio-image-smoke-${run_id}"
db="portfolio-smoke-db-${run_id}"
redis="portfolio-smoke-redis-${run_id}"
api="portfolio-smoke-api-${run_id}"
worker="portfolio-smoke-worker-${run_id}"
web="portfolio-smoke-web-${run_id}"

cleanup() {
  status=$?
  if (( status != 0 )); then
    docker logs "$api" 2>/dev/null || true
    docker logs "$worker" 2>/dev/null || true
    docker logs "$web" 2>/dev/null || true
    docker logs "$db" 2>/dev/null || true
  fi
  docker rm -f "$web" "$worker" "$api" "$redis" "$db" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  trap - EXIT
  exit "$status"
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker run --detach --name "$db" --network "$network" \
  --env POSTGRES_DB=portfolio_ai \
  --env POSTGRES_USER=portfolio \
  --env POSTGRES_PASSWORD=portfolio \
  pgvector/pgvector:pg16@sha256:1d533553fefe4f12e5d80c7b80622ba0c382abb5758856f52983d8789179f0fb \
  >/dev/null
docker run --detach --name "$redis" --network "$network" \
  redis:7-alpine@sha256:7aec734b2bb298a1d769fd8729f13b8514a41bf90fcdd1f38ec52267fbaa8ee6 \
  redis-server --save '' --appendonly no >/dev/null

for _ in {1..30}; do
  if docker exec "$db" pg_isready -U portfolio -d portfolio_ai >/dev/null 2>&1 \
    && docker exec "$redis" redis-cli ping | grep -q PONG; then
    break
  fi
  sleep 1
done
docker exec "$db" pg_isready -U portfolio -d portfolio_ai >/dev/null
docker exec "$redis" redis-cli ping | grep -q PONG

hatchet_token='eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ0ZXN0LXRlbmFudCIsInNlcnZlcl91cmwiOiJodHRwOi8vbG9jYWxob3N0OjgwODAiLCJncnBjX2Jyb2FkY2FzdF9hZGRyZXNzIjoiMTI3LjAuMC4xOjcwNzAifQ.test'
docker run --detach --name "$api" --network "$network" --network-alias portfolio-api \
  --env PORTFOLIO_DB_URL="postgresql://portfolio:portfolio@${db}:5432/portfolio_ai" \
  --env REDIS_URL="redis://${redis}:6379/0" \
  --env HATCHET_CLIENT_TOKEN="$hatchet_token" \
  --env HATCHET_CLIENT_TLS_STRATEGY=none \
  --env LOG_DIR=/tmp/portfolio-ai-logs \
  --env SEC_USER_AGENT='Portfolio AI image smoke ci@example.invalid' \
  "$api_image" >/dev/null

for _ in {1..60}; do
  if docker exec "$api" curl --fail --silent http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec "$api" curl --fail --silent http://127.0.0.1:8000/health >/dev/null
test "$(docker exec "$api" id -u)" -ne 0
docker exec "$db" psql -U portfolio -d portfolio_ai -Atc \
  "SELECT count(*) FROM alembic_version" | grep -qx 1

# Load the production worker module and exercise its real heartbeat mapping
# from the same non-root image. This isolated image smoke has no Hatchet server;
# the managed-stack check separately proves a healthy SDK connection.
docker run --name "$worker" --network "$network" \
  --env PORTFOLIO_DB_URL="postgresql://portfolio:portfolio@${db}:5432/portfolio_ai" \
  --env REDIS_URL="redis://${redis}:6379/0" \
  --env HATCHET_CLIENT_TOKEN="$hatchet_token" \
  --env HATCHET_CLIENT_TLS_STRATEGY=none \
  --env LOG_DIR=/tmp/portfolio-ai-logs \
  --env SEC_USER_AGENT='Portfolio AI image smoke ci@example.invalid' \
  "$api_image" python -c '
import os
from types import SimpleNamespace

from app.services.worker_heartbeat import WorkerHeartbeatPublisher
from app.storage import get_storage
from app.worker import _worker_reported_status

assert os.geteuid() != 0
smoke_worker = SimpleNamespace(status=SimpleNamespace(name="STARTING"))
publisher = WorkerHeartbeatPublisher(
    get_storage(),
    status_provider=lambda: _worker_reported_status(smoke_worker),
)
publisher.publish()
' >/dev/null

docker exec "$db" psql -U portfolio -d portfolio_ai -Atc \
  "SELECT count(*) FROM service_heartbeats WHERE service_name = 'portfolio-hatchet-worker' AND reported_status = 'starting'" \
  | grep -qx 1

docker run --detach --name "$web" --network "$network" \
  --env API_URL=http://portfolio-api:8000 \
  "$web_image" >/dev/null
for _ in {1..60}; do
  if docker exec "$web" node -e \
    "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"; then
    break
  fi
  sleep 2
done
docker exec "$web" node -e \
  "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
test "$(docker exec "$web" id -u)" -ne 0

echo "Fresh backend, worker, and frontend images passed database, migration, runtime, health, and non-root smoke checks."
