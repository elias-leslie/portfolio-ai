# Critical Issues Found - DO NOT MERGE YET

**Date**: 2025-11-08 (Updated after comprehensive browser automation review)
**Status**: 🔴 **BLOCKING ISSUES** - Need fixes before merge
**Branch**: claude/watchlist-vision-implementation-011CUw9W27dCwbxtwbECZsKT

**Comprehensive Review**: See `WATCHLIST-COMPREHENSIVE-REVIEW.md` for full analysis

---

## 🔴 CRITICAL ISSUES (Must Fix Before Merge)

### 1. **Missing Price Column Data**
**Issue**: No price information showing between Symbol and Signal columns
**Expected**: Price column with actual price + daily change % (e.g., "$172.50 +1.25%")
**Current**: Column appears to be missing or empty
**Fix Location**: `frontend/components/watchlist/WatchlistTable.tsx`
**Priority**: ⭐⭐⭐⭐⭐ CRITICAL

### 2. **Score Breakdown Shows Identical Data**
**Issue**: All stocks showing same scores (Price 37% / Technical 37%)
**Expected**: Each stock should have unique scores based on actual data
**Current**: Scores hardcoded or using same data source for all stocks
**Fix Location**: `frontend/components/watchlist/ExpandedRow.tsx`
**Root Cause**: Likely not pulling per-stock score data correctly
**Priority**: ⭐⭐⭐⭐⭐ CRITICAL

### 3. **Duplicate News Sections**
**Issue**: Two news sections in expanded row:
  - "News Intelligence"
  - "News & Sentiment"
**Design Reference**: `expanded_row_-_full_intelligence_view/screen.png` shows SINGLE "News Intelligence" section
**Expected**: One consolidated news section with headline + actionable insight
**Fix Location**: `frontend/components/watchlist/ExpandedRow.tsx`
**Priority**: ⭐⭐⭐⭐ HIGH

### 4. **Legacy Code in Settings**
**Issue**: "Legacy Score Weights (Deprecated)" section visible in settings panel
**Expected**: Only current weight sliders, no deprecated code
**Fix Location**: `frontend/components/settings/WatchlistPreferences.tsx`
**Action**: Remove deprecated section entirely
**Priority**: ⭐⭐⭐⭐ HIGH

### 5. **News Page Broken**
**Issue**: `/news` page stuck on "Loading..." infinitely
**Expected**: News articles should load
**Fix Location**: Check `frontend/app/news/page.tsx` and API endpoint
**Possible Causes**:
  - API endpoint not responding
  - Frontend query failing
  - Network timeout
**Priority**: ⭐⭐⭐⭐ HIGH

---

## 🔍 Investigation Needed

**Immediate Actions**:
1. Check `WatchlistTable.tsx` - verify Price column is rendering
2. Check `ExpandedRow.tsx` - verify scores pull from `item.current_score` not hardcoded
3. Check `ExpandedRow.tsx` - remove duplicate news section
4. Check `WatchlistPreferences.tsx` - remove deprecated section
5. Check `/api/news` endpoint - test if responding
6. Check browser console for errors (may have missed critical ones)

---

### Issue #6: Expanded Row Layout (OPTIONAL - Design Preference) ⚠️
**Issue**: Vertical stacking instead of 2-column landscape layout
**Expected**: 2-column grid (2/3 + 1/3 split) fitting in one screen
**Current**: Long vertical scroll through many sections
**Impact**: Poor information density, requires scrolling, not scannable
**Fix Location**: `frontend/components/watchlist/ExpandedRow.tsx` - Refactor to grid layout

---

## 📋 Files to Fix

### Priority 1: CRITICAL (Blocking Merge)
1. `frontend/components/watchlist/WatchlistTable.tsx` - Fix price column rendering
2. `frontend/components/watchlist/ExpandedRow.tsx` - Fix score breakdown (use per-stock data)
3. `frontend/components/watchlist/ExpandedRow.tsx` - Consolidate two news sections into one
4. `frontend/components/settings/WatchlistPreferences.tsx` - Remove "Legacy Score Weights (Deprecated)" section
5. `frontend/app/news/page.tsx` - Fix infinite loading issue

### Priority 2: Polish (Post-Merge OK)
6. `frontend/components/watchlist/ExpandedRow.tsx` - Consider 2-column layout (design preference)
7. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - Display actionable_insight field

---

## ⚠️ Status Update

