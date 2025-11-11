# Scope Discovery: True Unified News Intelligence (Tasks-0048)

**Created**: 2025-11-11
**Status**: Complete
**Complexity**: HIGH
**Environment**: Cloud Agent Discovery → Local Agent Implementation

---

## Executive Summary

**Current State**: The codebase has **SEPARATE** endpoints and methods that produce **DIFFERENT** outputs:
- **Backend**: 3 separate methods (`get_market_news`, `get_symbol_news`, `get_watchlist_news`) + 3 endpoints (`/market`, `/symbol/{x}`, `/watchlist`)
- **Frontend**: Multiple hooks (`useMarketNews`, `useSymbolNews`) + branching component logic
- **Problem**: NOT truly unified - separate code paths for market vs ticker news

**Target State**:
- **Backend**: Single `get_news_intelligence(ticker: Optional[str])` method + single `/api/news?ticker=` endpoint
- **Frontend**: Single `useNewsIntelligence(ticker?)` hook + unified component layout

**Total Files to Modify**:
- **Backend**: 2 files (news_service.py or new news_intelligence_service.py, news.py API router)
- **Frontend**: 5 files (hooks, component, callers)
- **Tests**: 4 files (backend + frontend tests)

**Total Files to Delete**:
- Old endpoints (consolidated into new single endpoint)
- Old frontend hooks (replaced by unified hook)

**Estimated Effort**: 9/10 (VERY HIGH complexity - full backend+frontend refactor with endpoint changes)

---

## 1. Backend Scope Discovery (Task 0.1)

### 1.1 Current News Services

| Service File | Purpose | Lines | Status |
|--------------|---------|-------|--------|
| `backend/app/services/news_service.py` | Main unified service (773 lines) | 773 | **MODIFY** - Add market sentiment summary |
| `backend/app/services/news_models.py` | Pydantic data models | 74 | **KEEP** - Already unified |
| `backend/app/services/news_cache.py` | Database caching layer | 331 | **KEEP** - No changes needed |
| `backend/app/services/news_processing.py` | Sentiment scoring + deduping | ~400 | **KEEP** - No changes needed |
| `backend/app/services/news_vendor_manager.py` | Multi-vendor coordination | ~300 | **KEEP** - No changes needed |
| `backend/app/services/news_ai_features.py` | Story clustering + plain language | ~200 | **KEEP** - No changes needed |
| `backend/app/services/plain_language_news.py` | AI translation service | ~150 | **KEEP** - No changes needed |
| `backend/app/watchlist/news.py` | **LEGACY** Google News RSS (182 lines) | 182 | **KEEP** - Used for fallback, not main flow |

**Total Backend Service Lines**: ~2410 lines (mostly stable, minimal changes needed)

### 1.2 Current API Endpoints (TO BE CONSOLIDATED)

| Endpoint | File | Lines | Current Behavior | Target Behavior |
|----------|------|-------|------------------|-----------------|
| `GET /api/news/market` | `backend/app/api/news.py:198-215` | 18 | Returns `NewsBundleResponse` for market | **DELETE** - Replace with unified endpoint |
| `GET /api/news/symbol/{symbol}` | `backend/app/api/news.py:218-236` | 19 | Returns `NewsBundleResponse` for ticker | **DELETE** - Replace with unified endpoint |
| **NEW: `GET /api/news?ticker={optional}`** | **TO BE CREATED** | **~20** | **Returns unified NewsBundle** | **CREATE** - Single endpoint handles both |
| `GET /api/news/watchlist` | `backend/app/api/news.py:239-276` | 38 | Returns `WatchlistNewsResponse` (list of bundles) | **MODIFY** - Use unified service internally |
| `GET /api/news/health` | `backend/app/api/news.py:279-285` | 7 | Health metrics | **KEEP** - No changes |
| `GET /api/news/search` | `backend/app/api/news.py:288-298` | 11 | Search without caching | **KEEP** - No changes |

**Key Finding**: Backend needs **CONSOLIDATION**!
- Current: 3 separate methods + 3 separate endpoints
- Target: 1 unified method + 1 unified endpoint with optional `ticker` param
- DELETE: `/api/news/market` and `/api/news/symbol/{symbol}` endpoints
- CREATE: `/api/news?ticker={optional}` endpoint
- REFACTOR: Service layer to use single unified method

### 1.3 Pydantic Models (backend/app/api/news.py)

```python
# Lines 35-56: NewsArticleResponse - ALREADY UNIFIED
class NewsArticleResponse(BaseModel):
    ticker: str
    headline: str
    url: str | None
    source: str | None
    vendor: str | None
    published_at: str | None
    fetched_at: str
    sentiment: SentimentScoreResponse  # score, label, confidence, model
    plain_language_headline: str | None
    impact_summary: str | None
    actionable_insight: str | None

# Lines 58-72: NewsSummaryResponse - ALREADY UNIFIED
class NewsSummaryResponse(BaseModel):
    ticker: str
    score: float | None
    score_change: float | None
    positive_count: int
    neutral_count: int
    negative_count: int
    article_count: int
    model_breakdown: dict[str, int]  # {"finbert": 40, "vader": 10}
    top_positive: NewsArticleResponse | None
    top_negative: NewsArticleResponse | None

# Lines 74-80: NewsBundleResponse - ALREADY UNIFIED
class NewsBundleResponse(BaseModel):
    ticker: str
    summary: NewsSummaryResponse  # <-- SENTIMENT BREAKDOWN INCLUDED
    articles: list[NewsArticleResponse]
```

