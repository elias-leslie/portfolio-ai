# Task 0040: Complete News/Sentiment Section Alignment

**Status**: Backend Implementation Needed
**Created**: 2025-11-10
**Branch**: `claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
**Complexity**: Medium
**Estimated Time**: 8-11 hours

## Overview

Frontend work is complete and pushed to the branch. The Market News and Watchlist News/Sentiment sections are now visually aligned with shared utilities and sentiment sorting. **Backend changes are needed** to enable AI-generated insights for market news (full feature parity with watchlist news).

## ✅ Already Completed (Frontend - Cloud Agent)

- [x] Created shared formatting utilities module (`frontend/lib/utils/news-formatting.ts`)
- [x] Refactored all 3 components to use shared utilities (eliminated 140 lines of duplicate code)
- [x] Aligned visual layouts between Market News and Watchlist News sections
- [x] Added sentiment sorting (Recent, Most Positive, Most Negative) to both sections
- [x] Changed display from "6 → 20" to "10 → all" with "Show All" button
- [x] Enabled `plain_language_headline` support in frontend
- [x] Updated TypeScript interfaces for AI insights fields
- [x] All changes committed and pushed to branch
- [x] Created documentation for backend requirements

**Commits**: 5 commits pushed
- `211d380` - Created shared utilities
- `95e8625` - Refactored components
- `dbe53dc` - Layout alignment
- `5d9e08e` - Sentiment sorting
- `5b469ab` - Backend documentation

## 🔧 Task 0: Review Frontend Changes

**Goal**: Understand what's been implemented

**Steps**:
1. Pull the branch:
   ```bash
   git fetch origin
   git checkout claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U
   ```

2. Review key files:
   - `frontend/lib/utils/news-formatting.ts` - Shared utilities
   - `frontend/components/dashboard/MarketNewsCard.tsx` - Market news with sorting
   - `frontend/components/watchlist/NewsIntelligenceCard.tsx` - Watchlist news with sorting
   - `frontend/lib/api/watchlist.ts` - Updated TypeScript interfaces
   - `docs/future-enhancements/market-news-ai-features.md` - Backend requirements

3. Start services and verify frontend works:
   ```bash
   bash ~/portfolio-ai/scripts/start.sh
   ```

4. Test in browser:
   - Navigate to dashboard → Market News section
   - Verify sentiment sorting works (Recent, Most Positive, Most Negative)
   - Verify "Show All" button works
   - Navigate to watchlist → Expand a row → News Intelligence section
   - Verify same sorting and Show All functionality

**Expected**: Frontend works, but market news doesn't show AI insights (impact summaries, actionable insights) because backend doesn't return them yet.

**Verification**:
- [ ] Services start successfully
- [ ] Market News section loads and displays articles
- [ ] Sentiment sorting works in Market News
- [ ] "Show All" button works in Market News
- [ ] Watchlist News Intelligence section loads
- [ ] Sentiment sorting works in Watchlist News
- [ ] Visual layouts are identical between sections

---

## 🔨 Task 1: Update Backend NewsArticleResponse Model

**Goal**: Add AI insight fields to market news API response

**File**: `backend/app/api/news.py`

**Changes**:

1. Update `NewsArticleResponse` class (lines 35-53):
   ```python
   class NewsArticleResponse(BaseModel):
       """Serialized news article."""

       ticker: str
       headline: str
       url: str | None = None
       summary: str | None = None
       source: str | None = None
       author: str | None = None
       image_url: str | None = None
       published_at: str | None = None
       fetched_at: str
       sentiment: SentimentScoreResponse
       vendor: str | None = None
       # SEC filing metadata
       filing_type: str | None = None
       is_material_event: bool = False
       plain_language_headline: str | None = None
       # NEW: AI-generated insights
       impact_summary: str | None = None
       actionable_insight: str | None = None
   ```

**Testing**:
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
python -c "from app.api.news import NewsArticleResponse; print(NewsArticleResponse.__fields__.keys())"
```

**Expected output**: Should include `'impact_summary'` and `'actionable_insight'` in fields.

**Verification**:
- [ ] Model updated with new fields
- [ ] No Pydantic validation errors
- [ ] Python import test passes

