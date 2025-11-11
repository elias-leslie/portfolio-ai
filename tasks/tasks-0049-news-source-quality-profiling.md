# Task List: News Source Quality Profiling System (Phase 1)

**Source**: User request - Build automated source quality monitoring with profiling metrics, status card UI, dynamic weighting, and user-adjustable controls
**Complexity**: HIGH (multi-component system)
**Effort**: HIGH (5-6 hours)
**Environment**: Local Dev
**Created**: 2025-11-11

---

## Summary

**Goal**: Build foundation for intelligent news source quality monitoring and personalization

**Phase 1 Scope:**
- 6 core metrics (duplicate rate, diversity, confidence, freshness, user feedback, quality score)
- Celery profiling task (scheduled 6-12h + on-demand)
- Status card UI showing source health grid
- User controls: 4 weight sliders + neutral filter toggle + reset button
- Article feedback: 👍👎 buttons to train personalization
- NO auto-disable sources (user control), NO publisher tiers yet (Phase 2)

**Why Phase 1:**
- Solves 80% of value (quality detection, spam filtering, personalization)
- Ships fast to validate usage patterns
- Foundation for Phase 2 (auto-optimization, publisher tiers, historical accuracy)

---

## Tasks

### 0.0 Architecture Discovery (MANDATORY)

**Goal**: Understand existing news infrastructure before building profiling system

- [ ] 0.1 Map existing news service architecture
  - [ ] Read `backend/app/services/news_service.py` - understand NewsService, vendor manager, cache
  - [ ] Read `backend/app/services/news_vendor_manager.py` - how vendors are tracked, metadata stored
  - [ ] Read `/api/news/health` endpoint - what health data already exists
  - [ ] Grep for existing metrics: `grep -r "duplicate\|diversity\|confidence" backend/app/services/`
  - [ ] Document: What metrics already exist vs what we need to add

- [ ] 0.2 Identify database schema needs
  - [ ] Check if `source_metrics` table exists or needs creation
  - [ ] Check if `user_article_feedback` table exists (for 👍👎)
  - [ ] Check `user_preferences` for source weight preferences
  - [ ] Document: Schema additions needed

- [ ] 0.3 Review existing Celery tasks
  - [ ] Read `backend/app/tasks/news_tasks.py` - understand refresh patterns
  - [ ] Check Celery beat schedule - where to add profiling task
  - [ ] Document: Integration points for profiling task

- [ ] 0.4 Checkpoint: Confirm approach
  - [ ] Architecture understood
  - [ ] Database schema designed
  - [ ] Integration points identified
  - [ ] Effort estimate validated (5-6h)

**DO NOT PROCEED TO TASK 1 UNTIL CHECKPOINT COMPLETE**

---

### 1.0 Backend - Core Metrics Calculation

**Goal**: Implement 6 core quality metrics

- [ ] 1.1 Create metrics calculation module
  - [ ] Create `backend/app/services/news_quality_metrics.py`
  - [ ] Define `SourceMetrics` Pydantic model (all 6 metrics)
  - [ ] Define `QualityWeights` model (4 adjustable weights)

- [ ] 1.2 Implement duplicate rate calculation
  - [ ] Function: `calculate_duplicate_rate(source: str, articles: List[NewsArticle]) -> float`
  - [ ] Logic: Check content_hash matches across articles from same source
  - [ ] Return: 0.0-1.0 (% of articles that are duplicates)

- [ ] 1.3 Implement diversity score calculation
  - [ ] Function: `calculate_diversity_score(source: str, articles: List[NewsArticle]) -> float`
  - [ ] Logic: Compare headline similarity (fuzzy matching or embeddings)
  - [ ] Return: 0.0-1.0 (1.0 = all unique, 0.0 = all same)

- [ ] 1.4 Implement sentiment confidence calculation
  - [ ] Function: `calculate_avg_confidence(source: str, articles: List[NewsArticle]) -> float`
  - [ ] Logic: Average sentiment_confidence from FinBERT scores
  - [ ] Return: 0.0-1.0 (avg confidence)

- [ ] 1.5 Implement freshness score
  - [ ] Function: `calculate_freshness_score(source: str, articles: List[NewsArticle]) -> float`
  - [ ] Logic: Average article age (now - published_at), normalize to 0-1 (24h = 1.0, 7d = 0.0)
  - [ ] Return: 0.0-1.0 (1.0 = very fresh, 0.0 = stale)

