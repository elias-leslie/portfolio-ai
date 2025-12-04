# Task List: Tier 0 Foundations - B&H Integration + Centralized Rules Engine

**Source**: trading_platform_improvements_v2.md sections 0.1, 0.2
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 16:30

---

## Summary

**Goal**: Complete the two CRITICAL foundation tasks that enable all other improvements - integrate the existing B&H benchmark engine and create a centralized trading rules YAML config.

**Approach**:
1. Task 0.1: Wire up existing `benchmark.py` (491 lines already written) into backtest pipeline
2. Task 0.2: Extract all hardcoded thresholds into versioned YAML, refactor consumers

**Scope Discovery**: Required for 0.2 (hardcoded thresholds scattered across 6+ files)

**Key Finding**: `backend/app/backtest/benchmark.py` is COMPLETE but has ZERO integration points.

**Additional Findings from Second Pass**:
1. **Risk thresholds mismatch**: Drawdown halt at 10% (should be 25%), warnings at 5%/7.5% (should be 15%)
2. **Per-trade max loss 2%**: Documented but NOT ENFORCED in order_executor.py
3. **Scoring weights incomplete**: news_sentiment_weight (20%) and catalyst_weight (20%) NOT IMPLEMENTED
4. **User preferences not wired**: DB has weight columns but preferences_loader.py doesn't load them

---

## Tasks

### 0.0 Scope Discovery for Rules Engine (MANDATORY)

- [ ] 0.1 Run Explore subagent "very thorough" for hardcoded thresholds
  - Pattern: RSI thresholds, position sizing constants, scoring weights
  - Known locations: indicators.py, signal_classifier.py, scoring.py, position_sizing.py, kelly.py, trade_calculations.py
  - Goal: Complete inventory of ALL hardcoded trading values
- [ ] 0.2 Document all threshold locations with line numbers
  - Create threshold-inventory.md with file:line:value mapping
  - Categorize: position_sizing, technical, fundamental, scoring, risk_management
- [ ] 0.3 Checkpoint: Confirm scope
  - Total files affected: [TBD from exploration]
  - Total hardcoded values: [TBD]
  - Estimated migration effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Integrate B&H Benchmark into Backtest Pipeline (Section 0.1)

**Prerequisite**: None (benchmark.py already complete)

- [ ] 1.1 Add benchmark fields to database schema
  - Create migration 072_backtest_benchmark_fields.sql
  - Add columns: buy_hold_return, excess_return, beats_buy_hold, alpha, information_ratio, beta
  - Run migration
- [ ] 1.2 Update BacktestRun model (models.py)
  - Add 6 new fields to BacktestRun dataclass
  - Add beats_buy_hold_risk_adjusted computed property
- [ ] 1.3 Wire benchmark engine into backtest execution
  - Edit backtest_tasks.py run_backtest_task()
  - After replay_backtest(), call BenchmarkComparisonEngine.compare_to_benchmark()
  - Pass benchmark metrics to storage.update_backtest_result()
- [ ] 1.4 Update storage layer
  - Edit storage.py update_backtest_result() to accept benchmark fields
  - Ensure all 6 fields persisted to backtest_runs table
- [ ] 1.5 Update API response model
  - Edit api/backtest.py RunMetricsResponse
  - Add benchmark comparison fields to response
- [ ] 1.6 Verify B&H calculation correctness
  - Same start/end dates: Verify in compare_to_benchmark()
  - Same initial capital: Verify in get_buy_and_hold_returns()
  - Transaction costs: B&H should have none, strategy should have costs
- [ ] 1.7 Test B&H integration
  - Write test: test_backtest_includes_benchmark_comparison
  - Run backtest via API, verify benchmark fields populated
  - Verify excess_return = strategy_return - buy_hold_return

---

### 2.0 Create Centralized Trading Rules Engine (Section 0.2)

- [ ] 2.1 Design rules YAML schema
  - Create backend/app/config/trading_rules/v1.0.0/rules.yaml
  - Sections: position_sizing, risk_management, technical_thresholds, scoring, fees
  - Include version, updated, updated_by fields
- [ ] 2.2 Create rules loader module
  - Create backend/app/rules/loader.py
  - Implement get_rules() function returning typed dataclass
  - Add caching with TTL (5 min) for hot reload support
  - Validate schema on load
