# Task List: Data Architecture Consolidation & Database Normalization

**Source**: User request via /task_it (very thorough exploration of data sources + database architecture + normalization analysis)
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-03 14:30
**Updated**: 2025-12-03 15:00 (added database normalization tasks)

---

## Summary

**Goal**: Consolidate data source gathering and database architecture to eliminate DRY violations, remove deprecated code, standardize patterns, normalize redundant data storage, and optimize for maintainability without introducing regressions.

**Approach**: Scope discovery first to validate all findings, then systematic refactoring with verification at each step. Focus on code consolidation, pattern standardization, removing dead code, and proper database normalization with FK constraints.

**Scope Discovery**: Required - Multiple files affected, need complete inventory before changes.

**Alignment with VISION.md**:
- Core Principle 5: "Reliability Through Redundancy" - Maintains multi-source failover, adds referential integrity
- Core Principle 6: "Developer Velocity & Code Quality" - Improves maintainability, <500 lines per file, single source of truth

---

## Tasks

**IMPORTANT: Use section headers (###) for high-level tasks**

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Verify deprecated CBOE source impact
  - Pattern: All imports/usages of cboe_source.py across codebase
  - Check: Any active references in tasks, API, or UI
  - Check: Any active Beat schedule entries
  - Output: Safe to remove (Y/N) with evidence

- [ ] 0.2 Inventory hardcoded symbol lists
  - Pattern: "SPY", "^GSPC", "^VIX", "^TNX", "XLK", etc. across entire codebase
  - Goal: Find ALL locations where market symbols are hardcoded
  - Output: List of files with line numbers

- [ ] 0.3 Inventory database access patterns
  - Pattern: storage.query(), storage.connection(), storage.execute()
  - Pattern: Direct SQL vs repository usage
  - Goal: Map which entities use which patterns
  - Output: Entity → Pattern mapping table

- [ ] 0.4 Measure upsert_watchlist_snapshot method
  - File: backend/app/storage/queries.py
  - Verify: Line count, parameter count
  - Check: Any other >100 line methods in storage layer
  - Output: Methods violating size standards

- [ ] 0.5 Inventory ticker/symbol column inconsistencies
  - Tables using `symbol`: day_bars, watchlist_items, technical_indicators, fundamental_cache
  - Tables using `ticker`: price_cache, news_cache, paper_trade_transactions, earnings_surprises
  - Goal: Complete list of all tables with ticker/symbol columns
  - Output: Table → Column name mapping

- [ ] 0.6 Identify redundant data storage
  - Price data: day_bars.close vs watchlist_snapshots.price vs paper_trade_transactions.price
  - Fundamental data: reference_cache vs fundamental_cache overlap
  - Technical data: technical_indicators vs watchlist_snapshots computed fields
  - Output: Redundancy matrix showing duplicate storage

- [ ] 0.7 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Total migrations needed: [TBD]
  - Estimated effort: [TBD]
  - Architectural concerns: [TBD]
  - Dependencies on deprecated code: [TBD]
  - Breaking changes requiring API updates: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Remove Deprecated CBOE Source

- [ ] 1.1 Remove cboe_source.py from sources directory
  - File: backend/app/sources/cboe_source.py
  - Verify: No active imports remain
  - Note: cboe_most_active.py is ACTIVE (different file - scrapes options activity)

- [ ] 1.2 Remove any CBOE source references from multi_source_fetcher.py
  - Check for CboeSource in source list
  - Check for cboe_source imports

- [ ] 1.3 Remove any CBOE Beat schedule entries
  - File: backend/app/celery_schedules.py
  - Look for: putcall_ratio tasks using CBOE (not yfinance)

- [ ] 1.4 Verify tests pass after removal
  - Run: pytest tests/ -v -k cboe
  - Expected: Either no tests OR tests skip/pass

### 2.0 Consolidate Hardcoded Symbol Lists

- [ ] 2.1 Create centralized symbol constants module
  - File: backend/app/constants/symbols.py (new)
  - Contents: MARKET_INDICATORS, SECTOR_ETFS, BENCHMARK_SYMBOLS
  - Include: SPY, ^GSPC, ^VIX, ^TNX, DX-Y.NYB, XLK-XLC

- [ ] 2.2 Update price_ingestion.py to use constants
  - Current: Hardcoded list in refresh_daily_ohlcv
  - Replace with: from app.constants.symbols import MARKET_INDICATORS

- [ ] 2.3 Update historical_ohlcv_pipeline.py to use constants
  - Current: Hardcoded market_symbols list
  - Replace with: from app.constants.symbols import MARKET_INDICATORS, SECTOR_ETFS

- [ ] 2.4 Update fear_greed_pipeline.py to use constants
  - Current: Hardcoded SPY, ^VIX references
  - Replace with: from app.constants.symbols import BENCHMARK_SPY, BENCHMARK_VIX

- [ ] 2.5 Update any remaining hardcoded symbol locations
  - Based on scope discovery findings from 0.2
  - Apply DRY principle consistently

- [ ] 2.6 Verify all tasks still work after symbol consolidation
  - Run: pytest tests/tasks/ -v
  - Manual check: Scripts still resolve symbols correctly

### 3.0 Standardize Database Access Patterns

- [ ] 3.1 Create PortfolioRepository class
  - File: backend/app/portfolio/portfolio_repository.py (new)
  - Pattern: Match WatchlistRepository interface
  - Methods: get_all_positions(), get_position_by_id(), upsert_position()

- [ ] 3.2 Create BacktestRepository class
  - File: backend/app/backtest/backtest_repository.py (new)
  - Pattern: Match WatchlistRepository interface
  - Methods: get_runs(), get_trades(), get_equity_curve()

- [ ] 3.3 Migrate portfolio API endpoints to use PortfolioRepository
  - File: backend/app/api/portfolio.py
  - Replace: Direct storage.query() calls
  - With: PortfolioRepository methods

- [ ] 3.4 Migrate backtest API endpoints to use BacktestRepository
  - File: backend/app/api/backtest.py
  - Replace: Direct storage.query() calls
  - With: BacktestRepository methods

- [ ] 3.5 Verify API endpoints work after migration
  - Run: pytest tests/api/ -v
  - Manual: Test /api/portfolio and /api/backtest endpoints

### 4.0 Refactor Large Upsert Method

- [ ] 4.1 Extract JSON serialization helper
  - From: QueryManager.upsert_watchlist_snapshot()
  - To: _serialize_snapshot_fields() private method
  - Reduce: Main method line count

- [ ] 4.2 Extract SQL builder helper
  - From: QueryManager.upsert_watchlist_snapshot()
  - To: _build_upsert_sql() with column list parameter
  - Goal: Reusable for other upsert operations

- [ ] 4.3 Extract parameter preparation helper
  - From: QueryManager.upsert_watchlist_snapshot()
  - To: _prepare_upsert_params() private method
  - Goal: Main method under 50 lines

- [ ] 4.4 Verify refactored upsert still works
  - Run: pytest tests/ -v -k snapshot
  - Verify: Watchlist scores still update correctly

### 5.0 Fix DRY Violation in Source Initialization

- [ ] 5.1 Consolidate source initialization in price_fetcher.py
  - Current: Manual if/else for each API key (lines 60-98)
  - Replace with: Call to _initialize_data_sources() helper from price_ingestion.py
  - Or: Extract shared helper to sources/__init__.py

- [ ] 5.2 Verify price fetching still works
  - Run: pytest tests/ -v -k price
  - Manual: Verify portfolio page shows prices

### 6.0 Add Missing Query Profiling (Optional Enhancement)

- [ ] 6.1 Add query logging to storage facade
  - File: backend/app/storage/facade.py
  - Add: Optional SLOW_QUERY_LOG_MS env var (default: 1000ms)
  - Log: Queries exceeding threshold with duration

- [ ] 6.2 Add connection retry logic
  - File: backend/app/storage/connection.py
  - Add: Exponential backoff for transient connection failures
  - Max: 3 retries with 1s, 2s, 4s delays

### 7.0 Standardize Placeholder Styles (Low Priority)

- [ ] 7.1 Document placeholder convention
  - Add: Comment in connection.py explaining ? → %s conversion
  - Prefer: %s (PostgreSQL native) in new code

- [ ] 7.2 Audit critical paths for placeholder consistency
  - Focus: Ingestion and upsert operations
  - Goal: Verify converter handles all cases

---

## DATABASE NORMALIZATION TASKS

### 8.0 Create Centralized Symbols Table (FOUNDATIONAL)

- [ ] 8.1 Create migration for symbols table
  - File: backend/migrations/058_symbols_table.sql
  - Schema:
    ```sql
    CREATE TABLE symbols (
        symbol VARCHAR(20) PRIMARY KEY,
        company_name TEXT,
        sector VARCHAR(100),
        industry VARCHAR(100),
        exchange VARCHAR(10),
        security_type VARCHAR(20) DEFAULT 'equity',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX idx_symbols_sector ON symbols(sector);
    CREATE INDEX idx_symbols_exchange ON symbols(exchange);
    ```

- [ ] 8.2 Populate symbols table from existing data
  - Source: DISTINCT symbols from day_bars, watchlist_items, portfolio_positions
  - Enrich: Sector/industry from reference_cache or yfinance
  - Verify: All existing tickers have entries

- [ ] 8.3 Add FK constraints to core tables (non-breaking)
  - day_bars: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - watchlist_items: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - portfolio_positions: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - technical_indicators: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - Note: Use ON DELETE RESTRICT to prevent orphans

- [ ] 8.4 Update application code to use symbols table
  - Add: SymbolsRepository for symbol lookups
  - Add: Validation that new symbols are registered before use
  - Update: Watchlist add flow to check/create symbol first

- [ ] 8.5 Verify no broken FK constraints
  - Run: pytest tests/ -v
  - Check: All existing data passes FK validation

### 9.0 Standardize Ticker/Symbol Column Naming

- [ ] 9.1 Create migration to rename ticker → symbol columns
  - File: backend/migrations/059_standardize_symbol_columns.sql
  - Tables to update:
    - price_cache: RENAME COLUMN ticker TO symbol
    - news_cache: RENAME COLUMN ticker TO symbol
    - paper_trade_transactions: RENAME COLUMN ticker TO symbol
    - earnings_surprises: RENAME COLUMN ticker TO symbol
    - news_summary_log: RENAME COLUMN ticker TO symbol
    - watchlist_gap_coverage: RENAME COLUMN ticker TO symbol

- [ ] 9.2 Update all Python code referencing renamed columns
  - Search: grep -r "\.ticker" backend/app/
  - Update: All model classes, queries, API responses
  - Verify: No hardcoded "ticker" column references remain

- [ ] 9.3 Update frontend TypeScript types
  - Search: grep -r "ticker:" frontend/
  - Update: API response types to use "symbol"
  - Note: May need API backward compatibility layer

- [ ] 9.4 Add FK constraints to renamed tables
  - news_cache: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - earnings_surprises: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  - price_cache: ADD FOREIGN KEY (symbol) REFERENCES symbols(symbol)

- [ ] 9.5 Verify all queries work after rename
  - Run: pytest tests/ -v
  - Manual: Test news, earnings, price cache endpoints

### 10.0 Remove Redundant Symbol from watchlist_snapshots

- [ ] 10.1 Verify watchlist_snapshots.symbol duplicates watchlist_items.symbol
  - Query: Check if all snapshots have matching item symbol
  - Confirm: No cases where snapshot.symbol != item.symbol

- [ ] 10.2 Create migration to drop redundant column
  - File: backend/migrations/060_drop_snapshot_symbol.sql
  - SQL: ALTER TABLE watchlist_snapshots DROP COLUMN symbol;
  - Note: Use item_id FK to get symbol via JOIN

- [ ] 10.3 Update queries to JOIN for symbol
  - Pattern: SELECT wi.symbol, ws.* FROM watchlist_snapshots ws JOIN watchlist_items wi ON ws.item_id = wi.id
  - Update: WatchlistRepository, QueryManager, API endpoints

- [ ] 10.4 Update Pydantic models
  - File: backend/app/watchlist/models.py
  - Remove: symbol from WatchlistSnapshot model (or make it computed)

### 11.0 Consolidate Fundamental Data Tables

- [ ] 11.1 Analyze reference_cache vs fundamental_cache overlap
  - reference_cache: pe_ratio_trailing, ps_ratio, pb_ratio, dividend_yield, payout_ratio
  - fundamental_cache: profit_margin, revenue_growth, debt_to_equity, recommendation_mean
  - Goal: Identify which table is source of truth

- [ ] 11.2 Create unified fundamental_metrics table
  - File: backend/migrations/061_unified_fundamentals.sql
  - Schema: Combine all metrics into single table
  - Include: symbol (FK), as_of_date, all metric columns, source, cached_at

- [ ] 11.3 Migrate data from both tables
  - Merge: reference_cache extracted metrics + fundamental_cache metrics
  - Dedupe: Keep most recent for each symbol

- [ ] 11.4 Update application code
  - Replace: Separate queries to reference_cache and fundamental_cache
  - With: Single query to fundamental_metrics
  - Update: Ingestion tasks to write to unified table

- [ ] 11.5 Drop deprecated tables (after verification)
  - SQL: DROP TABLE reference_cache; DROP TABLE fundamental_cache;
  - Note: Only after all code updated and tested

### 12.0 Remove Redundant backtest_trades.symbol

- [ ] 12.1 Verify backtest is single-symbol (Phase A constraint)
  - Check: All trades in a run have same symbol as backtest_runs.symbol
  - Confirm: No multi-symbol backtests exist

- [ ] 12.2 Create migration to drop redundant column
  - File: backend/migrations/062_drop_backtest_trade_symbol.sql
  - SQL: ALTER TABLE backtest_trades DROP COLUMN symbol;
  - Note: Get symbol via run_id FK → backtest_runs.symbol

- [ ] 12.3 Update backtest queries to JOIN for symbol
  - Pattern: SELECT br.symbol, bt.* FROM backtest_trades bt JOIN backtest_runs br ON bt.run_id = br.id

### 13.0 Normalize watchlist_snapshots Position Sizing (Optional)

- [ ] 13.1 Create separate trade_recommendations table
  - Purpose: entry_price, stop_loss, profit_target, position_size_shares don't belong in snapshots
  - Schema:
    ```sql
    CREATE TABLE trade_recommendations (
        id SERIAL PRIMARY KEY,
        item_id UUID NOT NULL REFERENCES watchlist_items(id),
        signal_date DATE NOT NULL,
        entry_price DECIMAL(15,4),
        stop_loss DECIMAL(15,4),
        profit_target DECIMAL(15,4),
        position_size_shares INT,
        recommended_style VARCHAR(50),
        risk_level VARCHAR(20),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(item_id, signal_date)
    );
    ```

- [ ] 13.2 Migrate position sizing data
  - From: watchlist_snapshots (entry_price, stop_loss, etc.)
  - To: trade_recommendations (one per signal_date)

- [ ] 13.3 Drop position sizing columns from watchlist_snapshots
  - Columns: entry_price, stop_loss, profit_target, position_size_shares, recommended_style, risk_level

### 14.0 Add Price Data FK Constraints (Referential Integrity)

- [ ] 14.1 Add FK from technical_indicators to day_bars
  - SQL: ALTER TABLE technical_indicators ADD FOREIGN KEY (symbol, date) REFERENCES day_bars(symbol, date);
  - Note: Ensures indicators only exist for dates with OHLCV data

- [ ] 14.2 Add FK from fear_greed_inputs to day_bars (for SPY)
  - Conceptual: spy_close should match day_bars.close for SPY on as_of_date
  - Note: May be too restrictive - evaluate

- [ ] 14.3 Document price data relationships
  - day_bars: Source of truth for historical OHLCV
  - price_cache: Real-time lookup cache (can differ from day_bars.close)
  - Transaction prices: Audit trail (intentionally denormalized for history)

---

## Verification

- [ ] Functional: All data sources still work (multi-source failover)
- [ ] Tests: pytest -v passes (regression check)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: bash ~/portfolio-ai/scripts/restart.sh succeeds
- [ ] Clean: No deprecated CBOE imports remain
- [ ] DRY: Symbol lists consolidated, no hardcoded duplicates
- [ ] Normalized: symbols table exists with FK constraints
- [ ] Consistent: All tables use "symbol" (not "ticker")
- [ ] Referential: FK constraints enforced, no orphan records
- [ ] Docs: Update ARCHITECTURE.md with new schema

---

## Risk Assessment

**Low Risk (Safe):**
- Removing deprecated CBOE source (already non-functional, HTTP 403)
- Adding new repository classes (additive, non-breaking)
- Adding query profiling (optional, behind env var)
- Creating symbols table (additive, non-breaking)

**Medium Risk (Test Carefully):**
- Symbol constant consolidation (ensure all import paths work)
- Upsert method refactoring (critical path for watchlist data)
- Renaming ticker → symbol columns (requires code updates)
- Adding FK constraints (may fail if orphan data exists)

**High Risk (Requires Careful Migration):**
- Dropping columns from watchlist_snapshots (50+ columns affected)
- Consolidating fundamental tables (multiple consumers)
- Removing redundant price data (audit trail concerns)

**Mitigation:**
- Run full test suite after each high-level task
- Manual verification of affected pages (watchlist, portfolio, backtest)
- Keep git commits atomic for easy rollback
- Create database backup before schema changes
- Use transactions for multi-step migrations
- Add backward compatibility layer for API changes if needed

---

## Notes from Exploration

**Data Sources (23 files):**
- 6 OHLCV sources: YFinance (priority 1), TwelveData (2), FMP (3), Finnhub (5), AlphaVantage (6), Polygon (10)
- CBOE source marked DEPRECATED (HTTP 403 since 2025-11-17)
- cboe_most_active.py is ACTIVE (different from cboe_source.py)

**Database Architecture:**
- Raw SQL everywhere (no SQLAlchemy ORM)
- Only WatchlistRepository exists
- QueryManager.upsert_watchlist_snapshot() is 253+ lines
- Connection pooling properly configured (QueuePool)

**Data Ingestion (47 Celery tasks):**
- Self-healing backfill mechanisms working well
- Market-hours awareness implemented
- Redis task deduplication in place

---

## Data Redundancy Analysis Findings

**Critical Issues Identified:**

1. **No Centralized Symbols Table**
   - 15+ tables store ticker/symbol as TEXT with no FK
   - Inconsistent naming: some use "symbol", others use "ticker"
   - Risk: Data inconsistency, no referential integrity

2. **Price Data Stored Multiple Times**
   - day_bars.close (source of truth)
   - watchlist_snapshots.price (copy)
   - paper_trade_transactions.price (copy)
   - idea_outcomes.entry_price (copy)
   - backtest_trades.entry_price (copy)

3. **watchlist_snapshots Massive Denormalization (50+ columns)**
   - Stores: scores, signals, narratives, technical data, earnings, news, position sizing
   - Should be: 4 separate tables with FKs

4. **Duplicate Fundamental Data**
   - reference_cache: pe_ratio, ps_ratio, pb_ratio, dividend_yield
   - fundamental_cache: profit_margin, revenue_growth, debt_to_equity
   - Should be: Single unified fundamental_metrics table

5. **Fear & Greed: 3 Tables for Derived Data**
   - fear_greed_inputs (raw) → fear_greed_components (computed) → fear_greed_daily (aggregated)
   - Tables 2 and 3 are 100% derived from Table 1

**Tables Using "ticker" (need rename to "symbol"):**
- price_cache
- news_cache
- paper_trade_transactions
- earnings_surprises
- news_summary_log
- watchlist_gap_coverage

**Recommended Migration Order:**
1. Create symbols table (foundation)
2. Rename ticker → symbol (consistency)
3. Add FK constraints (referential integrity)
4. Remove redundant columns (cleanup)
5. Consolidate fundamental tables (single source of truth)
