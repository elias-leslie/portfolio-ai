# Watchlist Improvements - Part 3: Polish

**Created**: 2025-11-08
**Tier**: Polish (Sprint 3)
**Estimated Effort**: 6 hours
**Environment**: Cloud Claude Code (sandbox, limited runtime)
**Priority**: MEDIUM
**Depends On**: Part 1 (Quick Wins) and Part 2 (Foundation) must be complete

---

## ⚠️ IMPORTANT: Cloud Environment Constraints

**See Part 1 (tasks-cloud-watchlist-part1-quick-wins.md) for full cloud environment constraints.**

**Quick Reference**:
- ✅ CAN: Read code, write code, static analysis, git operations
- ❌ CANNOT: Run services, tests, database commands, check logs
- ✅ MUST: Run ruff + mypy before committing
- Read Part 1 for complete workflow and command restrictions

---

## Overview

**Part 3 Focus**: Polish - User experience refinements and documentation

**Part 3 Deliverables**:
- **Plain Language Coverage**: Investigate and improve from 32% to 90%+
- **Search & Filtering**: Advanced watchlist filtering UI
- **Documentation**: Update API reference and user guides

**Note**: Part 3 is optional polish - Parts 1 and 2 deliver core functionality. This part enhances UX.

---

## Task 1: Research & Validation (DO THIS FIRST)

**Objective**: Understand plain language system and filtering architecture

**Estimated Time**: 30 minutes

### 1.1 Plain Language System Research

- [ ] **File**: `backend/app/tasks/news_tasks.py` or similar
  - Search for plain_language generation logic
  - Check if LLM tasks are being queued
  - Note any error handling for failed LLM calls
  - Document task queue patterns

- [ ] **File**: `backend/app/news/` directory
  - Find where plain_language_headline is generated
  - Check if there's a fallback mechanism
  - Note API rate limiting logic

### 1.2 Filtering System Research

- [ ] **File**: `frontend/app/watchlist/page.tsx`
  - Check existing filtering logic (style filter exists)
  - Note component structure
  - Check if search state exists
  - Document filter patterns

- [ ] **File**: `frontend/components/watchlist/WatchlistTable.tsx`
  - Check if filtering is client-side or server-side
  - Note data structure passed to table

### 1.3 Document Findings

**Plain Language Coverage Issues** (update after research):
- Current coverage: 32% (verified?)
- Root cause: [TBD - LLM failing? Tasks not running? Rate limits?]
- Proposed fix: [TBD based on findings]

**Filtering Architecture** (update after research):
- Current filters: Style filter only
- Proposed additions: Search, signal, sentiment, score range
- Implementation approach: Client-side useMemo filtering

---

## Task 2: Improve Plain Language Coverage

**Goal**: Increase plain language headline coverage from 32% to 90%+

**Estimated Time**: 2 hours

**IMPORTANT**: This task requires runtime investigation which cloud agent CANNOT do.

### 2.1 Code-Based Analysis (Cloud Can Do)

**File**: Search for plain_language generation in codebase

#### Step 1: Find LLM Task Logic
```bash
# Search for plain_language generation
grep -r "plain_language" backend/app/
```

Document findings:
- Where is plain_language_headline generated? [TBD]
- Is there a fallback if LLM fails? [TBD]
- Are failed tasks being retried? [TBD]

#### Step 2: Add Fallback Mechanism

**File**: `backend/app/news/[wherever plain_language is generated]`

Add fallback logic (if not exists):
```python
def generate_plain_language_headline(article: dict) -> str:
    """Generate plain language headline using LLM with fallback.

    Args:
        article: News article dict with headline

    Returns:
        Plain language headline (or original if LLM fails)
    """
    try:
        # Existing LLM logic
        plain_headline = llm_generate_plain_headline(article["headline"])
        if plain_headline:
            return plain_headline
    except Exception as e:
        logger.warning(
            "plain_language_generation_failed",
            error=str(e),
            article_id=article.get("id"),
        )

    # Fallback to original headline (better than NULL)
    return article["headline"]
```

### 2.2 Runtime Investigation (Local Dev Only)

**CLOUD AGENT**: Document these investigation steps for local dev:

```bash
# Check Celery logs for LLM task failures
tail -f /var/log/portfolio-ai/celery-worker.log | grep plain_language

# Check task queue length
redis-cli LLEN celery

# Check database for NULL plain_language
psql -U portfolio_ai_user -d portfolio_ai -c "SELECT COUNT(*) FROM news_cache WHERE plain_language_headline IS NULL"

# Check LLM API key and rate limits
# (In backend code - check OpenAI/Anthropic client configuration)
```

### 2.3 Potential Fixes (Local Dev to Implement Based on Findings)

**If LLM API failing**:
- Check API keys in environment
- Verify rate limits not exceeded
- Add retry logic with exponential backoff

**If tasks not running**:
- Increase Celery workers: Edit celery service config
- Reduce batch size: Lower LLM task concurrency
- Check beat schedule for task frequency

**If timeout issues**:
- Increase task timeout: `@celery_app.task(time_limit=300)`
- Use async LLM calls
- Process in smaller batches

---

## Task 3: Search and Advanced Filtering

**Goal**: Add comprehensive filtering UI to watchlist page

**Estimated Time**: 3 hours

### 3.1 Add Filter State Management

**File**: `frontend/app/watchlist/page.tsx`
**Location**: In component state section (top of component)

Add state variables:
```typescript
// Search and filter state
const [searchQuery, setSearchQuery] = useState("");
const [signalFilter, setSignalFilter] = useState("all");
const [sentimentFilter, setSentimentFilter] = useState("all");
const [scoreRange, setScoreRange] = useState([0, 100]);
```

### 3.2 Add Filtering Logic

**File**: `frontend/app/watchlist/page.tsx`
**Location**: Before passing data to WatchlistTable

Add filtering memo:
```typescript
const filteredItems = useMemo(() => {
  let results = watchlistData?.items || [];

  // Search filter (symbol)
  if (searchQuery) {
    const query = searchQuery.toLowerCase();
    results = results.filter(item =>
      item.symbol.toLowerCase().includes(query)
    );
  }

  // Signal filter
  if (signalFilter !== "all") {
    results = results.filter(item => item.signal_type === signalFilter);
  }

  // Sentiment filter
  if (sentimentFilter !== "all") {
    results = results.filter(item => {
      const sentiment = item.news_intelligence?.sentiment_label?.toLowerCase();
      return sentiment === sentimentFilter;
    });
  }

  // Score range filter
  results = results.filter(item => {
    const score = item.current_score?.overall || 0;
    return score >= scoreRange[0] && score <= scoreRange[1];
  });

  // Style filter (existing)
  if (styleFilter !== "all") {
    results = results.filter(item => item.recommended_style === styleFilter);
  }

  return results;
}, [watchlistData, searchQuery, signalFilter, sentimentFilter, scoreRange, styleFilter]);

// Count active filters
const activeFilterCount = [
  searchQuery !== "",
  signalFilter !== "all",
  sentimentFilter !== "all",
  scoreRange[0] > 0 || scoreRange[1] < 100,
  styleFilter !== "all",
].filter(Boolean).length;
```

### 3.3 Add Filter UI

**File**: `frontend/app/watchlist/page.tsx`
**Location**: In header section (before WatchlistTable)

Add imports:
```typescript
import { Search, SlidersHorizontal } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
```

Add filter UI (~80 lines):
```typescript
{/* Search and Filters */}
<div className="flex gap-2 items-center mb-4">
  {/* Search Box */}
  <div className="relative flex-1 max-w-md">
    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
    <Input
      placeholder="Search by symbol..."
      value={searchQuery}
      onChange={(e) => setSearchQuery(e.target.value)}
      className="pl-10"
    />
  </div>

  {/* Signal Filter */}
  <Select value={signalFilter} onValueChange={setSignalFilter}>
    <SelectTrigger className="w-[140px]">
      <SelectValue placeholder="All Signals" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Signals</SelectItem>
      <SelectItem value="BUY">BUY</SelectItem>
      <SelectItem value="HOLD">HOLD</SelectItem>
      <SelectItem value="AVOID">AVOID</SelectItem>
    </SelectContent>
  </Select>

  {/* News Sentiment Filter */}
  <Select value={sentimentFilter} onValueChange={setSentimentFilter}>
    <SelectTrigger className="w-[140px]">
      <SelectValue placeholder="All Sentiment" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Sentiment</SelectItem>
      <SelectItem value="bullish">Bullish</SelectItem>
      <SelectItem value="neutral">Neutral</SelectItem>
      <SelectItem value="bearish">Bearish</SelectItem>
    </SelectContent>
  </Select>

  {/* Score Range Filter */}
  <Popover>
    <PopoverTrigger asChild>
      <Button variant="outline" size="sm">
        <SlidersHorizontal className="mr-2 h-4 w-4" />
        Score Filter
      </Button>
    </PopoverTrigger>
    <PopoverContent className="w-80">
      <div className="space-y-4">
        <div>
          <Label>Overall Score: {scoreRange[0]} - {scoreRange[1]}</Label>
          <Slider
            min={0}
            max={100}
            step={1}
            value={scoreRange}
            onValueChange={setScoreRange}
            className="mt-2"
          />
        </div>
      </div>
    </PopoverContent>
  </Popover>

  {/* Active Filters Badge */}
  {activeFilterCount > 0 && (
    <Badge variant="secondary">{activeFilterCount} active</Badge>
  )}
</div>
```