- [ ] 2.3 Migrate position sizing thresholds
  - Extract from position_sizing.py: DEFAULT_RISK_PERCENT, MIN/MAX values
  - Extract from kelly.py: DEFAULT_KELLY_FRACTION, MIN_TRADES_FOR_KELLY
  - Update consumers to use get_rules().position_sizing
- [ ] 2.4 Migrate technical thresholds
  - Extract from indicators.py: RSI 30/70, EMA periods (20,50,200)
  - Extract from trade_calculations.py: ATR multiplier (2.0)
  - Update consumers to use get_rules().technical_thresholds
- [ ] 2.5 Migrate scoring weights
  - Extract from signal_classifier.py: All 20+ thresholds (profit_margin, revenue_growth, etc.)
  - Extract from scoring.py: Component weights
  - Update consumers to use get_rules().scoring
- [ ] 2.6 Migrate fee configuration
  - Extract from trading_requirements.yaml: commission_pct, slippage, min_profitable_position
  - Update consumers to use get_rules().fees
- [ ] 2.7 Add rules version tracking
  - Create migration 073_rules_version_history.sql
  - Track: version, updated_at, updated_by, change_description
- [ ] 2.8 Test rules engine
  - Unit tests: rules load correctly, validation works
  - Integration tests: consumers use rules not hardcoded values
  - Verify no hardcoded thresholds remain in migrated files

---

### 3.0 Fix Risk Management Thresholds (From Second Pass)

**Current vs Required**:
- Drawdown halt: 10% (actual) → 25% (spec)
- Drawdown warning: 5%/7.5% → 15%
- Max single loss per trade: NOT ENFORCED → 2% required

- [ ] 3.1 Update drawdown thresholds
  - Edit portfolio/drawdown.py line 28: PORTFOLIO_DRAWDOWN_HALT_PCT = 25.0
  - Edit line 29-30: Update warning levels (10%, 15%)
- [ ] 3.2 Enforce max single loss per trade
  - Edit order_executor.py execute_market_order()
  - Add validation: if position_risk_pct > 2% → reject
  - Before line 155 (position limits check)
- [ ] 3.3 Wire user preferences to scoring
  - Edit preferences_loader.py to load watchlist_score_weights JSONB
  - Edit watchlist/scoring_service/context.py to use loaded weights
  - Ensure user-configured weights flow through to scoring.py

---

### 4.0 Rules Engine UI (Optional Enhancement)

- [ ] 4.1 Add /api/rules endpoint
  - GET /api/rules - Return current rules version + all values
  - GET /api/rules/history - Return version history
- [ ] 4.2 Add rules viewer to frontend
  - New page or section in /capabilities
  - Display all active rules in readable format
  - Show version history with diff capability

---

## Verification

- [ ] Functional: B&H comparison works in all backtests
- [ ] Functional: All trading rules loaded from YAML
- [ ] Tests: pytest tests/backtest/ -v passes
- [ ] Tests: pytest tests/rules/ -v passes (new)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified
- [ ] Clean: No hardcoded thresholds in migrated files
- [ ] Docs: ARCHITECTURE.md updated with rules engine section

---

## Files to Modify

**Task 1 (B&H)**:
- backend/app/storage/migrations/072_backtest_benchmark_fields.sql (NEW)
- backend/app/backtest/models.py (lines 37-127)
- backend/app/tasks/backtest_tasks.py (lines 164-306)
- backend/app/backtest/storage.py
- backend/app/api/backtest.py (lines 108-142)

**Task 2 (Rules Engine)**:
- backend/app/config/trading_rules/v1.0.0/rules.yaml (NEW)
- backend/app/rules/loader.py (NEW)
- backend/app/rules/__init__.py (NEW)
- backend/app/analytics/position_sizing.py
- backend/app/analytics/kelly.py
- backend/app/analytics/indicators.py
- backend/app/analytics/trade_calculations.py
- backend/app/watchlist/signal_classifier.py
- backend/app/watchlist/scoring.py

---

## Dependencies

- This task BLOCKS: 1.1, 1.2, 3.1, 3.2 (all require rules engine or B&H baseline)
- This task HAS NO BLOCKERS