**Initial Assessment**: ✅ APPROVED FOR MERGE
**After User Report**: 🔴 5 critical bugs found
**After Comprehensive Review**: 🔴 **MAJOR DEVIATIONS FROM DESIGN**

**Key Findings**:
- Backend implementation: **Excellent** (A+ grade)
- Main table UI: **Good** (B+ grade, minor styling differences)
- Expanded row UI: **Needs fixes** (data display + duplicate sections)
- Settings UI: **Acceptable** (centralized /settings page is fine)
- **Overall**: **B- grade** - Solid foundation, needs data fixes

**Actual Issues (Not Design Preferences)**:
- 5 critical data/display bugs that break functionality
- Settings location is fine (centralized is actually better)
- Layout preferences are optional polish work

---

## 🎯 Complete Fix Plan

**Total Estimated Time**: 8-12 hours (2 focused sessions)

---

### Session 1: Critical Bug Fixes (3-4 hours)

#### Phase 1A: Data Display Fixes (2 hours)
- Fix price column rendering in WatchlistTable.tsx
- Fix score breakdown to use per-stock data (not hardcoded)
- Remove "Legacy Score Weights (Deprecated)" section

#### Phase 1B: News Page Fix (0.5-1 hour)
- Debug why /news page stuck on "Loading..."
- Check API endpoint response
- Fix frontend query or add error handling

#### Phase 1C: Testing (0.5-1 hour)
- Verify all 3 critical issues resolved
- Test with multiple stocks
- User acceptance testing

---

### Session 2: News Intelligence Overhaul (5-8 hours)

**Goal**: Unified, LLM-ready news section with smart article ranking

#### Phase 2A: Database & Architecture (1-2 hours)
**Files**: `backend/migrations/`, `backend/app/services/`

1. **Add LLM tracking columns** to `news_cache`:
   ```sql
   ALTER TABLE news_cache ADD COLUMN llm_processed BOOLEAN DEFAULT FALSE;
   ALTER TABLE news_cache ADD COLUMN llm_processed_at TIMESTAMP;
   ALTER TABLE news_cache ADD COLUMN llm_model_name VARCHAR(50);
   ALTER TABLE news_cache ADD COLUMN quality_score FLOAT;
   ```

2. **Create abstract LLM translator interface**:
   - `backend/app/services/llm_translator.py`
   - Abstract base class: `LLMTranslator`
   - Implementations: `NoOpTranslator`, `ClaudeTranslator`, `LocalLLMTranslator`
   - Config-driven selection (ENV vars)

3. **Add ranking weights** to `user_preferences`:
   ```sql
   ALTER TABLE user_preferences
   ADD COLUMN news_sentiment_weight FLOAT DEFAULT 1.0,
   ADD COLUMN news_materiality_weight FLOAT DEFAULT 1.0,
   ADD COLUMN news_source_quality_weight FLOAT DEFAULT 1.0,
   ADD COLUMN news_recency_weight FLOAT DEFAULT 1.0,
   ADD COLUMN news_coverage_weight FLOAT DEFAULT 1.0;
   ```

#### Phase 2B: Article Quality Ranking (2-3 hours)
**Files**: `backend/app/services/news_ranker.py`

1. **Implement quality scoring algorithm**:
   - Sentiment strength (0-25 points)
   - Event materiality (0-30 points) - earnings > opinions
   - Source quality (0-20 points) - Bloomberg > blogs
   - Recency (0-15 points) - decay over time
   - Story coverage (0-10 points) - multiple sources boost
   - LLM processing bonus (0-5 points)

2. **Smart article selection**:
   - Diversity constraints (max 2 per story, max 3 per category)
   - Select best N articles from larger pool
   - Deduplication by normalized headline + summary + source

3. **User-tunable weights**:
   - Apply user preferences to scoring
   - Default weights: all 1.0x

#### Phase 2C: Unified News Section (2-3 hours)
**Files**: `frontend/components/watchlist/`

1. **Delete duplicate section**:
   - Remove `NewsIntelligenceCard.tsx` component
   - Keep only enhanced "News & Sentiment" section

2. **Build unified component** with:
   - **Collapsed view (default)**:
     - Top positive article (highest sentiment + quality)
     - Top negative article (lowest sentiment + quality)
     - Summary stats (sentiment, count, model coverage)
     - "Show all N articles" button

   - **Expanded view**:
     - All articles ranked by quality score
     - Collapsible stats section (FinBERT %, confidence, headline mix)
     - Each article shows:
       - Plain language headline (if LLM processed) OR original headline
       - "✨ AI Enhanced" badge when LLM processed
       - Source, timestamp, sentiment badge
       - Impact summary and actionable insight (if available)

