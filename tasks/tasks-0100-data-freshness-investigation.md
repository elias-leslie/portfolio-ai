# Task List: Data Freshness Investigation

<!-- PAUSED: 2025-12-04 11:30 | Context: 80% | Reason: User request | Next: Task 0.1 - Very thorough exploration -->

**Created**: 2025-12-04
**Status**: PENDING (scheduled from pause)
**Priority**: HIGH
**Effort**: MEDIUM
**Source**: User reported data not fresh despite fixes

---

## Problem Statement

User reports data showing as stale on dashboard despite:
- Symbol standardization fixes (30+ files updated)
- Scheduled task fixes (news_sentiment, fear_greed, technical_indicators)
- Services restarted

Need very thorough investigation using Explore agents to find root cause.

---

## 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Use Explore agent (very thorough) to investigate UI data display
  - Check frontend components showing "last updated"
  - Find where timestamps come from (API vs cache vs DB)
  - Identify timezone handling issues

- [ ] 0.2 Use Explore agent (very thorough) to check backend data freshness
  - Check all tables for latest dates
  - Verify Celery beat schedules are registered
  - Check if tasks are actually running vs skipping

- [ ] 0.3 Use Explore agent (very thorough) to trace data flow
  - From scheduled task → database → API → frontend
  - Find where freshness info is lost or stale

- [ ] 0.4 Use Explore agent (very thorough) to check caching issues
  - Redis cache TTLs and invalidation
  - API response caching (@cache_response decorators)
  - Frontend caching (SWR, React Query, etc.)
  - Check if stale data served from cache despite fresh DB data

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

## 1.0 Fix Data Freshness Display

- [ ] 1.1 Fix any discovered timestamp issues
- [ ] 1.2 Fix any discovered cache issues
- [ ] 1.3 Fix any discovered scheduling issues
- [ ] 1.4 Verify all scheduled tasks run correctly
- [ ] 1.5 Test UI shows current data

---

## 2.0 Verification

- [ ] 2.1 Check dashboard shows today's date for relevant data
- [ ] 2.2 Check scheduled tasks complete without errors
- [ ] 2.3 Browser screenshot verification of dashboard

---

## Resume Command

```bash
/do_it tasks/tasks-0100-data-freshness-investigation.md
```

Use `--max` flag for very thorough Explore agents.
