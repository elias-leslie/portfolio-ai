# Code Review Agent Instructions

**USER WILL TELL YOU: "You are Cloud Agent X" - Find your section below.**

Branch: claude/code-review-011CV3yYsKEbVuDcMNAiKG56

## Cloud Agent 1: Market Intelligence

**Files YOU own:**
- backend/app/market/ (ALL files)
- backend/app/api/market.py (697 lines)
- frontend/components/market/ (ALL files)
- frontend/lib/hooks/useMarketIntelligence.ts

**Tasks:**
- P0: Optimize market.py (697 lines) - reduce query count
- P1: Remove duplicate sector mapping logic
- P1: Clean unused imports across module
- P2: Add type hints for mypy --strict compliance

**DO NOT TOUCH:** watchlist/*, portfolio/*, services/*, tasks/*, utils/*

---

## Cloud Agent 2: Watchlist

**Files YOU own:**
- backend/app/watchlist/ (ALL files)
- backend/app/api/watchlist.py (517 lines)
- frontend/components/watchlist/ (ALL files)
- frontend/components/settings/WatchlistPreferences.tsx (889 lines)
- frontend/components/settings/sections/WatchlistSettingsSection.tsx (479 lines)

**Tasks:**
- P0: Split refresh_processor.py (1030 lines → 3 files: fetch, process, save)
- P0: Split ExpandedRow.tsx (1142 lines → extract news, fundamentals, technicals)
- P1: Optimize watchlist_service.py (778 lines) - reduce N+1 queries
- P1: Simplify scoring_service.py (648 lines)
- P2: Remove duplicate scoring logic
- P2: Clean dead code

**DO NOT TOUCH:** market/*, portfolio/*, services/*, tasks/*, utils/*

---

## Cloud Agent 3: Portfolio & Analytics

**Files YOU own:**
- backend/app/portfolio/ (ALL files)
- backend/app/analytics/ (ALL files)
- backend/app/api/portfolio.py
- backend/app/api/analytics.py
- backend/app/api/ideas.py (474 lines)
- frontend/components/portfolio/ (ALL files)

**Tasks:**
- P0: Remove SELECT * in manager.py - use explicit columns
- P1: Optimize paper_trading.py (536 lines) - reduce computational overhead
- P1: Optimize peers.py (508 lines)
- P1: Clean analytics.py (503 lines)
- P2: Clean dead code and unused functions
- P2: Add type hints for mypy --strict compliance

**DO NOT TOUCH:** market/*, watchlist/*, services/*, tasks/*, utils/*

---

## Cloud Agent 4: News & Services

**Files YOU own:**
- backend/app/services/ (ALL files)
- backend/app/sources/ (ALL files)
- backend/app/ml/ (ALL files)
- backend/app/api/news.py (608 lines)
- frontend/components/shared/UnifiedNewsIntelligence*.tsx (495 lines)

**Tasks:**
- P0: Refactor news_service.py (841 lines → split into: fetch, transform, store)
- P1: Consolidate source fetchers in multi_source_fetcher.py (577 lines)
- P1: Optimize news_vendor_manager.py (565 lines)
- P1: Clean news_quality_metrics.py (532 lines)
- P2: Address TODOs in news_service.py
- P2: Remove duplicate news formatting logic

**DO NOT TOUCH:** market/*, watchlist/*, portfolio/*, tasks/*, utils/*

---

## Cloud Agent 5: Tasks & Infrastructure

**Files YOU own:**
- backend/app/tasks/ (ALL files)
- backend/app/utils/ (ALL files)
- backend/app/storage/ (ALL files)
- backend/app/api/health.py (615 lines)
- backend/app/api/status.py (966 lines)
- backend/app/api/maintenance.py (495 lines)
- backend/app/api/celery_endpoints.py
- backend/app/celery_app.py
- frontend/components/status/ (ALL files)

**Tasks:**
- P0: Split status.py (966 lines → metrics, health, scheduler modules)
- P1: Optimize health_checks.py (621 lines) - reduce redundant checks
- P1: Optimize indicator_tasks.py - Fear & Greed calc (4 queries → 1)
- P1: Clean maintenance.py (495 lines)
- P2: Consolidate logging patterns across tasks
- P2: Clean dead code in utils

**DO NOT TOUCH:** market/*, watchlist/*, portfolio/*, services/*

---

## Instructions (ALL AGENTS)

### Setup
```bash
cd /home/user/portfolio-ai
git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56
git pull origin claude/code-review-011CV3yYsKEbVuDcMNAiKG56
```

### Process
1. **TodoWrite**: Create task list from your P0/P1/P2 tasks above
2. **Read YOUR files only**: Use Read tool on files you own
3. **Fix issues in order**: P0 (critical) → P1 (important) → P2 (nice-to-have)
4. **Test after each fix**:
   ```bash
   bash ~/portfolio-ai/scripts/lint.sh
   cd ~/portfolio-ai/backend && pytest tests/ -v
   ```
5. **Commit frequently**:
   ```bash
   git add <files>
   git commit -m "chore(cloud-X): <summary>"
   ```
6. **Push when done**:
   ```bash
   git push origin claude/code-review-011CV3yYsKEbVuDcMNAiKG56
   ```
7. **Generate report**: Use template below

### Rules
✅ **Edit ONLY your files** - Zero overlap ensures zero conflicts
✅ **Test before commit** - All lint and tests must pass
✅ **Small commits** - One logical change per commit
✅ **Follow patterns** - Match existing code style
❌ **NEVER touch other agents' files** - This prevents merge conflicts
❌ **NEVER skip testing** - Broken code blocks other agents
❌ **NEVER use `--no-verify`** - Pre-commit hooks must pass

### Priority Definitions
- **P0 (Critical)**: Files >800 lines, N+1 queries, SELECT *, performance issues
- **P1 (Important)**: Files 500-800 lines, duplicate code, missing types
- **P2 (Nice-to-have)**: Dead code, TODOs, unused imports, documentation

### Report Template
```markdown
# Cloud Agent X: [Module Name]

## Summary
[2-3 sentences describing what you accomplished]

## Files Modified
- `path/to/file.py` - [description of changes]
- `path/to/other.tsx` - [description of changes]

## Issues Fixed

### P0: Critical
1. **Issue**: [description]
   - **Location**: `file.py:123`
   - **Fix**: [what you did]
   - **Impact**: [measurable improvement]

### P1: Important
1. **Issue**: [description]
   - **Location**: `file.py:456`
   - **Fix**: [what you did]
   - **Impact**: [improvement]

### P2: Nice-to-have
1. **Issue**: [description]
   - **Location**: `file.py:789`
   - **Fix**: [what you did]

## Metrics
- **Files Modified**: X
- **Lines Added**: +X
- **Lines Removed**: -X
- **Net Change**: -X lines (Y% reduction)
- **Time Spent**: X hours

## Testing
- ✅ Linting: `bash ~/portfolio-ai/scripts/lint.sh` passed
- ✅ Tests: All X tests passed
- ✅ Manual: [brief description of manual testing]

## Notes
[Any issues, blockers, or recommendations for other agents]
```

---

## Example Workflow

### Agent 1 starts:
```bash
cd /home/user/portfolio-ai
git checkout claude/code-review-011CV3yYsKEbVuDcMNAiKG56
git pull
```

Read files:
- backend/app/market/
- backend/app/api/market.py
- frontend/components/market/

Fix issues → Test → Commit → Push → Report

### All 5 agents can work in parallel with ZERO conflicts because:
- Each agent owns different files
- No file overlap between agents
- Each pushes to same branch (git handles auto-merge)

---

## BEGIN WORK

When user says: **"You are Cloud Agent X"**
1. Find your section above (1-5)
2. Use TodoWrite to create task list
3. Follow the Process steps
4. Generate report when done
5. Push to branch

**Good luck!** 🚀
