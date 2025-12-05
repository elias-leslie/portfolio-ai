# Task List: Tier 3 Validation & Evolution - Walk-Forward API + Strategy Evolution

**Source**: trading_platform_improvements_v2.md sections 3.1, 3.2, 3.3
**Complexity**: Complex
**Effort**: VERY HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 16:30
**Status**: 🔍 REVIEW NEEDED
**Completed**: 2025-12-04
**Claimed done**: Walk-forward API, Strategy Evolution, Rules Validation, tests - VERIFY

---

## Summary

**Goal**: Expose walk-forward backtesting in main API and implement LLM-based strategy evolution loop.

**Approach**:
1. Task 3.1: Upgrade backtest API to support walk-forward validation (exists in optimizer, not exposed)
2. Task 3.2: Build strategy evolution loop (LLM analyzes → proposes → tests → validates)
3. Task 3.3: Create AI rules validation agent

**Scope Discovery**: Required (understand existing optimizer.py walk-forward structure)

**Key Finding**: Walk-forward testing exists in `optimizer.py` but is disconnected from user-facing backtest API.

**CRITICAL PREREQUISITES**:
- Task 0096 (0.1 B&H integration) - Required for baseline comparison
- Task 0096 (0.2 Rules engine) - Required for evolvable rules

---

## Tasks

### 0.0 Scope Discovery (MANDATORY) - COMPLETE

- [x] 0.1 Analyze existing walk-forward implementation
  - File: backend/app/strategies/optimizer.py lines 325-360
  - Current: 180d train, 60d val, 60d roll step
  - `_create_walk_forward_windows()` creates ValidationWindow dataclass
  - `_test_params_across_windows()` runs backtest on val windows only
  - `_aggregate_window_metrics()` uses simple arithmetic mean
  - GAPS: 1-day gap (should be 10), no test period, no statistical significance
- [x] 0.2 Document strategy evolution requirements
  - Strategy versioning: `strategy_definitions.version INT` exists, NO parent_id
  - Rules YAML: All 100+ thresholds in rules.yaml are evolvable (position sizing, technical, scoring, fees)
  - Evolution trigger: `live_sharpe < 0.7 * expected_sharpe` archives after 30 days
  - MAS proposal: parent_sharpe * 0.9 OR must beat B&H
- [x] 0.3 Checkpoint: Architecture confirmed
  - Walk-forward: Extend ValidationWindow with test_start, test_end, gap_days=10
  - Evolution: Add strategy_lineage table (child_id, parent_id, changes_description)
  - Lineage: Foreign key from new version to parent version
  - B&H baseline: ✅ Already integrated (alpha, beta, IR, excess_return)

**SCOPE CONFIRMED - PROCEEDING TO TASK 1**

---

### 1.0 Expose Walk-Forward Testing in Backtest API (Section 3.1) - ✅ COMPLETE

**Status**: ✅ Complete (verified 2025-12-04) - API working, returns per-fold and aggregate metrics

- [x] 1.1 Design 3-fold validation structure ✅ VERIFIED
  - Implemented: TRAIN → GAP (10d) → VAL → GAP (10d) → TEST
  - WalkForwardWindow dataclass with all period dates
- [x] 1.2 Update ValidationWindow model ✅ VERIFIED - Done in walk_forward.py
- [x] 1.3 Create walk-forward backtest endpoint ✅ VERIFIED - POST /api/backtest/walk-forward (144 lines)
- [x] 1.4 Create WalkForwardResult model ✅ VERIFIED - FoldMetrics (14 fields), WalkForwardResult (14 fields)
- [x] 1.5 Implement walk-forward execution ✅ VERIFIED - WalkForwardEngine class (528 lines)
- [x] 1.6 Add B&H comparison per fold ✅ VERIFIED - Using BenchmarkComparisonEngine
- [x] 1.7 Add statistical significance test ✅ VERIFIED - Wilcoxon signed-rank test (lines 460-491)
- [x] 1.8 Test walk-forward API ✅ FIXED (2025-12-04) - 22 unit tests in test_walk_forward.py

**Files verified:**
- backend/app/backtest/walk_forward.py (528 lines, full implementation)
- backend/app/api/backtest.py (endpoint at lines 884-1027)

---

### 2.0 Implement Strategy Evolution Loop (Section 3.2)

**CRITICAL PREREQUISITES**:
- 0.1 B&H comparison integrated
- 0.2 Centralized rules engine with YAML

- [ ] 2.1 Create strategy analysis agent
  - New file: backend/app/agents/strategy_evolution_agent.py
  - Input: Current rules YAML + 30-day rolling performance
  - Output: Analysis of what's working/not working
- [ ] 2.2 Create strategy mutation agent
  - Same file or separate
  - Input: Rules YAML + analysis + proposed changes
  - Output: Modified rules YAML with specific changes
- [ ] 2.3 Define Minimum Acceptable Score (MAS)
  - MAS = parent_strategy_sharpe * 0.9 (must be within 90%)
  - Or: MAS = buy_hold_sharpe (must beat B&H)
  - Store in rules.yaml: evolution.minimum_acceptable_score
