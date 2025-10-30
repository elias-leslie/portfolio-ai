# Task List: PostgreSQL Migration - Production-Ready Database

**PRD**: `0015-prd-postgresql-migration.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: High (5 days of focused work)
**Last Updated**: 2025-10-29

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
1. **CRITICAL FIRST STEP:** Complete Task 0.0 (all `sudo` operations) so you can approve them upfront
2. After Task 0.0 approval, tasks 1.0-7.0 can run autonomously
3. Follow checklist sequentially
4. Update this summary as work progresses

**EFFORT TO COMPLETE:** High (5 days)

---

## Relevant Files

### Files to Create (9 new files)

- `scripts/setup-postgres.sh` (~150 lines) - PostgreSQL installation and database setup script
- `scripts/migrate-schema-to-postgres.py` (~400 lines) - DDL conversion and schema creation
- `scripts/export-duckdb-data.py` (~200 lines) - Export configuration data from DuckDB
- `scripts/import-data-to-postgres.py` (~250 lines) - Import data into PostgreSQL
- `scripts/postgres-backup.sh` (~80 lines) - Automated backup utility
- `scripts/postgres-restore.sh` (~100 lines) - Interactive restore utility
- `scripts/postgres-vacuum.sh` (~60 lines) - Maintenance utility
- `scripts/postgres-status.sh` (~120 lines) - Connection pool and performance monitoring
- `scripts/benchmark-concurrent-writes.py` (~150 lines) - Performance benchmark for concurrent operations
- `scripts/benchmark-watchlist-refresh.py` (~80 lines) - Watchlist refresh performance test
- `docs/postgresql-dialect-reference.md` (~300 lines) - SQL dialect guide for DuckDB → PostgreSQL
- `docs/postgresql-migration-rollback.md` (~200 lines) - Rollback procedures

### Files to Update (15 files)

- `backend/app/storage/connection.py` - Replace DuckDB connection with SQLAlchemy PostgreSQL engine
- `backend/app/storage/queries.py` - Update SQL queries for PostgreSQL dialect (timestamps, JSON, auto-increment)
- `backend/app/storage/schema.py` - Convert schema DDL to PostgreSQL syntax
- `backend/app/constants.py` - Change `DEFAULT_DUCKDB_PATH` → `DATABASE_URL`
- `backend/app/celery_app.py` - Configure Celery with PostgreSQL broker/backend (remove Redis)
- `backend/requirements.txt` - Add psycopg2-binary, sqlalchemy; remove duckdb
- `backend/.env.example` - Add DATABASE_URL environment variable
- `scripts/start.sh` - Add PostgreSQL status check, remove Redis check
- `scripts/restart.sh` - Update to check PostgreSQL instead of Redis
- `scripts/shutdown.sh` - Remove Redis shutdown
- `scripts/start-celery.sh` - Update concurrency from 1 → 4
- `docs/core/SETUP.md` - Add PostgreSQL setup instructions
- `docs/core/ARCHITECTURE.md` - Replace DuckDB with PostgreSQL architecture
- `docs/core/DEVELOPMENT.md` - Update command reference (PostgreSQL commands)
- `docs/core/OPERATIONS.md` - Add PostgreSQL operational runbooks
- `CLAUDE.md` - Update tech stack and quick start commands

### Notes

- PostgreSQL 16 will be installed natively (no Docker)
- Connection pooling: SQLAlchemy QueuePool (size=20, max_overflow=10)
- Celery will use PostgreSQL for both broker and result backend
- Data migration: Configuration data only (API keys, preferences, accounts)
- Transactional data will be flushed (price_cache, day_bars, etc.)
- DuckDB backup created before migration for rollback
- Run `pytest tests/ -v --cov=app` to verify 100% test pass rate
- Run benchmarks to verify 4x performance improvement
- Use `psql portfolio_ai` to connect directly to database

---

## Tasks

- [ ] **0.0 PostgreSQL Installation & System Setup (REQUIRES SUDO - DO FIRST)** [EFFORT: Low, 30 minutes]
  - [ ] 0.1 **[SUDO REQUIRED]** Install PostgreSQL 16 and dependencies
    - [ ] 0.1.1 Run: `sudo apt update`
    - [ ] 0.1.2 Run: `sudo apt install -y postgresql-16 postgresql-contrib-16 postgresql-client-16`
    - [ ] 0.1.3 Verify installation: `psql --version` (should show 16.x)
  - [ ] 0.2 **[SUDO REQUIRED]** Configure PostgreSQL service
    - [ ] 0.2.1 Run: `sudo systemctl enable postgresql` (auto-start on boot)
    - [ ] 0.2.2 Run: `sudo systemctl start postgresql` (start now)
    - [ ] 0.2.3 Verify running: `sudo systemctl status postgresql | grep "active (running)"`
    - [ ] 0.2.4 Run: `pg_isready` (should return "accepting connections")
  - [ ] 0.3 **[SUDO REQUIRED]** Create database and user
    - [ ] 0.3.1 Run: `sudo -u postgres psql -c "CREATE DATABASE portfolio_ai;"`
    - [ ] 0.3.2 Run: `sudo -u postgres psql -c "CREATE USER portfolio_ai_user WITH PASSWORD 'REDACTED_PASSWORD';"`
    - [ ] 0.3.3 Run: `sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE portfolio_ai TO portfolio_ai_user;"`
    - [ ] 0.3.4 Run: `sudo -u postgres psql -d portfolio_ai -c "GRANT ALL ON SCHEMA public TO portfolio_ai_user;"`
    - [ ] 0.3.5 Verify connection: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT version();"` (may need to configure pg_hba.conf for local trust)
  - [ ] 0.4 **[SUDO REQUIRED]** Configure pg_hba.conf for local development
    - [ ] 0.4.1 Run: `sudo nano /etc/postgresql/16/main/pg_hba.conf` (or locate correct path)
    - [ ] 0.4.2 Add line: `local   portfolio_ai    portfolio_ai_user                            trust` (before other rules)
    - [ ] 0.4.3 Add line: `host    portfolio_ai    portfolio_ai_user   127.0.0.1/32            trust`
    - [ ] 0.4.4 Run: `sudo systemctl reload postgresql` (apply config changes)
    - [ ] 0.4.5 Verify: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT 1;"` (should work without password prompt)
  - [ ] 0.5 **[SUDO REQUIRED]** Enable pg_stat_statements extension for monitoring
    - [ ] 0.5.1 Run: `sudo nano /etc/postgresql/16/main/postgresql.conf`
    - [ ] 0.5.2 Add/uncomment line: `shared_preload_libraries = 'pg_stat_statements'`
    - [ ] 0.5.3 Add line: `pg_stat_statements.track = all`
    - [ ] 0.5.4 Run: `sudo systemctl restart postgresql`
    - [ ] 0.5.5 Run: `psql -U portfolio_ai_user -d portfolio_ai -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"`
  - [ ] 0.6 **[NO SUDO]** Backup existing DuckDB database
    - [ ] 0.6.1 Run: `cp ~/portfolio-ai/backend/data/portfolio.duckdb ~/portfolio-ai/backend/data/portfolio.duckdb.backup-$(date +%Y%m%d)`
    - [ ] 0.6.2 Verify backup exists: `ls -lh ~/portfolio-ai/backend/data/portfolio.duckdb.backup-*`
    - [ ] 0.6.3 Document backup location in migration notes
  - [ ] 0.7 **[NO SUDO]** Add DATABASE_URL to environment
    - [ ] 0.7.1 Create `~/portfolio-ai/backend/.env` if it doesn't exist
    - [ ] 0.7.2 Add line: `DATABASE_URL=postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai`
    - [ ] 0.7.3 Update `~/portfolio-ai/backend/.env.example` with DATABASE_URL template
    - [ ] 0.7.4 Verify: `cat ~/portfolio-ai/backend/.env | grep DATABASE_URL`

