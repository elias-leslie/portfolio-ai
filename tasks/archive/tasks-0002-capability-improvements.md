# Task List: Capability Improvements (from /capability_it)

**Source**: Automated analysis via /capability_it
**Complexity**: Complex (multi-area improvements)
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-03 (current session)
**Generated From**:
  - Capabilities scan: 2025-12-03
  - Insights pending: 1 critical, 5 high, 15 medium (21 total)
  - Gaps: 11 P0, 22 P1, 2 P2 (35 total)

---

## Summary

**Goal**: Address 1 critical insight, 5 high-priority insights, and implement 8 LOW-effort P0 gaps
**Approach**: Fix broken dependencies first, then add missing risk/execution capabilities
**Quick Wins**: 8 items (LOW effort, HIGH impact - internal calculations only)

---

## Tasks

### 0.0 Pre-Fix Verification

- [ ] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 0.2 Note current capability health baseline (21 pending insights, 26.8% avg coverage)
- [ ] 0.3 Ensure clean git state: `git status`

### 1.0 Fix Critical Insight: SEC CIK Cache (Insight #151)

**Problem**: sec_cik_cache 27 days stale, `refresh-sec-cik-cache-weekly` not running
**Impact**: SEC EDGAR lookups fail

- [ ] 1.1 Check if task exists in Celery beat schedule
- [ ] 1.2 Verify task implementation in `app/tasks/`
- [ ] 1.3 Fix or create the refresh task
- [ ] 1.4 Manually trigger to populate data
- [ ] 1.5 Verify table has fresh data

### 2.0 Fix High Priority Insights

#### 2.1 Fear & Greed Index Failing (Insight #4)

**Problem**: calculate-fear-greed-daily failing, put/call ratio not fetching
- [ ] 2.1.1 Check `fetch-putcall-ratio-daily` task status
- [ ] 2.1.2 Debug Fear & Greed calculation dependencies
- [ ] 2.1.3 Ensure all component tasks (VIX, put/call, SPY levels) are working

#### 2.2 Daily OHLCV Refresh 66% Success (Insight #2)

**Problem**: refresh-daily-ohlcv has 66% success rate
- [ ] 2.2.1 Check recent task logs for failure patterns
- [ ] 2.2.2 Identify problematic tickers causing failures
- [ ] 2.2.3 Add better error handling / retry logic
- [ ] 2.2.4 Ensure partial failures don't block entire refresh

#### 2.3 News Cache Stale (Insight #42)

**Problem**: news_cache and news_summary_log 1 day old despite hourly expectation
- [ ] 2.3.1 Check news refresh task schedule
- [ ] 2.3.2 Verify news task is completing successfully
- [ ] 2.3.3 Fix scheduling or task logic as needed

#### 2.4 Agent Workflows Stale (Insight #61)

**Problem**: agent_workflows table 3 days stale
- [ ] 2.4.1 Check `run-discovery-agent-daily` and `run-portfolio-analyzer-daily` tasks
- [ ] 2.4.2 Verify agent infrastructure is operational
- [ ] 2.4.3 Fix any agent execution issues

#### 2.5 Strategy Metrics Empty (Insight #140)

**Problem**: strategy_metrics and strategy_performance tables empty
- [ ] 2.5.1 Check if strategy monitoring tasks exist
- [ ] 2.5.2 Create or fix `evaluate_strategy_performance` task
- [ ] 2.5.3 Populate initial strategy metrics from idea_outcomes

### 3.0 Implement P0 Risk Analysis Gaps (LOW Effort - Internal Calculations)

These are all internal calculations using existing data - no external APIs needed.

#### 3.1 Covariance Matrix (GAP-020)

**Current**: Assumes ρ=1 (perfect correlation) - WRONG
**Target**: Pairwise covariance matrix, proper portfolio σ
**Effort**: LOW (252-day returns from day_bars)

- [ ] 3.1.1 Create `portfolio_covariance` table schema
- [ ] 3.1.2 Implement covariance calculation service
- [ ] 3.1.3 Create Celery task to refresh daily
- [ ] 3.1.4 Add to beat schedule

#### 3.2 Factor Exposures (GAP-021)

**Current**: Cannot distinguish alpha from beta
**Target**: Fama-French 5-factor loadings
**Effort**: LOW (Kenneth French free data)

- [ ] 3.2.1 Create `portfolio_factors` table schema
- [ ] 3.2.2 Fetch Fama-French factors from Kenneth French library
- [ ] 3.2.3 Implement factor regression calculation
- [ ] 3.2.4 Create Celery task to refresh weekly

#### 3.3 Drawdown Tracking (GAP-023)

**Current**: No max/current drawdown tracking
**Target**: Max DD, current DD, days since ATH
**Effort**: LOW (from portfolio_snapshots)

- [ ] 3.3.1 Create `portfolio_drawdowns` table schema
- [ ] 3.3.2 Implement drawdown calculation from snapshots
- [ ] 3.3.3 Create Celery task to update daily
- [ ] 3.3.4 Add to beat schedule

#### 3.4 Correlation Monitoring (GAP-024)

**Current**: No real-time correlation tracking
**Target**: Rolling 30-day correlation matrix, alerts at >0.7
**Effort**: LOW (from day_bars)

- [ ] 3.4.1 Extend covariance service for correlation output
- [ ] 3.4.2 Add correlation threshold alerts
- [ ] 3.4.3 Store in portfolio_covariance table

