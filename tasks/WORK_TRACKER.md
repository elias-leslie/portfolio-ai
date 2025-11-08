# Portfolio AI - Work Tracker

**Last Updated:** 2025-11-07 (System Resource Optimization completed)

**📊 Implementation Reality Check:** Narrative Intelligence 100% complete, News Intelligence 75% complete, Market Conditions enhanced with per-item timestamps, System resource usage optimized (48% RAM reduction)

---

## 🔄 Active (Currently Working)

- **[INFRA] Service Account Setup - Post-Reboot Verification**
  - **File:** `tasks/PAUSE-HANDOFF-20251107-2116-reboot.md`
  - **Status:** PAUSED - Awaiting server reboot
  - **Started:** 2025-11-07
  - **Pause Reason:** Reboot required to verify service account setup
  - **Next:** Reboot server, run verification steps 1-6 from handoff

---

## 📋 Planned (Prioritized by User Goal & Dependencies)

### TIER 1: Critical for User Goal (Easy-to-digest market intelligence)

1. **[TASK-0035] News Intelligence - Phase 2: Plain Language UI** - PAUSED
   - **File:** `tasks/news-phase2-plain-language-ui.md`
   - **Status:** 40% complete - PAUSED 2025-11-06
   - **Effort:** MEDIUM (6-8 hours remaining, 1-2 days)
   - **Priority:** ⭐⭐⭐⭐ HIGH
   - **User Goal Alignment:** EXCELLENT - Zero-jargon news intelligence
   - **Actual Progress (verified via code exploration):**
     - ✅ Tasks 1-2: Story clustering DONE (69% of articles clustered)
     - ⚠️ Task 2: Plain language translation PARTIAL (only 32% coverage, need 90%+)
     - ✅ Task 3: API integration DONE (NewsIntelligence models exist)
     - ✅ Task 4: Frontend card DONE but missing actionable_insight display (1-line fix)
     - ⏹️ Task 5: Priority indicators (📋📈📰) NOT IMPLEMENTED - High value
     - ⏹️ Task 6: "Big Stories" + "Watchlist Impact" sections NOT IMPLEMENTED
     - ⏹️ Task 7: News content filter settings NOT IMPLEMENTED
     - ⏹️ Tasks 8-10: Testing/docs/performance PARTIAL
   - **What's Really Left:**
     - Increase plain_language_headline coverage from 32% → 90%
     - Add actionable_insight to NewsIntelligenceCard (simple)
     - Implement priority indicators in main watchlist table
     - Add "Today's Big Stories" section to /news page
     - Add user settings for content filters
   - **Dependencies:** Benefits from Phase 3 cleanup (can run in parallel)
   - **Critical Gap:** Actionable insights generated in backend but NOT displayed in UI

2. **[TASK-0036] News Intelligence - Phase 3: Cleanup & Polish**
   - **File:** `tasks/news-phase3-cleanup-and-polish.md`
   - **Status:** 0% complete
   - **Effort:** MEDIUM (6-8 hours, 1-2 days)
   - **Priority:** ⭐⭐⭐⭐ HIGH
   - **User Goal Alignment:** EXCELLENT - Quality over quantity (reduce noise)
   - **What it does:**
     - Fix Finnhub credential loading (currently 0 articles despite integration)
     - Audit and remove low-quality RSS feeds (reduce noise)
     - Debug RSS feeds returning 0 articles (7 sources integrated, some not fetching)
     - Implement content filtering (remove promotional content, ads)
     - Optimize article mix (prevent single vendor dominance)
     - Monitor deduplication ratio (target 50-70%)
   - **Dependencies:** None - can start immediately
   - **Value:** Ensures high signal-to-noise ratio for news intelligence

### TIER 2: Verification & Final Polish

3. **[TASK-0038] News Source Enhancements - Final Verification** - MERGE
   - **File:** `tasks/news-source-enhancements.md`
   - **Status:** 95% complete (only Task 11.3 remaining)
   - **Effort:** LOW (1 hour)
   - **Priority:** ⭐⭐⭐ MEDIUM
   - **Action:** MERGE Task 11.3 (Finnhub verification) into TASK-0036 Phase 3
   - **What's Done:**
     - ✅ User-configurable lookback window (news_lookback_hours)
     - ✅ Multi-vendor aggregation (12 sources: SEC EDGAR, Polygon, Finnhub, FMP, Yahoo, Google, 7 RSS)
     - ✅ Vendor toggles via env flags
     - ✅ Max articles configurable (news_max_articles preference)
     - ✅ Round-robin vendor selection (prevents single-source dominance)