- [ ] **1.0 Schema Translation & Migration Scripts** [EFFORT: High, 1 day]
  - [ ] 1.1 Create PostgreSQL schema DDL conversion script
    - [ ] 1.1.1 Create `scripts/migrate-schema-to-postgres.py`
    - [ ] 1.1.2 Add imports: `psycopg2`, `os`, `sys`, `pathlib`, `logging`
    - [ ] 1.1.3 Add function `connect_to_postgres()` - Read DATABASE_URL from env, return connection
    - [ ] 1.1.4 Add function `translate_duckdb_to_postgres_type(duckdb_type: str) -> str`
      - Map: `TIMESTAMP` → `TIMESTAMP WITH TIME ZONE`
      - Map: `JSON` → `JSONB`
      - Map: `INTEGER` (with auto-increment) → `SERIAL`
      - Map: `HUGEINT` → `BIGINT`
      - Map: `BOOLEAN`, `TEXT`, `DOUBLE`, `REAL` → same
    - [ ] 1.1.5 Add function `create_config_tables(conn)` - Translate 6 config tables from schema.py
      - `source_registry`, `source_credentials`, `endpoint_catalog`
      - `portfolio_accounts`, `portfolio_positions`, `user_preferences`
      - Convert foreign key syntax: DuckDB `FOREIGN KEY (...)` → PostgreSQL same (compatible)
    - [ ] 1.1.6 Add function `create_timeseries_tables(conn)` - Translate 7 timeseries tables
      - `price_cache`, `day_bars`, `technical_indicators`, `news_cache`
      - `reference_cache`, `source_performance`, `agent_runs`, `agent_messages`, `agent_costs`
    - [ ] 1.1.7 Add function `create_watchlist_tables(conn)` - Translate 2 watchlist tables
      - `watchlist_items`, `watchlist_snapshots`
    - [ ] 1.1.8 Add function `create_metadata_tables(conn)` - Translate metadata tables
      - `schema_migrations`, `table_registry`
    - [ ] 1.1.9 Add function `create_indexes(conn)` - Create performance indexes
      - `price_cache(ticker, fetched_at DESC)`
      - `day_bars(ticker, date DESC)`
      - `technical_indicators(ticker, calculated_at DESC)`
      - `watchlist_items(account_id, added_at DESC)`
      - `watchlist_snapshots(item_id, snapshot_at DESC)`
      - `news_cache(ticker, published_at DESC)`
      - `agent_runs(account_id, started_at DESC)`
    - [ ] 1.1.10 Add function `create_foreign_keys(conn)` - Add foreign key constraints
      - `portfolio_positions.account_id` → `portfolio_accounts.id` (CASCADE DELETE)
      - `watchlist_items.account_id` → `portfolio_accounts.id` (CASCADE DELETE)
      - `watchlist_snapshots.item_id` → `watchlist_items.item_id` (CASCADE DELETE)
      - `agent_messages.run_id` → `agent_runs.run_id` (CASCADE DELETE)
      - `endpoint_catalog.source_id` → `source_registry.source_id`
    - [ ] 1.1.11 Add `main()` function - Execute schema creation in transaction
    - [ ] 1.1.12 Add error handling and rollback on failure
    - [ ] 1.1.13 Add logging for each table created
    - [ ] 1.1.14 Test: `python scripts/migrate-schema-to-postgres.py` (dry-run mode first)
  - [ ] 1.2 Create DuckDB data export script
    - [ ] 1.2.1 Create `scripts/export-duckdb-data.py`
    - [ ] 1.2.2 Add imports: `duckdb`, `json`, `pathlib`, `logging`
    - [ ] 1.2.3 Add function `connect_to_duckdb()` - Connect to ~/portfolio-ai/backend/data/portfolio.duckdb
    - [ ] 1.2.4 Add function `export_table_to_json(conn, table_name: str, output_dir: Path)`
      - Query: `SELECT * FROM {table_name}`
      - Export as JSON lines format (one JSON object per line)
      - Save to: `output_dir/{table_name}.jsonl`
    - [ ] 1.2.5 Add `TABLES_TO_EXPORT` constant - Configuration tables only:
      - `source_credentials` (API keys)
      - `user_preferences` (user settings)
      - `portfolio_accounts` (accounts)
      - `source_performance` (source metrics)
      - `schema_migrations` (migration history)
    - [ ] 1.2.6 Add `main()` function - Export each table, log row counts
    - [ ] 1.2.7 Create output directory: `~/portfolio-ai/backend/data/migration_export/`
    - [ ] 1.2.8 Test: `python scripts/export-duckdb-data.py`
    - [ ] 1.2.9 Verify: Check `ls ~/portfolio-ai/backend/data/migration_export/` for JSONL files
  - [ ] 1.3 Create PostgreSQL data import script
    - [ ] 1.3.1 Create `scripts/import-data-to-postgres.py`
    - [ ] 1.3.2 Add imports: `psycopg2`, `json`, `pathlib`, `logging`
    - [ ] 1.3.3 Add function `connect_to_postgres()` - Read DATABASE_URL from env
    - [ ] 1.3.4 Add function `import_table_from_json(conn, table_name: str, input_file: Path)`
      - Read JSONL file line by line
      - Build parameterized INSERT query: `INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING`
      - Execute for each row, commit in batches of 1000
      - Log: rows inserted, skipped (conflicts)
    - [ ] 1.3.5 Add `IMPORT_ORDER` constant - Import in dependency order:
      - 1. `portfolio_accounts` (no dependencies)
      - 2. `source_performance` (no dependencies)
      - 3. `schema_migrations` (no dependencies)
      - 4. `source_credentials` (no dependencies, but references sources)
      - 5. `user_preferences` (references accounts)
    - [ ] 1.3.6 Add `main()` function - Import each table in order
    - [ ] 1.3.7 Add validation: Check foreign key constraints pass after import
    - [ ] 1.3.8 Test: `python scripts/import-data-to-postgres.py`
    - [ ] 1.3.9 Verify: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT count(*) FROM source_credentials;"`

