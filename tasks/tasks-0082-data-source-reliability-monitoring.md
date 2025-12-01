<!-- PAUSED: 2025-12-01 08:35 | Context: 85% | Reason: Context limit | Next: Task 0.1 - Scope Discovery -->

# Task List: Data Source Reliability & Monitoring Improvements

**Source**: User request via /task_it - Post-incident improvements after data staleness issues
**Complexity**: Complex
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-01 08:15
**Status**: PAUSED
**Last Updated**: 2025-12-01 08:35
**Pause Reason**: Context limit (85%)
**Next Action**: Task 0.1 - Scope Discovery (full discovery for ALL tasks, not just monitoring)
**Resume Command**: `/do_it tasks/tasks-0082-data-source-reliability-monitoring.md`

---

## Summary

**Goal**: Make data pipelines self-healing, redundant, and bulletproof with proactive monitoring and alerting for stale data conditions.

**Approach**: Add monitoring layer on top of existing Celery tasks, implement automatic remediation for common failures, and create unified health dashboard.

**Scope Discovery**: Required - need to understand existing monitoring patterns and task structures

---

## Context

Recent incident revealed:
- SPY OHLCV data had only 4 days (needed 252) due to deadlock failures
- Technical indicators showed Nov 14 (17 days stale)
- No alerts fired for these conditions
- Root causes: deadlocks, missing credential loading, no self-healing

**Fixes already applied:**
- Changed OHLCV ingestion from DELETE+INSERT to UPSERT (prevents deadlocks)
- Added credential loading from database in data_ingestion_tasks.py
- Graceful handling of missing API keys (falls back to yfinance)

**This task adds:** Monitoring, alerting, self-healing, and redundancy verification

---

## Tasks

### 0.0 Scope Discovery (MANDATORY - Full Discovery for ALL Tasks Below)

**USER CLARIFICATION**: This is not just monitoring discovery - discover ALL code/data related to:
- Self-healing mechanisms (Task 2)
- Data source fallbacks (Task 3)
- Existing status page at http://192.168.8.233:3000/status (Task 4)
- Celery retry patterns (Task 5)

- [ ] 0.1 Explore existing monitoring and self-healing patterns
  - Pattern: maintenance_log, capability_insights, data freshness checks
  - Find: All places where data staleness is already checked
  - Find: Existing alerting mechanisms (logs, status endpoints)
  - Find: Any existing self-healing/auto-retry logic in Celery tasks
  - Find: Data source fallback patterns (like the yfinance fallback added today)
- [ ] 0.2 Document current data source dependencies and pipelines
  - Map: Which tasks depend on which data sources
  - Map: Task execution order and timing
  - Map: All Celery scheduled tasks that pull/refresh data
  - Map: Data flow: API → storage → UI
