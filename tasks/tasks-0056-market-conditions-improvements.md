# Task List: Market Conditions Card Improvements

**Source**: Comprehensive review of market intelligence card identified 15 improvements + CBOE enhancements
**Complexity**: Complex
**Effort**: HIGH (36 hours total, phased implementation recommended)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 14:30
**Updated**: 2025-11-13 (Added Phase 5 + Phase 6 for CBOE enhancements)
**Status**: Phase 3 (P2) COMPLETE, Phase 5 (CBOE Status) NEXT
**PAUSED**: 2025-11-13 18:22 (Context 88% - natural pause point after Task 12 refactor)
**Commits**:
  - a5fccc2 (refactor: switch Put/Call ratio from yfinance to official CBOE source)
  - 35203dc (feat: add Put/Call Ratio indicator to Market Conditions card)
  - 8b0f56a (feat: market conditions Phase 2 (P1) - UX improvements)
  - 338541e (refactor: make S&P 500 scoring dynamic with percentile-based approach)
  - ae153ce (feat: add 7-day trend indicators to Fear & Greed scores)
  - a66e7ce (perf: add Redis caching to Fear & Greed queries)
  - 0cfdd95 (feat: add 30-day sparkline charts to market intelligence)
  - 7c8a933 (fix: use theme-aware colors for sparkline visibility on dark mode)
  - 65be0e8 (fix: resolve sparkline rendering and visibility issues)
  - 7635689 (fix: actually fix sparkline visibility - use var(--color-gain) not hsl())
**Completed**: Phase 1 (P0) + Phase 2 (P1) + Phase 3 (P2) ✅ ALL COMPLETE
**Next**: **Phase 5 (CBOE Status Integration) - DO THIS FIRST**, then Phase 6 (CBOE Options Intelligence)

<!-- NEXT: Phase 5 - CBOE Status Page Integration (missing from initial implementation) -->

---

## Summary

**Goal**: Fix critical data quality issues, improve user experience, add advanced market intelligence features to the Market Conditions card, and enhance CBOE options data with comprehensive status monitoring and additional metrics.

**Approach**: Phased implementation across 6 priority levels (P0 → P1 → P2 → **P_CBOE_STATUS** → **P_CBOE_INTEL** → P3). P0 focuses on critical data integrity fixes, P1 on user experience improvements, P2 on enhanced analytics, **P_CBOE_STATUS on monitoring existing CBOE integration**, **P_CBOE_INTEL on adding Most Active Options intelligence**, P3 on advanced features.

**Key Principle**: NO manual backfilling. All data maintenance via scheduled Celery tasks that run automatically.

**Scope Discovery**: Not required (detailed task list provided with specific file locations)

---

## Tasks

### Phase 1: Priority 0 - Critical Data Integrity (8 hours) ✅ COMPLETE

### 1.0 Create Scheduled Historical Data Maintenance Task ✅ COMPLETE

**CRITICAL: NO MANUAL BACKFILLING. Create a scheduled Celery task that automatically maintains data.**

- [x] 1.1 Create scheduled Celery task `backend/app/tasks/market_data_tasks.py::maintain_historical_market_data`
  - [x] Task logic: Check day_bars for each required symbol
  - [x] If missing or <252 days: Backfill using existing ingest_historical_ohlcv task
  - [x] Target symbols: ^GSPC, ^VIX, ^TNX, DX-Y.NYB (main indicators)
  - [x] Target symbols: XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLU, XLRE, XLB, XLC (sectors)
  - [x] Make idempotent (safe to run repeatedly)
  - [x] Add comprehensive logging (symbols checked, records added, errors)
- [x] 1.2 Add task to Celery beat schedule (run daily at 04:00 UTC, after market close)
  - [x] Update `backend/app/celery_app.py` beat_schedule
  - [x] Schedule after Fear & Greed calculation (03:00 UTC)
  - [x] Also updated `refresh-daily-ohlcv` to include market indicators
- [x] 1.3 Test task execution (manual trigger for immediate testing)
  - [x] Tested backfill via: `celery -A app.celery_app call ingest_historical_ohlcv`
  - [x] Verified backfill completes for all symbols (3,887 rows inserted)
  - [x] Verified record counts: All symbols have 259-261 days each ✅
