# Task List: Capabilities Scan System Improvements

**Source**: User request via /task_it + /polish_it findings
**Complexity**: Complex
**Effort**: MEDIUM
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-05 09:10

---

## Summary

**Goal**: Make the capabilities scan system accurate, fast (<30s), and self-healing so orphan detection and health status are always correct without manual intervention.

**Approach**: Review all three scanners (API, Celery, DB), fix frontend detection patterns, add comprehensive cleanup logic, optimize query performance, and ensure scheduled execution.

**Scope Discovery**: Required - need to audit all scanner code and frontend API call patterns

---

## Background

Issues discovered during /polish_it:
1. API scanner didn't include router prefix in endpoint paths (FIXED)
2. Frontend usage detection missed template literal patterns
3. Orphan detection had false positives
4. Cleanup logic was missing from API scanner (FIXED)
5. No performance benchmarking

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Audit all scanner implementations
  - Files: capability_api_scanner.py, capability_celery_scanner.py, capability_db_scanner.py
  - Check: Cleanup logic, health status calculation, frontend detection
- [ ] 0.2 Audit frontend API call patterns
  - Search frontend/ for all API call patterns (fetch, axios, useSWR, api.*)
  - Identify patterns not currently detected
- [ ] 0.3 Benchmark current scan performance
  - Time each scanner individually
  - Identify slowest operations
- [ ] 0.4 Checkpoint: Document findings
  - Current scan time: [TBD]
  - Missing patterns: [TBD]
  - Performance bottlenecks: [TBD]

### 1.0 Improve Frontend Usage Detection

- [ ] 1.1 Add template literal detection
  - Pattern: `` `${API_BASE}/api/path` ``
  - Pattern: `` `${baseUrl}/path/${id}` ``
- [ ] 1.2 Add useSWR hook detection
  - Pattern: `useSWR('/api/path'...)`
  - Pattern: `useSWR(\`/api/${path}\`...)`
- [ ] 1.3 Add TanStack Query detection
  - Pattern: `useQuery(['key', '/api/path']...)`
- [ ] 1.4 Add custom API client patterns
  - Pattern: `api.get('/path')`, `apiClient.post('/path')`
- [ ] 1.5 Test with known endpoints that should be detected

### 2.0 Optimize Scan Performance

- [ ] 2.1 Profile current scan operations
  - Use cProfile or timing decorators
  - Identify N+1 queries
- [ ] 2.2 Batch database operations
  - Group INSERTs instead of one-by-one commits
  - Use executemany where possible
- [ ] 2.3 Cache file reads
  - Don't re-read same file multiple times
  - Cache frontend file contents during scan
- [ ] 2.4 Parallelize independent scans
  - Consider running DB, Celery, API scans concurrently
- [ ] 2.5 Target: Scan completes in <30s

### 3.0 Improve Health Status Logic

- [ ] 3.1 Review API health status criteria
  - Active: Has frontend callers OR has table dependencies
  - Orphaned: No callers AND no dependencies
  - Legacy: Exists but deprecated annotation
  - Suspect: Has issues (errors, slow, etc.)
- [ ] 3.2 Add "suspect" detection for APIs
  - Check for error rates from logs
  - Check for slow response times
- [ ] 3.3 Cross-reference with actual usage
  - Check request logs if available
  - Consider adding request counting middleware

### 4.0 Ensure Scheduled Execution & Data Pipeline

- [ ] 4.1 Verify full data pipeline is scheduled
  - Task 1: `scan_all_capabilities` - scans DB/Tasks/Endpoints
  - Task 2: `analyze_capabilities_ai` - generates Insights (ai_analyzer.py)
  - Task 3: `analyze_trading_gaps` - updates Gaps (gap_analysis_tasks.py)
  - Verify: All 3 run in sequence (scan → insights → gaps)
- [ ] 4.2 Add health check for scan freshness
  - Alert if last_scanned_at > 24h ago
  - Show in /capabilities dashboard
