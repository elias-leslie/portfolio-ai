# Task List: Celery Task Improvements

**Source**: /data_check analysis (2025-12-04) - Medium Priority Issues #10, #11, #12
**Complexity**: Simple
**Effort**: LOW-MEDIUM (~2 hours total)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 15:45

---

## Summary

**Goal**: Improve Celery task configuration with task-specific timeouts, explicit dependencies, and RestApiSource client pooling
**Approach**: Configure each improvement independently
**Scope Discovery**: Required for timeout and dependency analysis

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Analyze current task timeouts
  - File: `backend/app/celery_app.py`
  - Current: 600s hard limit, 540s soft limit for ALL tasks
  - Find: Tasks that timeout or complete quickly
- [ ] 0.2 Analyze task execution times
  - Check Celery logs for typical durations
  - Identify: Backfill tasks (long), API tasks (short), calculation tasks (medium)
- [ ] 0.3 Map task dependencies
  - File: `backend/app/celery_schedules.py`
  - Current: Time-based ordering (02:00, 02:15, 02:30, etc.)
  - Find: Which tasks actually depend on others
- [ ] 0.4 Checkpoint: Confirm scope
  - Tasks needing custom timeout: [TBD]
  - Critical dependency chains: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Configure Task-Specific Timeouts

**Issue**: All tasks have same 600s timeout - backfill tasks may timeout, API tasks waste resources

- [ ] 1.1 Categorize tasks by expected duration
  - Long (1800s): `ingest_historical_ohlcv`, `backfill_technical_indicators`, `maintain_historical_market_data`
  - Medium (300s): `calculate_fear_greed`, `update_portfolio_covariance`, `ingest_fundamental_data`
  - Short (60s): API-calling tasks, health checks, data freshness checks
- [ ] 1.2 Update task decorators with soft_time_limit and time_limit
  ```python
  @celery_app.task(soft_time_limit=1700, time_limit=1800)
  def ingest_historical_ohlcv(...):
  ```
- [ ] 1.3 Test tasks with new timeouts
- [ ] 1.4 Document timeout configuration in OPERATIONS.md

### 2.0 Add Explicit Task Dependencies (Optional)

**Issue**: Tasks rely on implicit time-based ordering - clock drift or long-running tasks can cause issues

- [ ] 2.1 Identify critical dependency chains
  - Chain 1: refresh_daily_ohlcv → refresh_watchlist_ohlcv → backfill_technical_indicators
  - Chain 2: populate_fear_greed_inputs → calculate_fear_greed
  - Chain 3: refresh_yfinance_reference_data → parse_valuation_metrics → refresh_alphavantage_reference_backup
- [ ] 2.2 Consider using Celery chains for critical paths
  ```python
  # Instead of separate scheduled tasks
  chain(
      refresh_daily_ohlcv.s(),
      refresh_watchlist_ohlcv.s(),
      backfill_technical_indicators.s()
  ).apply_async()
  ```
- [ ] 2.3 Evaluate trade-offs
  - Pro: Explicit dependencies, no race conditions
  - Con: Less visibility in Celery beat schedule, harder to run individual tasks
- [ ] 2.4 If implementing, update celery_schedules.py

### 3.0 Add RestApiSource Client Pooling

**Issue**: RestApiSource creates new httpx.Client per instance - no connection pooling

- [ ] 3.1 Analyze RestApiSource usage
  - File: `backend/app/sources/rest_api_source.py:96`
  - Current: `self.client = httpx.Client(timeout=timeout)`
- [ ] 3.2 Implement shared client pool
  ```python
  class RestApiClientPool:
      _clients: dict[str, httpx.Client] = {}
      _lock = threading.Lock()

      @classmethod
      def get_client(cls, base_url: str, timeout: float) -> httpx.Client:
          key = f"{base_url}:{timeout}"
          if key not in cls._clients:
              with cls._lock:
                  if key not in cls._clients:
                      cls._clients[key] = httpx.Client(timeout=timeout)
          return cls._clients[key]
  ```
- [ ] 3.3 Update RestApiSource to use pool
- [ ] 3.4 Add cleanup method for pool (for testing)
- [ ] 3.5 Test with existing RestApiSource usages

---

## Verification

- [ ] Functional: All tasks run successfully with new config
- [ ] Tests: All existing tests pass
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] Services: Restarted and verified
- [ ] Monitoring: Check Celery logs for timeout/timing improvements

---

## Notes

- Task 1 (timeouts) is LOW effort and high value - do first
- Task 2 (dependencies) is MEDIUM effort - evaluate ROI before implementing
- Task 3 (client pooling) is LOW effort - nice performance improvement
- All tasks are independent