- [x] 1.4 Document in OPERATIONS.md
  - [x] Documented automated maintenance approach
  - [x] Documented manual trigger command for initial setup
  - [x] Noted: Tasks run automatically daily, no manual intervention needed

### 2.0 Fix Misleading Last Updated Timestamp ✅ COMPLETE

- [x] 2.1 Backend: Update `backend/app/api/market.py:239-244`
  - [x] Approach: Use Fear & Greed as_of_date (already correct)
  - [x] Added clarifying comments about what timestamp represents
  - [x] Timestamp represents market data date, not cache date
- [x] 2.2 Frontend: Update `frontend/components/market/MarketIntelligence.tsx:201-205`
  - [x] Changed label from "Updated" to "Market Data as of"
  - [x] Clarifies that timestamp shows data age, not cache age
  - [x] Now shows "Market Data as of 3 days ago" (clear and accurate)

### 3.0 Add Daily Change Percentages for Main Indicators ✅ COMPLETE

- [x] 3.1 Backend: Update `backend/app/api/market.py`
  - [x] Added calculate_daily_change_pct() helper function
  - [x] Calculate daily changes from day_bars table for ^GSPC, ^VIX, ^TNX, DX-Y.NYB
  - [x] Query uses LIMIT 1 OFFSET 1 to get previous day's close
  - [x] Handle missing data gracefully (returns None if no historical data)
- [x] 3.2 Backend: Update `backend/app/models/market_intelligence.py`
  - [x] Models already had change_pct fields (Optional[float])
  - [x] Updated enrichment functions to accept and use change_pct parameter
- [x] 3.3 Frontend: Update `frontend/components/market/LabeledIndicator.tsx`
  - [x] Added changePct prop to component
  - [x] Display as "+6.19%" or "-1.24%" with proper formatting
  - [x] Added color coding (text-gain for positive, text-loss for negative)
  - [x] Positioned next to current values with items-baseline alignment
  - [x] Pass change_pct from all four indicators (VIX, S&P 500, TNX, DXY)

### 4.0 Fix Sector Change Calculation ✅ COMPLETE (Already Fixed)

- [x] 4.1 Verified `backend/app/api/market.py:94-143` (fetch_sector_data_with_changes)
  - [x] Already using ONLY day_bars historical data (no cache comparison)
  - [x] Window function query with ROW_NUMBER() gets 2nd most recent close
  - [x] Returns None for change_pct if no historical data available
  - [x] Added comments explaining why day_bars is used instead of cache comparison

---

### Phase 2: Priority 1 - High Priority UX Improvements (6 hours) ✅ COMPLETE

### 5.0 Update S&P 500 Scoring Thresholds ✅ COMPLETE (Enhanced with Dynamic Approach)

**Initial Implementation (commit 8b0f56a):**
- [x] 5.1 Update `backend/app/market/sentiment.py:73-92`
  - [x] Updated hardcoded thresholds from 4000-4800 to 6000-6800 (2025 levels)
  - [x] Added comment noting threshold reasoning

**Enhanced Implementation (commit 338541e):**
- [x] 5.2 **Implemented percentile-based dynamic scoring** (no more manual updates!)
  - [x] Calculates where current S&P sits in 252-day rolling window
  - [x] Scores based on percentile rank (≥80% = Bullish, 60-80% = Bullish, 40-60% = Neutral, <40% = Bearish)
  - [x] Automatically adapts to any market environment
  - [x] Falls back to price-based thresholds only if historical data unavailable
  - [x] Verified working: Current S&P 6772.88 at 95.63rd percentile → 75 score (Bullish) ✅

### 6.0 Investigate Missing Fear & Greed Signal ✅ COMPLETE

**Finding**: No missing signal. Task description mentioned 5 signals, but implementation correctly uses 4 components (VIX, Momentum, RSI, Credit Spread). All 4 working correctly.

- [x] 6.1 Review `backend/app/tasks/indicator_tasks.py:221-451` (calculate_fear_greed task)
  - [x] Traced logic - uses 4 components (VIX, Momentum, RSI, Credit Spread)
  - [x] Checked fear_greed_inputs table schema - has put_call_ratio and breadth_pct columns but not used in calculation
- [x] 6.2 Query fear_greed_inputs to verify data
  - [x] Verified all 4 components have data: VIX ✅, Momentum ✅, RSI ✅, Credit Spread ✅
  - [x] Checked fear_greed_components table - all 4 percentiles calculated correctly
