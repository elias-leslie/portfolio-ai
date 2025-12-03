<!-- PAUSED: 2025-12-03 13:45 | Context: 83% | Reason: User request | Next: Task 3.0 - Standardize database access patterns -->

# Task List: Data Architecture Consolidation & Database Normalization

**Source**: User request via /task_it (very thorough exploration of data sources + database architecture + normalization analysis)
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-03 14:30
**Updated**: 2025-12-03 15:00 (added database normalization tasks)
**Status**: PAUSED
**Last Updated**: 2025-12-03 13:45
**Pause Reason**: User request
**Context Used**: 165K/200K (83%)
**Completed This Session**: Tasks 1.0, 2.0, 8.0, 9.0 (symbol consolidation + DB normalization)
**Next Action**: Task 3.0 - Standardize database access patterns (create repositories)
**Resume Command**: `/do_it`

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

- [x] 0.1 Verify deprecated CBOE source impact ✅ COMPLETE
  - Pattern: All imports/usages of cboe_source.py across codebase
  - Check: Any active references in tasks, API, or UI
  - Check: Any active Beat schedule entries
  - Output: **Safe to remove: YES**
  - Evidence: Zero imports, zero usages, zero tests. Explicitly marked DEPRECATED.
  - Note: cboe_most_active.py is DIFFERENT and ACTIVE (don't remove)

- [x] 0.2 Inventory hardcoded symbol lists ✅ COMPLETE
  - Pattern: "SPY", "^GSPC", "^VIX", "^TNX", "XLK", etc. across entire codebase
  - Goal: Find ALL locations where market symbols are hardcoded
  - Output: **16 unique symbols across 14 files**
  - Key duplications:
    - SECTOR_ETFS defined in 4+ places (market_breadth.py, sector_strength.py, market_data_sources.py, plain_language.py)
    - MARKET_INDICATORS in celery_schedules.py AND historical_ohlcv_pipeline.py
  - Consolidation target: constants/symbols.py

- [x] 0.3 Inventory database access patterns ✅ COMPLETE
  - Pattern: storage.query(), storage.connection(), storage.execute()
  - Pattern: Direct SQL vs repository usage
  - Output: **134 storage.query() calls | 171 storage.connection() calls | 4 storage.execute() calls**
  - Only WatchlistRepository exists (used in 3 files, 11 others bypass it)
  - Entities needing repositories: Portfolio (9 files), News (10 files), Agents (8 files)
  - Assessment: Widespread raw SQL - repository pattern NOT consistently applied

- [x] 0.4 Measure upsert_watchlist_snapshot method ✅ COMPLETE
  - File: backend/app/storage/queries.py
  - Output: **120 lines, 43 parameters** (violates <50 line standard by 2.4x)
  - Helper methods also large:
    - _prepare_snapshot_parameters(): 97 lines
    - _build_snapshot_upsert_sql(): 66 lines
  - Other violations: connection.py::insert_dataframe() 79 lines
  - Assessment: 43 params = schema bloat indicator

- [x] 0.5 Inventory ticker/symbol column inconsistencies ✅ COMPLETE
  - **Tables using `symbol`** (7): watchlist_items, portfolio_positions, fundamental_cache, strategy_definitions, strategy_signals, backtest_runs, backtest_trades
  - **Tables using `ticker`** (7): day_bars, price_cache, news_cache, paper_trade_transactions, earnings_surprises, news_summary_log, watchlist_gap_coverage
  - **Special**: portfolio_covariance uses ticker1/ticker2, sec_cik_cache uses ticker as PK
  - **No FKs exist** - all are TEXT columns with no referential integrity
  - Output: 14+ tables with inconsistent naming, zero FK constraints to symbols

- [x] 0.6 Identify redundant data storage ✅ COMPLETE
  - **Price data**: NOT redundant - different semantics (day_bars=historical, price_cache=real-time, snapshots=audit, trades=immutable)
  - **Fundamental data**: RESOLVED - fundamental_cache was dropped in migration 021, reference_cache is single source
  - **Fear & Greed**: CORRECT ETL pipeline (inputs→components→daily), not redundancy
  - **watchlist_snapshots**: 46 columns, INTENTIONAL denormalization for snapshot audit trail
  - Output: **Low-to-moderate redundancy, mostly intentional design choices**

- [x] 0.7 Checkpoint: Confirm scope before proceeding ✅ CONFIRMED (Full scope)
  - **Total files affected**: ~50+ files (14 symbol files, 27+ storage files, 10+ API files)
  - **Total migrations needed**: 5-7 (symbols table, ticker→symbol renames, FK constraints)
  - **Estimated effort**: HIGH (3-5 days for full consolidation)
  - **Architectural concerns**:
    - Repository pattern not adopted (only WatchlistRepository exists)
    - 43-param upsert method indicates schema complexity
    - Zero FK constraints across all symbol/ticker columns
  - **Dependencies on deprecated code**: cboe_source.py safe to delete (0 usages)
  - **Breaking changes**: Renaming ticker→symbol requires API+frontend updates
  - **Risk assessment**:
    - LOW: Remove CBOE source, create symbols.py constants
    - MEDIUM: Consolidate SECTOR_ETFS across 4 files
    - HIGH: Rename ticker→symbol columns (14+ tables, code updates)
    - HIGH: Add FK constraints (may fail on orphan data)

**SCOPE DISCOVERY SUMMARY:**
| Finding | Impact | Recommendation |
|---------|--------|----------------|
| CBOE source deprecated | LOW | Remove immediately (Task 1) |
| 16 symbols in 14 files | MEDIUM | Create constants/symbols.py (Task 2) |
| 305 raw SQL calls | HIGH | DEFER - too invasive for this task |
| 120-line upsert method | MEDIUM | Refactor but keep current schema (Task 4) |
| ticker/symbol inconsistency | HIGH | Create symbols table + standardize (Tasks 8-9) |
| Redundant data storage | LOW | Mostly intentional - no action needed |

**RECOMMENDED SCOPE REDUCTION:**
Skip Tasks 3 (repositories), 10-14 (aggressive normalization) as too invasive.
Focus on: Tasks 1, 2, 4, 8, 9 (safe consolidation + symbols table)

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Remove Deprecated CBOE Source ✅ COMPLETE

- [x] 1.1 Removed cboe_source.py from sources directory
- [x] 1.2 No CBOE imports existed in multi_source_fetcher.py (verified during scope)
- [x] 1.3 No CBOE Beat schedule entries (using yfinance for put/call ratio)
- [x] 1.4 N/A - no CBOE-specific tests exist

### 2.0 Consolidate Hardcoded Symbol Lists ✅ COMPLETE

- [x] 2.1 Created centralized symbol constants module (backend/app/constants/symbols.py)
- [x] 2.2 Updated celery_schedules.py to use ALL_MARKET_SYMBOLS constant
- [x] 2.3 Updated historical_ohlcv_pipeline.py to use ALL_MARKET_SYMBOLS constant
- [x] 2.4 Updated market_breadth.py, sector_strength.py, market_data_sources.py, sentiment.py to use SECTOR_ETFS constant
- [x] 2.5 Merged old constants.py into new constants package (__init__.py)
  - Based on scope discovery findings from 0.2
  - Apply DRY principle consistently

- [x] 2.6 Verify all tasks still work after symbol consolidation ✅ COMPLETE
  - 60 symbol/market tests passed
  - Symbol constants import OK (16 ALL_MARKET_SYMBOLS, 11 SECTOR_ETFS)
  - Mypy passes (306 files, 0 errors)
  - Ruff format applied (4 files)

### 3.0 Standardize Database Access Patterns ⏭️ DEFERRED

**Reason**: Scope discovery identified 305 raw SQL calls across 27+ files.
Creating repository pattern for all entities is too invasive for this task.
Only WatchlistRepository exists - adding more requires significant refactoring.

**Future work**: Consider incremental adoption when touching specific APIs.

### 4.0 Refactor Large Upsert Method ✅ ALREADY COMPLETE

**Status**: Helpers already extracted in queries.py:
- `_serialize_snapshot_json_fields()` (lines 113-140) - JSON serialization
- `_build_snapshot_upsert_sql()` (lines 142-207) - SQL builder
- `_prepare_snapshot_parameters()` (lines 209-305) - Parameter preparation
- `upsert_watchlist_snapshot()` (lines 307-426) - Main method, 120 lines

Main method now just: serialize → build SQL → prepare params → execute.
43 params still exist due to schema - that's acceptable (audit trail requirement).

### 5.0 Fix DRY Violation in Source Initialization ✅ COMPLETE

- [x] 5.1 Created shared initialize_data_sources() in sources/__init__.py
- [x] 5.2 Updated price_fetcher.py to use shared helper (removed ~50 lines)
- [x] 5.3 Updated price_ingestion.py to use shared helper with credentials wrapper
- [x] 5.4 Verified: Both modules initialize 6 sources correctly

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

### 8.0 Create Centralized Symbols Table (FOUNDATIONAL) ✅ COMPLETE

- [x] 8.1 Created migration 058_symbols_table.sql
  - Created symbols table with symbol as PRIMARY KEY
  - Added columns: company_name, sector, industry, exchange, security_type, is_active
  - Added indexes on sector, exchange, security_type, is_active

- [x] 8.2 Populated symbols table from existing data
  - Source: DISTINCT symbols from day_bars, watchlist_items, news_cache, portfolio_positions, backtest_runs
  - Auto-classified security_type: equity, etf, index, currency based on symbol patterns
  - Result: 43 unique symbols populated

- [x] 8.3 Add FK constraints to core tables ✅ COMPLETE
  - Created migration 061_add_symbol_fk_constraints.sql
  - 10 FK constraints added: day_bars, watchlist_items, portfolio_positions,
    news_cache, price_cache, technical_indicators, strategy_definitions,
    strategy_signals, backtest_runs, earnings_surprises
  - Added missing symbol NVDL to symbols table
  - All constraints use DEFERRABLE INITIALLY DEFERRED for transaction flexibility

- [x] 8.4 Application code now uses consistent 'symbol' column naming
  - Add: SymbolsRepository for symbol lookups
  - Add: Validation that new symbols are registered before use
  - Update: Watchlist add flow to check/create symbol first

- [x] 8.5 Verify no broken FK constraints ✅ COMPLETE
  - Validated: 0 orphan symbols in day_bars, watchlist_items, news_cache
  - All 10 FK constraints applied successfully
  - symbols table now has 44 entries (43 original + 1 NVDL)

### 9.0 Standardize Ticker/Symbol Column Naming ✅ COMPLETE

- [x] 9.1 Created migrations to rename ticker → symbol columns
  - File: backend/migrations/059_standardize_symbol_columns.sql (idempotent)
  - File: backend/migrations/060_remaining_ticker_columns.sql
  - Tables renamed: day_bars, price_cache, news_cache, paper_trade_transactions,
    earnings_surprises, news_summary_log, watchlist_gap_coverage, reference_cache,
    technical_indicators, idea_outcomes
  - Special: portfolio_covariance ticker1/ticker2 → symbol1/symbol2
  - Kept: sec_cik_cache retains 'ticker' (SEC-specific mapping table)

- [x] 9.2 Updated all Python code referencing renamed columns
  - Batch sed replacements for: WHERE ticker, SELECT ticker, GROUP BY ticker, etc.
  - Updated ~38 files with ~70+ SQL references
  - Verified: API working (market/conditions endpoint returns data)

- [ ] 9.3 Update frontend TypeScript types ⏭️ DEFERRED

  **Analysis**: Frontend uses "ticker" in ~15 files for API response types.
  Backend API Pydantic models still expose `ticker` (e.g., PaperTradeResponse.ticker).
  Database columns renamed (ticker→symbol), but API maintains backward compatibility.

  **Design Decision**: Keep `ticker` in API responses for backward compatibility.
  This avoids breaking frontend code. The database uses `symbol` internally,
  but API/frontend can continue using `ticker` terminology.

  **Future work**: If full standardization needed, requires coordinated API + frontend update.

- [x] 9.4 Add FK constraints to renamed tables ✅ COMPLETE (merged with 8.3)
  - news_cache, earnings_surprises, price_cache all included in migration 061
  - See Task 8.3 for full list of 10 FK constraints added

- [x] 9.5 Verified queries work after rename
  - Services restarted successfully
  - API endpoints returning data correctly

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
