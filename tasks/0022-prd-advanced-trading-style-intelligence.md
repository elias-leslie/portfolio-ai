# PRD #0022: Advanced Trading Style Intelligence (v2 Enhancement)

**Status**: Ready for Implementation (after PRD #0021 complete)
**Depends On**: PRD #0021 (Watchlist Narrative Intelligence)
**Owner**: Portfolio AI
**Last Updated**: 2025-11-01
**Audience**: Junior developers

---

## 1. Introduction

PRD #0021 implements a **simplified** trading style classifier (v1) using basic heuristics:
- Index: Hardcoded ETF list
- Event: Earnings < 7 days
- Swing: RSI in reversal zones [30-40] or [60-70]
- Trend: Signal strength >= 8
- Value: Default fallback

**The Problem**: v1 is too simplistic and suffers from:
- **Inaccuracy**: Misclassifies stocks frequently (e.g., calls overbought stocks "Trend" when they're ready to reverse)
- **Lack of Adaptation**: Same rules apply in bull and bear markets
- **Missing Nuance**: Can't distinguish between similar setups (strong breakout vs weak bounce)

**The Solution**: Build v2 classifier with sophisticated detection algorithms that provide **professional-grade** recommendations by analyzing:
1. Momentum scoring (multi-timeframe rate of change)
2. Volatility regimes (trending vs choppy markets)
3. Support/resistance levels (key price zones)
4. Sector-relative valuation (using sector-specific fundamental metrics)

This will benefit **all users** (not just advanced traders) with more accurate, adaptive recommendations that match current market conditions.

---

## 2. Goals

1. **Improve classification accuracy**: Reduce misclassification rate from ~40% (v1 estimate) to <15% (v2 target)
2. **Adapt to market conditions**: Detect volatility regimes and adjust style recommendations accordingly
3. **Add nuance**: Distinguish between similar setups with confidence scoring
4. **Maintain simplicity**: Keep user-facing language plain (no jargon), complexity hidden in backend
5. **Enable user choice**: Let users toggle between v1 (simple) and v2 (advanced) in settings

---

## 3. User Stories

- As an active trader, I want accurate style classifications so I don't enter Swing trades during trending markets
- As a user, I want the system to adapt to market volatility so recommendations match current conditions
- As a user, I want to understand WHY a stock is classified as Trend vs Swing with clear explanations
- As a user, I want to choose between simple (v1) and advanced (v2) mode in settings based on my experience level
- As a user, I want confidence scores (0-10) so I know when the system is uncertain
- As an investor, I want sector-relative valuations so "Value" classifications compare stocks to their sector peers

---

## 4. Functional Requirements

### Implementation Priority (Easiest → Hardest)

#### FR-1: Momentum Scoring (PRIORITY 1 - Easiest)

**Goal**: Calculate multi-timeframe momentum to distinguish strong trends from weak bounces

**Implementation**:
- Calculate rate of change (ROC) at 3 timeframes: 10-day, 20-day, 60-day
- Formula: `ROC = ((close_today - close_N_days_ago) / close_N_days_ago) × 100`
- Momentum score (0-100): Normalize using percentile rank vs historical 250-day distribution
- Classify momentum strength:
  - **Strong up**: All 3 timeframes > 60th percentile → Strong Trend candidate
  - **Moderate up**: 2 of 3 timeframes > 50th percentile → Moderate Trend
  - **Neutral**: Mixed signals → Value or Hold candidate
  - **Moderate down**: 2 of 3 timeframes < 40th percentile → Avoid or contrarian Value
  - **Strong down**: All 3 timeframes < 30th percentile → Avoid

**Data Requirements**:
- Historical close prices (already have in `day_bars` table)
- 250 days of history for percentile calculation

**Success Criteria**:
- Momentum score accurately reflects trend strength
- Strong momentum (80+ score) correlates with continued price movement
- Manual review: 20 high-momentum stocks continue trending for 10+ days

---

#### FR-2: Volatility Regime Detection (PRIORITY 2 - Easy)

**Goal**: Detect if stock is in trending vs choppy (range-bound) environment

**Implementation**:
- Use ATR (Average True Range) 14-day percentile
- Calculate ATR percentile vs own 250-day history
- Classify regime:
  - **Low volatility** (ATR < 25th percentile): Range-bound → Swing or Index candidate
  - **Normal volatility** (ATR 25th-75th percentile): Normal trending → Trend or Value
  - **High volatility** (ATR > 75th percentile): Choppy or explosive → Event or Avoid
- **Bollinger Band Width** (secondary signal):
  - Narrow bands (< 25th percentile): Compression → Swing breakout candidate
  - Wide bands (> 75th percentile): Expansion → Trend or Event

**Data Requirements**:
- ATR-14 (already required in PRD #0021 Task 1.4)
- Bollinger Bands (calculate: 20-day SMA ± 2 std deviations)

**Success Criteria**:
- Low-vol stocks correctly identified as Swing candidates
- High-vol stocks flagged as Event or Avoid during earnings/news
- Volatility regime matches visual chart inspection (manual review of 20 stocks)

---

#### FR-3: Support/Resistance Detection (PRIORITY 3 - Medium)

**Goal**: Identify key price levels where stock has reversed or consolidated

**Implementation (Simple Approach - High Success Probability)**:
- **Support**: Price level touched 2+ times in last 60 days where stock bounced (low within 2% of prior low)
- **Resistance**: Price level touched 2+ times in last 60 days where stock reversed (high within 2% of prior high)
- Algorithm:
  1. Find all local minima (lows) and maxima (highs) in 60-day window
  2. Group touches within 2% price range
  3. Support = strongest cluster of lows (3+ touches)
  4. Resistance = strongest cluster of highs (3+ touches)
- **Near support**: Current price within 3% above support → Swing buy candidate
- **Near resistance**: Current price within 3% below resistance → Swing exit or Hold
- **Breakout**: Price breaks above resistance with volume > 1.5× avg → Trend candidate
- **Breakdown**: Price breaks below support → Avoid

**Data Requirements**:
- 60 days of OHLC data (have in `day_bars`)
- Volume data for breakout confirmation

**Success Criteria**:
- Detected support/resistance levels align with visual chart inspection (20 stocks)
- Stocks "near support" bounce >60% of the time within 5 days
- Breakouts above resistance with volume continue trending

---

#### FR-4: Sector-Relative Valuation (PRIORITY 4 - Hard)

**Goal**: Compare stock valuation to sector peers using sector-specific fundamental metrics

**Implementation**:
- **Use Sector Fundamental Metric Map from PRD #0014** (see Appendix)
- For each stock:
  1. Determine sector/sub-sector (from yfinance info or manual mapping)
  2. Fetch sector-specific valuation metrics (e.g., Tech Software uses EV/Sales, Banks use P/TBV)
  3. Calculate stock's z-score: `(stock_metric - sector_median) / sector_stdev`
  4. Value classification:
     - **Cheap** (z-score < -1.0): Strong Value candidate
     - **Fair** (z-score -1.0 to +0.5): Neutral
     - **Expensive** (z-score > +1.0): Growth/Momentum play, not Value
- **Combine with quality metrics**:
  - High quality (profit margin > 15%, low debt) + cheap = Strong Value
  - Low quality + cheap = Value trap → Avoid or low confidence
  - High quality + expensive = Quality Growth → Trend candidate if momentum strong

**Data Requirements**:
- Sector classification for each ticker
- Sector-specific fundamental ratios (P/E, EV/Sales, P/TBV, etc.)
- Sector peer group for median/stdev calculation (top 20 stocks by market cap in sector)
- Quality metrics: Profit margin, debt-to-equity, revenue growth

**Success Criteria**:
- Stocks classified as "Value" trade at discount vs sector peers (z-score < -0.5)
- Sector-specific metrics used correctly (Tech uses EV/Sales, not P/E)
- Manual review: 20 "Value" stocks are actually undervalued vs peers

---

### FR-5: Enhanced Classification Logic (Integrates FR-1 through FR-4)

**New Classification Hierarchy** (replaces v1 simple heuristics):

1. **Index** (unchanged):
   - Symbol in: `['SPY', 'VOO', 'VTI', 'QQQ', 'IWM', 'DIA', 'AGG', 'BND', 'VEA', 'VWO', 'GLD', 'SLV']`
   - Timeframe: Hold indefinitely
   - Risk: Low
   - Confidence: 10/10 (hard-coded list)

2. **Event** (enhanced):
   - **Primary**: Earnings < 7 days
   - **Secondary**: High volatility (ATR > 90th percentile) + news spike (sentiment score changed >0.3 in 24 hours)
   - Timeframe: Days to weeks
   - Risk: High
   - Confidence: 9/10 if earnings, 6/10 if news-driven

3. **Swing** (enhanced):
   - **Primary**: Near support (price within 3% above support) + low volatility regime (ATR < 40th percentile)
   - **Secondary**: RSI in [30-40] (oversold bounce) or [60-70] (overbought fade)
   - **Tertiary**: Bollinger Band squeeze (band width < 25th percentile) → compression breakout pending
   - Timeframe: 1-3 weeks
   - Risk: Medium
   - Confidence: 8/10 if near support, 6/10 if RSI-only, 5/10 if BB squeeze

4. **Trend** (enhanced):
   - **Primary**: Strong momentum (all 3 timeframes > 60th percentile) + breakout above resistance with volume
   - **Secondary**: Signal strength >= 8 (from PRD #0021) + normal/high volatility (trending, not ranging)
   - **Tertiary**: Price > 50-day MA + MACD > 0 + momentum score > 70
   - Timeframe: 2-3 months
   - Risk: Medium
   - Confidence: 9/10 if breakout + momentum, 7/10 if signal strength only

5. **Value** (enhanced):
   - **Primary**: Sector-relative cheap (z-score < -1.0) + high quality (profit margin > 15%, debt manageable)
   - **Secondary**: Company health = EXCELLENT/GOOD (from PRD #0021 fundamentals) + weak momentum (< 40th percentile)
   - **Fallback**: None of the above (default as in v1)
   - Timeframe: 6-12 months
   - Risk: Medium-Low
   - Confidence: 8/10 if sector-relative + quality, 5/10 if fundamentals only, 3/10 if fallback

---

### FR-6: Confidence Scoring (Confirming Signals Approach)

Count confirming signals for each style classification:

**Index**: Always 10/10 (hardcoded list)

**Event**:
- Earnings < 7 days: +5 points
- Earnings < 3 days: +3 points (total 8)
- High volatility (ATR > 90th percentile): +2 points
- News sentiment spike (>0.3 change in 24h): +2 points
- Max confidence: 10/10

**Swing**:
- Near support (within 3%): +4 points
- Support touched 3+ times (strong level): +2 points
- Low volatility (ATR < 40th percentile): +2 points
- RSI in reversal zone [30-40] or [60-70]: +2 points
- Bollinger Band squeeze: +2 points
- Max confidence: 10/10 (but requires 8+ points for Strong Swing)

**Trend**:
- Strong momentum (3/3 timeframes positive): +4 points
- Breakout above resistance + volume: +3 points
- Signal strength >= 8: +2 points
- Price > 50-day MA: +1 point
- MACD > 0: +1 point
- Momentum score > 70: +2 points
- Max confidence: 10/10 (requires 8+ for Strong Trend)

**Value**:
- Sector-relative cheap (z-score < -1.0): +4 points
- High quality fundamentals: +3 points
- Company health EXCELLENT: +2 points
- Weak momentum (< 40th percentile): +1 point (contrarian value)
- Max confidence: 10/10

**General Rule**: Confidence >= 8 = High confidence, 6-7 = Medium, <= 5 = Low

---

### FR-7: User Preferences - Classifier Version Selection

Add to Settings page (Watchlist Preferences section):

**"Trading Style Classification Mode"**:
- Radio buttons:
  - ( ) **Simple** (v1): Basic heuristics, fast, easy to understand
  - ( ) **Advanced** (v2): Sophisticated detection, higher accuracy, adaptive to market conditions

- **Default**: Simple (v1) for existing users, Advanced (v2) for new users
- **Save to** `user_preferences` table: `watchlist_style_classifier_version: 'v1' | 'v2'`
- **UI Note**: "Advanced mode uses momentum, volatility, support/resistance, and sector analysis for more accurate recommendations"

---

## 5. Non-Goals (Out of Scope for v2)

Deferred to v3 or beyond:

- **Real-time streaming data** (< 1 minute): Stick with 15-minute delayed data
- **Machine learning pattern recognition**: Defer complex ML (LSTM, neural networks) to v3
- **Custom user-defined patterns**: Power user feature for v3
- **Backtesting engine**: Separate tool, not part of watchlist
- **Automated performance tracking**: v3 will track v1 vs v2 with paper trading and Sharpe ratio analysis
- **Intraday timeframes**: Stick with daily data only
- **Options-specific styles** (straddles, iron condors): Equity-focused only

---

## 6. Technical Considerations

### Data Requirements (Auto-Discovery)

**Already Available**:
- Historical OHLC data: `day_bars` table (60-250 days needed)
- ATR-14: Being added in PRD #0021 Task 1.4
- RSI, MACD, SMA: `technical_indicators` table

**Need to Add**:
- **Sector classification**: Add `sector` column to watchlist_items or fetch from yfinance `info.sector`
- **Sector peer groups**: Pre-compute top 20 stocks by market cap per sector (stored in `sector_peers` table)
- **Sector median metrics**: Cache sector median P/E, EV/Sales, etc. in `sector_benchmarks` table (updated daily)
- **Bollinger Bands**: Calculate 20-day SMA ± 2 std deviations (add to `technical_indicators` table)

**Caching Strategy**:
- Momentum scores: Recalculate daily (after market close), cache in `technical_indicators`
- Volatility percentiles: Recalculate daily, cache with ATR
- Support/resistance levels: Recalculate weekly (computationally expensive), cache in `price_levels` table
- Sector valuations: Recalculate daily (fundamentals update slowly)

### Performance Goals

- **Latency**: No hard limit, but aim for <2 seconds per ticker for style classification
- **Accuracy priority**: Accuracy > speed (allow batch processing if needed)
- **Exception**: Event style needs <500ms (users checking earnings urgently)
- **Batch mode**: Celery task can process all watchlist items in background (15 min refresh)

### Database Schema Additions

**New tables**:

```sql
-- Support/resistance levels
CREATE TABLE price_levels (
  ticker TEXT NOT NULL,
  level_type TEXT CHECK(level_type IN ('support', 'resistance')),
  price_level DOUBLE PRECISION NOT NULL,
  touch_count INTEGER NOT NULL,
  strength_score INTEGER CHECK(strength_score BETWEEN 0 AND 10),
  last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ticker, level_type, price_level)
);

-- Sector benchmarks (medians for relative valuation)
CREATE TABLE sector_benchmarks (
  sector TEXT NOT NULL,
  metric_name TEXT NOT NULL,  -- 'forward_pe', 'ev_sales', 'p_tbv', etc.
  median_value DOUBLE PRECISION,
  stdev_value DOUBLE PRECISION,
  peer_count INTEGER,  -- Number of stocks in calculation
  as_of_date DATE NOT NULL,
  PRIMARY KEY (sector, metric_name, as_of_date)
);

-- Sector peer groups
CREATE TABLE sector_peers (
  sector TEXT NOT NULL,
  ticker TEXT NOT NULL,
  market_cap BIGINT,  -- For ranking
  rank_in_sector INTEGER,
  PRIMARY KEY (sector, ticker)
);
```

**Extend existing tables**:

```sql
-- Add to technical_indicators table
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS bollinger_upper DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS bollinger_lower DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS bollinger_width DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS momentum_10d DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS momentum_20d DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS momentum_60d DOUBLE PRECISION;
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS momentum_score DOUBLE PRECISION;  -- 0-100
ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS volatility_regime TEXT CHECK(volatility_regime IN ('low', 'normal', 'high'));

-- Add to watchlist_items table
ALTER TABLE watchlist_items ADD COLUMN IF NOT EXISTS sector TEXT;
ALTER TABLE watchlist_items ADD COLUMN IF NOT EXISTS sub_sector TEXT;
```

---

## 7. Success Metrics

**Manual Accuracy Review** (Primary):
- Sample 100 tickers across all styles
- Manual expert review: Does classification make sense based on chart/fundamentals?
- Target: >85% accuracy (vs estimated 60% for v1)

**Future Automated Tracking** (v3 - noted for implementation later):
- **Paper trading performance**: Track Sharpe ratio of v2 style recommendations vs v1
- **Backtesting**: Historical accuracy of style changes (did Swing → Trend correctly predict continuation?)
- **User feedback**: Survey "Are v2 recommendations more helpful than v1?" (target: 80% yes)

---

## 8. Dependencies & Preconditions

**Must Complete First**:
- PRD #0021 complete (v1 classifier, narrative system, fundamentals module)
- Task 1.4-1.5 from PRD #0021: EMA-20, ATR-14, swing low/high detection

**Required Data**:
- Sector classification for all watchlist tickers
- 250 days of historical OHLC data (for percentile calculations)
- Sector peer groups (top 20 stocks per sector by market cap)

---

## 9. Implementation Plan

**Phase 1: Momentum & Volatility** (Easiest, Highest ROI):
1. Add momentum calculations (10/20/60-day ROC) to `technical_indicators`
2. Add Bollinger Bands calculation
3. Implement volatility regime detection (ATR percentile)
4. Update classification logic to use momentum + volatility
5. Test: Verify Trend classifications have strong momentum, Swing has low volatility

**Phase 2: Support/Resistance** (Medium complexity):
1. Implement local minima/maxima detection
2. Cluster price levels (2% tolerance)
3. Store in `price_levels` table
4. Update Swing classification to check "near support"
5. Update Trend classification to check "breakout above resistance"
6. Test: Verify support/resistance levels match visual charts

**Phase 3: Sector Valuation** (Hardest):
1. Add sector classification to watchlist items
2. Create sector peer groups (top 20 per sector)
3. Calculate sector medians for relevant metrics (use PRD #0014 map)
4. Implement z-score calculation
5. Update Value classification to use sector-relative metrics
6. Test: Verify Value stocks are actually cheap vs sector peers

**Phase 4: Settings Integration**:
1. Add "Classifier Version" radio buttons to Settings page
2. Store preference in `user_preferences` table
3. Update backend to respect user preference (v1 vs v2)
4. Test: Toggle between v1 and v2, verify classifications change

---

## 10. Open Questions

1. **Sector classification source**: Use yfinance `info.sector` or maintain manual mapping? (Recommendation: Start with yfinance, add manual override later)
2. **Support/resistance refresh frequency**: Daily, weekly, or on-demand? (Recommendation: Weekly batch job, on-demand for individual ticker)
3. **Momentum lookback for percentiles**: 250 days or 500 days? (Recommendation: 250 days = 1 year, sufficient for most stocks)
4. **Value fallback behavior**: If sector valuation data unavailable, fall back to v1 logic? (Recommendation: Yes, graceful degradation)
5. **Confidence threshold for display**: Show style only if confidence >= 6? (Recommendation: Show all, but badge low-confidence as "Uncertain")

---

## Appendix: Sector Fundamental Metric Map

**Reference**: See PRD #0014 Appendix for complete sector-specific valuation metrics.

**Key sectors for v2 implementation** (prioritize most common stocks):
1. **Info Tech (Software)**: EV/Sales vs sector median
2. **Info Tech (Hardware/Semi)**: Forward P/E vs sector median
3. **Consumer Discretionary**: Forward P/E vs sector median
4. **Health Care (Pharma)**: EV/EBITDA vs sector median
5. **Financials (Banks)**: Price/Tangible Book vs sector median

**Fallback**: If sector not in map, use generic Forward P/E vs S&P 500 median.

---

**End of PRD #0022**