- [ ] **2.0 Application Code Migration** [EFFORT: High, 1 day]
  - [ ] 2.1 Update dependencies
    - [ ] 2.1.1 Edit `backend/requirements.txt`
    - [ ] 2.1.2 Add: `sqlalchemy==2.0.23`
    - [ ] 2.1.3 Add: `psycopg2-binary==2.9.9`
    - [ ] 2.1.4 Remove line: `duckdb==1.4.1`
    - [ ] 2.1.5 Keep: `redis==7.0.1` (may uninstall later, but keep for now for safety)
    - [ ] 2.1.6 Run: `cd ~/portfolio-ai/backend && source .venv/bin/activate && pip install -r requirements.txt`
    - [ ] 2.1.7 Verify: `pip list | grep -E "(sqlalchemy|psycopg2)"` (should show installed)
    - [ ] 2.1.8 Verify: `pip list | grep duckdb` (should show nothing)
  - [ ] 2.2 Update connection management (connection.py)
    - [ ] 2.2.1 Open `backend/app/storage/connection.py`
    - [ ] 2.2.2 Replace imports: Remove `import duckdb`, add `from sqlalchemy import create_engine, pool`
    - [ ] 2.2.3 Update `ConnectionManager.__init__()`
      - Remove: `self.db_path` logic
      - Add: `self.database_url = os.getenv("DATABASE_URL", "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai")`
      - Add: Create SQLAlchemy engine:
        ```python
        self.engine = create_engine(
            self.database_url,
            poolclass=pool.QueuePool,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        ```
    - [ ] 2.2.4 Update `connection()` context manager
      - Replace: `conn = duckdb.connect(str(self.db_path))` with `conn = self.engine.raw_connection()`
      - Remove: DuckDB-specific config (SET commands)
      - Keep: try/finally block with `conn.close()`
    - [ ] 2.2.5 Update return type hint: `Iterator[duckdb.DuckDBPyConnection]` → `Iterator[Any]` (or `psycopg2.extensions.connection`)
    - [ ] 2.2.6 Update docstring: Change references from DuckDB to PostgreSQL
    - [ ] 2.2.7 Test: Run `cd ~/portfolio-ai/backend && python -c "from app.storage.connection import get_connection_manager; mgr = get_connection_manager(); print('Connection manager created')"`
  - [ ] 2.3 Update constants.py for DATABASE_URL
    - [ ] 2.3.1 Open `backend/app/constants.py`
    - [ ] 2.3.2 Remove: `DEFAULT_DUCKDB_PATH` constant
    - [ ] 2.3.3 Add: `DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai")`
    - [ ] 2.3.4 Update any code that referenced `DEFAULT_DUCKDB_PATH` to use `DATABASE_URL`
  - [ ] 2.4 Update SQL queries in queries.py for PostgreSQL dialect
    - [ ] 2.4.1 Open `backend/app/storage/queries.py`
    - [ ] 2.4.2 Find all `CURRENT_TIMESTAMP` → Replace with `NOW()` (or keep, both work in PostgreSQL)
    - [ ] 2.4.3 Find JSON operations: `json_extract(col, '$.key')` → Replace with `col->>'key'`
    - [ ] 2.4.4 Find auto-increment columns: Add `RETURNING id` clause to INSERT statements if needed
    - [ ] 2.4.5 Review timestamp columns: Ensure `TIMESTAMP WITH TIME ZONE` is used
    - [ ] 2.4.6 Review parameterized placeholders: DuckDB uses `?`, PostgreSQL uses `%s` or `%(name)s`
      - **CRITICAL:** Check if queries use `?` placeholders - may need to change to `%s` for psycopg2
      - SQLAlchemy raw connections use `%s` format
    - [ ] 2.4.7 Test each modified query individually (see Task 3.0 for testing)
  - [ ] 2.5 Update schema.py DDL statements
    - [ ] 2.5.1 Open `backend/app/storage/schema.py`
    - [ ] 2.5.2 **Option A:** Replace all DDL with references to migration script (recommended)
      - Update `ensure_schema()` to check if tables exist, if not, raise error directing to migration script
    - [ ] 2.5.3 **Option B:** Inline update DDL to PostgreSQL syntax (not recommended, redundant with migration script)
    - [ ] 2.5.4 Update imports: Remove `import duckdb`, add SQLAlchemy imports if needed
    - [ ] 2.5.5 Update `_create_*_tables()` methods: Change syntax to PostgreSQL
      - `TIMESTAMP` → `TIMESTAMP WITH TIME ZONE`
      - `JSON` → `JSONB`
      - Auto-increment → `SERIAL` or `IDENTITY`
    - [ ] 2.5.6 Remove DuckDB-specific pragmas or settings
  - [ ] 2.6 Update Celery configuration (celery_app.py)
    - [ ] 2.6.1 Open `backend/app/celery_app.py`
    - [ ] 2.6.2 Remove: `REDIS_URL` constant
    - [ ] 2.6.3 Add: `DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://...")`
    - [ ] 2.6.4 Update `celery_app` creation:
      ```python
      celery_app = Celery(
          "portfolio-ai",
          broker=f"db+{DATABASE_URL}",      # PostgreSQL broker
          backend=f"db+{DATABASE_URL}",     # PostgreSQL result backend
          broker_connection_retry_on_startup=True,
      )
      ```
    - [ ] 2.6.5 Update `celery_app.conf.update()`: Keep existing config, verify compatibility with PostgreSQL backend
    - [ ] 2.6.6 Test: `cd ~/portfolio-ai/backend && celery -A app.celery_app inspect ping` (after migration)
  - [ ] 2.7 Update .env.example
    - [ ] 2.7.1 Open `backend/.env.example`
    - [ ] 2.7.2 Add: `DATABASE_URL=postgresql://portfolio_ai_user:YOUR_PASSWORD@localhost:5432/portfolio_ai`
    - [ ] 2.7.3 Remove or comment out: `REDIS_URL` (optional, may keep for future)
    - [ ] 2.7.4 Add comment: `# PostgreSQL connection string for application and Celery`

