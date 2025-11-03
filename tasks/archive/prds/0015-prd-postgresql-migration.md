# PRD 0015: PostgreSQL Migration - Production-Ready Database Infrastructure

**Status:** Draft
**Priority:** Critical (Immediate)
**Created:** 2025-10-29
**Owner:** Platform Infrastructure
**Blocks:** PRD #0014 Phase 1 completion (watchlist intelligence hub)

---

## Introduction/Overview

Migrate the Portfolio AI platform from DuckDB to PostgreSQL to resolve critical concurrency limitations that are blocking production readiness. DuckDB's single-writer architecture causes lock contention when multiple Celery workers attempt concurrent database operations, forcing the system to run with `concurrency=1` (significant performance degradation).

PostgreSQL's mature MVCC (Multi-Version Concurrency Control) and multi-writer architecture will eliminate these bottlenecks, enabling the platform to scale horizontally with multiple concurrent Celery workers, API requests, and background tasks without lock contention.

This migration maintains the existing storage abstraction layer while upgrading the underlying database to a production-grade solution that supports both OLTP (high-concurrency transactions) and OLAP (analytical queries) workloads.

**Root Problem:** DuckDB was designed for analytical workloads (OLAP), not high-concurrency transactional workloads (OLTP). The platform's architecture (FastAPI + Celery + background tasks) requires true multi-writer support.

**Solution:** PostgreSQL is the industry-standard database for this exact use case (web APIs + background workers), with proven scalability and operational maturity.

---

## Goals

1. **Eliminate Database Concurrency Bottlenecks**
   - Remove DuckDB lock contention issues
   - Enable multiple concurrent Celery workers (increase from 1 to 4+)
   - Support simultaneous API requests + background task writes

2. **Simplify Infrastructure**
   - Replace Redis with PostgreSQL for Celery broker/backend (one database for everything)
   - Native PostgreSQL installation (no Docker complexity)
   - Leverage existing PostgreSQL operational knowledge

3. **Preserve Existing Functionality**
   - Maintain storage abstraction layer (minimal code changes)
   - Migrate critical configuration data (API keys, credentials, preferences)
   - All existing features continue working without regression

4. **Improve Data Integrity**
   - Add proper foreign key constraints
   - Add missing indexes for performance
   - Enforce referential integrity at database level

5. **Production Readiness**
   - Comprehensive testing and validation
   - Performance benchmarking (prove improvement over DuckDB)
   - Operational documentation (backup, restore, monitoring)
   - Clear rollback strategy (safety net)

6. **Future-Proof Architecture**
   - Document migration path to Redis if high-throughput needed later
   - Scalable connection pooling configuration
   - Support for read replicas (future optimization)

---

## User Stories

### As a Developer
- **US-1:** I want database operations to complete without lock errors so that I can run multiple Celery workers concurrently
- **US-2:** I want clear setup scripts so that I can get PostgreSQL running with a single command
- **US-3:** I want comprehensive documentation so that I can troubleshoot issues using standard PostgreSQL tools
- **US-4:** I want automated migration scripts so that I can migrate configuration data without manual SQL editing
- **US-5:** I want the storage facade to remain unchanged so that application code requires minimal modifications

### As a Platform Operator
- **US-6:** I want native PostgreSQL installation so that I can use standard system tools (`systemctl`, `psql`, `pg_dump`)
- **US-7:** I want connection pooling configured so that the system handles concurrent load efficiently
- **US-8:** I want performance benchmarks so that I can verify the migration improved system performance
- **US-9:** I want backup/restore procedures so that I can protect data and recover from failures
- **US-10:** I want monitoring guidelines so that I can detect and respond to database issues proactively

### As a System
- **US-11:** The system must support 4+ concurrent Celery workers without database lock errors
- **US-12:** The system must complete watchlist refresh (5 tickers) in <2 seconds (current: ~1.2s with locks)
- **US-13:** The system must handle 100+ concurrent API requests without connection exhaustion
- **US-14:** The system must maintain <100ms p95 latency for read queries (portfolio, watchlist listings)

---

## Functional Requirements

### Phase 1: PostgreSQL Setup & Schema Migration (Days 1-2)

**FR-1.1:** Install PostgreSQL 16 (latest stable) natively on Ubuntu/Debian Linux
- Use system package manager (`apt install postgresql-16`)
- Configure to start automatically on boot (`systemctl enable postgresql`)
- Set up non-root postgres user with appropriate privileges

**FR-1.2:** Create database initialization script (`scripts/setup-postgres.sh`)
- Create database: `portfolio_ai`
- Create dedicated user: `portfolio_ai_user` with strong password
- Grant appropriate privileges (CONNECT, CREATE, INSERT, UPDATE, DELETE, SELECT)
- Configure authentication (local trust for dev, password for production)

