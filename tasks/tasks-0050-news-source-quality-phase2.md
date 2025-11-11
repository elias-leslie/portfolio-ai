# Task List: News Source Quality Profiling System (Phase 2)

**Source**: Phase 1 completion - User controls and filtering enhancements
**Complexity**: MEDIUM (5 UI components + backend filtering)
**Effort**: MEDIUM (4-5 hours)
**Environment**: Local Dev
**Created**: 2025-11-11
**Depends on**: Phase 1 ✅ COMPLETE

---

## Summary

**Goal**: Add user-facing controls for news source quality personalization

**Phase 2 Scope:**
- 👍👎 Article feedback buttons in news cards (train quality model)
- ⚖️ Settings weight sliders (adjust quality formula: duplicate/diversity/confidence/freshness/feedback)
- 🎯 Neutral article filter toggle (hide articles with sentiment ±0.2)
- 📈 Historical metrics tracking (time-series charts for vendor quality)
- 🏆 Publisher tier classification (A/B/C rating based on consistent quality)

**Why Phase 2:**
- Phase 1 provides infrastructure & data collection
- Phase 2 adds user control & personalization
- Validates user engagement with quality features before advanced ML

---

## Tasks

### Task 1: Article Feedback Buttons (1 hour)

**Goal**: Add 👍👎 buttons to article cards for user feedback

**UI Changes:**
- [ ] 1.1 Add feedback buttons to `UnifiedNewsIntelligenceCard.tsx`
  - [ ] Buttons: Thumbs up (useful) / Thumbs down (not useful)
  - [ ] Show count of user's feedback per vendor
  - [ ] Visual feedback on click (button highlight)
  - [ ] POST to `/api/news/article-feedback` endpoint

- [ ] 1.2 Update article rendering to show feedback state
  - [ ] Check GET `/api/news/article-feedback/{hash}` on mount
  - [ ] Highlight already-rated articles
  - [ ] Show aggregate useful rate per vendor (tooltip)

**Verification:**
```bash
# Click thumbs up on article
# Verify: POST to /api/news/article-feedback succeeds
# Verify: Feedback persists (check database)
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT * FROM user_article_feedback;"
```

---

### Task 2: Settings Weight Sliders (1.5 hours)

**Goal**: Add sliders to adjust quality score weights in settings page

**UI Changes:**
- [ ] 2.1 Create `SourceQualitySettings.tsx` component
  - [ ] 5 sliders: Duplicate Penalty, Diversity, Confidence, Freshness, User Feedback
  - [ ] Default values: 30%, 25%, 20%, 15%, 10%
  - [ ] Auto-normalize to 100% (redistribute on change)
  - [ ] Save to user_preferences via PATCH `/api/preferences`

- [ ] 2.2 Add section to settings page
  - [ ] Place under "News Preferences" section
  - [ ] Show real-time quality score preview
  - [ ] "Reset to Defaults" button

- [ ] 2.3 Update backend to use preferences
  - [ ] Modify `load_quality_weights_from_preferences()` to read columns
  - [ ] Ensure profiling task uses user weights
  - [ ] Update quality scores when weights change

**Verification:**
```bash
# Adjust sliders, save
# Trigger profiling: curl -X POST http://localhost:8000/api/news/profile-sources
# Check updated quality scores reflect new weights
```

---

### Task 3: Neutral Article Filtering (1 hour)

**Goal**: Add toggle to hide neutral articles (sentiment ±0.2)

**Backend Changes:**
- [ ] 3.1 Update `NewsService.get_ticker_news()` to respect filter
  - [ ] Check `user_preferences.filter_neutral_articles`
  - [ ] Filter articles where `-0.2 < sentiment < 0.2`
  - [ ] Apply BEFORE balanced view selection (still show 3 pos + 3 neg)

- [ ] 3.2 Update `/api/news/ticker/{symbol}` endpoint
  - [ ] Load filter preference
  - [ ] Pass to NewsService

**Frontend Changes:**
- [ ] 3.3 Add toggle to settings page
  - [ ] "Hide Neutral Articles" checkbox
  - [ ] Tooltip: "Only show articles with clear sentiment (±0.2 threshold)"
  - [ ] Save to user_preferences

**Verification:**
```bash
# Enable filter in settings
# Check watchlist news - verify no neutral articles shown
# Backend: Verify filtered count logged
```

---

### Task 4: Historical Metrics Tracking (1 hour)

**Goal**: Add time-series tracking of vendor quality over time

**Backend Changes:**
- [ ] 4.1 Keep all `source_metrics` records (don't overwrite)
  - [ ] Current behavior: Profiling creates new row each run
  - [ ] Already correct! Just verify no cleanup job exists

- [ ] 4.2 Add `/api/news/source-stats/history/{vendor}` endpoint
  - [ ] Query: `SELECT * FROM source_metrics WHERE vendor = %s ORDER BY calculated_at`
  - [ ] Return: List of metrics ordered by time
  - [ ] Limit: Last 30 days

**Frontend Changes:**
- [ ] 4.3 Add time-series chart to `SourceQualityCard`
  - [ ] Click vendor → expand to show chart
  - [ ] Use recharts library (already in project)
  - [ ] Show quality score trend over time
  - [ ] Color-code: green=improving, red=degrading

**Verification:**
```bash
# Wait 24 hours for multiple profiling runs
# Or: Manually trigger profiling 3x with time.sleep(2) between
# Check chart shows trend line
```

---

### Task 5: Publisher Tier Classification (0.5 hours)

**Goal**: Add A/B/C tier badges based on consistent quality

**Backend Logic:**
- [ ] 5.1 Add tier calculation to `SourceMetrics`
  - [ ] Tier A: quality_score >= 0.90 AND article_count >= 50
  - [ ] Tier B: quality_score >= 0.75 AND article_count >= 20
  - [ ] Tier C: Everything else
  - [ ] Return tier in `/api/news/source-stats` response

**Frontend Changes:**
- [ ] 5.2 Add tier badge to `SourceQualityCard`
  - [ ] Display next to vendor name
  - [ ] Color-code: A=gold, B=silver, C=bronze
  - [ ] Tooltip: Explain tier criteria

**Verification:**
```bash
# Check status page - verify tier badges shown
# Polygon (148 articles, 96%) should be Tier A
# sec_edgar (0 articles) should be Tier C
```

---

## Verification Checklist

**Functional:**
- [ ] Article feedback buttons work, persist to database
- [ ] Settings sliders adjust quality scores
- [ ] Neutral filter hides ±0.2 sentiment articles
- [ ] Historical chart shows quality trend
- [ ] Tier badges display correctly

**Quality:**
- [ ] All 535+ tests still passing
- [ ] Zero linting errors (ruff, mypy --strict)
- [ ] Files under 500 lines (soft limit)

**UX:**
- [ ] Feedback buttons respond immediately (<100ms)
- [ ] Sliders save without page refresh
- [ ] Filter applies instantly
- [ ] Chart loads smoothly

---

## Success Criteria

- ✅ Users can rate articles as useful/not useful
- ✅ Quality formula adjustable via settings
- ✅ Neutral articles filterable
- ✅ Vendor quality trends visible over time
- ✅ Tier classification helps identify best sources

---

**Estimated Effort**: 4-5 hours
**Dependencies**: Phase 1 complete (database, API, metrics engine)
**Risk Level**: Low (all additive features, foundation exists)
