# PRD 0021: Watchlist Narrative Intelligence

**Status**: Draft (Blocked by PRD 0020 - Foundational Fixes)
**Created**: 2025-10-31
**Owner**: Portfolio AI Platform
**Related PRDs**: #0014 (Watchlist Intelligence Hub Phase 1), #0018 (Watchlist Refresh Infrastructure Fixes), #0020 (Foundational Fixes - BLOCKING)

---

## Introduction / Overview

The current watchlist displays technical scores (62.5, 83.2, etc.) and trader jargon (RSI, MACD, EMA) that confuse users. Users see numbers but don't know the answer to the fundamental question: **"Should I buy, sell, or hold this stock?"**

This PRD transforms the watchlist from "interesting diagnostics" to "actionable trade recommendations" using a narrative-driven, story-telling approach with zero trader jargon. Each stock will tell a clear story combining technical setup + fundamental health + recent news into simple **Buy/Hold/Avoid** signals with specific entry/exit/stop levels and position sizing.

**The Vision**: Users scan the watchlist and immediately see 🟢 BUY or 🔴 AVOID. They click to expand and read a plain-language story explaining WHY (company health + news + technical setup), WHAT to do (specific prices), HOW MUCH to buy (exact shares), and WHEN to exit (stop loss + target).

---

## Goals

1. **Eliminate Confusion**: Replace technical scores with clear Buy/Hold/Avoid signals
2. **Provide Actionable Guidance**: Specify exact entry price, stop loss, and profit target
3. **Enable Position Sizing**: Calculate exact shares to buy based on risk budget
4. **Explain the "Why"**: Use fundamentals and news to contextualize technical signals
5. **Use Plain Language**: Zero trader jargon - translate everything into simple English
6. **Fix Data Integrity Bugs**: Build on solid foundation by fixing existing data issues first

---

## User Stories

### As a beginner investor...
- I want to see clear Buy/Hold/Avoid signals instead of scores, so I know what action to take
- I want to understand WHY a stock is recommended, so I can build confidence in the decision
- I want specific entry and exit prices, so I know exactly when to buy and sell
- I want to know how many shares to buy, so I can manage my risk properly

### As an intermediate trader...
- I want to see the reasoning behind each signal (technical + fundamental + news), so I can validate the recommendation
- I want position sizing based on dollar risk, so I maintain consistent risk per trade
- I want to know when signals change, so I can adjust positions accordingly
- I want earnings warnings, so I don't hold through volatility

### As the system...
- I need to fix data integrity bugs before building new features, so narratives are accurate
- I need to classify signals based on multiple indicators, so recommendations are robust
- I need to fetch fundamentals and news, so I can provide complete context
- I need to calculate position sizes automatically, so users don't have to do math

---

## Functional Requirements

### Phase 1: Fix Data Integrity (Foundation) - CRITICAL PRIORITY

#### FR-1.1: Fix History Endpoint Bug
**Current Issue**: History endpoint uses `fundamental_score` (not implemented) instead of extracting `price_score` from `raw_metrics` JSON
**Location**: `backend/app/api/watchlist.py:546-548`
**Requirement**: Parse `raw_metrics` JSONB field to extract `price.score` value
**Impact**: 7-day trend sparklines will display correct price score history
**Test**: GET `/api/watchlist/{item_id}/history` returns array with correct `price_score` values matching snapshots

#### FR-1.2: Fix Staleness Detection
**Current Issue**: Staleness calculated as `is_stale(fetched_at=now, now=now)` always returns False
**Location**: `backend/app/watchlist/service.py:376`
**Requirement**: Calculate staleness at display time using `snapshot.fetched_at` vs `current_time`
**Impact**: Stale badges appear correctly when data ages beyond TTL threshold
**Test**: Snapshot created 20 minutes ago with 15-minute TTL shows `is_stale=true`