**FR-1.3:** Convert DuckDB schema to PostgreSQL DDL
- Translate all 17+ tables from DuckDB to PostgreSQL syntax
- Tables to migrate:
  - **Core:** `accounts`, `portfolios`, `portfolio_holdings`, `user_preferences`
  - **Market Data:** `price_cache`, `day_bars`, `technical_indicators`, `news_cache`, `reference_cache`
  - **Watchlist:** `watchlist_items`, `watchlist_snapshots`
  - **Sources:** `source_performance`, `api_credentials`
  - **Agents:** `agent_runs`, `agent_messages`, `agent_costs`
  - **Metadata:** `schema_migrations`
- Add primary keys, indexes, and foreign key constraints (see FR-1.5)

**FR-1.4:** Handle SQL dialect differences between DuckDB and PostgreSQL
- **Timestamps:** Convert DuckDB `TIMESTAMP` → PostgreSQL `TIMESTAMP WITH TIME ZONE`
- **JSON:** Convert DuckDB `JSON` → PostgreSQL `JSONB` (better performance)
- **Auto-increment:** Convert DuckDB `INTEGER PRIMARY KEY` → PostgreSQL `SERIAL PRIMARY KEY`
- **Boolean:** Ensure consistent `BOOLEAN` type usage
- **Sequences:** Replace DuckDB implicit sequences with explicit `SERIAL` or `IDENTITY`
- **Data types:** Map DuckDB `HUGEINT` → PostgreSQL `BIGINT`

**FR-1.5:** Add schema enhancements (indexes, constraints) for data integrity and performance
- **Primary Keys:** All tables must have explicit primary key constraints
- **Foreign Keys:** Add referential integrity constraints:
  - `portfolio_holdings.portfolio_id` → `portfolios.portfolio_id` (CASCADE DELETE)
  - `watchlist_items.account_id` → `accounts.account_id` (CASCADE DELETE)
  - `watchlist_snapshots.item_id` → `watchlist_items.item_id` (CASCADE DELETE)
  - `agent_messages.run_id` → `agent_runs.run_id` (CASCADE DELETE)
- **Indexes:** Add performance indexes:
  - `price_cache(ticker, fetched_at DESC)` - Price lookups
  - `day_bars(ticker, date DESC)` - Historical data queries
  - `technical_indicators(ticker, calculated_at DESC)` - Indicator queries
  - `watchlist_items(account_id, added_at DESC)` - Watchlist listings
  - `watchlist_snapshots(item_id, snapshot_at DESC)` - Score history
  - `news_cache(ticker, published_at DESC)` - News queries
  - `agent_runs(account_id, started_at DESC)` - Agent history
- **Unique Constraints:**
  - `accounts(account_id)` - Unique account identifiers
  - `api_credentials(source_name)` - One credential per source
  - `source_performance(source_name)` - One perf record per source

**FR-1.6:** Create schema migration script (`scripts/migrate-schema-to-postgres.py`)
- Connect to PostgreSQL database
- Execute DDL statements in correct order (handle dependencies)
- Verify schema creation (all tables exist, indexes created)
- Seed initial data (schema_migrations table with version 1, 2)

### Phase 2: Data Migration (Day 2)

**FR-2.1:** Create data export script from DuckDB (`scripts/export-duckdb-data.py`)
- Export **configuration data only** (preserving system state):
  - `api_credentials` - All API keys and credentials
  - `user_preferences` - User settings (weights, refresh intervals)
  - `accounts` - User account records
  - `source_performance` - Source reliability metrics
  - `schema_migrations` - Migration history
- Export as CSV or JSON files (one per table)
- Log export summary (row counts per table)

**FR-2.2:** Create data import script to PostgreSQL (`scripts/import-data-to-postgres.py`)
- Read exported CSV/JSON files
- Insert data into PostgreSQL tables using parameterized queries
- Handle conflicts gracefully (e.g., ON CONFLICT DO NOTHING for duplicates)
- Validate data integrity (foreign key constraints pass)
- Log import summary (rows inserted, skipped, failed)

**FR-2.3:** Flush transactional data (start with clean slate)
- Do NOT migrate ephemeral data:
  - `price_cache` - Will be refetched from APIs
  - `day_bars` - Will be reingested
  - `technical_indicators` - Will be recalculated
  - `news_cache` - Will be refetched
  - `reference_cache` - Will be refetched
  - `watchlist_items`, `watchlist_snapshots` - Users can re-add tickers
  - `portfolios`, `portfolio_holdings` - Test data, can recreate
  - `agent_runs`, `agent_messages`, `agent_costs` - Historical logs, not critical
- Rationale: Cleaner migration, avoids data corruption, forces fresh data ingestion

**FR-2.4:** Provide rollback capability (backup DuckDB before migration)
- Create full DuckDB backup: `cp backend/data/portfolio.duckdb backend/data/portfolio.duckdb.backup-YYYYMMDD`
- Document rollback procedure (restore from backup, revert code changes)
- Keep backup for 7 days post-migration

### Phase 3: Application Code Updates (Day 3)