### 3.4 Update WatchlistTable to Use Filtered Data

**File**: `frontend/app/watchlist/page.tsx`
**Location**: Where WatchlistTable is rendered

Change:
```typescript
{/* OLD */}
<WatchlistTable items={watchlistData?.items || []} />

{/* NEW */}
<WatchlistTable items={filteredItems} />
```

---

## Task 4: Documentation Updates

**Goal**: Update documentation to reflect all changes

**Estimated Time**: 1 hour

### 4.1 Update API Reference

**File**: `docs/core/API_REFERENCE.md`
**Location**: In Watchlist API section

Add:
```markdown
#### WatchlistItem Response Fields (New in v1.3.1)

**priority_indicators** (array):
- Type: `PriorityIndicator[]`
- Description: Array of priority indicators (no cap on display)
- Fields:
  - `icon`: Emoji (🔥📋📰📈📉💎⚡⚠️)
  - `label`: Display name
  - `tooltip`: Detailed explanation
  - `priority`: Sort order (1-8)
  - `category`: "time_sensitive" | "risk" | "opportunity" | "caution"

**current_score.fundamental** (object):
- Type: `ScoreComponent | null`
- Description: Fundamental score component (33-34% of overall)
- Sub-scores:
  - `valuation`: 0-100 (30% weight)
  - `growth`: 0-100 (35% weight)
  - `health`: 0-100 (25% weight)
  - `sentiment`: 0-100 (10% weight)

**current_score.price.sub_scores** (object):
- Type: `dict[str, float]`
- Description: Price component breakdown
- Fields: `change_pct`, `beta` (future), `volatility` (future)

**current_score.technical.sub_scores** (object):
- Type: `dict[str, float]`
- Description: Technical component breakdown
- Fields: `rsi_14`, `trend`, `macd`
```

### 4.2 Update Development Documentation

**File**: `docs/core/DEVELOPMENT.md`
**Location**: In "Watchlist System" section

Add section:
```markdown
#### Score Calculation System (3-Pillar)

**Overall Score Formula**:
```
overall = (price * 0.33) + (technical * 0.33) + (fundamental * 0.34)
```

**Price Component** (33%):
- Sub-metrics: change_pct (100%)
- Future: beta, volatility

**Technical Component** (33%):
- Sub-metrics: rsi_14 (33%), trend (34%), macd (33%)
- Configurable weights in settings

**Fundamental Component** (34%):
- 4-pillar system:
  - Valuation (30%): P/E, profit margin
  - Growth (35%): Revenue growth
  - Health (25%): Debt/equity, margins
  - Sentiment (10%): Analyst ratings
- Configurable weights in settings

**Fallback**: If fundamental data unavailable, 2-pillar formula (price 50%, technical 50%)
```

### 4.3 Create Settings Documentation

**File**: `docs/user-guides/watchlist-settings.md` (NEW)

