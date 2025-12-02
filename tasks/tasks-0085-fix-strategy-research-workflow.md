# Task List: Fix Strategy Research Workflow

**Source**: User request via /task_it (bugs discovered during /do_it session)
**Complexity**: Complex
**Effort**: MEDIUM (4-6 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 11:05

---

## Summary

**Goal**: Fix all bugs in the strategy research workflow to enable autonomous backtest/paper trade execution as designed in VISION.md

**Approach**: Systematically test and fix each component of the workflow pipeline: research aggregator, strategy generator, optimizer, and storage

**Scope Discovery**: Required - need to verify all data sources and aggregation methods work

---

## Background

The `weekly_strategy_generation` Celery task was supposed to:
1. Get top 20 watchlist symbols by score
2. Run `strategy_research_workflow` for each symbol
3. Generate strategies via LLM
4. Optimize parameters via backtesting
5. Store and track performance

**Issues discovered (2025-12-02):**
- Task wasn't registered with Celery (FIXED)
- SQL queried non-existent `priority` column (FIXED)
- `research_aggregator.py` queried `news` table instead of `news_cache` (FIXED)
- datetime vs date comparison TypeError (FIXED)
- Remaining methods likely have similar untested bugs

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Map the complete workflow execution path
  - Entry: `weekly_strategy_generation()` in strategy_monitoring_tasks.py
  - Calls: `strategy_research_workflow()` in agents/workflows/
  - Uses: `ResearchAggregator`, `StrategyGenerator`, `StrategyOptimizer`, `StrategyStorage`
- [ ] 0.2 Identify all database tables accessed
  - news_cache (sentiment data)
  - day_bars (price/technical data)
  - watchlist_items, watchlist_snapshots (symbol selection)
  - strategy_definitions, strategy_performance (output storage)
  - Any others referenced in code
- [ ] 0.3 Document current test coverage
  - Check for existing tests in tests/strategies/
  - Note which methods have no tests
- [ ] 0.4 Checkpoint: Confirm scope
  - Files affected: [TBD after 0.1-0.3]
  - Methods needing fixes: [TBD]
  - Estimated remaining effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Fix Research Aggregator Methods

- [ ] 1.1 Test `_aggregate_news_intelligence()` end-to-end
  - Verify news_cache query returns data
  - Verify sentiment calculations work
  - Fix any remaining datetime issues
- [ ] 1.2 Test `_aggregate_fundamental_analysis()`
  - Check which tables it queries
  - Verify data exists and query works
  - Fix table names or schema mismatches
- [ ] 1.3 Test `_aggregate_technical_analysis()`
  - Check day_bars queries
  - Verify indicator calculations
  - Fix any issues found
- [ ] 1.4 Test `_aggregate_macro_context()`
  - Check fear_greed data access
  - Verify economic indicator queries
  - Fix any issues found
- [ ] 1.5 Run full `aggregate_research()` successfully for one symbol

### 2.0 Fix Strategy Generator

- [ ] 2.1 Test LLM prompt generation
  - Verify research data is formatted correctly for prompt
  - Check prompt template exists and is valid
- [ ] 2.2 Test LLM API call
  - Verify Claude/Gemini credentials work
  - Test with mock data if needed to avoid costs
  - Verify response parsing works
- [ ] 2.3 Test strategy output validation
  - Verify StrategyParameters model validates correctly
  - Check all required fields are populated

### 3.0 Fix Strategy Optimizer

- [ ] 3.1 Test parameter grid generation
  - Verify combinations are generated correctly
  - Check weight constraints (sum = 1.0)
- [ ] 3.2 Test backtest integration
  - Verify `replay_backtest()` is called correctly
  - Check historical data availability
- [ ] 3.3 Test walk-forward optimization
  - Verify train/test window splits
  - Check metric calculations

### 4.0 Fix Strategy Storage

- [ ] 4.1 Verify strategy_definitions table schema matches code
  - Check all columns exist
  - Verify data types match
- [ ] 4.2 Test `store_strategy()` method
  - Insert a test strategy
  - Verify all fields saved correctly
- [ ] 4.3 Test `get_active_strategy()` retrieval
  - Verify query returns correct data
  - Check status filtering works

### 5.0 End-to-End Integration Test

- [ ] 5.1 Run `weekly_strategy_generation()` for 1 symbol
  - Use a well-covered symbol (e.g., GOOGL)
  - Monitor logs for errors
  - Verify strategy is created
- [ ] 5.2 Run for 3 symbols sequentially
  - Test batch processing
  - Check for resource/rate limit issues
- [ ] 5.3 Verify scheduled execution works
  - Check Celery Beat recognizes the task
  - Optionally trigger manually via Celery

### 6.0 Add Monitoring & Error Handling

- [ ] 6.1 Add detailed logging to workflow steps
  - Log entry/exit of each major function
  - Log data counts (news articles, bars, etc.)
- [ ] 6.2 Add graceful fallbacks for missing data
  - If no news data, continue with reduced confidence
  - If no technical data, skip that component
- [ ] 6.3 Add workflow status tracking
  - Store workflow attempts in database
  - Track success/failure rates

---

## Verification

- [ ] Functional: `weekly_strategy_generation()` completes for 5+ symbols without errors
- [ ] Tests: Add unit tests for fixed methods (target 80%+ for research_aggregator)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: Restarted and verified (bash ~/portfolio-ai/scripts/restart.sh)
- [ ] Logs: Workflow execution visible in Celery logs
- [ ] Data: At least 1 strategy created in strategy_definitions table

---

## Files Likely Affected

- `backend/app/tasks/strategy_monitoring_tasks.py` - Entry point
- `backend/app/agents/workflows/strategy_research_workflow.py` - Orchestration
- `backend/app/strategies/research_aggregator.py` - Data collection (BUGS FOUND)
- `backend/app/strategies/strategy_generator.py` - LLM generation
- `backend/app/strategies/optimizer.py` - Parameter optimization
- `backend/app/strategies/storage.py` - Database operations
- `backend/app/strategies/models.py` - Data models

---

## Known Fixed Issues (2025-12-02)

1. ✅ `strategy_monitoring_tasks` not imported in celery_app.py
2. ✅ SQL used `ORDER BY priority` but column doesn't exist (changed to overall_score)
3. ✅ `research_aggregator.py` queried `news` table (changed to `news_cache`)
4. ✅ datetime.date vs datetime.datetime comparison in sentiment analysis