- [ ] 1.6 Implement user useful rate
  - [ ] Function: `calculate_user_useful_rate(source: str, db: Connection) -> float`
  - [ ] Query: Get user feedback for source from DB
  - [ ] Return: 0.0-1.0 (thumbs_up / total_feedback), None if no feedback

- [ ] 1.7 Implement composite quality score
  - [ ] Function: `calculate_quality_score(metrics: SourceMetrics, weights: QualityWeights) -> float`
  - [ ] Formula: `(1-dup)*w1 + diversity*w2 + confidence*w3 + user_rate*w4`
  - [ ] Default weights: 0.30, 0.25, 0.20, 0.25

- [ ] 1.8 Write unit tests for all metrics
  - [ ] Test each metric function with mock data
  - [ ] Test edge cases (no articles, all dupes, no user feedback)
  - [ ] Test quality score calculation with various weights

---

### 2.0 Backend - Database Schema

**Goal**: Store metrics and user feedback persistently

- [ ] 2.1 Create `source_metrics` table migration
  - [ ] Schema: vendor, duplicate_rate, diversity_score, confidence_avg, freshness_score, user_useful_rate, quality_score, calculated_at, article_count
  - [ ] Indexes: vendor, calculated_at
  - [ ] Migration: `backend/app/storage/migrations/NNNN_add_source_metrics.sql`

- [ ] 2.2 Create `user_article_feedback` table migration
  - [ ] Schema: user_id, article_url, article_hash, vendor, is_useful (bool), created_at
  - [ ] Indexes: vendor, user_id, created_at
  - [ ] Migration: `backend/app/storage/migrations/NNNN_add_user_article_feedback.sql`

- [ ] 2.3 Add source weight preferences to user_preferences
  - [ ] Add columns: duplicate_penalty_weight (default 0.30), diversity_weight (0.25), confidence_weight (0.20), user_feedback_weight (0.25)
  - [ ] Add column: filter_neutral_articles (bool, default false)
  - [ ] Migration: `backend/app/storage/migrations/NNNN_add_source_quality_preferences.sql`

- [ ] 2.4 Run migrations and verify schema
  - [ ] Apply migrations to dev database
  - [ ] Verify tables created with correct schema
  - [ ] Seed test data for development

---

### 3.0 Backend - Profiling Celery Task

**Goal**: Scheduled + on-demand source quality analysis

- [ ] 3.1 Create profiling task
  - [ ] Create `backend/app/tasks/news_profiling_tasks.py`
  - [ ] Task: `@celery_app.task def profile_news_sources()`
  - [ ] Logic: Loop through all active sources, calculate metrics, store in DB

- [ ] 3.2 Implement profiling logic
  - [ ] Fetch last 24h articles per source
  - [ ] Calculate all 6 metrics using functions from Task 1
  - [ ] Store results in `source_metrics` table
  - [ ] Log summary (source: quality_score, warnings)

- [ ] 3.3 Add to Celery beat schedule
  - [ ] Add to `backend/app/celeryconfig.py` or equivalent
  - [ ] Schedule: Every 12 hours (configurable via preference)
  - [ ] Ensure doesn't conflict with news refresh tasks

- [ ] 3.4 Add on-demand trigger endpoint
  - [ ] Endpoint: `POST /api/news/profile-sources`
  - [ ] Triggers profiling task immediately
  - [ ] Returns: Task ID for monitoring

- [ ] 3.5 Add reset endpoint
  - [ ] Endpoint: `POST /api/news/reset-source-metrics`
  - [ ] Deletes all `source_metrics` records
  - [ ] Deletes all `user_article_feedback` records
  - [ ] Returns: Success message

- [ ] 3.6 Test profiling task
  - [ ] Run manually, verify metrics calculated
  - [ ] Verify DB records created correctly
  - [ ] Test with various article scenarios

---

### 4.0 Backend - User Feedback API

**Goal**: Allow users to flag articles as useful/not useful

- [ ] 4.1 Create feedback endpoint
  - [ ] Endpoint: `POST /api/news/article-feedback`
  - [ ] Body: `{article_url, article_hash, vendor, is_useful: bool}`
  - [ ] Logic: Insert into `user_article_feedback` table
  - [ ] Return: Success + updated useful rate for source