- [ ] **3.0 Data Migration & Validation** [EFFORT: Medium, half day]
  - [ ] 3.1 Execute schema migration
    - [ ] 3.1.1 Stop all services: `cd ~/portfolio-ai && ./scripts/shutdown.sh`
    - [ ] 3.1.2 Verify PostgreSQL is running: `pg_isready`
    - [ ] 3.1.3 Run schema migration: `cd ~/portfolio-ai/backend && python ../scripts/migrate-schema-to-postgres.py`
    - [ ] 3.1.4 Check for errors in output, verify "Schema migration completed successfully"
    - [ ] 3.1.5 Verify tables exist: `psql -U portfolio_ai_user -d portfolio_ai -c "\dt"`
    - [ ] 3.1.6 Count tables: Should see 17+ tables listed
  - [ ] 3.2 Export data from DuckDB
    - [ ] 3.2.1 Run export script: `cd ~/portfolio-ai/backend && python ../scripts/export-duckdb-data.py`
    - [ ] 3.2.2 Verify export files created: `ls -lh ~/portfolio-ai/backend/data/migration_export/`
    - [ ] 3.2.3 Check file sizes (should be non-zero for tables with data)
    - [ ] 3.2.4 Sample check: `head -5 ~/portfolio-ai/backend/data/migration_export/source_credentials.jsonl`
  - [ ] 3.3 Import data into PostgreSQL
    - [ ] 3.3.1 Run import script: `cd ~/portfolio-ai/backend && python ../scripts/import-data-to-postgres.py`
    - [ ] 3.3.2 Check for errors in output, verify row counts imported
    - [ ] 3.3.3 Verify data: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT count(*) FROM source_credentials;"`
    - [ ] 3.3.4 Verify data: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM user_preferences LIMIT 1;"`
    - [ ] 3.3.5 Verify data: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM portfolio_accounts;"`
  - [ ] 3.4 Validate foreign key constraints
    - [ ] 3.4.1 Test constraint enforcement: Attempt to insert orphaned record (should fail)
      - `psql -U portfolio_ai_user -d portfolio_ai -c "INSERT INTO portfolio_positions (id, account_id, symbol, shares, cost_basis, position_type) VALUES ('test', 'nonexistent', 'AAPL', 10, 100, 'long');"`
      - Should see: `ERROR:  insert or update on table "portfolio_positions" violates foreign key constraint`
    - [ ] 3.4.2 Test CASCADE DELETE:
      - Create test account: `INSERT INTO portfolio_accounts (id, name, account_type) VALUES ('test_acct', 'Test', 'paper');`
      - Create test position: `INSERT INTO portfolio_positions (id, account_id, symbol, shares, cost_basis, position_type) VALUES ('test_pos', 'test_acct', 'AAPL', 10, 100, 'long');`
      - Delete account: `DELETE FROM portfolio_accounts WHERE id = 'test_acct';`
      - Verify position deleted: `SELECT count(*) FROM portfolio_positions WHERE id = 'test_pos';` (should be 0)
  - [ ] 3.5 Test connection pooling
    - [ ] 3.5.1 Create test script: `scripts/test-connection-pool.py`
    - [ ] 3.5.2 Open 25 connections simultaneously (exceeds pool_size=20, tests overflow)
    - [ ] 3.5.3 Execute simple query on each connection
    - [ ] 3.5.4 Verify all succeed without "too many connections" error
    - [ ] 3.5.5 Monitor: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'portfolio_ai';"`
    - [ ] 3.5.6 Verify: Connection count stays at or below 30 (pool_size + max_overflow)
  - [ ] 3.6 Create Celery database tables
    - [ ] 3.6.1 Start Celery worker: `cd ~/portfolio-ai/backend && celery -A app.celery_app worker --loglevel=info`
    - [ ] 3.6.2 Check logs for "Created Celery tables" or similar message
    - [ ] 3.6.3 Verify tables exist: `psql -U portfolio_ai_user -d portfolio_ai -c "\dt celery*"`
    - [ ] 3.6.4 Should see: `celery_taskmeta`, `celery_tasksetmeta` tables
    - [ ] 3.6.5 Stop Celery worker: Ctrl+C

