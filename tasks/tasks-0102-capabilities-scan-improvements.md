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

### 4.0 Ensure Scheduled Execution

- [ ] 4.1 Verify scan is scheduled in celery_schedules.py
  - Task: scan_all_capabilities
  - Schedule: Daily or more frequent
- [ ] 4.2 Add health check for scan freshness
  - Alert if last_scanned_at > 24h ago
  - Show in /capabilities dashboard
- [ ] 4.3 Add manual trigger button
  - "Scan System" button should be prominent
  - Show scan progress/status

### 5.0 Testing & Verification

- [ ] 5.1 Write unit tests for frontend detection patterns
  - Test all regex patterns against real code snippets
- [ ] 5.2 Add integration test for full scan
  - Run scan, verify no false positives
  - Verify known endpoints detected correctly
- [ ] 5.3 Performance benchmark test
  - Assert scan < 30s
  - Log timing breakdown

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