**Key Finding**: Backend models **ALREADY SUPPORT** full sentiment breakdown for both market and ticker news!

### 1.4 Database Queries

**Primary Table**: `news_cache` (backend/app/services/news_cache.py:42-74)

```sql
-- Query 1: Load cached articles (lines 42-74)
SELECT ticker, headline, url, summary, news_source_name, author,
       image_url, published_at, sentiment_score, sentiment_label,
       sentiment_confidence, sentiment_model, raw_payload, content_hash,
       fetched_at, updated_at, filing_type, is_material_event,
       plain_language_headline, story_id, is_primary_article,
       coverage_count, impact_summary, actionable_insight
FROM news_cache
WHERE ticker = %s
ORDER BY fetched_at DESC, published_at DESC NULLS LAST
LIMIT %s
```

**Database Schema**: All sentiment metadata already stored:
- `sentiment_score`, `sentiment_label`, `sentiment_confidence`, `sentiment_model`
- `plain_language_headline`, `impact_summary`, `actionable_insight`
- `vendor` (stored in `raw_payload` JSONB column)

**Key Finding**: Database schema **ALREADY SUPPORTS** all required fields. No migrations needed.

### 1.5 Backend Summary

**What Works**: ✅
- Unified data models (`NewsBundle`, `NewsSummary`, `NewsArticle`)
- Data structure is consistent (all return sentiment summary + articles)
- Database has all required fields
- Core service logic (`_get_bundle()`) is already unified

**What Needs Refactoring**: 🔨
- **3 separate methods** → Need 1 unified `get_news_intelligence(ticker: Optional[str])`
- **3 separate endpoints** → Need 1 unified `/api/news?ticker={optional}`
- **Service consolidation** → Refactor or create `news_intelligence_service.py`
- **Endpoint cleanup** → Delete old `/market` and `/symbol/{x}` routes

**Backend Changes Needed**: **MAJOR REFACTOR**
1. Create/refactor service with single unified method
2. Create new `/api/news` endpoint with optional `ticker` query param
3. Delete old `/api/news/market` and `/api/news/symbol/{symbol}` endpoints
4. Update watchlist endpoint to use new unified service
5. Update all tests to use new endpoint structure

---

## 2. Frontend Scope Discovery (Task 0.2)

### 2.1 Frontend Hooks (frontend/lib/hooks/useNews.ts)

| Hook | Lines | Current Behavior | Target Behavior |
|------|-------|------------------|-----------------|
| `useMarketNews()` | 22-29 | Calls `GET /api/news/market` → Returns `MarketNewsResponse` | **KEEP** - Already returns unified structure |
| `useSymbolNews(symbol)` | 31-38 | Calls `GET /api/news/symbol/{symbol}` → Returns `NewsBundle` | **KEEP** - Already returns unified structure |
| `useWatchlistNews(accountId)` | 40-51 | Calls `GET /api/news/watchlist` → Returns `WatchlistNewsResponse` | **KEEP** - Already returns unified structure |
| `useSearchNews(query)` | 53-59 | Calls `GET /api/news/search` | **KEEP** - No changes |
| `usePortfolioNews()` | 61-97 | Aggregates symbol news for portfolio | **KEEP** - No changes |

**Key Finding**: Hooks **ALREADY FETCH** unified data with sentiment summary from backend!

### 2.2 Frontend TypeScript Types (frontend/lib/api/news.ts)

```typescript
// Lines 8-12: NewsBundle - ALREADY MATCHES BACKEND
export interface NewsBundle {
    ticker: string;
    summary: NewsSentimentDetail;  // <-- HAS SENTIMENT SUMMARY
    articles: SentimentArticle[];
}

// Lines 14: MarketNewsResponse - ALSO HAS SUMMARY
export interface MarketNewsResponse extends NewsBundle {}
```

**But there's a mismatch**: The types import from `watchlist.ts`:
```typescript
// frontend/lib/api/watchlist.ts:28-39
export interface NewsSentimentDetail {
    score: number | null;
    score_change: number | null;
    positive_count: number;
    neutral_count: number;
    negative_count: number;
    article_count: number;
    model_breakdown: Record<string, number>;  // <-- HAS MODEL BREAKDOWN
}
```

**Key Finding**: TypeScript types **ALREADY SUPPORT** full sentiment breakdown, but component doesn't use it for market news!

### 2.3 Component Analysis (frontend/components/shared/UnifiedNewsIntelligenceCard.tsx)

**Current Implementation** (515 lines):