**FR-3.1:** Replace DuckDB connection with PostgreSQL in `backend/app/storage/connection.py`
- Install `psycopg2-binary` package (PostgreSQL Python adapter)
- Replace `duckdb.connect()` with SQLAlchemy engine:
  ```python
  from sqlalchemy import create_engine
  from sqlalchemy.pool import QueuePool

  DATABASE_URL = "postgresql://portfolio_ai_user:password@localhost:5432/portfolio_ai"
  engine = create_engine(
      DATABASE_URL,
      poolclass=QueuePool,
      pool_size=20,        # Max connections in pool
      max_overflow=10,     # Extra connections when pool exhausted
      pool_pre_ping=True,  # Verify connection health before use
      pool_recycle=3600,   # Recycle connections after 1 hour
  )
  ```
- Update `connection()` context manager to yield SQLAlchemy connections
- Remove DuckDB-specific pragmas (no longer needed)

**FR-3.2:** Update SQL queries for PostgreSQL compatibility in `backend/app/storage/queries.py`
- **Auto-increment columns:** Replace implicit integer PKs with explicit `SERIAL` or `RETURNING id` clauses
- **JSON operations:** Update DuckDB JSON syntax → PostgreSQL JSONB operators (`->`, `->>`, `@>`)
- **LIMIT/OFFSET:** PostgreSQL syntax is compatible, no changes needed
- **Date/time functions:** Replace DuckDB `CURRENT_TIMESTAMP` with PostgreSQL `NOW()`
- **String operations:** Review and test string functions (most compatible)
- **Window functions:** PostgreSQL syntax is similar, verify complex queries

**FR-3.3:** Update `backend/app/constants.py` to use PostgreSQL environment variable
- Change `DEFAULT_DUCKDB_PATH` → `DATABASE_URL`
- Add environment variable: `DATABASE_URL=postgresql://portfolio_ai_user:password@localhost:5432/portfolio_ai`
- Update `.env.example` with PostgreSQL connection string

**FR-3.4:** Update `backend/requirements.txt` with PostgreSQL dependencies
- Add: `psycopg2-binary==2.9.9` (PostgreSQL adapter)
- Add: `sqlalchemy==2.0.23` (Database toolkit)
- Remove: `duckdb` (no longer needed)
- Keep: All other dependencies unchanged

**FR-3.5:** Remove DuckDB-specific code and references
- Delete DuckDB connection configurations in `connection.py`
- Update comments/docstrings that mention DuckDB
- Remove DuckDB from project documentation

### Phase 4: Celery Configuration (Day 3)

**FR-4.1:** Configure Celery to use PostgreSQL as broker and result backend
- Update `backend/app/celery_app.py`:
  ```python
  from celery import Celery

  DATABASE_URL = "postgresql://portfolio_ai_user:password@localhost:5432/portfolio_ai"

  app = Celery(
      "portfolio_ai",
      broker=f"db+{DATABASE_URL}",           # PostgreSQL as message broker
      backend=f"db+{DATABASE_URL}",          # PostgreSQL for task results
      broker_connection_retry_on_startup=True,
  )

  app.conf.update(
      result_expires=3600,                   # Task results expire after 1 hour
      task_serializer="json",
      result_serializer="json",
      accept_content=["json"],
      timezone="UTC",
      enable_utc=True,
      worker_prefetch_multiplier=1,          # Avoid overloading single worker
  )
  ```

**FR-4.2:** Create Celery tables in PostgreSQL
- Celery automatically creates required tables on first startup:
  - `celery_taskmeta` - Task results and state
  - `celery_tasksetmeta` - Task group metadata
- Verify tables are created after first Celery worker start

**FR-4.3:** Remove Redis dependency from startup scripts
- Update `scripts/start-celery.sh` - Remove Redis startup check
- Update `scripts/start.sh` - Remove Redis startup
- Update `scripts/shutdown.sh` - Remove Redis shutdown
- Document: Redis can be uninstalled if not used by other services

**FR-4.4:** Increase Celery worker concurrency (now safe with PostgreSQL)
- Update `scripts/start-celery.sh`: Change `--concurrency=1` → `--concurrency=4`
- Rationale: PostgreSQL can handle 4 concurrent workers without lock issues
- Monitor CPU/memory usage and adjust concurrency if needed

**FR-4.5:** Document migration path to Redis (if high-throughput needed in future)
- Add section to `docs/core/OPERATIONS.md`: "Migrating Celery to Redis"
- When to consider Redis:
  - Celery task throughput exceeds 1000 tasks/second
  - Task latency requirements drop below 10ms
  - Worker pool scales beyond 20 workers
- Migration steps:
  1. Install Redis: `sudo apt install redis-server`
  2. Update Celery config: `broker="redis://localhost:6379/0"`
  3. Keep PostgreSQL as result backend (or switch to Redis)
  4. Test and benchmark performance difference

### Phase 5: Testing & Validation (Day 4)

**FR-5.1:** Run existing test suite and verify all tests pass
- Execute: `cd ~/portfolio-ai/backend && pytest tests/ -v`
- Target: 100% test pass rate (no regressions)
- Fix any test failures related to schema changes or SQL dialect differences

