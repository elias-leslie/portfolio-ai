# Task List: True Unified News Intelligence (Backend + Frontend)

**Source**: User request - achieve TRUE parity between Market News and ticker-specific News & Sentiment with unified backend service
**Complexity**: COMPLEX
**Effort**: HIGH (8-12 hours)
**Environment**: Local Dev
**Created**: 2025-11-11 18:00
**Status**: Planned

---

## Summary

**Goal**: Create single unified backend service and frontend component with TRUE visual parity between Market News (dashboard) and News & Sentiment (watchlist). Both sections should look identical except for conditional sentiment breakdown.

**Problem with Current Implementation (tasks-0047)**:
- ❌ Frontend uses different article layouts (simple vs detailed)
- ❌ Backend has separate endpoints with different response structures
- ❌ Market news lacks sentiment breakdown
- ❌ Code duplication between services
- ❌ NOT truly unified

**Approach**:
1. **Backend**: Create single `/api/news` endpoint with optional `?ticker=` parameter
2. **Data Structure**: Unified `NewsIntelligenceResponse` with sentiment summary + articles
3. **Frontend**: Single article layout for both sections, conditional sentiment breakdown
4. **Cleanup**: Delete old endpoints, services, and duplicate code

**Scope Discovery**: Required - find all backend services, endpoints, hooks, and callers

---

## Architecture Diagrams

### CURRENT STATE (tasks-0047 - WRONG)

```
Backend:
┌─────────────────────────────────────────────────┐
│ /api/news/market                                │
│ ├─ Returns: { articles: [...] }                │ <- No sentiment summary
│ ├─ Service: market_news_service.py             │
│ └─ Articles: Basic sentiment fields            │
├─────────────────────────────────────────────────┤
│ Watchlist /api/watchlist/:id endpoint           │
│ ├─ Returns: { recent_news: {                   │
│ │     summary: {...},                           │ <- Has sentiment summary
│ │     articles: [...]                           │
│ │   }}                                          │
│ ├─ Service: watchlist_service.py               │
│ └─ Articles: Full sentiment + confidence + model│
└─────────────────────────────────────────────────┘

Frontend:
┌─────────────────────────────────────────────────┐
│ UnifiedNewsIntelligenceCard                     │
│ ├─ if (recentNews): Detailed 2-column layout   │ <- Different layouts
│ ├─ else: Simple inline layout                  │
│ └─ Conditional sentiment breakdown              │
└─────────────────────────────────────────────────┘

Visual Result:
Dashboard Market News       Watchlist News & Sentiment
┌─────────────────────┐    ┌──────────────────────────┐
│ Simple articles     │    │ Sentiment breakdown      │
│ • Headline          │    │ Score: 0.48  Mix: 5/3/2 │
│   Source · POSITIVE │    ├──────────────────────────┤
└─────────────────────┘    │ Detailed articles        │
                           │ ┌────────────┬─────────┐ │
                           │ │ Headline   │POSITIVE │ │
                           │ │ Publisher  │Score 92%│ │
                           │ └────────────┴─────────┘ │
                           └──────────────────────────┘
              ↑ NOT UNIFIED - LOOK DIFFERENT ↑
```

### TARGET STATE (TRUE UNIFICATION)