4. **[TASK-0039] News Surface Implementation - Final QA** - VERIFICATION
   - **File:** `tasks/tasks-implementation-notes-news-surface.md`
   - **Status:** 80% complete (just needs QA sign-off)
   - **Effort:** LOW (2 hours - manual QA checklist)
   - **Priority:** ⭐⭐⭐ MEDIUM
   - **What's Done (verified via code exploration):**
     - ✅ Backend NewsService fully implemented
     - ✅ All 5 API endpoints working (/market, /symbol, /watchlist, /health, /search)
     - ✅ Frontend /news page fully functional (675 lines)
     - ✅ Watchlist news card embedded (216 lines)
     - ✅ FinBERT sentiment analysis (99.9% coverage)
     - ✅ Story clustering active (69% of articles)
   - **What's Left:** Execute manual QA checklist, capture screenshots for docs
   - **Action:** Quick verification pass, then archive

### TIER 3: Code Health (Not user-facing)

5. **[TASK-0034] HTTP Client Deduplication (Critical Code Cleanup)** - NEW
   - **File:** `tasks/tasks-0034-http-client-deduplication.md`
   - **Status:** 0% complete
   - **Effort:** MEDIUM (2-3 days)
   - **Priority:** ⭐⭐⭐ MEDIUM (high ROI for code health)
   - **Created:** 2025-11-07
   - **What it does:**
     - Eliminate 1,469 lines of duplicate code (61% reduction) across 5 API clients
     - Create BaseHTTPClient abstraction (solves 3 critical issues in 1 refactoring)
     - Single source of truth for retry logic, rate limiting, HTTP handling
   - **Impact:**
     - 🔴 HTTP Client Duplication: 5 clients with 95% identical code → eliminated
     - 🔴 Retry Logic Duplication: Same function copied 5 times → eliminated
     - 🔴 Rate Limiting Duplication: Same algorithm copied 5 times → eliminated
   - **Dependencies:** None - can start immediately
   - **Value:** High ROI (1 refactoring fixes 3 critical issues), easier maintenance, easier to add new API sources

6. **[TASK-0035] Database Query & Data Fetching Deduplication** - NEW
   - **File:** `tasks/tasks-0035-database-query-deduplication.md`
   - **Status:** 0% complete
   - **Effort:** MEDIUM-HIGH (8-12 hours, 2-3 sessions)
   - **Priority:** ⭐⭐⭐⭐ HIGH (critical performance + API quota waste)
   - **Created:** 2025-11-07
   - **What it does:**
     - Fix duplicate queries and redundant API calls identified in database analysis
     - **VALIDATION-FIRST approach**: Prove each issue exists with measurements before fixing
     - Target: 60-80% reduction in duplicate queries/API calls
   - **Issues to Investigate & Fix** (validate first, then fix):
     1. 🔴 Overlapping news fetches between 2 Celery tasks (both run every 60s)
     2. 🔴 Per-symbol news fetching in loop (N calls vs 1 batch)
     3. 🟡 User preferences queried 5 times per task (could be 1 query)
     4. 🟡 Watchlist items queried twice by different tasks
     5. 🔴 N+1 query pattern in get_items_with_scores() (snapshots queried individually)
   - **Approach:** VALIDATE → FIX → VERIFY (facts only, no assumptions)
   - **Impact:** Massive API quota savings + 30-50% faster watchlist refresh
   - **Dependencies:** None - can start immediately
   - **Value:** Critical for performance, reduces API costs, improves responsiveness