- [x] 6.3 Verified fear_greed_daily table - composite scores calculated correctly
- [x] 6.4 Conclusion: No fixes needed - all 4 components working as designed

### 7.0 Add Staleness Warning for Old Fear & Greed Data ✅ COMPLETE

- [x] 7.1 Backend: Updated `backend/app/market/fear_greed_stub.py`
  - [x] Added is_stale and age_days fields to FearGreedReading class
  - [x] Calculate age using (today - as_of_date).days
  - [x] Flag as stale if >2 days old
- [x] 7.2 Backend: Updated `backend/app/models/market_intelligence.py`
  - [x] Added is_stale and age_days fields to FearGreedScore model
- [x] 7.3 Backend: Updated `backend/app/api/market.py`
  - [x] Pass is_stale and age_days to FearGreedScore response
- [x] 7.4 Frontend: Updated `frontend/lib/api/market.ts`
  - [x] Added is_stale and age_days to FearGreedScore interface
- [x] 7.5 Frontend: Updated `frontend/components/market/MarketIntelligence.tsx`
  - [x] Display warning banner if is_stale: true
  - [x] Message: "⚠️ Fear & Greed data is {age_days} days old - next update at 03:00 UTC"
  - [x] Style as yellow/orange warning banner with icon

### 8.0 Remove Unused Code and Fields ✅ COMPLETE

- [x] 8.1 Delete `frontend/components/portfolio/MarketConditions.tsx`
  - [x] Verified component is truly unused (no imports, no JSX usage)
  - [x] Deleted 299-line legacy component file
- [x] 8.2 Verified `backend/app/models/market_intelligence.py`
  - [x] vix.level field - Already removed or never existed in current structure
  - [x] health.sectors field - Already removed, sector rotation properly separated
- [x] 8.3 Document removals (included in commit message)

---

### Phase 3: Priority 2 - Enhanced Analytics (8 hours) ✅ COMPLETE

### 9.0 Add Trend Indicators to Scores ✅ COMPLETE

- [x] 9.1 Backend: Update `backend/app/api/market.py`
  - [x] Query fear_greed_daily for 7-day historical data
  - [x] Calculate trend: score today vs 7 days ago
  - [x] Add trend field to response (up/down/flat)
- [x] 9.2 Backend: Update `backend/app/models/market_intelligence.py`
  - [x] Add trend fields (Literal["up", "down", "flat"])
- [x] 9.3 Frontend: Update `frontend/components/market/MarketIntelligence.tsx`
  - [x] Display visual trend arrows (↑↓) next to scores
  - [x] Example: "Market Health: 66 ↑" (up from 60 last week)

### 10.0 Add 30-Day Sparkline Charts ✅ COMPLETE

- [x] 10.1 Backend: Create new endpoint `/api/market/trends?days=30`
  - [x] Return daily Market Health + Fear & Greed scores (30 days)
  - [x] Query fear_greed_daily table for historical data
- [x] 10.2 Frontend: Create `frontend/components/market/MarketTrendChart.tsx`
  - [x] Use recharts or similar library for sparkline
  - [x] Keep minimal/clean (small inline charts, not full-size)
- [x] 10.3 Frontend: Integrate into `frontend/components/market/MarketIntelligence.tsx`
  - [x] Place between dual scores and main indicators sections
  - [x] Fetch data from /api/market/trends endpoint
- [x] 10.4 Update `frontend/lib/api/market.ts` (API client)

### 11.0 Optimize Fear & Greed Caching ✅ COMPLETE

- [x] 11.1 Update `backend/app/api/market.py` or create new caching module
  - [x] Implement Redis cache for fear_greed result (TTL = 1 hour or until next midnight)
  - [x] Note: F&G updates once daily at 03:00 UTC, no need for frequent DB queries
- [x] 11.2 Measure performance improvement
  - [x] Log query time before/after caching
  - [x] Document performance gain

### 12.0 Add Put/Call Ratio Indicator ✅ COMPLETE (REFACTORED TO CBOE)