```
Backend:
┌─────────────────────────────────────────────────┐
│ SINGLE UNIFIED ENDPOINT: /api/news              │
│                                                 │
│ GET /api/news?ticker=AAPL  (ticker-specific)   │
│ GET /api/news              (market-wide)       │
│                                                 │
│ Service: news_intelligence_service.py           │ <- Single service
│                                                 │
│ Unified Response Structure:                     │
│ {                                               │
│   "summary": {                                  │
│     "score": 0.45,                             │
│     "score_change": 0.02,                      │
│     "positive_count": 15,                      │
│     "neutral_count": 20,                       │
│     "negative_count": 10,                      │
│     "article_count": 45,                       │
│     "model_breakdown": {"finbert": 40, ...}    │
│   },                                            │
│   "articles": [                                 │
│     {                                           │
│       "headline": "...",                        │
│       "url": "...",                             │
│       "source": "...",                          │
│       "vendor": "...",                          │
│       "published_at": "...",                    │
│       "sentiment": {                            │
│         "score": 0.92,                          │
│         "label": "positive",                    │
│         "confidence": 0.87,                     │
│         "model": "finbert"                      │
│       },                                        │
│       "plain_language_headline": "...",         │
│       "impact_summary": "...",                  │
│       "actionable_insight": "..."               │
│     }                                            │
│   ]                                             │
│ }                                               │
└─────────────────────────────────────────────────┘

Frontend:
┌─────────────────────────────────────────────────┐
│ UnifiedNewsIntelligenceCard                     │
│                                                 │
│ Single Code Path:                               │
│ ├─ All articles use SAME detailed layout       │ <- Same layout
│ ├─ Sentiment breakdown: conditional on ticker  │
│ └─ No if/else for article rendering             │
└─────────────────────────────────────────────────┘

Visual Result - TRUE PARITY:
Dashboard Market News           Watchlist News & Sentiment
┌──────────────────────────┐   ┌──────────────────────────┐
│ [Recent ▼] [Sort]        │   │ Sentiment breakdown      │
│                          │   │ Score: 0.48  Mix: 5/3/2 │
│ Detailed articles:       │   ├──────────────────────────┤
│ ┌────────────┬─────────┐ │   │ [Recent ▼] [Sort]        │
│ │ Headline   │POSITIVE │ │   │                          │
│ │ YFINANCE   │Score 92%│ │   │ Detailed articles:       │
│ │ Publisher  │Conf 87% │ │   │ ┌────────────┬─────────┐ │
│ │ 2h ago     │FINBERT  │ │   │ │ Headline   │POSITIVE │ │
│ └────────────┴─────────┘ │   │ │ YFINANCE   │Score 92%│ │
│ ┌────────────┬─────────┐ │   │ │ Publisher  │Conf 87% │ │
│ │ Another... │NEGATIVE │ │   │ │ 2h ago     │FINBERT  │ │
│ └────────────┴─────────┘ │   │ └────────────┴─────────┘ │
│                          │   │                          │
│ [Show All (50 total)]    │   │ [Show All (50 total)]    │
└──────────────────────────┘   └──────────────────────────┘
         ↑ IDENTICAL ARTICLE CARDS ↑
  (Only diff: sentiment breakdown at top)
```

---

## Tasks

### 0.0 Scope Discovery (MANDATORY - CLOUD AGENT)

**⚠️ This task should be delegated to a cloud/general-purpose agent for parallel execution**

Cloud agent has access to: Read, Glob, Grep (NO Bash, NO running services/tests)

- [x] 0.1 Backend scope discovery
  - [x] Find all news-related services
    - `Glob: backend/app/services/**/*news*.py`
    - `Grep: "def.*news" backend/app/services/`
    - `Grep: "class.*News" backend/app/services/`
  - [x] Find all news-related endpoints
    - `Grep: "@router.get.*news" backend/app/api/`
    - `Read: backend/app/api/news.py` (if exists)
    - `Read: backend/app/api/watchlist.py` (check for news logic)
  - [x] Document response structures
    - Find Pydantic models: `Grep: "class.*News.*BaseModel" backend/`
    - Read relevant model files
    - Compare market vs ticker news response structures
  - [x] Identify database queries
    - `Grep: "SELECT.*FROM.*news" backend/`
    - Document query patterns
  - [x] Output: Markdown document with:
    - List of all files to modify
    - List of all files to delete
    - Current vs desired data flow diagrams
    - Estimated lines of code affected

- [x] 0.2 Frontend scope discovery
  - [x] Find all news-related hooks
    - `Glob: frontend/lib/hooks/**/*news*.ts`
    - `Grep: "export.*useNews" frontend/lib/hooks/`
    - Read each hook file
  - [x] Find all TypeScript types
    - `Grep: "interface.*News" frontend/lib/`
    - `Grep: "type.*News" frontend/lib/`
    - Document type differences between market/ticker
  - [x] Find all components using news hooks
    - `Grep: "useMarketNews" frontend/`
    - `Grep: "useNews" frontend/`
    - Document component dependencies
  - [x] Output: Markdown document with:
    - Hook dependency graph
    - Type migration plan
    - Component update sequence