- [ ] 4.2 Create get feedback endpoint
  - [ ] Endpoint: `GET /api/news/article-feedback/{article_hash}`
  - [ ] Returns: User's previous feedback (if exists)
  - [ ] Used to show current state in UI (thumbs already clicked)

- [ ] 4.3 Add source stats endpoint
  - [ ] Endpoint: `GET /api/news/source-stats/{vendor}`
  - [ ] Returns: Latest metrics from `source_metrics` table
  - [ ] Returns: User's feedback count for this source

- [ ] 4.4 Test feedback flow
  - [ ] Submit feedback, verify DB insert
  - [ ] Query feedback, verify retrieval
  - [ ] Verify user_useful_rate recalculates on next profile

---

### 5.0 Backend - Source Quality Filtering

**Goal**: Apply quality scores to article selection

- [ ] 5.1 Update article selection logic
  - [ ] Modify `news_service.py` article selection
  - [ ] Add `apply_quality_weights()` method
  - [ ] Weight articles by source quality score when selecting top N

- [ ] 5.2 Add neutral article filtering
  - [ ] Read `filter_neutral_articles` preference
  - [ ] If enabled, filter articles with -0.2 < sentiment < 0.2
  - [ ] Apply BEFORE balanced view selection (3 pos + 3 neg)

- [ ] 5.3 Test weighted selection
  - [ ] Verify high-quality sources prioritized
  - [ ] Verify neutral filtering works
  - [ ] Verify doesn't break when no metrics exist yet

---

### 6.0 Frontend - Status Card UI

**Goal**: Display source health grid on status page

- [ ] 6.1 Create source metrics component
  - [ ] Component: `frontend/components/status/SourceQualityCard.tsx`
  - [ ] Fetch: `GET /api/news/source-stats` (all sources)
  - [ ] Display: Grid of sources with quality scores

- [ ] 6.2 Design status card layout
  - [ ] Header: "News Source Quality" + "Analyze Now" + "Reset" buttons
  - [ ] Grid: Source name, Quality score (0-100%), 6 metrics as mini-bars
  - [ ] Color code: Green (>80%), Yellow (60-80%), Red (<60%)
  - [ ] Show user feedback count: "15 articles rated"

- [ ] 6.3 Add analyze and reset buttons
  - [ ] "Analyze Now" → POST /api/news/profile-sources → Show spinner → Refresh on complete
  - [ ] "Reset Scores" → Confirm dialog → POST /api/news/reset-source-metrics → Refresh

- [ ] 6.4 Add to status page
  - [ ] Import component in `frontend/app/status/page.tsx`
  - [ ] Place below existing status cards
  - [ ] Ensure responsive layout

---

### 7.0 Frontend - User Feedback Buttons

**Goal**: Add 👍👎 buttons to each article

- [ ] 7.1 Add feedback buttons to article cards
  - [ ] Update `UnifiedNewsIntelligenceCard.tsx`
  - [ ] Add thumbs up/down buttons to each article
  - [ ] Fetch existing feedback on load (show which thumb is active)

- [ ] 7.2 Implement feedback submission
  - [ ] onClick → POST /api/news/article-feedback
  - [ ] Update UI immediately (optimistic update)
  - [ ] Show toast: "Feedback saved - helps improve source quality"

- [ ] 7.3 Add feedback indicator
  - [ ] Small counter: "You've rated 15/45 articles"
  - [ ] Tooltip: "Rate articles to improve source quality scores"

- [ ] 7.4 Test feedback flow
  - [ ] Click thumbs, verify API call
  - [ ] Verify state persists on page reload
  - [ ] Verify updates source stats

---

### 8.0 Frontend - Settings Sliders

**Goal**: User-adjustable quality weight sliders

- [ ] 8.1 Add quality settings section
  - [ ] Update `frontend/app/settings/page.tsx`
  - [ ] Section: "News Source Quality"
  - [ ] 4 sliders + neutral filter toggle

- [ ] 8.2 Create weight sliders
  - [ ] Slider 1: Duplicate Penalty (0-100%, default 30%)
  - [ ] Slider 2: Diversity Weight (0-100%, default 25%)
  - [ ] Slider 3: Confidence Weight (0-100%, default 20%)
  - [ ] Slider 4: User Feedback Weight (0-100%, default 25%)
  - [ ] Show: Total = 100% (normalize on save)

