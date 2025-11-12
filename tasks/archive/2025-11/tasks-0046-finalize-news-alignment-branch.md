# Task List: Finalize News Alignment Branch

**Source**: Cloud agent work - claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U
**Complexity**: MEDIUM
**Effort**: MEDIUM-HIGH (8-11 hours)
**Environment**: Local Dev
**Created**: 2025-11-11
**Branch**: `claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
**Status**: Frontend complete (backend implementation needed)

---

## Summary

**Goal**: Complete backend AI insights for market news, align feature parity with watchlist news, and merge to main

**What's Already Done**:
- ✅ Frontend: Shared formatting utilities (eliminated 140 lines duplication)
- ✅ Frontend: Sentiment sorting (Recent, Most Positive, Most Negative)
- ✅ Frontend: "Show All" button (10 → all articles)
- ✅ Frontend: Visual alignment between Market News and Watchlist News
- ✅ Frontend: TypeScript interfaces updated for AI insights
- ✅ Documentation: Backend requirements documented
- ✅ 5 commits pushed to branch

**What's Left**:
- Update backend NewsArticleResponse model (add AI insight fields)
- Generate AI insights for market news (impact summaries, actionable insights)
- Test backend changes
- Verify frontend displays AI insights
- Merge to main

**Why Fourth**: Requires most new backend work (8-11 hours of development)

---

## Tasks

### 1.0 Load Branch and Review Work

- [ ] 1.1 Checkout branch
  - `git fetch origin`
  - `git checkout claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
  - `git pull origin claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
- [ ] 1.2 Read task documentation
  - `cat tasks/task-0040-complete-news-sentiment-alignment.md`
  - Read: `docs/future-enhancements/market-news-ai-features.md`
  - Understand: Frontend complete, backend work needed
- [ ] 1.3 Review frontend changes
  - `frontend/lib/utils/news-formatting.ts` - Shared utilities
  - `frontend/components/dashboard/MarketNewsCard.tsx` - Market news with sorting
  - `frontend/components/watchlist/NewsIntelligenceCard.tsx` - Watchlist news
  - Understand: What AI fields frontend expects

### 2.0 Test Frontend (Baseline)

- [ ] 2.1 Start services
  - `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify all services running
- [ ] 2.2 Test Market News section (dashboard)
  - Open: `http://192.168.8.233:3000`
  - Find: Market News section
  - Test: Sentiment sorting (Recent, Most Positive, Most Negative)
  - Test: "Show All" button
  - **Observe**: AI insights (impact summaries, actionable insights) NOT shown yet
- [ ] 2.3 Test Watchlist News section (for comparison)
  - Navigate: `http://192.168.8.233:3000/watchlist`
  - Expand: Any ticker row
  - Find: News Intelligence section
  - **Observe**: AI insights ARE shown (this is what market news should match)
- [ ] 2.4 Document baseline behavior
  - Market news: Shows headline, sentiment, source, timestamp
  - Watchlist news: Shows same PLUS impact summaries, actionable insights, plain language headlines
  - Goal: Add AI insights to market news

### 3.0 Update Backend NewsArticleResponse Model

**File**: `backend/app/api/news.py`

- [ ] 3.1 Add AI insight fields to NewsArticleResponse
  - Add field: `impact_summary: str | None = None` (1-2 sentence summary)
  - Add field: `actionable_insights: list[str] | None = None` (bulleted list)
  - Add field: `plain_language_headline: str | None = None` (simplified headline)
  - Add field: `key_topics: list[str] | None = None` (extracted topics)
  - Verify: Fields match what frontend expects (check news-formatting.ts)
- [ ] 3.2 Update serialization logic
  - Find: Where NewsArticle (DB model) → NewsArticleResponse (API)
  - Add: Mapping for new fields from DB columns
  - If DB columns don't exist yet: Return None for now (we'll generate them next)

### 4.0 Database Schema Check

- [ ] 4.1 Check if NewsArticle model has AI fields
  - File: `backend/app/models/news.py` (or wherever NewsArticle is defined)
  - Look for: `impact_summary`, `actionable_insights`, `plain_language_headline` columns
  - If NOT present: We need to add them