---

## 🔨 Task 2: Update Serialization Function

**Goal**: Include AI insights when serializing articles

**File**: `backend/app/api/news.py`

**Changes**:

Update `_serialize_article()` function (lines 130-154):

```python
def _serialize_article(article: Any) -> NewsArticleResponse:
    published_at = (
        article.published_at.isoformat().replace("+00:00", "Z")
        if getattr(article, "published_at", None)
        else None
    )
    fetched_at = (
        article.fetched_at.isoformat().replace("+00:00", "Z")
        if getattr(article, "fetched_at", None)
        else ""
    )

    return NewsArticleResponse(
        ticker=article.ticker,
        headline=article.headline,
        url=article.url,
        summary=article.summary,
        source=article.source,
        author=article.author,
        image_url=article.image_url,
        published_at=published_at,
        fetched_at=fetched_at or "",
        sentiment=_serialize_sentiment(article.sentiment),
        vendor=getattr(article, "vendor", None),
        # NEW: Include AI insights
        plain_language_headline=getattr(article, "plain_language_headline", None),
        impact_summary=getattr(article, "impact_summary", None),
        actionable_insight=getattr(article, "actionable_insight", None),
    )
```

**Testing**:
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/unit/test_news_api.py -v -k serialize
```

**Verification**:
- [ ] Serialization includes new fields
- [ ] Unit tests pass
- [ ] No mypy errors: `~/portfolio-ai/scripts/lint.sh`

---

## 🔨 Task 3: Enable AI Features for Market News

**Goal**: Generate AI insights for market news articles (currently only done for watchlist)

**File**: `backend/app/services/news_service.py`

**Current behavior**: Market news fetching (`get_market_news()`) doesn't apply AI features.

**Reference implementation**: `backend/app/watchlist/watchlist_service.py` (lines 500-650) shows how to apply AI features.

**Required changes**:

1. Import AI services at top of `news_service.py`:
   ```python
   from app.services.plain_language_news import PlainLanguageNewsService
   from app.services.news_ai_features import NewsAIFeatures
   ```

2. Add AI processing to `get_market_news()` method:
   ```python
   def get_market_news(
       self,
       max_articles: int = 10,
       force_refresh: bool = False
   ) -> NewsBundle:
       # ... existing code to fetch articles ...

       # NEW: Apply AI features to articles
       plain_language_service = PlainLanguageNewsService(self.storage)
       ai_features = NewsAIFeatures(self.storage)

       enhanced_articles = []
       for article in bundle.articles[:max_articles]:
           # Apply plain language headline
           enhanced = plain_language_service.enhance_article(article)

           # Generate impact summary and actionable insight
           enhanced = ai_features.generate_insights(enhanced)

           enhanced_articles.append(enhanced)

       bundle.articles = enhanced_articles
       return bundle
   ```

**Note**: The exact method names may differ. Check existing implementations:
- `backend/app/services/plain_language_news.py`
- `backend/app/services/news_ai_features.py`
- `backend/app/watchlist/watchlist_service.py` (reference)

**Important considerations**:
- AI generation is expensive - only process `max_articles`, not all 50
- Cache AI insights to avoid regenerating on every request
- Check if insights already exist before regenerating
- May want to make this async/background processing

**Testing**:
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate

# Test market news endpoint
python -c "
from app.services import NewsService
from app.storage import get_storage

storage = get_storage()
service = NewsService(storage)
bundle = service.get_market_news(max_articles=3)

for article in bundle.articles:
    print(f'Headline: {article.headline}')
    print(f'Plain: {article.plain_language_headline}')
    print(f'Impact: {article.impact_summary}')
    print(f'Insight: {article.actionable_insight}')
    print('---')
"
```

**Expected output**: Each article should have AI-generated fields populated.

**Verification**:
- [ ] AI features are applied to market news
- [ ] `plain_language_headline` is generated
- [ ] `impact_summary` is generated
- [ ] `actionable_insight` is generated
- [ ] Performance is acceptable (<3 seconds for 10 articles)
- [ ] Caching works (subsequent calls are fast)

---

## 🔨 Task 4: Update Frontend TypeScript Types

**Goal**: Remove `as any` cast and use proper types