**FR-5.2:** Perform data integrity checks
- Verify foreign key constraints are enforced:
  - Attempt to insert orphaned record (should fail)
  - Verify CASCADE DELETE works (delete parent, child records auto-deleted)
- Verify unique constraints:
  - Attempt to insert duplicate account_id (should fail)
- Check data consistency:
  - All migrated API credentials are present (`SELECT COUNT(*) FROM api_credentials`)
  - All user preferences migrated (`SELECT * FROM user_preferences`)

**FR-5.3:** Execute performance benchmarks and compare against DuckDB baseline
- **Benchmark 1: Concurrent Writes (Celery Simulation)**
  - Run 4 concurrent tasks writing to different tables
  - Measure: Lock errors (should be 0), completion time
  - Compare: DuckDB (concurrency=1) vs PostgreSQL (concurrency=4)
  - Expected: PostgreSQL completes 4x faster with no lock errors

- **Benchmark 2: Watchlist Refresh**
  - Refresh 5 tickers (current production scenario)
  - Measure: End-to-end latency (price fetch + indicator calc + score compute)
  - Target: <2 seconds (current baseline: ~1.2s with locks, should remain similar)

- **Benchmark 3: API Read Performance**
  - Execute 100 GET requests to `/api/watchlist?account_id=default`
  - Measure: p50, p95, p99 latency
  - Target: p95 < 100ms

- **Benchmark 4: Bulk Insert**
  - Insert 1000 rows into `day_bars` table
  - Measure: Insertion time, transactions per second
  - Expected: PostgreSQL faster due to better bulk insert optimization

**FR-5.4:** Load testing with multiple concurrent clients
- Simulate production load:
  - 4 Celery workers running tasks concurrently
  - 20 concurrent API clients making requests
  - Background tasks writing data continuously
- Monitor:
  - PostgreSQL connection pool usage (`SELECT count(*) FROM pg_stat_activity`)
  - Database lock wait events (`SELECT * FROM pg_locks WHERE NOT granted`)
  - Query performance (`SELECT * FROM pg_stat_statements ORDER BY total_time DESC`)
- Target: No lock errors, connection pool never exhausted, p95 latency <100ms

**FR-5.5:** Verify Celery task execution with PostgreSQL broker/backend
- Queue 10 tasks of each type:
  - `refresh_watchlist_scores`
  - `ingest_historical_ohlcv`
  - `update_technical_indicators`
- Verify:
  - All tasks complete successfully (no failures)
  - Task results are stored in PostgreSQL (`celery_taskmeta` table)
  - No message loss (all 30 tasks accounted for)
  - Concurrent execution works (4 workers pick up tasks simultaneously)

**FR-5.6:** Manual end-to-end smoke testing
- **Watchlist Flow:**
  1. Add 5 tickers to watchlist via UI
  2. Trigger manual refresh
  3. Verify scores appear (non-zero)
  4. Check expanded row shows data
  5. Edit notes, verify persistence
  6. Delete ticker, verify cascade (snapshots also deleted)

- **Portfolio Flow:**
  1. Create portfolio
  2. Add holdings
  3. View analytics page
  4. Verify charts render
  5. Delete portfolio, verify cleanup

- **Preferences Flow:**
  1. Update watchlist preferences (weights, refresh interval)
  2. Verify persistence across page refresh
  3. Reset to defaults

**FR-5.7:** Create automated regression test suite for PostgreSQL-specific features
- Test: Foreign key constraints enforcement
- Test: Cascade deletes work correctly
- Test: Unique constraints are enforced
- Test: Connection pooling handles exhaustion gracefully (test with pool_size + max_overflow connections)
- Test: Concurrent transactions don't deadlock
- Add tests to `tests/test_postgresql_integration.py`

### Phase 6: Documentation & Operations (Day 5)

**FR-6.1:** Update core documentation with PostgreSQL setup instructions
- Update `docs/core/SETUP.md`:
  - Add PostgreSQL installation section
  - Document `scripts/setup-postgres.sh` usage
  - Add troubleshooting section (connection errors, permission issues)

- Update `docs/core/ARCHITECTURE.md`:
  - Replace DuckDB architecture diagram with PostgreSQL
  - Document connection pooling configuration
  - Explain Celery + PostgreSQL integration

- Update `docs/core/DEVELOPMENT.md`:
  - Update command quick reference (remove Redis commands, add PostgreSQL commands)
  - Add PostgreSQL-specific development tips (using `psql`, viewing logs)

- Update `CLAUDE.md`:
  - Update tech stack (PostgreSQL replaces DuckDB)
  - Update quick start commands (add PostgreSQL setup)

**FR-6.2:** Create operational runbooks in `docs/core/OPERATIONS.md`
- **Backup Procedures:**
  ```bash
  # Daily automated backup (cron job)
  pg_dump portfolio_ai > /backup/portfolio_ai_$(date +%Y%m%d).sql

  # Backup with compression
  pg_dump portfolio_ai | gzip > /backup/portfolio_ai_$(date +%Y%m%d).sql.gz
  ```