- [x] 0.3 Create implementation plan (CLOUD AGENT)
  - [x] Sequence backend changes (which order to modify files)
  - [x] Identify breaking changes and mitigation
  - [x] Create test update checklist
  - [x] Estimate effort per section (1-7 sections)
  - [x] Output: Detailed implementation roadmap

- [ ] 0.4 Checkpoint: Confirm scope before proceeding (LOCAL AGENT)
  - Review cloud agent findings in `tasks/tasks-0048-scope-findings.md` (CORRECTED after deep verification)
  - Confirm:
    - [x] Total backend files: **7 files** to modify (service, API router, watchlist, agents, tasks, tests)
    - [x] Total frontend files: **5 files** to modify (news.ts API, useNews.ts hook, component, callers, tests)
    - [x] Estimated effort: **15.0 hours** (VERY HIGH complexity - 9/10)
    - [x] Architectural concerns: **BREAKING API CHANGES** + **Multiple internal consumers**
  - Key Findings (CORRECTED):
    - **Backend**: 2 methods to consolidate (`get_market_news`, `get_symbol_news`) → 1 method (`get_news_intelligence`)
    - **Backend**: 2 endpoints to delete (`/market`, `/symbol/{symbol}`) → 1 new endpoint (`/api/news?ticker={optional}`)
    - **Backend consumers**: 7 files affected (API + watchlist refresh + AI agents + Celery tasks + tests)
    - **Test impact**: 45+ references across 6+ test files
    - **Frontend**: 2 hooks to delete (`useMarketNews`, `useSymbolNews`) → 1 new hook (`useNewsIntelligence`)
    - **Frontend**: Component layout unification required
  - Critical Consumers Found:
    - `backend/app/watchlist/refresh_processor.py:463` - Uses `get_symbol_news()`
    - `backend/app/agents/tools.py:191-195` - Uses both `get_market_news()` and `get_symbol_news()`
    - `backend/app/tasks/news_tasks.py:123` - Uses `get_market_news()`
  - Target Architecture:
    - Backend: Single `/api/news?ticker={optional}` endpoint calling `get_news_intelligence(ticker: Optional[str])`
    - Frontend: Single `useNewsIntelligence(ticker?)` hook + unified component layout
    - All internal consumers updated to use new unified method
  - Decision: Proceed to Task 1 (Backend Service Consolidation) - this is a MAJOR refactor with 20+ files!

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

**Handoff Protocol:**
1. Cloud agent completes 0.1-0.3 → saves findings to `tasks/tasks-0048-scope-findings.md`
2. Cloud agent marks Task 0.1-0.3 as [x] complete in this file
3. Fresh local agent session can be started
4. New local agent runs `/do_it` → automatically:
   - Reads WORK_TRACKER.md (finds this task)
   - Reads this task file (sees Task 0 marked complete)
   - Reads tasks/tasks-0048-scope-findings.md (gets context)
   - Reviews findings in Task 0.4
   - Proceeds to Task 1 with full scope understanding

**For fresh session to work:**
- Cloud agent MUST mark [ ] → [x] for tasks 0.1-0.3 before completing
- Cloud agent MUST create tasks/tasks-0048-scope-findings.md
- Fresh local agent runs `/do_it` (no arguments needed - auto-discovers work)

---

## CHECKPOINT-BASED IMPLEMENTATION (11 Rollback Points)

**Safety Protocol:**
- Each checkpoint = incremental change + test + commit (rollback point)
- New code added BEFORE old code deleted (no breaking changes until checkpoint 11)
- Critical systems tested independently (watchlist, agents, tasks)
- Backend fully working before touching frontend
- Quality check at end to catch any regressions

---

### ✅ CHECKPOINT 0: Scope Confirmed (COMPLETE)
- [x] 0.4 User confirmed: 15h, 20+ files, proceed with checkpoint-based approach
- [x] Quality baseline established: 19 critical, 77 warnings, 93 medium
- **Rollback**: N/A (starting point)

---

### 🔵 CHECKPOINT 1: Add Unified Backend Method (NO BREAKING CHANGES)

**Goal**: Add new `get_news_intelligence()` method alongside existing methods