```markdown
# Watchlist Settings Guide

## Score Weight Configuration

Configure how overall watchlist scores are calculated using the 3-pillar system.

### Top-Level Weights

**Price Score** (default 33%):
- Measures recent price momentum
- Based on percentage change over 1-30 days

**Technical Score** (default 33%):
- Measures technical indicators
- Sub-metrics: RSI, Trend (SMA), MACD

**Fundamental Score** (default 34%):
- Measures company fundamentals
- Sub-metrics: Valuation, Growth, Health, Sentiment

**Constraint**: All 3 weights must sum to 100%

### Sub-Metric Weights

**Technical Sub-Metrics** (must sum to 100%):
- **RSI** (default 33%): Relative Strength Index (14-day)
- **Trend** (default 34%): SMA alignment (5/20/50/200-day)
- **MACD** (default 33%): MACD momentum indicator

**Fundamental Sub-Metrics** (must sum to 100%):
- **Valuation** (default 30%): P/E ratio, profit margin
- **Growth** (default 35%): Revenue and earnings growth
- **Health** (default 25%): Debt levels, financial stability
- **Sentiment** (default 10%): Analyst recommendations

### How to Adjust Weights

1. Navigate to Settings page
2. Scroll to "Score Weights" section
3. Adjust top-level sliders (Price, Technical, Fundamental)
4. Expand each pillar to adjust sub-metric weights
5. Ensure all totals = 100%
6. Click "Save Settings"
7. Refresh watchlist page to see updated scores

### Example Configurations

**Conservative Value Investor**:
- Price: 20%, Technical: 20%, Fundamental: 60%
- Fundamental: Valuation 40%, Growth 20%, Health 35%, Sentiment 5%

**Aggressive Momentum Trader**:
- Price: 50%, Technical: 40%, Fundamental: 10%
- Technical: RSI 50%, Trend 30%, MACD 20%

**Balanced Growth**:
- Price: 33%, Technical: 33%, Fundamental: 34% (default)
- All sub-metrics at defaults
```

### 4.4 Comment Code

Add docstrings to key functions:
- `calculate_priority_indicators()` - Explain 8 indicator types
- `calculate_fundamental_score()` - Explain 4-pillar system
- `calculate_watchlist_scores()` - Explain 3-pillar formula

---

## Task 5: Static Analysis & Code Quality

**Goal**: Ensure all code passes linting

**Estimated Time**: 15 minutes

```bash
# Backend linting
ruff check backend/app/
ruff format backend/app/

# Type checking
mypy backend/app/watchlist/ --strict

# Fix all errors before committing
```

---

## Task 6: Git Commit & Handoff

**Goal**: Commit Part 3 changes

**Estimated Time**: 15 minutes

### 6.1 Commit

```bash
git add -A
git commit -m "feat(watchlist): Part 3 Polish - filtering, plain language improvements, docs

Backend Changes:
- Plain language fallback mechanism (uses original headline if LLM fails)
- Investigation notes for local dev (logs, queue, API limits)

Frontend Changes:
- Search by symbol
- Signal filter (BUY/HOLD/AVOID)
- Sentiment filter (bullish/neutral/bearish)
- Score range slider (0-100)
- Active filter counter
- Client-side filtering with useMemo

Documentation:
- Updated API_REFERENCE.md with new fields
- Updated DEVELOPMENT.md with 3-pillar formula
- New watchlist-settings.md user guide
- Code comments and docstrings

Part 3 of 3 (Polish tier, 6 hours)"
```

---

## Handoff Instructions

**What Cloud Agent Completed**:
- Advanced filtering UI ✅
- Plain language fallback logic ✅
- Documentation updates ✅
- Static analysis passed ✅

**What Local Dev Must Do**:

### 1. Plain Language Coverage Investigation
```bash
# Check current coverage
psql -U portfolio_ai_user -d portfolio_ai -c "
  SELECT
    COUNT(*) FILTER (WHERE plain_language_headline IS NOT NULL) * 100.0 / COUNT(*) as coverage_pct
  FROM news_cache
"

# Check Celery logs for LLM failures
tail -f /var/log/portfolio-ai/celery-worker.log | grep plain_language

# Check task queue
redis-cli LLEN celery

# Based on findings, implement fixes:
# - If API rate limited: Reduce task concurrency
# - If tasks failing: Check API keys, add retries
# - If tasks not running: Increase workers
```

### 2. Test Filtering UI
1. Open http://192.168.8.233:3000/watchlist
2. Test search box (type symbol)
3. Test signal filter dropdown
4. Test sentiment filter dropdown
5. Test score range slider
6. Verify active filter counter updates
7. Verify filtered results correct