7. **[TASK-0033] Code Quality Improvements (Health Check Remediation)** - PAUSED
   - **File:** `tasks/tasks-0033-code-quality-improvements.md`
   - **Status:** 50% complete (Phase 1: 6/6 files refactored) - PAUSED 2025-11-04
   - **Effort:** HIGH (10-15 hours, 2-3 sessions)
   - **Priority:** ⭐⭐ LOW (code health, not user-facing)
   - **What's Done:**
     - ✅ Phase 1: scoring_service.py refactored (922→409 lines)
   - **What's Left:**
     - Phase 1 remaining: 5 more files to refactor (rest_api_source, api/watchlist, paper_trading, api/health, watchlist_service)
     - Phase 2: Type safety improvements (reduce Any usage)
     - Phase 3: Documentation completeness (7 missing API endpoints)
     - Phase 4: Minor improvements (holiday calendar, pre-commit docs)
   - **Dependencies:** None
   - **Defer Until:** User-facing features complete
   - **Goal:** Improve health score 7.95/10 → 9.0/10

### TIER 4: Future Vision (Strategic Roadmap)

6. **[TASK-0040] Integrated Trading Intelligence Roadmap**
   - **File:** `tasks/tasks-trading-intelligence-roadmap.md`
   - **Status:** 0% complete - FUTURE WORK
   - **Effort:** VERY HIGH (multi-week effort)
   - **Priority:** ⭐⭐⭐⭐⭐ FUTURE (ultimate goal)
   - **User Goal Alignment:** PERFECT - "High risk/reward strategies backed by data"
   - **What it does:**
     - Combine news intelligence + fundamentals + technical indicators
     - Deterministic strategy engine (rule-based recommendations)
     - Paper trading harness with backtesting
     - LLM reviewer as analyst (not executor)
     - Performance metrics, attribution, drift detection
   - **Dependencies:**
     - News Intelligence Phase 2+3 complete
     - Market Conditions enhancements complete (✅ DONE)
     - Fundamental scoring service complete (exists but not fully utilized)
   - **Timeline:** Q1 2026 earliest
   - **Value:** Ultimate destination for data-backed trading strategies

---

## ✅ Recently Completed (Last 5)

- **System Resource Optimization** ✓ 2025-11-07 (COMPLETE)
  - **Implementation:** Comprehensive systemd service optimization and resource usage reduction
  - **Duration:** ~1 session (investigation + implementation + verification)
  - **Changes:**
    - ✅ Eliminated duplicate processes (37 → 5 processes, 86% reduction)
    - ✅ Optimized Celery worker concurrency (16 → 2, based on actual usage analysis)
    - ✅ Fixed systemd + manual script conflicts (moved to systemd-only)
    - ✅ Installed production-appropriate sudo rules for service management
    - ✅ Removed --reload flag from uvicorn (eliminated duplicate backend process)
    - ✅ Added DB connection pool environment variables (DB_POOL_SIZE=3, DB_MAX_OVERFLOW=2)
  - **Files Modified:**
    - /etc/systemd/system/portfolio-celery.service (added --concurrency=2)
    - /etc/systemd/system/portfolio-backend.service (added DB pool env vars)
    - /etc/sudoers.d/portfolio-ai-services (passwordless service management)
    - ~/portfolio-ai/scripts/start.sh (--concurrency=2, removed --reload)
    - ~/portfolio-ai/scripts/restart.sh (--concurrency=2, removed --reload)
    - ~/portfolio-ai/scripts/portfolio-ai-celery-worker.service (--concurrency=2)
  - **Results:**
    - Memory: 10GB → 5.2GB (48% reduction, ~5GB saved)
    - Processes: 37 → 5 (86% reduction, 32 fewer idle workers)
    - Concurrency: 32 workers → 4 workers (matched to actual workload)
    - CPU overhead: Eliminated 31 idle worker processes
  - **Root Causes Found:**
    - Duplicate Celery workers: systemd service + manual scripts running simultaneously
    - Duplicate Celery Beat: Two schedulers triggering same tasks
    - Default concurrency: Using CPU count (16) instead of workload-based (2)
    - Manual scripts: Creating orphaned processes not managed by systemd
  - **Analysis:**
    - Measured actual worker utilization: Only 1 of 32 workers actively used
    - Task rate: ~4 tasks/minute (mostly skipped due to refresh intervals)
    - Execution pattern: Serial (one task at a time), no parallelism needed
    - Optimal concurrency: 2 workers (100% headroom over actual usage)
  - **Production Setup:**
    - Systemd services: Primary management interface (enabled, auto-restart)
    - Sudo rules: Passwordless restart/status/logs for portfolio-* services only
    - Manual scripts: Updated for consistency but systemd is authoritative
    - Security: All processes run as kasadis user (non-root), proper least-privilege
  - **User Impact:** Significantly reduced resource footprint while maintaining same functionality and responsiveness