- **Restore Procedures:**
  ```bash
  # Restore from backup
  psql portfolio_ai < /backup/portfolio_ai_20251029.sql

  # Restore from compressed backup
  gunzip -c /backup/portfolio_ai_20251029.sql.gz | psql portfolio_ai
  ```

- **Monitoring Queries:**
  ```sql
  -- Active connections
  SELECT count(*) FROM pg_stat_activity WHERE datname = 'portfolio_ai';

  -- Connection pool usage
  SELECT count(*), state FROM pg_stat_activity WHERE datname = 'portfolio_ai' GROUP BY state;

  -- Slow queries (>100ms)
  SELECT query, total_time, calls FROM pg_stat_statements
  WHERE total_time / calls > 100 ORDER BY total_time DESC LIMIT 10;

  -- Table sizes
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

  -- Index usage
  SELECT schemaname, tablename, indexname, idx_scan
  FROM pg_stat_user_indexes WHERE schemaname = 'public' ORDER BY idx_scan DESC;
  ```

- **Performance Tuning:**
  - Recommended `postgresql.conf` settings for mixed workload
  - When to analyze tables (`ANALYZE table_name`)
  - When to reindex (`REINDEX TABLE table_name`)
  - Vacuum strategy (automatic vs manual)

- **Troubleshooting Guide:**
  - Connection exhaustion: Check connection pool settings
  - Slow queries: Analyze with `EXPLAIN ANALYZE`
  - Disk space: Monitor with `pg_size_pretty`
  - Deadlocks: Review `pg_locks` and adjust isolation levels

**FR-6.3:** Document SQL dialect differences for future development
- Create reference document: `docs/postgresql-dialect-reference.md`
- Common patterns:
  - DuckDB: `SELECT * FROM table LIMIT 10` → PostgreSQL: Same (compatible)
  - DuckDB: `json_extract(column, '$.field')` → PostgreSQL: `column->>'field'`
  - DuckDB: `CURRENT_TIMESTAMP` → PostgreSQL: `NOW()` or `CURRENT_TIMESTAMP` (both work)
  - DuckDB: Auto-increment implicit → PostgreSQL: `SERIAL` or `IDENTITY` explicit
- Add examples from actual codebase queries

**FR-6.4:** Update management scripts (`scripts/start.sh`, `scripts/restart.sh`, `scripts/shutdown.sh`)
- Add PostgreSQL status check to `start.sh`:
  ```bash
  # Check PostgreSQL is running
  if ! pg_isready -q; then
      echo "PostgreSQL not running, starting..."
      sudo systemctl start postgresql
  fi
  ```
- Remove Redis checks (no longer needed)
- Update service status section to show PostgreSQL instead of Redis

**FR-6.5:** Create PostgreSQL-specific utility scripts
- `scripts/postgres-backup.sh` - One-command backup with timestamp
- `scripts/postgres-restore.sh` - Interactive restore from backup file
- `scripts/postgres-vacuum.sh` - Maintenance vacuum and analyze
- `scripts/postgres-status.sh` - Show connection pool, active queries, table sizes
- Make scripts executable and document in README

### Phase 7: Rollback Strategy & Safety (Day 5)

**FR-7.1:** Document rollback procedure in case of critical issues
- Create `docs/postgresql-migration-rollback.md`:
  1. Stop all services (`./scripts/shutdown.sh`)
  2. Restore DuckDB backup: `cp backend/data/portfolio.duckdb.backup-YYYYMMDD backend/data/portfolio.duckdb`
  3. Revert code changes: `git checkout <commit-before-migration>`
  4. Reinstall DuckDB: `pip install duckdb`
  5. Restart services: `./scripts/start.sh`
  6. Verify functionality: Test critical flows (watchlist, portfolio)

**FR-7.2:** Define rollback decision criteria (when to abort migration)
- Rollback if:
  - Test suite pass rate drops below 95%
  - Performance benchmarks show >50% regression
  - Critical bugs discovered within 48 hours post-migration
  - Data integrity violations detected
  - Production downtime exceeds 4 hours
- Otherwise: Fix forward (PostgreSQL is the correct long-term solution)

**FR-7.3:** Implement health check for PostgreSQL connection
- Add to `/api/health` endpoint:
  ```json
  {
    "database": {
      "type": "postgresql",
      "status": "healthy",
      "connection_pool": {
        "size": 20,
        "active": 5,
        "available": 15
      },
      "response_time_ms": 12
    }
  }
  ```
- Alert if: connection pool exhausted, response time >100ms, connection errors

**FR-7.4:** Create pre-flight checklist (run before migration starts)
- [ ] DuckDB backup created and verified
- [ ] PostgreSQL installed and running (`pg_isready`)
- [ ] Database and user created (`psql -l | grep portfolio_ai`)
- [ ] All tests passing with DuckDB (baseline)
- [ ] Performance benchmarks captured (baseline metrics)
- [ ] All services running normally
- [ ] No pending code changes (clean working directory)
- [ ] Rollback procedure documented and reviewed