- [ ] 1.1 Add unified method to `news_service.py`
  - [ ] Method signature: `get_news_intelligence(ticker: Optional[str] = None, *, max_articles: int, force_refresh: bool) -> NewsBundle`
  - [ ] If ticker is None: use MARKET_TICKER and "stock market" query
  - [ ] If ticker provided: use ticker and "{ticker} stock" query
  - [ ] Call existing `_get_bundle()` method (reuse logic)
  - [ ] KEEP old methods (`get_market_news`, `get_symbol_news`) - DO NOT DELETE

- [ ] 1.2 Write unit tests for new method
  - [ ] Test: `get_news_intelligence(None)` returns market news
  - [ ] Test: `get_news_intelligence("AAPL")` returns ticker news
  - [ ] Test: Results match existing methods
  - [ ] Run: `cd ~/portfolio-ai/backend && pytest tests/unit/services/test_news_service.py -v`

- [ ] 1.3 **TEST**: Verify new method works
  ```bash
  # Should succeed without errors
  cd ~/portfolio-ai/backend && python -c "
  from app.services.news_service import NewsService
  svc = NewsService()
  market = svc.get_news_intelligence(None, max_articles=5, force_refresh=False)
  ticker = svc.get_news_intelligence('AAPL', max_articles=5, force_refresh=False)
  print(f'Market: {len(market.articles)} articles')
  print(f'Ticker: {len(ticker.articles)} articles')
  "
  ```

- [ ] 1.4 **COMMIT**: "feat(news): add unified get_news_intelligence method"
  - **Rollback**: `git reset --hard HEAD~1` if issues found

---

### 🔵 CHECKPOINT 2: Add New API Endpoint (OLD ENDPOINTS STILL ACTIVE)

**Goal**: Add `/api/news` endpoint alongside existing `/market` and `/symbol/{symbol}`

- [ ] 2.1 Add new endpoint to `backend/app/api/news.py`
  - [ ] Route: `@router.get("/news", response_model=NewsIntelligenceResponse)`
  - [ ] Query param: `ticker: Optional[str] = None`
  - [ ] Query param: `limit: int = Query(default=50, ge=1, le=200)`
  - [ ] Call: `news_service.get_news_intelligence(ticker, max_articles=limit)`
  - [ ] KEEP old endpoints (`/market`, `/symbol/{symbol}`) - DO NOT DELETE

- [ ] 2.2 **TEST**: Verify new endpoint works
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  # Test market news
  curl http://localhost:8000/api/news?limit=5 | jq '.summary'
  # Test ticker news
  curl http://localhost:8000/api/news?ticker=AAPL&limit=5 | jq '.summary'
  # Both should return: score, score_change, positive/neutral/negative_count, model_breakdown
  ```

- [ ] 2.3 **COMMIT**: "feat(api): add unified /api/news endpoint"
  - **Rollback**: `git reset --hard HEAD~1` if issues found

---

### 🔵 CHECKPOINT 3: Migrate Watchlist Refresh (CRITICAL SYSTEM)

**Goal**: Update watchlist refresh processor to use new method

- [ ] 3.1 Update `backend/app/watchlist/refresh_processor.py:463`
  - [ ] Change: `news_service.get_symbol_news(symbol)` → `news_service.get_news_intelligence(symbol)`
  - [ ] Verify: No other changes needed (NewsBundle structure unchanged)

- [ ] 3.2 **TEST**: Run watchlist refresh
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  cd ~/portfolio-ai/backend && python -c "
  from app.watchlist.refresh_processor import process_ticker_snapshot
  from app.storage import get_storage
  storage = get_storage()
  # Test with a real ticker in watchlist
  result = process_ticker_snapshot(storage, 'AAPL')
  print(f'Success: {result is not None}')
  "
  ```

- [ ] 3.3 **COMMIT**: "refactor(watchlist): use unified news intelligence method"
  - **Rollback**: `git reset --hard HEAD~1` if watchlist breaks

---

### 🔵 CHECKPOINT 4: Migrate Agent Tools (CRITICAL SYSTEM)

**Goal**: Update AI agent tools to use new method