### 3. Verify Documentation
- Read `docs/user-guides/watchlist-settings.md`
- Check API_REFERENCE.md updates
- Verify DEVELOPMENT.md changes

### 4. Run Tests
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
pytest tests/ -v
```

**Branch**: `[branch-name]`

---

## Success Criteria - Complete System

**Parts 1-3 Combined Deliverables**:

✅ **Priority Indicators**:
- 8 indicator types implemented
- NO cap on display (show all relevant)
- Displayed in Signal column with tooltips

✅ **Actionable Insights**:
- Displayed in NewsIntelligenceCard
- Pulled from existing backend field

✅ **Sparkline Backfill**:
- Automated daily Celery task
- Backfills up to 30 days of history
- Sparklines re-enabled in UI

✅ **4-Pillar Fundamental Scoring**:
- Valuation/Growth/Health/Sentiment (30/35/25/10)
- Integrated into 3-pillar overall formula

✅ **3-Pillar Score Formula**:
- Price 33% / Technical 33% / Fundamental 34%
- Sub-scores tracked for all components
- Fallback to 2-pillar if fundamental missing

✅ **Volume/Timeframe/Percentile**:
- Calculation modules created
- Integrated into snapshot creation

✅ **AVOID Signal Fixes**:
- sma_5_prev parameter added
- news_sentiment passed correctly
- Threshold changed to 2+ flags

✅ **Settings Sliders**:
- 3 top-level weights (price/technical/fundamental)
- 7 sub-metric weights (RSI, trend, MACD, valuation, growth, health, sentiment)
- Validation: All groups sum to 100%

✅ **Score Breakdown UI**:
- 3 pillars displayed in expanded row
- Sub-scores shown under each pillar
- Progress bars for visual feedback

✅ **Advanced Filtering**:
- Search by symbol
- Filter by signal type
- Filter by sentiment
- Filter by score range
- Active filter counter

✅ **Documentation**:
- API reference updated
- Development guide updated
- User guide created

---

## Files Summary (All 3 Parts)

**New Backend Files** (5):
1. `backend/app/watchlist/priority.py` (~200 lines)
2. `backend/app/watchlist/timeframe.py` (~60 lines)
3. `backend/app/watchlist/percentiles.py` (~30 lines)
4. `backend/migrations/019_score_weight_sliders.sql` (~25 lines)
5. Task added to `backend/app/tasks/watchlist_tasks.py` (backfill function ~80 lines)

**Modified Backend Files** (8):
1. `backend/app/watchlist/models.py` - ScoreWeights, ScoreBreakdown, ScoreComponent
2. `backend/app/watchlist/scoring.py` - 3-pillar formula, fundamental component
3. `backend/app/watchlist/fundamentals.py` - 4-pillar scoring functions
4. `backend/app/watchlist/response_builders.py` - priority_indicators field
5. `backend/app/watchlist/watchlist_service.py` - calculate priority indicators
6. `backend/app/watchlist/refresh_processor.py` - volume/timeframe/percentile, fundamental scores
7. `backend/app/watchlist/signal_classifier.py` - AVOID bug fixes
8. `backend/app/celery_app.py` - backfill task schedule

**Modified Frontend Files** (5):
1. `frontend/lib/api/watchlist.ts` - PriorityIndicator type
2. `frontend/components/watchlist/WatchlistTable.tsx` - indicators, sparklines
3. `frontend/components/watchlist/NewsIntelligenceCard.tsx` - actionable_insight
4. `frontend/components/watchlist/ExpandedRow.tsx` - score breakdown
5. `frontend/components/settings/WatchlistPreferences.tsx` - sub-metric sliders
6. `frontend/app/watchlist/page.tsx` - advanced filtering

**Documentation Files** (3):
1. `docs/core/API_REFERENCE.md` - Updated
2. `docs/core/DEVELOPMENT.md` - Updated
3. `docs/user-guides/watchlist-settings.md` - NEW

**Total**: 5 new files, 14 modified files, 3 docs

---

## Estimated Timeline (All 3 Parts)

**Part 1 (Quick Wins)**: 6 hours
**Part 2 (Foundation)**: 12 hours
**Part 3 (Polish)**: 6 hours
**Total**: 24 hours (3-4 days of focused work)

---

**END OF PART 3 - All Watchlist Improvements Complete**