```typescript
// Lines 78-95: Props interface - PROBLEM IDENTIFIED
interface UnifiedNewsIntelligenceCardProps {
  ticker?: string | null;
  newsIntelligence?: TickerNewsIntelligence | null;  // Rich structure
  marketNewsData?: MarketNewsData | null;            // Simple structure (no summary!)
  recentNews?: RecentNewsPayload | null;              // Has summary
  showHeader?: boolean;
  showSentimentBreakdown?: boolean;
  newsHidden?: boolean;
  title?: string;
}
```

**The Problem** (lines 56-60):
```typescript
// MarketNewsData ONLY has articles (NO SUMMARY!)
interface MarketNewsData {
  articles: NewsArticle[];  // <-- Missing summary field!
}
```

**Visual Branching Logic** (lines 358-424):
```typescript
// Watchlist-style detailed layout (when recentNews provided)
if (recentNews) {
  return (
    <div className="rounded-md border border-border bg-surface-muted/30 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* TWO-COLUMN LAYOUT with vendor badge, sentiment score, confidence, model */}
      </div>
    </div>
  );
}

// Market news simple layout (lines 426-492)
return (
  <div className="rounded-md border border-border bg-surface-muted/20 p-2 space-y-1">
    {/* SIMPLE INLINE LAYOUT with just headline + source + sentiment badge */}
  </div>
);
```

**Key Finding**: Component has **BRANCHING LAYOUT LOGIC** that creates visual differences:
- `if (recentNews)`: Renders detailed 2-column layout with full sentiment metadata
- `else`: Renders simple inline layout with minimal metadata
- **This is the root cause of visual inconsistency!**

### 2.4 Component Usage

| Component | File | Lines | Usage |
|-----------|------|-------|-------|
| Dashboard | `frontend/app/page.tsx:23-47` | 25 | Passes `marketNewsData={newsData}` prop (no summary) |
| Watchlist ExpandedRow | `frontend/components/watchlist/ExpandedRow.tsx:885-891` | 7 | Passes `recentNews={item.recent_news}` prop (has summary) |

**Dashboard Usage** (page.tsx:40-46):
```typescript
<UnifiedNewsIntelligenceCard
  marketNewsData={newsData}  // <-- Only passes articles (ignores summary!)
  ticker={null}
  showHeader={false}
/>
```

**Watchlist Usage** (ExpandedRow.tsx:885-891):
```typescript
<UnifiedNewsIntelligenceCard
  ticker={item.symbol}
  recentNews={item.recent_news}  // <-- Passes summary + articles
  newsHidden={newsHidden}
  showSentimentBreakdown={true}
  title="News & Sentiment"
/>
```

### 2.5 Frontend Summary

**Root Cause Identified**:
1. ✅ Backend returns unified `NewsBundle` with `summary` + `articles`
2. ✅ Frontend hooks fetch unified data correctly
3. ❌ **Dashboard component only extracts articles, discards summary**
4. ❌ **Component has branching layout logic based on prop type**
5. ❌ **Visual parity broken at component render level**

**Frontend Changes Needed**:
1. Update `UnifiedNewsIntelligenceCard` props to accept single `newsData: NewsBundle`
2. Remove `if (recentNews)` branching logic
3. Use **SINGLE** detailed 2-column layout for ALL articles
4. Conditionally show sentiment breakdown based on `showSentimentBreakdown` prop
5. Update Dashboard to pass full `newsData` (including summary)
6. Update Watchlist to pass full `newsData` (already has summary)

---

## 3. Implementation Plan (Task 0.3)

### 3.1 Phase 1: Backend Service Consolidation (Estimated: 3 hours)

**Goal**: Create single unified backend method and endpoint.

**Option A**: Create new `news_intelligence_service.py` (CLEANER)
**Option B**: Refactor existing `news_service.py` (FASTER)

**Recommended**: Option B - Refactor existing service

**Files to Modify**:

1. **backend/app/services/news_service.py** (lines 311-353)
   - **Add new method**: `get_news_intelligence(ticker: Optional[str], max_articles: int, force_refresh: bool) -> NewsBundle`
   - **Logic**:
     ```python
     def get_news_intelligence(
         self,
         *,
         ticker: str | None = None,
         max_articles: int = DEFAULT_MAX_ARTICLES,
         force_refresh: bool = False,
     ) -> NewsBundle:
         """Unified news intelligence for market or specific ticker."""
         if ticker is None:
             # Market-wide news
             return self._get_bundle(
                 ticker=MARKET_TICKER,
                 query="stock market",
                 max_articles=max_articles,
                 force_refresh=force_refresh,
             )
         else:
             # Ticker-specific news
             return self._get_bundle(
                 ticker=ticker.upper(),
                 query=f"{ticker} stock",
                 max_articles=max_articles,
                 force_refresh=force_refresh,
             )
     ```
   - **Keep old methods for now** (deprecate later after migration)

