# Watchlist Page - Top 10 Priority Improvements

**Created**: 2025-11-08
**Based on**: Comprehensive review of tasks-0022, news-phase2, WORK_TRACKER, and codebase
**Status**: Ready for discussion and implementation

---

## Executive Summary

After reviewing all watchlist-related tasks and the current codebase, I've identified **10 high-priority improvements** grouped into 3 tiers. Many features have DB columns and backend code ready but are **not being calculated or displayed**.

**Key Finding**: Migration 009 completed (volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d columns exist) but **none are being calculated** - backend logic missing.

---

## ⭐ TIER 1: High User Value, Quick Wins (4-6 hours total)

### 1. **Priority Indicators in Main Table** 📋📈📰
**Effort**: MEDIUM (2-3 hours)
**User Value**: HIGH
**Status**: NOT STARTED

**What it is**: Visual badges that highlight time-sensitive or noteworthy conditions at a glance

**Indicators** (show max 2 per ticker):
- 📋 **Earnings Alert** - Earnings <7 days away
- 📰 **Breaking News** - 10+ articles in 24h
- 📈 **Insider Buying** - Executive purchases >$1M
- 📉 **Negative Catalyst** - News sentiment <-0.3
- 🔥 **Hot Opportunity** - Top 3 BUY signals
- 💎 **Value Play** - High fundamental / low price score
- ⚡ **Momentum** - High price + technical scores
- ⚠️ **Caution** - Score misalignment warning

**Implementation**:
- Create `backend/app/watchlist/priority.py` module
- Add `calculate_priority_indicators()` function
- Add `priority_indicators` field to API response
- Add visual badges to WatchlistTable (merge with Signal column)
- Show tooltips on hover

**Why Priority 1**: Already fully designed in task files, high visibility, immediate value

**Task File Reference**: `news-phase2-plain-language-ui.md` Task 5

---

### 2. **Display Actionable Insights in UI** 💡
**Effort**: LOW (30 min - 1 hour)
**User Value**: HIGH
**Status**: BACKEND DONE, FRONTEND MISSING

**What it is**: Backend generates `actionable_insight` field (e.g., "Wait for RSI to cool off before entry") but frontend doesn't display it

**Current State**:
- ✅ Backend: `news_intelligence.actionable_insight` populated (verified in code)
- ❌ Frontend: NewsIntelligenceCard doesn't render this field

**Implementation**:
- Add `actionable_insight` display to `NewsIntelligenceCard.tsx`
- Style as prominent text (different color/weight)
- Place below sentiment score, above article count

**Why Priority 2**: Backend work already complete, just needs UI plumbing - quick win

**Task File Reference**: `news-phase2-plain-language-ui.md` gap identified in WORK_TRACKER

---

### 3. **Re-enable Score History Sparklines** 📈
**Effort**: LOW (1-2 hours)
**User Value**: MEDIUM-HIGH
**Status**: TEMPORARILY DISABLED

**What it is**: Inline sparkline charts showing 30-day score trends

**Current State**:
- Component exists: `SparklineWithHistory.tsx`
- Temporarily disabled due to insufficient historical data
- API endpoint exists: `/api/watchlist/{item_id}/score-history`
- Comment: "Re-enable after 90 days of snapshot data accumulated"

**Implementation**:
- Check if 90 days of data exists: `SELECT MIN(fetched_at) FROM watchlist_snapshots`
- If yes: Uncomment sparkline in WatchlistTable.tsx
- If no: Wait, or implement with shorter history (7-14 days)
- Update TODO comment with actual decision

**Why Priority 3**: Component ready, just needs data threshold check and re-enable

**Task File Reference**: `SparklineWithHistory.tsx:13-14` TODO comment

---

## ⭐⭐ TIER 2: Complete Half-Finished Features (8-12 hours total)

### 4. **Integrate Fundamental Score into Overall Score** 🎯
**Effort**: MEDIUM (2-3 hours)
**User Value**: HIGH
**Status**: COLUMNS EXIST, NOT CALCULATED

