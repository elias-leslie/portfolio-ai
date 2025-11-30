# Task List: Advanced Trading Intelligence Features

**Source**: User request via /task_it (VISION.md alignment - deferred items)
**Complexity**: Complex
**Effort**: HIGH (estimated 15-20 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-30
**Prerequisite**: Complete tasks-0076 first

---

## Summary

**Goal**: Implement advanced trading intelligence features to enhance strategy validation, agent monitoring, and risk analysis per VISION.md goals.
**Approach**: Build agent telemetry dashboard, strategy comparison tools, and Monte Carlo simulation for stress testing.
**Scope Discovery**: Required
**Dependencies**: Tasks-0076 must be complete (working backtesting, paper trading, multi-agent workflows)

---

## Tasks

### 0.0 Scope Discovery (MANDATORY) ✅ COMPLETE

- [x] 0.1 Run Explore subagent in "medium" mode
  - ✅ Pattern 1: Agent telemetry in `backend/app/agents/` - `agent_runs` table has telemetry columns (provider, model, token_usage, duration_ms)
  - ✅ Pattern 2: Backtest visualization in `frontend/app/backtest/` - BacktestDetails.tsx (689 lines), Recharts LineChart pattern
  - ✅ Pattern 3: Statistical libraries available: numpy 2.2.6, pandas 2.3.3, scipy 1.16.3, numba 0.61.2
  - **Reusable**: AgentStatsCard, PaperTradePerformance chart patterns, existing metrics.py calculations
  - **Gaps**: No /agents dashboard, no comparison metrics panel, zero Monte Carlo code
- [x] 0.2 Verify prerequisite completion
  - ✅ Task 0076 is 100% complete (verified in archive)
  - ✅ Backtesting produces valid results (248+ equity points, 7-12 trades per run)
  - ✅ Agent workflows execute successfully (Gemini CLI fixed, multi-agent working)
- [x] 0.3 Update this task list with specific implementation details
  - Task 1: Create `backend/app/api/agents.py`, `frontend/app/agents/page.tsx` (~400 lines each)
  - Task 2: Modify `/api/backtest/compare`, create `ComparisonMetrics.tsx` (~200 lines)
  - Task 3: Create `backend/app/backtest/monte_carlo.py` (~250 lines), new frontend page
- [x] 0.4 Checkpoint: Confirm scope before proceeding
  - Total files affected: 15-20 files (8 new, 7-12 modified)
  - Estimated effort: 15-18 hours total (Task 1: 8h, Task 2: 4h, Task 3: 6h)
  - Architectural concerns: None - all builds on existing patterns

**SCOPE CONFIRMED - PROCEED TO TASK 1**

### 1.0 Agent Telemetry Dashboard (A3) ✅ COMPLETE

**Objective**: Track token usage, latency, error rates for all AI agent operations

- [x] 1.1 Design telemetry data model
  - ✅ Using existing `agent_runs` table (migration 046 added telemetry columns)
  - ✅ Fields: provider, model, token_usage (JSONB), duration_ms, error_message
- [x] 1.2 Implement telemetry collection
  - ✅ Already implemented in `backend/app/agents/base.py`
  - ✅ Captures metrics after each agent run
- [x] 1.3 Create telemetry aggregation queries
  - ✅ Created `backend/app/services/agent_telemetry.py` (380 lines)
  - ✅ Daily token usage by provider, avg latency, error rates, cost tracking
- [x] 1.4 Create backend API endpoints
  - ✅ Created `backend/app/api/agents.py` with endpoints:
    - GET `/api/agents/telemetry/summary` - 7/14/30d aggregates
    - GET `/api/agents/telemetry/history` - Paginated run history with filters
    - GET `/api/agents/runs/{run_id}` - Individual run details
- [x] 1.5 Create frontend telemetry dashboard
  - ✅ Created `frontend/app/agents/page.tsx` (356 lines)
  - ✅ Summary metric cards (total runs, success rate, tokens, duration)
  - ✅ Provider metrics panel
  - ✅ Recent runs table with filtering
  - ✅ Added "Agents" nav link to Navigation.tsx
- [x] 1.6 Add telemetry to health dashboard
  - ✅ Enhanced `AgentStatsCard` component with token usage (7d)
  - ✅ Added "View Full Telemetry" link to /agents page
- [x] 1.7 Add unit tests
  - ✅ Created `tests/unit/services/test_agent_telemetry.py` (11 tests)
  - ✅ Tests for all dataclasses and service methods

### 2.0 Strategy Comparison Mode (B2) ✅ COMPLETE

**Objective**: Compare multiple backtest strategies side-by-side with visual equity curves

- [x] 2.1 Design comparison data model
  - ✅ Created `backend/app/backtest/comparison.py` (210 lines)
  - ✅ Uses ad-hoc comparison via API parameters (no new table needed)
  - ✅ Dataclasses: NormalizedEquityPoint, RunMetrics, ComparisonResult
- [x] 2.2 Create comparison API endpoint
  - ✅ Enhanced POST `/api/backtest/compare?run_ids=id1,id2,id3`
  - ✅ Returns: Normalized equity curves (starting at 0%), side-by-side metrics with rankings
  - ✅ Added correlation matrix between strategies
- [x] 2.3 Create comparison metrics calculator
  - ✅ Location: `backend/app/backtest/comparison.py`
  - ✅ Functions: normalize_equity_curve, rank_metrics, calculate_correlation
  - ✅ Rankings for return, Sharpe ratio, and drawdown (lower drawdown = better rank)
- [x] 2.4 Create frontend comparison view
  - ✅ Updated `frontend/components/backtest/BacktestDetails.tsx`
  - ✅ MetricsComparisonTable component with rankings (gold/silver/bronze badges)
  - ✅ Correlation matrix with color coding (green=diversified, red=correlated)
  - ✅ Symbol names in chart legend (not just "Run 1")
- [x] 2.5 Add comparison to backtest page
  - ✅ Already exists - comparison mode toggle with run selection
  - ✅ Updated to use new API response structure
- [x] 2.6 Add comparison tests
  - ✅ Created `tests/unit/backtest/test_comparison.py` (14 tests)
  - ✅ Tests: normalization, ranking, correlation, integration

### 3.0 Monte Carlo Simulation (B4) ✅ COMPLETE

**Objective**: Stress-test strategies with randomized scenarios to estimate risk bounds

- [x] 3.1 Research Monte Carlo approaches
  - ✅ Chose: Bootstrap resampling of trade returns (most common/robust)
- [x] 3.2 Implement Monte Carlo engine
  - ✅ Location: `backend/app/backtest/monte_carlo.py` (340 lines)
  - ✅ Functions: bootstrap_resample, generate_equity_paths
  - ✅ Reproducible with seed parameter
- [x] 3.3 Calculate Monte Carlo statistics
  - ✅ Percentiles: 5th, 25th, 50th (median), 75th, 95th
  - ✅ Risk metrics: probability_of_loss, value_at_risk_95, expected_shortfall
  - ✅ Distribution stats: mean, std_dev, skewness, kurtosis
- [x] 3.4 Create Monte Carlo API endpoint
  - ✅ POST `/api/backtest/runs/{run_id}/monte-carlo`
  - ✅ Parameters: num_simulations (100-10000), seed
  - ✅ Returns: statistics, histogram_data, equity_bands
  - ✅ Validates: run must be completed with trades
- [x] 3.5 Create frontend Monte Carlo view
  - ✅ MonteCarloResults component in BacktestDetails.tsx
  - ✅ Key stats cards: median return, 95% confidence, prob of loss, VaR, expected shortfall
  - ✅ Distribution stats: mean, std_dev, skewness, kurtosis
- [x] 3.6 Add Monte Carlo to backtest detail page
  - ✅ "Run Monte Carlo" button with loading state
  - ✅ Results displayed inline in collapsible section
  - ✅ Error handling with retry button
- [x] 3.7 Add Monte Carlo tests
  - ✅ Created `tests/unit/backtest/test_monte_carlo.py` (22 tests)
  - ✅ Tests: extraction, resampling, paths, statistics, histogram, bands, integration

---

## Verification

- [x] Functional: All three features working end-to-end
  - ✅ Agent Telemetry: Dashboard at /agents shows runs, tokens, providers
  - ✅ Strategy Comparison: Normalized curves, metrics table, correlation matrix
  - ✅ Monte Carlo: 1000 simulations with percentiles, VaR, probability of loss
- [x] Tests: 80%+ coverage for new code, all passing
  - ✅ Comparison tests: 14 tests in test_comparison.py
  - ✅ Monte Carlo tests: 22 tests in test_monte_carlo.py
  - ✅ Agent telemetry tests: 11 tests in test_agent_telemetry.py
- [x] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
  - ✅ All backend files pass ruff and mypy
- [ ] Services: Restarted and verified (bash ~/portfolio-ai/scripts/restart.sh)
- [x] Performance: Monte Carlo 1000 sims completes in < 30 seconds
  - ✅ Runs in ~1-2 seconds for typical backtests (synchronous, no Celery needed)
- [ ] Docs: Updated API_REFERENCE.md with new endpoints
- [x] UI: All new pages mobile-responsive
  - ✅ Using responsive grid layouts and existing SectionCard pattern

---

## VISION.md Alignment

- [x] A3: "Zero manual intervention required for routine operations" - Telemetry enables proactive monitoring
- [x] B2: "Equity curves available for visual comparison" - Direct implementation
- [x] B4: "Validates rigorously" - Monte Carlo adds statistical rigor to validation

---

## Success Criteria ✅ ALL MET

1. **Agent Telemetry**: ✅ Dashboard shows real-time token usage, costs, and error rates
2. **Strategy Comparison**: ✅ Can compare 2-5 backtests with overlaid equity curves, metrics, rankings
3. **Monte Carlo**: ✅ Can run 1000 simulations and see probability distribution of outcomes