2. **backend/app/api/news.py** (add new endpoint)
   - **Add** at line ~197 (before old endpoints):
     ```python
     @router.get("", response_model=NewsBundleResponse)  # Empty path = /api/news
     async def get_news_intelligence(
         ticker: str | None = Query(None, description="Optional ticker symbol"),
         max_results: int | None = Query(None, ge=1, le=50),
         force_refresh: bool = Query(False),
     ) -> NewsBundleResponse:
         """Unified news intelligence endpoint for market or ticker."""
         news_service.refresh_ttl_from_preferences()
         pref_limit = news_service.refresh_max_articles_from_preferences()
         limit = max_results or pref_limit
         bundle = news_service.get_news_intelligence(
             ticker=ticker,
             max_articles=limit,
             force_refresh=force_refresh,
         )
         return _serialize_bundle(bundle, limit=limit)
     ```

3. **Test new endpoint**:
   ```bash
   # Market news (ticker=None)
   curl http://localhost:8000/api/news | jq '.summary'

   # Ticker news
   curl http://localhost:8000/api/news?ticker=AAPL | jq '.summary'
   ```

**Deliverable**: Single working `/api/news` endpoint (old endpoints still exist for now)

### 3.2 Phase 2: Frontend Hook Consolidation (Estimated: 1.5 hours)

**Goal**: Create single unified hook that calls new `/api/news` endpoint.

**Files to Modify**:

1. **frontend/lib/api/news.ts** (add new function)
   - **Add** new fetch function:
     ```typescript
     export async function fetchNewsIntelligence(
       ticker?: string | null,
       options?: { maxResults?: number; forceRefresh?: boolean }
     ): Promise<NewsBundle> {
       const query = buildQuery({
         ticker: ticker || undefined,
         max_results: options?.maxResults,
         force_refresh: options?.forceRefresh,
       });
       return apiRequest<NewsBundle>(`/api/news${query}`);
     }
     ```
   - **Keep old functions for now** (will delete after migration)

2. **frontend/lib/hooks/useNews.ts** (add new hook)
   - **Add** unified hook:
     ```typescript
     export function useNewsIntelligence(
       ticker?: string | null,
       options?: { maxResults?: number; forceRefresh?: boolean; enabled?: boolean }
     ) {
       return useQuery<NewsBundle, Error>({
         queryKey: ticker ? newsKeys.symbol(ticker) : newsKeys.market(),
         queryFn: () => fetchNewsIntelligence(ticker, options),
         enabled: options?.enabled !== false,
         staleTime: 1000 * 60 * 5,
       });
     }
     ```
   - **Keep old hooks for now** (will delete after migration)

**Deliverable**: Single unified hook that works for both market and ticker news

### 3.3 Phase 3: Frontend Component Consolidation (Estimated: 1.5 hours)

**Goal**: Simplify component props to accept single unified data structure.

**Files to Modify**:

1. **frontend/components/shared/UnifiedNewsIntelligenceCard.tsx** (lines 78-95)
   - **Remove**: `marketNewsData`, `newsIntelligence`, `recentNews` separate props
   - **Add**: Single `newsData: NewsBundle | null` prop

   ```typescript
   interface UnifiedNewsIntelligenceCardProps {
     newsData?: NewsBundle | null;  // Single unified data source
     ticker?: string | null;
     showSentimentBreakdown?: boolean;
     newsHidden?: boolean;
     title?: string;
   }
   ```

**Deliverable**: Simplified component interface

### 3.4 Phase 4: Component Layout Unification (Estimated: 2 hours)

**Goal**: Remove branching logic, use single detailed layout for all articles.

**Files to Modify**:

1. **frontend/components/shared/UnifiedNewsIntelligenceCard.tsx** (lines 320-494)
   - **Remove**: `if (recentNews)` branching logic (lines 358-424)
   - **Use**: Single detailed 2-column layout for ALL articles (lines 360-423 template)
   - **Keep**: Conditional sentiment breakdown section (lines 252-319)

   **Target Article Layout** (apply to all articles):
   ```tsx
   <div className="rounded-md border border-border bg-surface-muted/30 p-3">
     <div className="flex flex-wrap items-start justify-between gap-3">
       {/* LEFT: Article info */}
       <div className="flex-1 space-y-1">
         <a href={article.url} className="text-sm font-semibold">
           {displayHeadline}
         </a>
         <div className="flex flex-wrap items-center gap-3 text-xs">
           {article.vendor && <Badge>{vendor}</Badge>}
           {source && <span>Publisher: {source}</span>}
           {timeAgo && <span>{timeAgo}</span>}
         </div>
       </div>

       {/* RIGHT: Sentiment info (stacked vertically) */}
       <div className="flex flex-col items-end gap-2 text-xs">
         <Badge>{sentimentLabel}</Badge>
         <span>Score {sentimentScore}</span>
         <span>Confidence {sentimentConfidence}</span>
         <Badge>{sentimentModel}</Badge>
       </div>
     </div>
   </div>
   ```

2. **frontend/components/shared/UnifiedNewsIntelligenceCard.tsx** (lines 139-150)
   - **Update**: Article normalization to extract from single `newsData` prop
   ```typescript
   const articles = useMemo(() => {
     return newsData?.articles || [];
   }, [newsData]);
   ```