- [ ] 0.3 Analyze existing Status Page (http://192.168.8.233:3000/status)
  - What data does it already show?
  - What endpoints does it call?
  - What's missing that users need?
  - Set up next agent for success by documenting current state
- [ ] 0.4 Checkpoint: Confirm scope for ALL tasks
  - Existing monitoring coverage: [TBD]
  - Existing self-healing mechanisms: [TBD]
  - Gap areas per task: [TBD]
  - Integration points: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Data Freshness Monitoring with Alerts

- [ ] 1.1 Create data freshness checker service
  - Check all critical tables: day_bars, technical_indicators, fear_greed_daily, options_market_metrics
  - Define "stale" threshold per table (accounting for weekends/holidays)
  - Return structured freshness report
- [ ] 1.2 Add Celery task for periodic freshness checks
  - Run every 2 hours
  - Log WARNING for stale data
  - Create maintenance_log entry for critical staleness
- [ ] 1.3 Implement trading day awareness
  - Skip weekend/holiday staleness alerts
  - Use market calendar for accurate thresholds
- [ ] 1.4 Add freshness check to existing maintain_data_freshness task

### 2.0 Self-Healing Data Pipelines (ENTIRE SOLUTION)

**USER CLARIFICATION**: Not just technical indicators - self-healing mechanisms for our ENTIRE solution that will re-pull data when no/stale/partial data exists.

- [ ] 2.1 Create unified self-healing framework
  - Generic "check freshness → trigger refresh" pattern
  - Apply to ALL data tables, not just indicators
  - Handle: no data, stale data, partial data scenarios
- [ ] 2.2 Self-healing for OHLCV data (day_bars)
  - Check if symbol has <252 days OR data >1 trading day old
  - Trigger maintain_historical_market_data or refresh_daily_ohlcv
- [ ] 2.3 Self-healing for technical_indicators
  - Check if SPY indicators are >1 trading day old
  - Check if required OHLCV data exists (>200 days)
  - Trigger update_technical_indicators
- [ ] 2.4 Self-healing for Fear & Greed pipeline
  - Check fear_greed_inputs freshness
  - Trigger populate_fear_greed_inputs if stale
  - Chain to calculate_fear_greed after successful populate
- [ ] 2.5 Self-healing for Put/Call ratio
  - Check if put_call_ratio in fear_greed_inputs is stale
  - Trigger fetch_putcall_ratio (yfinance with fallbacks)
- [ ] 2.6 Self-healing for reference/fundamental data
  - Check reference_cache freshness per symbol
  - Trigger refresh for stale symbols
- [ ] 2.7 Self-healing for news data
  - Check news_cache age
  - Trigger news refresh if stale
- [ ] 2.8 Create maintain_all_data_freshness umbrella task
  - Single scheduled task that runs ALL self-healing checks
  - Runs frequently (every 2-4 hours during market hours)
- [ ] 2.9 Test self-healing scenarios
  - Simulate stale data conditions for each data type
  - Verify automatic remediation works end-to-end

### 3.0 Redundant Data Source Fallback Verification

- [ ] 3.1 Add source availability logging
  - Log which sources are available at task start
  - Log which source actually provided data
- [ ] 3.2 Create fallback chain verification
  - Ensure yfinance always works (no API key required)
  - Test that fallback actually triggers when primary fails
- [ ] 3.3 Add data source health check task
  - Periodically test each configured source
  - Mark sources as degraded/healthy in source_metrics
- [ ] 3.4 Alert on all-source-failure scenarios
  - If no source can provide data, create critical alert

### 4.0 Unified Data Source Health Dashboard Endpoint

**USER CLARIFICATION**: Check existing status page at http://192.168.8.233:3000/status FIRST before designing new endpoints. Understand what already exists to avoid duplication.

**PREREQUISITE**: Task 0.3 must document existing status page capabilities

- [ ] 4.1 Gap analysis vs existing status page
  - What does /status already show?
  - What backend endpoints does it call?
  - What's missing for data health visibility?
- [ ] 4.2 Extend existing endpoints (prefer over creating new)
  - Add data freshness to existing /api/status/* endpoints if possible
  - Only create new /api/status/data-health if truly needed
  - Include last update time, staleness flag, row counts
- [ ] 4.3 Add data source availability status
  - Show which API sources are configured
  - Show recent success/failure rates per source
- [ ] 4.4 Add pipeline execution status
  - Show last run time for each scheduled task
  - Show success/failure status
  - Show next scheduled run
- [ ] 4.5 Enhance frontend status page (extend existing, don't rebuild)
  - Add data health section to existing status page
  - Color-coded freshness indicators (green/yellow/red)
  - Integrate with existing UI patterns

### 5.0 Celery Task Retry Logic Enhancement

- [ ] 5.1 Add exponential backoff retry decorator
  - Create reusable retry config for data tasks
  - Configure: max_retries=3, base_delay=60s, max_delay=3600s
- [ ] 5.2 Apply retry logic to critical tasks
  - maintain_historical_market_data
  - populate_fear_greed_inputs
  - update_technical_indicators
  - refresh_daily_ohlcv
- [ ] 5.3 Add retry-specific logging
  - Log retry attempts with attempt number
  - Log final failure after all retries exhausted
- [ ] 5.4 Add dead letter handling
  - Track permanently failed tasks
  - Create maintenance_log entry for investigation

---

## Verification

- [ ] Functional: All monitoring endpoints return accurate data
- [ ] Self-healing: Simulate stale data, verify auto-remediation triggers
- [ ] Alerting: Verify maintenance_log entries created for critical conditions
- [ ] Dashboard: New endpoint returns comprehensive health status
- [ ] Retries: Verify exponential backoff works correctly
- [ ] Tests: Add unit tests for freshness checker and self-healing logic
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified
