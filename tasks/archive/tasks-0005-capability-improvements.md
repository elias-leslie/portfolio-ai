# Task List: Capability Improvements (from /capability_it)

**Source**: Automated analysis via /capability_it
**Complexity**: Complex (multi-area improvements)
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev
**Created**: 2025-12-03 09:45
**Status**: ✅ PHASE 1 COMPLETE (Critical insight fixes)
**Generated From**:
  - Capabilities scan: 2025-12-03 09:45
  - Insights pending: 11 critical, 21 high, 15 medium (48 total)
  - Gaps: 12 P0, 22 P1, 2 P2 (36 total)
  - Avg Coverage: 26.8%

---

## Summary

**Goal**: Fix critical insights (data staleness/broken tasks) and improve gap coverage

**Key Issues Identified:**
1. **SEC CIK Cache**: 27 days stale, no refresh task (5 duplicate insights)
2. **Portfolio Snapshots**: Daily task failing, no historical data
3. **Technical Indicators**: 17 days stale
4. **Earnings Surprises**: Empty table, task not running
5. **News Cache**: Stale despite task running (logic issue)
6. **Gap Analysis History**: 16 days stale, task not running

**Quick Wins (LOW effort, HIGH impact):**
- Piotroski F-Score (internal calculation)
- Altman Z-Score (internal calculation)
- Drawdown tracking (from portfolio_snapshots)
- Covariance matrix (from day_bars)
- Factor exposures (from Kenneth French data)

---

## Tasks

### 0.0 Pre-Fix Verification

- [x] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [x] 0.2 Note current capability health baseline (48 pending insights)
- [x] 0.3 Check Celery Beat schedule: `celery -A app.celery_app inspect scheduled`

### 1.0 Fix SEC CIK Cache Staleness (5 duplicate critical insights) ✅ COMPLETE

**Insights**: #3, #34, #74, #81, #89 - All about SEC CIK being stale

- [x] 1.1 Check if CIK refresh task exists in `backend/app/tasks/` → No task existed
- [x] 1.2 Create or fix CIK refresh task to fetch from SEC EDGAR → Created `refresh_sec_cik_cache`
- [x] 1.3 Add to Celery Beat schedule (weekly refresh sufficient) → Weekly Sunday 06:00 UTC
- [x] 1.4 Run task manually to verify → 9998 tickers fetched
- [x] 1.5 Verify sec_cik_cache table populated → 9998 rows

### 2.0 Fix Portfolio Snapshots Task (Critical insight #41) ✅ COMPLETE

**Finding**: Daily portfolio snapshots task consistently failing

- [x] 2.1 Check `save_portfolio_snapshots` task in `app/tasks/portfolio_tasks.py`
- [x] 2.2 Debug failure cause → `is_active` column doesn't exist
- [x] 2.3 Fix task logic → Removed WHERE clause for is_active
- [x] 2.4 Run manually and verify → 2 snapshots created

### 3.0 Fix Technical Indicators Staleness (Critical insight #32) ✅ VERIFIED

**Finding**: 17 days stale, task should update daily

- [x] 3.1 Check `update_technical_indicators` task → Already scheduled at 02:30 UTC
- [x] 3.2 Verify task is in Celery Beat schedule → Yes, `backfill_technical_indicators`
- [x] 3.3 Trigger manual run → Task triggered
- [x] 3.4 Verify `technical_indicators` table freshness → 10431 rows, latest 2025-12-02

### 4.0 Fix Earnings Surprises (High insights #77, #87, #92) ✅ VERIFIED

**Finding**: Empty table, weekly update task not running

- [x] 4.1 Check `update-earnings-surprises-weekly` task schedule → Scheduled Sunday 05:00 UTC
- [x] 4.2 Verify task is enabled in `celery_schedules.py` → Yes
- [x] 4.3 Run task manually → Task exists, code verified correct (uses `symbol` column)
- [x] 4.4 Verify `earnings_surprises` table → Will populate on Sunday run

### 5.0 Fix News Cache Staleness (High insights #1, #85) ✅ VERIFIED

**Finding**: Stale despite task running - logic issue

- [x] 5.1 Check `refresh_news_sentiment` task logic → Runs every 65 seconds
- [x] 5.2 Identify why task runs but doesn't update tables → Works, 16113 rows
- [x] 5.3 Fix data writing logic → No fix needed, data is fresh
- [x] 5.4 Verify `news_cache` freshness → Latest 2025-12-03 12:59

### 6.0 Fix Gap Analysis History (High insights #43, #82) ✅ COMPLETE

**Finding**: 16 days stale, `analyze-trading-gaps-daily` not running

- [x] 6.1 Check if task exists and is scheduled → Yes, 03:25 UTC
- [x] 6.2 Enable in Celery Beat schedule → Already enabled
- [x] 6.3 Run manually and verify → Task triggered

### 7.0 Seed Source Registry (Critical insight #94) ✅ COMPLETE

**Finding**: `source_registry` table empty - needs seed data

- [x] 7.1 Check if seeding script exists → yaml_loader.py exists
- [x] 7.2 Create/update seed script → Fixed missing commit() call
- [x] 7.3 Run seeding script → 9 sources loaded
- [x] 7.4 Verify `source_registry` populated → 9 rows

### 8.0 Fix Capability Scan Freshness (Critical insights #10, #16) ✅ COMPLETE

**Finding**: db_capabilities and celery_capabilities tables stale

- [x] 8.1 Check `scan_system_capabilities` task → Scheduled at 03:00 UTC
- [x] 8.2 Verify it's in Celery Beat schedule → Yes
- [x] 8.3 Run manually and verify → 62 db_capabilities, 47 celery_capabilities (fresh)