**FR-7.5:** Create post-migration checklist (verification steps)
- [ ] All services start successfully
- [ ] Test suite 100% pass rate
- [ ] Performance benchmarks meet targets
- [ ] Data integrity checks pass
- [ ] Manual smoke tests successful
- [ ] Connection pooling configured correctly
- [ ] Celery tasks execute successfully with concurrency=4
- [ ] No errors in logs for 1 hour
- [ ] Backup procedure tested (backup + restore)
- [ ] Documentation updated

---

## Non-Goals (Out of Scope)

**NG-1:** Docker containerization for PostgreSQL
- Rationale: Avoid Docker complexity based on negative market-sim experience
- Alternative: Native PostgreSQL installation with clear documentation

**NG-2:** Migrating historical transactional data
- Rationale: Clean slate is simpler and forces fresh data ingestion
- Preserved data: Configuration only (API keys, preferences, accounts)
- Not migrated: price_cache, day_bars, technical_indicators, watchlist items, portfolios

**NG-3:** Full schema refactoring or normalization
- Rationale: Minimize scope and risk
- Scope: Add indexes, constraints, and foreign keys only
- Future work: Schema optimization can be done after stable migration

**NG-4:** Switching to an ORM (SQLAlchemy Core/ORM)
- Rationale: Existing storage facade provides sufficient abstraction
- Current approach: Direct SQL queries with parameterized placeholders (secure and performant)
- Future work: Consider ORM if codebase grows significantly

**NG-5:** PostgreSQL replication or read replicas
- Rationale: Single-server setup sufficient for current scale
- Future work: Add read replicas if analytics queries impact write performance

**NG-6:** Immediate Redis migration for Celery
- Rationale: PostgreSQL broker is sufficient for current task frequency
- Migration path documented for future if high-throughput needs emerge

**NG-7:** Multi-tenant database architecture
- Rationale: Single-user/developer project currently
- Current approach: Single database, `account_id` filtering
- Future work: Consider schema-per-tenant if multi-tenant SaaS becomes goal

---

## Technical Considerations

### PostgreSQL Version & Extensions
- **Version:** PostgreSQL 16.x (latest stable release as of 2024)
- **Required Extensions:**
  - `pg_stat_statements` - Query performance monitoring (enable in postgresql.conf)
  - Built-in JSONB support (no extension needed)
- **Optional Extensions (future):**
  - `pg_trgm` - Fuzzy text search (for ticker symbol search)
  - `timescaledb` - Time-series optimization (for OHLCV data if scale increases)

### Connection Pooling Strategy
- **Pool Size:** 20 connections (4 Celery workers × 4 connections + 4 API workers = 20)
- **Max Overflow:** 10 additional connections (burst capacity)
- **Pool Pre-Ping:** Enabled (verify connection health before use, handles stale connections)
- **Pool Recycle:** 3600 seconds (1 hour - prevent long-lived connection issues)
- **Rationale:** Conservative sizing for personal project, can scale up if needed

### Performance Configuration (postgresql.conf)
```ini
# Mixed OLTP + OLAP workload tuning
shared_buffers = 256MB              # 25% of RAM for 1GB system
effective_cache_size = 768MB        # 75% of RAM
maintenance_work_mem = 64MB         # For VACUUM, CREATE INDEX
work_mem = 16MB                     # Per-query sort/hash memory

# Concurrency
max_connections = 50                # Conservative limit
max_worker_processes = 4            # Parallel query workers

# Write-Ahead Log (WAL)
wal_level = replica                 # Enable replication (future-proof)
max_wal_size = 1GB                  # WAL checkpoint tuning
min_wal_size = 80MB

# Query Planning
random_page_cost = 1.1              # SSD optimization
effective_io_concurrency = 200      # SSD concurrent I/O

# Monitoring
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all      # Track all queries
log_min_duration_statement = 1000   # Log queries >1 second
```

### SQL Dialect Mapping (DuckDB → PostgreSQL)

| Feature | DuckDB | PostgreSQL | Notes |
|---------|--------|------------|-------|
| Timestamps | `TIMESTAMP` | `TIMESTAMP WITH TIME ZONE` | Always use TZ-aware |
| JSON | `JSON` | `JSONB` | Binary format, faster queries |
| Auto-increment | Implicit | `SERIAL` or `IDENTITY` | Explicit declaration |
| JSON extract | `json_extract(col, '$.key')` | `col->>'key'` | PostgreSQL operator syntax |
| Current time | `CURRENT_TIMESTAMP` | `NOW()` | Both work in PG |
| Limit | `LIMIT n` | `LIMIT n` | Compatible |
| Boolean | `BOOLEAN` | `BOOLEAN` | Compatible |
| Arrays | `INTEGER[]` | `INTEGER[]` | Compatible |

### Dependencies
**Add to `requirements.txt`:**
```txt
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
```

**Remove from `requirements.txt`:**
```txt
duckdb
```