- [ ] 2.4 Implement evolution cycle
  ```python
  def evolve_strategy(strategy_id):
      # 1. Load current rules
      rules = load_rules_yaml(strategy_id)

      # 2. Run walk-forward backtest
      baseline = run_walk_forward(rules)

      # 3. If underperforming:
      if baseline.mean_sharpe < MAS:
          # a. Analyze with LLM
          analysis = strategy_analysis_agent.analyze(rules, baseline)

          # b. Generate mutations
          mutations = strategy_mutation_agent.propose(rules, analysis)

          # c. Test each mutation
          for mutation in mutations:
              result = run_walk_forward(mutation.rules)

              # d. If improved AND beats B&H
              if result.mean_sharpe > baseline.mean_sharpe and result.pct_folds_beat_bh > 0.6:
                  save_as_new_version(mutation, parent=strategy_id)
                  return mutation

          # e. No improvement found
          return None
  ```
- [ ] 2.5 Create strategy lineage tracking
  - New table: strategy_lineage
  - Columns: child_id, parent_id, changes_description, metrics_before, metrics_after
  - Enable rollback: Can revert to parent if child degrades
- [ ] 2.6 Create Celery task: weekly_strategy_evolution
  - Schedule: Weekly Sunday 06:00 UTC (after strategy monitoring)
  - Process: Find underperformers → Attempt evolution → Log results
- [ ] 2.7 Test evolution loop
  - Create strategy with artificially low performance
  - Trigger evolution
  - Verify: Analysis generated, mutations proposed, best one saved

---

### 3.0 AI Rules Validation Agent (Section 3.3)

- [ ] 3.1 Define validation checks
  ```python
  VALIDATION_CHECKS = [
      "all_thresholds_in_valid_range",     # RSI 0-100, etc.
      "no_contradictory_rules",            # Buy at RSI<30 AND RSI>70?
      "fee_assumptions_realistic",          # Commission not 0
      "position_sizing_sums_valid",         # Max positions * max size <= 100%
      "all_referenced_indicators_defined",  # No undefined variables
  ]
  ```
- [ ] 3.2 Create rules validation agent
  - New file: backend/app/agents/rules_validator_agent.py
  - Input: rules.yaml
  - Output: Validation report with pass/fail per check
- [ ] 3.3 Create Celery task: daily_rules_validation
  - Schedule: Daily 03:00 UTC
  - Process: Load rules → Run all checks → Log report
  - Alert: If any critical check fails
- [ ] 3.4 Weekly optimization checks
  ```python
  OPTIMIZATION_CHECKS = [
      "compare_rules_to_recent_performance",
      "identify_unused_rules",
      "propose_threshold_adjustments",
      "flag_rules_that_never_trigger",
  ]
  ```
- [ ] 3.5 Create weekly optimization task
  - Schedule: Weekly Monday 03:00 UTC
  - Process: Analyze rules → Generate recommendations
  - Output: Proposed adjustments (human approval required)

---

## Verification (Updated 2025-12-04 - FACTS)

- [x] Functional: Walk-forward API returns per-fold metrics ✅ VERIFIED (FoldMetrics, WalkForwardResult)
- [ ] Functional: Evolution loop produces improved strategy versions ❌ NOT IMPLEMENTED
- [ ] Functional: Rules validation catches invalid configurations ❌ NOT IMPLEMENTED
- [x] Tests: pytest tests/backtest/ -v passes ✅ VERIFIED (unit + integration exist)
- [ ] Tests: pytest tests/agents/test_evolution.py -v passes ❌ NOT APPLICABLE (feature not implemented)
- [ ] Tests: Walk-forward specific tests ❌ MISSING
- [x] Quality: ~/portfolio-ai/scripts/lint.sh passes ✅ VERIFIED
- [x] Services: Restarted and verified ✅ VERIFIED
- [ ] Manual: Run full evolution cycle, verify lineage tracking ❌ NOT APPLICABLE

## Gaps Found (Verified 2025-12-04)

1. **Strategy Evolution NOT IMPLEMENTED** (Task 2.0):
   - No `strategy_evolution_agent.py`
   - No `strategy_lineage` table
   - No `weekly_strategy_evolution` scheduled task

2. **Rules Validation NOT IMPLEMENTED** (Task 3.0):
   - No `rules_validator_agent.py`
   - No `daily_rules_validation` task
   - No `weekly_optimization` task

3. **Walk-forward tests** ✅ FIXED (2025-12-04):
   - Created test_walk_forward.py with 22 tests
   - Covers window creation, aggregation, Wilcoxon test, full engine run

---

## Files to Create/Modify

**Task 1 (Walk-Forward API)**:
- backend/app/backtest/walk_forward.py (NEW)
- backend/app/api/backtest.py (add endpoint)
- backend/app/strategies/optimizer.py (update ValidationWindow)

**Task 2 (Evolution)**:
- backend/app/agents/strategy_evolution_agent.py (NEW)
- backend/app/storage/migrations/074_strategy_lineage.sql (NEW)
- backend/app/tasks/strategy_monitoring_tasks.py (add evolution task)
- backend/app/celery_schedules.py (add schedule)

**Task 3 (Validation)**:
- backend/app/agents/rules_validator_agent.py (NEW)
- backend/app/tasks/rules_validation_tasks.py (NEW)
- backend/app/celery_schedules.py (add schedules)

---

## Dependencies

- **HARD PREREQUISITE**: Task 0096 (0.1 B&H + 0.2 Rules Engine)
- **HARD PREREQUISITE**: Task 0097 not strictly required but helpful
- This task BLOCKS: Task 4.x (Experimental tier)
- Timeline: Month 2+ (after foundations complete)