- [ ] 8.3 Add neutral article filter toggle
  - [ ] Toggle: "Hide neutral articles (sentiment between ±0.2)"
  - [ ] Description: "Show only clear positive/negative signals"

- [ ] 8.4 Save preferences
  - [ ] Update `PATCH /api/preferences` endpoint to accept new fields
  - [ ] Save weights to `user_preferences` table
  - [ ] Show success toast

- [ ] 8.5 Test settings flow
  - [ ] Adjust sliders, verify save
  - [ ] Verify weights apply to article selection
  - [ ] Verify neutral filter works

---

### 9.0 Integration Testing

**Goal**: End-to-end verification of profiling system

- [ ] 9.1 Test scheduled profiling
  - [ ] Trigger profiling task manually
  - [ ] Verify metrics calculated for all sources
  - [ ] Verify DB records created
  - [ ] Check logs for errors

- [ ] 9.2 Test user feedback loop
  - [ ] Rate 10+ articles (mix of useful/not useful)
  - [ ] Trigger profiling
  - [ ] Verify user_useful_rate updates
  - [ ] Verify quality score changes

- [ ] 9.3 Test weight adjustments
  - [ ] Change weight sliders
  - [ ] Trigger profiling
  - [ ] Verify quality scores recalculate
  - [ ] Verify article selection changes

- [ ] 9.4 Test neutral filtering
  - [ ] Enable neutral filter
  - [ ] Verify neutral articles hidden
  - [ ] Verify balanced view still shows 3 pos + 3 neg (from non-neutral pool)

- [ ] 9.5 Test reset functionality
  - [ ] Click reset, confirm
  - [ ] Verify all metrics cleared
  - [ ] Verify feedback cleared
  - [ ] Verify starts fresh on next profile

- [ ] 9.6 Visual verification
  - [ ] Screenshot status card with quality scores
  - [ ] Screenshot article with feedback buttons
  - [ ] Screenshot settings with sliders
  - [ ] Verify UI matches design intent

---

### 10.0 Documentation and Cleanup

**Goal**: Document profiling system for future reference

- [ ] 10.1 Update API documentation
  - [ ] Document new endpoints in API_REFERENCE.md
  - [ ] Include request/response examples
  - [ ] Document profiling schedule

- [ ] 10.2 Add user guide
  - [ ] How to interpret quality scores
  - [ ] What each metric means
  - [ ] How to adjust weights for your preferences
  - [ ] When to use reset button

- [ ] 10.3 Code cleanup
  - [ ] Remove debug logging
  - [ ] Add type hints to all functions
  - [ ] Run linting: `~/portfolio-ai/scripts/lint.sh`
  - [ ] Ensure all tests pass

- [ ] 10.4 Update WORK_TRACKER.md
  - [ ] Move task to "Recently Completed"
  - [ ] Document: Metrics implemented, UI locations
  - [ ] Note: Phase 2 ideas (publisher tiers, auto-optimization)

---

## Verification Checklist

**Functional:**
- [ ] Profiling task runs on schedule (12h) and on-demand
- [ ] All 6 metrics calculate correctly
- [ ] User feedback saves and updates quality scores
- [ ] Weight sliders affect article selection
- [ ] Neutral filter hides neutral articles
- [ ] Reset button clears all metrics
- [ ] Status card shows all sources with color coding

**Quality:**
- [ ] Backend: mypy --strict passes, ruff clean
- [ ] Frontend: TypeScript compiles, no warnings
- [ ] Tests: Unit tests for all metric functions
- [ ] Performance: Profiling task completes <30 seconds

**UX:**
- [ ] Status card loads quickly (<1s)
- [ ] Feedback buttons respond immediately
- [ ] Sliders save without page refresh
- [ ] Clear labels and tooltips throughout

---

## Phase 2 Ideas (Future)

**After validating Phase 1 usage:**
- Publisher quality tiers (based on user feedback patterns)
- Auto-optimization toggle (auto-adjust weights)
- Sentiment magnitude tracking
- Historical accuracy (sentiment → price correlation)
- Source uptime monitoring (once temporary failures understood)
- Advanced diversity (topic clustering, not just headline matching)

**Decision point:** Build Phase 2 only if user actively uses Phase 1 features (checks status card, adjusts sliders, rates articles)

---

**Estimated Effort**: 5-6 hours
**Dependencies**: None (builds on existing news infrastructure)
**Risk Level**: Low (additive features, no breaking changes)