#### FR-1.3: Expand Price Change Clamp
**Current Issue**: ±10% clamp loses signal for extreme moves (META -13.7% → clamped to -10% → score 0.0)
**Location**: `backend/app/watchlist/scoring.py:40`
**Requirement**: Change clamp from `±10%` to `±20%` to preserve extreme price move signals
**Impact**: Stocks with moves >10% retain meaningful differentiated scores
**Test**: Stock down 15% scores ~25 (not 0); stock up 18% scores ~90 (not 100)

---

### Phase 2: Narrative Signal Generation (Core Feature) - HIGH PRIORITY

#### FR-2.1: Signal Classification Engine
**Requirement**: Classify each watchlist item into one of three categories based on multiple indicators

**🟢 BUY Signal** = All of the following:
- Price > 20-day EMA (uptrend)
- RSI between 30-70 (not extreme)
- MACD > 0 (positive momentum)
- Volume >= 70% of 20-day average (healthy volume)
- Company health = EXCELLENT or GOOD (if fundamental data available)
- News sentiment >= 0.2 (positive or neutral, if news available)

**🟡 HOLD Signal** = Mixed conditions:
- Some positive, some negative indicators
- OR trending but no good entry point (RSI >70 overbought)
- OR quality company but poor technical timing

**🔴 AVOID Signal** = Any of the following:
- Price < 20-day EMA AND 5-day SMA declining (downtrend)
- News sentiment < -0.3 (significantly negative)
- Earnings within 5 days (high volatility risk)
- Company health = WEAK

**Signal Strength** (0-10 scale):
- Count number of confirming indicators
- BUY with 8+ confirmations = 9/10
- BUY with 5-7 confirmations = 6-8/10
- HOLD = 4-6/10
- AVOID with multiple red flags = 1-3/10

**Test**:
- NVDA (uptrend, pullback, positive MACD, good volume, strong fundamentals) → BUY 9/10
- META (down 13%, negative news, weak momentum) → AVOID 2/10

#### FR-2.2: Plain Language Narrative Generator
**Requirement**: Translate technical indicators into plain English narrative sections

**Technical → Plain Language Mapping**:
```python
NARRATIVE_TEMPLATES = {
    "uptrend": "Stock is in an uptrend (rising steadily)",
    "downtrend": "Stock is in a downtrend (declining)",
    "pullback": "Just pulled back to a good entry point",
    "breakout": "Breaking above key price level",
    "momentum_positive": "Momentum is positive (buyers are in control)",
    "momentum_negative": "Momentum is negative (sellers in control)",
    "volume_high": "Excellent volume - strong conviction",
    "volume_low": "Low volume - less conviction",
    "overbought": "Already extended - just hit new high",
    "oversold": "Oversold - potential bounce opportunity"
}
```

**Narrative Sections to Generate**:
1. **Headline**: `"{signal_type} - {reason}"` (e.g., "STRONG BUY - Quality Company + Good Setup")
2. **Company Health** (if available): 3-5 bullets with ✓✗⚠ indicators
3. **Recent News** (if available): 3-5 headlines with sentiment icons
4. **Technical Setup**: 3-5 plain-language technical reasons
5. **Action Plan**: Specific buy/sell/stop prices
6. **Position Sizing**: Shares, dollar investment, gain/loss potential
7. **Special Notes**: Warnings, tips, earnings alerts

**Test**: Generate narrative for AAPL, verify no jargon like "RSI", "MACD", "EMA" appears in user-facing text

#### FR-2.3: Entry/Exit/Stop Calculator
**Requirement**: Calculate actionable trade levels for each signal type

**Entry Price**:
- BUY signals: Current price (or breakout level if resistance near)
- HOLD signals: Wait for pullback to support OR breakout confirmation level
- AVOID signals: Recovery setup price (e.g., "Watch for stabilization at $640")

**Stop Loss** (choose tighter of):
- ATR-based: `entry_price - (2 × ATR_14)`
- Technical: Below recent swing low from last 10 days

**Profit Target**:
- First target: `entry_price + (2 × ATR_14)` (quick profit)
- Second target: Prior swing high from last 30 days (if exists)