- [ ] 4.1 Update `backend/app/agents/tools.py:191-195`
  - [ ] Line 191: `get_market_news()` → `get_news_intelligence(None)`
  - [ ] Line 193: `get_symbol_news(symbol)` → `get_news_intelligence(symbol)`

- [ ] 4.2 **TEST**: Run agent tool tests
  ```bash
  cd ~/portfolio-ai/backend && pytest tests/unit/agents/test_agent_tools.py -v
  ```

- [ ] 4.3 **COMMIT**: "refactor(agents): use unified news intelligence method"
  - **Rollback**: `git reset --hard HEAD~1` if agents break

---

### 🔵 CHECKPOINT 5: Migrate Celery Tasks

**Goal**: Update scheduled tasks to use new method

- [ ] 5.1 Update `backend/app/tasks/news_tasks.py:123`
  - [ ] Change: `get_market_news()` → `get_news_intelligence(None)`

- [ ] 5.2 **TEST**: Verify task imports work
  ```bash
  cd ~/portfolio-ai/backend && python -c "
  from app.tasks.news_tasks import refresh_market_news
  print('Import successful')
  "
  ```

- [ ] 5.3 **COMMIT**: "refactor(tasks): use unified news intelligence method"
  - **Rollback**: `git reset --hard HEAD~1` if tasks break

---

### 🔵 CHECKPOINT 6: Update Backend Tests (45+ References)

**Goal**: Update all test references to use new method

- [ ] 6.1 Find and update test files
  ```bash
  cd ~/portfolio-ai/backend
  grep -r "get_market_news\|get_symbol_news" tests/ --files-with-matches
  # Update each file to use get_news_intelligence()
  ```

- [ ] 6.2 **TEST**: Run full backend test suite
  ```bash
  cd ~/portfolio-ai/backend && pytest tests/ -v
  # All tests should pass
  ```

- [ ] 6.3 **COMMIT**: "test(news): update tests to use unified method"
  - **Rollback**: `git reset --hard HEAD~1` if test suite breaks

---

### 🔵 CHECKPOINT 7: Add Unified Frontend Function and Hook

**Goal**: Add new frontend code alongside existing hooks

- [ ] 7.1 Add to `frontend/lib/api/news.ts`
  - [ ] Function: `fetchNewsIntelligence(ticker?: string, options?: ...)`
  - [ ] Call: `GET /api/news?ticker={ticker}`
  - [ ] KEEP old functions (`fetchMarketNews`, `fetchSymbolNews`) - DO NOT DELETE

- [ ] 7.2 Add to `frontend/lib/hooks/useNews.ts`
  - [ ] Hook: `useNewsIntelligence(ticker?: string, options?: ...)`
  - [ ] Call: `fetchNewsIntelligence(ticker, options)`
  - [ ] KEEP old hooks (`useMarketNews`, `useSymbolNews`) - DO NOT DELETE

- [ ] 7.3 **TEST**: Verify new hook works
  ```bash
  cd ~/portfolio-ai/frontend && npx tsc --noEmit
  # Should compile without errors
  ```

- [ ] 7.4 **COMMIT**: "feat(frontend): add unified news intelligence hook"
  - **Rollback**: `git reset --hard HEAD~1` if frontend breaks

---

### 🔵 CHECKPOINT 8: Update Dashboard to Use New Hook

**Goal**: Switch dashboard to new hook (first user-facing change)

- [ ] 8.1 Update `frontend/app/page.tsx`
  - [ ] Replace: `useMarketNews()` → `useNewsIntelligence(undefined)`
  - [ ] Update: Pass data to UnifiedNewsIntelligenceCard