**Data Source:** CBOE Official Daily Statistics (https://www.cboe.com/us/options/market_statistics/daily/)

**Refactor:** Initially implemented with yfinance (open interest), which was 51% inaccurate.
Refactored to scrape official CBOE page using Playwright for volume-based ratios (gold standard).

- [x] 12.1 Research & Implement CBOE scraper (`backend/app/sources/cboe_source.py`)
  - [x] Tested CBOE CSV (dead - ends Oct 2019)
  - [x] Tested CBOE HTML (live - daily updates) ✅
  - [x] Uses Playwright execute.js to render JavaScript page
  - [x] Parses TOTAL, INDEX, EQUITY, SPX+SPXW ratios
  - [x] Primary metric: SPX+SPXW (S&P 500 specific)
- [x] 12.2 Backend: Updated `fetch_putcall_ratio` task
  - [x] Replaced yfinance with CBOESource.fetch_put_call_ratios()
  - [x] Execution time: ~10s (vs 90s for yfinance)
  - [x] Stores SPX+SPXW ratio in fear_greed_inputs.put_call_ratio
  - [x] Source tracking: `{"put_call_ratio": "cboe_daily_statistics"}`
- [x] 12.3 Backend: API integration (`/api/market/intelligence`)
  - [x] Already complete from initial implementation
- [x] 12.4 Backend: Enrichment helpers
  - [x] Already complete from initial implementation
- [x] 12.5 Frontend: Display in Market Conditions card
  - [x] Already complete from initial implementation

**Accuracy Validation (Nov 12, 2025):**
- CBOE Official: SPX+SPXW = 1.04, Total = 0.78
- Our Implementation: 1.04 ✅ (exact match)
- Previous yfinance: 1.57 ❌ (51% error)

**⚠️ INCOMPLETE: Status page monitoring NOT implemented** → See Phase 5 below

---

### Phase 5: CBOE Status Page Integration (2 hours) ⏸️ **DO THIS FIRST**

**Priority**: **P_CBOE_STATUS** (must complete BEFORE Phase 6)

**Issue**: Task 12.0 added CBOE put/call ratio but never integrated with status page monitoring. CBOE source is not visible on status page (no Data Sources entry, no Table Freshness entry).

**Goal**: Make CBOE source fully observable on status page with health monitoring and data freshness tracking.

### 16.0 Add CBOE Source to Status Page Monitoring

- [ ] 16.1 Backend: Integrate cboe_source.py with SourceMetricsManager
  - [ ] Import SourceMetricsManager in `backend/app/sources/cboe_source.py`
  - [ ] Add metrics tracking to CBOESource class (`__init__` and `fetch_put_call_ratios`)
  - [ ] Wrap `fetch_put_call_ratios()` with metrics tracking:
    - [ ] Initialize metric: `self.metrics_manager.initialize_metric("cboe_daily_statistics")`
    - [ ] Record success with latency: `record_success(source_name, latency_ms)`
    - [ ] Record failures: `record_failure(source_name, error)`
    - [ ] Save to DB after each fetch: `save_to_db(source_name)`
  - [ ] Add get_health_status() method (already exists, verify it's complete)
  - [ ] Pattern reference: See `backend/app/sources/base.py` and `backend/app/sources/source_metrics_manager.py`

- [ ] 16.2 Backend: Add CBOE to source_performance table
  - [ ] Verify `source_performance` table schema supports CBOE
  - [ ] Manual verification: Check if CBOE appears after fetch task runs
  - [ ] SQL query: `SELECT * FROM source_performance WHERE source_name = 'cboe_daily_statistics';`

- [ ] 16.3 Backend: Add fear_greed_inputs to Table Freshness monitoring
  - [ ] Update table_registry to include fear_greed_inputs
  - [ ] File: `backend/app/storage/schema.py` or table_registry insert SQL
  - [ ] Set expected_refresh_hours = 24 (daily updates at 03:00 UTC)
  - [ ] Verify table appears in `/api/status/table-freshness` response

- [ ] 16.4 Frontend: Verify CBOE appears on Status Page
  - [ ] Navigate to http://localhost:3000/status (or deployed URL)
  - [ ] **Data Sources Card** should show "CBOE Daily Statistics" with:
    - [ ] Status badge (Healthy/Degraded/Down)
    - [ ] Last success timestamp
    - [ ] Success rate %
    - [ ] Avg latency ms
  - [ ] **Data Freshness Card** should show "Fear Greed Inputs" table with:
    - [ ] Fresh/Stale/Critical badge
    - [ ] Last updated timestamp
    - [ ] Age in hours/days

- [ ] 16.5 Test CBOE health monitoring end-to-end
  - [ ] Trigger put/call fetch manually: `celery -A app.celery_app call app.tasks.market_data_tasks.fetch_putcall_ratio`
  - [ ] Verify source_performance updated: `SELECT * FROM source_performance WHERE source_name = 'cboe_daily_statistics';`
  - [ ] Check status page shows healthy CBOE source
  - [ ] Simulate failure (disconnect network or break URL) and verify status changes to "Down"
  - [ ] Restore and verify recovery

**Verification:**
```bash
# Check CBOE in source_performance table
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT source_name, success_count, failure_count, last_success_at,
       (success_count::float / NULLIF(success_count + failure_count, 0) * 100) as success_rate_pct
FROM source_performance
WHERE source_name = 'cboe_daily_statistics';"

# Check fear_greed_inputs freshness
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT as_of_date, put_call_ratio,
       EXTRACT(EPOCH FROM (NOW() - as_of_date::timestamp)) / 3600 as age_hours
FROM fear_greed_inputs
ORDER BY as_of_date DESC LIMIT 5;"

# Check table_registry includes fear_greed_inputs
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT table_name, expected_refresh_hours
FROM table_registry
WHERE table_name = 'fear_greed_inputs';"
```

---

### Phase 6: CBOE Options Intelligence Enhancements (6 hours)

**Priority**: **P_CBOE_INTEL** (complete AFTER Phase 5)

**Goal**: Add Most Active Options metrics and Put/Call historical context for richer market sentiment intelligence.

**Data Strategy**: Store **aggregated daily metrics** (not raw contracts) for trend analysis over 90 days.

### 17.0 Database Schema for Options Market Metrics

- [ ] 17.1 Create migration for options_market_metrics table
  - [ ] File: `backend/migrations/0XX_options_market_metrics.sql`
  - [ ] Schema:
    ```sql
    CREATE TABLE IF NOT EXISTS options_market_metrics (
        as_of_date DATE PRIMARY KEY,
        most_active_call_pct DECIMAL(5,2),      -- % of top 25 that are calls (sentiment)
        near_term_pct DECIMAL(5,2),              -- % expiring within 30 days (event positioning)
        concentration_pct DECIMAL(5,2),          -- % of volume in top 5 vs top 25 (conviction)
        sector_weights JSONB,                    -- {"tech": 45, "financials": 25, ...}
        source_timestamp TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX idx_options_metrics_date ON options_market_metrics(as_of_date DESC);
    ```
  - [ ] Add to table_registry with expected_refresh_hours = 24

- [ ] 17.2 Apply migration
  - [ ] Run migration on local dev database
  - [ ] Verify table created: `\d options_market_metrics` in psql
  - [ ] Verify table_registry entry

### 18.0 CBOE Most Active Options Scraper

- [ ] 18.1 Create new source module
  - [ ] File: `backend/app/sources/cboe_most_active.py`
  - [ ] Class: `CBOEMostActiveSource`
  - [ ] Method: `fetch_most_active_metrics() -> dict[str, Any]`
  - [ ] Implementation:
    - [ ] Uses Playwright to scrape https://www.cboe.com/us/options/market_statistics/most_active/
    - [ ] Parses top 25 contracts (Symbol, Strike, Expiration, Call/Put, Volume)
    - [ ] Calculates 4 aggregate metrics:
      - [ ] `most_active_call_pct` = (call count / 25) * 100
      - [ ] `near_term_pct` = (contracts expiring ≤30 days / 25) * 100
      - [ ] `concentration_pct` = (top 5 volume / total top 25 volume) * 100
      - [ ] `sector_weights` = map symbols to sectors, calculate % distribution
    - [ ] Returns dict: `{as_of_date, most_active_call_pct, near_term_pct, concentration_pct, sector_weights, source_timestamp}`
  - [ ] Pattern reference: `backend/app/sources/cboe_source.py` (use same Playwright approach)

- [ ] 18.2 Add SourceMetricsManager tracking
  - [ ] Track as source_name = "cboe_most_active"
  - [ ] Record success/failure/latency for each fetch
  - [ ] Save metrics to source_performance table

- [ ] 18.3 Unit tests
  - [ ] File: `backend/tests/unit/sources/test_cboe_most_active.py`
  - [ ] Test metric calculation logic (mock Playwright response)
  - [ ] Test error handling (empty page, timeout, parse failures)

### 19.0 Scheduled Task for Options Activity Metrics

- [ ] 19.1 Create Celery task
  - [ ] File: `backend/app/tasks/market_data_tasks.py`
  - [ ] Task: `fetch_options_activity_metrics()`
  - [ ] Implementation:
    - [ ] Calls CBOEMostActiveSource.fetch_most_active_metrics()
    - [ ] Stores result in options_market_metrics table
    - [ ] Uses INSERT ... ON CONFLICT (as_of_date) DO UPDATE
    - [ ] Idempotent (safe to re-run for same date)
  - [ ] Add comprehensive logging (metrics calculated, DB write, errors)

- [ ] 19.2 Add to Celery beat schedule
  - [ ] File: `backend/app/celery_app.py`
  - [ ] Schedule: Daily at 16:15 ET (21:15 UTC) - after market close (16:00 ET)
  - [ ] Add to beat_schedule dict:
    ```python
    'fetch-options-activity': {
        'task': 'app.tasks.market_data_tasks.fetch_options_activity_metrics',
        'schedule': crontab(hour=21, minute=15),  # 4:15 PM ET
    }
    ```

- [ ] 19.3 Test task execution
  - [ ] Manual trigger: `celery -A app.celery_app call app.tasks.market_data_tasks.fetch_options_activity_metrics`
  - [ ] Verify data inserted: `SELECT * FROM options_market_metrics ORDER BY as_of_date DESC LIMIT 5;`
  - [ ] Verify source_performance updated for "cboe_most_active"

### 20.0 Put/Call Ratio Historical Context

- [ ] 20.1 Backend: Add historical context calculation
  - [ ] File: `backend/app/market/intelligence.py` or new file `backend/app/market/options_context.py`
  - [ ] Function: `calculate_putcall_context(current_ratio: float, as_of_date: date) -> dict`
  - [ ] Implementation:
    - [ ] Query fear_greed_inputs for last 90 days of put_call_ratio
    - [ ] Calculate 7-day trend: `(current - 7d_ago) / 7d_ago * 100`
    - [ ] Calculate percentile rank: where current sits in 90-day distribution
    - [ ] Return: `{trend: "up"|"down"|"flat", trend_pct: float, percentile_rank: int}`

- [ ] 20.2 Backend: Update market intelligence API
  - [ ] File: `backend/app/api/market.py`
  - [ ] Endpoint: `/api/market/intelligence`
  - [ ] Add put/call context to putcall indicator response:
    ```python
    putcall = {
        "value": 0.95,
        "change_pct": None,  # Daily change not meaningful for this
        "label": "Put/Call Ratio",
        "signal": "Bearish",
        "emoji": "🔴",
        "last_updated": "...",
        "context": {
            "trend": "up",         # ↑ NEW
            "trend_pct": 12.3,     # ↑ NEW (up 12.3% over 7 days)
            "percentile_rank": 78  # ↑ NEW (78th percentile = elevated)
        }
    }
    ```

- [ ] 20.3 Frontend: Display put/call context
  - [ ] File: `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Update putcall indicator display:
    - [ ] Add trend arrow: ↑ or ↓ next to value
    - [ ] Add percentile badge: "78th percentile (elevated)" in tooltip
  - [ ] Update TypeScript interfaces in `frontend/lib/api/market.ts`

### 21.0 Options Activity Metrics Display

- [ ] 21.1 Backend: Add options activity to market intelligence API
  - [ ] File: `backend/app/api/market.py`
  - [ ] Add new field to `/api/market/intelligence` response:
    ```python
    {
        "narrative": {...},
        "market_health": {...},
        "fear_greed": {...},
        "indicators": {...},
        "sector_rotation": {...},
        "options_activity": {  # ↑ NEW
            "near_term_pct": 72,
            "near_term_signal": "High",  # High/Normal/Low
            "concentration_pct": 88,
            "concentration_signal": "Focused",  # Focused/Balanced/Dispersed
            "top_sectors": [
                {"sector": "Technology", "weight_pct": 45},
                {"sector": "Financials", "weight_pct": 25},
                {"sector": "Healthcare", "weight_pct": 15}
            ],
            "last_updated": "2025-11-13T21:15:00Z"
        }
    }
    ```
  - [ ] Query options_market_metrics for latest date
  - [ ] Calculate signal thresholds:
    - [ ] near_term_pct: >65% = High, 45-65% = Normal, <45% = Low
    - [ ] concentration_pct: >80% = Focused, 50-80% = Balanced, <50% = Dispersed

- [ ] 21.2 Frontend: Display options activity metrics
  - [ ] File: `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Add new section after main indicators:
    ```
    Options Positioning:
    - Near-term Focus: 72% ↑ (event uncertainty)
    - Market Positioning: Concentrated (88%)
    - Top Sectors: Tech (45%), Financials (25%), Healthcare (15%)
    ```
  - [ ] Use existing LabeledIndicator component pattern
  - [ ] Add tooltips explaining each metric

- [ ] 21.3 Frontend: Update TypeScript interfaces
  - [ ] File: `frontend/lib/api/market.ts`
  - [ ] Add OptionsActivityMetrics interface
  - [ ] Update MarketIntelligenceResponse to include options_activity

### 22.0 Plain-Language Narrative Enhancements

- [ ] 22.1 Backend: Add options activity to narrative generation
  - [ ] File: `backend/app/market/plain_language.py` or `backend/app/market/narrative.py`
  - [ ] Add templates for options context:
    - [ ] "Options traders are **increasingly defensive** ↑ (put/call up 12% this week)"
    - [ ] "Heavy near-term options activity suggests **event uncertainty**"
    - [ ] "Concentrated positioning in tech sector (**55% of activity**)"
    - [ ] "Put/call ratio at **78th percentile** - elevated fear"
  - [ ] Integrate into existing narrative generation logic

- [ ] 22.2 Test narrative generation
  - [ ] Verify narratives update with new options metrics
  - [ ] Check different scenarios: bullish, bearish, neutral, concentrated, dispersed

---

### Phase 4: Priority 3 - Advanced Features (6 hours) [DEFERRED - Optional]

### 13.0 Market Breadth Indicator (New Card)

**Note: Must use scheduled Celery task for data maintenance, not on-demand calculation.**

- [ ] 13.1 Backend: Create scheduled Celery task for breadth calculations
  - [ ] Create task `backend/app/tasks/market_data_tasks.py::calculate_market_breadth`
  - [ ] Calculate S&P 500 Advance/Decline ratio (requires constituent price data)
  - [ ] Calculate % of stocks above 200-day moving average
  - [ ] Calculate % of stocks making new 52-week highs vs lows
  - [ ] Store results in database table (e.g., `market_breadth` with date, metric, value)
  - [ ] Make idempotent (safe to run repeatedly)
  - [ ] Add to Celery beat schedule (daily at 05:00 UTC, after market data + Put/Call)
- [ ] 13.2 Backend: Create endpoint `/api/market/breadth`
  - [ ] Query breadth metrics from database (don't calculate on-demand)
  - [ ] Return most recent breadth data with timestamp
- [ ] 13.3 Frontend: Create `frontend/components/market/MarketBreadth.tsx`
  - [ ] Simple gauge: "Broad participation" vs "Narrow leadership"
  - [ ] Display all three breadth metrics
- [ ] 13.4 Integrate below Market Conditions card on dashboard

### 14.0 Correlation Matrix (Optional Expandable Section)

- [ ] 14.1 Backend: Update `backend/app/api/market.py`
  - [ ] Calculate correlations using 30-day rolling window
  - [ ] VIX vs S&P 500 (should be negative)
  - [ ] Dollar vs International stocks
  - [ ] Yields vs Growth stocks
- [ ] 14.2 Frontend: Create `frontend/components/market/CorrelationMatrix.tsx`
  - [ ] Expandable section with correlation heatmap
  - [ ] Color coding: Strong positive (green), neutral (yellow), negative (red)
- [ ] 14.3 Integrate as expandable section in MarketIntelligence card

### 15.0 Volatility Regime Indicator

- [ ] 15.1 Backend: Update `backend/app/market/intelligence.py`
  - [ ] Add regime classification logic
  - [ ] Categories: Low Vol (VIX <15), Normal Vol (15-20), High Vol (>20)
  - [ ] Include strategy recommendations for each regime
- [ ] 15.2 Frontend: Update `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Display colored chip next to VIX value
  - [ ] Tooltip with strategy recommendations
  - [ ] Recommendations:
    - Low Vol: "Trend-following strategies work"
    - Normal Vol: "Balanced approach"
    - High Vol: "Mean reversion, defensive positioning"

---

## Verification

**After Each Phase:**
- [ ] Functional: All phase requirements met, zero bugs
- [ ] Services: Restart and verify (bash ~/portfolio-ai/scripts/restart.sh)
- [ ] Tests: Run backend tests (cd ~/portfolio-ai/backend && pytest tests/ -v)
- [ ] Quality: Run lint checks (~/portfolio-ai/scripts/lint.sh passes)
- [ ] Manual: Test UI changes with screenshots
- [ ] Data: Verify database queries return expected data

**Phase-Specific Verification:**

**P0 Verification:**
```bash
# Verify scheduled task exists in Celery beat schedule
celery -A app.celery_app inspect scheduled

# Manually trigger task for immediate testing (task will also run automatically daily at 04:00 UTC)
celery -A app.celery_app call app.tasks.market_data_tasks.maintain_historical_market_data

# After task runs, verify 252 days per symbol
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT ticker, COUNT(*) as days, MIN(date), MAX(date)
FROM day_bars
WHERE ticker IN ('^GSPC', '^VIX', '^TNX', 'DX-Y.NYB',
                 'XLK', 'XLF', 'XLE', 'XLV', 'XLY', 'XLP',
                 'XLI', 'XLU', 'XLRE', 'XLB', 'XLC')
GROUP BY ticker
ORDER BY ticker;"
```

**P1 Verification:**
```sql
-- Verify Fear & Greed signals count
SELECT input_type, COUNT(*)
FROM fear_greed_inputs
GROUP BY input_type;
```

**Phase 5 (CBOE Status) Verification:**
```bash
# Check CBOE appears in source_performance
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT source_name, success_count, failure_count,
       last_success_at, avg_latency_ms
FROM source_performance
WHERE source_name IN ('cboe_daily_statistics', 'cboe_most_active');"

# Check fear_greed_inputs in table_registry
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT table_name, expected_refresh_hours
FROM table_registry
WHERE table_name = 'fear_greed_inputs';"

# Verify status page shows CBOE
# Visit http://localhost:3000/status
# Check Data Sources card has "CBOE Daily Statistics" with Healthy status
# Check Data Freshness card has "Fear Greed Inputs" with Fresh status
```

**Phase 6 (CBOE Intel) Verification:**
```bash
# Check options_market_metrics table has data
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT as_of_date, most_active_call_pct, near_term_pct,
       concentration_pct, sector_weights
FROM options_market_metrics
ORDER BY as_of_date DESC LIMIT 5;"

# Verify beat schedule includes new task
celery -A app.celery_app inspect scheduled | grep -i options

# Verify cboe_most_active in source_performance
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "
SELECT * FROM source_performance WHERE source_name = 'cboe_most_active';"

# Test market intelligence API includes new fields
curl http://localhost:8000/api/market/intelligence | jq '.options_activity'
```

**Final Verification:**
- [ ] All 6 phases complete (P0, P1, P2, P5, P6, P3 optional)
- [ ] No regressions in existing functionality
- [ ] Performance improvements measured (P2#11)
- [ ] Documentation updated (OPERATIONS.md, CHANGELOG)
- [ ] Clean: No Any types, single source of truth maintained
- [ ] Screenshots showing before/after improvements
- [ ] Status page shows all CBOE sources healthy
- [ ] Market Conditions card shows enhanced options intelligence

---

## Summary of Changes

**Phase 5 (CBOE Status)**: Fixes missing status page integration for existing CBOE put/call ratio feature. Makes CBOE observable and monitorable.

**Phase 6 (CBOE Intel)**: Adds Most Active Options metrics (aggregated daily snapshots) and Put/Call historical context (trends, percentiles) for richer sentiment analysis.

**Combined Value**:
- **Observability**: Know when CBOE is down/stale before users notice
- **Intelligence**: Understand WHERE traders are positioning (time horizon, sectors, conviction)
- **Context**: "Put/call at 0.95 ↑ (78th percentile - elevated fear)" vs just "0.95"