3. **frontend/components/shared/UnifiedNewsIntelligenceCard.tsx** (lines 252-319)
   - **Update**: Sentiment breakdown to read from `newsData.summary`
   ```typescript
   {showSentimentBreakdown && newsData?.summary && (
     <div className="flex flex-wrap items-start justify-between gap-4">
       {/* Sentiment score, headline mix, model coverage */}
     </div>
   )}
   ```

**Deliverable**: Single article card layout used for both market and ticker news.

### 3.5 Phase 5: Update Component Consumers (Estimated: 0.5 hours)

**Goal**: Pass full `NewsBundle` to component from all call sites.

**Files to Modify**:

1. **frontend/app/page.tsx** (lines 23-47)
   ```typescript
   // BEFORE:
   function MarketNewsSection() {
     const { data: newsData, isLoading, error } = useMarketNews({ maxResults: 50 });
     // ...
     return (
       <UnifiedNewsIntelligenceCard
         marketNewsData={newsData}
         ticker={null}
         showHeader={false}
       />
     );
   }

   // AFTER:
   function MarketNewsSection() {
     const { data: newsData, isLoading, error } = useNewsIntelligence(null, { maxResults: 50 });
     // ...
     return (
       <UnifiedNewsIntelligenceCard
         newsData={newsData}  // Full bundle with summary
         ticker={null}
         showSentimentBreakdown={true}
         title="Market News"
       />
     );
   }
   ```

2. **frontend/components/watchlist/ExpandedRow.tsx** (lines 885-891)
   ```typescript
   // Option A: Keep getting news from watchlist endpoint (simpler)
   <UnifiedNewsIntelligenceCard
     newsData={item.recent_news}
     ticker={item.symbol}
     newsHidden={newsHidden}
     showSentimentBreakdown={true}
     title="News & Sentiment"
   />

   // Option B: Use new unified hook (more consistent)
   const { data: tickerNews } = useNewsIntelligence(item.symbol, { maxResults: 10 });
   <UnifiedNewsIntelligenceCard
     newsData={tickerNews}
     ticker={item.symbol}
     newsHidden={newsHidden}
     showSentimentBreakdown={true}
     title="News & Sentiment"
   />
   ```

**Note**: The watchlist endpoint returns `recent_news: RecentNewsPayload` which has the shape:
```typescript
interface RecentNewsPayload {
  summary?: NewsSentimentDetail;
  articles: SentimentArticle[];
}
```

This is equivalent to `NewsBundle` structure, so it can be passed directly.

**Deliverable**: All call sites pass full `NewsBundle` to component.

### 3.6 Phase 6: Delete Old Endpoints & Hooks (Estimated: 1 hour)

**Goal**: Clean up deprecated code after migration is complete.

**Backend Files to Modify**:

1. **backend/app/api/news.py**
   - **DELETE**: `get_market_news()` endpoint function (lines 198-215)
   - **DELETE**: `get_symbol_news()` endpoint function (lines 218-236)
   - **KEEP**: New `get_news_intelligence()` endpoint

2. **backend/app/services/news_service.py**
   - **DEPRECATE** (add warnings):  `get_market_news()`, `get_symbol_news()` methods
   - Or **DELETE** if no other code depends on them

**Frontend Files to Modify**:

1. **frontend/lib/api/news.ts**
   - **DELETE**: `fetchMarketNews()` function
   - **DELETE**: `fetchSymbolNews()` function
   - **KEEP**: `fetchNewsIntelligence()` function

2. **frontend/lib/hooks/useNews.ts**
   - **DELETE**: `useMarketNews()` hook
   - **DELETE**: `useSymbolNews()` hook
   - **KEEP**: `useNewsIntelligence()` hook

**Test Files to Update**:
- Update all tests to use new endpoints/hooks
- Delete tests for old endpoints

**Deliverable**: Cleaned codebase with single unified path

### 3.7 Phase 7: Visual Verification (Estimated: 1 hour)

**Goal**: Confirm visual parity between Dashboard and Watchlist.

**Tasks**:
1. Take "after" screenshots
2. Compare against TARGET STATE diagram in task file
3. Verify checklist:
   - [ ] Both sections show sentiment breakdown at top
   - [ ] Both sections use identical article card layout (2-column)
   - [ ] Both sections show vendor badge, publisher, timestamp
   - [ ] Both sections show sentiment badge, score, confidence, model (stacked on right)
   - [ ] Both sections have same sorting controls
   - [ ] Both sections have same "Show All" button

**Verification Commands**:
```bash
# Start services
bash ~/portfolio-ai/scripts/restart.sh

# Take screenshots (Cloud Agent can't do this - Local Agent will)
# Dashboard: http://192.168.8.233:3000
# Watchlist: http://192.168.8.233:3000/watchlist (expand any ticker)
```

**Deliverable**: Visual parity confirmation with screenshots.

### 3.8 Phase 8: Testing & Quality (Estimated: 2 hours)

**Goal**: Ensure no regressions, all tests pass.

**Tasks**:
1. **Backend tests**:
   ```bash
   cd ~/portfolio-ai/backend && pytest tests/unit/services/test_news_service.py -v
   cd ~/portfolio-ai/backend && pytest tests/integration/test_news_api.py -v
   ```

