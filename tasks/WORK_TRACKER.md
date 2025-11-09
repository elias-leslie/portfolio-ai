# Work Tracker

**Last Updated:** 2025-11-08 (Workflow Simplification)

**Current Status:** Watchlist bug fixes complete, ready for next planned work

---

## 🔄 Active Tasks

*Currently working on - use `/do_it` to auto-resume*

*Empty - run `/do_it` to start next planned task*

---

## 📋 Planned Tasks

*Prioritized queue - `/do_it` picks first when Active is empty*

1. **Portfolio-Watchlist Integration & News Cleanup**
   - File: `tasks-0036-portfolio-watchlist-integration-news-cleanup.md`
   - Effort: MEDIUM (3-4 hours)
   - Priority: HIGH
   - Goal: Auto-sync portfolio→watchlist, add portfolio indicators, streamline news UI
   - Created: 2025-11-08

2. **Portfolio/Watchlist UI & Data Model Fixes**
   - File: `tasks-ui-portfolio-watchlist-fixes.md`
   - Effort: MEDIUM-HIGH (8-12 hours)
   - Priority: URGENT
   - Goal: Fix portfolio accounts UI, clarify watchlist independence, prevent data loss
   - Created: 2025-11-07

3. **HTTP Client Deduplication**
   - File: `tasks-0034-http-client-deduplication.md`
   - Effort: MEDIUM (2-3 days)
   - Priority: MEDIUM
   - Goal: Eliminate 1,469 lines of duplicate HTTP client code
   - Created: 2025-11-07

4. **Database Query Deduplication**
   - File: `tasks-0035-database-query-deduplication.md`
   - Effort: MEDIUM-HIGH (8-12 hours)
   - Priority: HIGH
   - Goal: Fix duplicate queries and API calls (60-80% reduction target)
   - Created: 2025-11-07

5. **Code Quality Improvements** (PAUSED)
   - File: `tasks-0033-code-quality-improvements.md`
   - Status: 50% complete (6/6 files in Phase 1 done)
   - Effort: HIGH (10-15 hours)
   - Priority: LOW
   - Goal: Improve health score 7.95/10 → 9.0/10
   - Paused: 2025-11-04

6. **Trading Intelligence Roadmap** (FUTURE)
   - File: `tasks-trading-intelligence-roadmap.md`
   - Effort: VERY HIGH (multi-week)
   - Priority: FUTURE (Q1 2026)
   - Goal: Combine news+fundamentals+technicals for data-backed trading strategies

---

## ✅ Recently Completed

*Last 5 completions - older items auto-archive to tasks/archive/YYYY-MM.md*

1. **Critical Watchlist Bug Fixes** (2025-11-08)
   - Fixed: Price column, sorting, duplicate news, fundamental scoring, news loading
   - Commits: b04b420, 188bf0a, ccd8315, 7313116, 13e0ba0
   - Branch: `claude/watchlist-vision-implementation-011CUw9W27dCwbxtwbECZsKT`
   - Status: 100% complete, ready to merge

2. **Watchlist Improvements Part 2** (2025-11-08)
   - 3-pillar scoring (price/technical/fundamental) with UI breakdown
   - Commits: cddff66, af98369
   - Status: 81% complete (settings sliders deferred to Part 3)

3. **Service Account Post-Reboot Verification** (2025-11-07)
   - Verified auto-start on boot, fixed 3 post-reboot issues
   - Commit: 4c3c595
   - All services running as portfolio-ai user

4. **System Resource Optimization** (2025-11-07)
   - Memory: 10GB → 5.2GB (48% reduction)
   - Processes: 37 → 5 (86% reduction)
   - Systemd-only service management

5. **Market Conditions Per-Item Timestamps** (2025-11-07)
   - Added accurate freshness timestamps to all indicators
   - Commit: f87f271

---

## 📊 Quick Stats

- **Active Features**: Narrative Intelligence (100%), News Intelligence (75%), Watchlist (100%)
- **Test Count**: 508 tests passing
- **Coverage**: 85% backend
- **Database**: PostgreSQL (portfolio_ai + portfolio_ai_test)

---

## 🎯 Usage

```bash
/task_it <desc>     # Smart task creation (simple or complex, adds Task 0 when needed)
/do_it              # Auto-resume Active or start first Planned
/do_it tasks-*.md   # Work on specific task
/pause_it           # Save state when context >85% or blocked
/doc_it             # Update documentation after major changes
```

**Workflow:**
1. `/task_it` → Analyzes complexity, asks questions if complex, adds Task 0 for scope discovery
2. `/do_it` → Autonomous execution (stops at Task 0 checkpoint if present)
3. `/pause_it` → Save state (auto-archives if Recently Completed >5)
4. Resume next session → `/do_it` picks up where you left off

**Task 0:** Mandatory scope discovery for pattern/refactor work - prevents incomplete implementations

---

## 📁 Archive

Older completions and historical work: `tasks/archive/YYYY-MM.md`