**What it is**: Change from 2-pillar scoring (price 50%, technical 50%) to 3-pillar (price 33%, technical 33%, fundamental 34%)

**Current State**:
- ✅ `fundamental_score` column exists in watchlist_snapshots
- ✅ Basic fundamental fetching works (health classification)
- ❌ `fundamental_score` NOT calculated (always NULL)
- ❌ Overall score formula still 2-pillar (line 184-185 in scoring.py)
- ❌ No 4-pillar detailed scoring (Valuation/Growth/Health/Sentiment)

**Implementation**:
1. Add 4-pillar scoring functions to `fundamentals.py`:
   - `calculate_valuation_score()` - P/E, P/B, PEG ratio (30% weight)
   - `calculate_growth_score()` - Revenue growth, earnings growth (35% weight)
   - `calculate_health_score()` - Debt/equity, profit margin (25% weight)
   - `calculate_sentiment_score()` - Analyst recommendations (10% weight)
   - `calculate_fundamental_score()` - Weighted average
2. Update `refresh_processor.py` to calculate and store fundamental_score
3. Update `scoring.py` to support 3-pillar formula
4. Add user preference: `watchlist_score_weights` JSONB (already in migration 009)
5. Update frontend to show 3-pillar breakdown

**Why Priority 4**: Half-complete (DB ready, just needs calculation logic), high impact on accuracy

**Task File Reference**: `tasks-0022-watchlist-intelligence-2.md` Task 3

---

### 5. **Calculate Volume, Timeframe, and Percentile Fields** 📊
**Effort**: MEDIUM-HIGH (3-4 hours)
**User Value**: MEDIUM
**Status**: COLUMNS EXIST, NOT CALCULATED

**What it is**: Populate the 4 fields from migration 009 that are currently always NULL

**Current State**:
- ✅ DB columns exist (migration 009 completed)
- ✅ Fields in Pydantic models
- ❌ NOT calculated anywhere (grep shows no calculation code)

**Fields**:
1. **volume_relative** - Current volume / 50-day avg (e.g., 2.3 = 2.3x surge)
2. **timeframe_short_aligned** - Price > SMA_20 > SMA_50 (bullish short-term)
3. **timeframe_long_aligned** - SMA_50 > SMA_200 (bullish long-term)
4. **percentile_rank_30d** - Overall score vs 30-day history (0-100 percentile)

**Implementation**:
1. Create `backend/app/watchlist/timeframe.py`:
   - `calculate_timeframe_alignment()` function
2. Create `backend/app/watchlist/percentiles.py`:
   - `calculate_percentile_rank()` function
3. Update `refresh_processor.py` to calculate all 4 fields
4. Add to snapshot storage
5. Display in ExpandedRow (volume surge, timeframe status)

**Why Priority 5**: Foundational data for better signal classification, columns already exist

**Task File Reference**: `tasks-0022-watchlist-intelligence-2.md` Tasks 2, 4, 6

---

### 6. **Fix AVOID Signal Bugs (sma_5_prev, news_sentiment)** 🐛
**Effort**: LOW-MEDIUM (2-3 hours)
**User Value**: HIGH (correctness)
**Status**: PAUSED AT 19% (Task 2.4)

**What it is**: Fix bugs where AVOID signal classifier receives None values instead of actual data

**Current Bugs**:
- `sma_5_prev=None` - Signal classifier can't detect declining trends
- `news_sentiment=None` - Signal classifier can't use news in AVOID logic

**Current State**:
- ✅ SMA_5 calculation implemented in indicators.py
- ❌ SMA_5_prev NOT passed to signal_classifier.py
- ❌ News sentiment NOT integrated into refresh flow