- [ ] 8.2 **TEST**: Verify dashboard loads
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
    http://192.168.8.233:3000 /tmp/checkpoint8-dashboard.png
  # Read screenshot - should show news cards
  ```

- [ ] 8.3 **COMMIT**: "refactor(dashboard): use unified news intelligence hook"
  - **Rollback**: `git reset --hard HEAD~1` if dashboard breaks

---

### 🔵 CHECKPOINT 9: Unify Component Layout (VISUAL PARITY)

**Goal**: Remove layout branching to achieve TRUE visual parity

- [ ] 9.1 Take "before" screenshots
  ```bash
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
    http://192.168.8.233:3000 /tmp/before-dashboard.png
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
    http://192.168.8.233:3000/watchlist VTI /tmp/before-watchlist.png
  ```

- [ ] 9.2 Update `frontend/components/shared/UnifiedNewsIntelligenceCard.tsx`
  - [ ] Remove: `if (recentNews)` branching for article layout
  - [ ] Use: SINGLE detailed two-column layout for ALL articles
  - [ ] Simplify props: Accept unified `newsIntelligence` structure

- [ ] 9.3 Take "after" screenshots and compare
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
    http://192.168.8.233:3000 /tmp/after-dashboard.png
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
    http://192.168.8.233:3000/watchlist VTI /tmp/after-watchlist.png
  # READ both screenshots - verify IDENTICAL article cards
  ```

- [ ] 9.4 **TEST**: Verify visual parity
  - [ ] Both sections have sentiment breakdown
  - [ ] Both sections have IDENTICAL article cards
  - [ ] Both sections have same sorting/show-all controls

- [ ] 9.5 **COMMIT**: "feat(ui): achieve true visual parity for news intelligence"
  - **Rollback**: `git reset --hard HEAD~1` if visual parity not achieved

---

### 🔵 CHECKPOINT 10: Update Frontend Tests

**Goal**: Update frontend tests to use new hooks

- [ ] 10.1 Update component tests
  - [ ] Update tests for UnifiedNewsIntelligenceCard
  - [ ] Update tests for useNewsIntelligence hook

- [ ] 10.2 **TEST**: Run frontend test suite
  ```bash
  cd ~/portfolio-ai/frontend && npm test
  # All tests should pass
  ```

- [ ] 10.3 **COMMIT**: "test(frontend): update tests for unified news intelligence"
  - **Rollback**: `git reset --hard HEAD~1` if tests break

---

### 🔴 CHECKPOINT 11: Delete Old Code (BREAKING CHANGES)

**Goal**: Remove old methods, endpoints, and hooks

- [ ] 11.1 Delete old backend code
  - [ ] Remove: `get_market_news()` from news_service.py
  - [ ] Remove: `get_symbol_news()` from news_service.py
  - [ ] Remove: `/api/news/market` endpoint
  - [ ] Remove: `/api/news/symbol/{symbol}` endpoint

- [ ] 11.2 Delete old frontend code
  - [ ] Remove: `fetchMarketNews()` from news.ts
  - [ ] Remove: `fetchSymbolNews()` from news.ts
  - [ ] Remove: `useMarketNews()` from useNews.ts
  - [ ] Remove: `useSymbolNews()` from useNews.ts

- [ ] 11.3 **TEST**: Final integration test
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  cd ~/portfolio-ai/backend && pytest tests/ -v
  cd ~/portfolio-ai/frontend && npm test
  ~/portfolio-ai/scripts/lint.sh
  # All should pass
  ```

- [ ] 11.4 **TEST**: Manual UI verification
  ```bash
  # Dashboard should load correctly
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
    http://192.168.8.233:3000 /tmp/final-dashboard.png
  # Watchlist should load correctly
  node ~/portfolio-ai/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
    http://192.168.8.233:3000/watchlist VTI /tmp/final-watchlist.png
  ```

- [ ] 11.5 **COMMIT**: "refactor(news): remove deprecated methods and endpoints"
  - **Rollback**: `git reset --hard HEAD~1` if breaking changes cause issues

---

### 🔵 CHECKPOINT 12: Quality Verification and Documentation

**Goal**: Final quality check and documentation update

- [ ] 12.1 Quality check vs baseline
  ```bash
  bash ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report.sh backend/app --quick
  # Compare to baseline: 19 critical, 77 warnings, 93 medium
  # NEW critical issues? Fix them now
  ```

- [ ] 12.2 Update documentation
  - [ ] Update API_REFERENCE.md with new `/api/news` endpoint
  - [ ] Mark tasks-0047 as superseded in WORK_TRACKER.md
  - [ ] Update component documentation

- [ ] 12.3 **COMMIT**: "docs: update documentation for unified news intelligence"
  - **Rollback**: N/A (documentation only)

---

## Verification Checklist (Must Match TARGET STATE Diagram)

Run these checks after implementation:

### Backend Verification

```bash
# Test market news
curl http://localhost:8000/api/news | jq '.summary'
# Should show: score, score_change, positive/neutral/negative_count, model_breakdown