3. **Deduplication display**:
   - Group similar articles
   - Show "X more sources" indicator
   - Expand to see all sources for same story

#### Phase 2D: Testing (1 hour)
- Test ranking with real data (verify quality > recency)
- Test collapsed/expanded states
- Test deduplication (same story, different sources)
- Test graceful degradation (no LLM = original headlines)
- Verify "✨ AI Enhanced" badge only on LLM-processed articles

---

### Future Enhancement: Add LLM (30 min setup, then automatic)

**When ready to enable Claude**:
```bash
# Add to .env
LLM_TRANSLATION_ENABLED=true
LLM_TRANSLATOR_TYPE=claude
ANTHROPIC_API_KEY=sk-ant-...
```

**When ready to try local LLM (Qwen/Llama)**:
```bash
# Add to .env
LLM_TRANSLATION_ENABLED=true
LLM_TRANSLATOR_TYPE=local
LLM_MODEL_NAME=Qwen/Qwen2.5-0.5B-Instruct
```

**Cost estimates**:
- Claude Haiku: ~$0.90/month
- Local model: $0/month (one-time 1GB download)

---

## 📋 Complete File List

### Session 1 Files (Bug Fixes)
1. `frontend/components/watchlist/WatchlistTable.tsx` - Fix price column
2. `frontend/components/watchlist/ExpandedRow.tsx` - Fix score breakdown
3. `frontend/components/settings/WatchlistPreferences.tsx` - Remove legacy section
4. `frontend/app/news/page.tsx` - Fix loading issue

### Session 2 Files (News Intelligence)

**Backend**:
1. `backend/migrations/0XX_news_intelligence_enhancements.sql` - New columns
2. `backend/app/services/llm_translator.py` - NEW: Abstract LLM interface
3. `backend/app/services/news_ranker.py` - NEW: Quality scoring & selection
4. `backend/app/services/news_translator.py` - NEW: Hybrid translation (patterns → LLM)
5. `backend/app/watchlist/watchlist_service.py` - Use new ranking system
6. `backend/app/config.py` - Add LLM settings

**Frontend**:
7. `frontend/components/watchlist/ExpandedRow.tsx` - Remove NewsIntelligenceCard, enhance News & Sentiment
8. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - DELETE this file
9. `frontend/components/settings/NewsPreferences.tsx` - NEW: Ranking weight sliders (optional)

**Tests**:
10. `backend/tests/unit/test_news_ranker.py` - NEW: Test quality scoring
11. `backend/tests/unit/test_llm_translator.py` - NEW: Test LLM abstraction
12. `backend/tests/unit/test_news_translator.py` - NEW: Test hybrid translation

---

## 🎯 Success Criteria

### Session 1 (Bug Fixes)
- ✅ Price column shows actual prices (not empty)
- ✅ Score breakdown unique per stock (not 37%/37% for all)
- ✅ Legacy section removed from settings
- ✅ News page loads articles (not stuck)
- ✅ All existing tests still pass

### Session 2 (News Intelligence)
- ✅ One unified news section (not two)
- ✅ Collapsed by default (top pos + top neg only)
- ✅ Articles ranked by quality (not just time)
- ✅ Best articles from larger pool (top 10 from 50+)
- ✅ Deduplication working (same story = 1 entry)
- ✅ LLM architecture ready (but disabled by default)
- ✅ Works without LLM (shows original headlines)
- ✅ "✨ AI Enhanced" badge when LLM processed
- ✅ All model coverage stats preserved
- ✅ New tests passing

---

**Note**: Settings location is FINE as-is (centralized /settings page). Layout changes (2-column expanded row) are optional polish work for future.

---

## 📖 Documentation

**Comprehensive Analysis**: `tasks/WATCHLIST-COMPREHENSIVE-REVIEW.md`
- 85% main table match
- 45% expanded row match
- 25% settings match
- Detailed comparison tables
- Grading breakdown
- Fix recommendations

**Previous Reviews**:
- `tasks/FINAL-REVIEW-RESULTS.md` - Initial optimistic assessment
- `tasks/IMPLEMENTATION-REVIEW.md` - Pre-testing checklist

---

**Context**: Fresh session
**Recommendation**: Fix 5 critical + 3 major issues before merge