### 4.0 Implement P0 Execution Quality Gaps (LOW Effort)

#### 4.1 Equity-Based Position Sizing (GAP-043)

**Current**: Fixed $500 risk (not linked to equity)
**Target**: Risk = 1% of account equity (configurable)
**Effort**: LOW

- [ ] 4.1.1 Find current position sizing code
- [ ] 4.1.2 Replace fixed $500 with equity-based calculation
- [ ] 4.1.3 Add configuration for risk percentage
- [ ] 4.1.4 Test position size calculations

#### 4.2 Kelly Criterion Position Sizing (GAP-045)

**Current**: No Kelly criterion
**Target**: Kelly% = (WinRate×AvgWin - LossRate×AvgLoss)/AvgWin, use fractional Kelly
**Effort**: LOW

- [ ] 4.2.1 Create Kelly calculation service
- [ ] 4.2.2 Calculate from historical strategy performance
- [ ] 4.2.3 Implement fractional Kelly (0.25-0.5 multiplier)
- [ ] 4.2.4 Integrate with position sizing

#### 4.3 Transaction Cost Model (GAP-046)

**Current**: No slippage or commission estimates
**Target**: Half-spread cost + market impact (square root law)
**Effort**: LOW

- [ ] 4.3.1 Implement basic transaction cost model
- [ ] 4.3.2 Add slippage estimation based on ADV
- [ ] 4.3.3 Integrate into backtest calculations

### 5.0 Implement P0 ML Infrastructure (GAP-019)

#### 5.1 Backtesting Framework

**Current**: Signals are untested hypotheses
**Target**: Historical simulation with realistic fills, costs, slippage
**Effort**: LOW (we already have backtest_runs infrastructure)

- [ ] 5.1.1 Review existing backtest infrastructure
- [ ] 5.1.2 Ensure backtests incorporate transaction costs
- [ ] 5.1.3 Add proper historical replay with slippage
- [ ] 5.1.4 Create backtest_results table if needed

### 6.0 Implement P0 Compliance (GAP-052)

#### 6.1 PDT Rule Tracking

**Current**: No pattern day trader tracking
**Target**: Track day trades per 5-day window, alert at 3/5
**Effort**: LOW

- [ ] 6.1.1 Add day trade counter to order tracking
- [ ] 6.1.2 Implement 5-day rolling window check
- [ ] 6.1.3 Add alert when approaching PDT limit
- [ ] 6.1.4 Block order submission if PDT would be violated

---

## Verification & Insight Resolution

### V.1 Re-scan Capabilities

- [ ] V.1.1 Trigger fresh scan: `curl -s -X POST http://localhost:8000/api/capabilities/scan`
- [ ] V.1.2 Wait 15 seconds for scan + AI analysis
- [ ] V.1.3 Verify health improved: `curl -s http://localhost:8000/api/capabilities/health/summary`

### V.2 Mark Resolved Insights as Fixed

**For EACH insight we fixed, mark via API:**

```bash
# Template:
curl -s -X POST "http://localhost:8000/api/capabilities/insights/$ID/review" \
  -H "Content-Type: application/json" \
  -d '{"status": "fixed", "status_reason": "..."}'
```

Insight IDs to mark after verification:
- [ ] V.2.1 Mark insight #151 (sec_cik_cache) as fixed if data is fresh
- [ ] V.2.2 Mark insight #4 (Fear & Greed) as fixed if calculation succeeds
- [ ] V.2.3 Mark insight #2 (OHLCV) as fixed if success rate improved
- [ ] V.2.4 Mark insight #42 (news_cache) as fixed if fresh
- [ ] V.2.5 Mark insight #61 (agent_workflows) as fixed if fresh
- [ ] V.2.6 Mark insight #140 (strategy_metrics) as fixed if populated

### V.3 Verify Gap Coverage Improved

- [ ] V.3.1 Check gap summary: `curl -s http://localhost:8000/api/gaps/summary | jq '{avg_coverage: .avg_coverage_pct, p0: .p0_gaps}'`
- [ ] V.3.2 Verify risk_analysis coverage increased from 0%
- [ ] V.3.3 Verify execution_quality coverage increased from 40%

### V.4 Final Quality Check

- [ ] V.4.1 Run lint: `~/portfolio-ai/scripts/lint.sh`
- [ ] V.4.2 Services healthy: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] V.4.3 Restart services: `bash ~/portfolio-ai/scripts/restart.sh`
- [ ] V.4.4 Take screenshot: `node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/capabilities /tmp/capabilities-verified.png`

---

## Priority Order

Execute in this order for maximum impact:

1. **Section 1**: Critical SEC CIK (eliminates critical insight)
2. **Section 3.3**: Drawdown tracking (quick win, high visibility)
3. **Section 4.1**: Position sizing (immediate trading improvement)
4. **Section 3.1**: Covariance matrix (fixes core risk calculation)
5. **Section 2**: High priority insights (stabilize existing features)
6. **Remaining**: Other P0 gaps as time permits

---

## Notes

- All risk analysis gaps (Section 3) use internal data only - no API keys needed
- Execution quality gaps (Section 4) are pure code changes
- Focus on LOW effort items first for quick wins
- Skip MEDIUM effort fundamental gaps (GAP-003, GAP-005) as they need external API setup