**File**: `frontend/lib/api/news.ts`

**Current**: Frontend uses `(article as any).plain_language_headline` because types don't include AI fields.

**Changes**:

Update `SentimentArticle` interface in `frontend/lib/api/watchlist.ts` (already done, but verify):

```typescript
export interface SentimentArticle {
    ticker: string;
    headline: string;
    url?: string | null;
    summary?: string | null;
    source?: string | null;
    vendor?: string | null;
    author?: string | null;
    image_url?: string | null;
    published_at?: string | null;
    fetched_at: string;
    sentiment: SentimentScoreMeta;
    content_hash: string;
    raw?: Record<string, unknown>;
    // AI-generated insights
    plain_language_headline?: string | null;
    impact_summary?: string | null;
    actionable_insight?: string | null;
}
```

Update `MarketNewsCard.tsx` to remove cast (line 93):

**Before**:
```typescript
const displayHeadline = (article as any).plain_language_headline || article.headline;
```

**After**:
```typescript
const displayHeadline = article.plain_language_headline || article.headline;
```

**Verification**:
- [ ] TypeScript types updated
- [ ] No type errors: `cd frontend && npm run type-check`
- [ ] `as any` cast removed from MarketNewsCard

---

## 🔨 Task 5: Add AI Insight Display to MarketNewsCard

**Goal**: Display impact summaries and actionable insights in market news

**File**: `frontend/components/dashboard/MarketNewsCard.tsx`

**Reference**: `NewsIntelligenceCard.tsx` already displays these (lines 200-210)

**Changes**:

Add after the metadata div (around line 135):

```typescript
                  </div>
                  {/* NEW: AI Insights */}
                  {(article as any).impact_summary && (
                    <p className="text-xs text-text-muted italic">
                      💡 {(article as any).impact_summary}
                    </p>
                  )}
                  {(article as any).actionable_insight && (
                    <p className="text-xs text-primary font-medium mt-1">
                      💡 {(article as any).actionable_insight}
                    </p>
                  )}
                </div>
```

**Note**: Once Task 4 is complete, remove `as any` casts.

**Verification**:
- [ ] AI insights render in Market News section
- [ ] Impact summaries appear in muted text
- [ ] Actionable insights appear in primary color
- [ ] Layout looks consistent with NewsIntelligenceCard

---

## 🔨 Task 6: Backend Performance Optimization (Optional)

**Goal**: Ensure AI generation doesn't slow down the API too much

**Considerations**:

1. **Caching**: Check if AI insights are cached in `news_cache` table
   - Verify columns exist: `plain_language_headline`, `impact_summary`, `actionable_insight`
   - If not, add migration to add these columns
   - Update cache logic to store/retrieve AI insights

2. **Batch Processing**: Generate AI insights for multiple articles in parallel
   - Use `asyncio.gather()` if services support async
   - Limit concurrent requests to avoid rate limits

3. **Background Processing**: Consider moving AI generation to background task
   - Initial request returns basic data
   - Celery task generates AI insights
   - Frontend polls or uses websockets to update

4. **Selective Processing**: Only generate for most recent/relevant articles
   - Maybe only top 10 articles get AI treatment
   - Older cached articles keep existing insights

**Testing**:
```bash
# Benchmark API performance
time curl http://localhost:8000/api/news/market?max_results=10

# Should complete in <3 seconds
```

**Verification**:
- [ ] Market news API responds in <3 seconds
- [ ] AI insights are cached and reused
- [ ] No duplicate AI generation on page refresh

---

## 🧪 Task 7: Comprehensive Testing

**Goal**: Verify everything works end-to-end

### Backend Tests

```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate

# Run all news-related tests
pytest tests/unit/test_news_service.py -v
pytest tests/integration/test_news_api.py -v

# Run linting
~/portfolio-ai/scripts/lint.sh

# Check test coverage
pytest tests/ --cov=app --cov-report=term-missing
```

**Verification**:
- [ ] All tests pass
- [ ] No mypy errors
- [ ] No ruff errors
- [ ] Coverage remains >85%

### Frontend Tests

```bash
cd ~/portfolio-ai/frontend

# Type check
npm run type-check

# Component tests
npm test

# E2E tests (if applicable)
npm run test:e2e
```

