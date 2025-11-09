# Task List Review - Critical Missing Items

**Created**: 2025-11-08 16:20
**Purpose**: Verify task list completeness vs design references

---

## Design Requirements Checklist

### ✅ COVERED in Task List

**Main Table**:
- [x] Hide technical columns (Task 1.2)
- [x] Add Trading Style column (Task 1.3)
- [x] Add Risk Level column (Task 1.4)
- [x] Add search bar (Task 1.5)
- [x] Filter dropdowns - Signal/Style/Risk (Phase 2)
- [x] Sparklines (already implemented)

**Expanded Row**:
- [x] Score breakdown - 3 pillars (already implemented)
- [x] 4-pillar fundamental sub-scores (already implemented)
- [x] News intelligence card (already implemented)
- [x] Trade recommendation (already implemented)

**Settings**:
- [x] Weight sliders for 3 pillars (Task 3.1)
- [x] Sub-weight sliders for technical (Task 3.1)
- [x] Sub-weight sliders for fundamental (Task 3.1)

---

## ❌ CRITICAL GAPS - Need to Add

### Gap 1: Priority Indicators in Signal Column
**Design Shows**: 🔥📰⚡📋💎📉📈 badges next to BUY/HOLD/AVOID
**Current**: Plain signal badges
**Missing**:
- Backend logic to detect priority conditions
- Frontend display of indicator icons

**Required Backend Logic**:
```python
# In refresh_processor.py or new priority_indicators.py
def calculate_priority_indicators(item, fundamentals, news, technical):
    indicators = []

    # 🔥 Hot Opportunity (score >85 + BUY signal)
    if item.overall_score > 85 and item.signal_type == "BUY":
        indicators.append("hot")

    # 📰 Breaking News (recent high-impact news)
    if news and news.impact_score > 0.7 and news.hours_ago < 24:
        indicators.append("breaking_news")

    # ⚡ Momentum (price >3%, volume spike)
    if item.change_pct > 3.0 and item.volume_relative > 1.5:
        indicators.append("momentum")

    # 📋 Earnings Alert (earnings within 7 days)
    if item.earnings_days_away and 0 <= item.earnings_days_away <= 7:
        indicators.append("earnings_alert")

    # 💎 Value Play (low P/E, high quality)
    if fundamentals and fundamentals.pe_ratio < 15 and fundamentals.quality_score > 70:
        indicators.append("value")

    # 📉 Negative Catalyst (recent bad news)
    if news and news.sentiment_score < -0.5:
        indicators.append("negative_catalyst")

    # 📈 Insider Buying (recent insider purchases)
    if fundamentals and fundamentals.insider_buying_recent:
        indicators.append("insider_buying")

    return indicators
```

**Frontend Display**:
```typescript
// In WatchlistTable.tsx Signal column
const indicatorIcons = {
  hot: "🔥",
  breaking_news: "📰",
  momentum: "⚡",
  earnings_alert: "📋",
  value: "💎",
  negative_catalyst: "📉",
  insider_buying: "📈"
};

// Display after signal badge
{item.priority_indicators?.map(indicator => (
  <span key={indicator}>{indicatorIcons[indicator]}</span>
))}
```

**Needs**: New task for this

---

### Gap 2: Rich Fundamental Metrics Display
**Design Shows**:
- "Revenue +24%, EPS +18%" (Growth section)
- "Gross: 18%, Operating: 12%, ROIC: 24%" (Profitability section)
- "P/E: 52 (premium but justified), PEG: 1.8" (Valuation section)
- "Institutional buying, analyst upgrades" (Momentum section)

**Current**: Just shows score numbers (e.g., "Growth: 92")

**Required Data Fields** (need to verify exist in backend):
```python
# FundamentalData model needs:
revenue_growth_yoy: float  # Year-over-year revenue growth %
eps_growth_yoy: float      # EPS growth %
gross_margin: float        # Gross profit margin %
operating_margin: float    # Operating profit margin %
roic: float                # Return on invested capital %
pe_ratio: float            # Price-to-earnings ratio
peg_ratio: float           # Price/earnings to growth
institutional_ownership: float  # % owned by institutions
analyst_ratings: dict      # Recent analyst ratings/upgrades
```

**Frontend Display**:
```typescript
// In ExpandedRow.tsx, replace simple score with rich detail
<div className="space-y-1 text-xs">
  <div className="font-medium">Growth: {item.fundamental.growth_score}</div>
  <div className="text-text-muted ml-2">
    • Revenue: +{(item.fundamental.revenue_growth * 100).toFixed(1)}% YoY
  </div>
  <div className="text-text-muted ml-2">
    • EPS: +{(item.fundamental.eps_growth * 100).toFixed(1)}% YoY
  </div>
</div>
```

**Needs**: More specific task with data field requirements

---

### Gap 3: News Intelligence - Missing Fields
**Design Shows**:
- "Articles (24h): 20" - Count of articles in last 24 hours
- "Coverage: High" - Coverage level (Low/Medium/High)
- "Key Events" list with dates and details

**Current**: Has headline and impact summary, missing counts and events

**Required Data**:
```python
# In news_intelligence or watchlist snapshot
recent_news_count_24h: int
recent_news_count_7d: int
news_coverage_level: str  # "Low" | "Medium" | "High"
key_events: list[dict]  # [{ date, type, description, impact }]
```

