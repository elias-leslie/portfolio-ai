# Task List: Data Source Reliability & Monitoring Improvements

**Source**: User request via /task_it - Post-incident improvements after data staleness issues
**Complexity**: Complex
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-01 08:15

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

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Explore existing monitoring patterns
  - Pattern: maintenance_log, capability_insights, data freshness checks
  - Find: All places where data staleness is already checked
  - Find: Existing alerting mechanisms (logs, status endpoints)
- [ ] 0.2 Document current data source dependencies
  - Map: Which tasks depend on which data sources
  - Map: Task execution order and timing
- [ ] 0.3 Checkpoint: Confirm scope
  - Existing monitoring coverage: [TBD]
  - Gap areas: [TBD]
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

### 2.0 Self-Healing Technical Indicators

- [ ] 2.1 Add staleness detection for technical_indicators
  - Check if SPY indicators are >1 trading day old
  - Check if required OHLCV data exists (>200 days)
- [ ] 2.2 Implement auto-recalculation trigger
  - If indicators stale AND OHLCV data sufficient, trigger update_technical_indicators
  - Add to maintain_data_freshness task
- [ ] 2.3 Add self-healing for Fear & Greed pipeline
  - Check fear_greed_inputs freshness
  - Trigger populate_fear_greed_inputs if stale
  - Chain to calculate_fear_greed after successful populate
- [ ] 2.4 Test self-healing scenarios
  - Simulate stale data conditions
  - Verify automatic remediation

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

- [ ] 4.1 Create /api/status/data-health endpoint
  - Return freshness status for all data sources
  - Include last update time, staleness flag, row counts
- [ ] 4.2 Add data source availability status
  - Show which API sources are configured
  - Show recent success/failure rates per source
- [ ] 4.3 Add pipeline execution status
  - Show last run time for each scheduled task
  - Show success/failure status
  - Show next scheduled run
- [ ] 4.4 Create frontend component for status page
  - Display data health in existing status page
  - Color-coded freshness indicators (green/yellow/red)

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
