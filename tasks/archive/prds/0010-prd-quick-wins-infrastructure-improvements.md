# PRD #0010: Quick Wins & Infrastructure Improvements

**Status**: Ready for Implementation
**Created**: 2025-10-27
**Priority**: High (Critical fixes + High-value quick wins)
**Estimated Effort**: Medium (8 features, varying complexity)

---

## Introduction/Overview

This PRD addresses 8 high-priority improvements to portfolio-ai ranging from critical bug fixes to infrastructure enhancements. These improvements will increase system reliability, developer productivity, and operational visibility. All features are independent and can be implemented in priority order.

**Problem Statement**: Portfolio-ai has several critical issues and missing infrastructure that impact reliability and developer experience:
1. Deprecated FastAPI lifecycle handlers that will break in future versions
2. Missing error handling in price fetcher causing analytics crashes
3. No structured logging for debugging production issues
4. No automated code quality checks before commits
5. Database schema changes require manual DB deletion (data loss)
6. Missing health monitoring for production deployments
7. No multi-source failover for price data (yfinance-only is fragile)
8. Slow agent execution blocks API (poor UX)

---

## Goals

1. **Fix critical deprecations** - Migrate to FastAPI lifespan handlers before breaking changes
2. **Improve reliability** - Add error handling to prevent crashes, implement multi-source price failover
3. **Enhance observability** - Add structured logging and health monitoring
4. **Boost developer productivity** - Add pre-commit hooks to catch issues early
5. **Enable safe schema evolution** - Implement database migrations
6. **Improve UX** - Make agent execution non-blocking

---

## User Stories

### As a **developer**:
- I want pre-commit hooks to catch linting/type errors so I don't push broken code
- I want structured JSON logs so I can debug production issues efficiently
- I want database migrations so I can evolve the schema without losing data
- I want the app to start without deprecation warnings so I know it won't break

### As a **system operator**:
- I want a health check endpoint so I can monitor service status
- I want to see data source availability so I know when yfinance is down
- I want structured logs so I can aggregate and search them

### As an **end user**:
- I want agent runs to not block the UI so I can continue using the app
- I want price data to work even when yfinance is down (Polygon backup)
- I want the app to not crash when stock data is unavailable

---

## Functional Requirements

### Feature 1: Migrate to FastAPI Lifespan Handlers (Critical Fix)

**Priority**: P0 (Critical - 10 minutes to fix)

1.1. Replace `@app.on_event("startup")` with `@asynccontextmanager` lifespan pattern
1.2. Replace `@app.on_event("shutdown")` if present with lifespan cleanup
1.3. Initialize storage and schema in lifespan startup phase
1.4. Verify no deprecation warnings on app startup
1.5. Update tests if needed to work with lifespan

**Technical Details**:
- Location: `backend/app/main.py:47`
- Current: `@app.on_event("startup")`
- New: `@asynccontextmanager async def lifespan(app: FastAPI):`
- Reference: https://fastapi.tiangolo.com/advanced/events/

### Feature 2: Add Comprehensive Error Handling to Price Fetcher

**Priority**: P1 (High value, small effort)