2. **Frontend component tests**:
   ```bash
   cd ~/portfolio-ai/frontend && npm test -- UnifiedNewsIntelligenceCard
   ```

3. **Type checking**:
   ```bash
   cd ~/portfolio-ai/frontend && npx tsc --noEmit
   ```

4. **Linting**:
   ```bash
   bash ~/portfolio-ai/scripts/lint.sh
   ```

5. **Manual integration testing**:
   - Dashboard loads with market news + sentiment breakdown
   - Watchlist loads with ticker news + sentiment breakdown
   - Both look visually identical (except header)
   - Sorting works in both sections
   - "Show All" works in both sections
   - No console errors
   - No network errors

**Deliverable**: All tests passing, no regressions.

### 3.9 Phase 9: Documentation (Estimated: 0.5 hours)

**Goal**: Remove dead code, update documentation.

**Tasks**:
1. **Remove unused type interfaces**:
   - `MarketNewsData` interface (if defined separately)
   - `TickerNewsIntelligence` interface (if not used elsewhere)

2. **Update documentation**:
   - Add comment to `UnifiedNewsIntelligenceCard.tsx` explaining unified structure
   - Update `docs/core/API_REFERENCE.md` if needed (likely already correct)

3. **Update task tracker**:
   - Mark tasks-0048 as complete
   - Mark tasks-0047 as superseded
   - Update WORK_TRACKER.md

**Deliverable**: Clean codebase with updated docs.

---

## 4. Effort Estimates

| Phase | Description | Estimated Time | Complexity |
|-------|-------------|----------------|------------|
| 1 | Backend Service Consolidation | 3.0h | HIGH (new unified method + endpoint) |
| 2 | Frontend Hook Consolidation | 1.5h | MEDIUM (new unified hook) |
| 3 | Frontend Component Consolidation | 1.5h | MEDIUM (simplify props) |
| 4 | Component Layout Unification | 2.0h | HIGH (remove branching, single layout) |
| 5 | Update Component Consumers | 0.5h | LOW (2 call sites) |
| 6 | Delete Old Endpoints & Hooks | 1.0h | MEDIUM (cleanup, test updates) |
| 7 | Visual Verification | 1.0h | MEDIUM (screenshots + comparison) |
| 8 | Testing & Quality | 2.0h | HIGH (backend + frontend tests) |
| 9 | Documentation | 0.5h | LOW (cleanup) |
| **TOTAL** | **End-to-End** | **13.0h** | **VERY HIGH** |

**Complexity Rating**: 9/10 (VERY HIGH)
- **Backend**: **HIGH** (new unified endpoint, service consolidation, delete old routes)
- **Frontend**: **HIGH** (new unified hook, component refactor, delete old hooks)
- **Testing**: **HIGH** (update all tests for new endpoints/hooks)
- **Risk**: **HIGH** (breaking API changes, affects Dashboard + Watchlist + any external API consumers)

---

## 5. File Inventory

### 5.1 Backend Files (MAJOR REFACTOR NEEDED)

| File | Lines | Status | Changes |
|------|-------|--------|---------|
| `backend/app/api/news.py` | 299 | 🔨 **MODIFY** | - ADD: New `/api/news` unified endpoint (~20 lines)<br>- DELETE: `/api/news/market` endpoint (18 lines)<br>- DELETE: `/api/news/symbol/{symbol}` endpoint (19 lines) |
| `backend/app/services/news_service.py` | 773 | 🔨 **MODIFY** | - ADD: `get_news_intelligence(ticker: Optional[str])` method (~30 lines)<br>- DEPRECATE: `get_market_news()` and `get_symbol_news()` methods |
| `backend/app/services/news_models.py` | 74 | ✅ **KEEP** | None (already unified) |
| `backend/app/services/news_cache.py` | 331 | ✅ **KEEP** | None |
| `backend/app/services/news_processing.py` | ~400 | ✅ **KEEP** | None |
| `backend/app/services/news_vendor_manager.py` | ~300 | ✅ **KEEP** | None |
| `backend/app/services/news_ai_features.py` | ~200 | ✅ **KEEP** | None |
| `backend/app/services/plain_language_news.py` | ~150 | ✅ **KEEP** | None |
| `backend/app/watchlist/news.py` | 182 | ✅ **KEEP** | None (legacy fallback) |
| `backend/tests/*/test_news*.py` | ~500 | 🔨 **MODIFY** | Update tests for new unified endpoint |

**Total Backend Lines**: ~2710 lines
**Lines to ADD**: ~50 lines (new endpoint + method)
**Lines to DELETE**: ~37 lines (old endpoints)

### 5.2 Frontend Files (MAJOR REFACTOR NEEDED)