- [ ] **4.0 Testing & Performance Validation** [EFFORT: High, 1 day]
  - [ ] 4.1 Run existing test suite
    - [ ] 4.1.1 Activate venv: `cd ~/portfolio-ai/backend && source .venv/bin/activate`
    - [ ] 4.1.2 Run all tests: `pytest tests/ -v`
    - [ ] 4.1.3 Target: 100% pass rate (no failures)
    - [ ] 4.1.4 If failures, debug and fix:
      - Check SQL dialect differences
      - Check parameterized query placeholders (`?` vs `%s`)
      - Check timestamp timezone handling
      - Check JSON operations
    - [ ] 4.1.5 Run with coverage: `pytest tests/ --cov=app --cov-report=term-missing`
    - [ ] 4.1.6 Target: Maintain 80%+ coverage (current baseline)
  - [ ] 4.2 Create concurrent write benchmark
    - [ ] 4.2.1 Create `scripts/benchmark-concurrent-writes.py`
    - [ ] 4.2.2 Import: `concurrent.futures`, `time`, `app.storage.facade`
    - [ ] 4.2.3 Define function `write_task(task_id)`:
      - Connect to database
      - Insert row into `price_cache` table
      - Measure latency
      - Return latency
    - [ ] 4.2.4 Run 100 write tasks with 4 concurrent workers (ThreadPoolExecutor)
    - [ ] 4.2.5 Measure: Average latency, total time, error count
    - [ ] 4.2.6 Execute: `cd ~/portfolio-ai/backend && python ../scripts/benchmark-concurrent-writes.py`
    - [ ] 4.2.7 Target: Zero errors, average latency <50ms
  - [ ] 4.3 Create watchlist refresh benchmark
    - [ ] 4.3.1 Create `scripts/benchmark-watchlist-refresh.py`
    - [ ] 4.3.2 Import: `time`, `app.tasks.agent_tasks`
    - [ ] 4.3.3 Add 5 test tickers to watchlist (or use existing)
    - [ ] 4.3.4 Trigger: `refresh_watchlist_scores.apply(args=["default"]).get()`
    - [ ] 4.3.5 Measure: End-to-end latency
    - [ ] 4.3.6 Execute: `cd ~/portfolio-ai/backend && python ../scripts/benchmark-watchlist-refresh.py`
    - [ ] 4.3.7 Target: <2 seconds (baseline: ~1.2s, should remain similar)
  - [ ] 4.4 Load testing with concurrent workers and API clients
    - [ ] 4.4.1 Start services: `cd ~/portfolio-ai && ./scripts/start.sh`
    - [ ] 4.4.2 Verify 4 Celery workers started: `ps aux | grep celery | grep worker`
    - [ ] 4.4.3 Queue 20 watchlist refresh tasks simultaneously
    - [ ] 4.4.4 Send 50 GET requests to `/api/watchlist?account_id=default` (concurrent)
    - [ ] 4.4.5 Monitor: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT count(*), state FROM pg_stat_activity WHERE datname = 'portfolio_ai' GROUP BY state;"`
    - [ ] 4.4.6 Check for lock wait events: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM pg_locks WHERE NOT granted;"`
    - [ ] 4.4.7 Target: Zero lock wait events, all tasks complete successfully
  - [ ] 4.5 Verify Celery task execution with PostgreSQL backend
    - [ ] 4.5.1 Queue 10 tasks: `refresh_watchlist_scores`, `ingest_historical_ohlcv`, `update_technical_indicators`
    - [ ] 4.5.2 Monitor Celery logs: `tail -f /tmp/portfolio-ai-celery-worker.log`
    - [ ] 4.5.3 Verify all tasks complete (check logs for "succeeded")
    - [ ] 4.5.4 Check task results: `psql -U portfolio_ai_user -d portfolio_ai -c "SELECT count(*) FROM celery_taskmeta;"`
    - [ ] 4.5.5 Target: All 30 tasks completed, results stored in PostgreSQL
  - [ ] 4.6 Manual end-to-end smoke testing
    - [ ] 4.6.1 **Watchlist Flow:**
      - Open http://192.168.8.233:3000/watchlist
      - Add 5 tickers (AAPL, TSLA, NVDA, MSFT, GOOGL)
      - Trigger manual refresh
      - Verify scores appear (non-zero)
      - Expand row, verify data shown
      - Edit notes, save, verify persistence
      - Delete one ticker, verify removed
    - [ ] 4.6.2 **Portfolio Flow:**
      - Navigate to portfolio page
      - Create new portfolio
      - Add holdings
      - View analytics
      - Delete portfolio, verify cleanup
    - [ ] 4.6.3 **Preferences Flow:**
      - Navigate to settings
      - Update watchlist preferences (weights, refresh interval)
      - Save, refresh page
      - Verify settings persisted
    - [ ] 4.6.4 **API Direct Testing:**
      - `curl http://localhost:8000/api/health` (verify PostgreSQL status)
      - `curl http://localhost:8000/api/watchlist?account_id=default` (verify data)
  - [ ] 4.7 Create PostgreSQL-specific integration tests
    - [ ] 4.7.1 Create `tests/test_postgresql_integration.py`
    - [ ] 4.7.2 Test: Foreign key constraint enforcement
      - Attempt to insert orphaned record
      - Assert `psycopg2.IntegrityError` raised
    - [ ] 4.7.3 Test: Cascade delete behavior
      - Create parent + child records
      - Delete parent
      - Assert child records deleted
    - [ ] 4.7.4 Test: Unique constraint enforcement
      - Insert record with duplicate unique key
      - Assert `psycopg2.IntegrityError` raised
    - [ ] 4.7.5 Test: Connection pool exhaustion handling
      - Open pool_size + max_overflow + 1 connections
      - Assert graceful handling (queue or timeout, not crash)
    - [ ] 4.7.6 Test: Concurrent transaction isolation
      - Two threads update same row simultaneously
      - Assert no deadlock, both succeed (last write wins)
    - [ ] 4.7.7 Run: `pytest tests/test_postgresql_integration.py -v`

