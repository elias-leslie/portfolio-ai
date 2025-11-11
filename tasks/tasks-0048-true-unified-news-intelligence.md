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

### 1.0 Backend: Create Unified News Intelligence Service

- [ ] 1.1 Create `backend/app/services/news_intelligence_service.py`
  - [ ] Define `NewsIntelligenceResponse` Pydantic model with summary + articles
  - [ ] Create `get_news_intelligence(ticker: Optional[str], limit: int)` function
  - [ ] Implement sentiment summary calculation (aggregate from articles)
  - [ ] Implement article fetching with full sentiment metadata
  - [ ] Add model breakdown calculation (finbert vs vader counts)
  - [ ] Include AI insights (plain_language_headline, impact_summary, actionable_insight)

- [ ] 1.2 Add database helper functions
  - [ ] `fetch_news_articles(ticker: Optional[str], limit: int)` - unified query
  - [ ] `calculate_sentiment_summary(articles: List)` - aggregate stats
  - [ ] `enrich_with_ai_insights(articles: List)` - add AI fields if available

- [ ] 1.3 Write comprehensive tests
  - [ ] Test market-wide news (ticker=None)
  - [ ] Test ticker-specific news (ticker="AAPL")
  - [ ] Test sentiment summary calculation
  - [ ] Test model breakdown calculation
  - [ ] Test with/without AI insights
  - [ ] Test edge cases (no articles, all same sentiment, etc.)

### 2.0 Backend: Create Unified API Endpoint

- [ ] 2.1 Create `/api/news` endpoint in `backend/app/api/news.py`
  - [ ] GET /api/news?ticker={ticker}&limit={limit}
  - [ ] Use news_intelligence_service.get_news_intelligence()
  - [ ] Return unified NewsIntelligenceResponse structure
  - [ ] Add query parameter validation
  - [ ] Add proper error handling

- [ ] 2.2 Delete old market news endpoint
  - [ ] Remove /api/news/market route
  - [ ] Delete market_news_service.py (if separate)
  - [ ] Remove old Pydantic models

- [ ] 2.3 Update watchlist endpoint to use unified service
  - [ ] Modify watchlist endpoint to call news_intelligence_service
  - [ ] Return recent_news using new unified structure
  - [ ] Ensure backward compatibility for other watchlist fields

- [ ] 2.4 Write API tests
  - [ ] Test GET /api/news (market news)
  - [ ] Test GET /api/news?ticker=AAPL (ticker news)
  - [ ] Test invalid ticker
  - [ ] Test limit parameter
  - [ ] Test response structure matches schema

### 3.0 Frontend: Update Hooks to Use Unified Endpoint

- [ ] 3.1 Create unified `useNewsIntelligence` hook
  - [ ] Accept optional ticker parameter
  - [ ] Call `/api/news?ticker={ticker}` endpoint
  - [ ] Return unified NewsIntelligenceResponse type
  - [ ] Handle loading, error states

- [ ] 3.2 Update Dashboard to use new hook
  - [ ] Replace useMarketNews with useNewsIntelligence()
  - [ ] Pass data to UnifiedNewsIntelligenceCard
  - [ ] Remove old hook import

- [ ] 3.3 Update Watchlist to use new hook
  - [ ] Replace recent_news from watchlist endpoint with useNewsIntelligence(ticker)
  - [ ] Or keep in watchlist response but ensure it uses unified structure
  - [ ] Update ExpandedRow props

- [ ] 3.4 Delete old hooks
  - [ ] Remove useMarketNews hook file
  - [ ] Remove old TypeScript types for market news
  - [ ] Update imports across codebase

### 4.0 Frontend: Unify Article Layout in Component

- [ ] 4.1 Update UnifiedNewsIntelligenceCard
  - [ ] Remove `if (recentNews)` branching for article layout
  - [ ] Use SINGLE detailed two-column layout for ALL articles
  - [ ] Ensure layout includes:
    - [ ] Left side: Headline, Vendor badge, Publisher, Timestamp
    - [ ] Right side: Sentiment badge, Score, Confidence, Model badge (stacked)
  - [ ] Show AI insights if available (impact_summary, actionable_insight)
  - [ ] Show ⏳ indicator if plain_language_headline missing

