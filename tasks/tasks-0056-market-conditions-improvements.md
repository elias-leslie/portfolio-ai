# Task List: Market Conditions Card Improvements

**Source**: Comprehensive review of market intelligence card identified 15 improvements
**Complexity**: Complex
**Effort**: HIGH (28 hours total, phased implementation recommended)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 14:30
**Status**: Paused - Phase 1 (P0) Complete
**PAUSED**: 2025-11-13 16:00 (User request for fresh /clear + /do_it)
**Next**: Phase 2 (P1) - Task 5.0: Update S&P 500 Scoring Thresholds

<!-- PAUSED: 2025-11-13 16:00 | Context: 69% | Next: Task 5.0 - Update S&P 500 scoring thresholds in sentiment.py -->

---

## Summary

**Goal**: Fix critical data quality issues, improve user experience, and add advanced market intelligence features to the Market Conditions card. Address missing historical data, misleading timestamps, outdated thresholds, and add enhanced indicators.

**Approach**: Phased implementation across 4 priority levels (P0 → P1 → P2 → P3). P0 focuses on critical data integrity fixes (including automated scheduled task for historical data maintenance), P1 on user experience improvements, P2 on enhanced analytics, P3 on advanced features.

**Key Principle**: NO manual backfilling. All data maintenance via scheduled Celery tasks that run automatically.

**Scope Discovery**: Not required (detailed task list provided with specific file locations)

---

## Tasks

### Phase 1: Priority 0 - Critical Data Integrity (8 hours)

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

### Phase 2: Priority 1 - High Priority UX Improvements (6 hours)

### 5.0 Update S&P 500 Scoring Thresholds

- [ ] 5.1 Update `backend/app/market/sentiment.py:73-92`
  - [ ] Quick fix: Update hardcoded thresholds from 4000-4800 to 6000-6800 (2025 levels)
  - [ ] Add comment noting current S&P level and threshold reasoning
- [ ] 5.2 Document threshold update in CHANGELOG or migration notes
- [ ] 5.3 (Optional) Plan future enhancement: Percentile-based scoring using 252-day rolling window

### 6.0 Investigate Missing Fear & Greed Signal

- [ ] 6.1 Review `backend/app/tasks/indicator_tasks.py:221-451` (calculate_fear_greed task)
  - [ ] Trace logic for all 5 expected signals (VIX, Momentum, RSI, Credit spreads, Put/Call)
  - [ ] Check fear_greed_inputs table schema
- [ ] 6.2 Query fear_greed_inputs to verify data
  - [ ] `SELECT input_type, COUNT(*) FROM fear_greed_inputs GROUP BY input_type`
  - [ ] Identify which signal is missing
- [ ] 6.3 Add logging to identify missing signal source
- [ ] 6.4 Fix data source or add fallback logic for missing signal

### 7.0 Add Staleness Warning for Old Fear & Greed Data

- [ ] 7.1 Backend: Update `backend/app/api/market.py:207-336`
  - [ ] Calculate age of most recent fear_greed_daily entry
  - [ ] Add staleness flag to response (is_stale: bool, age_days: int)
  - [ ] Flag as stale if >2 days old
- [ ] 7.2 Frontend: Update `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Display warning banner if is_stale: true
  - [ ] Message: "⚠️ Fear & Greed data is {age_days} days old - next update at 03:00 UTC"
  - [ ] Style as yellow/orange warning banner at top of card

### 8.0 Remove Unused Code and Fields

- [ ] 8.1 Delete `frontend/components/portfolio/MarketConditions.tsx`
  - [ ] Verify component is truly unused (grep references)
  - [ ] Delete 300-line legacy component file
- [ ] 8.2 Update `backend/app/models/market_intelligence.py`
  - [ ] Remove vix.level field (always null, never used)
  - [ ] Remove health.sectors from MarketHealthScore (duplicate of sector_rotation)
- [ ] 8.3 Document removals in CHANGELOG

---

### Phase 3: Priority 2 - Enhanced Analytics (8 hours)

### 9.0 Add Trend Indicators to Scores

- [ ] 9.1 Backend: Update `backend/app/api/market.py`
  - [ ] Query fear_greed_daily for 7-day historical data
  - [ ] Calculate trend: score today vs 7 days ago
  - [ ] Add trend field to response (up/down/flat)
- [ ] 9.2 Backend: Update `backend/app/models/market_intelligence.py`
  - [ ] Add trend fields (Literal["up", "down", "flat"])
- [ ] 9.3 Frontend: Update `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Display visual trend arrows (↑↓) next to scores
  - [ ] Example: "Market Health: 66 ↑" (up from 60 last week)