**Display Format**:
```
What To Do:
• BUY around $202 - quality company at good entry
• EXIT if drops below $195 (protect capital)
• TAKE PROFIT at $216 (6.9% gain)
```

**Test**:
- NVDA at $202.49, ATR=$7.00 → Entry $202, Stop $195 ($202-2×3.5), Target $216 ($202+2×7)
- Verify stop is always BELOW entry, target ABOVE entry

#### FR-2.4: Position Sizing Calculator
**Requirement**: Calculate exact shares to buy based on user's risk budget and trade levels

**Formula**:
```python
position_size = risk_budget / (entry_price - stop_loss)
```

**User Preference** (stored in `user_preferences`):
- Default `watchlist_risk_budget = 500` (dollars)
- Allow user to adjust via settings (e.g., $250, $1000, $2000)

**Display Format**:
```
Position Sizing (for $500 risk):
• Buy 71 shares = $14,377 invested
• Potential gain: +$994 (+6.9%)
• Maximum loss: -$500 (-3.5%)
```

**Calculations**:
- Shares: `floor(risk_budget / (entry - stop))`
- Investment: `shares × entry_price`
- Potential gain: `shares × (target - entry)`
- Max loss: `shares × (entry - stop)` (should equal risk_budget)

**Test**:
- Entry $202, Stop $195, Target $216, Risk $500
- Shares = floor(500 / 7) = 71
- Investment = 71 × 202 = $14,342
- Gain = 71 × 14 = $994
- Loss = 71 × 7 = $497 (~$500)

---

### Phase 3: Fundamental & News Integration (Context) - HIGH PRIORITY

#### FR-3.1: Company Health Scoring
**Requirement**: Classify company fundamentals into EXCELLENT / GOOD / WEAK categories

**Data Sources** (multi-source failover):
- Primary: YFinance (free, no auth)
- Secondary: Finnhub (paid, requires FINNHUB_API_KEY)
- Tertiary: FMP (paid, requires FMP_API_KEY)

**Classification Rules**:

**EXCELLENT**:
- Profit margin > 20% AND revenue growth > 20% YoY
- Debt-to-equity < 0.5 (low debt)
- Analyst consensus: >70% buy ratings

**GOOD**:
- Profit margin > 5% AND revenue growth 5-20% YoY
- Debt-to-equity < 1.5 (manageable debt)
- Analyst consensus: 50-70% buy ratings

**WEAK**:
- Profit margin < 0% (unprofitable) OR revenue shrinking
- Debt-to-equity > 2.0 (high debt)
- Analyst consensus: <50% buy ratings

**Display Format**:
```
📊 Company Health: EXCELLENT
✓ Growing fast - Revenue up 122% this year
✓ Very profitable - Profit margins 53%
✓ Strong balance sheet - $26B cash, low debt
✓ Analysts love it - 47 buy, 3 hold, 0 sell
```

**Storage**: Add to `watchlist_snapshots`:
- `company_health` ENUM('EXCELLENT', 'GOOD', 'WEAK', NULL)
- Store details in `raw_metrics` JSONB field

**Test**:
- NVDA (margin 53%, growth 122%, low debt) → EXCELLENT
- Unprofitable startup (margin -15%, high debt) → WEAK

#### FR-3.2: News Headline Integration
**Requirement**: Fetch recent news headlines (last 7 days) and score sentiment

**Data Sources**:
- Primary: Google News RSS (free, no auth, no built-in sentiment)
- Sentiment: VADER library from nltk (free, finance-tuned)
- Optional enhancement: Claude API for nuanced sentiment

**Implementation**:
1. Fetch 10 most recent headlines for ticker
2. Score each headline with VADER: -1.0 (negative) to +1.0 (positive)
3. Categorize: ✓ Positive (>0.2), ✗ Negative (<-0.2), ~ Neutral (-0.2 to 0.2)
4. Display top 3-5 most relevant headlines with sentiment icons

**Display Format**:
```
📰 Recent News (Last 7 Days):
✓ Oct 30: New AI chip orders exceed expectations
✓ Oct 28: Major cloud provider signs $5B deal
~ Oct 26: Analyst raises price target to $250
```