### Security Considerations
- **Authentication:** Use password authentication for PostgreSQL user (not trust for production)
- **Network:** Bind PostgreSQL to localhost only (`listen_addresses = 'localhost'`)
- **Credentials:** Store PostgreSQL password in environment variable, not code
- **Permissions:** Grant minimal privileges to `portfolio_ai_user` (no SUPERUSER, CREATEROLE)
- **Backups:** Encrypt backup files if stored off-server

---

## Success Metrics

### Performance Metrics (Measured via benchmarks)
- **SM-1:** Celery worker concurrency increases from 1 → 4 workers without lock errors
- **SM-2:** Watchlist refresh latency remains <2 seconds (no regression)
- **SM-3:** API read latency (p95) <100ms for GET /api/watchlist
- **SM-4:** Bulk insert throughput >1000 rows/second for `day_bars`
- **SM-5:** No database lock wait events under load testing (4 workers + 20 API clients)

### Reliability Metrics
- **SM-6:** Test suite maintains 100% pass rate post-migration
- **SM-7:** Zero data integrity violations (foreign key constraints enforced)
- **SM-8:** Zero connection pool exhaustion events during 24-hour soak test
- **SM-9:** Backup/restore completes successfully in <5 minutes

### Operational Metrics
- **SM-10:** PostgreSQL service uptime >99.9% (minimal downtime during migration)
- **SM-11:** Developer can set up PostgreSQL in <10 minutes using setup script
- **SM-12:** Clear operational documentation reduces troubleshooting time by 50%

### Developer Experience Metrics
- **SM-13:** Zero "forgetting Docker commands" incidents (native PostgreSQL is simpler)
- **SM-14:** Standard PostgreSQL tools work (psql, pg_dump, pgAdmin)
- **SM-15:** Migration completed within 5 days (goal timeline)

---

## Open Questions

**OQ-1:** Should we implement automated daily backups via cron job?
- **Recommendation:** Yes - Add cron job for daily `pg_dump` to `/backup/` directory
- **Who decides:** Developer (user)
- **Impact:** Data safety, disaster recovery

**OQ-2:** Do we need query performance logging (`pg_stat_statements`) enabled by default?
- **Recommendation:** Yes - Essential for troubleshooting slow queries
- **Trade-off:** Minimal performance overhead (<1%)
- **Who decides:** Developer

**OQ-3:** Should we add a migration validation test suite before cutover?
- **Recommendation:** Yes - Automated comparison of DuckDB vs PostgreSQL query results
- **Scope:** Sample 100 queries, compare results, flag differences
- **Who decides:** Developer (good practice)

**OQ-4:** What should be the backup retention policy?
- **Recommendation:** Keep 7 daily backups, 4 weekly backups, 3 monthly backups
- **Storage:** ~100MB per backup × 14 backups = ~1.4GB total
- **Who decides:** Developer

**OQ-5:** Should we implement a migration dry-run mode?
- **Recommendation:** Yes - Add `--dry-run` flag to migration scripts to preview changes without committing
- **Benefit:** Safety, allows verification before actual migration
- **Who decides:** Developer

---

## Implementation Plan Overview

### Timeline: 5 Days (Critical Priority - Immediate Start)

**Day 1: PostgreSQL Setup & Schema Migration**
- Install PostgreSQL 16
- Create setup scripts
- Convert schema to PostgreSQL DDL
- Add indexes, constraints, foreign keys
- Verify schema creation

**Day 2: Data Migration**
- Export configuration data from DuckDB
- Import into PostgreSQL
- Validate data integrity
- Create rollback backup

**Day 3: Application Code Updates**
- Update connection management (SQLAlchemy)
- Convert SQL queries for PostgreSQL
- Configure Celery with PostgreSQL broker/backend
- Increase Celery concurrency to 4 workers
- Run test suite, fix failures

**Day 4: Testing & Validation**
- Execute comprehensive test suite
- Run performance benchmarks
- Load testing (concurrent workers + API clients)
- Manual smoke testing
- Document results

**Day 5: Documentation & Deployment**
- Update all core documentation
- Create operational runbooks
- Write utility scripts
- Final verification checklist
- Go-live decision

---

## Appendix A: Migration Scripts Reference

### Scripts to Create
1. `scripts/setup-postgres.sh` - PostgreSQL installation and database setup
2. `scripts/migrate-schema-to-postgres.py` - DDL conversion and schema creation
3. `scripts/export-duckdb-data.py` - Export configuration data from DuckDB
4. `scripts/import-data-to-postgres.py` - Import data into PostgreSQL
5. `scripts/postgres-backup.sh` - Automated backup utility
6. `scripts/postgres-restore.sh` - Interactive restore utility
7. `scripts/postgres-vacuum.sh` - Maintenance utility
8. `scripts/postgres-status.sh` - Connection pool and performance monitoring
9. `scripts/validate-migration.py` - Post-migration validation checks