2.1. Wrap all yfinance API calls in try/except blocks
2.2. Return None or empty PriceData for individual symbol failures (don't crash batch)
2.3. Log specific error types (ticker not found, API timeout, rate limit, network error)
2.4. Add retry logic with exponential backoff for transient failures (3 retries)
2.5. Return partial results when some symbols succeed and others fail
2.6. Add error field to PriceData model to track per-symbol failures
2.7. Update analytics to skip positions with missing price data gracefully

**Technical Details**:
- Location: `backend/app/portfolio/price_fetcher.py`
- Errors to handle: `HTTPError`, `Timeout`, `JSONDecodeError`, `KeyError`
- Add: `PriceData.error: str | None` field
- Cache failures for 5 minutes to avoid retry storms

### Feature 3: Implement Structured JSON Logging with structlog

**Priority**: P2 (Enables debugging for all other features)

3.1. Add `structlog` dependency to `requirements.txt`
3.2. Configure structlog with JSON processor for machine-readable logs
3.3. Add context processors: timestamp, log level, logger name, thread ID
3.4. Replace all `logging.info()` calls with `logger.info()` + structured fields
3.5. Add request ID to all API logs (FastAPI middleware)
3.6. Log to stdout (JSON format) + file (`logs/portfolio-ai.log` with daily rotation)
3.7. Add structured fields for key operations:
   - Price fetches: `symbol`, `source`, `cache_hit`, `duration_ms`
   - Agent runs: `agent_type`, `run_id`, `num_ideas`, `cost_usd`, `duration_s`
   - API requests: `method`, `path`, `status_code`, `duration_ms`, `user_agent`
3.8. Update existing log calls to include structured context

**Technical Details**:
- Library: `structlog` (https://www.structlog.org/)
- Output: JSON to stdout + file
- File rotation: Daily, keep 30 days
- Example: `logger.info("price_fetch_complete", symbol="AAPL", source="yfinance", cache_hit=True, duration_ms=245)`

### Feature 4: Add Pre-commit Hooks for Code Quality

**Priority**: P2 (Prevents future issues)

4.1. Add `pre-commit` framework to `requirements.txt`
4.2. Create `.pre-commit-config.yaml` with hooks:
   - `ruff format` (auto-fix formatting)
   - `ruff check` (linting, fail on errors)
   - `mypy` (type checking, fail on errors)
4.3. Configure hooks to run on staged Python files only
4.4. Auto-fix formatting issues (ruff format --fix)
4.5. Fail commit on linting or type errors (show how to fix)
4.6. Add `.pre-commit-config.yaml` to git
4.7. Document setup in `docs/core/DEVELOPMENT.md`:
   - Run `pre-commit install` once after clone
   - Run `pre-commit run --all-files` to check all files
   - Use `git commit --no-verify` to bypass (emergency only)

**Technical Details**:
- Framework: `pre-commit` (https://pre-commit.com/)
- Scope: Linting + type checking only (no tests - too slow)
- Auto-fix: Formatting only (ruff format)
- Performance: Target <5 seconds for typical commit

### Feature 5: Implement Database Migration System

**Priority**: P2 (Important but can defer)

5.1. Create `backend/app/storage/migrations.py` module
5.2. Add `schema_migrations` table to track applied migrations:
   - `version INTEGER PRIMARY KEY`
   - `description TEXT`
   - `applied_at TIMESTAMP`
   - `checksum TEXT` (to detect tampering)
5.3. Create `backend/migrations/` directory for SQL migration files
5.4. Migration file naming: `001_add_user_preferences_table.sql`, `002_add_beta_column.sql`
5.5. Implement `MigrationManager.apply_migrations()`:
   - Read all migration files
   - Check which are already applied (schema_migrations table)
   - Execute pending migrations in order
   - Record each migration in schema_migrations
5.6. Run migrations automatically on app startup (before schema.ensure_schema())
5.7. Add `scripts/create_migration.sh` helper to generate new migration files
5.8. Schema changes only (no data transformations or rollbacks for v1)

**Technical Details**:
- Tool: Custom SQL-based migrations (DuckDB doesn't support Alembic)
- Location: `backend/app/storage/migrations.py`, `backend/migrations/*.sql`
- Example migration file:
  ```sql
  -- 003_add_idea_tags_column.sql
  ALTER TABLE agent_ideas ADD COLUMN tags TEXT;
  ```

### Feature 6: Add Health Check Dashboard Endpoint

**Priority**: P3 (Nice to have)

6.1. Extend `GET /health` endpoint to return detailed health status
6.2. Check DuckDB connectivity (execute simple query)
6.3. Check yfinance availability (fetch AAPL price)
6.4. Check Polygon availability (once implemented in PRD #0011)
6.5. Return last successful price fetch timestamp (from price_cache)
6.6. Return cache hit rate (last 100 fetches)
6.7. Return agent run statistics (total runs, avg duration, avg cost)
6.8. Return HTTP 503 if critical checks fail, 200 if healthy
6.9. Add optional HTML dashboard view (`GET /health?format=html`)
6.10. Include system info: Python version, app version, uptime

**Technical Details**:
- Endpoint: `GET /health` (extend existing)
- Response format: JSON (default) or HTML (`?format=html`)
- Status codes: 200 (healthy), 503 (unhealthy)
- Example response:
  ```json
  {
    "status": "healthy",
    "timestamp": "2025-10-27T10:30:00Z",
    "version": "1.0.0",
    "uptime_seconds": 86400,
    "checks": {
      "database": {"status": "ok", "latency_ms": 2},
      "yfinance": {"status": "ok", "last_fetch": "2025-10-27T10:25:00Z"},
      "polygon": {"status": "ok", "last_fetch": "2025-10-27T10:20:00Z"}
    },
    "cache_stats": {"hit_rate": 0.85, "total_fetches": 1250},
    "agent_stats": {"total_runs": 42, "avg_duration_s": 45, "avg_cost_usd": 0.12}
  }
  ```

### Feature 7: Implement Multi-Source Price Data with Polygon Backup

**Priority**: P1 (Critical resilience - but more complex)

7.1. Copy market-sim YAML configs to `config/sources/`:
   - `polygon.yaml`, `yfinance.yaml`, `finnhub.yaml`, `fred.yaml`, `google_news.yaml`
   - Extract API keys from market-sim Docker container (see FUTURE-market-sim-datasources-migration.md)
7.2. Add DuckDB tables for source configuration:
   - `source_registry` (source_id, display_name, priority, enabled, definition JSON)
   - `source_credentials` (source_id, field, value - encrypted)
   - `endpoint_catalog` (source_id, endpoint_key, target_table, path_template, field_mapping JSON)
7.3. Create YAML loader to populate these tables from `config/sources/*.yaml`
7.4. Port market-sim infrastructure:
   - `backend/app/sources/rest_api_source.py` - Generic REST API adapter
   - `backend/app/multi_source_fetcher.py` - Failover logic
   - `backend/app/polygon_client.py` - Polygon REST client with rate limiting
7.5. Update `PriceDataFetcher` to use `MultiSourceFetcher`:
   - Try yfinance first (priority 1)
   - Fallback to Polygon on 429/timeout/error (priority 10)
   - Track success/failure stats per source
   - Implement 60-second cooldown after rate limit
7.6. Add source performance tracking (success rate, latency, rate limits)
7.7. Update health check to report source availability
7.8. Migrate existing yfinance calls to multi-source pattern

**Technical Details**:
- API key storage: DuckDB `source_credentials` table + environment variables
- Failover priority: yfinance (1) → Polygon (10) → Finnhub (20)
- Rate limit handling: 60s cooldown, automatic source switching
- Cost tracking: Log Polygon API usage (5 req/min free tier)
- Reference: `~/market-sim/app/multi_source_fetcher.py`, `~/market-sim/config/sources/polygon.yaml`

### Feature 8: Convert Agent Runs to Background Tasks

**Priority**: P1 (UX improvement)

8.1. Add `celery` and `redis` dependencies to `requirements.txt`
8.2. Create `backend/app/celery_app.py` to configure Celery with Redis broker
8.3. Convert agent run methods to Celery tasks:
   - `@celery_app.task def run_discovery_agent() -> str` (returns run_id)
   - `@celery_app.task def run_portfolio_analyzer(portfolio_id: str) -> str`
8.4. Update `POST /api/ideas/generate` to:
   - Start Celery task instead of blocking
   - Return immediately with `run_id` and `status: "running"`
8.5. Add new endpoint `GET /api/ideas/runs/{run_id}/status`:
   - Query Celery task status
   - Return `{status: "pending|running|completed|failed", progress: 0-100, num_ideas: int}`
8.6. Add polling logic to frontend (check status every 2 seconds)
8.7. Update agent run tracking to include Celery task_id
8.8. Add cleanup job to remove completed tasks after 1 hour

**Technical Details**:
- Backend: Celery with Redis broker
- Task queue: Redis (add to docker-compose or run natively: `redis-server`)
- Worker: `celery -A app.celery_app worker --loglevel=info`
- Status endpoint: `GET /api/ideas/runs/{run_id}/status`
- Frontend polling: 2-second interval, timeout after 5 minutes
- Celery config: `broker_url="redis://localhost:6379/0"`, `result_backend="redis://localhost:6379/1"`

---

## Non-Goals (Out of Scope)

- ❌ Running tests in pre-commit hooks (too slow)
- ❌ Data transformations or rollback in migrations (schema-only)
- ❌ Prometheus/Grafana integration for monitoring (use JSON logs + external tools)
- ❌ WebSocket updates for agent status (REST polling is sufficient)
- ❌ Encrypted credentials at rest (environment variables are acceptable for single-user)
- ❌ Multiple Redis instances or HA setup (single Redis is fine for MVP)

---

## Implementation Priority Order

**Suggested order** (dependencies noted):

1. **Feature 1** - Lifespan handlers (10 min, critical fix)
2. **Feature 2** - Price fetcher error handling (1 hour, high value)
3. **Feature 3** - Structured logging (2 hours, enables debugging)
4. **Feature 4** - Pre-commit hooks (1 hour, prevents issues)
5. **Feature 6** - Health check dashboard (2 hours, nice monitoring)
6. **Feature 7** - Multi-source failover (8 hours, critical resilience) *depends on Feature 3*
7. **Feature 8** - Background tasks (4 hours, UX improvement)
8. **Feature 5** - Database migrations (3 hours, important but can defer)

**Total estimated effort**: ~21 hours

---

## Technical Considerations

### Dependencies to Add

```txt
# requirements.txt additions
structlog>=24.1.0          # Feature 3 - Structured logging
pre-commit>=3.7.0          # Feature 4 - Pre-commit hooks
celery>=5.3.0              # Feature 8 - Background tasks
redis>=5.0.0               # Feature 8 - Celery broker client
```

### External Services Required

- **Redis** (Feature 8): Run natively via `redis-server` or add to docker-compose
- **API Keys** (Feature 7):
  - `POLYGON_API_KEY` (extract from market-sim or get free tier at polygon.io)
  - `FINNHUB_API_KEY` (optional, get free tier at finnhub.io)

### Database Schema Changes

**Feature 5 - Migrations**:
```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT NOT NULL
);
```

**Feature 7 - Multi-source**:
```sql
CREATE TABLE IF NOT EXISTS source_registry (
    source_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    priority INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    definition JSON
);

CREATE TABLE IF NOT EXISTS source_credentials (
    source_id TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (source_id, field)
);

CREATE TABLE IF NOT EXISTS endpoint_catalog (
    source_id TEXT NOT NULL,
    endpoint_key TEXT NOT NULL,
    target_table TEXT NOT NULL,
    path_template TEXT NOT NULL,
    field_mapping JSON,
    PRIMARY KEY (source_id, endpoint_key)
);
```

**Feature 8 - Background tasks**:
```sql
ALTER TABLE agent_runs ADD COLUMN celery_task_id TEXT;
```

---

## Success Metrics

1. **Feature 1**: Zero deprecation warnings on startup ✅
2. **Feature 2**: Zero analytics crashes due to missing price data ✅
3. **Feature 3**: 100% of logs in structured JSON format ✅
4. **Feature 4**: Zero failed commits due to linting/type errors (after setup) ✅
5. **Feature 5**: Schema changes applied without manual DB deletion ✅
6. **Feature 6**: Health check returns accurate status in <100ms ✅
7. **Feature 7**: Price data fetched even when yfinance returns 429 ✅
8. **Feature 8**: Agent runs return immediately, frontend polls status ✅

---

## Open Questions

1. ✅ **ANSWERED** - Polygon API key: Extract from market-sim or get new free tier key?
   - **Decision**: Extract from market-sim Docker container first, document how to get new key as fallback

2. ✅ **ANSWERED** - Redis deployment: Native redis-server or Docker?
   - **Decision**: Native redis-server (matches project's no-Docker philosophy)

3. ✅ **ANSWERED** - Log rotation: Daily or size-based?
   - **Decision**: Daily rotation, keep 30 days

4. ✅ **ANSWERED** - Health check HTML dashboard: Simple table or fancy UI?
   - **Decision**: Simple table (can enhance later)

5. **TO CLARIFY** - Migration checksum: MD5 or SHA256?
   - **Recommendation**: SHA256 for better security

6. **TO CLARIFY** - Celery worker deployment: systemd service or manual start?
   - **Recommendation**: Document manual start for now, add systemd in OPERATIONS.md later

---

## Design Considerations

### Feature 3: Structured Logging Example

**Before** (basic logging):
```python
logger.info(f"Fetching prices for {len(symbols)} symbols")
```

**After** (structured logging):
```python
logger.info("price_fetch_started",
            num_symbols=len(symbols),
            symbols=symbols,
            source="yfinance",
            request_id=request_id)
```

**Output**:
```json
{"event": "price_fetch_started", "num_symbols": 5, "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"], "source": "yfinance", "request_id": "abc123", "timestamp": "2025-10-27T10:30:00.123456Z", "level": "info"}
```

### Feature 7: Multi-Source Failover Flow

```
1. User requests portfolio analytics
2. PriceDataFetcher.fetch_price_data(["AAPL", "MSFT", "GOOGL"])
3. MultiSourceFetcher tries sources in priority order:
   a. yfinance (priority 1) - fetches AAPL, MSFT successfully
   b. yfinance returns 429 (rate limited) for GOOGL
   c. MultiSourceFetcher marks yfinance as rate-limited (60s cooldown)
   d. MultiSourceFetcher tries Polygon (priority 10) for GOOGL
   e. Polygon returns GOOGL price successfully
4. Return combined results: {AAPL: yfinance, MSFT: yfinance, GOOGL: polygon}
5. Log source performance: yfinance 2/3 success, polygon 1/1 success
```

---

## Documentation Updates Required

- `docs/core/DEVELOPMENT.md`: Add pre-commit hooks setup section
- `docs/core/OPERATIONS.md`: Add Redis setup, Celery worker startup, log rotation config
- `docs/core/API_REFERENCE.md`: Document new health check response format, agent status endpoint
- `CLAUDE.md`: Add celery worker startup to command quick reference

---

## Related PRDs

- **PRD #0011** (Strategic Features) - Depends on Features 3, 7 for logging and data sources
- **FUTURE-market-sim-datasources-migration.md** - Reference for Feature 7 implementation

---

**End of PRD #0010**