**Implementation**:
1. Update `refresh_processor.py` to fetch previous SMA_5 (yesterday's value)
2. Pass `sma_5_prev` to `classify_signal()` call
3. Integrate news sentiment into watchlist refresh flow
4. Update AVOID threshold from 3→2 confirming indicators (per task-0022 spec)
5. Write test for 2-flag AVOID signal

**Why Priority 6**: Bug fixes always high priority, affects signal accuracy

**Task File Reference**: `tasks-0022-watchlist-intelligence-2.md` Task 2 (paused at subtask 2.4)

---

## ⭐⭐⭐ TIER 3: Polish & Enhancement (4-6 hours total)

### 7. **Improve Plain Language Headline Coverage** 📰
**Effort**: MEDIUM (2-3 hours)
**User Value**: MEDIUM-HIGH
**Status**: 32% COVERAGE, TARGET 90%+

**What it is**: Increase LLM-generated plain language headlines from 32% to 90%+ of articles

**Current State** (per WORK_TRACKER):
- 2,004 news articles cached
- Only 32% have plain_language_headline (should be 90%+)
- 68% have impact_summary (decent but could be higher)

**Implementation**:
1. Audit why 68% of articles have no plain language headline
2. Check LLM task completion rate in Celery logs
3. Increase batch processing or reduce rate limits if failing
4. Add fallback: Use article title if LLM translation fails
5. Monitor coverage improvement

**Why Priority 7**: User-facing quality improvement, affects readability

**Task File Reference**: `news-phase2-plain-language-ui.md` Task 2

---

### 8. **Add Search and Advanced Filtering** 🔍
**Effort**: MEDIUM (2-3 hours)
**User Value**: HIGH
**Status**: NOT STARTED

**What it is**: Search bar and multi-dimensional filters for the watchlist

**Features**:
- Search box (filter by symbol or company name)
- Filter by signal type (BUY/HOLD/AVOID)
- Filter by news sentiment (Bullish/Neutral/Bearish)
- Filter by score range (e.g., "overall > 70")
- Combined filters (AND logic)
- Save filter presets to localStorage

**Implementation**:
1. Add search input to WatchlistPage header
2. Add filter dropdowns next to existing style filter
3. Implement client-side filtering logic
4. Persist active filters to localStorage
5. Show active filter count badge

**Why Priority 8**: Common user request, improves usability for large watchlists

**Task File Reference**: NEW (identified in user workflow analysis)

---

### 9. **Add "What If I Bought" Calculator** 📊
**Effort**: MEDIUM (2-3 hours)
**User Value**: MEDIUM
**Status**: NOT STARTED

**What it is**: Show hypothetical P&L if user had followed the recommendation

**Features**:
- "If you bought at entry_price X days ago"
- Calculate current P&L based on current price
- Show vs. stop loss and profit target
- Color code: green (winning), red (stopped out), yellow (in progress)
- Accuracy tracking for signals

**Implementation**:
1. Add `simulated_entry_date` to watchlist_items (user can set when they "virtually entered")
2. Calculate P&L in API: `(current_price - entry_price) / entry_price * 100`
3. Add "Start Tracking" button in ExpandedRow
4. Display P&L badge in main table
5. Add "Performance Tracking" tab to watchlist page

**Why Priority 9**: Gamification, helps users learn signal accuracy

**Task File Reference**: NEW (inspired by paper trading roadmap)

---

### 10. **Add Bulk Actions** ✅
**Effort**: LOW-MEDIUM (1-2 hours)
**User Value**: MEDIUM
**Status**: NOT STARTED

**What it is**: Select multiple tickers and perform batch operations

**Features**:
- Checkbox column in WatchlistTable
- Select all / deselect all
- Bulk delete selected tickers
- Bulk refresh selected tickers
- Compare 2-3 tickers side-by-side

**Implementation**:
1. Add checkbox column to WatchlistTable
2. Track selected items in state: `const [selected, setSelected] = useState<Set<string>>(new Set())`
3. Show action bar when items selected
4. Add "Delete Selected" and "Refresh Selected" buttons
5. Implement batch API calls

**Why Priority 10**: Nice-to-have for power users with large watchlists

**Task File Reference**: NEW (common feature request)

---

## 📋 Implementation Recommendations

### Quick Wins Sprint (1 day, ~6 hours)
Do Tier 1 items 1-3 in sequence:
1. Priority Indicators (2-3h)
2. Display Actionable Insights (1h)
3. Re-enable Sparklines (1-2h)

**Outcome**: Immediate visible improvements, high user delight

---

### Foundation Sprint (2 days, ~12 hours)
Do Tier 2 items 4-6:
1. Integrate Fundamental Score (3h)
2. Calculate Volume/Timeframe/Percentile (4h)
3. Fix AVOID Signal Bugs (3h)
4. Update tests and restart services (2h)

**Outcome**: Complete half-finished features, improve accuracy

---

### Polish Sprint (1 day, ~6 hours)
Do Tier 3 items 7-8:
1. Improve Plain Language Coverage (2h)
2. Add Search and Filtering (3h)
3. Documentation updates (1h)

**Outcome**: Professional polish, better UX

---

### Future Enhancements
Items 9-10 can be deferred or done as standalone projects:
- "What If I Bought" Calculator
- Bulk Actions

---

## 🔍 Key Insights from Review

1. **Migration 009 is a false positive** - Columns exist but nothing populates them
2. **Fundamental score is unused** - Column exists, basic fetching works, but not in overall score
3. **Priority indicators have 2 detailed designs** - One in task-0022, one in news-phase2 (use news-phase2 version, it's simpler)
4. **Sparklines are ready** - Just need to check data availability and flip a switch
5. **Actionable insights are hidden gold** - Backend generates them, UI doesn't show them

---

## ❓ Questions for Discussion

1. **Fundamental Scoring**: Do you want 4-pillar detailed scoring (Valuation/Growth/Health/Sentiment) or simple health classification is enough?
2. **Priority Indicators**: Which indicators matter most? All 8 or subset of 4-5?
3. **Sparklines**: If <90 days of data, show partial history or wait?
4. **Search/Filter**: High priority or defer after other items?
5. **Volume/Timeframe/Percentile**: Are these genuinely useful or academic nice-to-haves?

---

## 📁 Related Files

**Task Lists**:
- `tasks-0022-watchlist-intelligence-2.md` - Original comprehensive plan (19% done, paused)
- `news-phase2-plain-language-ui.md` - Task 5 has priority indicators
- `WORK_TRACKER.md` - Shows task-0022 superseded but priority indicators missing

**Backend Modules**:
- `backend/app/watchlist/scoring.py` - 2-pillar formula (needs 3-pillar)
- `backend/app/watchlist/fundamentals.py` - Basic fetching (needs 4-pillar scoring)
- `backend/app/watchlist/signal_classifier.py` - AVOID bugs (sma_5_prev, news_sentiment)
- `backend/app/watchlist/refresh_processor.py` - Refresh flow (needs volume/timeframe/percentile)
- `backend/migrations/009_watchlist_intelligence_2.sql` - Columns exist (need calculation)

**Frontend Components**:
- `frontend/components/watchlist/WatchlistTable.tsx` - Main table
- `frontend/components/watchlist/NewsIntelligenceCard.tsx` - Missing actionable_insight
- `frontend/components/watchlist/SparklineWithHistory.tsx` - Disabled, needs re-enable
- `frontend/app/watchlist/page.tsx` - Page layout

---

## ✅ Next Steps

1. **Review this list** - Agree on priorities, add/remove/reorder items
2. **Answer questions** - Clarify fundamental scoring depth, indicator selection, etc.
3. **Choose sprint** - Pick Quick Wins (Tier 1), Foundation (Tier 2), or custom selection
4. **Implementation begins** - Create task list, run /do_it, autonomous execution

---

**Total Estimated Effort**: 16-24 hours across all 10 items
**Recommended First Sprint**: Tier 1 (items 1-3) - 4-6 hours, high visible impact