- [ ] 4.2 Update sentiment breakdown section
  - [ ] Always render if summary data exists
  - [ ] Show score, score_change, headline mix, model coverage
  - [ ] Format model breakdown (FinBERT X/Y, fallback count)

- [ ] 4.3 Verify props interface
  - [ ] Accept single `newsIntelligence` prop (unified structure)
  - [ ] Remove marketNewsData, recentNews separate props
  - [ ] Keep ticker prop for conditional sentiment breakdown positioning

### 5.0 Visual Verification with Diagrams

- [ ] 5.1 Take "before" screenshots (from current tasks-0047 state)
  - [ ] Dashboard Market News: /tmp/before-dashboard.png
  - [ ] Watchlist News & Sentiment (VTI expanded): /tmp/before-watchlist.png
  - [ ] **Read both screenshots** and document differences

- [ ] 5.2 After implementation, take "after" screenshots
  - [ ] Dashboard Market News: /tmp/after-dashboard.png
  - [ ] Watchlist News & Sentiment (VTI expanded): /tmp/after-watchlist.png
  - [ ] **Read both screenshots**

- [ ] 5.3 Compare against TARGET STATE diagram
  - [ ] ✅ Both sections have sentiment breakdown at top?
    - Dashboard: Should have "Sentiment Score: X, Headline Mix, Model Coverage"
    - Watchlist: Should have same breakdown
  - [ ] ✅ Both sections use IDENTICAL article cards?
    - Same two-column layout (article info left, sentiment right)
    - Same vendor badge, publisher label, timestamp
    - Same sentiment badge, score, confidence, model badge stacked on right
  - [ ] ✅ Both sections have same sorting controls?
  - [ ] ✅ Both sections have same Show All button?
  - [ ] ✅ No visual differences except positioning?

- [ ] 5.4 Test interactivity
  - [ ] Sorting works in both sections
  - [ ] Show All button works in both sections
  - [ ] Sentiment badges show correct colors
  - [ ] Links open correctly

### 6.0 Testing and Quality Verification

- [ ] 6.1 Backend tests
  - [ ] Run all news service tests
  - [ ] Run all API endpoint tests
  - [ ] Verify no regression in watchlist tests
  - [ ] All tests passing

- [ ] 6.2 Frontend tests (if applicable)
  - [ ] Test component with market news data
  - [ ] Test component with ticker news data
  - [ ] Test edge cases (no data, loading, errors)

- [ ] 6.3 Manual integration testing
  - [ ] Dashboard loads with market news
  - [ ] Watchlist loads with ticker news
  - [ ] Both look visually identical (except sentiment breakdown)
  - [ ] No console errors
  - [ ] No network errors

- [ ] 6.4 Code quality
  - [ ] Run lint: `~/portfolio-ai/scripts/lint.sh`
  - [ ] All type checks pass (mypy)
  - [ ] No duplicate code between sections
  - [ ] Single source of truth verified

### 7.0 Cleanup and Documentation

- [ ] 7.1 Delete obsolete backend files
  - [ ] Old market_news_service.py (if separate)
  - [ ] Old market news endpoint routes
  - [ ] Old Pydantic models for market news

- [ ] 7.2 Delete obsolete frontend files
  - [ ] Old useMarketNews hook
  - [ ] Old TypeScript types for separate structures

- [ ] 7.3 Update documentation
  - [ ] API docs: Document new /api/news endpoint
  - [ ] Component docs: Update UnifiedNewsIntelligenceCard usage
  - [ ] Add architecture diagram to docs (optional)

- [ ] 7.4 Update task files
  - [ ] Mark tasks-0047 as superseded
  - [ ] Update WORK_TRACKER.md

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