- **Market Conditions - Per-Item Timestamps** ✓ 2025-11-07 (COMPLETE)
  - **Implementation:** Added accurate data freshness timestamps to all market indicators
  - **Commit:** f87f271 (feat: Add per-item timestamps to Market Conditions card)
  - **Changes:**
    - ✅ Backend: Added last_updated to ComponentScore, SectorScore, and indicator dicts
    - ✅ Backend: Use PriceData.cached_at for accurate timestamps (respects 15-min cache TTL)
    - ✅ Frontend: Created formatRelativeTime() utility ("12m ago", "1h ago" format)
    - ✅ Frontend: Display timestamps on all 4 top indicators
    - ✅ Frontend: Display timestamps on all 4 component breakdowns
    - ✅ Frontend: Display timestamps on all 11 sector ETFs
    - ✅ Testing: Created expand-click-screenshot.js for expandable UI testing
    - ✅ Documentation: Comprehensive browser automation README.md
  - **Files Modified:**
    - backend/app/api/market.py (accurate cache timestamps)
    - frontend/lib/utils.ts (formatRelativeTime)
    - frontend/lib/api/market.ts (TypeScript types)
    - frontend/components/portfolio/MarketConditions.tsx (timestamp display)
    - .claude/skills/browser-automation/ (testing infrastructure)
  - **User Impact:** See actual data age per indicator - identify stale data sources immediately
  - **Screenshot:** Shows "12m ago" on all indicators (actual 15-min cache age)

- **Status Page Display Alignment Fixes** ✓ 2025-11-07 (COMPLETE)
  - **Implementation:** Fixed three major misalignments between status page and reality
  - **Commit:** 8ce859f (Merge to main)
  - **Changes:**
    - ✅ Data Sources: RSS sources now use news_cache timestamps (accurate "1m ago")
    - ✅ Beat Schedule: Shows user-configured intervals ("Every 15 min") not polling (60s)
    - ✅ Celery Tasks: Proper names, metadata, dark mode colors
    - ✅ Enabled result_extended=True for task metadata storage
    - ✅ Cleaned up 23,629 old celery_taskmeta records
  - **Files Modified:**
    - backend/app/utils/health_checks.py
    - backend/app/api/celery_endpoints.py
    - backend/app/celery_app.py
    - backend/app/services/celery_inspector.py
    - frontend/components/status/CeleryTaskTable.tsx
  - **User Impact:** Status page now accurately reflects system behavior

- **Market Conditions - Sector Performance Data Pipeline** ✓ 2025-11-07 (COMPLETE)
  - **Implementation:** Fixed table names and added automated sector ETF data refresh
  - **Commit:** 6974a42 + f87f271 (Merge to main + timestamps)
  - **Status:** ⭐⭐⭐⭐⭐ 100% COMPLETE
  - **Changes:**
    - ✅ Fixed table reference: daily_ohlcv → day_bars, symbol → ticker
    - ✅ Added 11 sector ETFs to Beat schedule (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLU, XLRE, XLB, XLC)
    - ✅ Populated 5 days of historical data (Oct 31 - Nov 6)
    - ✅ Automated daily refresh via Celery Beat (02:00 UTC)
    - ✅ API returns sector performance with change % and signals
    - ✅ Frontend displays 11 sectors with 🟢🟡🔴 indicators
    - ✅ Per-item timestamps added (f87f271)
  - **Files Modified:**
    - backend/app/api/market.py
    - backend/app/celery_app.py
  - **User Impact:** Sector breakdown shows live data with daily change % and actual freshness

