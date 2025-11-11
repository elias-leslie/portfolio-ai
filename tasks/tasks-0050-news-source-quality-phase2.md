# Task List: News Source Quality Profiling System (Phase 2)

**Source**: Phase 1 completion - User controls and quality-based filtering
**Complexity**: MEDIUM (3 UI components + quality-based selection logic)
**Effort**: MEDIUM (3.5-4 hours)
**Environment**: Local Dev
**Created**: 2025-11-11
**Updated**: 2025-11-11 (removed historical tracking & tier classification)
**Depends on**: Phase 1 ✅ COMPLETE

---

## Summary

**Goal**: Make article feedback actually affect what users see - not just data collection

**Phase 2 Scope:**
- 👍👎 Article feedback buttons that TRAIN the model (affects future article selection)
- ⚖️ Settings weight sliders (adjust quality formula: duplicate/diversity/confidence/freshness/feedback)
- 🎯 Neutral article filter toggle (hide articles with sentiment ±0.2)
- 🔍 **Quality-based article ranking** (de-prioritize low-quality vendors based on feedback)

**NOT in Phase 2** (removed as low-value):
- ❌ Historical metrics tracking (need months of data, not actionable yet)
- ❌ Publisher tier classification (redundant with existing quality badges)

**Why This Matters:**
- Phase 1 built the infrastructure but doesn't USE quality scores yet
- Feedback must CHANGE what articles appear, not just collect data
- De-prioritize vendors when user dislikes their articles
- Boost vendors when user likes their articles

---

## Tasks

### Task 1: Article Feedback Buttons (Full Implementation) (1.5 hours)

**Goal**: Thumbs up/down affects future article selection from that vendor

**Backend Changes:**
- [x] 1.1 API endpoints already exist (Phase 1)
  - POST `/api/news/article-feedback` - saves feedback ✅
  - GET `/api/news/article-feedback/{hash}` - retrieves feedback ✅
  - Backend calculates `user_useful_rate` per vendor ✅

- [ ] 1.2 Verify feedback updates quality scores
  - [ ] Test: Submit feedback → trigger profiling → verify quality_score changes
  - [ ] Quality score formula already includes user_useful_rate (weighted 10%)
  - [ ] Confirm: More thumbs down → lower quality_score for that vendor

**Frontend Changes:**
- [ ] 1.3 Add feedback buttons to `UnifiedNewsIntelligenceCard.tsx`
  - [ ] Location: Below each article, next to vendor name
  - [ ] Icons: ThumbsUp/ThumbsDown from lucide-react
  - [ ] States: Default (gray), Active (green/red), Disabled (loading)
  - [ ] Click handler: POST to `/api/news/article-feedback`

- [ ] 1.4 Load existing feedback on mount
  - [ ] For each article: GET `/api/news/article-feedback/{hash}`
  - [ ] Highlight already-rated articles
  - [ ] Show count: "You've rated X articles from {vendor}"

- [ ] 1.5 Visual feedback
  - [ ] Optimistic update (instant UI change)
  - [ ] Toast notification: "Feedback saved - {vendor} useful rate now X%"
  - [ ] Disable buttons after rating (prevent double-voting)

**Testing:**
```bash
# 1. Click thumbs down on polygon article
# 2. Verify: POST succeeds, button turns red
# 3. Check database:
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT vendor, is_useful FROM user_article_feedback ORDER BY created_at DESC LIMIT 5;"

# 4. Trigger profiling:
curl -X POST http://localhost:8000/api/news/profile-sources

# 5. Wait 5 seconds, check quality score decreased:
curl http://localhost:8000/api/news/source-stats/polygon | jq '.quality_score, .user_useful_rate'
```

---

### Task 2: Quality-Based Article Ranking (1.5 hours)

**Goal**: Use quality scores to prioritize high-quality vendors in article selection

**CRITICAL**: This is the missing piece that makes feedback actionable!

