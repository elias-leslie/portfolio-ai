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

### Task 0: Discover Best Approach for Feedback-Based Ranking (MANDATORY) (0.5 hours)

**Goal**: Research and choose the RIGHT approach for using feedback to affect article selection

**CRITICAL**: Don't just implement something - discover what actually works and is maintainable!

**Options to Evaluate:**

**Option A: Vendor-Level Reputation Scores** (Simple)
- What it is: Aggregate feedback per vendor (user_useful_rate), use to weight article selection
- How it works:
  - Polygon: 20 thumbs up, 5 thumbs down = 80% useful rate
  - Article selection: if random.random() < 0.80: include polygon articles
- Pros: Simple weighted average, no ML dependencies, maintainable by any dev
- Cons: Doesn't learn article-level patterns (headline style, topic, author), only vendor reputation
- Is it "training"? Barely - it's just counting likes/dislikes per vendor
- Good enough? Maybe - if vendor is primary signal of quality

**Option B: ML Article Classifier** (Real Training)
- What it is: Train sklearn model to predict "will user find this useful?" per article
- Features: vendor, sentiment_score, headline_keywords, article_length, time_of_day, author, topic
- Model: LogisticRegression or RandomForestClassifier (scikit-learn)
- How it works:
  - Collect training data: (article_features, is_useful) from user_article_feedback
  - Train model: clf.fit(features, labels)
  - Predict: usefulness_score = clf.predict_proba(article_features)
  - Rank articles by usefulness_score
- Pros: ACTUALLY learns patterns, can discover "user likes negative sentiment on TSLA but positive on AAPL"
- Cons: Requires sklearn, training pipeline, model versioning, retraining schedule, more complexity
- Is it "training"? YES - real machine learning
- Supportable? Medium - needs someone who understands ML to maintain
- Needs: >100 feedback samples to train reliably

**Option C: Hybrid Progressive** (Start Simple, Add ML Later)
- Phase 2a: Vendor-level scores (ship fast, works now)
- Phase 2b: Add ML classifier when proven useful (>500 feedback samples collected)
- Pros: Progressive enhancement, don't over-engineer before validating engagement
- Cons: Eventually maintaining two systems (or migrating)

**Research Tasks:**
- [ ] 0.1 Check existing codebase for ML infrastructure
  - [ ] Search for: sklearn, joblib, model training, feature engineering
  - [ ] Check: Do we already train models anywhere? (technical analysis? sentiment?)
  - [ ] Result: Can we reuse existing patterns or starting from scratch?

- [ ] 0.2 Estimate data requirements for Option B
  - [ ] Check: How many user_article_feedback rows exist?
  - [ ] Calculate: Need ~100 samples minimum for binary classifier
  - [ ] Decision: Do we have enough data NOW or need to collect first?

- [ ] 0.3 Evaluate complexity vs value
  - [ ] Option A: 1 hour implementation, works immediately, limited learning
  - [ ] Option B: 3 hours implementation, needs data collection period, real learning
  - [ ] Option C: 1 hour now + 2 hours later, staged approach

- [ ] 0.4 Checkpoint - Present findings and get user decision
  - [ ] Summary: "Found X existing ML infrastructure, Y feedback samples"
  - [ ] Recommendation: "Option [A/B/C] because [reason]"
  - [ ] User confirms approach before implementing

**Verification:**
```bash
# Check for ML infrastructure
cd ~/portfolio-ai/backend
grep -r "sklearn\|joblib\|RandomForest\|LogisticRegression" app/ --include="*.py" | head -10

# Check feedback data volume
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM user_article_feedback;"

# Check if we already train models
find app/ -name "*train*" -o -name "*model*" | grep -v __pycache__
```

**Decision Criteria:**

Use **Option A** if:
- ✅ No existing ML infrastructure
- ✅ <100 feedback samples
- ✅ Want to ship fast and validate engagement first
- ✅ Primary quality signal IS vendor reputation

Use **Option B** if:
- ✅ Already have sklearn in dependencies
- ✅ >100 feedback samples or willing to collect first
- ✅ Want article-level personalization (not just vendor)
- ✅ Have ML expertise on team

Use **Option C** if:
- ✅ Uncertain about engagement levels
- ✅ Want to validate before investing in ML
- ✅ Prefer iterative approach

---

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

### Task 2: Implement Chosen Approach (1.5 hours)

**Goal**: Implement the approach chosen in Task 0 - NOT DECIDED YET!

**CRITICAL**: This is the missing piece that makes feedback actionable!

**Implementation depends on Task 0 decision:**

---

#### If Option A Chosen: Vendor-Level Reputation Scoring

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

**Testing (Option A):**
```bash
# 1. Rate polygon articles as "not useful" (thumbs down) 5 times
# 2. Rate finnhub articles as "useful" (thumbs up) 5 times
# 3. Trigger profiling (updates quality scores)
# 4. Refresh watchlist news
# 5. Verify: More finnhub articles, fewer polygon articles
# 6. Check logs for: "Selected X/{total} articles (quality-weighted)"
```

---

#### If Option B Chosen: ML Article Classifier

**Backend Changes:**
- [ ] 2.1 Create `app/ml/article_classifier.py` module
  - [ ] Feature extraction: extract_features(article) → dict
  - [ ] Features: vendor (one-hot), sentiment_score, headline_length, time_of_day, article_age
  - [ ] Training: train_classifier(feedback_data) → trained model
  - [ ] Prediction: predict_usefulness(article) → float [0-1]

- [ ] 2.2 Add training pipeline
  - [ ] Query user_article_feedback for training data
  - [ ] Split: 80% train, 20% test
  - [ ] Train: RandomForestClassifier or LogisticRegression
  - [ ] Save model: joblib.dump(model, 'models/article_classifier.joblib')
  - [ ] Log metrics: accuracy, precision, recall

- [ ] 2.3 Integrate predictions into article selection
  - [ ] Load trained model on startup
  - [ ] For each article: usefulness_score = model.predict_proba(features)[1]
  - [ ] Rank articles by usefulness_score
  - [ ] Select top N after ranking

- [ ] 2.4 Add retraining schedule
  - [ ] Celery task: retrain model weekly or when >50 new feedback samples
  - [ ] Monitor: Model performance degrades? Retrain more frequently

**Testing (Option B):**
```bash
# 1. Collect 100+ feedback samples (thumbs up/down)
# 2. Train initial model: python -m app.ml.article_classifier train
# 3. Check model metrics: accuracy >70%, precision >65%
# 4. Refresh news - verify articles ranked by usefulness
# 5. Continue collecting feedback
# 6. Retrain after 1 week - verify accuracy improves
```

---

#### If Option C Chosen: Hybrid Progressive

**Phase 2a: Implement Option A** (vendor-level, 1 hour)
- See Option A implementation above
- Ship this immediately to validate engagement

**Phase 2b: Upgrade to Option B** (ML classifier, 2 hours later)
- Implement when >500 feedback samples collected
- Migrate from vendor-level to article-level predictions
- Gradual rollout: 10% → 50% → 100% of users

**Testing (Option C):**
```bash
# Week 1: Ship Option A, monitor engagement
# Week 2-4: Collect 500+ feedback samples
# Week 5: Implement Option B upgrade if engagement validates
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
