# Task List: PRD #0010 - Quick Wins & Infrastructure Improvements

**PRD**: `0010-prd-quick-wins-infrastructure-improvements.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: High
**Last Updated**: 2025-10-27

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0 (Lifespan handlers - critical, 10 min fix)
2. Proceed with Task 2.0 (Error handling - high value, 1 hour)
3. Continue in priority order: 3.0 → 4.0 → 6.0 → 7.0 → 8.0 → 5.0

**EFFORT TO COMPLETE:** High (~21 hours total across 8 features)

---

## High-Level Tasks (Parent Tasks)

Based on PRD #0010, here are the main implementation phases:

- [ ] **1.0 Migrate to FastAPI Lifespan Handlers** (P0 - Critical, 10 min)
- [ ] **2.0 Add Comprehensive Error Handling to Price Fetcher** (P1 - High value, 1 hour)
- [ ] **3.0 Implement Structured JSON Logging with structlog** (P2 - Enables debugging, 2 hours)
- [ ] **4.0 Add Pre-commit Hooks for Code Quality** (P2 - Prevents issues, 1 hour)
- [ ] **5.0 Implement Database Migration System** (P2 - Important but can defer, 3 hours)
- [ ] **6.0 Add Health Check Dashboard Endpoint** (P3 - Nice to have, 2 hours)
- [ ] **7.0 Implement Multi-Source Price Data with Polygon Backup** (P1 - Critical resilience, 8 hours)
- [ ] **8.0 Convert Agent Runs to Background Tasks (Celery)** (P1 - UX improvement, 4 hours)

---

## Relevant Files

### Files to Create (33 new files)

**Feature 3 - Structured Logging:**
- `backend/app/logging_config.py` (~80 lines) - structlog configuration and setup
- `backend/logs/.gitkeep` (1 line) - Create logs directory

**Feature 4 - Pre-commit Hooks:**
- `.pre-commit-config.yaml` (~40 lines) - Pre-commit hooks configuration

**Feature 5 - Database Migrations:**
- `backend/app/storage/migrations.py` (~150 lines) - Migration manager implementation
- `backend/migrations/.gitkeep` (1 line) - Create migrations directory
- `backend/migrations/001_create_schema_migrations_table.sql` (~10 lines) - Initial migration
- `scripts/create_migration.sh` (~30 lines) - Helper script to create new migrations

**Feature 7 - Multi-Source Architecture:**
- `backend/app/sources/base.py` (~100 lines) - Port from market-sim (BaseSource, SourceManager)
- `backend/app/sources/rest_api_source.py` (~200 lines) - Port from market-sim (RestApiSource)
- `backend/app/sources/polygon_source.py` (~150 lines) - Port from market-sim (PolygonSource)
- `backend/app/polygon_client.py` (~100 lines) - Port from market-sim (PolygonClient)
- `backend/app/multi_source_fetcher.py` (~400 lines) - Port from market-sim (MultiSourceFetcher with failover)
- `backend/app/jsonpath_mapper.py` (~100 lines) - Port from market-sim (JSONPath field mapping)
- `backend/app/storage/yaml_loader.py` (~120 lines) - Load YAML configs into DB tables

**YAML Source Configs (9 enabled sources from market-sim):**
- `config/sources/yfinance.yaml` (~70 lines) - Priority 1, FREE unlimited
- `config/sources/twelvedata.yaml` (~85 lines) - Priority 2, 8 req/min, 800/day
- `config/sources/fmp.yaml` (~100 lines) - Priority 3, 250/day
- `config/sources/polygon.yaml` (~100 lines) - Priority 10, 5 req/min
- `config/sources/finnhub.yaml` (~80 lines) - Priority 10, 60 req/min
- `config/sources/newsapi.yaml` (~65 lines) - Priority 25, 100/day
- `config/sources/alphavantage.yaml` (~90 lines) - Priority 30, 5 req/min, 500/day
- `config/sources/fred.yaml` (~75 lines) - FREE, economic data
- `config/sources/google_news.yaml` (~70 lines) - FREE RSS news

**Feature 8 - Background Tasks:**
- `backend/app/celery_app.py` (~60 lines) - Celery application configuration
- `backend/app/tasks/__init__.py` (5 lines) - Tasks module init
- `backend/app/tasks/agent_tasks.py` (~80 lines) - Celery tasks for agents

**Tests:**
- `backend/tests/test_logging_config.py` (~50 lines) - Test structured logging
- `backend/tests/test_migrations.py` (~80 lines) - Test migration manager
- `backend/tests/test_multi_source_fetcher.py` (~120 lines) - Test failover logic
- `backend/tests/test_celery_tasks.py` (~60 lines) - Test background tasks

### Files to Update (15 files)

**Feature 1 - Lifespan:**
- `backend/app/main.py` - Replace @app.on_event with lifespan context manager

**Feature 2 - Error Handling:**
- `backend/app/portfolio/price_fetcher.py` - Add try/except blocks, retry logic
- `backend/app/portfolio/models.py` - Add error field to PriceData
- `backend/app/portfolio/analytics.py` - Handle missing price data gracefully

**Feature 3 - Structured Logging:**
- `backend/app/main.py` - Import and configure structlog
- `backend/app/portfolio/price_fetcher.py` - Replace logging with structured logs
- `backend/app/agents/base.py` - Add structured logging to agent runs
- `backend/app/api/ideas.py` - Add request_id middleware and structured logs

**Feature 5 - Migrations:**
- `backend/app/storage/schema.py` - Call MigrationManager before ensure_schema()

**Feature 6 - Health Check:**
- `backend/app/main.py` - Extend /health endpoint with detailed checks
- `backend/app/api/health.py` - Create new health router (or extend main.py)

**Feature 7 - Multi-Source:**
- `backend/app/storage/schema.py` - Add source_registry, source_credentials, endpoint_catalog tables
- `backend/app/portfolio/price_fetcher.py` - Replace direct yfinance calls with MultiSourceFetcher

**Feature 8 - Background Tasks:**
- `backend/app/api/ideas.py` - Update generate endpoint to use Celery tasks
- `backend/app/storage/schema.py` - Add celery_task_id column to agent_runs

**Dependencies:**
- `backend/requirements.txt` - Add structlog, pre-commit, celery, redis

**Documentation:**
- `docs/core/DEVELOPMENT.md` - Add pre-commit setup, migration workflow
- `docs/core/OPERATIONS.md` - Add Redis setup, Celery worker startup
- `docs/core/API_REFERENCE.md` - Document new health check format, agent status endpoint
- `CLAUDE.md` - Add celery worker command to quick reference

### Notes

- All tests should be placed in `backend/tests/` directory
- Use `pytest tests/ -v` to run all tests
- Use `pytest tests/test_file.py -v` to run specific test
- Use `mypy app/ --strict` to verify type safety
- Use `scripts/lint.sh` to run linting and formatting checks
- Port market-sim files from `~/market-sim/app/` (use Docker container if needed)

---

## Tasks

- [ ] **1.0 Migrate to FastAPI Lifespan Handlers** (P0 - Critical, 10 min)
  - [x] 1.1 Replace deprecated on_event with lifespan context manager
    - [x] 1.1.1 Import `contextlib.asynccontextmanager` in `backend/app/main.py`
    - [x] 1.1.2 Create `lifespan()` async context manager function
    - [x] 1.1.3 Move `storage = get_storage()` and `storage.ensure_schema()` into lifespan startup
    - [x] 1.1.4 Add placeholder for shutdown logic (yield statement)
    - [x] 1.1.5 Update `FastAPI(lifespan=lifespan)` initialization
    - [x] 1.1.6 Remove `@app.on_event("startup")` decorator
  - [x] 1.2 Verify no deprecation warnings
    - [x] 1.2.1 Start backend: `uvicorn app.main:app --reload`
    - [x] 1.2.2 Check logs for deprecation warnings (should be zero)
    - [x] 1.2.3 Test GET /health endpoint works
  - [x] 1.3 Update tests if needed
    - [x] 1.3.1 Check if any tests depend on startup event
    - [x] 1.3.2 Update test fixtures to use lifespan if needed

- [ ] **2.0 Add Comprehensive Error Handling to Price Fetcher** (P1 - High value, 1 hour)
  - [ ] 2.1 Add error field to PriceData model
    - [ ] 2.1.1 Edit `backend/app/portfolio/models.py`
    - [ ] 2.1.2 Add `error: str | None = None` field to PriceData class
  - [ ] 2.2 Wrap yfinance API calls in try/except
    - [ ] 2.2.1 Edit `backend/app/portfolio/price_fetcher.py`
    - [ ] 2.2.2 Add try/except around `yf.Ticker(symbol).info` in `_fetch_fresh_prices()`
    - [ ] 2.2.3 Handle specific exceptions: HTTPError, Timeout, JSONDecodeError, KeyError
    - [ ] 2.2.4 Log specific error types with structured logging (after Feature 3)
    - [ ] 2.2.5 Return PriceData with error field set instead of crashing
  - [ ] 2.3 Add retry logic with exponential backoff
    - [ ] 2.3.1 Import `tenacity` library (add to requirements.txt)
    - [ ] 2.3.2 Add `@retry` decorator to `_fetch_fresh_prices()`: 3 attempts, exponential backoff
    - [ ] 2.3.3 Retry only on transient errors (Timeout, 503, 429)
    - [ ] 2.3.4 Don't retry on permanent errors (404, invalid symbol)
  - [ ] 2.4 Cache failures to avoid retry storms
    - [ ] 2.4.1 Cache failed fetches with 5-minute TTL
    - [ ] 2.4.2 Return cached error instead of retrying immediately
  - [ ] 2.5 Update analytics to handle missing price data
    - [ ] 2.5.1 Edit `backend/app/portfolio/analytics.py`
    - [ ] 2.5.2 Skip positions with PriceData.error set in calculations
    - [ ] 2.5.3 Log warning when skipping positions due to price errors
    - [ ] 2.5.4 Don't crash calculations if some prices missing
  - [ ] 2.6 Write tests for error handling
    - [ ] 2.6.1 Create `backend/tests/test_price_fetcher_errors.py`
    - [ ] 2.6.2 Test yfinance HTTP 429 (rate limit) handling
    - [ ] 2.6.3 Test yfinance timeout handling
    - [ ] 2.6.4 Test invalid symbol (404) handling
    - [ ] 2.6.5 Test partial success (some symbols succeed, some fail)
    - [ ] 2.6.6 Test analytics with missing price data

- [ ] **3.0 Implement Structured JSON Logging with structlog** (P2 - Enables debugging, 2 hours)
  - [ ] 3.1 Add structlog dependency
    - [ ] 3.1.1 Add `structlog>=24.1.0` to `backend/requirements.txt`
    - [ ] 3.1.2 Add `python-json-logger>=2.0.7` to requirements.txt
    - [ ] 3.1.3 Run `pip install -r backend/requirements.txt`
  - [ ] 3.2 Create logging configuration module
    - [ ] 3.2.1 Create `backend/app/logging_config.py`
    - [ ] 3.2.2 Configure structlog with JSON processor
    - [ ] 3.2.3 Add processors: timestamp, log level, logger name, thread ID
    - [ ] 3.2.4 Configure output to stdout (JSON) + file (`logs/portfolio-ai.log`)
    - [ ] 3.2.5 Add daily log rotation (keep 30 days)
  - [ ] 3.3 Create logs directory
    - [ ] 3.3.1 Create `backend/logs/` directory
    - [ ] 3.3.2 Add `backend/logs/.gitkeep` to track directory
    - [ ] 3.3.3 Add `backend/logs/*.log` to `.gitignore`
  - [ ] 3.4 Add request ID middleware to FastAPI
    - [ ] 3.4.1 Edit `backend/app/main.py`
    - [ ] 3.4.2 Add middleware to inject request_id into each request
    - [ ] 3.4.3 Store request_id in contextvars for access in all logs
  - [ ] 3.5 Replace logging calls with structured logging
    - [ ] 3.5.1 Update `backend/app/portfolio/price_fetcher.py`:
      - [ ] 3.5.1.1 Replace logger.info() with structured fields (symbol, source, cache_hit, duration_ms)
    - [ ] 3.5.2 Update `backend/app/agents/base.py`:
      - [ ] 3.5.2.1 Add structured logging for agent runs (agent_type, run_id, num_ideas, cost_usd, duration_s)
    - [ ] 3.5.3 Update `backend/app/api/ideas.py`:
      - [ ] 3.5.3.1 Add structured logging for API requests (method, path, status_code, duration_ms)
    - [ ] 3.5.4 Update `backend/app/main.py`:
      - [ ] 3.5.4.1 Replace basic logging.basicConfig with structlog setup
  - [ ] 3.6 Write tests for structured logging
    - [ ] 3.6.1 Create `backend/tests/test_logging_config.py`
    - [ ] 3.6.2 Test JSON output format
    - [ ] 3.6.3 Test log fields (timestamp, level, event, request_id)
    - [ ] 3.6.4 Test log rotation configuration

- [ ] **4.0 Add Pre-commit Hooks for Code Quality** (P2 - Prevents issues, 1 hour)
  - [ ] 4.1 Add pre-commit dependency
    - [ ] 4.1.1 Add `pre-commit>=3.7.0` to `backend/requirements.txt`
    - [ ] 4.1.2 Run `pip install -r backend/requirements.txt`
  - [ ] 4.2 Create pre-commit configuration
    - [ ] 4.2.1 Create `.pre-commit-config.yaml` in project root
    - [ ] 4.2.2 Add `ruff format` hook (auto-fix formatting)
    - [ ] 4.2.3 Add `ruff check` hook (linting, fail on errors)
    - [ ] 4.2.4 Add `mypy` hook (type checking, fail on errors)
    - [ ] 4.2.5 Configure hooks to run on Python files only
  - [ ] 4.3 Install pre-commit hooks
    - [ ] 4.3.1 Run `pre-commit install` in project root
    - [ ] 4.3.2 Test hooks: `pre-commit run --all-files`
    - [ ] 4.3.3 Verify hooks auto-fix formatting issues
    - [ ] 4.3.4 Verify hooks fail on linting/type errors
  - [ ] 4.4 Update documentation
    - [ ] 4.4.1 Edit `docs/core/DEVELOPMENT.md`
    - [ ] 4.4.2 Add "Pre-commit Hooks" section with setup instructions
    - [ ] 4.4.3 Document `pre-commit install` one-time setup
    - [ ] 4.4.4 Document `pre-commit run --all-files` to check all files
    - [ ] 4.4.5 Document `git commit --no-verify` for emergency bypass

- [ ] **5.0 Implement Database Migration System** (P2 - Important but can defer, 3 hours)
  - [ ] 5.1 Create schema_migrations table
    - [ ] 5.1.1 Edit `backend/app/storage/schema.py`
    - [ ] 5.1.2 Add `_create_migrations_table()` method to SchemaManager
    - [ ] 5.1.3 Create table: version (PK), description, applied_at, checksum
    - [ ] 5.1.4 Call from `ensure_schema()` before other tables
  - [ ] 5.2 Create MigrationManager class
    - [ ] 5.2.1 Create `backend/app/storage/migrations.py`
    - [ ] 5.2.2 Implement `MigrationManager.__init__(storage: DuckDBStorage)`
    - [ ] 5.2.3 Implement `_get_migration_files() -> list[tuple[int, str, str]]`
      - [ ] 5.2.3.1 Read all .sql files from `backend/migrations/` directory
      - [ ] 5.2.3.2 Parse version from filename (e.g., `001_add_column.sql` → version 1)
      - [ ] 5.2.3.3 Return sorted list of (version, filename, SQL content)
    - [ ] 5.2.4 Implement `_get_applied_migrations() -> set[int]`
      - [ ] 5.2.4.1 Query schema_migrations table
      - [ ] 5.2.4.2 Return set of applied version numbers
    - [ ] 5.2.5 Implement `apply_migrations() -> None`
      - [ ] 5.2.5.1 Get all migration files
      - [ ] 5.2.5.2 Get already-applied migrations
      - [ ] 5.2.5.3 Filter to pending migrations
      - [ ] 5.2.5.4 Execute each pending migration in order
      - [ ] 5.2.5.5 Calculate checksum (SHA256) of SQL content
      - [ ] 5.2.5.6 Record migration in schema_migrations table
      - [ ] 5.2.5.7 Log each migration applied
  - [ ] 5.3 Create migrations directory
    - [ ] 5.3.1 Create `backend/migrations/` directory
    - [ ] 5.3.2 Create `backend/migrations/.gitkeep` to track directory
    - [ ] 5.3.3 Create first migration: `backend/migrations/001_create_schema_migrations_table.sql`
      - [ ] 5.3.3.1 SQL to create schema_migrations table (idempotent)
  - [ ] 5.4 Integrate migrations into startup
    - [ ] 5.4.1 Edit `backend/app/storage/schema.py`
    - [ ] 5.4.2 Import MigrationManager
    - [ ] 5.4.3 Call `MigrationManager(storage).apply_migrations()` at start of ensure_schema()
    - [ ] 5.4.4 Migrations run before table creation
  - [ ] 5.5 Create migration helper script
    - [ ] 5.5.1 Create `scripts/create_migration.sh`
    - [ ] 5.5.2 Accept description as argument
    - [ ] 5.5.3 Auto-increment version number (check last migration file)
    - [ ] 5.5.4 Create new migration file: `XXX_description.sql`
    - [ ] 5.5.5 Add template SQL comment with description
    - [ ] 5.5.6 Make script executable: `chmod +x scripts/create_migration.sh`
  - [ ] 5.6 Write migration tests
    - [ ] 5.6.1 Create `backend/tests/test_migrations.py`
    - [ ] 5.6.2 Test migration file parsing (version extraction)
    - [ ] 5.6.3 Test migration application (pending migrations executed)
    - [ ] 5.6.4 Test idempotency (running migrations twice doesn't duplicate)
    - [ ] 5.6.5 Test checksum validation
  - [ ] 5.7 Update documentation
    - [ ] 5.7.1 Edit `docs/core/DEVELOPMENT.md`
    - [ ] 5.7.2 Add "Database Migrations" section
    - [ ] 5.7.3 Document `scripts/create_migration.sh "description"` usage
    - [ ] 5.7.4 Document migration file naming convention
    - [ ] 5.7.5 Document that migrations run automatically on startup

- [ ] **6.0 Add Health Check Dashboard Endpoint** (P3 - Nice to have, 2 hours)
  - [ ] 6.1 Extend /health endpoint with detailed checks
    - [ ] 6.1.1 Edit `backend/app/main.py` or create `backend/app/api/health.py`
    - [ ] 6.1.2 Create `HealthCheckService` class
    - [ ] 6.1.3 Implement `check_database()` - Execute simple query, measure latency
    - [ ] 6.1.4 Implement `check_yfinance()` - Fetch AAPL price, measure success
    - [ ] 6.1.5 Implement `get_last_price_fetch()` - Query price_cache for last fetch timestamp
    - [ ] 6.1.6 Implement `get_cache_stats()` - Calculate hit rate from logs/metrics
    - [ ] 6.1.7 Implement `get_agent_stats()` - Query agent_runs for total, avg duration, avg cost
  - [ ] 6.2 Create health check response model
    - [ ] 6.2.1 Create Pydantic models for health check response
    - [ ] 6.2.2 HealthCheckResponse with status, timestamp, version, uptime, checks
    - [ ] 6.2.3 CheckResult with status (ok/degraded/down), latency_ms, last_success
    - [ ] 6.2.4 CacheStats with hit_rate, total_fetches
    - [ ] 6.2.5 AgentStats with total_runs, avg_duration_s, avg_cost_usd
  - [ ] 6.3 Implement health check endpoint
    - [ ] 6.3.1 Replace simple /health with comprehensive check
    - [ ] 6.3.2 Run all health checks (database, yfinance, cache, agents)
    - [ ] 6.3.3 Return HTTP 503 if any critical check fails (database)
    - [ ] 6.3.4 Return HTTP 200 if healthy or degraded (non-critical failures)
    - [ ] 6.3.5 Return JSON response with all check results
  - [ ] 6.4 Add optional HTML dashboard
    - [ ] 6.4.1 Accept `?format=html` query parameter
    - [ ] 6.4.2 Return simple HTML table with check results
    - [ ] 6.4.3 Color-code status (green=ok, yellow=degraded, red=down)
  - [ ] 6.5 Add system info to health check
    - [ ] 6.5.1 Include Python version
    - [ ] 6.5.2 Include app version (from main.py)
    - [ ] 6.5.3 Calculate uptime (time since startup)
  - [ ] 6.6 Write health check tests
    - [ ] 6.6.1 Create `backend/tests/test_health_check.py`
    - [ ] 6.6.2 Test /health returns 200 when all checks pass
    - [ ] 6.6.3 Test /health returns 503 when database fails
    - [ ] 6.6.4 Test JSON response format
    - [ ] 6.6.5 Test HTML response format (?format=html)
  - [ ] 6.7 Update API documentation
    - [ ] 6.7.1 Edit `docs/core/API_REFERENCE.md`
    - [ ] 6.7.2 Document new /health response format
    - [ ] 6.7.3 Add example JSON response
    - [ ] 6.7.4 Document status codes (200, 503)

- [ ] **7.0 Implement Multi-Source Price Data with Polygon Backup** (P1 - Critical resilience, 8 hours)
  - [ ] 7.1 Extract ALL API keys from market-sim (9 sources need keys)
    - [ ] 7.1.1 Start market-sim Docker container: `cd ~/market-sim && docker-compose up -d`
    - [ ] 7.1.2 Extract ALL API keys: `docker exec market-sim-app env | grep -E "POLYGON|FINNHUB|TWELVEDATA|FMP|NEWSAPI|ALPHAVANTAGE|FRED"`
    - [ ] 7.1.3 Save to portfolio-ai .env file:
      - [ ] 7.1.3.1 POLYGON_API_KEY (priority 10, 5 req/min)
      - [ ] 7.1.3.2 TWELVEDATA_API_KEY (priority 2, 8 req/min, 800/day)
      - [ ] 7.1.3.3 FMP_API_KEY (priority 3, 250/day)
      - [ ] 7.1.3.4 FINNHUB_API_KEY (priority 10, 60 req/min)
      - [ ] 7.1.3.5 NEWSAPI_API_KEY (priority 25, 100/day)
      - [ ] 7.1.3.6 ALPHAVANTAGE_API_KEY (priority 30, 5 req/min, 500/day)
      - [ ] 7.1.3.7 FRED_API_KEY (free, economic data)
    - [ ] 7.1.4 yfinance and google_news require NO API keys (free)
    - [ ] 7.1.5 Optional: Extract source_credentials from DuckDB if keys stored there
  - [ ] 7.2 Copy ALL 9 enabled YAML source configurations from market-sim
    - [ ] 7.2.1 Create `config/sources/` directory in portfolio-ai
    - [ ] 7.2.2 Copy ALL enabled sources: `cp ~/market-sim/config/sources/{yfinance,twelvedata,fmp,polygon,finnhub,newsapi,alphavantage,fred,google_news}.yaml config/sources/`
    - [ ] 7.2.3 Review each YAML for portfolio-ai compatibility:
      - [ ] 7.2.3.1 yfinance.yaml (priority 1) - No changes needed
      - [ ] 7.2.3.2 twelvedata.yaml (priority 2) - Verify rate limits 8/min, 800/day
      - [ ] 7.2.3.3 fmp.yaml (priority 3) - Note 250/day limit, EOD only
      - [ ] 7.2.3.4 polygon.yaml (priority 10) - Verify 5/min limit
      - [ ] 7.2.3.5 finnhub.yaml (priority 10) - Verify 60/min limit
      - [ ] 7.2.3.6 newsapi.yaml (priority 25) - Note 100/day limit
      - [ ] 7.2.3.7 alphavantage.yaml (priority 30) - Verify 5/min, 500/day limits
      - [ ] 7.2.3.8 fred.yaml - No changes needed
      - [ ] 7.2.3.9 google_news.yaml - No changes needed
    - [ ] 7.2.4 Do NOT copy disabled sources (alpaca, stockdata - not viable on free tier)
    - [ ] 7.2.5 Update rate_limit_config in each YAML to match current free tier limits
  - [ ] 7.3 Add DuckDB tables for source configuration
    - [ ] 7.3.1 Edit `backend/app/storage/schema.py`
    - [ ] 7.3.2 Add `source_registry` table (source_id, display_name, priority, enabled, definition JSON)
    - [ ] 7.3.3 Add `source_credentials` table (source_id, field, value)
    - [ ] 7.3.4 Add `endpoint_catalog` table (source_id, endpoint_key, target_table, path_template, field_mapping JSON)
    - [ ] 7.3.5 Add indexes for efficient lookups
  - [ ] 7.4 Create YAML loader to populate source tables
    - [ ] 7.4.1 Create `backend/app/storage/yaml_loader.py`
    - [ ] 7.4.2 Implement `load_source_config(yaml_path: str) -> dict`
      - [ ] 7.4.2.1 Parse YAML file with pyyaml
      - [ ] 7.4.2.2 Extract source metadata (source_id, priority, enabled)
      - [ ] 7.4.2.3 Extract definition (connection, auth, rate_limits)
      - [ ] 7.4.2.4 Extract field_mapping for each target_table
    - [ ] 7.4.3 Implement `insert_source_to_db(source_config: dict, storage: DuckDBStorage)`
      - [ ] 7.4.3.1 Insert into source_registry
      - [ ] 7.4.3.2 Insert credentials into source_credentials
      - [ ] 7.4.3.3 Insert endpoints into endpoint_catalog
    - [ ] 7.4.4 Implement `load_all_sources(storage: DuckDBStorage)`
      - [ ] 7.4.4.1 Scan `config/sources/*.yaml`
      - [ ] 7.4.4.2 Load each YAML and insert to DB
      - [ ] 7.4.4.3 Run on first startup or via CLI command
  - [ ] 7.5 Port market-sim source infrastructure
    - [ ] 7.5.1 Copy `~/market-sim/app/sources/base.py` to `backend/app/sources/base.py`
      - [ ] 7.5.1.1 Adapt imports for portfolio-ai (no perf_profiler)
      - [ ] 7.5.1.2 Keep BaseSource, SourceManager, DatasetRequest
    - [ ] 7.5.2 Copy `~/market-sim/app/sources/rest_api_source.py` to `backend/app/sources/rest_api_source.py`
      - [ ] 7.5.2.1 Adapt imports (use portfolio-ai's storage)
      - [ ] 7.5.2.2 Keep RestApiSource class
    - [ ] 7.5.3 Copy `~/market-sim/app/sources/polygon_source.py` to `backend/app/sources/polygon_source.py`
      - [ ] 7.5.3.1 Adapt for portfolio-ai (remove minute bars, focus on reference/price)
    - [ ] 7.5.4 Copy `~/market-sim/app/polygon_client.py` to `backend/app/polygon_client.py`
      - [ ] 7.5.4.1 Keep PolygonClient with rate limiting
    - [ ] 7.5.5 Copy `~/market-sim/app/multi_source_fetcher.py` to `backend/app/multi_source_fetcher.py`
      - [ ] 7.5.5.1 Adapt for portfolio-ai (use DuckDB connection, remove job_queue)
      - [ ] 7.5.5.2 Keep failover logic, rate limit tracking
    - [ ] 7.5.6 Copy `~/market-sim/app/jsonpath_mapper.py` to `backend/app/jsonpath_mapper.py`
      - [ ] 7.5.6.1 Keep JSONPath field mapping utilities
  - [ ] 7.6 Update PriceDataFetcher to use MultiSourceFetcher
    - [ ] 7.6.1 Edit `backend/app/portfolio/price_fetcher.py`
    - [ ] 7.6.2 Import MultiSourceFetcher
    - [ ] 7.6.3 Replace direct yfinance calls with MultiSourceFetcher.fetch_reference_data()
    - [ ] 7.6.4 Handle multi-source response format
    - [ ] 7.6.5 Track source used per symbol (log which source succeeded)
    - [ ] 7.6.6 Keep existing cache logic
  - [ ] 7.7 Add source performance tracking
    - [ ] 7.7.1 Track success/failure stats per source in MultiSourceFetcher
    - [ ] 7.7.2 Log source performance metrics (success rate, latency, rate limits)
    - [ ] 7.7.3 Add to health check endpoint (source availability)
  - [ ] 7.8 Write multi-source tests
    - [ ] 7.8.1 Create `backend/tests/test_multi_source_fetcher.py`
    - [ ] 7.8.2 Test yfinance primary success
    - [ ] 7.8.3 Test Polygon failover when yfinance returns 429
    - [ ] 7.8.4 Test Polygon failover when yfinance times out
    - [ ] 7.8.5 Test all sources fail (AllSourcesFailedError)
    - [ ] 7.8.6 Test rate limit cooldown (60 seconds)
    - [ ] 7.8.7 Test source performance stats tracking
  - [ ] 7.9 Update health check to include ALL 9 data sources
    - [ ] 7.9.1 Edit health check endpoint (from Feature 6)
    - [ ] 7.9.2 Check availability for ALL enabled sources:
      - [ ] 7.9.2.1 yfinance (priority 1) - Test AAPL fetch
      - [ ] 7.9.2.2 twelvedata (priority 2) - Test API response
      - [ ] 7.9.2.3 fmp (priority 3) - Test API response
      - [ ] 7.9.2.4 polygon (priority 10) - Test API response
      - [ ] 7.9.2.5 finnhub (priority 10) - Test API response
      - [ ] 7.9.2.6 newsapi (priority 25) - Test API response
      - [ ] 7.9.2.7 alphavantage (priority 30) - Test API response
      - [ ] 7.9.2.8 fred - Test API response
      - [ ] 7.9.2.9 google_news - Test RSS feed
    - [ ] 7.9.3 Report last successful fetch timestamp per source (from MultiSourceFetcher stats)
    - [ ] 7.9.4 Report source status (ok/degraded/down) + rate limit status
    - [ ] 7.9.5 Display failover chain: yfinance → twelvedata → fmp → polygon → alphavantage

- [ ] **8.0 Convert Agent Runs to Background Tasks (Celery)** (P1 - UX improvement, 4 hours)
  - [ ] 8.1 Add Celery and Redis dependencies
    - [ ] 8.1.1 Add `celery>=5.3.0` to `backend/requirements.txt`
    - [ ] 8.1.2 Add `redis>=5.0.0` to requirements.txt
    - [ ] 8.1.3 Run `pip install -r backend/requirements.txt`
  - [ ] 8.2 Install and start Redis
    - [ ] 8.2.1 Install Redis: `sudo apt install redis-server` (or via package manager)
    - [ ] 8.2.2 Start Redis: `redis-server` (or `sudo systemctl start redis`)
    - [ ] 8.2.3 Verify Redis running: `redis-cli ping` (should return PONG)
  - [ ] 8.3 Create Celery application configuration
    - [ ] 8.3.1 Create `backend/app/celery_app.py`
    - [ ] 8.3.2 Configure Celery with Redis broker: `broker_url="redis://localhost:6379/0"`
    - [ ] 8.3.3 Configure result backend: `result_backend="redis://localhost:6379/1"`
    - [ ] 8.3.4 Set task serializer to JSON
    - [ ] 8.3.5 Import task modules
  - [ ] 8.4 Create Celery tasks for agent runs
    - [ ] 8.4.1 Create `backend/app/tasks/__init__.py`
    - [ ] 8.4.2 Create `backend/app/tasks/agent_tasks.py`
    - [ ] 8.4.3 Define `@celery_app.task def run_discovery_agent() -> str`
      - [ ] 8.4.3.1 Import DiscoveryAgent
      - [ ] 8.4.3.2 Execute agent.run()
      - [ ] 8.4.3.3 Return run_id
    - [ ] 8.4.4 Define `@celery_app.task def run_portfolio_analyzer() -> str`
      - [ ] 8.4.4.1 Import PortfolioAnalyzerAgent
      - [ ] 8.4.4.2 Execute agent.run()
      - [ ] 8.4.4.3 Return run_id
  - [ ] 8.5 Update agent_runs table schema
    - [ ] 8.5.1 Edit `backend/app/storage/schema.py`
    - [ ] 8.5.2 Add `celery_task_id TEXT` column to agent_runs table
    - [ ] 8.5.3 Create migration: `backend/migrations/002_add_celery_task_id.sql`
  - [ ] 8.6 Update ideas API to use Celery tasks
    - [ ] 8.6.1 Edit `backend/app/api/ideas.py`
    - [ ] 8.6.2 Import Celery tasks (run_discovery_agent, run_portfolio_analyzer)
    - [ ] 8.6.3 Update `POST /api/ideas/generate` endpoint:
      - [ ] 8.6.3.1 Instead of calling agent.run() directly, call task.apply_async()
      - [ ] 8.6.3.2 Get Celery task_id from AsyncResult
      - [ ] 8.6.3.3 Store task_id in agent_runs table
      - [ ] 8.6.3.4 Return immediately with `{status: "running", run_id: "...", task_id: "..."}`
  - [ ] 8.7 Create agent run status endpoint
    - [ ] 8.7.1 Add `GET /api/ideas/runs/{run_id}/status` endpoint
    - [ ] 8.7.2 Query agent_runs table for run_id
    - [ ] 8.7.3 Get Celery task status from task_id: `AsyncResult(task_id).state`
    - [ ] 8.7.4 Return `{status: "PENDING|STARTED|SUCCESS|FAILURE", progress: 0-100, num_ideas: int}`
    - [ ] 8.7.5 If status is SUCCESS, query agent_ideas count for num_ideas
  - [ ] 8.8 Add frontend polling for agent status
    - [ ] 8.8.1 Edit `frontend/lib/hooks/useIdeas.ts`
    - [ ] 8.8.2 After generating ideas, poll status endpoint every 2 seconds
    - [ ] 8.8.3 Update UI with status (Pending → Running → Complete)
    - [ ] 8.8.4 Stop polling when status is SUCCESS or FAILURE
    - [ ] 8.8.5 Timeout after 5 minutes
    - [ ] 8.8.6 Show error if status is FAILURE
  - [ ] 8.9 Add cleanup job for completed tasks
    - [ ] 8.9.1 Create Celery periodic task to delete completed task results after 1 hour
    - [ ] 8.9.2 Configure Celery beat scheduler
  - [ ] 8.10 Write Celery task tests
    - [ ] 8.10.1 Create `backend/tests/test_celery_tasks.py`
    - [ ] 8.10.2 Test discovery agent task execution
    - [ ] 8.10.3 Test portfolio analyzer task execution
    - [ ] 8.10.4 Test task status endpoint
    - [ ] 8.10.5 Test frontend polling integration
  - [ ] 8.11 Update documentation for Celery
    - [ ] 8.11.1 Edit `docs/core/OPERATIONS.md`
    - [ ] 8.11.2 Add "Redis Setup" section with installation instructions
    - [ ] 8.11.3 Add "Celery Worker Startup" section: `celery -A app.celery_app worker --loglevel=info`
    - [ ] 8.11.4 Document systemd service for Celery worker (optional)
    - [ ] 8.11.5 Edit `CLAUDE.md` - Add celery worker command to quick reference

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All 8 features implemented per PRD requirements
  - [ ] All integration points working correctly
  - [ ] Zero known bugs or regressions
  - [ ] Manual testing of each feature completed

- [ ] **Test Coverage** (target: 80%+)
  - [ ] Unit tests written for all new functions/classes
  - [ ] Integration tests for multi-source failover, background tasks
  - [ ] End-to-end test of agent generation with Celery
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage verified: `pytest tests/ --cov=app --cov-report=term-missing`

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Pre-commit hooks installed and passing
  - [ ] Code formatting applied: `ruff format app/`

- [ ] **Documentation**
  - [ ] All public functions/classes have docstrings
  - [ ] DEVELOPMENT.md updated with pre-commit, migrations workflow
  - [ ] OPERATIONS.md updated with Redis, Celery startup
  - [ ] API_REFERENCE.md updated with new health check, status endpoints
  - [ ] CLAUDE.md updated with celery worker command

- [ ] **Security & Performance**
  - [ ] SQL queries use parameterized placeholders (no f-strings with user input)
  - [ ] API keys stored in environment variables or DuckDB credentials table
  - [ ] No secrets in code
  - [ ] Input validation on all user inputs
  - [ ] No performance regressions vs baseline

- [ ] **Operational Readiness**
  - [ ] Structured logging configured and working
  - [ ] Health check endpoint returns accurate status
  - [ ] Multi-source failover tested with yfinance + Polygon
  - [ ] Celery worker running and processing tasks
  - [ ] Redis running and accepting connections
  - [ ] All services start cleanly (backend, frontend, celery, redis)
  - [ ] REFACTOR_STATUS.md updated (mark features complete)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist

---

## Notes

- **Implementation order**: Follow priority order from PRD: 1→2→3→4→6→7→8→5
- **Dependencies**: Feature 7 (multi-source) depends on Feature 3 (structured logging)
- **Testing**: Run tests after each feature: `pytest tests/ -v`
- **Port from market-sim**: Use `~/market-sim/app/` as reference, adapt for portfolio-ai patterns
- **API keys**: Extract ALL 7 API keys from market-sim Docker (yfinance + google_news are free, no keys)
- **Redis**: Must be running before starting Celery worker
- **Total effort**: ~21 hours across all 8 features

### Feature 7 - Multi-Source Architecture Details

**Why 9 Sources Matter**:
- **Resilience**: Automatic failover chain: yfinance → twelvedata → fmp → polygon → alphavantage
- **Load Balancing**: Distribute requests to avoid rate limits (yfinance unlimited, twelvedata 800/day, fmp 250/day, polygon 5/min, etc.)
- **Cost Optimization**: Free sources first (yfinance, google_news, fred), paid fallback only when needed
- **Data Quality**: Cross-validate prices across sources, detect anomalies
- **Capability Coverage**:
  - OHLCV: yfinance, twelvedata, fmp, polygon, alphavantage
  - News: finnhub, newsapi, polygon, google_news
  - Reference: all OHLCV sources + finnhub
  - Economic: fred

**MultiSourceFetcher Key Features** (from market-sim):
- **Priority-based routing**: Lower priority number = tried first
- **Rate limit tracking**: 60-second cooldown after 429 response
- **Automatic failover**: If source returns 429/timeout/error, try next source
- **Success/failure stats**: Track performance per source (success rate, latency)
- **Endpoint catalog**: Database-driven field mappings (JSONPath → DuckDB columns)
- **Source registry**: All config in DuckDB tables (source_registry, source_credentials, endpoint_catalog)

**Reference**: See `tasks/FUTURE-market-sim-datasources-migration.md` for complete source inventory and load balancing strategy
