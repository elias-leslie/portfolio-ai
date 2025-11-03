# PRD #0022: Watchlist Intelligence 2.0 - AI-First Data Foundation & UI Redesign

**Status**: Draft
**Created**: 2025-11-02
**Priority**: HIGH
**Estimated Effort**: 23 hours (3-4 days)
**Dependencies**: PRD #0021 (Narrative Intelligence) complete

---

## Introduction

Transform the watchlist from a data dashboard into an actionable intelligence platform. Currently, the system shows raw numeric scores that require interpretation, has broken AVOID signal logic, and lacks fundamental analysis. This PRD addresses critical bugs, completes the three-pillar scoring model, and reorganizes the UI to surface actionable insights over raw data.

**Core Problem**: Users see "72.3 technical score" but don't know if that's good, bad, or what action to take. The narrative intelligence system (PRD #0021) generates plain-language insights, but they're buried in expanded rows. AVOID signals don't work due to bugs. Fundamental analysis is missing.

---

## Goals

1. **Fix critical bugs** - AVOID signals must trigger on declining stocks (currently impossible due to bugs)
2. **Complete scoring model** - Add fundamental scoring as third pillar (price + technical + fundamental)
3. **Surface insights first** - Show AI headlines and priority indicators in main table, not buried
4. **Add proven edges** - Volume confirmation, multi-timeframe alignment (research-backed features)
5. **Improve clarity** - Rename "style" → "timeframe", add specific priority indicators with tooltips
6. **Enable context** - Show percentile ranks ("Top 20%") not just raw scores ("72.3")

---

## Success Metrics

- **AVOID signals work**: Add declining stocks → AVOID triggers within 24 hours
- **Low false positives**: AVOID false positive rate <20% over 30 days
- **High data coverage**: Fundamental data available for >90% of stocks
- **Fast decisions**: User identifies top 3 opportunities in <5 seconds
- **Contextual scores**: Percentile ranks visible without row expansion
- **Accuracy boost**: Volume confirmation improves signal accuracy by 3-5% (measured via backtest)

---

## User Stories

**As a trader**, I want to see which stocks need immediate attention (🔥📅) vs stable monitoring (no indicators), so I can focus on high-priority opportunities without analyzing 14 rows.

**As a value investor**, I want fundamental scoring (P/E, growth, debt ratios) alongside technical analysis, so I can identify undervalued stocks with strong technicals.

**As a risk-averse trader**, I want AVOID signals to warn me about declining stocks, so I can avoid losing money on bad entries.

**As a momentum trader**, I want volume confirmation on breakouts, so I don't get faked out by low-volume false breakouts.

**As a new trader**, I want to see "72 (Top 20%)" instead of just "72", so I understand if a score is actually good relative to history.

---

## Functional Requirements

### FR-1: Fix AVOID Signal Logic (CRITICAL BUG)

**Current Issue**: AVOID signals never trigger because:
- `sma_5_prev = None` (hardcoded) → AVOID Check 1 fails
- `news_sentiment = None` (hardcoded) → AVOID Check 2 fails
- Need 3 flags to trigger, but only 2 checks work

**Requirements**:
- FR-1.1: Add SMA_5 calculation to technical indicators module
- FR-1.2: Store `sma_5` in `technical_indicators` table
- FR-1.3: Provide `sma_5` and `sma_5_prev` (1-day lag) to signal classifier
- FR-1.4: Integrate news sentiment into refresh flow (populate `news_sentiment` field)
- FR-1.5: Lower AVOID threshold from 3 flags → 2 flags (fixed, not configurable yet)
- FR-1.6: Test with real declining stocks using scheduled refresh (not manual API calls)

**Acceptance Criteria**:
- Add HOOD, COIN, or ZM to watchlist → AVOID signal appears within 24 hours
- Signal classifier receives non-null `sma_5_prev` and `news_sentiment`
- AVOID triggers when 2+ flags present (downtrend + negative news, etc.)

---

### FR-2: Fundamental Scoring System (Three-Pillar Model)

**Current Issue**: Only price + technical scores. Missing fundamental analysis (P/E, growth, debt).

**Requirements**:
- FR-2.1: Define fundamental score components (0-100 scale):
  - **Valuation** (30%): P/E ratio, P/B ratio, PEG ratio (vs sector avg if available)
  - **Growth** (35%): Revenue growth YoY, earnings growth YoY, EPS trend (4 quarters)
  - **Health** (25%): Debt-to-equity, current ratio, profit margin (vs sector)
  - **Sentiment** (10%): Analyst rating consensus, earnings surprise %
- FR-2.2: Fetch data from YFinance (primary) → Finnhub → FMP (failover)
- FR-2.3: Cache fundamental data for 24 hours (changes slowly)
- FR-2.4: Handle ETFs differently:
  - Use constituent average (e.g., SPY = avg P/E of S&P 500 holdings)
  - If constituent data unavailable, use alternative metrics (expense ratio, tracking error)
  - Store in separate `etf_fundamentals` if needed
- FR-2.5: Store `fundamental_score` in `watchlist_snapshots` table
- FR-2.6: Update overall score formula:
  - **Before**: `overall = (price * 0.5) + (technical * 0.5)`
  - **After**: `overall = (price * 0.33) + (technical * 0.33) + (fundamental * 0.34)`
- FR-2.7: Make weights configurable in `user_preferences`:
  - Default: `{"price": 33, "technical": 33, "fundamental": 34}`
  - Allow user customization (e.g., 20/20/60 for fundamental-heavy)

**Acceptance Criteria**:
- NVDA shows fundamental_score between 0-100 with component breakdown
- SPY (ETF) shows fundamental_score using S&P 500 constituent average
- Overall score reflects 33/33/34 weighting
- User can adjust weights in settings page (future: not in this PRD)

---

### FR-3: Main Table Reorganization (Insight-First Design)

**Current Issue**: Main table shows numeric scores requiring interpretation. AI insights buried in expanded rows.

**New Column Structure** (8 columns):

1. **Symbol** (existing + enhancements)
   - Keep: Symbol name, YFinance badge, chevron
   - Add: Event badges (📅 if earnings <7 days, 📰 if news <24h)

2. **Priority Indicators** (NEW)
   - Show max 2 indicators per ticker (prioritized by importance)
   - Available indicators (with tooltips on hover):
     - 🔥 **Hot Opportunity**: Top 3 overall scores + BUY signal ("Top entry point - strong alignment")
     - 📉 **Declining**: Score dropped >10 points in 7 days ("Review position timing")
     - 📅 **Event Catalyst**: Earnings <7 days ("High volatility expected")
     - 📰 **News Alert**: News sentiment <-0.3 OR breaking news <24h ("Check headlines before entry")
     - 💎 **Value Play**: Fundamental >70 AND price <50 ("Undervalued with strong fundamentals")
     - ⚡ **Momentum**: Price >70 AND technical >70 ("Strong upward momentum")
     - 🛡️ **Defensive**: Risk=Low AND volatility <sector_avg ("Stable, low-risk holding")
     - ⚠️ **Caution**: (price >70 AND fundamental <40) OR (price <30 AND fundamental >70) ("Conflicting signals")
   - Priority order: 🔥 > 📉 > 📅 > 📰 > 💎 > ⚡ > 🛡️ > ⚠️ (show top 2)

3. **Timeframe** (rename from "Style")
   - Simplified categories:
     - **Quick Trade** (<1 week): Event-driven, catalyst plays
     - **Short-Term** (1-3 weeks): Swing/reversal setups
     - **Medium-Term** (1-6 months): Trend following
     - **Long-Term** (6-12 months): Value investing, index holds
   - Display: "Short-Term · Medium Risk"

4. **Headline** (NEW)
   - Show `narrative_headline` field (truncate to ~40 chars)
   - Example: "Strong breakout w/ volume confirm..."
   - Full headline visible in expanded row

5. **Price** (replace score with actual price)
   - Before: "49.1" (price score)
   - After: "$142.30 (+2.3%)" (actual price + daily change %)
   - Color: green if positive, red if negative

6. **Score** (replace technical with overall + context)
   - Before: "73.8" (technical score only)
   - After: "72 (Top 20%)" (overall score + percentile rank)
   - Calculation: Current score vs 30-day history

7. **Trend** (keep sparkline)
   - No changes, keep existing 7-day sparkline

8. **Updated** (relative time)
   - Before: "Nov 2, 5:39 PM EST"
   - After: "3m ago"
   - Tooltip on hover shows full timestamp

**Requirements**:
- FR-3.1: Add `priority_indicators` field to API response (array of objects with icon/tooltip)
- FR-3.2: Implement priority calculation logic (max 2 indicators per ticker)
- FR-3.3: Rename backend field: `recommended_style` → `recommended_timeframe`
- FR-3.4: Map old style values to new timeframe values:
  - Index → "Long-Term (Hold)"
  - Event → "Quick Trade (<1 week)"
  - Swing → "Short-Term (1-3 weeks)"
  - Trend → "Medium-Term (1-6 months)"
  - Value → "Long-Term (6-12 months)"
- FR-3.5: Calculate daily price change % from day_bars table
- FR-3.6: Update frontend table component to use new columns

**Acceptance Criteria**:
- Main table shows 8 columns with new structure
- NVDA with high score shows 🔥 indicator, GOOGL with earnings <7d shows 📅
- Timeframe column shows "Short-Term · Medium Risk" format
- Price column shows "$142.30 (+2.3%)" in green if positive
- Score column shows "72 (Top 20%)" with percentile context

---

### FR-4: News/Sentiment Integration

**Current Issue**: Infrastructure 90% complete (Google News RSS + VADER sentiment) but not integrated into refresh flow.

**Requirements**:
- FR-4.1: Call `fetch_news_headlines_cached()` in watchlist refresh service
- FR-4.2: Calculate average sentiment score from headlines
- FR-4.3: Store in `news_sentiment_score` field (average of top 10 headlines)
- FR-4.4: Store top 5 headlines in `recent_news_headlines` JSONB field
- FR-4.5: Pass `news_sentiment` to signal classifier (enables AVOID Check 2)
- FR-4.6: Show 📰 indicator if news published <24 hours ago
- FR-4.7: Cache news for 6 hours (already implemented in news module)

**Acceptance Criteria**:
- Add AAPL to watchlist → news_sentiment_score populates within 1 refresh cycle
- Ticker with negative news (<-0.3 sentiment) shows 📰 indicator
- Signal classifier receives non-null news_sentiment value
- News headlines visible in expanded row

---

### FR-5: Volume Confirmation (Proven Edge)

**Current Issue**: Not using volume to validate breakouts. Research shows 70% of successful breakouts have volume >1.5x average.

**Requirements**:
- FR-5.1: Calculate volume relative to 50-day average from day_bars table
- FR-5.2: Test 1.5x vs 2.0x multiplier with historical breakout data
- FR-5.3: Choose optimal multiplier based on backtest results (start with 1.5x if no clear winner)
- FR-5.4: Store `volume_relative` in watchlist_snapshots (ratio, e.g., 2.3 = 2.3x average)
- FR-5.5: Modify signal classification:
  - IF signal=BUY AND volume_relative >1.5: strength += 2, add flag "Volume confirms breakout"
  - IF signal=BUY AND volume_relative <0.8: strength -= 1, add flag "Low volume - watch for fakeout"
- FR-5.6: Display in expanded row: "Volume: 45M (2.3x avg) - Strong confirmation"

**Acceptance Criteria**:
- NVDA breakout with high volume shows strength boost (+2)
- Low volume breakout shows warning flag
- Volume analysis visible in expanded row with interpretation

---

### FR-6: Multi-Timeframe Alignment (Proven Edge)

**Current Issue**: Only checking single timeframe. Research shows 65% of successful trades align on multiple timeframes.

**Requirements**:
- FR-6.1: Calculate short-term alignment: `price > sma_20 AND sma_20 > sma_50`
- FR-6.2: Calculate long-term alignment: `sma_50 > sma_200`
- FR-6.3: Store boolean flags: `timeframe_short_aligned`, `timeframe_long_aligned`
- FR-6.4: Modify signal classification:
  - IF both aligned (uptrend on multiple timeframes): strength += 1, add flag "Multi-timeframe alignment"
- FR-6.5: Display in expanded row: "✓ Short-term uptrend ✓ Long-term uptrend"

**Acceptance Criteria**:
- NVDA in uptrend on daily + weekly shows alignment confirmation
- Signal strength increases +1 when both timeframes aligned
- Alignment status visible in expanded row

---

### FR-7: Historical Context & Percentiles

**Current Issue**: Score of "72.3" has no context. Is it high or low? Improving or declining?

**Requirements**:
- FR-7.1: Extend snapshot retention from 7 days → 30 days (for percentile calculation)
- FR-7.2: Add cleanup job: Delete snapshots >90 days old
- FR-7.3: Calculate percentile rank daily (cache result, don't recompute every refresh):
  - For each ticker, compare current overall_score to last 30 daily snapshots
  - Percentile = (# of scores below current) / (total count) * 100
- FR-7.4: Bucket into categories:
  - **Top 10%**: percentile >=90
  - **Top 20%**: percentile >=80
  - **Top 50%**: percentile >=50
  - **Below Avg**: percentile <50 AND >=20
  - **Bottom 10%**: percentile <10
- FR-7.5: Calculate trend indicator:
  - Compare current score to 7-day average
  - **↑ Improving**: current > 7d_avg + 5
  - **↓ Declining**: current < 7d_avg - 5
  - **→ Stable**: within ±5 points
- FR-7.6: Display in main table: "72 (Top 20%)"
- FR-7.7: Display in expanded row: "Current: 72.3 | 30-day avg: 65.2 | Percentile: 85th (Top 15%) ↑"

**Acceptance Criteria**:
- NVDA with score=89 (highest in 30 days) shows "89 (Top 10%)"
- Score trending up shows ↑ indicator
- Expanded row shows detailed percentile breakdown

---

### FR-8: Expanded Row Enhancements

**Requirements**:
- FR-8.1: Add "Score Breakdown" section (new section between Trade Levels and Notes):
  ```
  Score Breakdown
  ├─ Price Score: 49.1 (Below Avg) - [components]
  ├─ Technical Score: 73.8 (Top 20%) - [components]
  ├─ Fundamental Score: 68.5 (Top 50%) - [components] ← NEW
  └─ Overall: 72.3 (Top 15%) - Weighted average (33/33/34)
  ```
- FR-8.2: Show volume analysis: "Volume: 45M (2.3x avg) - Strong confirmation"
- FR-8.3: Show timeframe alignment: "✓ Short-term uptrend ✓ Long-term uptrend"
- FR-8.4: Keep all existing sections (Trading Intelligence, Trade Levels, History, Notes)

**Acceptance Criteria**:
- Expanded row shows 3 score components + overall with percentiles
- Volume and timeframe analysis visible
- All existing narrative fields preserved

---

## Non-Goals (Out of Scope)

- AI agent integration (deferred until data foundation complete)
- Portfolio cross-reference (watchlist-only focus)
- Sector rotation detection (nice-to-have, not critical edge)
- Options data (IV percentile, put/call ratio)
- Insider trading tracking
- Short interest data
- Real-time streaming quotes (keep batch refresh)
- Social sentiment (Twitter, Reddit)

---

## Technical Specifications

### Database Changes

**Migration 009: Add new columns to watchlist_snapshots**

```sql
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS fundamental_score FLOAT;
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS volume_relative FLOAT;
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS timeframe_short_aligned BOOLEAN DEFAULT FALSE;
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS timeframe_long_aligned BOOLEAN DEFAULT FALSE;
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS percentile_rank_30d FLOAT;

-- Add indexes for percentile calculations
CREATE INDEX IF NOT EXISTS idx_snapshots_item_fetched
  ON watchlist_snapshots(item_id, fetched_at DESC);
```

**Add SMA_5 to technical_indicators table** (already has sma_20/50/200):

```sql
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS sma_5 FLOAT;
```

**Add weights to user_preferences**:

```sql
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS
  watchlist_score_weights JSONB DEFAULT '{"price": 33, "technical": 33, "fundamental": 34}';

ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS
  watchlist_avoid_threshold INTEGER DEFAULT 2;

ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS
  watchlist_volume_surge_multiplier FLOAT DEFAULT 1.5;
```

### API Changes

**WatchlistItemResponse model updates**:

```python
class WatchlistItemResponse(BaseModel):
    # Existing fields...

    # New/modified fields
    fundamental_score: float | None = None
    percentile_rank: float | None = None
    percentile_bucket: str | None = None  # "Top 10%", "Top 20%", etc.
    score_trend: str | None = None  # "↑", "↓", "→"
    volume_relative: float | None = None
    timeframe_short_aligned: bool = False
    timeframe_long_aligned: bool = False
    priority_indicators: list[PriorityIndicator] = []

    # Rename
    recommended_timeframe: str | None = None  # was: recommended_style

    # For backward compatibility, keep old field (remove after 30 days)
    @property
    def recommended_style(self) -> str | None:
        return self.recommended_timeframe

class PriorityIndicator(BaseModel):
    icon: str  # "🔥", "📉", etc.
    label: str  # "Hot Opportunity", "Declining", etc.
    tooltip: str  # Full explanation
    priority: int  # 1-8 (for sorting)
```

### Data Sources & Caching

| Data Type | Source | Failover | Cache TTL | API Calls/Ticker |
|-----------|--------|----------|-----------|------------------|
| **Price** | YFinance | TwelveData → Polygon | 15 min | 1 (or 0 if cached) |
| **Fundamentals** | YFinance | Finnhub → FMP | 24 hours | 1 (or 0 if cached) |
| **News** | Google RSS | N/A (free) | 6 hours | ~1 (RSS fetch) |
| **Earnings** | YFinance | Finnhub | 30 days | 0 (cached) |
| **Volume** | day_bars | Local | N/A | 0 (local query) |
| **Technical** | day_bars | Local | N/A | 0 (local calc) |

**Total**: ~3-4 API calls per ticker per refresh (with caching: ~1-2)

### Performance Targets

- **Refresh time**: <10 seconds for 50 tickers (batch processing)
- **API calls**: <5 per ticker per refresh (target: <250 calls for 50 tickers)
- **Rate limits**: Stay within free tier quotas (YFinance unlimited, others conservative)
- **Database queries**: <50ms for percentile calculation (indexed by item_id + fetched_at)
- **Frontend render**: <100ms for table with 50 rows

---

## Implementation Phases

### Phase 1: Critical Fixes (Day 1 - 3 hours)

**Tasks**:
1. Add SMA_5 to technical indicators calculation (`analytics/indicators.py`)
2. Store SMA_5 in technical_indicators table
3. Update `TechnicalSnapshot` model to include `sma_5`
4. Integrate news fetching in `watchlist/service.py` (5 lines):
   ```python
   news_headlines = fetch_news_headlines_cached(conn, symbol, max_results=10, ttl_hours=6)
   if news_headlines:
       avg_sentiment = sum(h.sentiment_score for h in news_headlines) / len(news_headlines)
       signal_inputs["news_sentiment"] = avg_sentiment
   ```
5. Provide `sma_5_prev` to signal classifier (query previous day's value)
6. Lower AVOID threshold from 3 → 2 in `signal_classification.py`
7. Run database migration 009 (add columns)
8. Test with declining stocks (add HOOD or ZM, wait for scheduled refresh)

**Validation**:
- SMA_5 populates for all tickers
- News sentiment scores appear in snapshots
- AVOID signal triggers on declining stock within 24 hours

---

### Phase 2: Fundamental Scoring (Day 2 - 6 hours)

**Tasks**:
1. Create `fundamentals.py` module in watchlist/
2. Define scoring functions:
   - `calculate_valuation_score(pe, pb, peg, sector_avg)` → 0-100
   - `calculate_growth_score(revenue_growth, earnings_growth, eps_trend)` → 0-100
   - `calculate_health_score(debt_ratio, current_ratio, margin, sector_avg)` → 0-100
   - `calculate_sentiment_score(analyst_rating, earnings_surprise)` → 0-100
3. Fetch data from YFinance (primary):
   - `.info['trailingPE']`, `.info['priceToBook']`, `.info['pegRatio']`
   - `.info['revenueGrowth']`, `.info['earningsGrowth']`
   - `.info['debtToEquity']`, `.info['currentRatio']`, `.info['profitMargins']`
4. Handle ETFs: Fetch constituent average P/E (use yfinance `.constituents` if available, else hardcode SPY → S&P 500 tickers)
5. Calculate weighted fundamental_score: `(val*0.3 + growth*0.35 + health*0.25 + sent*0.1)`
6. Store in watchlist_snapshots.fundamental_score
7. Update overall score formula: `(price*0.33 + tech*0.33 + fund*0.34)`
8. Add user_preferences.watchlist_score_weights (default: 33/33/34)
9. Write 15+ tests for edge cases (missing data, ETFs, negative values)

**Validation**:
- NVDA shows fundamental_score with component breakdown
- SPY (ETF) shows fundamental_score using constituent average
- Overall score uses 33/33/34 weighting

---

### Phase 3: Volume & Timeframe Features (Day 2-3 - 4 hours)

**Tasks**:
1. Add volume_relative calculation:
   ```python
   volume_50d_avg = query_avg_volume(symbol, days=50)
   volume_relative = current_volume / volume_50d_avg
   ```
2. Test 1.5x vs 2.0x multiplier:
   - Backtest: Find 20 historical breakouts in day_bars
   - Measure: Which threshold has higher success rate?
   - Choose winner (default 1.5x if no clear winner)
3. Modify signal classification:
   - Boost strength +2 if volume_relative > threshold AND signal=BUY
   - Lower strength -1 if volume_relative < 0.8 AND signal=BUY
   - Add flags to narrative
4. Add multi-timeframe alignment:
   ```python
   short_aligned = price > sma_20 and sma_20 > sma_50
   long_aligned = sma_50 > sma_200
   if short_aligned and long_aligned:
       strength += 1
   ```
5. Store boolean flags in watchlist_snapshots
6. Display in expanded row with checkmarks

**Validation**:
- High volume breakout shows +2 strength boost
- Multi-timeframe aligned tickers show +1 boost
- Volume and alignment visible in expanded row

---

### Phase 4: UI Reorganization (Day 3 - 4 hours)

**Tasks**:
1. Backend: Rename `recommended_style` → `recommended_timeframe` (keep old field for compatibility)
2. Backend: Map style values to timeframe categories
3. Backend: Implement priority indicator calculation:
   - Check all 8 conditions (🔥📉📅📰💎⚡🛡️⚠️)
   - Sort by priority (1-8)
   - Return top 2 with tooltips
4. Backend: Calculate daily price change % from day_bars
5. Frontend: Update WatchlistTable component:
   - Replace "Signal" column with "Priority" (indicators)
   - Replace "Style" column with "Timeframe"
   - Add "Headline" column (truncate narrative_headline)
   - Replace "Price" score with actual price + change %
   - Replace "Technical" with "Score" (overall + percentile)
   - Change "Updated" to relative time
6. Frontend: Add Tooltip component for priority indicators
7. Frontend: Update filter dropdown (rename "Trading Styles" → "Timeframes")

**Validation**:
- Main table shows 8 new columns
- Top 3 BUY signals show 🔥 indicator
- Timeframe shows "Short-Term · Medium Risk"
- Score shows "72 (Top 20%)"

---

### Phase 5: Historical Context (Day 4 - 3 hours)

**Tasks**:
1. Modify snapshot cleanup job: Keep 30 days instead of 7 days
2. Add new cleanup job: Delete snapshots >90 days old
3. Create percentile calculation function:
   ```python
   def calculate_percentile_rank(item_id: str, current_score: float, conn) -> tuple[float, str]:
       # Query last 30 days of snapshots
       scores = query_30d_scores(item_id, conn)
       percentile = (len([s for s in scores if s < current_score]) / len(scores)) * 100
       bucket = get_percentile_bucket(percentile)  # "Top 10%", "Top 20%", etc.
       return percentile, bucket
   ```
4. Run percentile calculation daily (Celery scheduled task, not every refresh)
5. Store in watchlist_snapshots.percentile_rank_30d
6. Calculate trend indicator (current vs 7d_avg)
7. Update API response to include percentile_bucket and score_trend
8. Display in main table: "72 (Top 20%)"
9. Display in expanded row: Full breakdown with 30-day average

**Validation**:
- Percentile rank appears within 24 hours of adding ticker
- High-scoring ticker shows "Top 10%"
- Declining score shows ↓ indicator

---

### Phase 6: Testing & Documentation (Day 4-5 - 3 hours)

**Tasks**:
1. Add unit tests:
   - AVOID signal with 2 flags triggers
   - Fundamental scoring edge cases (missing data, ETFs, negative values)
   - Volume confirmation logic (surge vs low volume)
   - Multi-timeframe alignment combinations
   - Percentile calculation (edge cases: <7 days data, tied scores)
   - Priority indicator selection (multiple applicable indicators)
2. Add integration tests:
   - Full refresh cycle with news integration
   - ETF fundamental scoring (SPY)
   - Declining stock triggers AVOID (use historical HOOD data)
3. Browser automation screenshots:
   - Main table with new columns
   - Priority indicators visible
   - Expanded row with score breakdown
   - Update README.md in docs/screenshots/watchlist/
4. Update documentation:
   - ARCHITECTURE.md: Add fundamental scoring section
   - API_REFERENCE.md: Document new response fields
   - REFRESH_ARCHITECTURE.md: Update with news integration
5. Performance validation:
   - Measure API calls per refresh (target <5 per ticker)
   - Measure percentile calculation time (target <50ms)
   - Check rate limit compliance logs

**Validation**:
- All tests pass (target: 85% coverage)
- Screenshots show new UI
- Documentation accurate
- Performance targets met

---

## Design Considerations

### Priority Indicator Tooltips

Example tooltip text (shown on hover):

| Icon | Tooltip |
|------|---------|
| 🔥 | **Hot Opportunity** - This is one of your top 3 highest-scoring BUY signals. Strong technical and fundamental alignment. Consider reviewing entry timing. |
| 📉 | **Declining Signal** - Score dropped more than 10 points in the past 7 days. Review your position timing or wait for stabilization. |
| 📅 | **Event Catalyst** - Earnings announcement in less than 7 days. Expect increased volatility. Consider waiting until after earnings or reducing position size. |
| 📰 | **News Alert** - Recent negative news detected (sentiment: -0.4). Review headlines in expanded row before taking action. |
| 💎 | **Value Play** - Strong fundamental score (>70) but low price score (<50). Potential long-term value opportunity. |
| ⚡ | **Momentum** - Strong upward price momentum with technical confirmation. Short to medium-term opportunity. |
| 🛡️ | **Defensive** - Low volatility and stable fundamentals. Good for conservative or risk-averse portfolios. |
| ⚠️ | **Caution** - Conflicting signals detected (e.g., strong price but weak fundamentals). Proceed carefully or wait for confirmation. |

### Percentile Bucket Display

| Percentile Range | Bucket Label | Color |
|------------------|--------------|-------|
| 90-100 | Top 10% | Dark green |
| 80-89 | Top 20% | Green |
| 50-79 | Top 50% | Light green |
| 20-49 | Below Avg | Yellow |
| 0-19 | Bottom 10% | Red |

---

## Technical Constraints

1. **Backward Compatibility**:
   - Keep `recommended_style` field for 30 days (populate from `recommended_timeframe`)
   - Add deprecation warning in API docs
   - Remove after 30 days (set date: 2025-12-02)

2. **Rate Limits**:
   - YFinance: Unlimited (primary source)
   - TwelveData: 8 req/min, 800/day
   - Finnhub: 60 req/min (free tier)
   - FMP: 250 req/day (free tier)
   - Google News RSS: Unlimited (no API key)
   - Strategy: Use YFinance for all tickers, fallback only on errors

3. **Test Coverage**:
   - Maintain 85% coverage minimum
   - Critical paths must have 100% coverage (AVOID logic, score calculations)

4. **Type Safety**:
   - All new functions must have type hints
   - Pass mypy --strict checks

---

## Open Questions & Decisions

### ✅ RESOLVED

1. **ETF Fundamental Scoring**: Use constituent average P/E (e.g., SPY = S&P 500 avg)
2. **AVOID Threshold**: Fixed at 2 flags (monitor false positives, adjust if >20%)
3. **Volume Multiplier**: Test 1.5x vs 2.0x with real historical data, choose winner
4. **Percentile Buckets**: 5 buckets sufficient (Top 10/20/50, Below Avg, Bottom 10)
5. **Multiple Indicators**: Max 2 per ticker (prioritized by importance)
6. **News Integration**: Phase 1 (critical for AVOID Check 2)
7. **Breaking Changes**: Migration script, keep old fields temporarily

### 🔍 TO INVESTIGATE

1. **Volume Backtest**: Which multiplier (1.5x or 2.0x) performs better on historical breakouts?
2. **False Positive Rate**: Monitor AVOID signals over 30 days, adjust threshold if FP rate >20%
3. **ETF Constituent Data**: Can we reliably fetch constituent P/E averages for all ETFs? (May need manual mapping: SPY→S&P500, QQQ→Nasdaq100)

---

## Success Validation Plan

**Week 1 (Implementation)**:
1. Add declining stock (HOOD, COIN, or ZM) to watchlist
2. Verify AVOID signal triggers within 24 hours
3. Check news_sentiment and sma_5_prev are non-null

**Week 2 (Volume Testing)**:
1. Identify 20 historical breakouts in day_bars (2024 data)
2. Backtest: Compare 1.5x vs 2.0x multiplier accuracy
3. Choose optimal threshold based on results

**Week 3 (False Positive Monitoring)**:
1. Add 10 "good" stocks to watchlist (NVDA, AAPL, GOOGL, etc.)
2. Monitor AVOID signals over 21 days
3. Measure false positive rate (target: <20%)
4. If FP rate >20%, increase threshold to 3 flags

**Week 4 (User Acceptance)**:
1. Can user identify top 3 opportunities in <5 seconds? (measure with timer)
2. Are priority indicators clear and actionable? (user feedback)
3. Is score context helpful ("Top 20%")? (A/B test vs raw scores)

---

## Estimated Effort Breakdown

| Phase | Tasks | Hours | Complexity |
|-------|-------|-------|------------|
| Phase 1: Critical Fixes | SMA_5, news integration, AVOID fixes, testing | 3 | MEDIUM |
| Phase 2: Fundamental Scoring | Scoring logic, data fetching, ETF handling, tests | 6 | HIGH |
| Phase 3: Volume & Timeframe | Volume calc, backtest, multi-timeframe, integration | 4 | MEDIUM |
| Phase 4: UI Reorganization | Column changes, priority indicators, timeframe rename | 4 | MEDIUM |
| Phase 5: Historical Context | Percentile calc, trend indicators, display | 3 | LOW |
| Phase 6: Testing & Docs | Unit tests, integration tests, screenshots, docs | 3 | LOW |
| **TOTAL** | | **23 hours** | **(3-4 days)** |

**Risk Buffer**: Add 20% contingency (5 hours) for:
- ETF constituent data challenges
- Volume backtest takes longer than expected
- Frontend UI iteration
- **Total with buffer: 28 hours (~4 days)**

---

## Dependencies

- **PRD #0021** (Narrative Intelligence): Complete ✅ - Provides headline generation, signal classification, trading style foundation
- **Database**: PostgreSQL 16 with 4x Celery concurrency
- **Data Sources**: YFinance (primary), Finnhub, FMP (failovers), Google News RSS
- **Frontend**: Next.js 14, TanStack Table, shadcn/ui components

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| ETF constituent data unavailable | Can't score SPY, QQQ fundamentals | MEDIUM | Use hardcoded neutral score (50) for ETFs as fallback |
| Volume backtest shows no clear winner | Can't choose 1.5x vs 2.0x | LOW | Default to 1.5x (research standard), revisit later |
| False positive rate >20% for AVOID | Users lose trust in signals | MEDIUM | Monitor closely, increase threshold to 3 flags if needed |
| Rate limit hits on fundamental data | Refresh fails for some tickers | LOW | Conservative batching + caching prevents this |
| Percentile calculation slow (>100ms) | UI lag with 50+ tickers | LOW | Index on (item_id, fetched_at), cache calculation daily |

---

## Rollout Plan

**Phase 1 (Week 1)**: Deploy critical fixes + news integration
- User impact: AVOID signals start working
- Rollback plan: Disable news fetching if errors, revert AVOID threshold to 3

**Phase 2 (Week 2)**: Deploy fundamental scoring
- User impact: New score column appears, overall scores change
- Rollback plan: Revert overall score formula to 50/50, hide fundamental_score

**Phase 3-4 (Week 3)**: Deploy volume + UI changes
- User impact: Main table looks different, new columns
- Rollback plan: Frontend feature flag to show old UI

**Phase 5 (Week 4)**: Deploy percentile context
- User impact: Score context appears
- Rollback plan: Hide percentile labels, show raw scores only

---

## Future Enhancements (Not in This PRD)

- **AI Agent Integration**: Use agents to generate personalized watchlist recommendations
- **Portfolio Cross-Reference**: Show "You own 50 shares" in watchlist
- **Sector Rotation**: Highlight sectors with momentum
- **Options Flow**: IV percentile, put/call ratio signals
- **Insider Trading**: Recent buy/sell activity
- **Short Interest**: Days to cover, borrow rate
- **Social Sentiment**: Twitter/Reddit sentiment scores
- **Custom Alerts**: Notify when score reaches threshold
- **Backtesting**: Historical signal accuracy per ticker

---

**END OF PRD**

**Next Step**: Run `/task_it tasks/0022-prd-watchlist-intelligence-2.md` to generate detailed task list.