**Storage**: Add to `watchlist_snapshots`:
- `news_sentiment_score` FLOAT (-1.0 to +1.0) - average of all headlines
- `recent_news_headlines` JSONB - array of {date, headline, sentiment, url}

**Caching**: Store fetched news in `reference_cache` with 6-hour TTL

**Test**:
- Positive headline "Beats earnings by 20%" → sentiment > 0.5
- Negative headline "CEO resigns amid scandal" → sentiment < -0.5

#### FR-3.3: Earnings Calendar Warning
**Requirement**: Display days until next earnings with risk warnings

**Data Sources** (multi-source failover):
- Primary: Finnhub `/calendar/earnings` API (free tier, 60 req/min)
- Secondary: YFinance `.earnings_dates` method (free, unlimited)

**Implementation**:
1. Fetch next earnings date for ticker
2. Calculate `days_until_earnings = (earnings_date - today).days`
3. Display appropriate warning based on proximity

**Warning Levels**:
- 0-5 days: 🔴 "EARNINGS IN 2 DAYS - High volatility expected"
- 6-14 days: ⚠ "Earnings in 10 days - Consider exiting before report"
- 15-30 days: 💡 "Earnings in 3 weeks - factor into timing"
- >30 days: No special warning, just display date

**Storage**: Add to `watchlist_snapshots`:
- `earnings_date` DATE
- `earnings_days_away` INTEGER