**Verification**:
- [ ] No TypeScript errors
- [ ] Component tests pass
- [ ] No console errors in browser

### Manual Testing

1. **Market News Section**:
   - [ ] Loads without errors
   - [ ] Shows 10 articles by default
   - [ ] "Show All" button appears and works
   - [ ] Sentiment sorting works:
     - [ ] Recent: Articles in chronological order
     - [ ] Most Positive: Highest sentiment scores first
     - [ ] Most Negative: Lowest sentiment scores first
   - [ ] Plain language headlines appear (if generated)
   - [ ] Impact summaries appear (💡 in muted text)
   - [ ] Actionable insights appear (💡 in primary color)
   - [ ] External links work
   - [ ] Relative dates show correctly ("5 hours ago")

2. **Watchlist News Intelligence Section**:
   - [ ] Loads without errors
   - [ ] Shows 10 articles by default
   - [ ] "Show All" button appears and works
   - [ ] Sentiment sorting works (same as Market News)
   - [ ] AI insights display correctly
   - [ ] Visual layout matches Market News

3. **Visual Consistency**:
   - [ ] Both sections have identical article card layouts
   - [ ] Same text sizes and spacing
   - [ ] Same badge styles
   - [ ] Same metadata format (source · time · sentiment)
   - [ ] Same sorting controls

4. **Performance**:
   - [ ] Market news loads in <3 seconds
   - [ ] No lag when sorting
   - [ ] No lag when clicking "Show All"
   - [ ] Page doesn't freeze during AI generation

### Database Checks

```bash
# Check if AI insights are being stored
psql -U portfolio_ai_user -d portfolio_ai -c "
SELECT
  ticker,
  headline,
  plain_language_headline,
  impact_summary IS NOT NULL as has_impact,
  actionable_insight IS NOT NULL as has_insight,
  fetched_at
FROM news_cache
WHERE ticker = 'MARKET'
ORDER BY fetched_at DESC
LIMIT 5;
"
```

**Expected**: Recent market articles should have AI insights populated.

**Verification**:
- [ ] AI insights are stored in database
- [ ] Insights are reused on subsequent requests
- [ ] No duplicate entries

---

## 🔨 Task 8: Restart Services and Monitor

**Goal**: Ensure changes work in production-like environment

**Steps**:

1. Restart all services:
   ```bash
   bash ~/portfolio-ai/scripts/restart.sh
   ```

2. Verify service start times are AFTER code changes:
   ```bash
   systemctl show portfolio-backend -p ActiveEnterTimestamp
   systemctl show portfolio-frontend -p ActiveEnterTimestamp
   ```

3. Monitor logs for errors:
   ```bash
   tail -f /var/log/portfolio-ai/backend-error.log
   tail -f /var/log/portfolio-ai/celery-worker.log
   ```

4. Test in browser:
   - Navigate to `http://localhost:3000`
   - Open DevTools → Console (should be no errors)
   - Navigate to dashboard
   - Check Market News section
   - Check Watchlist News section

5. Monitor at least 2 scheduled task cycles for stability

**Verification**:
- [ ] Services restart successfully
- [ ] No errors in logs
- [ ] Frontend loads without console errors
- [ ] Market News displays correctly
- [ ] Watchlist News displays correctly
- [ ] No crashes or freezes over 30 minutes

---

## 🔨 Task 9: Create Pull Request

**Goal**: Prepare changes for review and merge

**Steps**:

1. Verify all commits are pushed:
   ```bash
   git status
   git log --oneline origin/main..HEAD
   ```