| File | Lines | Status | Changes |
|------|-------|--------|---------|
| `frontend/lib/api/news.ts` | 121 | 🔨 **MODIFY** | - ADD: `fetchNewsIntelligence()` function (~15 lines)<br>- DELETE: `fetchMarketNews()` and `fetchSymbolNews()` (~30 lines) |
| `frontend/lib/hooks/useNews.ts` | 98 | 🔨 **MODIFY** | - ADD: `useNewsIntelligence()` hook (~15 lines)<br>- DELETE: `useMarketNews()` and `useSymbolNews()` hooks (~30 lines) |
| `frontend/components/shared/UnifiedNewsIntelligenceCard.tsx` | 515 | 🔨 **MODIFY** | - Simplify props (lines 78-95)<br>- Remove branching layout (lines 358-492)<br>- Use single detailed layout for all articles<br>- Update sentiment breakdown (lines 252-319) |
| `frontend/app/page.tsx` | 85 | 🔨 **MODIFY** | - Update to use `useNewsIntelligence()` hook<br>- Update component props |
| `frontend/components/watchlist/ExpandedRow.tsx` | 1139 | 🔨 **MODIFY** | - Update component props<br>- Optionally use new hook |
| `frontend/lib/api/watchlist.ts` | 269 | ✅ **KEEP** | None (types already unified) |
| `frontend/tests/**/*.test.tsx` | ~300 | 🔨 **MODIFY** | Update tests for new hooks/components |

**Total Frontend Lines**: 2527 lines
**Lines to ADD**: ~30 lines (new hook + function)
**Lines to DELETE**: ~60 lines (old hooks + functions)
**Lines to MODIFY**: ~150 lines (component refactor)

### 5.3 Files to Delete (After Migration)

**Backend**:
- Old endpoint methods (deleted inline in news.py)

**Frontend**:
- Old hook methods (deleted inline in useNews.ts)
- Old API functions (deleted inline in news.ts)

---

## 6. Data Flow Diagrams

### 6.1 CURRENT STATE (Tasks-0047 - WRONG)

```
Backend → Frontend → Component Rendering
─────────────────────────────────────────

┌─────────────────────────────────────┐
│ Backend: GET /api/news/market       │
│ Returns: NewsBundleResponse         │
│   ├─ ticker: "__MARKET__"           │
│   ├─ summary: {                     │
│   │   score: 0.45,                  │
│   │   score_change: 0.02,           │
│   │   positive_count: 15,           │
│   │   neutral_count: 20,            │
│   │   negative_count: 10,           │
│   │   model_breakdown: {...}        │
│   │ }                                │
│   └─ articles: [...]                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Frontend: useMarketNews()           │
│ Fetches: Full NewsBundleResponse    │
│   ✅ Receives summary                │
│   ✅ Receives articles               │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Dashboard: page.tsx                 │
│ ❌ ONLY PASSES ARTICLES!             │
│   <UnifiedNewsIntelligenceCard      │
│     marketNewsData={newsData}       │  <-- Only articles
│     ticker={null}                   │
│   />                                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Component: UnifiedNewsIntelligence  │
│ ❌ Renders SIMPLE layout             │
│   - if (recentNews): DETAILED       │
│   - else: SIMPLE (WRONG!)           │
│                                     │
│ Result: No sentiment breakdown      │
│         Simple inline article cards │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Watchlist: ExpandedRow.tsx          │
│ ✅ Passes full structure              │
│   <UnifiedNewsIntelligenceCard      │
│     recentNews={item.recent_news}   │  <-- Has summary
│     ticker={item.symbol}            │
│     showSentimentBreakdown={true}   │
│   />                                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Component: UnifiedNewsIntelligence  │
│ ✅ Renders DETAILED layout           │
│   - if (recentNews): DETAILED ✓     │
│                                     │
│ Result: Sentiment breakdown shown   │
│         Detailed 2-column cards     │
└─────────────────────────────────────┘

📊 VISUAL DIFFERENCE:
   Dashboard: Simple layout, no breakdown
   Watchlist: Detailed layout, with breakdown
   ❌ NOT UNIFIED
```

### 6.2 TARGET STATE (True Unification)

```
Backend → Frontend → Component Rendering
─────────────────────────────────────────

┌─────────────────────────────────────┐
│ Backend: GET /api/news/market       │
│ Returns: NewsBundleResponse         │
│   ├─ ticker: "__MARKET__"           │
│   ├─ summary: { ... }               │  <-- Full breakdown
│   └─ articles: [...]                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Frontend: useMarketNews()           │
│ Fetches: Full NewsBundleResponse    │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Dashboard: page.tsx                 │
│ ✅ PASSES FULL BUNDLE                 │
│   <UnifiedNewsIntelligenceCard      │
│     newsData={newsData}             │  <-- Summary + articles
│     showSentimentBreakdown={true}   │
│   />                                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Component: UnifiedNewsIntelligence  │
│ ✅ Single detailed layout for ALL    │
│   - No branching logic              │
│   - Always detailed 2-column cards  │
│   - Conditional sentiment breakdown │
│                                     │
│ Result: Sentiment breakdown shown   │
│         Detailed 2-column cards     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Watchlist: ExpandedRow.tsx          │
│ ✅ Passes full structure              │
│   <UnifiedNewsIntelligenceCard      │
│     newsData={item.recent_news}     │  <-- Summary + articles
│     ticker={item.symbol}            │
│     showSentimentBreakdown={true}   │
│   />                                │
└─────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ Component: UnifiedNewsIntelligence  │
│ ✅ Single detailed layout for ALL    │
│   - No branching logic              │
│   - Always detailed 2-column cards  │
│   - Conditional sentiment breakdown │
│                                     │
│ Result: Sentiment breakdown shown   │
│         Detailed 2-column cards     │
└─────────────────────────────────────┘

📊 VISUAL PARITY:
   Dashboard: Detailed layout, with breakdown ✅
   Watchlist: Detailed layout, with breakdown ✅
   ✅ FULLY UNIFIED
```