**Caching**: Store in `reference_cache` with 30-day TTL (earnings don't change frequently)

**Test**:
- Earnings on 2025-11-20, today 2025-10-31 → 20 days away → "Earnings in 3 weeks"
- Verify failover: If Finnhub fails, YFinance provides date

---

### Phase 4: Enhanced UX (Polish) - MEDIUM PRIORITY

#### FR-4.1: Multi-Scenario Guidance (HOLD Signals)
**Requirement**: For HOLD signals, show "what would make this buyable"

**Display Format**:
```
Two Entry Scenarios:

📈 SCENARIO 1 (Breakout):
   • IF breaks above $285 on high volume → BUY
   • Target: $295
   • Stop: $280

📉 SCENARIO 2 (Pullback):
   • IF drops to $275 with low volume → BUY
   • Target: $285
   • Stop: $270
```

**Logic**:
- Breakout scenario: Current resistance + 1 ATR above
- Pullback scenario: Current support OR 20-day EMA (whichever closer)

**Test**: HOLD signal shows 2 actionable scenarios with different entry prices

#### FR-4.2: Risk Type Indicators
**Requirement**: Flag different risk categories with visual warnings

**Risk Types**:
- ⚠ **High Volatility**: ATR > 5% of price (stock swings ±5%+ daily)
- ⚠ **Earnings Risk**: Earnings within 14 days
- ⚠ **Weak Fundamentals**: Company health = WEAK (trade only, don't invest)
- ⚠ **News Risk**: Negative news sentiment < -0.3
- 🚀 **High Confidence**: Signal strength 9-10/10 (all signals aligned)

**Display**: Show 1-2 most relevant risk indicators below action plan

**Test**:
- TSLA (ATR=$15, price=$456) → 3.3% → "⚠ High Volatility: Stock can swing ±3% daily"
- META (news sentiment -0.6, earnings in 10 days) → Both warnings shown

#### FR-4.3: Score Change Delta
**Requirement**: Show how signal strength changed in last 24 hours

**Implementation**:
- Query previous snapshot from 24 hours ago
- Calculate delta: `current_strength - previous_strength`
- Display with direction arrow

**Display Formats**:
- Table row: "Signal: 9/10 (+2 today)"
- Expanded: "Signal improved from 7/10 to 9/10 in last 24 hours"

**Test**: Signal was 7/10 yesterday, 9/10 today → shows "+2 today"

#### FR-4.4: Volume Analysis Enhancement
**Requirement**: Add relative volume context to narratives

**Formula**: `volume_ratio = current_volume / avg_20day_volume`

**Plain Language Mapping**:
- >150%: "Excellent volume - strong conviction"
- 100-150%: "Good volume - institutional interest"
- 70-100%: "Normal volume"
- 50-70%: "Low volume - less conviction"
- <50%: "Very low volume - be cautious"

**Integration**: Add volume context to "Technical Setup" bullets

**Test**: Volume 2M, 20-day avg 1M → 200% → "Excellent volume - strong conviction"

---

## Non-Goals (Out of Scope)

The following features are explicitly **NOT** included in this PRD:

- Sector rotation / relative strength ranking (too complex, low ROI for MVP)
- Portfolio correlation matrices (belongs in portfolio manager, not watchlist)
- Walk-forward backtesting (research tool, not production feature)
- Cash buffer policy enforcement (portfolio-level constraint)
- Mean-reversion strategies with Keltner channels (niche use case)
- Intraday 30-minute data integration (requires new data pipeline)
- Options strategies (equity long-only for now)
- Paper trading integration (separate feature in existing system)

These may be considered for future iterations but are deferred to manage scope.

---

## Design Considerations

### Database Schema Changes

**Extend `watchlist_snapshots` table** with new columns:

```sql
ALTER TABLE watchlist_snapshots ADD COLUMN IF NOT EXISTS
  signal_type TEXT CHECK(signal_type IN ('BUY', 'HOLD', 'AVOID')),
  signal_strength INTEGER CHECK(signal_strength BETWEEN 0 AND 10),
  narrative_headline TEXT,
  narrative_why_bullets JSONB,  -- array of reason strings
  narrative_action_plan TEXT,
  entry_price DOUBLE PRECISION,
  stop_loss DOUBLE PRECISION,
  profit_target DOUBLE PRECISION,
  position_size_shares INTEGER,
  company_health TEXT CHECK(company_health IN ('EXCELLENT', 'GOOD', 'WEAK')),
  earnings_date DATE,
  earnings_days_away INTEGER,
  news_sentiment_score DOUBLE PRECISION CHECK(news_sentiment_score BETWEEN -1.0 AND 1.0),
  recent_news_headlines JSONB;  -- array of {date, headline, sentiment, url}
```

**Extend `user_preferences` table**:

```sql
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS
  watchlist_risk_budget INTEGER DEFAULT 500,
  watchlist_price_clamp INTEGER DEFAULT 20,
  watchlist_show_news BOOLEAN DEFAULT true,
  watchlist_show_fundamentals BOOLEAN DEFAULT true;
```

### UI/UX Components

**Table Row** (collapsed):
- Symbol + Price
- Signal icon (🟢🟡🔴) + type text
- Signal strength (e.g., "9/10")
- Updated timestamp
- Expand arrow

**Expanded View Sections** (in order):
1. Headline (signal type + reason)
2. Signal strength bar (visual ████████░░)
3. Company Health (if available)
4. Recent News (if available)
5. Technical Setup
6. Action Plan (entry/stop/target)
7. Position Sizing
8. Special Notes (warnings, tips)
9. Last updated timestamp

**Color Coding**:
- 🟢 BUY: Green accent (#10b981)
- 🟡 HOLD: Yellow/amber accent (#f59e0b)
- 🔴 AVOID: Red accent (#ef4444)

---

## Technical Considerations

### Data Dependencies (Verified Available)

✅ **Technical Indicators** - Ready to use:
- Location: `backend/app/analytics/indicators.py`
- Available: RSI-14, MACD (with signal/histogram), SMA-20/50/200, EMA-20/50/200, ATR-14, Stochastic
- Storage: `technical_indicators` table (already populated)

✅ **Volume Data** - Ready to use:
- Location: `day_bars` table, column `volume` (BIGINT)
- RVOL calculation: `backend/app/analytics/volume.py`

⚠️ **Earnings Dates** - Needs implementation (1-2 hours):
- Primary source: Finnhub `/calendar/earnings` API
- Fallback: YFinance `.earnings_dates` method
- Storage: `reference_cache` table with 30-day TTL

⚠️ **News + Sentiment** - Needs implementation (2-3 hours):
- News source: Google News RSS (already configured)
- Sentiment: VADER library (`pip install vaderSentiment`)
- Optional: Claude API for enhanced sentiment
- Storage: `recent_news_headlines` JSONB field in snapshots

✅ **Fundamental Data** - Multi-source failover ready:
- YFinance (primary, free) → Finnhub (secondary) → FMP (tertiary)
- Metrics needed: profit margin, revenue growth, debt-to-equity, analyst ratings

### Performance Considerations

**API Response Time Target**: <500ms for watchlist endpoint

**Optimization Strategies**:
- Cache narratives in `watchlist_snapshots` (regenerate on Celery refresh)
- Cache fundamental data in `reference_cache` (24-hour TTL)
- Cache news in `reference_cache` (6-hour TTL)
- Use batch queries for technical indicators (already optimized)
- Pre-calculate position sizing (don't compute on-the-fly)

**Celery Integration**:
- Narrative generation happens during `refresh_watchlist_scores_task`
- Runs every 1-5 minutes (user preference) during market hours
- Ensures narratives stay fresh without impacting API response times

### Migration Path

**Phase 1 (Bugs)**: No migration needed, direct code fixes
**Phase 2-3 (Narratives)**: Run migration to add new columns to `watchlist_snapshots`
**Phase 4 (UX)**: No schema changes, frontend updates only

**Migration Script**: Create `backend/app/storage/migrations/005_narrative_intelligence.sql`

---

## Success Metrics

### User Experience Metrics

1. **Clarity**: 90%+ users can identify Buy/Hold/Avoid signal without reading expanded view
2. **Comprehension**: 85%+ users understand reasoning when reading expanded narrative
3. **Actionability**: 80%+ users know exact entry/stop/target prices for each signal
4. **Confidence**: 75%+ users feel confident executing trades based on narratives

### Technical Metrics

1. **Data Accuracy**:
   - History sparklines show correct price score trend (not fundamental_score)
   - Staleness detection works (stale badge appears after TTL expires)
   - Extreme price moves (>10%) retain signal (no clamping at 0 or 100)

2. **Performance**:
   - Watchlist API response time <500ms (95th percentile)
   - Celery refresh completes in <10 seconds for 14 tickers
   - News fetching doesn't block watchlist display

3. **Test Coverage**:
   - 90%+ coverage for signal classification logic
   - 85%+ coverage for narrative generation
   - 80%+ coverage overall for new code

4. **Data Quality**:
   - Fundamental data available for >80% of US large-cap stocks
   - News headlines updated within 15 minutes of publication
   - Earnings dates accurate for next 90 days (>95%)
   - Position sizing calculations mathematically correct (100%)

### Business Metrics

1. **Engagement**: 30%+ increase in time spent on watchlist page
2. **Trade Execution**: 20%+ increase in users executing trades from watchlist
3. **Retention**: 15%+ increase in daily active users checking watchlist
4. **Support**: 25%+ decrease in "what does this score mean?" support tickets

---

## Open Questions

1. **Multi-timeframe Analysis**: Should we add intraday (30-min) MACD confirmation for stronger signals? (Would require intraday data pipeline - currently out of scope)

2. **AI-Generated Narratives**: Should we use Claude API to generate fully custom narratives instead of templates? (Higher cost, potentially better quality, slower response)

3. **Backtesting**: Should we show "this signal type has 65% win rate historically" for confidence? (Requires backtesting infrastructure - currently out of scope)

4. **Alert Integration**: Should signals trigger mobile/email alerts when they change? (Nice-to-have, could be Phase 5)

5. **Multi-language Support**: Should narratives be translatable to other languages? (International expansion consideration)

6. **Confidence Calibration**: How do we validate that "9/10" signals actually outperform "5/10" signals? (Requires tracking and analysis)

---

## References

- **Current Bugs Analysis**: History endpoint (watchlist.py:546-548), staleness detection (service.py:376), price clamp (scoring.py:40)
- **Trading Playbook**: `~/portfolio-ai/stock_trading.md` (entry/exit/stop/target methodology)
- **Existing PRD**: #0014 Watchlist Intelligence Hub (Phase 1 complete, this is Phase 2 expansion)
- **User Feedback**: "Abstract confusing trader jargon, show simple buy/sell/hold reasoning"
- **Design Inspiration**: Clear signals (🟢🟡🔴), strength bars (█████), checkmarks (✓✗⚠)
- **Data Audit**: Research findings on technical indicators, volume, earnings, news sources

---

## Appendix: Example Narratives

### Example 1: Strong Buy (NVDA)

**Table Row**:
```
> NVDA  $202.49  🟢 BUY  Signal: 9/10  Updated: 2 min ago
```

**Expanded View**:
```
NVDA  $202.49  🟢 STRONG BUY - Quality Company + Good Setup

Signal Strength: █████████░ 9/10

📊 Company Health: EXCELLENT
✓ Growing fast - Revenue up 122% this year
✓ Very profitable - Profit margins 53%
✓ Strong balance sheet - $26B cash, low debt
✓ Analysts love it - 47 buy, 3 hold, 0 sell

📰 Recent News (Last 7 Days):
✓ Oct 30: New AI chip orders exceed expectations
✓ Oct 28: Major cloud provider signs $5B deal
~ Oct 26: Analyst raises price target to $250

📈 Technical Setup:
✓ Strong uptrend - making higher highs
✓ Healthy pullback - normal profit-taking
✓ Buyers active - momentum positive
✓ Excellent volume - strong conviction

What To Do:
• BUY around $202 - quality company at good entry
• EXIT if drops below $195 (protect capital)
• TAKE PROFIT at $216 (6.9% gain)

Position Sizing (for $500 risk):
• Buy 71 shares = $14,377 invested
• Potential gain: +$994 (+6.9%)
• Maximum loss: -$500 (-3.5%)

💡 WHY THIS WORKS: Technical setup + Strong fundamentals
   You're buying a great company at a good price

⚠ Next Earnings: Nov 20 (3 weeks) - could be volatile

Last updated: Oct 31, 9:02 PM EDT
```

### Example 2: Avoid Signal (META)

**Table Row**:
```
> META  $648.35  🔴 AVOID  Signal: 2/10  Updated: 2 min ago
```

**Expanded View**:
```
META  $648.35  🔴 AVOID - TOO RISKY RIGHT NOW

Signal Strength: ██░░░░░░░░ 2/10

📊 Company Health: GOOD (But Under Pressure)
✓ Still profitable - Strong margins
⚠ Growth slowing - User engagement declining
⚠ Regulatory pressure - EU fines, antitrust concerns
~ Analysts cautious - 28 buy, 15 hold, 3 sell

📰 Recent News (Last 7 Days): NEGATIVE
✗ Oct 30: EU announces $2B fine for privacy violations
✗ Oct 29: Advertising revenue misses estimates
✗ Oct 28: Several analysts downgrade ratings
✗ Oct 26: User growth slowest in 5 years

📈 Technical Setup:
✗ Sharp selloff - down 13.7% this week
✗ Breaking support levels - trend weakening
✗ Sellers dominant - negative momentum
⚠ High volume - institutional selling (not good)

What To Do:
• STAY AWAY - too much negative news
• If you own it: Consider selling on any bounce to $660
• DON'T try to catch falling knife

When It MIGHT Be Buyable Again:
• After news cycle calms down (2-3 weeks minimum)
• Price stabilizes around $640 for several days
• Volume dries up (selling exhaustion)
• New positive catalyst emerges

💡 WHY AVOID: Bad news is driving the selloff - not just
   technical weakness. Wait for dust to settle.

⚠ Next Earnings: Nov 15 (2 weeks) - likely to be rough

Last updated: Oct 31, 9:02 PM EDT
```

---

**END OF PRD**