- [ ] **5.0 Operational Scripts & Documentation** [EFFORT: Medium, half day]
  - [ ] 5.1 Create backup utility script
    - [ ] 5.1.1 Create `scripts/postgres-backup.sh`
    - [ ] 5.1.2 Add shebang: `#!/usr/bin/env bash`
    - [ ] 5.1.3 Set variables: `BACKUP_DIR=~/portfolio-ai/backups`, `DB_NAME=portfolio_ai`, `TIMESTAMP=$(date +%Y%m%d_%H%M%S)`
    - [ ] 5.1.4 Create backup directory: `mkdir -p $BACKUP_DIR`
    - [ ] 5.1.5 Run pg_dump: `pg_dump -U portfolio_ai_user $DB_NAME | gzip > $BACKUP_DIR/portfolio_ai_$TIMESTAMP.sql.gz`
    - [ ] 5.1.6 Log success: `echo "Backup created: $BACKUP_DIR/portfolio_ai_$TIMESTAMP.sql.gz"`
    - [ ] 5.1.7 Cleanup old backups: `find $BACKUP_DIR -name "portfolio_ai_*.sql.gz" -mtime +7 -delete` (keep 7 days)
    - [ ] 5.1.8 Make executable: `chmod +x scripts/postgres-backup.sh`
    - [ ] 5.1.9 Test: `./scripts/postgres-backup.sh`
  - [ ] 5.2 Create restore utility script
    - [ ] 5.2.1 Create `scripts/postgres-restore.sh`
    - [ ] 5.2.2 Add parameter: `BACKUP_FILE=$1` (restore from specific file)
    - [ ] 5.2.3 Validate parameter exists
    - [ ] 5.2.4 Drop database: `psql -U postgres -c "DROP DATABASE IF EXISTS portfolio_ai;"`
    - [ ] 5.2.5 Recreate database: `psql -U postgres -c "CREATE DATABASE portfolio_ai OWNER portfolio_ai_user;"`
    - [ ] 5.2.6 Restore: `gunzip -c $BACKUP_FILE | psql -U portfolio_ai_user portfolio_ai`
    - [ ] 5.2.7 Log success: `echo "Restore completed from $BACKUP_FILE"`
    - [ ] 5.2.8 Make executable: `chmod +x scripts/postgres-restore.sh`
    - [ ] 5.2.9 Test: `./scripts/postgres-restore.sh ~/portfolio-ai/backups/portfolio_ai_YYYYMMDD_HHMMSS.sql.gz`
  - [ ] 5.3 Create vacuum utility script
    - [ ] 5.3.1 Create `scripts/postgres-vacuum.sh`
    - [ ] 5.3.2 Run VACUUM ANALYZE: `psql -U portfolio_ai_user -d portfolio_ai -c "VACUUM ANALYZE;"`
    - [ ] 5.3.3 Log table sizes before/after
    - [ ] 5.3.4 Make executable: `chmod +x scripts/postgres-vacuum.sh`
  - [ ] 5.4 Create status monitoring script
    - [ ] 5.4.1 Create `scripts/postgres-status.sh`
    - [ ] 5.4.2 Show connection pool status: `SELECT count(*), state FROM pg_stat_activity WHERE datname = 'portfolio_ai' GROUP BY state;`
    - [ ] 5.4.3 Show active queries: `SELECT pid, usename, state, query FROM pg_stat_activity WHERE state = 'active';`
    - [ ] 5.4.4 Show table sizes: `SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(...)) FROM pg_tables WHERE schemaname = 'public';`
    - [ ] 5.4.5 Show slow queries: `SELECT query, total_time, calls FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;`
    - [ ] 5.4.6 Make executable: `chmod +x scripts/postgres-status.sh`
  - [ ] 5.5 Update management scripts
    - [ ] 5.5.1 Update `scripts/start.sh`:
      - Add PostgreSQL check: `if ! pg_isready -q; then echo "PostgreSQL not running"; exit 1; fi`
      - Remove Redis check
      - Update status output to show PostgreSQL instead of Redis
    - [ ] 5.5.2 Update `scripts/restart.sh`:
      - Same changes as start.sh
    - [ ] 5.5.3 Update `scripts/shutdown.sh`:
      - Remove Redis shutdown section
      - Keep PostgreSQL running (system service, don't stop)
    - [ ] 5.5.4 Update `scripts/start-celery.sh`:
      - Change `--concurrency=1` → `--concurrency=4`
      - Remove Redis startup check
      - Add PostgreSQL check instead
  - [ ] 5.6 Update SETUP.md documentation
    - [ ] 5.6.1 Open `docs/core/SETUP.md`
    - [ ] 5.6.2 Add "PostgreSQL Installation" section:
      - Steps from Task 0.0 (apt install, systemctl, database creation)
    - [ ] 5.6.3 Update "Quick Start" section:
      - Add PostgreSQL setup step
      - Remove Redis setup step
    - [ ] 5.6.4 Add "Database Connection" section:
      - Explain DATABASE_URL environment variable
      - Show how to connect with psql
    - [ ] 5.6.5 Add troubleshooting section:
      - Connection errors (pg_hba.conf)
      - Permission issues (GRANT ALL)
      - Port conflicts (5432 in use)
  - [ ] 5.7 Update ARCHITECTURE.md documentation
    - [ ] 5.7.1 Open `docs/core/ARCHITECTURE.md`
    - [ ] 5.7.2 Replace DuckDB architecture diagram with PostgreSQL
    - [ ] 5.7.3 Update "Database Layer" section:
      - PostgreSQL 16 native installation
      - SQLAlchemy connection pooling (pool_size=20)
      - MVCC multi-writer concurrency
    - [ ] 5.7.4 Update "Background Tasks" section:
      - Celery uses PostgreSQL for broker + backend
      - Redis no longer required
    - [ ] 5.7.5 Add "Data Flow" diagram:
      - FastAPI → SQLAlchemy → PostgreSQL
      - Celery → PostgreSQL (broker + results)
  - [ ] 5.8 Update DEVELOPMENT.md documentation
    - [ ] 5.8.1 Open `docs/core/DEVELOPMENT.md`
    - [ ] 5.8.2 Update "Command Quick Reference" table:
      - Remove Redis commands
      - Add PostgreSQL commands:
        - `pg_isready` - Check PostgreSQL status
        - `psql portfolio_ai` - Connect to database
        - `./scripts/postgres-backup.sh` - Backup database
        - `./scripts/postgres-status.sh` - Monitor connections
    - [ ] 5.8.3 Add "PostgreSQL Development Tips" section:
      - How to view logs: `sudo journalctl -u postgresql -f`
      - How to restart: `sudo systemctl restart postgresql`
      - How to check connections: `SELECT count(*) FROM pg_stat_activity;`
  - [ ] 5.9 Update OPERATIONS.md documentation
    - [ ] 5.9.1 Open `docs/core/OPERATIONS.md`
    - [ ] 5.9.2 Add "Backup Procedures" section:
      - Daily automated backup (cron job setup)
      - Manual backup command
      - Backup compression and retention
    - [ ] 5.9.3 Add "Restore Procedures" section:
      - Restore from backup command
      - Emergency restore process
    - [ ] 5.9.4 Add "Monitoring Queries" section:
      - Active connections
      - Connection pool usage
      - Slow queries (pg_stat_statements)
      - Table sizes
      - Index usage
    - [ ] 5.9.5 Add "Performance Tuning" section:
      - Recommended postgresql.conf settings
      - When to ANALYZE tables
      - When to REINDEX
      - VACUUM strategy
    - [ ] 5.9.6 Add "Troubleshooting Guide" section:
      - Connection exhaustion
      - Slow queries (EXPLAIN ANALYZE)
      - Disk space monitoring
      - Deadlock resolution
  - [ ] 5.10 Create SQL dialect reference document
    - [ ] 5.10.1 Create `docs/postgresql-dialect-reference.md`
    - [ ] 5.10.2 Add "Common Pattern Conversions" section:
      - DuckDB vs PostgreSQL syntax table
      - Timestamp functions
      - JSON operations
      - Auto-increment columns
      - Parameterized query placeholders
    - [ ] 5.10.3 Add "Examples from Codebase" section:
      - Show actual queries before/after conversion
      - Explain why changes were needed
  - [ ] 5.11 Create rollback procedure document
    - [ ] 5.11.1 Create `docs/postgresql-migration-rollback.md`
    - [ ] 5.11.2 Add "Rollback Decision Criteria" section (from PRD)
    - [ ] 5.11.3 Add "Rollback Steps" section:
      1. Stop all services
      2. Restore DuckDB backup
      3. Revert code changes (git checkout)
      4. Reinstall DuckDB (pip install)
      5. Restart services
      6. Verify functionality
    - [ ] 5.11.4 Add "Data Preservation" section:
      - How to export PostgreSQL data before rollback
      - How to merge data back after fixes
  - [ ] 5.12 Update CLAUDE.md
    - [ ] 5.12.1 Open `CLAUDE.md`
    - [ ] 5.12.2 Update "Tech Stack" section:
      - Replace "DuckDB" with "PostgreSQL 16"
    - [ ] 5.12.3 Update "Quick Start" commands:
      - Add PostgreSQL setup step
      - Remove Redis startup step
      - Update connection string example
    - [ ] 5.12.4 Update "Command Quick Reference" table:
      - Replace DuckDB commands with PostgreSQL commands

- [ ] **6.0 Production Deployment & Go-Live** [EFFORT: Medium, half day]
  - [ ] 6.1 Pre-flight checklist execution
    - [ ] 6.1.1 Verify: DuckDB backup created and validated
    - [ ] 6.1.2 Verify: PostgreSQL installed and running (`pg_isready`)
    - [ ] 6.1.3 Verify: Database and user created (`psql -l | grep portfolio_ai`)
    - [ ] 6.1.4 Verify: All tests passing with DuckDB (baseline captured)
    - [ ] 6.1.5 Verify: Performance benchmarks captured (baseline metrics)
    - [ ] 6.1.6 Verify: All services stopped
    - [ ] 6.1.7 Verify: No pending code changes (`git status` clean)
    - [ ] 6.1.8 Verify: Rollback procedure documented and reviewed
  - [ ] 6.2 Execute migration
    - [ ] 6.2.1 Stop all services: `./scripts/shutdown.sh`
    - [ ] 6.2.2 Run schema migration: `python scripts/migrate-schema-to-postgres.py`
    - [ ] 6.2.3 Run data export: `python scripts/export-duckdb-data.py`
    - [ ] 6.2.4 Run data import: `python scripts/import-data-to-postgres.py`
    - [ ] 6.2.5 Verify data integrity (foreign keys, counts)
    - [ ] 6.2.6 Start services: `./scripts/start.sh`
    - [ ] 6.2.7 Monitor startup logs for errors
  - [ ] 6.3 Post-migration validation checklist
    - [ ] 6.3.1 Verify: All services start successfully
    - [ ] 6.3.2 Verify: Test suite 100% pass rate (`pytest tests/ -v`)
    - [ ] 6.3.3 Verify: Performance benchmarks meet targets (4x concurrency, <2s watchlist refresh)
    - [ ] 6.3.4 Verify: Data integrity checks pass (see Task 3.4)
    - [ ] 6.3.5 Verify: Manual smoke tests successful (see Task 4.6)
    - [ ] 6.3.6 Verify: Connection pooling configured correctly (see Task 3.5)
    - [ ] 6.3.7 Verify: Celery tasks execute successfully with concurrency=4
    - [ ] 6.3.8 Verify: No errors in logs for 1 hour (`tail -f /tmp/portfolio-backend.log`)
    - [ ] 6.3.9 Verify: Backup procedure tested (`./scripts/postgres-backup.sh`)
    - [ ] 6.3.10 Verify: Documentation updated (all docs from Task 5.0)
  - [ ] 6.4 Monitor for 24 hours (soak test)
    - [ ] 6.4.1 Monitor connection pool: `./scripts/postgres-status.sh` (every 4 hours)
    - [ ] 6.4.2 Monitor query performance: Check slow query log
    - [ ] 6.4.3 Monitor Celery worker logs: `tail -f /tmp/portfolio-ai-celery-worker.log`
    - [ ] 6.4.4 Monitor backend API logs: `tail -f /tmp/portfolio-backend.log`
    - [ ] 6.4.5 Check for lock errors: `SELECT * FROM pg_locks WHERE NOT granted;` (should be empty)
    - [ ] 6.4.6 Check for connection leaks: Connection count should stay <30
    - [ ] 6.4.7 Test watchlist refresh multiple times: Scores should update correctly
  - [ ] 6.5 Update health endpoint with PostgreSQL status
    - [ ] 6.5.1 Open `backend/app/api/health.py`
    - [ ] 6.5.2 Update `database` field in health response:
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
    - [ ] 6.5.3 Add query to check connection pool: `SELECT count(*), state FROM pg_stat_activity WHERE datname = 'portfolio_ai' GROUP BY state;`
    - [ ] 6.5.4 Add query to check response time: Measure latency of `SELECT 1;`
    - [ ] 6.5.5 Test: `curl http://localhost:8000/api/health | jq .database`

- [ ] **7.0 Cleanup & Future-Proofing** [EFFORT: Low, 1-2 hours]
  - [ ] 7.1 Remove DuckDB code and references
    - [ ] 7.1.1 Search codebase for "duckdb" (case-insensitive): `grep -r -i "duckdb" backend/app/`
    - [ ] 7.1.2 Remove DuckDB imports: Delete any remaining `import duckdb` lines
    - [ ] 7.1.3 Remove DuckDB comments: Update comments that mention DuckDB
    - [ ] 7.1.4 Remove DuckDB connection code: Delete old connection logic (if not already done)
    - [ ] 7.1.5 Verify: `grep -r "duckdb" backend/app/` returns no results (or only in comments/docs)
  - [ ] 7.2 Optional: Uninstall Redis (if not used elsewhere)
    - [ ] 7.2.1 Check if Redis is used by other services: `ps aux | grep redis`
    - [ ] 7.2.2 If safe to remove:
      - Stop Redis: `redis-cli shutdown`
      - Uninstall: `sudo apt remove redis-server` (optional, not required)
      - Or just leave installed but stopped (no harm)
    - [ ] 7.2.3 Update documentation to note Redis is no longer required
  - [ ] 7.3 Document Redis migration path (future optimization)
    - [ ] 7.3.1 Add section to `docs/core/OPERATIONS.md`: "Migrating Celery to Redis"
    - [ ] 7.3.2 Add "When to Consider" subsection:
      - Celery task throughput exceeds 1000 tasks/second
      - Task latency requirements drop below 10ms
      - Worker pool scales beyond 20 workers
    - [ ] 7.3.3 Add "Migration Steps" subsection:
      1. Install Redis: `sudo apt install redis-server`
      2. Update Celery config: `broker="redis://localhost:6379/0"`
      3. Keep PostgreSQL as result backend (or switch to Redis)
      4. Test and benchmark performance difference
    - [ ] 7.3.4 Add "Performance Comparison" subsection:
      - PostgreSQL: Good for low-medium throughput (<100 tasks/sec)
      - Redis: Excellent for high throughput (1000+ tasks/sec)
      - Trade-off: Redis adds operational complexity (one more service)
  - [ ] 7.4 Update REFACTOR_STATUS.md
    - [ ] 7.4.1 Open `docs/core/REFACTOR_STATUS.md`
    - [ ] 7.4.2 Add entry: "PRD #0015: PostgreSQL Migration - COMPLETE ✅"
    - [ ] 7.4.3 Add completion date: 2025-10-XX
    - [ ] 7.4.4 Add summary: "Migrated from DuckDB to PostgreSQL, eliminated concurrency bottlenecks, increased Celery worker concurrency from 1 → 4"
    - [ ] 7.4.5 Add metrics achieved:
      - Zero database lock errors under load
      - 4x Celery worker concurrency
      - <2s watchlist refresh latency (maintained)
      - 100% test pass rate
  - [ ] 7.5 Archive DuckDB backup
    - [ ] 7.5.1 Create archive directory: `mkdir -p ~/portfolio-ai/archives/duckdb`
    - [ ] 7.5.2 Move backup: `mv ~/portfolio-ai/backend/data/portfolio.duckdb.backup-* ~/portfolio-ai/archives/duckdb/`
    - [ ] 7.5.3 Compress: `gzip ~/portfolio-ai/archives/duckdb/portfolio.duckdb.backup-*`
    - [ ] 7.5.4 Document archive location in `docs/core/OPERATIONS.md`
    - [ ] 7.5.5 Set reminder: Keep archive for 30 days, then delete if no issues
  - [ ] 7.6 Create migration summary report
    - [ ] 7.6.1 Create `docs/postgresql-migration-summary.md`
    - [ ] 7.6.2 Add "Migration Overview" section: Timeline, scope, goals achieved
    - [ ] 7.6.3 Add "Performance Results" section: Before/after benchmarks
      - Concurrency: 1 worker → 4 workers
      - Lock errors: Frequent → Zero
      - Watchlist refresh: ~1.2s → ~1.2s (maintained)
      - Connection pool: N/A → 20 connections + 10 overflow
    - [ ] 7.6.4 Add "Lessons Learned" section:
      - What went well (planning, schema translation)
      - What was challenging (SQL dialect differences, connection pool tuning)
      - What would we do differently (test earlier, more incremental)
    - [ ] 7.6.5 Add "Next Steps" section:
      - Continue Phase 1 watchlist completion
      - Monitor PostgreSQL performance over time
      - Consider Redis migration if throughput increases
      - Add read replicas if needed for analytics

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All PRD requirements implemented (PostgreSQL installed, schema migrated, application updated)
  - [ ] All user stories satisfied (concurrent workers, no lock errors, connection pooling)
  - [ ] Integration points working correctly (Celery + PostgreSQL, FastAPI + PostgreSQL)
  - [ ] Zero known bugs or regressions

- [ ] **Test Coverage** (target: 80%+)
  - [ ] All existing tests pass with PostgreSQL (100% pass rate)
  - [ ] New PostgreSQL-specific tests added (foreign keys, connection pool, cascade deletes)
  - [ ] Integration tests for cross-module interactions
  - [ ] End-to-end test of complete workflow (watchlist, portfolio, preferences)
  - [ ] All tests passing: `pytest tests/ -v`
  - [ ] Coverage maintained: `pytest tests/ --cov=app --cov-report=term-missing` (80%+)

- [ ] **Performance Validation**
  - [ ] Concurrent write benchmark passes (4 workers, zero errors)
  - [ ] Watchlist refresh benchmark passes (<2 seconds)
  - [ ] Load testing passes (4 workers + 20 API clients, no lock errors)
  - [ ] Connection pool never exhausted under load
  - [ ] Query performance maintained or improved (p95 <100ms)

- [ ] **Type Safety & Code Quality**
  - [ ] 100% type hints on all modified functions: `mypy app/ --strict` passes
  - [ ] Linting passes: `scripts/lint.sh` returns zero errors
  - [ ] Code formatting applied: `ruff format app/`
  - [ ] Complexity limits met (functions <50 lines, complexity <10)

- [ ] **Documentation**
  - [ ] All operational scripts documented (backup, restore, status, vacuum)
  - [ ] SETUP.md updated with PostgreSQL installation steps
  - [ ] ARCHITECTURE.md updated with PostgreSQL architecture
  - [ ] DEVELOPMENT.md updated with PostgreSQL commands
  - [ ] OPERATIONS.md updated with runbooks (backup, restore, monitoring, tuning)
  - [ ] SQL dialect reference created (postgresql-dialect-reference.md)
  - [ ] Rollback procedure documented (postgresql-migration-rollback.md)
  - [ ] REFACTOR_STATUS.md updated (mark PRD #0015 complete)

- [ ] **Security & Data Integrity**
  - [ ] Foreign key constraints enforced (tested)
  - [ ] Cascade deletes working correctly (tested)
  - [ ] Unique constraints enforced (tested)
  - [ ] No SQL injection vulnerabilities (parameterized queries verified)
  - [ ] Database credentials in environment variables, not code
  - [ ] pg_hba.conf configured securely (trust for localhost only)

- [ ] **Operational Readiness**
  - [ ] Backup procedure tested (create + restore successful)
  - [ ] Monitoring queries documented and tested
  - [ ] Health endpoint reports PostgreSQL status
  - [ ] Connection pool monitoring working
  - [ ] Manual end-to-end test via UI successful
  - [ ] 24-hour soak test completed without issues
  - [ ] Rollback procedure documented and ready

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist

---

## Rollback Procedure (Emergency Use Only)

If critical issues arise within 48 hours of migration, follow these steps:

1. **Stop all services:** `./scripts/shutdown.sh`
2. **Restore DuckDB backup:**
   ```bash
   cp ~/portfolio-ai/backend/data/portfolio.duckdb.backup-YYYYMMDD ~/portfolio-ai/backend/data/portfolio.duckdb
   ```
3. **Revert code changes:**
   ```bash
   cd ~/portfolio-ai
   git checkout <commit-hash-before-migration>
   ```
4. **Reinstall DuckDB:**
   ```bash
   cd ~/portfolio-ai/backend
   source .venv/bin/activate
   pip install duckdb==1.4.1
   ```
5. **Restart services:** `./scripts/start.sh`
6. **Verify functionality:** Test critical flows (watchlist, portfolio)
7. **Document issue:** Create incident report in `docs/postgresql-migration-rollback.md`

**Rollback Decision Criteria:**
- Test suite pass rate drops below 95%
- Performance regression >50%
- Critical bugs within 48 hours
- Data integrity violations
- Production downtime exceeds 4 hours

**Note:** Rollback should be a last resort. PostgreSQL is the correct long-term solution. Most issues can be fixed forward.

---

**Last Updated:** 2025-10-29
**Status:** Ready for implementation - Start with Task 0.0 for sudo approval
**Next Action:** Execute Task 0.0 to install PostgreSQL and configure system