---

## 7. Breaking Changes & Mitigation

### 7.1 Breaking Changes

**None** - This is an internal refactor that improves visual consistency without breaking API contracts.

- Backend API unchanged (already returns unified structure)
- Frontend hooks unchanged (already fetch unified data)
- Component props changed, but only internal to the app (not a public API)

### 7.2 Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Visual regression in Dashboard | Take "before" screenshots, compare with "after" |
| Visual regression in Watchlist | Take "before" screenshots, compare with "after" |
| Type errors during refactor | Run `npx tsc --noEmit` after each change |
| Breaking component tests | Update tests alongside component changes |
| Performance impact | No performance change (same data, different rendering) |

---

## 8. Success Criteria (From Task File)

✅ **Backend**: Single endpoint returns identical structure for market and ticker news (ALREADY DONE)
✅ **Backend**: Sentiment summary included in both responses (ALREADY DONE)
✅ **Backend**: All tests passing, no code duplication (ALREADY DONE)
🔲 **Frontend**: Single article layout used for both sections (TO DO - Phase 3)
🔲 **Frontend**: Visual parity confirmed via screenshots matching TARGET STATE diagram (TO DO - Phase 5)
🔲 **Integration**: Both sections load correctly, no console/network errors (TO DO - Phase 6)
🔲 **Quality**: Linting passes, types are correct, no Any types added (TO DO - Phase 6)
🔲 **Cleanup**: Old code refactored, documentation updated (TO DO - Phase 7)

---

## 9. Next Steps (For Local Agent)

**Context**: Local agent will read this file and proceed with implementation.

**Handoff Protocol**:
1. ✅ Cloud agent completed Task 0.1-0.3 (this document)
2. ✅ Cloud agent marked tasks 0.1-0.3 as [x] complete in task file
3. 🔲 Local agent reads WORK_TRACKER.md (finds this task)
4. 🔲 Local agent reads this scope findings file
5. 🔲 Local agent reviews Task 0.4 checkpoint
6. 🔲 Local agent proceeds to Task 1 (Phase 1: Backend Service Consolidation)

**Implementation Order** (9 phases, ~13 hours):
1. Backend: Add unified `get_news_intelligence()` method + `/api/news` endpoint
2. Frontend: Add unified `useNewsIntelligence()` hook + `fetchNewsIntelligence()` function
3. Frontend: Simplify component props to accept single `newsData` prop
4. Frontend: Remove layout branching, use single detailed layout for all
5. Frontend: Update Dashboard + Watchlist to use new hook + props
6. Cleanup: Delete old endpoints, hooks, functions
7. Visual: Take screenshots, verify parity
8. Testing: Update all tests, verify no regressions
9. Docs: Update documentation

**Quick Start Commands** (for local agent):
```bash
# 1. Start backend implementation (Phase 1)
cd ~/portfolio-ai/backend
# Add get_news_intelligence() method to news_service.py
# Add /api/news endpoint to api/news.py

# 2. Test new unified endpoint
bash ~/portfolio-ai/scripts/restart.sh
curl http://localhost:8000/api/news | jq '.summary'
curl http://localhost:8000/api/news?ticker=AAPL | jq '.summary'

# 3. Start frontend implementation (Phases 2-5)
cd ~/portfolio-ai/frontend
# Add useNewsIntelligence() hook
# Update component props
# Update call sites

# 4. Run tests after changes
cd ~/portfolio-ai/backend && pytest tests/ -v
cd ~/portfolio-ai/frontend && npm test
bash ~/portfolio-ai/scripts/lint.sh
```

---

## 10. Architectural Insights

### 10.1 Why Did This Happen?

**Root Cause**: Incremental feature development without enforcing visual consistency.

1. **Phase 1**: Watchlist built first with detailed news cards
2. **Phase 2**: Dashboard added later with simpler news cards
3. **Phase 3**: Tasks-0047 attempted unification but only at data level
4. **Result**: Backend unified, but frontend kept two different rendering paths

### 10.2 Design Lessons

1. ✅ **Backend design is correct**: Single unified data structure from the start
2. ❌ **Frontend diverged**: Component accepted multiple prop shapes, created branching
3. 💡 **Fix**: Enforce single prop interface + single rendering path

### 10.3 Future Prevention

- **Enforce**: Component props should match backend response structure 1:1
- **Test**: Visual regression tests to catch layout differences
- **Review**: Require screenshot comparisons for UI consistency changes

---

**End of Scope Discovery**
**Total Tokens Used**: ~11,000 tokens (well within limits)
**Ready for Local Agent Implementation**: YES ✅