**Backend Changes:**
- [ ] 2.1 Modify `NewsService._select_articles_for_ticker()` to use quality scores
  - [ ] Currently: Random/time-based selection from all vendors
  - [ ] New: Weight selection by quality_score
  - [ ] Algorithm:
    ```python
    # Load latest quality scores for all vendors
    quality_map = _load_vendor_quality_scores()

    # Weight articles by vendor quality
    # quality_score=0.95 → 95% chance to include
    # quality_score=0.60 → 60% chance to include
    for article in all_articles:
        vendor = article['vendor']
        quality = quality_map.get(vendor, 0.70)  # Default 0.70 if no score
        if random.random() < quality:
            selected_articles.append(article)
    ```

- [ ] 2.2 Add `_load_vendor_quality_scores()` helper
  - [ ] Query: Latest quality_score per vendor from source_metrics
  - [ ] Cache for 1 hour (quality doesn't change rapidly)
  - [ ] Return: Dict[vendor, quality_score]

- [ ] 2.3 Update article selection to respect quality weights
  - [ ] Apply weighting BEFORE balanced view selection
  - [ ] Still maintain 3 positive + 3 negative balance
  - [ ] Log: "Selected X/{total} articles (quality-weighted)"

**Algorithm Example:**
```python
def _select_articles_for_ticker(self, articles: list, max_articles: int) -> list:
    """Select articles using quality-based weighting."""
    # Load vendor quality scores (cached)
    quality_scores = self._load_vendor_quality_scores()

    # Weight each article by vendor quality
    weighted_articles = []
    for article in articles:
        vendor = article.get('vendor', 'unknown')
        quality = quality_scores.get(vendor, 0.70)  # Default if no profiling yet

        # Higher quality = higher probability of inclusion
        if random.random() < quality:
            weighted_articles.append(article)

    # If too few articles after weighting, add more (ensure min 6)
    if len(weighted_articles) < 6:
        remaining = [a for a in articles if a not in weighted_articles]
        weighted_articles.extend(remaining[:6 - len(weighted_articles)])

    # Apply balanced view (3 positive + 3 negative)
    return self._apply_balanced_view(weighted_articles, max_articles)
```

**Testing:**
```bash
# 1. Rate polygon articles as "not useful" (thumbs down) 5 times
# 2. Rate finnhub articles as "useful" (thumbs up) 5 times
# 3. Trigger profiling (updates quality scores)
# 4. Refresh watchlist news
# 5. Verify: More finnhub articles, fewer polygon articles
# 6. Check logs for: "Selected X/{total} articles (quality-weighted)"
```

---

### Task 3: Settings Weight Sliders (1 hour)

**Goal**: User adjusts quality formula weights in real-time

**Frontend Changes:**
- [ ] 3.1 Create `SourceQualityWeights.tsx` component
  - [ ] 5 sliders with labels:
    - Duplicate Penalty (default 30%)
    - Diversity Score (default 25%)
    - Confidence Average (default 20%)
    - Freshness Score (default 15%)
    - User Feedback (default 10%)
  - [ ] Auto-normalize to 100% on change
  - [ ] Show preview: "New quality scores will be calculated on next profiling run"

- [ ] 3.2 Add to settings page under "News Preferences"
  - [ ] Section header: "News Source Quality Weights"
  - [ ] Description: "Adjust how quality scores are calculated. Higher weight = more important."
  - [ ] "Reset to Defaults" button

- [ ] 3.3 Save preferences
  - [ ] PATCH `/api/preferences` with new weights
  - [ ] Update columns: source_duplicate_weight, source_diversity_weight, etc.
  - [ ] Toast: "Weights saved. Trigger profiling to recalculate quality scores."

**Backend Changes:**
- [x] 3.4 Preferences columns already exist (Phase 1) ✅
- [x] 3.5 `load_quality_weights_from_preferences()` already implemented ✅
- [ ] 3.6 Verify profiling task uses user weights
  - [ ] Check: `profile_news_sources_task` loads preferences
  - [ ] Confirm: Quality scores recalculated with new weights

**Testing:**
```bash
# 1. Adjust sliders (e.g., User Feedback to 50%, Duplicate Penalty to 10%)
# 2. Save preferences
# 3. Trigger profiling: curl -X POST http://localhost:8000/api/news/profile-sources
# 4. Wait 5 seconds
# 5. Check quality scores changed based on new weights:
curl http://localhost:8000/api/news/source-stats | jq '.[] | "\(.vendor): \(.quality_score)"'
```

---

### Task 4: Neutral Article Filtering (0.5 hours)

**Goal**: Hide neutral articles (sentiment ±0.2) with a settings toggle

**Backend Changes:**
- [ ] 4.1 Update `NewsService.get_ticker_news()` to respect filter
  - [ ] Load `user_preferences.filter_neutral_articles`
  - [ ] Filter: `article['sentiment'] < -0.2 OR article['sentiment'] > 0.2`
  - [ ] Apply BEFORE quality weighting and balanced view selection
  - [ ] Log: "Filtered X neutral articles (threshold: ±0.2)"

- [ ] 4.2 Update `/api/news/ticker/{symbol}` endpoint
  - [ ] Load filter preference from database
  - [ ] Pass to NewsService

**Frontend Changes:**
- [ ] 4.3 Add toggle to settings page
  - [ ] Label: "Hide Neutral Articles"
  - [ ] Description: "Only show articles with clear sentiment (±0.2 threshold)"
  - [ ] Checkbox component with save to preferences
  - [ ] Default: OFF (show all articles)

**Testing:**
```bash
# 1. Enable "Hide Neutral Articles" in settings
# 2. Refresh watchlist news
# 3. Check: All articles have sentiment < -0.2 or > 0.2
# 4. Backend logs: "Filtered X neutral articles"
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM news_cache WHERE sentiment_score BETWEEN -0.2 AND 0.2;"
```

---

## Verification Checklist

**Functional:**
- [ ] Article feedback buttons work (POST succeeds, database updated)
- [ ] Feedback affects quality scores (thumbs down → lower score)
- [ ] Quality scores affect article selection (low-quality vendors de-prioritized)
- [ ] Settings sliders adjust quality formula (save + profiling = new scores)
- [ ] Neutral filter hides ±0.2 sentiment articles

**Quality:**
- [ ] All 535+ tests still passing
- [ ] Zero linting errors (ruff, mypy --strict)
- [ ] Files under 500 lines (soft limit)

**UX:**
- [ ] Feedback buttons respond immediately (<100ms optimistic update)
- [ ] Sliders save without page refresh
- [ ] Filter applies on next news refresh
- [ ] Toast notifications confirm actions

---

## Success Criteria

✅ **Feedback Loop Complete**:
- User thumbs down polygon article
- Quality score decreases for polygon
- Future article selection includes fewer polygon articles
- User sees immediate impact of their feedback

✅ **User Control**:
- Settings sliders change quality formula
- Neutral filter reduces noise
- Both affect what articles appear

✅ **No Mock/Fake/Temp Code**:
- Real database writes
- Real quality score calculations
- Real article selection changes

---

## Key Changes from Original Phase 2

**Removed (low value):**
- ❌ Historical metrics tracking (need months of data first)
- ❌ Publisher tier classification (redundant with badges)

**Added (critical for functionality):**
- ✅ Task 2: Quality-based article ranking (makes feedback actionable!)
- ✅ Emphasis on "training the model" not just data collection
- ✅ Verification that feedback CHANGES what user sees

**Time Saved:** 1.5 hours (5h → 3.5h)
**Value Increased:** Feedback now affects user experience immediately

---

**Estimated Effort**: 3.5-4 hours
**Dependencies**: Phase 1 complete (database, API, metrics engine)
**Risk Level**: Low (all infrastructure exists, just connecting the pieces)
