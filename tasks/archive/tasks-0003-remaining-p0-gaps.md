# Task List: Resolve Remaining P0 Capability Gaps

**Source**: /capability_it analysis - 3 remaining P0 gaps blocking full trading capability
**Complexity**: Complex (multiple components, new tables, API integrations)
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-03

---

## Summary

**Goal**: Eliminate all P0 blocking gaps to achieve full trading capability coverage
**Approach**: Create missing tables, implement data fetching tasks, integrate with existing APIs
**Scope Discovery**: Required for GAP-029 (bid/ask integration points)

**Remaining P0 Gaps:**
1. GAP-005: Analyst estimate revisions (no table exists)
2. GAP-029: Bid/ask spreads (need to extend price_cache)
3. GAP-052: PDT rule tracking (no tracking system)

**APIs Available**: FMP and Finnhub already configured and working

---

## Tasks

### 0.0 Scope Discovery for Bid/Ask Integration

- [ ] 0.1 Run Explore subagent to find price fetching code
  - Pattern: price_cache population, quote fetching, PriceData model
  - Goal: Understand where to add bid/ask fields
  - Output: Files that need modification for bid/ask support
- [ ] 0.2 Check FMP/Finnhub quote endpoints for bid/ask data
  - Verify: Do our existing API calls return bid/ask?
  - Check: app/sources/fmp_fetcher.py, app/sources/finnhub_fetcher.py
- [ ] 0.3 Document integration approach
  - Which source provides best bid/ask data?
  - Schema changes needed for price_cache

---

### 1.0 GAP-005: Analyst Estimate Revisions

**Current**: Only static recommendation_mean in reference_cache
**Target**: EPS estimate trends, upgrades/downgrades, revision magnitude

#### 1.1 Create analyst_revisions table

- [ ] 1.1.1 Design schema:
  ```sql
  analyst_revisions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    metric VARCHAR(50), -- 'eps_current_qtr', 'eps_next_qtr', 'revenue_current_qtr'
    period VARCHAR(20), -- 'Q1 2024', 'FY 2024'
    current_estimate DECIMAL,
    estimate_7d_ago DECIMAL,
    estimate_30d_ago DECIMAL,
    estimate_90d_ago DECIMAL,
    revision_direction VARCHAR(10), -- 'up', 'down', 'unchanged'
    revision_magnitude DECIMAL, -- percentage change
    num_analysts INTEGER,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, metric, period)
  )
  ```
- [ ] 1.1.2 Create migration file in app/storage/migrations/
- [ ] 1.1.3 Run migration

#### 1.2 Implement data fetcher

- [ ] 1.2.1 Add fetch_analyst_estimates() to app/sources/fmp_fetcher.py
  - Endpoint: /analyst-estimates/{symbol}
  - Parse: current, 7d, 30d, 90d estimates
- [ ] 1.2.2 Add calculate_revision_metrics() helper
  - Calculate: direction, magnitude from estimate changes
- [ ] 1.2.3 Add save_analyst_revisions() to storage layer

#### 1.3 Create Celery task

- [ ] 1.3.1 Create refresh_analyst_revisions task in app/tasks/
- [ ] 1.3.2 Add to beat schedule (daily at 07:00 UTC)
- [ ] 1.3.3 Test task manually for watchlist symbols

#### 1.4 Update requirements YAML

- [ ] 1.4.1 Change GAP-005 tables from `analyst_revisions (new table)` to `analyst_revisions`
- [ ] 1.4.2 Verify coverage updates after restart

---

### 2.0 GAP-029: Bid/Ask Spreads

**Current**: No bid/ask in PriceData model or price_cache
**Target**: Bid, ask, spread, bid_size, ask_size in price_cache

#### 2.1 Extend price_cache schema

- [ ] 2.1.1 Add columns to price_cache:
  ```sql
  ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS bid DECIMAL;
  ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS ask DECIMAL;
  ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS bid_size INTEGER;
  ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS ask_size INTEGER;
  ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS spread DECIMAL GENERATED ALWAYS AS (ask - bid) STORED;
  ```
- [ ] 2.1.2 Create migration file
- [ ] 2.1.3 Run migration

#### 2.2 Update PriceData model

- [ ] 2.2.1 Add bid/ask fields to PriceData in app/models/ or app/api/
- [ ] 2.2.2 Update any TypedDict or Pydantic models

#### 2.3 Update price fetcher

- [ ] 2.3.1 Modify fetch_quote() in app/sources/ to extract bid/ask
  - FMP: Check /quote endpoint for bid/ask fields
  - Fallback: If not available, leave NULL
- [ ] 2.3.2 Update save_price_cache() to store bid/ask
- [ ] 2.3.3 Test with a few tickers

#### 2.4 Update requirements YAML

- [ ] 2.4.1 Change GAP-029 tables to `price_cache`
- [ ] 2.4.2 Verify coverage updates

---

### 3.0 GAP-052: PDT Rule Tracking

**Current**: No pattern day trader tracking
**Target**: Track day trades per 5-day window, alert at 3/5

#### 3.1 Create pdt_tracking table

- [ ] 3.1.1 Design schema:
  ```sql
  pdt_day_trades (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES portfolio_accounts(id),
    trade_date DATE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    buy_order_id VARCHAR(50),
    sell_order_id VARCHAR(50),
    is_day_trade BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
  )
  ```
- [ ] 3.1.2 Create migration file
- [ ] 3.1.3 Run migration

#### 3.2 Implement PDT detection logic

- [ ] 3.2.1 Create app/analytics/pdt_tracking.py:
  - count_day_trades_5d(account_id) -> int
  - is_day_trade(buy_time, sell_time, symbol) -> bool
  - check_pdt_limit(account_id) -> PDTStatus (ok, warning, blocked)
- [ ] 3.2.2 Add PDT check to order execution flow
  - Warn at 3 day trades in 5 days
  - Block at 4 (would trigger PDT status)
- [ ] 3.2.3 Add account_value check (PDT only applies if <$25k)

#### 3.3 Integrate with paper trading

- [ ] 3.3.1 Update paper trade order execution to log day trades
- [ ] 3.3.2 Add PDT status to portfolio dashboard API
- [ ] 3.3.3 Add frontend warning badge if approaching limit

#### 3.4 Update requirements YAML

- [ ] 3.4.1 Add `pdt_day_trades` table to GAP-052
- [ ] 3.4.2 Verify coverage updates

---

### 4.0 Final Verification

- [ ] 4.1 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
- [ ] 4.2 Trigger capability scan: `curl -s -X POST http://localhost:8000/api/capabilities/scan`
- [ ] 4.3 Verify P0 gaps = 0: `curl -s http://localhost:8000/api/gaps/summary | jq .p0_gaps`
- [ ] 4.4 Verify coverage improved: `curl -s http://localhost:8000/api/gaps/summary | jq .avg_coverage_pct`
- [ ] 4.5 Screenshot capabilities page: `node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/capabilities /tmp/p0-complete.png`

---

## Verification

- [ ] Functional: All 3 P0 gaps resolved, data populating
- [ ] Tests: New tables have data, tasks running successfully
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified
- [ ] Coverage: P0 gaps = 0, avg coverage > 55%

---

## Notes

- FMP API already has analyst estimates endpoint
- Bid/ask may require Polygon subscription for real-time (FMP has delayed quotes)
- PDT tracking only applies to margin accounts <$25k (cash accounts exempt)
- Consider adding PDT exemption flag to portfolio_accounts for cash accounts