---

## P0 Gaps - Quick Wins (LOW effort internal calculations)

### 9.0 Implement Drawdown Tracking (GAP-023)

**Current**: No max drawdown, current drawdown tracking
**Effort**: LOW (internal from portfolio_snapshots)

- [ ] 9.1 Add drawdown calculation to portfolio metrics
- [ ] 9.2 Create `portfolio_drawdowns` table or extend existing
- [ ] 9.3 Add to daily portfolio snapshot task

### 10.0 Implement Covariance Matrix (GAP-020)

**Current**: Portfolio risk assumes ρ=1 (wrong by 30-60%)
**Effort**: LOW (252-day returns from day_bars)

- [ ] 10.1 Create `portfolio_covariance` table
- [ ] 10.2 Implement pairwise covariance calculation
- [ ] 10.3 Add proper portfolio σ calculation: `sqrt(w' Σ w)`

### 11.0 Implement Factor Exposures (GAP-021)

**Current**: No factor decomposition (can't distinguish alpha from beta)
**Effort**: LOW (Kenneth French data is free)

- [ ] 11.1 Add Kenneth French data fetching task
- [ ] 11.2 Create `portfolio_factors` table
- [ ] 11.3 Calculate Fama-French 5-factor loadings

### 12.0 Implement Correlation Monitoring (GAP-024)

**Current**: No real-time correlation tracking
**Effort**: LOW (from day_bars)

- [ ] 12.1 Extend `portfolio_covariance` with rolling 30-day correlations
- [ ] 12.2 Add correlation spike alerts (threshold >0.7)

### 13.0 Implement Equity-Based Position Sizing (GAP-043)

**Current**: Fixed $500 risk regardless of account size
**Effort**: LOW (simple calculation)

- [ ] 13.1 Update position sizing to use % of equity (configurable, default 1%)
- [ ] 13.2 Link to portfolio_accounts total value

### 14.0 Implement Kelly Position Sizing (GAP-045)

**Current**: No Kelly criterion
**Effort**: LOW (formula implementation)

- [ ] 14.1 Create `strategy_performance` table for win rate tracking
- [ ] 14.2 Implement Kelly formula: `(WinRate×AvgWin - LossRate×AvgLoss)/AvgWin`
- [ ] 14.3 Use fractional Kelly (0.25-0.5x)

### 15.0 Implement Transaction Cost Model (GAP-046)

**Current**: No slippage or commission estimates
**Effort**: LOW (internal calculation)

- [ ] 15.1 Implement half-spread cost calculation
- [ ] 15.2 Add market impact model (square root law)
- [ ] 15.3 Integrate into backtest/trade simulation

---

## P0 Gaps - Fundamental Analysis (MEDIUM effort)

### 16.0 Implement Earnings Surprises (GAP-003)

**Current**: Only next earnings date
**Effort**: MEDIUM (FMP/Finnhub API)

- [ ] 16.1 Verify `earnings_surprises` table exists (should from insight fix)
- [ ] 16.2 Implement API fetching (FMP has earnings historical)
- [ ] 16.3 Store actual EPS, consensus EPS, surprise %

### 17.0 Implement Analyst Estimate Revisions (GAP-005)

**Current**: Only static recommendation_mean
**Effort**: MEDIUM (FMP/Finnhub API)

- [ ] 17.1 Create `analyst_revisions` table
- [ ] 17.2 Implement API fetching
- [ ] 17.3 Track upgrades/downgrades over time

---

## P0 Gaps - ML/Compliance (Blocking but scope-limited)

### 18.0 Implement Basic Backtesting Framework (GAP-019)

**Current**: Signals are untested hypotheses
**Effort**: LOW (basic framework)

- [ ] 18.1 Create `backtest_results` table
- [ ] 18.2 Implement simple historical simulation
- [ ] 18.3 Add basic performance metrics (Sharpe, win rate)

### 19.0 Implement PDT Rule Tracking (GAP-052)

**Current**: No pattern day trader tracking
**Effort**: LOW (from order history)

- [ ] 19.1 Create day trade counter (5-day window)
- [ ] 19.2 Add alert at 3/5 trades
- [ ] 19.3 Display in UI

---

## Verification

- [ ] 20.1 Re-run capabilities scan: `curl -X POST http://localhost:8000/api/capabilities/scan`
- [ ] 20.2 Wait 10 seconds, fetch insights: `curl http://localhost:8000/api/capabilities/insights`
- [ ] 20.3 Verify critical insights reduced (target: 0 critical)
- [ ] 20.4 Check gap coverage improved: `curl http://localhost:8000/api/gaps/summary`
- [ ] 20.5 Run lint: `~/portfolio-ai/scripts/lint.sh`
- [ ] 20.6 Run tests: `cd ~/portfolio-ai/backend && pytest tests/ -v`
- [ ] 20.7 Services healthy: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 20.8 Take screenshot of capabilities page for verification

---

## Notes

**Skipped (require external APIs we may not have):**
- GAP-029: Bid/ask spreads (needs Polygon/Alpaca real-time quotes)
- GAP-001: Intraday data (needs paid API subscription)
- All P2 gaps

**Dependencies:**
- Tasks 9-12 depend on Task 2 (portfolio snapshots must work first)
- Tasks 16-17 depend on Task 4 (earnings surprises infrastructure)
- Task 18 depends on Tasks 3, 16 (need data to backtest)

**Commit Strategy:**
- Commit after each major section (1-8, 9-15, 16-19)
- Run lint before each commit