- **Market Conditions Enhancement - Real-Time Scoring** ✓ 2025-11-07 (COMPLETE)
  - **Implementation:** Replaced Fear & Greed Index with enhanced Market Conditions card
  - **Status:** ⭐⭐⭐⭐⭐ MERGED TO MAIN
  - **What Changed:**
    - ✅ Removed Fear & Greed Index (outdated daily EOD data)
    - ✅ Removed Investment Ideas section from homepage
    - ✅ Added real-time market health scoring (0-100 scale)
    - ✅ 4 component scores: VIX, S&P 500, Treasury Yields, US Dollar
    - ✅ Expandable details with interpretations and methodology
    - ✅ Color-coded signals (Bullish/Neutral/Bearish)
    - ✅ Cleaned up 1,777 lines of unused backend code
  - **Backend:** ComponentScore and MarketHealthScore models in /api/market/conditions
  - **Frontend:** Completely rewritten MarketConditions.tsx with expandable UI
  - **User Impact:** Real-time market sentiment (not stale), clear visual indicators, educational context

- **[PRD-0021] Narrative Intelligence System** ✓ 2025-11-06 (100% COMPLETE)
  - **Implementation:** Fully operational, all features working in production
  - **Status:** ⭐⭐⭐⭐⭐ VERIFIED VIA CODE EXPLORATION
  - **Database:** ALL 23 narrative fields in watchlist_snapshots (migrations 008 + 009)
  - **Backend:**
    - Signal classification: BUY/HOLD/AVOID with 8 confirming indicators
    - Trading styles: Index/Event/Swing/Trend/Value (hierarchical)
    - Trade calculations: Entry/stop/target/position sizing
    - 6 narrative generators: headline, technical, company health, action plan, position sizing, special notes
    - Fundamental fetching: YFinance → Finnhub → FMP with health classification
  - **API:** All narrative fields in /api/watchlist response
  - **Frontend:** Complete "Trading Intelligence" section with badges, grids, formatted text
  - **Tests:** 49 comprehensive tests, all passing
  - **Evidence:**
    - `/home/kasadis/portfolio-ai/backend/app/watchlist/signal_classifier.py` (lines 17-225)
    - `/home/kasadis/portfolio-ai/backend/app/watchlist/narrative_generator.py` (lines 14-418)
    - `/home/kasadis/portfolio-ai/frontend/components/watchlist/ExpandedRow.tsx` (lines 280-650)
  - **User Impact:** Zero-jargon trade insights, plain-language narratives, actionable entry/stop/target levels

- **[TASK-0034] Folder Structure Reorganization** ✓ 2025-11-06 (COMPLETE)
  - **Duration:** ~1 session (HIGH complexity completed efficiently)
  - **Results:**
    - ✅ 508 backend tests reorganized (unit/ & integration/)
    - ✅ 8 frontend component tests created
    - ✅ 14 E2E test cases created (Playwright)
    - ✅ Unified test runner script (test-all.sh)
  - **Impact:** Significantly improved developer experience