**Logic for Coverage Level**:
```python
def calculate_coverage_level(article_count_24h):
    if article_count_24h >= 15:
        return "High"
    elif article_count_24h >= 5:
        return "Medium"
    else:
        return "Low"
```

**Needs**: New task for news intelligence enhancements

---

### Gap 4: Price Data - Market Cap & Beta
**Design Shows**:
- "Mkt Cap: $768B"
- "Beta: 2.1"

**Current**: Have beta in snapshot, but not displayed. Market cap missing.

**Required**:
- Fetch market_cap from price service
- Display in Price Data section

**Needs**: Minor addition to existing display task

---

### Gap 5: Technical Indicators - Missing Some
**Design Shows**:
- SMA(50), SMA(200)
- Bollinger: "Upper band breakout"
- ATR: "$12.50"
- Trend: "Strong uptrend"

**Current**: Have RSI, MACD, trend. Missing SMA, Bollinger, ATR.

**Required Backend**:
```python
# In technical snapshot calculation
sma_50: float | None
sma_200: float | None
bollinger_upper: float | None
bollinger_lower: float | None
bollinger_status: str | None  # "Upper band breakout", "Lower band bounce", etc.
atr: float | None
```

**Needs**: Add to technical calculation task

---

### Gap 6: "Top 3 in watchlist" Ranking Display
**Design Shows**: "Overall: 85 (Top 3 in watchlist)"
**Current**: Just shows score number

**Required**:
- Client-side ranking logic
- Display rank if in top 5

**Implementation**:
```typescript
// In page.tsx, calculate rankings
const rankedItems = useMemo(() => {
  return [...items]
    .sort((a, b) => (b.current_score?.overall || 0) - (a.current_score?.overall || 0))
    .map((item, index) => ({ ...item, rank: index + 1 }));
}, [items]);

// In ExpandedRow.tsx
{item.rank <= 5 && (
  <span className="text-text-muted text-xs ml-2">
    (Top {item.rank} in watchlist)
  </span>
)}
```

**Needs**: Add to Phase 4

---

## 🔄 Updated Task Requirements

### NEW Phase 1.8: Priority Indicators Logic (Backend)
**Estimated**: 2 hours
**Agent**: Cloud

- [ ] Create `backend/app/watchlist/priority_indicators.py`
- [ ] Implement 7 indicator detection functions
- [ ] Add to refresh_processor.py
- [ ] Add `priority_indicators: list[str]` to WatchlistSnapshot
- [ ] Static analysis and commit

---

### NEW Phase 1.9: Priority Indicators Display (Frontend)
**Estimated**: 30 minutes
**Agent**: Cloud

- [ ] Add indicator icons to Signal column
- [ ] Update TypeScript types
- [ ] Visual design (spacing, tooltips)

---

### ENHANCED Phase 4.1: Rich Fundamental Display
**Add specifics**:
- [ ] Verify all fundamental fields exist in backend
  - revenue_growth_yoy
  - eps_growth_yoy
  - gross_margin, operating_margin, roic
  - pe_ratio, peg_ratio
  - institutional_ownership
  - analyst_ratings
- [ ] If missing: Add to FundamentalData model
- [ ] If missing: Update fundamentals fetch logic
- [ ] Display rich context in ExpandedRow.tsx:
  - Growth: Revenue %, EPS %
  - Profitability: Margins, ROIC
  - Valuation: P/E, PEG with context
  - Momentum: Institutional, analyst ratings

---

### NEW Phase 4.2: News Intelligence Enhancements
**Estimated**: 1 hour
**Agent**: Cloud → Local

- [ ] Add article count fields to backend
- [ ] Add coverage level calculation
- [ ] Add key events list structure
- [ ] Display in News Intelligence card

---

### NEW Phase 4.3: Technical Indicators Complete
**Estimated**: 1 hour
**Agent**: Cloud

- [ ] Add SMA(50), SMA(200) calculations
- [ ] Add Bollinger band calculations
- [ ] Add ATR calculation
- [ ] Display in Technical Indicators section

---

### NEW Phase 4.4: Watchlist Ranking Display
**Estimated**: 30 minutes
**Agent**: Cloud

- [ ] Add client-side ranking logic
- [ ] Display "Top N" badge in score breakdown
- [ ] Only show for top 5 items

---

## Summary of Additions Needed

**Total New Tasks**: 6 tasks
**Additional Time**: ~6 hours

**New Phase Breakdown**:
- Phase 1: +2 tasks (Priority Indicators) = 9 tasks total
- Phase 4: +4 tasks (Rich Details) = 5 tasks total

**New Total**: 30 tasks (~18-21 hours)

---

## Recommendation

**Option A: Include All Enhancements Now** (Recommended)
- Comprehensive from start
- Avoids future rework
- Cloud agent implements complete backend
- Total: 30 tasks, ~18-21 hours

**Option B: Defer Enhancements**
- Start with current 24 tasks
- Add enhancements as "Phase 6" later
- Gets basic UX done faster
- Risk: May never get polished

**I recommend Option A** - better to do it right once than iterate multiple times.

---

## Next Steps

1. Update task list with 6 new tasks
2. Reorganize into logical phases
3. Ensure cloud agent has clear data requirements
4. Provide updated handoff instructions
