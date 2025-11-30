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

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "medium" mode
  - Pattern 1: Existing telemetry/metrics in `backend/app/agents/` - What's already tracked?
  - Pattern 2: Backtest visualization in `frontend/app/backtest/` - Existing chart patterns
  - Pattern 3: Statistical libraries in use - pandas, numpy, scipy availability
  - Goal: Understand existing infrastructure to build upon
  - Output: List of reusable components and gaps
- [ ] 0.2 Verify prerequisite completion
  - Confirm tasks-0076 is 100% complete
  - Confirm backtesting produces valid results
  - Confirm agent workflows execute successfully
- [ ] 0.3 Update this task list with specific implementation details
  - Add file paths based on exploration
  - Estimate effort per task
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Estimated effort: [TBD]
  - Architectural concerns: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Agent Telemetry Dashboard (A3)

**Objective**: Track token usage, latency, error rates for all AI agent operations

- [ ] 1.1 Design telemetry data model
  - Create migration for `agent_telemetry` table
  - Fields: agent_run_id, provider (claude/gemini), model, input_tokens, output_tokens, latency_ms, cost_usd, error_type, timestamp
  - Add indexes for time-based queries
- [ ] 1.2 Implement telemetry collection
  - Location: `backend/app/agents/llm_client.py` or `dual_provider_client.py`
  - Capture metrics after each LLM call
  - Store in `agent_telemetry` table
  - Handle errors gracefully (don't fail workflow if telemetry fails)
- [ ] 1.3 Create telemetry aggregation queries
  - Daily token usage by provider
  - Average latency by model
  - Error rate over time
  - Cost tracking (estimate based on token counts)
- [ ] 1.4 Create backend API endpoints
  - GET `/api/agents/telemetry/summary` - 24h/7d/30d aggregates
  - GET `/api/agents/telemetry/history` - Time series data for charts
  - GET `/api/agents/telemetry/costs` - Estimated costs by provider
- [ ] 1.5 Create frontend telemetry dashboard
  - Location: `frontend/app/agents/telemetry/page.tsx` or add to existing agents page
  - Components:
    - Token usage chart (line chart, daily)
    - Latency distribution (histogram)
    - Error rate gauge
    - Cost summary cards
  - Use existing Recharts library
- [ ] 1.6 Add telemetry to health dashboard
  - Add summary card to /status page
  - Show: Total tokens today, avg latency, error rate
- [ ] 1.7 Add unit tests
  - Test telemetry collection
  - Test aggregation queries
  - Test API endpoints

### 2.0 Strategy Comparison Mode (B2)

**Objective**: Compare multiple backtest strategies side-by-side with visual equity curves

- [ ] 2.1 Design comparison data model
  - Create `backtest_comparisons` table (optional, or use in-memory)
  - Fields: comparison_id, backtest_run_ids[], created_at, notes
  - Or: Support ad-hoc comparison via API parameters
- [ ] 2.2 Create comparison API endpoint
  - GET `/api/backtest/compare?run_ids=id1,id2,id3`
  - Returns: Normalized equity curves, side-by-side metrics
  - Normalize starting equity to 100% for fair comparison
- [ ] 2.3 Create comparison metrics calculator
  - Location: `backend/app/backtest/comparison.py`
  - Calculate for each strategy:
    - Total return, Sharpe ratio, max drawdown, win rate
    - Correlation between strategies
    - Risk-adjusted return ranking
- [ ] 2.4 Create frontend comparison view
  - Location: `frontend/app/backtest/compare/page.tsx`
  - Multi-select backtests from list
  - Display:
    - Overlaid equity curves (different colors)
    - Side-by-side metrics table
    - Highlight best/worst performers
- [ ] 2.5 Add comparison to backtest page
  - Add "Compare" button to backtest list
  - Allow selecting 2-5 backtests for comparison
  - Link to comparison view
- [ ] 2.6 Add comparison tests
  - Test normalized equity calculation
  - Test metrics comparison accuracy
  - Test API with multiple run_ids

### 3.0 Monte Carlo Simulation (B4)

**Objective**: Stress-test strategies with randomized scenarios to estimate risk bounds

- [ ] 3.1 Research Monte Carlo approaches
  - Bootstrap resampling of daily returns
  - Random trade shuffling
  - Parameter sensitivity analysis
  - Choose approach: Bootstrap resampling (most common)
- [ ] 3.2 Implement Monte Carlo engine
  - Location: `backend/app/backtest/monte_carlo.py`
  - Input: backtest_run_id, num_simulations (default 1000)
  - Process:
    - Get original trade returns from backtest
    - Resample with replacement N times
    - Calculate equity curve for each simulation
    - Calculate distribution of outcomes
- [ ] 3.3 Calculate Monte Carlo statistics
  - 5th percentile return (worst case)
  - 50th percentile return (median)
  - 95th percentile return (best case)
  - Probability of loss (% of simulations with negative return)
  - Value at Risk (VaR) at 95% confidence
- [ ] 3.4 Create Monte Carlo API endpoint
  - POST `/api/backtest/{run_id}/monte-carlo`
  - Parameters: num_simulations, confidence_level
  - Returns: Statistics + distribution data for visualization
  - Consider: Run as Celery task if > 1000 simulations
- [ ] 3.5 Create frontend Monte Carlo view
  - Location: `frontend/app/backtest/[id]/monte-carlo/page.tsx` or modal
  - Display:
    - Distribution histogram of final returns
    - Confidence interval bands on equity curve
    - Risk metrics (VaR, probability of loss)
    - Run simulation button with progress indicator
- [ ] 3.6 Add Monte Carlo to backtest detail page
  - Add "Run Monte Carlo" button
  - Show summary stats inline
  - Link to full analysis view
- [ ] 3.7 Add Monte Carlo tests
  - Test resampling produces valid distributions
  - Test statistics calculation accuracy
  - Test API with various parameters

---

## Verification

- [ ] Functional: All three features working end-to-end
- [ ] Tests: 80%+ coverage for new code, all passing
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: Restarted and verified (bash ~/portfolio-ai/scripts/restart.sh)
- [ ] Performance: Monte Carlo 1000 sims completes in < 30 seconds
- [ ] Docs: Updated API_REFERENCE.md with new endpoints
- [ ] UI: All new pages mobile-responsive

---

## VISION.md Alignment

- [ ] A3: "Zero manual intervention required for routine operations" - Telemetry enables proactive monitoring
- [ ] B2: "Equity curves available for visual comparison" - Direct implementation
- [ ] B4: "Validates rigorously" - Monte Carlo adds statistical rigor to validation

---

## Success Criteria

1. **Agent Telemetry**: Dashboard shows real-time token usage, costs, and error rates
2. **Strategy Comparison**: Can compare 2-5 backtests with overlaid equity curves
3. **Monte Carlo**: Can run 1000 simulations and see probability distribution of outcomes
