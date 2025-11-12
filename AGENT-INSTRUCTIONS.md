# Code Review Agent Instructions

**IMPORTANT: USER WILL TELL YOU "You are Cloud Agent X" - Find your section below.**

**Git Strategy:** Each agent works on their own session-specific branch (git requires branches end with session ID). The Verification Agent will merge all 5 branches.

**Setup Branch:** `claude/setup-prompt-execution-011CV4G6BAFpWhEUx1Ff9XfJ`

---

## ⚠️ CRITICAL: Cloud Agent Constraints

**YOU (All Worker Agents 1-5) are Cloud Agents with LIMITED capabilities:**

### ✅ Cloud Agents CAN:
- Read files (Read, Glob, Grep tools)
- Edit files (Edit, Write tools)
- Static analysis (code review, pattern detection)
- Git operations (checkout, commit, push, pull, log, diff, status)
- Create documentation and reports

### ❌ Cloud Agents CANNOT:
- **Run tests** (`pytest`, `npm test`, etc.) - No test execution
- **Start/restart services** - No service management
- **Run database migrations** - No database access
- **Execute application code** (`python`, `node`, etc.) - No runtime execution
- **Check service status** (except via git) - No system inspection
- **Access .venv/** - Virtual environment not available
- **Run linters/formatters** (`ruff`, `mypy`, `eslint`) - Tools not installed

### 🎯 Cloud Agent Workflow:
1. **Read** code to understand issues
2. **Edit** code to fix issues (based on static analysis)
3. **Commit** changes with clear messages
4. **Trust** that fixes are correct (no local verification possible)
5. **Report** what you did for Verification Agent

### 🖥️ Local Verification Agent:
- **ONLY the Verification Agent** can run tests, restart services, and verify changes
- Verification Agent runs on local dev machine with full capabilities
- All 5 worker agents submit code blindly, verification agent validates

**IMPORTANT:** Do NOT attempt to run tests or services. Focus on code quality through reading and editing only.

---

## Cloud Agent 1: Market Intelligence

**Module:** Market data, intelligence, and health indicators

### Files YOU Own:

**Backend (1 file):**
- `backend/app/api/market.py` (697 lines - **P1**)

**Frontend:**
- `frontend/components/market/*` (all files in this directory)
- `frontend/app/market/*` (all files in this directory)

### Tasks:

#### P0: Critical (Must Fix)
- None! This is the cleanest module ✨

#### P1: Important (Optimize)
1. **File: backend/app/api/market.py (697L)**
   - **Issue**: Approaching 800-line hard limit (87% of limit)
   - **Action**: Refactor into smaller focused modules:
     - Extract market intelligence logic to `backend/app/market/intelligence.py`
     - Extract Fear & Greed calculation to `backend/app/market/sentiment.py`
     - Keep only API endpoints in `market.py`
   - **Target**: Reduce to <400 lines per file

#### P2: Nice-to-have (Cleanup)
1. **Check for N+1 queries** in market data fetching
2. **Remove duplicate code** across market components
3. **Add type hints** to any untyped functions
4. **Clean up unused imports**

### DO NOT TOUCH:
- watchlist/* (Agent 2)
- portfolio/* (Agent 3)
- services/* (Agent 4)
- tasks/*, utils/*, storage/* (Agent 5)

### Estimated Complexity: **LOW** (20% - smallest module)

---

## Cloud Agent 2: Watchlist

**Module:** Watchlist management, refresh, scoring, and fundamentals

### Files YOU Own:

**Backend (5 files):**
- `backend/app/watchlist/*` (all files - **4 files over 500L!**)
  - `refresh_processor.py` (1,030 lines - **P0 CRITICAL**)
  - `watchlist_service.py` (778 lines - **P1**)
  - `scoring_service.py` (648 lines - **P1**)
  - `fundamentals.py` (531 lines - **P1**)
- `backend/app/api/watchlist.py` (517 lines - **P1**)

**Frontend (8 files):**
- `frontend/components/watchlist/*` (all files)
  - `ExpandedRow.tsx` (1,142 lines - **P0 CRITICAL**)
  - `WatchlistTable.tsx` (633 lines - **P1**)
  - `AddTickerModal.tsx` (282 lines)
- `frontend/components/settings/WatchlistPreferences.tsx` (889 lines - **P0 CRITICAL**)
- `frontend/components/settings/sections/WatchlistSettingsSection.tsx` (479 lines)
- `frontend/lib/api/watchlist.ts` (268 lines)
- `frontend/lib/hooks/useWatchlist.ts` (266 lines)
- `frontend/app/watchlist/*` (all files)

### Tasks:

#### P0: Critical (Must Fix - 3 files >800L)

1. **File: backend/app/watchlist/refresh_processor.py (1,030L)**
   - **Issue**: 29% over hard limit, complex refresh logic
   - **Action**: Split into focused modules:
     - `refresh_processor.py` - Main orchestration (<300L)
     - `refresh_validators.py` - Input validation, error handling
     - `refresh_executor.py` - Actual refresh execution
     - `refresh_scheduler.py` - Scheduling and throttling logic
   - **Impact**: Reduce from 1,030L → ~250L per file

2. **File: frontend/components/watchlist/ExpandedRow.tsx (1,142L)**
   - **Issue**: 43% over hard limit, massive component
   - **Action**: Split into smaller components:
     - `ExpandedRow.tsx` - Main container (<200L)
     - `ExpandedRowHeader.tsx` - Ticker info, quick actions
     - `ExpandedRowStats.tsx` - Price, fundamentals, stats grid
     - `ExpandedRowNews.tsx` - News/intelligence section
     - `ExpandedRowCharts.tsx` - Chart visualization
   - **Impact**: Reduce from 1,142L → ~200L per component

3. **File: frontend/components/settings/WatchlistPreferences.tsx (889L)**
   - **Issue**: 11% over hard limit, complex settings
   - **Action**: Split into logical sections:
     - `WatchlistPreferences.tsx` - Main layout (<200L)
     - `WatchlistDisplaySettings.tsx` - Display preferences
     - `WatchlistRefreshSettings.tsx` - Refresh/update settings
     - `WatchlistScoringSettings.tsx` - Scoring configuration
     - `WatchlistNotificationSettings.tsx` - Alerts/notifications
   - **Impact**: Reduce from 889L → ~180L per component

#### P1: Important (Optimize - 4 files 500-800L)

1. **File: backend/app/watchlist/watchlist_service.py (778L)**
   - **Action**: Extract CRUD operations to `watchlist_repository.py`
   - **Target**: Reduce to <400L

2. **File: backend/app/watchlist/scoring_service.py (648L)**
   - **Action**: Extract scoring algorithms to separate files by type
   - **Target**: Reduce to <400L

3. **File: backend/app/watchlist/fundamentals.py (531L)**
   - **Action**: Split data fetching vs. calculation logic
   - **Target**: Reduce to <350L

4. **File: frontend/components/watchlist/WatchlistTable.tsx (633L)**
   - **Action**: Extract table columns, filters, sort logic to separate files
   - **Target**: Reduce to <400L

5. **File: backend/app/api/watchlist.py (517L)**
   - **Action**: Move business logic to service layer, keep only endpoints
   - **Target**: Reduce to <300L

#### P2: Nice-to-have (Cleanup)
1. **Check for N+1 queries** in watchlist data fetching
2. **Remove duplicate code** between scoring and fundamentals
3. **Optimize database queries** (use SELECT specific columns, not *)
4. **Add proper error handling** for API failures
5. **Clean up unused imports** across all files

### DO NOT TOUCH:
- market/* (Agent 1)
- portfolio/* (Agent 3)
- services/* (Agent 4)
- tasks/*, utils/*, storage/* (Agent 5)

### Estimated Complexity: **HIGH** (35% - largest module, 3 critical files)

---

## Cloud Agent 3: Portfolio & Analytics

**Module:** Portfolio management, analytics, paper trading, investment ideas

### Files YOU Own:

**Backend (6 files):**
- `backend/app/portfolio/*` (all files)
  - `analytics.py` (503 lines - **P1**)
- `backend/app/analytics/*` (all files)
  - `paper_trading.py` (536 lines - **P1**)
  - `peers.py` (508 lines - **P1**)
- `backend/app/api/portfolio.py` (453 lines)
- `backend/app/api/analytics.py`
- `backend/app/api/ideas.py` (474 lines)

**Frontend:**
- `frontend/components/portfolio/*` (all files)
  - `AccountsWithPositions.tsx` (458 lines)
  - `PositionTable.tsx` (400 lines)
  - `MarketConditions.tsx` (299 lines)
  - `PortfolioOverview.tsx` (212 lines)
- `frontend/app/portfolio/*` (all files)
  - `page.tsx` (305 lines)
- `frontend/app/ideas/*` (all files)
  - `[id]/page.tsx` (345 lines)

### Tasks:

#### P0: Critical (Must Fix)
- None! No files over 800L ✨

#### P1: Important (Optimize - 3 files 500-600L)

1. **File: backend/app/analytics/paper_trading.py (536L)**
   - **Action**: Split paper trading logic:
     - `paper_trading.py` - Main trading engine (<300L)
     - `paper_trading_orders.py` - Order management
     - `paper_trading_portfolio.py` - Portfolio calculations
   - **Target**: Reduce to <300L per file

2. **File: backend/app/analytics/peers.py (508L)**
   - **Action**: Extract peer comparison algorithms to separate functions
   - **Target**: Reduce to <350L

3. **File: backend/app/portfolio/analytics.py (503L)**
   - **Action**: Split analytics calculations by type (returns, risk, attribution)
   - **Target**: Reduce to <350L

#### P2: Nice-to-have (Cleanup)
1. **Check for N+1 queries** in portfolio/position fetching
2. **Optimize peer comparison** queries (use batch fetching)
3. **Add type hints** to analytics calculations
4. **Remove duplicate code** between portfolio and analytics modules
5. **Clean up unused imports**

### DO NOT TOUCH:
- market/* (Agent 1)
- watchlist/* (Agent 2)
- services/* (Agent 4)
- tasks/*, utils/*, storage/* (Agent 5)

### Estimated Complexity: **MEDIUM** (25% - moderate size, no critical files)

---

## Cloud Agent 4: News & Services

**Module:** News services, sources, ML models, and agent tools

### Files YOU Own:

**Backend (10+ files):**
- `backend/app/services/*` (all files - **3 large files!**)
  - `news_service.py` (841 lines - **P0 CRITICAL**)
  - `news_vendor_manager.py` (565 lines - **P1**)
  - `news_quality_metrics.py` (532 lines - **P1**)
- `backend/app/sources/*` (all files)
  - `multi_source_fetcher.py` (577 lines - **P1**)
  - `finnhub_source.py` (463 lines)
  - `fmp_source.py` (455 lines)
- `backend/app/ml/*` (all files)
- `backend/app/agents/*` (all files)
  - `tools.py` (454 lines)
- `backend/app/api/news.py` (608 lines - **P1**)

**Frontend:**
- `frontend/components/shared/UnifiedNewsIntelligenceCard.tsx` (495 lines)

### Tasks:

#### P0: Critical (Must Fix - 1 file >800L)

1. **File: backend/app/services/news_service.py (841L)**
   - **Issue**: 5% over hard limit, complex news aggregation
   - **Action**: Split news service into focused modules:
     - `news_service.py` - Main orchestration (<300L)
     - `news_fetcher.py` - Fetching from sources
     - `news_processor.py` - Processing, deduplication, enrichment
     - `news_storage.py` - Database operations
     - `news_cache.py` - Caching logic
   - **Impact**: Reduce from 841L → ~200L per file

#### P1: Important (Optimize - 4 files 500-800L)

1. **File: backend/app/api/news.py (608L)**
   - **Action**: Move business logic to service layer
   - **Target**: Reduce to <300L

2. **File: backend/app/sources/multi_source_fetcher.py (577L)**
   - **Action**: Extract source-specific logic to separate files
   - **Target**: Reduce to <350L

3. **File: backend/app/services/news_vendor_manager.py (565L)**
   - **Action**: Split vendor management into vendor registry + vendor health
   - **Target**: Reduce to <350L per file

4. **File: backend/app/services/news_quality_metrics.py (532L)**
   - **Action**: Extract metric calculations to individual metric files
   - **Target**: Reduce to <300L

#### P2: Nice-to-have (Cleanup)
1. **Check for N+1 queries** in news fetching loops
2. **Optimize SELECT \*** queries - select only needed columns
3. **Remove duplicate code** between news sources
4. **Add proper error handling** for source failures
5. **Clean up unused imports** and dead code

### DO NOT TOUCH:
- market/* (Agent 1)
- watchlist/* (Agent 2)
- portfolio/* (Agent 3)
- tasks/*, utils/*, storage/* (Agent 5)

### Estimated Complexity: **MEDIUM-HIGH** (30% - 1 critical file, several large files)

---

## Cloud Agent 5: Tasks & Infrastructure

**Module:** Celery tasks, utilities, health checks, status monitoring, maintenance

### Files YOU Own:

**Backend (10+ files):**
- `backend/app/tasks/*` (all files)
  - `indicator_tasks.py` (451 lines)
- `backend/app/utils/*` (all files)
  - `health_checks.py` (621 lines - **P1**)
- `backend/app/storage/*` (all files)
- `backend/app/api/health.py` (615 lines - **P1**)
- `backend/app/api/status.py` (1,127 lines - **P0 CRITICAL**)
- `backend/app/api/maintenance.py` (495 lines)
- `backend/app/celery_app.py`

**Frontend:**
- `frontend/components/status/*` (all files)
  - `MaintenanceCard.tsx` (432 lines)
  - `LogsCard.tsx` (425 lines)
  - `MLModelCard.tsx` (373 lines)
  - `TableFreshnessCard.tsx` (287 lines)
  - `CeleryTaskTable.tsx` (284 lines)
- `frontend/app/status/*` (all files)
  - `page.tsx` (614 lines - **P1**)
- `frontend/components/settings/ProfileSelector.tsx` (450 lines)
- `frontend/app/settings/*` (all files)
  - `page.tsx` (508 lines - **P1**)

### Tasks:

#### P0: Critical (Must Fix - 1 file >800L)

1. **File: backend/app/api/status.py (1,127L)**
   - **Issue**: 41% over hard limit, massive status endpoint
   - **Action**: Split status API into focused modules:
     - `status.py` - Main status endpoint (<200L)
     - `status_system.py` - System health (services, DB, Redis)
     - `status_tasks.py` - Celery task status
     - `status_data.py` - Data freshness, table status
     - `status_ml.py` - ML model status
     - `status_cache.py` - Cache statistics
   - **Impact**: Reduce from 1,127L → ~190L per file

#### P1: Important (Optimize - 4 files 500-800L)

1. **File: backend/app/utils/health_checks.py (621L)**
   - **Action**: Split health checks by system:
     - `health_checks.py` - Main health check orchestration (<200L)
     - `health_database.py` - Database health checks
     - `health_services.py` - Service health checks
     - `health_storage.py` - Storage/cache health checks
   - **Target**: Reduce to <200L per file

2. **File: backend/app/api/health.py (615L)**
   - **Action**: Move health check logic to utils, keep only endpoint
   - **Target**: Reduce to <250L

3. **File: frontend/app/status/page.tsx (614L)**
   - **Action**: Extract status sections to separate components
   - **Target**: Reduce to <350L

4. **File: frontend/app/settings/page.tsx (508L)**
   - **Action**: Extract settings sections to separate components
   - **Target**: Reduce to <350L

#### P2: Nice-to-have (Cleanup)
1. **Optimize status queries** (batch fetch instead of individual queries)
2. **Check for N+1 queries** in task status fetching
3. **Remove duplicate code** between health and status endpoints
4. **Add proper caching** for expensive status calculations
5. **Clean up unused imports** and dead code

### DO NOT TOUCH:
- market/* (Agent 1)
- watchlist/* (Agent 2)
- portfolio/* (Agent 3)
- services/*, sources/*, ml/*, agents/* (Agent 4)

### Estimated Complexity: **HIGH** (30% - 1 critical file, complex infrastructure)

---

## Instructions (ALL AGENTS)

### Setup (Each Agent)

**IMPORTANT:** You will be launching in a new session with your own session ID. Your branch will end with your unique session ID.

```bash
cd /home/user/portfolio-ai

# Fetch the setup branch with instructions
git fetch origin claude/setup-prompt-execution-011CV4G6BAFpWhEUx1Ff9XfJ

# Get the instructions file from setup branch
git checkout origin/claude/setup-prompt-execution-011CV4G6BAFpWhEUx1Ff9XfJ -- AGENT-INSTRUCTIONS.md

# Create your working branch (will auto-include your session ID)
git checkout -b claude/code-review-agent-X-<YOUR_SESSION_ID>

# Your branch name will look like:
# claude/code-review-agent-1-011CV4XXXXXXXXXX
# claude/code-review-agent-2-011CV4YYYYYYYYYY
# etc.
```

### Process (All Agents)

1. **TodoWrite**: Create task list from P0/P1/P2 for YOUR agent
2. **Read YOUR files only**: Don't touch other agents' files (causes merge conflicts)
3. **Fix in order**: P0 → P1 → P2
4. **Review your changes**: Use static analysis (read the code, check logic)
5. **Commit frequently**: One logical change per commit
   ```bash
   git add <files>
   git commit -m "chore(agent-X): brief description"
   ```
6. **Push when done**:
   ```bash
   git push -u origin HEAD
   ```
7. **Generate report** using template below

### Rules (Cloud Agent Constraints)

✅ **DO:**
- Edit ONLY your assigned files
- Review changes carefully (no testing available)
- Small, focused commits (one logical change)
- Trust your static analysis
- Read code thoroughly before editing
- Use proper type hints
- Follow existing patterns in codebase

❌ **DON'T:**
- Touch other agents' files (causes merge conflicts)
- Attempt to run tests (you can't - Cloud Agent)
- Attempt to restart services (you can't - Cloud Agent)
- Use runtime verification (Verification Agent will test)
- Skip P0 issues (critical priority)
- Create files larger than 500 lines
- Use `Any` type annotations without justification
- Copy/paste code (extract to shared utilities instead)

### Priority Levels

- **P0 (Critical)**: Files >800 lines - MUST split (hard requirement)
- **P1 (Important)**: Files 500-800 lines - Should optimize (reduce complexity)
- **P2 (Nice-to-have)**: Dead code, TODOs, unused imports, minor issues

### Code Quality Checklist

Before committing, verify (static analysis only):

- ✅ **Files <500 lines** (hard limit: 800, critical: 1000)
- ✅ **Functions <50 lines** (warning: 75, critical: 100)
- ✅ **Type hints on all functions** (avoid `Any`)
- ✅ **No exposed secrets** (use environment variables)
- ✅ **No SQL injection** (use parameterized queries)
- ✅ **No N+1 queries** (use batch fetching)
- ✅ **No SELECT \*** (select specific columns)
- ✅ **Proper error handling** (don't swallow exceptions)
- ✅ **Consistent patterns** (follow existing codebase style)

### Report Template

When done, create a report:

```markdown
# Agent X: [Module Name]

## Summary
[2-3 sentences describing what you accomplished]

## Branch
- **Branch name**: `claude/code-review-agent-X-<YOUR_SESSION_ID>`
- **Base**: `main`
- **Files modified**: X files
- **Commits**: X commits

## Files Modified

### P0: Critical Fixes
- `file.py` (1,200L → 250L avg) - Split into 5 focused modules
  - `file.py` - Main orchestration (250L)
  - `file_logic_a.py` - Feature A logic (200L)
  - `file_logic_b.py` - Feature B logic (230L)
  - etc.

### P1: Important Optimizations
- `other_file.py` (650L → 380L) - Extracted repository layer

### P2: Cleanup
- Removed unused imports from 12 files
- Fixed 3 N+1 queries
- Added type hints to 15 functions

## Issues Fixed

### P0: Critical (Files >800L)
1. **Issue**: backend/app/api/status.py was 1,127 lines (41% over limit)
   - **Root cause**: All status logic in single file
   - **Fix**: Split into 6 focused modules (see above)
   - **Impact**: 1,127L → 190L avg per file (83% reduction)
   - **Verification needed**: Status endpoint functionality

### P1: Important (Files 500-800L)
[Same format as P0]

### P2: Nice-to-have (Cleanup)
[Bulleted list of minor fixes]

## Metrics
- **Files modified**: X
- **Files created**: X (from splits)
- **Files deleted**: 0
- **Lines added**: +X
- **Lines removed**: -X
- **Net change**: -X lines (Y% reduction)
- **Commits**: X
- **Largest file after changes**: XL (down from YL)

## Testing (Cloud Agent - Static Analysis Only)

### Static Analysis Performed:
- ✅ Code reviewed for correctness and logic errors
- ✅ Type hints verified (no unsafe `Any` usage)
- ✅ Import statements checked (no circular imports)
- ✅ SQL queries reviewed (parameterized, no injection)
- ✅ Error handling verified (no swallowed exceptions)
- ✅ File sizes confirmed (all <500L target, <800L hard limit)
- ✅ Function complexity checked (<50L preferred)
- ✅ Patterns consistent with existing codebase

### ⏳ Awaiting Verification Agent:
- Runtime testing (pytest)
- Service restart verification
- Integration testing
- Manual smoke testing
- Linting (ruff, mypy)

## Notes for Verification Agent

### Potential Issues:
- [List any concerns, edge cases, or areas needing extra attention]

### Testing Focus:
- [Specific features/endpoints to test based on changes]

### Rollback Plan:
- If tests fail, revert commit: `git revert <commit-hash>`
- Alternatively, cherry-pick successful changes from this branch

## Recommendations

### For Future Work:
- [Suggestions for follow-up refactoring]
- [Technical debt items discovered but not addressed]

### For Other Agents:
- [Shared utilities created that other agents might use]
- [Patterns established that other agents should follow]
```

---

## Example: Agent Launch Flow

**User launches Agent 2 (Watchlist):**

```
You are Cloud Agent 2 (Watchlist module).

cd /home/user/portfolio-ai
git fetch origin claude/setup-prompt-execution-011CV4G6BAFpWhEUx1Ff9XfJ
git checkout origin/claude/setup-prompt-execution-011CV4G6BAFpWhEUx1Ff9XfJ -- AGENT-INSTRUCTIONS.md

Read /home/user/portfolio-ai/AGENT-INSTRUCTIONS.md and execute.
```

**Agent 2's process:**
1. Creates branch: `claude/code-review-agent-2-<AGENT2_SESSION_ID>`
2. Reads "Cloud Agent 2: Watchlist" section
3. Creates TodoWrite with P0/P1/P2 tasks
4. Fixes 3 critical files >800L (refresh_processor.py, ExpandedRow.tsx, WatchlistPreferences.tsx)
5. Optimizes 5 files 500-800L
6. Commits frequently, pushes to their branch
7. Generates report
8. Done!

**Important:** Agent 2 never touches market/*, portfolio/*, services/*, or tasks/* files.

---

## VERIFICATION & MERGE (Local Agent ONLY)

**⚠️ CRITICAL: This step requires a LOCAL agent with full capabilities (tests, services, database).**

**After all 5 agents complete their work:**

```
You are the Verification Agent running on LOCAL dev machine.

Environment: Local Dev (full capabilities - tests, services, database access)

## Step 1: Collect Agent Branches

All 5 agents worked on their own branches:
- claude/code-review-agent-1-<SESSION_ID_1>
- claude/code-review-agent-2-<SESSION_ID_2>
- claude/code-review-agent-3-<SESSION_ID_3>
- claude/code-review-agent-4-<SESSION_ID_4>
- claude/code-review-agent-5-<SESSION_ID_5>

## Step 2: Create Integration Branch

cd /home/user/portfolio-ai
git checkout main
git pull origin main

# Create integration branch for merging all agent work
git checkout -b claude/code-review-integration-$(date +%Y%m%d-%H%M%S)

## Step 3: Merge Agent Branches (One at a Time)

# Merge Agent 1 (Market - smallest, least conflicts)
git fetch origin claude/code-review-agent-1-<SESSION_ID_1>
git merge origin/claude/code-review-agent-1-<SESSION_ID_1> --no-ff -m "merge: Agent 1 (Market Intelligence)"

# Merge Agent 2 (Watchlist - largest, most critical)
git fetch origin claude/code-review-agent-2-<SESSION_ID_2>
git merge origin/claude/code-review-agent-2-<SESSION_ID_2> --no-ff -m "merge: Agent 2 (Watchlist)"

# Merge Agent 3 (Portfolio)
git fetch origin claude/code-review-agent-3-<SESSION_ID_3>
git merge origin/claude/code-review-agent-3-<SESSION_ID_3> --no-ff -m "merge: Agent 3 (Portfolio & Analytics)"

# Merge Agent 4 (News & Services)
git fetch origin claude/code-review-agent-4-<SESSION_ID_4>
git merge origin/claude/code-review-agent-4-<SESSION_ID_4> --no-ff -m "merge: Agent 4 (News & Services)"

# Merge Agent 5 (Infrastructure)
git fetch origin claude/code-review-agent-5-<SESSION_ID_5>
git merge origin/claude/code-review-agent-5-<SESSION_ID_5> --no-ff -m "merge: Agent 5 (Tasks & Infrastructure)"

# If merge conflicts (unlikely with zero file overlap):
# 1. Review conflict
# 2. Resolve manually
# 3. git add <resolved-files>
# 4. git commit

## Step 4: Review Integrated Changes

# Check all changes
git log --oneline -50
git diff main...HEAD --stat
git diff main...HEAD --name-only | wc -l

# Verify no file overlap conflicts
# Review critical file changes
git diff main...HEAD -- backend/app/api/status.py
git diff main...HEAD -- backend/app/watchlist/refresh_processor.py
git diff main...HEAD -- frontend/components/watchlist/ExpandedRow.tsx

## Step 5: Test Everything (LOCAL CAPABILITIES)

# Linting and type checking
bash ~/portfolio-ai/scripts/lint.sh

# If lint fails:
# - Review errors
# - Fix locally or ask specific agent to fix
# - Commit fixes to integration branch

# Run all tests
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/ -v

# If tests fail:
# - Identify which module failed
# - Review corresponding agent's changes
# - Fix locally or request agent revision
# - Document in final report

## Step 6: Verify Services (LOCAL CAPABILITIES)

# Restart all services
bash ~/portfolio-ai/scripts/restart.sh

# Wait for services to stabilize
sleep 15

# Check service status
bash ~/portfolio-ai/scripts/status.sh

# Verify services started AFTER our changes
systemctl show portfolio-backend -p ActiveEnterTimestamp
systemctl show portfolio-celery -p ActiveEnterTimestamp
systemctl show portfolio-frontend -p ActiveEnterTimestamp

## Step 7: Manual Smoke Test

# Open application
# URL: http://192.168.8.233:3000

# Test each module (corresponds to agents):
1. Market Intelligence page - Check market data, Fear & Greed
2. Watchlist page - Expand rows, check scoring, test refresh
3. Portfolio page - Check positions, analytics, paper trading
4. News/Intelligence - Check news loading, quality metrics
5. Status page - Check all status cards, health checks

# Monitor logs during testing
tail -f /var/log/portfolio-ai/backend-error.log
tail -f /var/log/portfolio-ai/celery-worker.log

# Check for errors in console (Frontend)
# Open browser DevTools → Console

## Step 8: Merge to Main (If All Pass)

cd /home/user/portfolio-ai
git checkout main
git merge claude/code-review-integration-<TIMESTAMP> --no-ff -m "feat: distributed code review - 5 agents"
git push origin main

## Step 9: Generate Final Report

```markdown
# Distributed Code Review - Final Report

## Overview
- **Date**: YYYY-MM-DD
- **Agents**: 5 Cloud Agents + 1 Local Verification Agent
- **Integration Branch**: claude/code-review-integration-<TIMESTAMP>
- **Status**: ✅ Merged to main / ⚠️ Issues found / ❌ Failed

## Agent Branches Merged
1. claude/code-review-agent-1-<ID> (Market Intelligence)
2. claude/code-review-agent-2-<ID> (Watchlist)
3. claude/code-review-agent-3-<ID> (Portfolio)
4. claude/code-review-agent-4-<ID> (News & Services)
5. claude/code-review-agent-5-<ID> (Infrastructure)

## Summary Statistics

### Files Changed
- **Total files modified**: X
- **Files created**: Y (from splits)
- **Files deleted**: Z
- **Net lines changed**: -XXX lines (Y% reduction)

### Critical Issues Fixed (P0)
- backend/app/api/status.py: 1,127L → 190L avg (6 files)
- backend/app/watchlist/refresh_processor.py: 1,030L → 250L avg (4 files)
- backend/app/services/news_service.py: 841L → 200L avg (5 files)
- frontend/components/watchlist/ExpandedRow.tsx: 1,142L → 200L avg (5 files)
- frontend/components/settings/WatchlistPreferences.tsx: 889L → 180L avg (5 files)

**Total**: 5 critical files fixed, 25 new focused modules created

### Important Optimizations (P1)
- X files reduced from 500-800L to <400L
- Y N+1 queries eliminated
- Z functions optimized

### Cleanup (P2)
- Removed unused imports from X files
- Added type hints to Y functions
- Fixed Z minor issues

## Test Results

### Linting (bash ~/portfolio-ai/scripts/lint.sh)
- ✅ Ruff: Pass
- ✅ Mypy: Pass
- ❌ Issues found: [describe]

### Backend Tests (pytest)
- ✅ Total: 508 tests
- ✅ Passed: 508
- ❌ Failed: 0
- ⚠️ Warnings: [describe]

### Service Verification
- ✅ Backend: Running (started HH:MM:SS)
- ✅ Celery Worker: Running (started HH:MM:SS)
- ✅ Celery Beat: Running (started HH:MM:SS)
- ✅ Frontend: Running (started HH:MM:SS)

### Manual Smoke Test
- ✅ Market Intelligence: [Pass/Issues]
- ✅ Watchlist: [Pass/Issues]
- ✅ Portfolio: [Pass/Issues]
- ✅ News: [Pass/Issues]
- ✅ Status: [Pass/Issues]

## Issues Found

### Critical (Blocking)
- [None] / [List issues that prevent merge]

### Important (Fix soon)
- [List issues found during testing]

### Minor (Tech debt)
- [List minor issues for future work]

## Merge Conflicts
- ✅ None (zero file overlap worked!)
- ⚠️ [List conflicts and how resolved]

## Recommendations

### Immediate Actions
- [Required fixes before production]

### Follow-up Work
- [Technical debt items]
- [Further optimizations]

### Process Improvements
- [What worked well]
- [What could be improved for next code review]

## Conclusion

[Overall assessment of code review success]

**Time saved**: ~X hours (parallel vs sequential)
**Code quality improvement**: [measurable metrics]
**Ready for production**: Yes/No/Partial
```

## Step 10: Cleanup (Optional)

# Delete agent branches (keep integration branch for reference)
git branch -d claude/code-review-agent-1-<SESSION_ID_1>
# ... repeat for agents 2-5

# Or keep branches for a few days in case rollback needed
```

**Note:** Zero file overlap means zero merge conflicts (in theory). But always review diffs carefully.

---

## SUCCESS METRICS

**Goals for this code review:**

1. **Critical Files (P0)**:
   - ✅ All 5 files >800L reduced to <400L per module
   - ✅ 5 files → 25+ focused modules

2. **Important Files (P1)**:
   - ✅ Reduce 14 files from 500-800L to <400L
   - ✅ Extract business logic from API layers

3. **Code Quality (P2)**:
   - ✅ Clean up unused imports
   - ✅ Fix N+1 queries
   - ✅ Add type hints
   - ✅ Remove duplicate code

4. **Test Coverage**:
   - ✅ All 508 tests pass
   - ✅ No regressions introduced

5. **Performance**:
   - ✅ ~4 hours total (parallel) vs ~20 hours (sequential)
   - ✅ 5x speedup from parallelization

---

## READY TO LAUNCH! 🚀

**Next steps:**

1. **Setup Agent** (done!) - Created this instructions file
2. **Launch 5 Cloud Agents** (user action) - Each agent processes their module
3. **Launch Local Verification Agent** (user action) - Tests, merges, validates
4. **Merge to main** (verification agent) - Production ready!

**Estimated timeline:**
- Agent 1 (Market): ~2 hours (smallest module)
- Agent 2 (Watchlist): ~4 hours (largest, 3 critical files)
- Agent 3 (Portfolio): ~3 hours (moderate size)
- Agent 4 (News): ~3.5 hours (1 critical file)
- Agent 5 (Infrastructure): ~3.5 hours (1 critical file)
- Verification: ~2 hours (testing, integration, merge)

**Total: ~18 hours wall time with 5 parallel agents vs ~90+ hours sequential**

**Let's ship it!** 🎉