- [ ] 4.3 Verify Insights generation is working
  - Check: Are new insights being generated?
  - Check: Is AI analyzer configured and running?
  - Check: What triggers insight generation?
- [ ] 4.4 Verify Gaps analysis is working
  - Check: Are gaps being identified from scan data?
  - Check: Is gap_analysis_tasks running on schedule?

### 5.0 Data Quality Audit (CRITICAL)

- [ ] 5.1 Audit API endpoint data - what's captured vs what's useful
  - Current: endpoint_path, http_method, category, depends_on_tables, health_status
  - Missing? Request count (actual usage), error rate, avg response time
  - Missing? Last called timestamp, caller context (which frontend pages)
  - Missing? Parameter types, return types, authentication required
- [ ] 5.2 Audit Celery task data - is it actionable?
  - Current: task_name, schedule, last_run, success_rate, populates_tables
  - Missing? Last error message, retry count, queue depth
  - Missing? Dependencies between tasks (task A must run before B)
  - Missing? Resource usage (memory, CPU, duration trend)
- [ ] 5.3 Audit DB table data - what insights matter?
  - Current: row_count, freshness, completeness_pct, columns
  - Missing? Growth rate (rows/day), storage size
  - Missing? Query patterns (which tables queried together)
  - Missing? Data quality issues (nulls, duplicates, orphans)
- [ ] 5.4 Gap analysis - what questions can't the UI answer?
  - "Why is this endpoint slow?" - need response time data
  - "Is this task actually running?" - need real-time status
  - "What data is stale?" - need freshness alerts
  - "What's broken?" - need error aggregation

### 6.0 Add Missing Contextual Data

- [ ] 6.1 Add request metrics to API endpoints (if feasible)
  - Middleware to track: request count, error rate, p50/p95 latency
  - Store in api_capabilities or separate metrics table
  - Consider: Is this already tracked elsewhere? (logs, APM)
- [ ] 6.2 Add error context to Celery tasks
  - Capture last_error_message, last_error_at
  - Link to maintenance_log for full history
- [ ] 6.3 Add freshness alerts
  - Flag tables where days_since_update > expected_freshness
  - Show prominently in UI (not buried in list)
- [ ] 6.4 Add cross-reference insights
  - "Endpoint X depends on table Y which is stale"
  - "Task A populates table B but hasn't run in 3 days"

### 7.0 Testing & Verification

- [ ] 7.1 Write unit tests for frontend detection patterns
  - Test all regex patterns against real code snippets
- [ ] 7.2 Validate scan accuracy
  - Pick 10 random endpoints - verify health_status is correct
  - Pick 10 random tasks - verify schedule and last_run accurate
  - Pick 10 random tables - verify row_count and freshness
- [ ] 7.3 User acceptance test
  - Can you answer: "What's broken right now?"
  - Can you answer: "What data is stale?"
  - Can you answer: "What code is unused?"
- [ ] 7.4 Performance benchmark
  - Assert scan < 30s
  - Log timing breakdown by scanner

---

## Verification

- [ ] Functional: All 3 scanners work correctly, no false positives
- [ ] Performance: Full scan completes in <30s
- [ ] Self-healing: Stale entries auto-cleaned on each scan
- [ ] Tests: Unit tests for pattern detection
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] UI: /capabilities page shows accurate data

---

## Files to Modify

- `backend/app/services/capability_api_scanner.py` - Frontend detection, performance
- `backend/app/services/capability_celery_scanner.py` - Review cleanup logic
- `backend/app/services/capability_db_scanner.py` - Review cleanup logic
- `backend/app/tasks/capability_tasks.py` - Performance optimization
- `backend/app/celery_schedules.py` - Verify scheduling
- `frontend/app/capabilities/page.tsx` - Scan status UI (optional)

---

## Already Fixed (from this session)

1. Router prefix now included in endpoint paths
2. Self-healing cleanup added to API scanner
3. Manual DB fix for existing orphan entries