- **[PRD-News Intelligence - Phase 1: SEC EDGAR Integration** ✓ 2025-11-06 (COMPLETE)
  - **Results:**
    - ✅ CIK cache system (9,998 mappings)
    - ✅ SECEdgarSource adapter integrated (priority 5, highest)
    - ✅ Database migration 015 (filing_type, is_material_event, plain_language_headline)
    - ✅ Multi-source concat working (12 sources total)
    - ✅ Health endpoint shows SEC EDGAR configured
  - **Note:** Source integrated but currently fetching 0 articles (debug in Phase 3)

- **[TASK-0031] Status Dashboard - Phases 4-5 (Resources + Controls)** ✓ 2025-11-04 (COMPLETE)
  - **Results:**
    - ✅ System resource monitoring (disk, memory, CPU, DB pool)
    - ✅ Service control endpoints (restart, cache clear, refresh)
    - ✅ Frontend resource cards with color-coded progress
    - ✅ 6 comprehensive tests passing

---

## 🗄️ Archived (Moved to archive/)

### Completed Task Lists
- tasks-0034-folder-structure-reorganization.md (100% complete)
- tasks-path-standardization.md (100% complete)
- tasks-0015-postgresql-migration.md (100% complete)
- tasks-prd-watchlist-fixes.md (100% complete)
- prd-watchlist-fixes.md (100% complete)

### Deprecated/Superseded
- **tasks-0022-watchlist-intelligence-2.md** → SUPERSEDED by PRD-0021 implementation
  - Status: 95% of features implemented via different path
  - What was done: Narrative intelligence fully operational (signal classification, trading styles, trade calculations, fundamentals)
  - Unique feature NOT implemented: Priority indicators (📋📈📰) in main table
  - Action: Extract priority indicators feature to news-phase2-plain-language-ui.md (Task 5)
  - Archived: 2025-11-07

### Old Handoff Files (Archived to archive/handoffs/2025-11/)
- PAUSE-HANDOFF-2025-11-04-*.md
- PAUSE-HANDOFF-2025-11-03-*.md
- PAUSE-HANDOFF-20251106-*.md
- HANDOFF-20251106-*.md
- PROGRESS-HANDOFF-*.md
- SEC-EDGAR-*.md

---

## 📊 Summary Statistics

**Active Features in Production:**
- ✅ Narrative Intelligence: 100% complete (23 database fields, all populated)
- ✅ News Intelligence Backend: 90% complete (12 sources, FinBERT, story clustering)
- ⚠️ News Intelligence Frontend: 70% complete (missing actionable insights display)
- ⚠️ News Sources: 75% active (SEC EDGAR + Finnhub not fetching, need debug)
- ✅ Watchlist Intelligence: 100% complete (scoring, fundamentals, news integration)
- ✅ Status Dashboard: 100% complete (resources, controls, Celery monitoring)

**Task List Health:**
- Planned: 6 tasks (2 high priority, 2 medium, 1 low, 1 future)
- Paused: 2 tasks (News Phase 2, Code Quality)
- Completed: 5 recent + ~30 archived
- Archived: 6 completed + 8 handoffs + 1 deprecated

**Current Database Stats (verified via exploration):**
- 2,004 news articles cached
- 99.9% FinBERT sentiment coverage
- 69% story clustering coverage
- 32% plain language headline coverage (target: 90%)
- 68% impact summary coverage
- 0 SEC EDGAR filings (source integrated but not fetching)

---

## 🎯 Next Actions (Recommended Priority)

**Immediate (User-Facing Value):**
1. Resume TASK-0035 (News Phase 2) - Complete priority indicators + actionable insights display
2. Start TASK-0036 (News Phase 3) - Fix source quality issues (Finnhub, SEC EDGAR, RSS)

**Short-Term (Polish):**
3. Complete TASK-0039 (News Surface QA) - Final verification, then archive
4. Merge TASK-0038 into TASK-0036 - Consolidate news cleanup work

**Defer (Code Health):**
5. TASK-0033 (Code Quality) - When user-facing features complete

**Future (Strategic):**
6. TASK-0040 (Trading Intelligence) - After Tier 1-2 complete

---

## 📝 Usage Notes

**Auto-discovery:**
- Run `/do_it` without arguments to automatically continue active work or start next planned task
- Run `/do_it <file>` to override and work on specific task list

**Context Management:**
- Check context: `node ~/portfolio-ai/.claude/skills/context-manager/check.js <current_tokens>`
- Decision helper: `node ~/portfolio-ai/.claude/skills/context-manager/should-continue.js <current_tokens>`
- Target: Use 85-90% of context before pausing

**Adding Tasks:**
- Full PRD: `/plan_it <feature description>` → `/task_it <PRD file>`
- Simple task: `/task_it <simple task description>` (auto-adds to Planned)

**Archiving:**
- Automatic: When "Recently Completed" exceeds 5 items, oldest auto-archives
- Manual: Move entry to `tasks/archive/YYYY-MM.md` and files to `tasks/archive/prds/` or `tasks/archive/task-lists/`

---

## 🔍 Implementation Verification Notes

**Data Sources (verified 2025-11-07):**
- Exploration agents confirmed actual implementation vs. task list claims
- Database schema verified via migrations + live queries
- API responses verified via curl tests
- Frontend components verified via code review
- Test coverage verified via pytest runs

**Key Discoveries:**
- Narrative Intelligence 100% complete (not reflected in old task lists)
- News actionable insights generated but not displayed in UI (1-line fix)
- SEC EDGAR source integrated but fetching 0 articles (needs debug)
- Plain language coverage only 32% vs. expected 90%+ (needs improvement)
- Priority indicators mentioned in multiple tasks but never implemented

**Files Examined:**
- 25 task files in tasks/ folder
- 10+ migration files
- 50+ backend source files
- 20+ frontend component files
- Actual database via psql queries