# Test ticker news
curl http://localhost:8000/api/news?ticker=AAPL | jq '.summary'
# Should show: identical structure to market news

# Verify articles have full metadata
curl http://localhost:8000/api/news | jq '.articles[0].sentiment'
# Should show: score, label, confidence, model
```

### Frontend Visual Verification

```bash
# Take screenshots
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000 /tmp/verify-dashboard.png true

node ~/.claude/skills/browser-automation/scripts/expand-and-screenshot.js \
  http://192.168.8.233:3000/watchlist VTI /tmp/verify-watchlist.png
```

**Then READ screenshots and verify:**

1. **Sentiment Breakdown Present in Both?**
   - [ ] Dashboard shows: "Sentiment Score: X.XX ▲/▼ X.XX"
   - [ ] Dashboard shows: "Headline Mix: X pos, X neu, X neg"
   - [ ] Dashboard shows: "Model Coverage: FinBERT X/Y"
   - [ ] Watchlist shows: Same three lines

2. **Article Cards Identical?**
   - [ ] Same card size/padding in both
   - [ ] Same two-column layout (info left, sentiment right)
   - [ ] Same metadata on left: Vendor badge + Publisher + Timestamp
   - [ ] Same metadata on right: Sentiment badge + Score + Confidence + Model (stacked vertically)
   - [ ] Same font sizes, spacing, colors

3. **Feature Parity?**
   - [ ] Both have sorting dropdown (Recent/Most Positive/Most Negative)
   - [ ] Both have "Show All (X total)" button
   - [ ] Both show AI insights if available
   - [ ] Both handle loading/error states

### Code Quality Verification

```bash
# No duplicate code patterns
rg "fetch.*news" backend/app/services/ | wc -l  # Should be ~1-2 (unified service only)
rg "sentiment.*calculation" backend/app/services/ | wc -l  # Should be 1 (unified)

# No old imports remain
rg "useMarketNews" frontend/  # Should find nothing
rg "MarketNewsCard" frontend/  # Should find nothing (already deleted in 0047)

# Type safety
cd ~/portfolio-ai/frontend && npx tsc --noEmit  # Should pass
```

---

## Success Criteria

- ✅ **Backend**: Single `/api/news` endpoint returns identical structure for market and ticker news
- ✅ **Backend**: Sentiment summary included in both responses
- ✅ **Backend**: All tests passing, no code duplication
- ✅ **Frontend**: Single article layout used for both sections
- ✅ **Frontend**: Visual parity confirmed via screenshots matching TARGET STATE diagram
- ✅ **Integration**: Both sections load correctly, no console/network errors
- ✅ **Quality**: Linting passes, types are correct, no Any types added
- ✅ **Cleanup**: Old files deleted, documentation updated

---

## Relevant Files

**Backend (to be created/modified):**
- `backend/app/services/news_intelligence_service.py` (NEW - unified service)
- `backend/app/api/news.py` (MODIFY - add /api/news endpoint, remove /api/news/market)
- `backend/app/api/watchlist.py` (MODIFY - use unified service)

**Backend (to be deleted):**
- Old market_news_service.py (if exists separately)
- Old market news Pydantic models (if separate)

**Frontend (to be modified):**
- `frontend/components/shared/UnifiedNewsIntelligenceCard.tsx` (MODIFY - remove layout branching)
- `frontend/lib/hooks/useNews.ts` (MODIFY - create useNewsIntelligence, delete useMarketNews)
- `frontend/app/page.tsx` (MODIFY - use new hook)
- `frontend/components/watchlist/ExpandedRow.tsx` (MODIFY - use new data structure)

**Frontend (to be deleted):**
- Old TypeScript types for separate market/ticker news structures

---

## Notes

- This task supersedes tasks-0047 which only did partial unification
- Context usage expected to be high - use /pause_it at 85% to save state
- Take screenshots BEFORE starting to document current state
- Read screenshots at each verification step - don't skip this!