- [ ] 4.2 Create migration if needed
  - If columns missing: Create migration to add them
  - `backend/migrations/NNN_add_news_ai_fields.sql`:
    ```sql
    -- Add AI-generated insight fields to news_articles table
    ALTER TABLE news_articles
    ADD COLUMN IF NOT EXISTS impact_summary TEXT,
    ADD COLUMN IF NOT EXISTS actionable_insights TEXT[], -- Array of strings
    ADD COLUMN IF NOT EXISTS plain_language_headline TEXT,
    ADD COLUMN IF NOT EXISTS key_topics TEXT[];

    COMMENT ON COLUMN news_articles.impact_summary IS 'AI-generated 1-2 sentence impact summary';
    COMMENT ON COLUMN news_articles.actionable_insights IS 'AI-generated bulleted insights';
    COMMENT ON COLUMN news_articles.plain_language_headline IS 'AI-simplified headline';
    COMMENT ON COLUMN news_articles.key_topics IS 'AI-extracted key topics';
    ```
  - Run migration: `python backend/scripts/migrate.py`
  - Verify: `psql -U portfolio_ai_user -d portfolio_ai -c "\d news_articles"`
- [ ] 4.3 Update SQLAlchemy model
  - Add columns to NewsArticle model:
    ```python
    impact_summary = Column(Text, nullable=True)
    actionable_insights = Column(ARRAY(Text), nullable=True)
    plain_language_headline = Column(Text, nullable=True)
    key_topics = Column(ARRAY(Text), nullable=True)
    ```

### 5.0 Implement AI Insight Generation

**Goal**: Generate AI insights for market news articles (same as watchlist news)

- [ ] 5.1 Find existing AI insight generation logic
  - Look in: `backend/app/services/news_service.py` or similar
  - Find: Where watchlist news gets AI insights generated
  - Method likely: `generate_insights()` or `analyze_article()`
- [ ] 5.2 Create reusable insight generator
  - If not already modular: Extract into function
  - Input: NewsArticle (headline, summary, sentiment)
  - Output: impact_summary, actionable_insights, plain_language_headline, key_topics
  - Use: OpenAI/Claude API or existing FinBERT-based logic
- [ ] 5.3 Add insight generation to market news fetch
  - Find: Where market news is fetched (probably in news_service.py)
  - After: Articles fetched and sentiment analyzed
  - Call: generate_insights() for each article
  - Store: Generated insights in DB (impact_summary, actionable_insights, etc.)
- [ ] 5.4 Handle backfill for existing articles
  - Option A: Regenerate insights for recent articles (last 7 days)
  - Option B: Only generate for new articles going forward
  - Recommend: Option B for simplicity (old articles gradually age out)

### 6.0 Backend Testing

- [ ] 6.1 Test API response structure
  - `curl -s http://192.168.8.233:8000/api/news/market | jq '.[0]'`
  - Verify: Response includes new fields (impact_summary, actionable_insights, etc.)
  - Check: At least some articles have non-null values (newly fetched)
- [ ] 6.2 Test insight quality
  - Read: Several generated insights
  - Verify: Summaries are coherent and relevant
  - Check: Actionable insights are actually actionable
  - Verify: Plain language headlines are simpler than originals
- [ ] 6.3 Test with different article types
  - Positive sentiment article: Should have bullish insights
  - Negative sentiment article: Should have bearish/cautious insights
  - Neutral article: Should have balanced insights
- [ ] 6.4 Test performance
  - Time: How long to fetch and process 20 market articles
  - Target: <5 seconds for full fetch + AI generation
  - If slow: Consider caching or async processing

### 7.0 Frontend Verification

- [ ] 7.1 Reload Market News section
  - Navigate: `http://192.168.8.233:3000`
  - Find: Market News section
  - **Verify**: AI insights now displayed for market news
- [ ] 7.2 Compare Market News vs Watchlist News
  - Check: Both sections show impact summaries
  - Check: Both show actionable insights (bulleted)
  - Check: Both show plain language headlines
  - Verify: Visual alignment is identical (thanks to shared utilities)
- [ ] 7.3 Test sorting with AI insights
  - Sort: Most Positive
  - Verify: Articles sorted correctly, insights match sentiment
  - Sort: Most Negative
  - Verify: Bearish insights shown
- [ ] 7.4 Test "Show All"
  - Click: "Show All" button
  - Verify: All articles expand, all have insights
  - Check: Performance (no lag with 20+ articles)

### 8.0 Code Quality and Tests

- [ ] 8.1 Run backend tests
  - `cd ~/portfolio-ai/backend && source .venv/bin/activate`
  - `pytest tests/ -v --tb=short`
  - Fix: Any broken tests (API response structure changed)
  - Add: Tests for new insight generation logic
- [ ] 8.2 Run ruff linter
  - `ruff check backend/app/api/news.py backend/app/services/news_service.py`
  - Fix: Any style issues