### 10.0 Add 30-Day Sparkline Charts

- [ ] 10.1 Backend: Create new endpoint `/api/market/trends?days=30`
  - [ ] Return daily Market Health + Fear & Greed scores (30 days)
  - [ ] Query fear_greed_daily table for historical data
- [ ] 10.2 Frontend: Create `frontend/components/market/MarketTrendChart.tsx`
  - [ ] Use recharts or similar library for sparkline
  - [ ] Keep minimal/clean (small inline charts, not full-size)
- [ ] 10.3 Frontend: Integrate into `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Place between dual scores and main indicators sections
  - [ ] Fetch data from /api/market/trends endpoint
- [ ] 10.4 Update `frontend/lib/api/market.ts` (API client)

### 11.0 Optimize Fear & Greed Caching

- [ ] 11.1 Update `backend/app/api/market.py` or create new caching module
  - [ ] Implement Redis cache for fear_greed result (TTL = 1 hour or until next midnight)
  - [ ] Note: F&G updates once daily at 03:00 UTC, no need for frequent DB queries
- [ ] 11.2 Measure performance improvement
  - [ ] Log query time before/after caching
  - [ ] Document performance gain

### 12.0 Add Put/Call Ratio Indicator

**Note: Must use scheduled Celery task for data maintenance, not on-demand fetching.**

- [ ] 12.1 Research CBOE Put/Call ratio data source
  - [ ] Identify API or data feed for daily Put/Call ratio
  - [ ] Document data source and update frequency
- [ ] 12.2 Backend: Create scheduled Celery task for Put/Call data
  - [ ] Create task `backend/app/tasks/market_data_tasks.py::fetch_putcall_ratio`
  - [ ] Fetch daily Put/Call ratio from CBOE or alternative source
  - [ ] Store in database table (e.g., `market_indicators` with type='putcall_ratio')
  - [ ] Make idempotent (safe to run repeatedly)
  - [ ] Add to Celery beat schedule (daily at 04:30 UTC, after market data)
- [ ] 12.3 Backend: Add Put/Call query to `backend/app/api/market.py`
  - [ ] Query Put/Call data from database (don't fetch on-demand)
  - [ ] Add to intelligence endpoint response
- [ ] 12.4 Backend: Update `backend/app/market/intelligence.py`
  - [ ] Create enrich_putcall_indicator() helper
  - [ ] Signal logic: >1.0 = Bearish, 0.7-1.0 = Neutral, <0.7 = Bullish
- [ ] 12.5 Frontend: Update `frontend/components/market/MarketIntelligence.tsx`
  - [ ] Add Put/Call ratio to Key Indicators section
  - [ ] Add tooltip: "Ratio of put options (bets stocks go down) to call options (bets stocks go up)"

---

### Phase 4: Priority 3 - Advanced Features (6 hours)

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

**Final Verification:**
- [ ] All 4 phases complete
- [ ] No regressions in existing functionality
- [ ] Performance improvements measured (P2#11)
- [ ] Documentation updated (OPERATIONS.md, CHANGELOG)
- [ ] Clean: No Any types, single source of truth maintained
- [ ] Screenshots showing before/after improvements