### Configuration Files to Update
1. `backend/app/storage/connection.py` - Connection management
2. `backend/app/storage/queries.py` - SQL query dialect updates
3. `backend/app/constants.py` - Database URL configuration
4. `backend/app/celery_app.py` - Celery broker/backend config
5. `backend/requirements.txt` - Dependencies
6. `backend/.env.example` - Environment variables
7. `scripts/start.sh` - Service startup
8. `scripts/restart.sh` - Service restart
9. `scripts/shutdown.sh` - Service shutdown
10. `scripts/start-celery.sh` - Celery worker concurrency

### Documentation Files to Update
1. `docs/core/SETUP.md` - PostgreSQL setup instructions
2. `docs/core/ARCHITECTURE.md` - Database architecture
3. `docs/core/DEVELOPMENT.md` - Development workflows
4. `docs/core/OPERATIONS.md` - Operational runbooks
5. `docs/core/REFACTOR_STATUS.md` - Migration status
6. `CLAUDE.md` - Tech stack, quick start commands
7. `docs/postgresql-dialect-reference.md` (new) - SQL dialect guide
8. `docs/postgresql-migration-rollback.md` (new) - Rollback procedures

---

## Appendix B: PostgreSQL Quick Reference

### Common Commands
```bash
# Service management
sudo systemctl start postgresql
sudo systemctl stop postgresql
sudo systemctl restart postgresql
sudo systemctl status postgresql
pg_isready                          # Check if server is running

# Database operations
psql portfolio_ai                    # Connect to database
psql -U portfolio_ai_user -d portfolio_ai  # Connect as specific user

# Backup and restore
pg_dump portfolio_ai > backup.sql    # Backup
psql portfolio_ai < backup.sql       # Restore
pg_dump -Fc portfolio_ai > backup.dump  # Compressed backup
pg_restore -d portfolio_ai backup.dump  # Restore compressed

# Monitoring
psql portfolio_ai -c "SELECT count(*) FROM pg_stat_activity"  # Active connections
psql portfolio_ai -c "SELECT * FROM pg_stat_activity WHERE state = 'active'"  # Active queries
```

### Useful SQL Queries (Inside psql)
```sql
-- List all tables
\dt

-- Describe table schema
\d table_name

-- Show indexes
\di

-- Show table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE schemaname = 'public';

-- Show active queries
SELECT pid, usename, application_name, state, query
FROM pg_stat_activity WHERE state = 'active';

-- Kill long-running query
SELECT pg_terminate_backend(pid) WHERE pid = 12345;

-- Connection pool status
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
```

---

## Appendix C: Performance Benchmarking Scripts

### Benchmark 1: Concurrent Writes
```python
# scripts/benchmark-concurrent-writes.py
import concurrent.futures
import time
from app.storage.facade import get_storage

def write_task(task_id):
    storage = get_storage()
    start = time.time()
    # Simulate Celery task writing to database
    with storage.connection_mgr.connection() as conn:
        conn.execute("""
            INSERT INTO price_cache (ticker, price, fetched_at, source)
            VALUES (?, ?, NOW(), ?)
        """, (f"TEST{task_id}", 100.0, "benchmark"))
    return time.time() - start

# Run 4 concurrent tasks (simulating 4 Celery workers)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(write_task, i) for i in range(100)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

print(f"Average latency: {sum(results)/len(results):.3f}s")
print(f"Total time: {max(results):.3f}s")
print(f"Errors: {sum(1 for r in results if r is None)}")
```

### Benchmark 2: Watchlist Refresh
```python
# scripts/benchmark-watchlist-refresh.py
import time
from app.tasks.agent_tasks import refresh_watchlist_scores

start = time.time()
result = refresh_watchlist_scores.apply(args=["default"]).get()
elapsed = time.time() - start

print(f"Watchlist refresh: {elapsed:.2f}s")
print(f"Tickers processed: {result['processed']}")
print(f"Target: <2 seconds - {'PASS' if elapsed < 2 else 'FAIL'}")
```

---

## Appendix D: Foreign Key Relationships

```
accounts
  ↓ (CASCADE DELETE)
  ├── portfolios
  │     ↓ (CASCADE DELETE)
  │     └── portfolio_holdings
  ├── watchlist_items
  │     ↓ (CASCADE DELETE)
  │     └── watchlist_snapshots
  ├── agent_runs
  │     ↓ (CASCADE DELETE)
  │     └── agent_messages
  └── user_preferences

api_credentials (standalone, no foreign keys)
source_performance (standalone, no foreign keys)
price_cache (standalone, no foreign keys - ticker is not FK)
day_bars (standalone, ticker is not FK)
technical_indicators (standalone, ticker is not FK)
news_cache (standalone, ticker is not FK)
reference_cache (standalone, ticker is not FK)
schema_migrations (standalone, metadata)
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-29 | AI Assistant | Initial PRD creation based on user requirements |

---

## Approval & Sign-Off

- [ ] **Developer Review:** PRD reviewed and approved
- [ ] **Architecture Review:** Database architecture validated
- [ ] **Security Review:** Security considerations addressed
- [ ] **Ready for Implementation:** All questions answered, risks mitigated

---

**End of PRD 0015: PostgreSQL Migration**