- [ ] 8.3 Run mypy type checker
  - `mypy backend/app/api/news.py backend/app/services/news_service.py --strict`
  - Fix: Type errors for new fields
- [ ] 8.4 Check frontend TypeScript
  - Should already be clean (frontend committed earlier)
  - Verify: No new errors

### 9.0 Edge Cases and Error Handling

- [ ] 9.1 Test with AI generation failure
  - Simulate: API error when generating insights
  - Verify: Article still saved with null insights (graceful degradation)
  - Check: Error logged but doesn't crash service
- [ ] 9.2 Test with missing sentiment data
  - Article: No sentiment score
  - Verify: Insights still generated (or gracefully skipped)
  - Check: Frontend handles null insights
- [ ] 9.3 Test with very long articles
  - Article: 5000+ word summary
  - Verify: Insight generation handles truncation
  - Check: No token limit errors from AI API

### 10.0 Documentation

- [ ] 10.1 Update task-0040-complete-news-sentiment-alignment.md
  - Mark all backend tasks complete
  - Note any implementation differences from plan
  - Document final approach
- [ ] 10.2 Update market-news-ai-features.md
  - Mark features as implemented
  - Add: Usage examples
  - Note: Any future enhancements
- [ ] 10.3 Update API documentation
  - Document: New fields in NewsArticleResponse
  - Add: Example response with AI insights
  - Note: When insights are generated (on fetch vs backfill)

### 11.0 Merge to Main

- [ ] 11.1 Final verification
  - All tests passing
  - No linter/type errors
  - AI insights working for market news
  - Frontend displays correctly
  - Feature parity achieved
- [ ] 11.2 Rebase on main (if needed)
  - `git fetch origin main`
  - `git rebase origin/main`
  - Resolve conflicts (unlikely)
  - Push: `git push origin claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U --force-with-lease`
- [ ] 11.3 Create comprehensive merge commit
  - `git checkout main`
  - `git pull origin main`
  - `git merge claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U --no-ff -m "feat(news): align market news and watchlist news with AI insights and sentiment sorting

Frontend (Cloud Agent - Complete):
- Created shared formatting utilities (news-formatting.ts)
- Eliminated 140 lines of duplicate code across 3 components
- Added sentiment sorting (Recent, Most Positive, Most Negative)
- Changed display from 6→20 to 10→all with 'Show All' button
- Visual alignment between MarketNewsCard and NewsIntelligenceCard

Backend (Local Dev - Complete):
- Added AI insight fields to NewsArticleResponse model
- Database migration for impact_summary, actionable_insights, plain_language_headline, key_topics
- AI insight generation for market news (feature parity with watchlist news)
- Backend API now returns AI insights for market news

Result: Market news and watchlist news now have identical features and visual layouts

Files: 4 frontend files, 3 backend files, 1 migration, 2 docs"`
- [ ] 11.4 Push to remote
  - `git push origin main`
- [ ] 11.5 Verify services after merge
  - `bash ~/portfolio-ai/scripts/restart.sh`
  - Test: Market news shows AI insights
  - Test: Watchlist news still works
  - Smoke test: Dashboard and watchlist pages
- [ ] 11.6 Delete remote branch
  - `git push origin --delete claude/align-news-sentiment-sections-011CUyEXr4XhbdjWn7Xapb7U`
- [ ] 11.7 Update WORK_TRACKER.md
  - Move to Recently Completed
  - Celebrate: Feature parity achieved! 🎉

---

## Verification Checklist

- [ ] Backend model updated with AI insight fields
- [ ] Database migration successful (if needed)
- [ ] AI insight generation working
- [ ] Market news API returns insights
- [ ] Frontend displays AI insights for market news
- [ ] Feature parity: Market news = Watchlist news
- [ ] Sentiment sorting works in both sections
- [ ] "Show All" works in both sections
- [ ] Visual alignment identical
- [ ] Tests passing
- [ ] Ruff + mypy clean
- [ ] Branch merged to main
- [ ] No regressions

---

## Success Criteria

- ✅ Market news shows AI insights (impact summaries, actionable insights, plain language headlines)
- ✅ Feature parity between Market News and Watchlist News sections
- ✅ Sentiment sorting works in both sections
- ✅ Shared formatting utilities eliminate code duplication
- ✅ AI insight generation is fast and high-quality
- ✅ Tests passing, code quality checks pass
- ✅ Branch merged to main
- ✅ No regressions in existing functionality