2. Create PR using GitHub CLI:
   ```bash
   gh pr create --title "feat: align Market News and Watchlist News sections with sentiment sorting" --body "$(cat <<'EOF'
## Summary
Aligned Market News and Watchlist News/Sentiment sections with shared formatting utilities, visual consistency, and sentiment sorting.

## Changes

### Frontend (Completed)
- Created shared `news-formatting.ts` utilities module
- Refactored 3 components to eliminate 140 lines of duplicate code
- Aligned visual layouts between sections
- Added sentiment sorting (Recent, Most Positive, Most Negative)
- Changed display from "6 → 20" to "10 → all" with "Show All" button
- Added support for plain language headlines

### Backend (This PR)
- Updated `NewsArticleResponse` model with AI insight fields
- Updated serialization to include `plain_language_headline`, `impact_summary`, `actionable_insight`
- Enabled AI feature generation for market news (not just watchlist)
- Added caching for AI insights
- Performance optimizations

## Testing
- [x] All backend tests pass (508 tests)
- [x] All frontend tests pass
- [x] No TypeScript errors
- [x] No linting errors
- [x] Manual testing on dashboard and watchlist
- [x] Performance testing (<3s for market news)
- [x] Visual consistency verified

## Screenshots
[Add screenshots of Market News and Watchlist News sections]

## Benefits
- Single source of truth for news formatting
- Consistent UX across sections
- AI insights improve user decision-making
- Better code maintainability
- ~140 lines of duplicate code eliminated

## Breaking Changes
None - all changes are additive

## Rollback Plan
If issues arise:
1. Revert merge commit
2. Services will fall back to not displaying AI insights
3. No data loss or corruption risk

EOF
)"
   ```

3. Link to original issue/task if applicable

**Verification**:
- [ ] PR created successfully
- [ ] PR description is complete
- [ ] Screenshots added
- [ ] All checks pass

---

## 🔨 Task 10: Documentation Updates

**Goal**: Keep documentation in sync with changes

**Files to update**:

1. **API Documentation** (`docs/core/API_REFERENCE.md`):
   - Add AI insight fields to news endpoint documentation
   - Update response examples

2. **Development Guide** (`docs/core/DEVELOPMENT.md`):
   - Add note about shared news utilities
   - Update component organization section

3. **Architecture** (`docs/core/ARCHITECTURE.md`):
   - Update news service architecture diagram (if exists)

4. **CHANGELOG** (if exists):
   - Add entry for this feature

**Verification**:
- [ ] API docs updated
- [ ] Dev docs updated
- [ ] Architecture docs updated (if applicable)
- [ ] CHANGELOG updated (if applicable)

---

## 📊 Success Criteria

**All tasks complete when**:

1. ✅ Backend returns AI insights for market news
2. ✅ Frontend displays AI insights in Market News section
3. ✅ Both sections have identical visual layouts
4. ✅ Sentiment sorting works in both sections
5. ✅ "Show All" functionality works
6. ✅ All tests pass (508+ tests)
7. ✅ No TypeScript/linting errors
8. ✅ Performance is acceptable (<3s for market news)
9. ✅ Services run stably for 2+ hours
10. ✅ Pull request is created and approved

---

## 🐛 Known Issues to Watch For

1. **LLM Rate Limits**: AI generation may hit rate limits with high traffic
   - Solution: Implement request queuing or background processing

2. **Cache Invalidation**: AI insights may become stale
   - Solution: Add TTL to cached insights, regenerate periodically

3. **TypeScript Errors**: Types may not match between frontend/backend
   - Solution: Keep types in sync, use code generation if possible

4. **Performance Degradation**: AI generation may slow down with scale
   - Solution: Move to background processing, increase cache TTL

---

## 📚 References

- **Frontend Changes**: Branch `claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
- **Backend Documentation**: `docs/future-enhancements/market-news-ai-features.md`
- **Watchlist Reference**: `backend/app/watchlist/watchlist_service.py` (lines 500-650)
- **AI Services**:
  - `backend/app/services/plain_language_news.py`
  - `backend/app/services/news_ai_features.py`
- **Shared Utilities**: `frontend/lib/utils/news-formatting.ts`
- **Component Examples**:
  - `frontend/components/dashboard/MarketNewsCard.tsx`
  - `frontend/components/watchlist/NewsIntelligenceCard.tsx`

---

## 🆘 Getting Help

If stuck on any task:

1. Check reference implementations in watchlist code
2. Review `docs/future-enhancements/market-news-ai-features.md`
3. Check commit history for context: `git log --oneline`
4. Review test files for examples: `backend/tests/integration/test_news_api.py`

---

**Estimated Total Time**: 8-11 hours
**Priority**: Medium
**Complexity**: Medium

Good luck! 🚀
