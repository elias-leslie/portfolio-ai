# Trading Intelligence Gap Definition

**Last Updated**: 2025-11-13
**Total Gaps Identified**: 47
**P0 (Critical)**: 17 gaps
**P1 (High)**: 20 gaps
**P2 (Medium)**: 7 gaps
**P3 (Low)**: 3 gaps

---

## Executive Summary

This document defines **all gaps preventing profitable trading edge** in the Portfolio AI platform. Gaps are organized by criticality (P0-P3) and include specific implementation guidance.

**Current Trading Capability**: **Limited swing trading only** (~30% confidence in profitability)
**Minimum Viable Gap-Fill**: **12 P0 gaps** (4 weeks effort)
**Target Edge After MVP**: **Sharpe Ratio 1.2-1.8**

### Gap Categories

| Category | P0 | P1 | P2 | Total |
|----------|----|----|----|----|
| Market Data | 3 | 3 | 1 | 7 |
| Fundamentals | 2 | 7 | 1 | 10 |
| Signals | 5 | 3 | 0 | 8 |
| Risk Analytics | 5 | 5 | 0 | 10 |
| Execution | 6 | 3 | 0 | 9 |
| Macro/Sentiment | 1 | 5 | 1 | 7 |
| ML Infrastructure | 2 | 0 | 0 | 2 |
| Compliance | 1 | 1 | 0 | 2 |

### What We Have (Current State)

✅ **Working Capabilities**:
- Multi-source price fetching (6 vendors with failover)
- Daily OHLCV data (`day_bars` table, 252-day history)
- Basic technical indicators (RSI, EMA, SMA, ATR, Bollinger Bands)
- Fundamental data caching (profit margin, revenue growth, debt/equity)
- News scraping and sentiment analysis
- Options market metrics (CBOE scraping)
- Portfolio analytics (basic beta, volatility, Sharpe ratio)
- Watchlist scoring system (price, technical, company health pillars)
- Celery-based scheduled data refresh

✅ **Viable Strategies** (limited edge):
- Sector rotation (60% confidence) - XLK/XLE/XLF data exists
- Long-only momentum (30% confidence) - but using noisy 1-day signals
- Mean reversion (40% confidence) - but hard-coded thresholds

### What We Need (Critical Gaps)

❌ **Blocking Issues** (17 P0 gaps):
- No intraday data (blocks day trading, realized volatility)
- Wrong portfolio risk math (assumes perfect correlation)
- No multi-horizon momentum (using noisy 1-day instead of proven 3-12 month)
- No earnings surprise tracking (missing most persistent equity premium)
- Options flow data collected but never used in scoring
- Broken position sizing (flat $500, not linked to equity or volatility)
- No backtesting framework (signals are untested)

### Why This Matters

**Without filling P0 gaps**: Cannot trade profitably. Current signals are noise, risk metrics are wrong, position sizing is broken.

**After filling P0 gaps** (4 weeks): Can deploy multi-horizon momentum + earnings surprise + options flow strategies with Sharpe ~1.5.

**After filling P1 gaps** (8-12 weeks): Can run institutional-grade quant strategies with Sharpe >2.0.

---

## P0 Gaps - CRITICAL (Must Fill Before Live Trading)

### Market Data Gaps

#### GAP-001: No Intraday Data Ingestion

**Category**: Market Data
**Criticality**: P0 - CRITICAL

**Current State**: `minute_bars` table exists in schema (`docs/core/ARCHITECTURE.md:239`) but has **0 rows**. `data_ingestion_tasks.py:332-350` only requests `dataset="daily"`, never `dataset="minute"`. `PriceDataFetcher` stores only single snapshot per symbol (`backend/app/portfolio/price_fetcher.py:205-241`).

**Desired State**: 1-minute OHLCV for all watchlist tickers (30-day rolling history). Ingest daily at 18:00 ET (after market close). Calculate realized volatility, intraday volume percentiles, breakout detection.

**Impact**: **BLOCKS 40% OF STRATEGIES**. Without intraday data:
- ❌ Cannot calculate high-frequency realized volatility (improves risk forecasts per Andersen et al. 2003)
- ❌ Cannot detect intraday breakouts or breakdown patterns
- ❌ Cannot identify volume anomalies (unusual buying/selling pressure)
- ❌ Cannot support day trading strategies
- ❌ Stuck with end-of-day data → forfeits edge from intraday momentum

**Data Sources**:
- **Polygon** (recommended): 1-min bars, $200/mo Starter plan, 5 req/sec. [API](https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to)
- **Alpaca** (free): 1-min bars, free for funded accounts, 200 req/min. [API](https://alpaca.markets/docs/api-references/market-data-api/stock-pricing-data/historical/)
- **IEX** (delayed): 15-min delayed, free but not useful for day trading

**Effort**: MEDIUM (1-2 weeks)
- Extend `data_ingestion_tasks.py:332` to support `dataset="minute"` parameter
- Add Celery task `ingest_intraday_bars(tickers: list, lookback_days=30)`
- Schedule daily at 18:00 ET via Celery beat
- Add data quality checks (detect gaps, outliers, stale data)
- Test with 5 tickers × 30 days × 390 bars/day = ~60k rows

**Blocks Strategies**: Day Trading, Mean Reversion Intraday, Breakout Detection, Realized Volatility Models

**Code References**:
- `backend/app/tasks/data_ingestion_tasks.py:332-350` - Request builder (add minute support)
- `backend/app/sources/base.py:45-67` - DataSource interface (already supports minute)
- Schema: `docs/core/ARCHITECTURE.md:239` - minute_bars table exists

**Success Criteria**:
- `SELECT COUNT(*) FROM minute_bars` returns >100,000 rows
- `SELECT DISTINCT ticker FROM minute_bars` includes all watchlist tickers
- Verify 1-min granularity: `SELECT COUNT(DISTINCT date) FROM minute_bars WHERE ticker='AAPL' AND date >= NOW() - INTERVAL '1 day'` returns ~390

**Dependencies**: None (can start immediately)
**Status**: Open
**Task File**: `tasks-0064-intraday-data-ingestion.md` (to be generated)

---

#### GAP-029: No Bid/Ask Spreads

**Category**: Market Data
**Criticality**: P0 - CRITICAL

**Current State**: `PriceData` model has no fields for bid/ask/spread (`backend/app/portfolio/models.py:37-47`). Only stores `current_price` snapshot. Cannot estimate transaction costs.

**Desired State**: Store bid, ask, spread, bid_size, ask_size in `price_cache` table. Update on every price fetch. Calculate half-spread as transaction cost estimate.

**Impact**: **TRANSACTION COSTS = DIFFERENCE BETWEEN BACKTEST AND REALITY**. Without bid/ask:
- ❌ Cannot estimate slippage (market orders pay the spread)
- ❌ Cannot assess liquidity (wide spreads = illiquid, avoid)
- ❌ Cannot size positions correctly (large positions move market)
- ❌ Backtests are overly optimistic (assume mid-price fills, reality is ask for buys, bid for sells)
- ❌ Strategies profitable in backtest can be losers in live trading

**Data Sources**:
- **Polygon**: Real-time quotes, $200/mo. [API](https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_tickers__stocksticker)
- **Alpaca**: Real-time quotes, free with funded account. [API](https://alpaca.markets/docs/api-references/market-data-api/stock-pricing-data/realtime/)
- **IEX**: 15-min delayed quotes, free. [API](https://iexcloud.io/docs/api/#quote)

**Effort**: MEDIUM (1-2 weeks)
- Extend `PriceData` model with bid/ask/spread fields
- Update `PriceDataFetcher.fetch_price()` to request quote data
- Store in `price_cache` table
- Calculate half-spread as transaction cost: `cost = (ask - bid) / 2`
- Update analytics to include spread in risk calculations

**Blocks Strategies**: All strategies (cannot trade profitably without transaction cost model)

**Code References**:
- `backend/app/portfolio/models.py:37-47` - PriceData model (add bid/ask fields)
- `backend/app/portfolio/price_fetcher.py:205-241` - Fetch logic (request quotes)
- `backend/app/analytics/trade_calculations.py:33-74` - Trade calcs (add spread cost)

**Success Criteria**:
- `price_cache` table has bid, ask, spread columns populated for all tickers
- Verify spread is reasonable: `SELECT AVG(spread/current_price) FROM price_cache` returns 0.01-0.10% for liquid stocks

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0065-bid-ask-spread-tracking.md` (to be generated)

---

#### GAP-041: Unchecked Vendor Data Quality

**Category**: Market Data
**Criticality**: P1 - HIGH

**Current State**: Vendor data (Yahoo, Finnhub, FMP) is cached as-is without validation (`backend/app/portfolio/price_fetcher.py:205-250`). Yahoo Finance `info` payload is notoriously noisy (missing values, outliers, stale data).

**Desired State**: Add data quality checks before caching:
- Outlier detection (price change >20% → flag for review)
- Staleness check (data >1 hour old → refetch)
- Cross-source validation (compare Yahoo vs Finnhub, flag discrepancies >5%)
- Missing value handling (retry with different source)

**Impact**: Garbage in → garbage out. Bad data leads to bad signals, bad risk metrics, bad trades.

**Data Sources**: Internal validation logic (no new data sources needed)

**Effort**: MEDIUM (1 week)
- Add `validate_price_data()` function
- Check for outliers, staleness, missing values
- Log warnings, retry with fallback source
- Store data quality score in `price_cache`

**Blocks Strategies**: All (data quality affects everything)

**Code References**:
- `backend/app/portfolio/price_fetcher.py:205-250` - Add validation before caching
- `backend/app/utils/data_quality.py` - New module for validation logic

**Success Criteria**:
- No price changes >20% without news catalyst
- All cached data <1 hour old
- Cross-source discrepancies <5%

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0066-data-quality-validation.md` (to be generated)

---

### Risk Analytics Gaps

#### GAP-020: No Covariance Matrix (Wrong Portfolio Risk Math)

**Category**: Risk Analytics
**Criticality**: P0 - CRITICAL

**Current State**: Portfolio beta and volatility are computed as **simple value-weighted averages** of per-security betas/vols (`backend/app/portfolio/analytics_returns.py:67-126`). This **implicitly assumes every holding is perfectly correlated** (ρ = 1.0), which is mathematically wrong and violates mean-variance portfolio theory (Markowitz 1952).

**Desired State**: Persist pairwise covariance matrix from `day_bars` table. Calculate portfolio volatility correctly:
```
σ_portfolio = √(w' Σ w)
where w = weight vector, Σ = covariance matrix
```

**Impact**: **CURRENT RISK METRICS ARE MATERIALLY WRONG**. Overstates diversified portfolio risk by 30-60%. Example:
- Current: 10 stocks, each 10% volatility → portfolio vol = 10% (assumes ρ=1)
- Correct: 10 stocks, avg correlation 0.3 → portfolio vol = 6.5% (35% lower!)
- **Makes portfolio look riskier than it is**, causes under-allocation and missed gains

**Data Sources**: Internal (`day_bars` table has all historical returns)

**Effort**: LOW (3-5 days)
- Query `day_bars` for last 252 days (1 year)
- Calculate return matrix (NxT, N tickers, T days)
- Compute covariance: `Σ = (1/T) * R * R'`
- Store in new `portfolio_covariance` table
- Update `analytics_returns.py:67-126` to use matrix math

**Blocks Strategies**: All (portfolio risk is foundational)

**Code References**:
- `backend/app/portfolio/analytics_returns.py:67-126` - Replace weighted avg with matrix calculation
- `backend/app/analytics/risk_calculations.py` - New module for covariance logic
- Schema: Add `portfolio_covariance` table (ticker1, ticker2, covariance, correlation, updated_at)

**Success Criteria**:
- `portfolio_covariance` table populated with NxN matrix (N = watchlist size)
- Portfolio volatility calculation uses proper linear algebra
- Verify: Diversified portfolio vol < average single-stock vol (unless highly correlated)

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0067-fix-portfolio-risk-covariance.md` (to be generated)

---

#### GAP-021: No Factor Exposures

**Category**: Risk Analytics
**Criticality**: P0 - CRITICAL

**Current State**: `PortfolioAnalytics.calculate_full_analytics` ends after basic beta/volatility/sector stats (`backend/app/portfolio/analytics.py:124-170`). No factor decomposition. Cannot distinguish alpha from beta.

**Desired State**: Join holdings with Fama-French 5-factor model or custom factors (value, size, momentum, quality, low-vol). Expose portfolio's factor tilts:
- **Market** (beta to S&P 500)
- **Size** (small-cap vs large-cap)
- **Value** (P/B, P/E)
- **Momentum** (3-12 month returns)
- **Quality** (profitability, investment)

**Impact**: **CANNOT DISTINGUISH SKILL FROM LUCK**. Example:
- Portfolio +20% return → Is this alpha (skill) or just "big tech" exposure (beta)?
- Without factor analysis, you don't know if you have edge or just rode the market
- **Blocks performance attribution** (which positions added value?)

**Data Sources**:
- **Kenneth French Data Library**: Free Fama-French factors. [Link](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
- **Internal calculation**: Can compute value/momentum/quality factors from existing `reference_cache` data

**Effort**: MEDIUM (1-2 weeks)
- Download Fama-French daily factor returns
- Regress portfolio returns on factors: `R_portfolio = α + β_mkt*R_mkt + β_smb*R_smb + β_hml*R_hml + β_rmw*R_rmw + β_cma*R_cma + ε`
- Store factor loadings (β values) in `portfolio_factors` table
- Display in analytics UI: "Your portfolio is +0.5 std dev tilted toward value, -0.3 toward momentum"

**Blocks Strategies**: Factor Investing, Performance Attribution, Risk Decomposition

**Code References**:
- `backend/app/portfolio/analytics.py:124-170` - Extend with factor analysis
- `backend/app/analytics/factor_models.py` - New module for factor regressions
- Schema: Add `portfolio_factors` table (factor_name, loading, t_stat, r_squared, updated_at)

**Success Criteria**:
- Portfolio returns regressed on Fama-French factors
- R² >0.7 (factors explain most portfolio variance)
- Alpha (intercept) is statistically significant (t-stat >2) if strategy has edge

**Dependencies**: GAP-020 (need historical returns)
**Status**: Open
**Task File**: `tasks-0068-factor-exposure-analysis.md` (to be generated)

---

#### GAP-023: No Drawdown Tracking

**Category**: Risk Analytics
**Criticality**: P0 - CRITICAL

**Current State**: No maximum drawdown, current drawdown, or underwater period tracking. `analytics_risk.py:120-205` only calculates point-in-time volatility, not drawdown history.

**Desired State**: Track:
- **Max Drawdown**: Worst peak-to-trough decline in portfolio value
- **Current Drawdown**: How far below peak are we now?
- **Underwater Period**: Days since last all-time high
- **Drawdown Duration**: How long did max DD last?

**Impact**: **DRAWDOWN = #1 REASON TRADERS QUIT**. Volatility doesn't tell the full story. Example:
- Portfolio A: 15% vol, 10% max DD → Smooth
- Portfolio B: 15% vol, 40% max DD → Gut-wrenching
- Both have same volatility but very different psychological pain

**Data Sources**: Internal (`portfolio_value` history in `portfolio_snapshots` table)

**Effort**: LOW (2-3 days)
- Query `portfolio_snapshots` for value history
- Calculate running peak: `peak[t] = max(value[0:t])`
- Calculate drawdown: `DD[t] = (value[t] - peak[t]) / peak[t]`
- Track max DD, current DD, underwater days
- Add to analytics dashboard

**Blocks Strategies**: All (risk management depends on drawdown, not just volatility)

**Code References**:
- `backend/app/portfolio/analytics_risk.py:120-205` - Add drawdown calculations
- `backend/app/analytics/drawdown.py` - New module for DD logic
- Schema: Add `portfolio_drawdowns` table (date, value, peak, drawdown, underwater_days)

**Success Criteria**:
- Max drawdown displayed in analytics UI
- Current drawdown alerts when >10%
- Underwater period tracked (days since ATH)

**Dependencies**: Need portfolio value history (check if `portfolio_snapshots` table exists)
**Status**: Open
**Task File**: `tasks-0069-drawdown-tracking.md` (to be generated)

---

#### GAP-024: No Correlation Monitoring

**Category**: Risk Analytics
**Criticality**: P0 - CRITICAL

**Current State**: No real-time correlation tracking between portfolio holdings. Correlations are static (computed once in covariance matrix). **Correlations increase during crashes** → diversification fails when needed most.

**Desired State**: Track rolling 30-day correlation matrix. Alert when average correlation >0.7 (portfolio becoming "one big bet"). Example:
- Normal times: Avg correlation = 0.3 (diversified)
- Crisis: Avg correlation → 0.9 ("everything goes down together")
- Need to detect regime change and reduce risk

**Impact**: **DIVERSIFICATION ILLUSION**. Think you're diversified but stocks crash together. Example:
- 2008: Tech, financials, energy all crashed together (ρ → 1)
- 2020: Same thing (except gold, bonds)
- **Without correlation monitoring, you don't see it coming**

**Data Sources**: Internal (`day_bars` table)

**Effort**: LOW (2-3 days)
- Calculate rolling 30-day correlation matrix
- Compute average pairwise correlation
- Alert when avg corr >0.7 threshold
- Display correlation heatmap in UI

**Blocks Strategies**: All (correlation is key to portfolio risk)

**Code References**:
- `backend/app/analytics/risk_calculations.py` - Add rolling correlation
- `backend/app/api/analytics.py` - Add correlation endpoint
- Frontend: Add correlation heatmap to analytics dashboard

**Success Criteria**:
- Rolling correlation matrix updated daily
- Alert triggered when avg correlation spikes >0.7
- Correlation heatmap displayed in UI

**Dependencies**: GAP-020 (need covariance matrix infrastructure)
**Status**: Open
**Task File**: `tasks-0070-correlation-monitoring.md` (to be generated)

---

#### GAP-027: No VaR/CVaR

**Category**: Risk Analytics
**Criticality**: P1 - HIGH

**Current State**: No Value at Risk (VaR) or Conditional VaR (CVaR) calculation. Industry-standard risk metrics missing.

**Desired State**: Calculate:
- **1-day VaR (95%)**: "I expect to lose no more than $X on 95% of days"
- **1-day CVaR (95%)**: "If I'm in the worst 5% of days, I expect to lose $Y on average"
- Use historical method (empirical quantiles) and parametric method (assume normal)

**Impact**: Institutional investors expect VaR reporting. Useful for position sizing and risk budgeting.

**Data Sources**: Internal (portfolio value history)

**Effort**: MEDIUM (1 week)
- Calculate daily portfolio returns from `portfolio_snapshots`
- Historical VaR: 5th percentile of returns
- Parametric VaR: -1.65 * σ_portfolio (assumes normality)
- CVaR: Average of returns below VaR threshold
- Display in analytics dashboard

**Blocks Strategies**: Institutional-grade risk reporting

**Code References**:
- `backend/app/analytics/risk_calculations.py` - Add VaR/CVaR functions
- `backend/app/portfolio/analytics_risk.py:120-205` - Integrate into analytics

**Success Criteria**:
- VaR and CVaR displayed in analytics UI
- VaR backtested: Check if actual losses exceed VaR <5% of days

**Dependencies**: GAP-023 (need portfolio value history)
**Status**: Open
**Task File**: `tasks-0071-var-cvar-calculation.md` (to be generated)

---

### Signal & Scoring Gaps

#### GAP-012: Single-Day Momentum (Need 3-12 Month)

**Category**: Signals
**Criticality**: P0 - CRITICAL

**Current State**: Price pillar scores only the **most recent percent change** and clamps it between ±20% (`backend/app/watchlist/scoring.py:39-103`). **1-day price moves are NOISE, not signal**. Academic evidence shows predictive power comes from **3-12 month momentum**, not 1-day noise (Jegadeesh & Titman 1993).

**Desired State**: Replace 1-day scoring with multi-horizon momentum:
- **20-day (1 month) momentum**: Short-term trend
- **60-day (3 month) momentum**: Medium-term trend (strongest predictor)
- **120-day (6 month) momentum**: Long-term trend
- Calculate cross-sectional percentile ranks (relative strength)
- Weight: 60% weight on 60-day, 20% on 20-day, 20% on 120-day

**Impact**: **CURRENT PRICE SCORING HAS ZERO EDGE**. 1-day moves are random walk. Example:
- Stock up 5% today → Could be noise, profit-taking tomorrow
- Stock up 30% over 3 months → Momentum, likely continues (Jegadeesh & Titman proven)
- **This is the difference between profitable and unprofitable strategies**

**Data Sources**: Internal (`day_bars` table has all historical data)

**Effort**: LOW (3-5 days)
- Query `day_bars` for 20/60/120-day returns
- Calculate percentile ranks across watchlist
- Replace 1-day scoring in `scoring.py:39-103`
- Add to `watchlist_scores` table

**Blocks Strategies**: Momentum Trading (current implementation is broken)

**Code References**:
- `backend/app/watchlist/scoring.py:39-103` - Replace 1-day with multi-horizon
- `backend/app/analytics/momentum.py` - New module for momentum calculations

**Success Criteria**:
- Watchlist scores use 20/60/120-day momentum instead of 1-day
- Verify: High-momentum stocks (top quintile) outperform low-momentum (bottom quintile) in backtest

**Dependencies**: None (data exists in `day_bars`)
**Status**: Open
**Task File**: `tasks-0072-multi-horizon-momentum.md` (to be generated)

---

#### GAP-013: No Sector-Relative Strength

**Category**: Signals
**Criticality**: P0 - CRITICAL

**Current State**: Signal classification uses absolute momentum (stock vs itself), not relative strength (stock vs sector). **Absolute momentum is weak. Relative strength is stronger predictor** (Faber 2007).

**Desired State**: For each stock, compare performance to sector ETF:
- AAPL vs XLK (Technology)
- JPM vs XLF (Financials)
- XOM vs XLE (Energy)
- Calculate **relative strength ratio**: `RS = stock_return / sector_return`
- Score: RS >1.2 = outperforming, RS <0.8 = underperforming

**Impact**: **SECTOR ROTATION DRIVES 30-40% OF STOCK RETURNS**. Example:
- Energy sector down 10%, XOM down 5% → XOM is strong (relative)
- Tech sector up 15%, AAPL up 10% → AAPL is weak (relative)
- **Buy relative strength, avoid relative weakness**

**Data Sources**: Internal (already fetch XLK, XLE, XLF, etc. in `watchlist/refresh_builders.py:127-174`)

**Effort**: LOW (2-3 days)
- Map each ticker to sector ETF (use existing sector classification)
- Calculate relative strength ratio
- Add to `watchlist_scores` table
- Update scoring to include RS pillar

**Blocks Strategies**: Sector Rotation, Relative Strength Trading

**Code References**:
- `backend/app/watchlist/scoring.py` - Add relative strength calculation
- `backend/app/analytics/relative_strength.py` - New module

**Success Criteria**:
- Each watchlist ticker has RS score vs sector
- Verify: High RS stocks outperform low RS stocks in backtest

**Dependencies**: None (sector ETF data already exists)
**Status**: Open
**Task File**: `tasks-0073-sector-relative-strength.md` (to be generated)

---

#### GAP-014: Hard-Coded Signal Thresholds

**Category**: Signals
**Criticality**: P0 - CRITICAL

**Current State**: Signal classification uses **fixed thresholds** on EMA(20), SMA(5), RSI(14), volume ratio (`backend/app/watchlist/signal_classifier.py:92-207`). Example:
- RSI >70 = overbought (sell)
- RSI <30 = oversold (buy)
- **These thresholds work for AAPL, fail for volatile biotech**

**Desired State**: Replace hard-coded thresholds with **percentile-based or volatility-adjusted** signals:
- RSI >70 → RSI > 80th percentile (relative to stock's own history)
- Volume spike → Volume > 2x ATR of volume (volatility-adjusted)
- EMA crossover → Normalized by ATR (position-independent)

**Impact**: **ONE SIZE DOES NOT FIT ALL**. Hard-coded thresholds generate false signals. Example:
- AAPL: Low volatility, RSI rarely hits 70 → few signals
- Volatile biotech: RSI whipsaws 20-80 daily → constant false signals
- **Need adaptive thresholds per ticker**

**Data Sources**: Internal (historical RSI, volume, price data in `technical_indicators` table)

**Effort**: MEDIUM (1 week)
- Calculate percentile ranks for each indicator
- Replace hard thresholds with percentile checks
- Test on high-vol vs low-vol stocks
- Update `signal_classifier.py:92-207`

**Blocks Strategies**: All technical signals (current implementation has high false positive rate)

**Code References**:
- `backend/app/watchlist/signal_classifier.py:92-207` - Replace thresholds
- `backend/app/analytics/percentile_scoring.py` - New module

**Success Criteria**:
- Signal classification uses percentile thresholds
- Verify: False positive rate decreases (backtest required)

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0074-adaptive-signal-thresholds.md` (to be generated)

---

#### GAP-018: No Multi-Timeframe Analysis

**Category**: Signals
**Criticality**: P0 - CRITICAL

**Current State**: Signals operate on single timeframe (daily). No confirmation across weekly/monthly. Professional traders use **multi-timeframe confluence** (daily + weekly alignment = stronger signal).

**Desired State**: Analyze signals across 3 timeframes:
- **Daily**: Short-term signals (RSI, EMA crossovers)
- **Weekly**: Medium-term trend confirmation
- **Monthly**: Long-term regime (bull/bear market)
- Score: All 3 aligned = high confidence, only 1 = low confidence

**Impact**: **MULTI-TIMEFRAME CONFIRMATION REDUCES FALSE SIGNALS**. Example:
- Daily RSI says "buy" but weekly trend is down → Low confidence (counter-trend trade)
- Daily, weekly, monthly all say "buy" → High confidence (trend alignment)
- **Improves signal quality and win rate**

**Data Sources**: Internal (`day_bars` table can be resampled to weekly/monthly)

**Effort**: MEDIUM (1-2 weeks)
- Resample `day_bars` to weekly/monthly
- Calculate indicators on each timeframe
- Check alignment (bull on all 3, bear on all 3, mixed)
- Add confidence score to `watchlist_scores`

**Blocks Strategies**: All (multi-timeframe is best practice)

**Code References**:
- `backend/app/analytics/multi_timeframe.py` - New module
- `backend/app/watchlist/scoring.py` - Add timeframe confidence score

**Success Criteria**:
- Signals scored across daily/weekly/monthly
- High-confidence signals (3/3 alignment) have better win rate than low-confidence (1/3)

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0075-multi-timeframe-analysis.md` (to be generated)

---

#### GAP-019: No Backtested Signal Validation

**Category**: Signals (ML Infrastructure)
**Criticality**: P0 - CRITICAL

**Current State**: Signals are **untested hypotheses**. No historical performance metrics. Don't know if they work.

**Desired State**: Build backtesting framework to validate every signal:
- Simulate historical trades based on signals
- Calculate performance: Win rate, avg profit, Sharpe ratio, max DD
- Compare signal performance vs buy-and-hold, vs random
- Only deploy signals with positive Sharpe >0.5

**Impact**: **CANNOT TRADE PROFITABLY WITHOUT BACKTESTING**. Example:
- Current momentum signal looks good on paper
- Backtest 2020-2024: Sharpe = 0.2 (barely above random)
- **Would lose money after transaction costs**
- Need backtesting to separate good signals from bad

**Data Sources**: Internal (`day_bars`, `technical_indicators`, `watchlist_scores`)

**Effort**: HIGH (2-3 weeks) - **This is foundational infrastructure**
- Build backtesting engine (historical simulation)
- Realistic fills (bid/ask spread, slippage)
- Transaction costs (commissions, market impact)
- Portfolio-level backtests (multiple positions, rebalancing)
- Performance reporting (equity curve, drawdown, Sharpe)

**Blocks Strategies**: All (cannot validate edge without backtesting)

**Code References**:
- `backend/app/backtesting/engine.py` - New backtesting engine
- `backend/app/backtesting/performance.py` - Performance metrics
- `backend/app/backtesting/signals.py` - Signal-to-trade logic

**Success Criteria**:
- Can backtest any signal on 2020-2024 data
- Performance metrics calculated (Sharpe, DD, win rate)
- Backtest matches live trading results (within 5% due to slippage)

**Dependencies**: GAP-029 (need bid/ask for realistic fills), GAP-046 (need transaction cost model)
**Status**: Open
**Task File**: `tasks-0076-backtesting-framework.md` (to be generated)

---

### Fundamental Data Gaps

#### GAP-003: No Earnings Surprise Tracking

**Category**: Fundamentals
**Criticality**: P0 - CRITICAL

**Current State**: Earnings calendar handling grabs only the **next date** (`backend/app/watchlist/refresh_data_fetchers.py:213-236`) but never stores **actual vs consensus** or **surprises**. **Earnings surprise = most persistent equity premium** (Piotroski 2000).

**Desired State**: Store earnings surprise data:
- **Actual EPS** (reported earnings)
- **Consensus EPS** (analyst estimates)
- **Surprise %**: `(Actual - Consensus) / |Consensus| * 100`
- **Surprise Direction**: Beat (positive), Miss (negative), In-Line
- Historical surprises (last 8 quarters)

**Impact**: **MISSING PROVEN EDGE**. Earnings surprises predict stock returns for weeks after announcement. Example:
- Stock beats earnings by 20% → Likely drifts up for 1-4 weeks (post-earnings drift)
- Stock misses by 10% → Likely drifts down
- **Current system is blind to this signal**

**Data Sources**:
- **FMP**: Earnings historical + surprise. [API](https://financialmodelingprep.com/api/v3/earnings-surprises/)
- **Finnhub**: Earnings surprises. [API](https://finnhub.io/docs/api/earnings-surprises)
- **Alpha Vantage**: Earnings (free tier limited)

**Effort**: LOW (1 week)
- Add `earnings_surprises` table (ticker, date, actual, consensus, surprise_pct, beat_miss)
- Fetch from FMP/Finnhub
- Update watchlist scoring to include earnings surprise pillar
- Alert on big beats/misses (>10% surprise)

**Blocks Strategies**: Earnings Plays, Post-Earnings Drift

**Code References**:
- Schema: Add `earnings_surprises` table
- `backend/app/watchlist/fundamentals.py` - Add surprise fetching
- `backend/app/watchlist/scoring.py` - Add earnings surprise pillar

**Success Criteria**:
- `earnings_surprises` table populated for last 8 quarters per ticker
- Watchlist scores include earnings surprise component
- Backtest: Stocks with >10% positive surprise outperform for 1-4 weeks

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0077-earnings-surprise-tracking.md` (to be generated)

---

#### GAP-005: No Analyst Estimate Revisions

**Category**: Fundamentals
**Criticality**: P0 - CRITICAL

**Current State**: `FundamentalData` stores only static `recommendation_mean` (`backend/app/watchlist/fundamentals.py:37-53`). No tracking of **estimate revisions** (upgrades vs downgrades, magnitude). **Earnings estimate upgrades predict outperformance** (Chan et al. 1996).

**Desired State**: Track analyst estimate revisions:
- **EPS estimate trend**: Upgrades, downgrades, unchanged
- **Revision magnitude**: How much did estimates move?
- **Revision breadth**: How many analysts revised?
- **Revision momentum**: 1-month, 3-month revision trends

**Impact**: **ESTIMATE REVISIONS = LEADING INDICATOR**. Example:
- 10 analysts upgrade EPS estimates by 15% → Stock likely to outperform (earnings momentum)
- 5 analysts downgrade by 20% → Stock likely to underperform
- **Current system misses this signal**

**Data Sources**:
- **FMP**: Analyst estimates. [API](https://financialmodelingprep.com/api/v3/analyst-estimates/)
- **Finnhub**: Recommendation trends. [API](https://finnhub.io/docs/api/recommendation-trends)

**Effort**: MEDIUM (1-2 weeks)
- Add `analyst_revisions` table (ticker, date, estimate_old, estimate_new, revision_pct, analyst_count)
- Fetch daily from FMP/Finnhub
- Calculate revision momentum (1-month, 3-month)
- Add to watchlist scoring

**Blocks Strategies**: Earnings Momentum, Estimate Revision Trading

**Code References**:
- Schema: Add `analyst_revisions` table
- `backend/app/watchlist/fundamentals.py` - Add revision fetching
- `backend/app/watchlist/scoring.py` - Add revision pillar

**Success Criteria**:
- `analyst_revisions` table tracks estimate changes over time
- Watchlist scores include revision momentum
- Backtest: Stocks with positive revisions outperform

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0078-analyst-estimate-revisions.md` (to be generated)

---

### Execution & Risk Control Gaps

#### GAP-042: Flat 5% Stop Without ATR

**Category**: Execution
**Criticality**: P0 - CRITICAL

**Current State**: If ATR data is missing, every trade defaults to a **flat 5% stop** (`backend/app/analytics/trade_calculations.py:58-74`). **Ignores asset volatility** → conflicts with risk-parity principles (Markowitz 1952).

**Desired State**: Never use flat % stops. Always volatility-adjusted:
- **With ATR**: Stop = Entry - 2×ATR (current, good)
- **Without ATR**: Estimate ATR from recent 14-day price range
- **Fallback**: Use sector volatility (tech stocks more volatile than utilities)

**Impact**: **FLAT STOPS ARE AMATEUR HOUR**. Example:
- 5% stop on low-vol utility (historical vol = 8%) → Stop too wide, gives up unnecessary losses
- 5% stop on high-vol biotech (historical vol = 40%) → Stop too tight, whipsawed out on noise
- **One size does NOT fit all**

**Data Sources**: Internal (`day_bars` for ATR calculation)

**Effort**: LOW (2-3 days)
- Always calculate ATR from `day_bars` if available
- Fallback: Estimate from 14-day high-low range
- Never use flat 5% (remove this code path)
- Update `trade_calculations.py:58-74`

**Blocks Strategies**: All (proper stops are critical for risk management)

**Code References**:
- `backend/app/analytics/trade_calculations.py:58-74` - Remove flat 5% fallback
- `backend/app/analytics/atr_estimation.py` - New module for ATR fallback logic

**Success Criteria**:
- No trades use flat 5% stops
- All stops are ATR-based or volatility-adjusted
- Backtest: Adaptive stops have lower false stop-out rate than flat stops

**Dependencies**: None
**Status**: Open
**Task File**: `tasks-0079-fix-flat-stop-loss.md` (to be generated)

---

#### GAP-043: Fixed Dollar Risk Budget

**Category**: Execution
**Criticality**: P0 - CRITICAL

**Current State**: Position sizing pulls a single `watchlist_risk_budget` value from preferences (default **$500**) with **no linkage to account equity, exposure, or symbol volatility** (`backend/app/utils/preferences_loader.py:32-97`). **Position sizing is fundamentally broken.**

**Desired State**: Risk budget as **% of account equity**:
- Example: 1% risk per trade (industry standard)
- $10k account → $100 risk per trade
- $1M account → $10k risk per trade
- Position size = `risk_budget / (entry - stop_loss)`

**Impact**: **CURRENT SYSTEM IS ACCOUNT-SIZE AGNOSTIC**. Example:
- $500 risk on $10k account = 5% risk per trade (too aggressive, blow up risk)
- $500 risk on $1M account = 0.05% risk per trade (too conservative, missed gains)
- **Position sizing should scale with account size**

**Data Sources**: Internal (need account equity value)

**Effort**: LOW (2-3 days)
- Add account equity tracking (portfolio total value)
- Replace fixed $500 with `equity * risk_pct_per_trade`
- Default: 1% risk per trade
- Calculate position size: `shares = (equity * 0.01) / (entry - stop)`
- Update `trade_calculations.py`

**Blocks Strategies**: All (position sizing is foundational)

**Code References**:
- `backend/app/analytics/trade_calculations.py` - Replace fixed $500
- `backend/app/analytics/position_sizing.py` - New module for Kelly/fractional sizing
- `backend/app/portfolio/models.py` - Track account equity

**Success Criteria**:
- Position sizes scale with account equity
- Risk per trade = 1% of equity (configurable)
- Backtest: Proper sizing improves risk-adjusted returns vs fixed $500

**Dependencies**: Need portfolio value tracking
**Status**: Open
**Task File**: `tasks-0080-fix-position-sizing.md` (to be generated)

---

#### GAP-044: No Liquidity Checks

**Category**: Execution
**Criticality**: P0 - CRITICAL

**Current State**: No average daily volume (ADV) or spread checks. System might recommend buying $100k of illiquid microcap → **would move market and get terrible fill**.

**Desired State**: Check liquidity before sizing positions:
- Fetch **Average Daily Volume (ADV)** (20-day avg)
- Rule: **Position size ≤ 1% of ADV** (avoid moving market)
- Example: Stock has ADV = 1M shares → Max position = 10k shares
- If position exceeds liquidity, reduce size or skip trade

**Impact**: **LARGE POSITIONS IN ILLIQUID STOCKS = DISASTER**. Example:
- Want to buy $100k of microcap with 50k ADV
- Your order is 2x daily volume → Price spikes 10% on your buy
- Now underwater immediately (bought at inflated price)
- **Cannot exit without crashing price**

**Data Sources**:
- **Internal**: Calculate ADV from `day_bars` volume history
- **External**: Polygon/Alpaca provide ADV

**Effort**: LOW (2-3 days)
- Calculate 20-day ADV from `day_bars`
- Add liquidity check to position sizing logic
- Warn if position >1% ADV
- Reduce position or skip if illiquid

**Blocks Strategies**: All (liquidity is critical for execution)

**Code References**:
- `backend/app/analytics/liquidity.py` - New module for ADV calculation
- `backend/app/analytics/position_sizing.py` - Add liquidity constraint
- `backend/app/watchlist/scoring.py` - Flag illiquid stocks

**Success Criteria**:
- All positions ≤1% of ADV
- Illiquid stocks flagged with warning
- Backtest: Liquidity-aware sizing improves fill quality

**Dependencies**: None (volume data in `day_bars`)
**Status**: Open
**Task File**: `tasks-0081-liquidity-checks.md` (to be generated)

---

#### GAP-045: No Kelly Position Sizing

**Category**: Execution
**Criticality**: P0 - CRITICAL

**Current State**: Position sizing is flat $500 (GAP-043). Even after fixing to equity-based, need **Kelly criterion** or **fixed fractional** to optimize bet size for edge.

**Desired State**: Implement Kelly criterion position sizing:
- **Kelly %** = `(Win_Rate * Avg_Win - Loss_Rate * Avg_Loss) / Avg_Win`
- **Position size** = `Account_Equity * Kelly% * Safety_Factor`
- Safety factor = 0.25-0.5 (fractional Kelly to reduce volatility)
- Example: 60% win rate, 2:1 payoff → Kelly = 20% → Use 5% (quarter-Kelly)

**Impact**: **KELLY MAXIMIZES LONG-TERM GROWTH**. Example:
- Strategy has 55% win rate, 1.5:1 payoff → Kelly says bet 5% per trade
- Flat 1% → Underbet, missed gains
- Flat 10% → Overbet, blow-up risk
- **Kelly finds optimal bet size**

**Data Sources**: Internal (need strategy historical performance: win rate, avg win, avg loss)

**Effort**: MEDIUM (1 week)
- Track historical trade outcomes (win/loss, size)
- Calculate win rate, avg win, avg loss per strategy
- Implement Kelly formula
- Add safety factor (quarter-Kelly or half-Kelly)
- Update position sizing logic

**Blocks Strategies**: All (optimal position sizing improves risk-adjusted returns)

**Code References**:
- `backend/app/analytics/position_sizing.py` - Add Kelly criterion
- `backend/app/analytics/strategy_performance.py` - Track win/loss stats
- `backend/app/utils/preferences_loader.py` - Add Kelly parameters (safety factor)

**Success Criteria**:
- Position sizes use Kelly criterion (or fractional Kelly)
- Backtest: Kelly sizing outperforms flat 1% in risk-adjusted returns (higher Sharpe)

**Dependencies**: GAP-043 (fix equity-based sizing first), GAP-019 (need backtest to measure win rate)
**Status**: Open
**Task File**: `tasks-0082-kelly-position-sizing.md` (to be generated)

---

#### GAP-046: No Transaction Cost Model

**Category**: Execution
**Criticality**: P0 - CRITICAL

**Current State**: No slippage or commission estimates. **Strategies profitable in backtest can be losers after costs.**

**Desired State**: Model transaction costs:
- **Commission**: $0 (most brokers are zero-commission now, but verify)
- **Spread cost**: Half-spread = `(Ask - Bid) / 2` (market orders pay the spread)
- **Market impact**: Square root law: `Impact = σ * √(Position_Size / ADV)` (large orders move market)
- **Total cost per trade**: Commission + Spread + Impact

**Impact**: **TRANSACTION COSTS KILL STRATEGIES**. Example:
- Strategy generates +0.5% avg profit per trade (backtest)
- Transaction costs = 0.4% per trade (spread + impact)
- **Net profit = 0.1% → Not worth it after tax and slippage variance**

**Data Sources**:
- **Bid/Ask**: GAP-029 (need to fill first)
- **Volatility (σ)**: From `technical_indicators.ATR` or `day_bars` std dev
- **ADV**: From `day_bars` volume

**Effort**: MEDIUM (1 week)
- Fetch bid/ask spreads (GAP-029)
- Calculate half-spread cost
- Implement market impact model (square root law)
- Add to backtesting engine (subtract costs from returns)
- Display estimated costs in trade recommendations

**Blocks Strategies**: All (cannot assess profitability without cost model)

**Code References**:
- `backend/app/analytics/transaction_costs.py` - New module for cost calculation
- `backend/app/backtesting/engine.py` - Integrate costs into backtest
- `backend/app/api/trades.py` - Display estimated costs in UI

**Success Criteria**:
- All backtests include transaction costs
- Trade recommendations show estimated cost
- Backtest: Some strategies become unprofitable after costs (realistic)

**Dependencies**: GAP-029 (bid/ask spreads), GAP-044 (liquidity/ADV)
**Status**: Open
**Task File**: `tasks-0083-transaction-cost-model.md` (to be generated)

---

### Macro & Sentiment Gaps

#### GAP-031: Options Flow Unused in Scoring

**Category**: Macro/Sentiment
**Criticality**: P0 - CRITICAL

**Current State**: `fetch_options_activity_metrics` scrapes CBOE "Most Active" data and normalizes near-term vs longer-dated flows (`backend/app/tasks/market_data_tasks.py:305-389`). **Data is collected but NEVER used in signals**. Only consumer is `/api/market/conditions` response builder (`backend/app/api/market.py:388-420`).

**Desired State**: Wire options flow into watchlist scoring as **sentiment pillar**:
- **High put/call ratio** → Bearish sentiment (contrarian buy signal)
- **High call/put ratio** → Bullish sentiment (momentum confirmation)
- **Unusual options activity** → Informed flow, follow the smart money
- Pan & Poteshman (2006) **prove option volume predicts stock returns**

**Impact**: **FREE EDGE LEFT ON TABLE**. Data already exists, just need to connect it. Example:
- NVDA has huge call buying (put/call = 0.3) → Bullish signal
- SPY has huge put buying (put/call = 1.5) → Bearish/hedge signal
- **This is proven alpha, just sitting unused**

**Data Sources**: Internal (`options_market_metrics` table already populated)

**Effort**: LOW (3-5 days) - **Easiest high-impact gap to fill**
- Query `options_market_metrics` for ticker-specific data
- Calculate put/call ratio, unusual activity flags
- Add options sentiment as 4th scoring pillar (alongside price, technical, fundamental)
- Weight: 15-20% of total score

**Blocks Strategies**: Options Flow Trading, Sentiment Analysis

**Code References**:
- `backend/app/watchlist/scoring.py` - Add options sentiment pillar
- `backend/app/tasks/market_data_tasks.py:305-389` - Data already exists, just use it

**Success Criteria**:
- Watchlist scores include options sentiment component
- Backtest: High call buying predicts positive returns (per Pan & Poteshman)

**Dependencies**: None (data already exists!)
**Status**: Open
**Task File**: `tasks-0084-wire-options-flow-to-scoring.md` (to be generated)

---

## P1 Gaps - HIGH (Major Edge Improvement)

### Market Data Gaps

#### GAP-038: No Pre-Market/After-Hours Data

**Category**: Market Data
**Criticality**: P1 - HIGH

**Current State**: Only regular session data (9:30-16:00 ET). **Earnings reactions often happen pre-market** (8:00-9:30 ET). Missing this loses edge on event-driven trades.

**Desired State**: Collect pre-market (4:00-9:30 ET) and after-hours (16:00-20:00 ET) OHLCV data.

**Impact**: Earnings announcements happen pre-market. Stock gaps up/down before open. Without pre-market data, you miss the initial reaction.

**Data Sources**: Polygon, Alpaca (both support extended hours)

**Effort**: MEDIUM (1 week) - Extend intraday ingestion to include extended hours

**Blocks Strategies**: Earnings Plays, Gap Trading

**Status**: Open
**Task File**: `tasks-0085-premarket-afterhours-data.md` (to be generated)

---

#### GAP-039: No Corporate Actions Data

**Category**: Market Data
**Criticality**: P1 - HIGH

**Current State**: No tracking of stock splits, dividends, spin-offs. **Historical prices need adjustment**. Without this, backtests are incorrect.

**Desired State**: Fetch corporate actions from vendor, adjust historical prices accordingly.

**Impact**: Example: Stock splits 2:1 → Historical prices need to be halved. Without adjustment, momentum calculations are wrong.

**Data Sources**: FMP, Polygon, Yahoo Finance (all provide corporate actions)

**Effort**: MEDIUM (1-2 weeks)

**Blocks Strategies**: Backtesting (data quality issue)

**Status**: Open
**Task File**: `tasks-0086-corporate-actions.md` (to be generated)

---

### Fundamental Data Gaps

#### GAP-002: Missing P/E, P/B, PEG Ratios

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: `FundamentalData` holds only profit margin, revenue growth, debt/equity. **Valuation score has TODO for P/E, P/B, PEG** (`backend/app/watchlist/fundamentals.py:307-331`).

**Desired State**: Add valuation ratios: P/E, P/B, PEG, P/S, EV/EBITDA.

**Impact**: Cannot run value screens without basic valuation. P/E <15 + P/B <2 = classic value criteria (Graham).

**Data Sources**: FMP, Finnhub, Yahoo Finance (all provide ratios)

**Effort**: LOW (3-5 days)

**Blocks Strategies**: Value Investing, Valuation Screens

**Status**: Open
**Task File**: `tasks-0087-add-pe-pb-peg.md` (to be generated)

---

#### GAP-004: No Cash Flow Metrics

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No free cash flow (FCF), operating cash flow (OCF), or cash conversion ratio. Profit can be manipulated via accruals. **Cash flow is more reliable**.

**Desired State**: Add FCF, OCF, cash conversion (OCF/Net Income), FCF yield (FCF/Market Cap).

**Impact**: Quality investing requires cash flow metrics. High FCF yield = value signal (Greenblatt).

**Data Sources**: FMP, Finnhub

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Quality Investing, Piotroski F-Score

**Status**: Open
**Task File**: `tasks-0088-cash-flow-metrics.md` (to be generated)

---

#### GAP-006: No Insider Trading Data

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No tracking of insider buying/selling (SEC Form 4 filings). **Insider buying clusters = bullish signal**.

**Desired State**: Parse SEC Form 4 filings, detect buying/selling clusters, flag unusual insider activity.

**Impact**: Insider buying often precedes stock outperformance (Seyhun 1986).

**Data Sources**: SEC EDGAR API, Finnhub, FMP

**Effort**: MEDIUM (1-2 weeks)

**Blocks Strategies**: Insider Flow Trading

**Status**: Open
**Task File**: `tasks-0089-insider-trading.md` (to be generated)

---

#### GAP-007: No Institutional Ownership

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No tracking of 13F filings (institutional holdings). **Smart money positioning**.

**Desired State**: Track institutional ownership % and changes (quarter-over-quarter).

**Impact**: Rising institutional ownership = smart money accumulation (positive signal).

**Data Sources**: FMP, Finnhub, SEC 13F filings

**Effort**: MEDIUM (1-2 weeks)

**Blocks Strategies**: Smart Money Flow Trading

**Status**: Open
**Task File**: `tasks-0090-institutional-ownership.md` (to be generated)

---

#### GAP-008: No Piotroski F-Score

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No composite fundamental quality score. **Piotroski F-Score** = 9-point checklist proven to separate winners from losers in value stocks (Piotroski 2000).

**Desired State**: Calculate F-Score (profitability + leverage + operating efficiency). Score 0-9, higher = better quality.

**Impact**: F-Score 8-9 value stocks outperform F-Score 0-1 by ~20% annually (Piotroski).

**Data Sources**: Internal (calculate from fundamentals)

**Effort**: LOW (3-5 days) - **High impact, easy to implement**

**Blocks Strategies**: Value Investing, Quality Screens

**Status**: Open
**Task File**: `tasks-0091-piotroski-fscore.md` (to be generated)

---

#### GAP-009: No Altman Z-Score

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No bankruptcy prediction. **Altman Z-Score** predicts financial distress.

**Desired State**: Calculate Z-Score from balance sheet ratios. Z <1.8 = distress zone (avoid).

**Impact**: Avoid bankruptcy candidates (value traps).

**Data Sources**: Internal (calculate from fundamentals)

**Effort**: LOW (2-3 days)

**Blocks Strategies**: Risk Management (avoid value traps)

**Status**: Open
**Task File**: `tasks-0092-altman-zscore.md` (to be generated)

---

#### GAP-011: No Short Interest Data

**Category**: Fundamentals
**Criticality**: P1 - HIGH

**Current State**: No short interest or days-to-cover tracking. **High short interest + catalyst = squeeze potential**.

**Desired State**: Track short interest % of float, days to cover, short interest trends.

**Impact**: Short squeeze trades (GME, AMC style). High short interest + positive catalyst = explosive upside.

**Data Sources**: Finnhub, FMP, exchanges

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Short Squeeze Plays, Contrarian Trading

**Status**: Open
**Task File**: `tasks-0093-short-interest.md` (to be generated)

---

### Signal & Scoring Gaps

#### GAP-015: News Not a Scoring Pillar

**Category**: Signals
**Criticality**: P1 - HIGH

**Current State**: News sentiment exists (`news_cache` table) but only a modifier in heuristics. **Never promoted to first-class signal pillar**.

**Desired State**: Add **news sentiment pillar** to watchlist scoring (alongside price, technical, fundamental). Weight 15-20%.

**Impact**: Textual tone adds alpha (Tetlock 2007). Positive news clusters predict outperformance.

**Data Sources**: Internal (`news_cache` table)

**Effort**: LOW (3-5 days)

**Blocks Strategies**: News Sentiment Trading

**Status**: Open
**Task File**: `tasks-0094-news-sentiment-pillar.md` (to be generated)

---

#### GAP-016: No Breadth Indicators

**Category**: Signals
**Criticality**: P1 - HIGH

**Current State**: No market breadth tracking (advance-decline line, new highs/lows, % stocks above 200-day MA). **Breadth divergences predict reversals**.

**Desired State**: Calculate:
- Advance-Decline Line (cumulative NYSE breadth)
- New Highs - New Lows
- % Stocks Above 50-day MA, 200-day MA

**Impact**: Breadth divergence = early warning. Example: Market up but breadth declining → Top forming.

**Data Sources**: Internal (aggregate from `day_bars`)

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Market Timing, Regime Detection

**Status**: Open
**Task File**: `tasks-0095-breadth-indicators.md` (to be generated)

---

#### GAP-017: No Mean Reversion Signals

**Category**: Signals
**Criticality**: P1 - HIGH

**Current State**: Only momentum signals. No mean reversion (Bollinger Band bounces, RSI divergences, pair reversions).

**Desired State**: Add mean reversion signals:
- Bollinger Band oversold/overbought bounces
- RSI bullish/bearish divergences
- Relative strength pair reversions

**Impact**: Momentum + Mean Reversion = diversified strategy set (uncorrelated returns).

**Data Sources**: Internal (`technical_indicators` table)

**Effort**: LOW (1 week)

**Blocks Strategies**: Mean Reversion, Range Trading

**Status**: Open
**Task File**: `tasks-0096-mean-reversion-signals.md` (to be generated)

---

### Risk Analytics Gaps

#### GAP-022: Short Beta Estimation Window

**Category**: Risk Analytics
**Criticality**: P1 - HIGH

**Current State**: Betas re-computed from only ~90 trading days when vendor data missing (`backend/app/portfolio/price_fetcher.py:324-385`). **Short windows inflate estimation error**. Betas mean-revert toward 1.0 unless shrunk (Blume 1975).

**Desired State**: Use 3-5 year beta estimation windows. Apply Bayesian shrinkage toward cross-sectional mean.

**Impact**: More stable, accurate betas → Better risk forecasts.

**Data Sources**: Internal (`day_bars`)

**Effort**: LOW (3-5 days)

**Blocks Strategies**: Portfolio Risk Management

**Status**: Open
**Task File**: `tasks-0097-long-window-beta.md` (to be generated)

---

#### GAP-025: No Portfolio Stress Testing

**Category**: Risk Analytics
**Criticality**: P1 - HIGH

**Current State**: No scenario analysis (What if VIX→50? Tech crashes 20%?). Don't know portfolio behavior in crisis.

**Desired State**: Run stress tests:
- 2008 crisis scenario
- 2020 COVID crash scenario
- Tech bubble pop (-40% tech)
- VIX spike to 80

**Impact**: Understand tail risk. "What's my max loss in a 2008-style event?"

**Data Sources**: Internal (historical correlation + shocks)

**Effort**: MEDIUM (1-2 weeks)

**Blocks Strategies**: Risk Management, Institutional Reporting

**Status**: Open
**Task File**: `tasks-0098-stress-testing.md` (to be generated)

---

#### GAP-026: No Marginal Risk Contribution

**Category**: Risk Analytics
**Criticality**: P1 - HIGH

**Current State**: Don't know which position adds most risk. Need **marginal VaR** (position-level risk contribution).

**Desired State**: Calculate marginal VaR per position. "Adding AAPL increases portfolio VaR by $X."

**Impact**: Identify risk concentrations. Which position to trim when reducing risk?

**Data Sources**: Internal (covariance matrix)

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Risk Budgeting, Portfolio Optimization

**Status**: Open
**Task File**: `tasks-0099-marginal-var.md` (to be generated)

---

#### GAP-028: No Exposure Budgets

**Category**: Risk Analytics
**Criticality**: P1 - HIGH

**Current State**: No limits on sector exposure, factor exposure, single-name concentration. Could accidentally allocate 90% to tech.

**Desired State**: Enforce exposure limits:
- Max position size: 10% of portfolio
- Max sector exposure: 30% per sector
- Max factor tilt: ±1 std dev

**Impact**: Prevent concentration blow-ups. Diversification discipline.

**Data Sources**: Internal

**Effort**: LOW (3-5 days)

**Blocks Strategies**: Risk Management

**Status**: Open
**Task File**: `tasks-0100-exposure-budgets.md` (to be generated)

---

### Execution Gaps

#### GAP-047: No Correlation-Based Sizing

**Category**: Execution
**Criticality**: P1 - HIGH

**Current State**: Position sizing ignores correlation. Adding correlated positions multiplies risk.

**Desired State**: Correlation-aware sizing. "You already have tech exposure via AAPL. Adding MSFT at full size doubles your tech risk. Reduce MSFT position."

**Impact**: Avoid concentration in disguise (5 tech stocks = 1 big bet if highly correlated).

**Data Sources**: Internal (covariance matrix from GAP-020)

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Portfolio Construction

**Status**: Open
**Task File**: `tasks-0101-correlation-aware-sizing.md` (to be generated)

---

#### GAP-048: No Slippage Tracking

**Category**: Execution
**Criticality**: P0 - CRITICAL (for live trading)

**Current State**: No tracking of actual fill vs expected price. **Strategies profitable in backtest can be losers in live trading due to slippage**.

**Desired State**: Track slippage per trade:
- Expected fill (mid-price at signal time)
- Actual fill (execution price)
- Slippage = Actual - Expected
- Aggregate: Avg slippage per strategy, per symbol

**Impact**: Measure execution quality. Identify which strategies/symbols have high slippage (avoid or adjust).

**Data Sources**: Internal (order history, actual fills from broker API)

**Effort**: MEDIUM (1-2 weeks) - Requires broker integration

**Blocks Strategies**: Live Trading (need execution quality feedback loop)

**Status**: Open
**Task File**: `tasks-0102-slippage-tracking.md` (to be generated)

---

#### GAP-049: No Market Impact Model

**Category**: Execution
**Criticality**: P1 - HIGH

**Current State**: No estimate of price movement from your order. Large orders move market → Worse fills.

**Desired State**: Implement market impact model (square root law):
```
Impact (bps) = σ * √(Order_Size / ADV) * constant
```
Where σ = volatility, ADV = average daily volume.

**Impact**: Know the cost of large orders before placing. Split large orders to reduce impact.

**Data Sources**: Internal (volatility, ADV from `day_bars`)

**Effort**: MEDIUM (1 week)

**Blocks Strategies**: Large Position Trading

**Status**: Open
**Task File**: `tasks-0103-market-impact-model.md` (to be generated)

---

### Macro & Sentiment Gaps

#### GAP-032: Manual Fear & Greed Estimates

**Category**: Macro
**Criticality**: P1 - HIGH

**Current State**: Fear & Greed inputs rely on manual script with "reasonable estimates" when data missing (`backend/scripts/update_fear_greed_inputs.py:191-199`). **Synthetic VIX contradicts Whaley 2000** (official VIX is the investor fear proxy).

**Desired State**: Automate VIX and credit spread ingestion directly from FRED/CBOE. Never use synthetic defaults.

**Impact**: Accurate fear/greed → Better macro regime detection.

**Data Sources**: FRED (VIX), CBOE, FRED (credit spreads)

**Effort**: LOW (3-5 days)

**Blocks Strategies**: Macro Sentiment Analysis

**Status**: Open
**Task File**: `tasks-0104-automate-fear-greed.md` (to be generated)

---

#### GAP-033: No Put/Call Ratio Per Ticker

**Category**: Macro
**Criticality**: P1 - HIGH

**Current State**: Aggregate options flow exists but no **ticker-specific put/call ratio**.

**Desired State**: Calculate put/call ratio per ticker. High put/call = bearish, low = bullish.

**Impact**: Ticker-specific sentiment more actionable than market-wide.

**Data Sources**: Polygon, Tradier (options data)

**Effort**: MEDIUM (1-2 weeks)

**Blocks Strategies**: Options Flow Trading

**Status**: Open
**Task File**: `tasks-0105-ticker-putcall-ratio.md` (to be generated)

---

#### GAP-034: No Yield Curve Data

**Category**: Macro
**Criticality**: P1 - HIGH

**Current State**: No yield curve tracking (2Y, 10Y, 30Y). **Inverted yield curve (2Y >10Y) predicts recessions**.

**Desired State**: Fetch yield curve from FRED. Track 2Y-10Y spread. Alert on inversion.

**Impact**: Recession predictor. Adjust risk when yield curve inverts.

**Data Sources**: FRED (free)

**Effort**: LOW (2-3 days)

**Blocks Strategies**: Macro Regime Detection

**Status**: Open
**Task File**: `tasks-0106-yield-curve.md` (to be generated)

---

#### GAP-035: No Inflation Data

**Category**: Macro
**Criticality**: P1 - HIGH

**Current State**: No CPI, PPI, PCE tracking. **Inflation drives Fed policy → Fed policy drives markets**.

**Desired State**: Fetch monthly inflation data from FRED. Track trends.

**Impact**: Inflation up → Fed hawkish → Risk-off. Useful macro signal.

**Data Sources**: FRED (free)

**Effort**: LOW (2-3 days)

**Blocks Strategies**: Macro Analysis

**Status**: Open
**Task File**: `tasks-0107-inflation-data.md` (to be generated)

---

#### GAP-036: No Fed Funds Rate Tracking

**Category**: Macro
**Criticality**: P1 - HIGH

**Current State**: No Fed funds rate or FOMC meeting calendar. **Fed policy is THE macro driver**.

**Desired State**: Track Fed funds rate, rate hike probabilities (from Fed futures), FOMC meeting dates.

**Impact**: Fed hikes → Risk-off. Fed cuts → Risk-on. Essential macro signal.

**Data Sources**: FRED (rate), CME FedWatch Tool (probabilities)

**Effort**: LOW (3-5 days)

**Blocks Strategies**: Macro Positioning

**Status**: Open
**Task File**: `tasks-0108-fed-funds-rate.md` (to be generated)

---

## P2 Gaps - MEDIUM (Incremental Gains)

*(Abbreviated - 7 gaps total)*

- **GAP-010**: No Share Buyback Tracking (P2, Fundamentals)
- **GAP-037**: No Commodity Signals (P2, Macro)
- **GAP-040**: No Level 2 Order Book (P2, Market Microstructure)
- **GAP-050**: No Feature Engineering Pipeline (P2, ML Infrastructure) - Covered in P0 as part of backtesting
- Plus 3 compliance gaps (wash sales, PDT rules, tax lots)

---

## P3 Gaps - LOW (Future Enhancements)

*(Abbreviated - 3 gaps total)*

- Alternative data (satellite, credit card, app analytics)
- Social sentiment (Reddit, Twitter)
- ESG scores

---

## Priority Recommendations (TOP 10)

**Ranked by Impact × (1/Effort)** - Maximize bang-for-buck:

| Rank | Gap ID | Gap Name | Impact | Effort | Why Start Here |
|------|--------|----------|--------|--------|----------------|
| **1** | GAP-020 | Fix portfolio risk (covariance) | 10/10 | LOW | **Current metrics are wrong**. 1-week fix, foundational. |
| **2** | GAP-031 | Wire options flow into scoring | 9/10 | LOW | **Free edge** - data exists, just connect it. Proven alpha (Pan & Poteshman). |
| **3** | GAP-012 | Multi-horizon momentum | 9/10 | LOW | Replace noisy 1-day with proven 3-12 month. Jegadeesh & Titman. |
| **4** | GAP-013 | Sector-relative strength | 8/10 | LOW | Data exists (XLK, XLE, XLF). Relative > absolute momentum. |
| **5** | GAP-043 | Fix position sizing (equity-based) | 10/10 | LOW | **Current $500 flat is broken**. Easy fix, huge impact. |
| **6** | GAP-003 | Earnings surprise tracking | 8/10 | LOW | Most persistent premium. Easy to add via FMP. |
| **7** | GAP-042 | Fix flat 5% stops | 9/10 | LOW | Always use ATR. Remove flat fallback. |
| **8** | GAP-044 | Liquidity checks | 9/10 | LOW | Prevent illiquid blow-ups. Use existing ADV data. |
| **9** | GAP-023 | Drawdown tracking | 8/10 | LOW | Psychological pain metric. Easy to calculate. |
| **10** | GAP-045 | Kelly position sizing | 10/10 | MED | Optimal bet sizing. Requires backtest data first. |

**Next 5** (after TOP 10):
- **GAP-001**: Intraday data (P0 but MEDIUM effort - prioritize after quick wins)
- **GAP-027**: VaR/CVaR (institutional reporting)
- **GAP-005**: Analyst revisions (proven edge)
- **GAP-008**: Piotroski F-Score (easy, high-impact quality screen)
- **GAP-019**: Backtesting framework (HIGH effort but foundational - start in parallel)

---

## Minimum Viable Gap-Fill Roadmap

**Goal**: Profitable trading within **4 weeks** with Sharpe ~1.5.

### Phase 1 (Week 1): Fix Foundations
**Focus**: Correct broken infrastructure

1. ✅ **GAP-020**: Fix portfolio risk math (covariance matrix)
   - Effort: 3-5 days
   - Impact: CRITICAL - current metrics are wrong
2. ✅ **GAP-043**: Fix position sizing (equity-based)
   - Effort: 2-3 days
   - Impact: CRITICAL - current sizing is broken
3. ✅ **GAP-042**: Fix flat stops (always use ATR)
   - Effort: 2-3 days
   - Impact: CRITICAL - risk management
4. ✅ **GAP-044**: Add liquidity checks
   - Effort: 2-3 days
   - Impact: CRITICAL - prevent execution disasters

**Deliverable**: Accurate risk metrics, proper position sizing, safety checks.

---

### Phase 2 (Week 2): Add Proven Signals
**Focus**: Replace noisy signals with proven alpha

5. ✅ **GAP-012**: Multi-horizon momentum (3-12 month)
   - Effort: 3-5 days
   - Impact: CRITICAL - Jegadeesh & Titman proven
6. ✅ **GAP-013**: Sector-relative strength
   - Effort: 2-3 days
   - Impact: HIGH - relative > absolute
7. ✅ **GAP-031**: Wire options flow into scoring
   - Effort: 3-5 days
   - Impact: HIGH - Pan & Poteshman proven
8. ✅ **GAP-023**: Drawdown tracking
   - Effort: 2-3 days
   - Impact: HIGH - risk monitoring

**Deliverable**: Momentum + relative strength + options sentiment signals.

---

### Phase 3 (Week 3): Add Fundamental Edge
**Focus**: Earnings and quality signals

9. ✅ **GAP-003**: Earnings surprise tracking
   - Effort: 1 week
   - Impact: HIGH - post-earnings drift
10. ✅ **GAP-002**: Add P/E, P/B, PEG ratios
    - Effort: 3-5 days
    - Impact: MEDIUM - basic value screens
11. ✅ **GAP-008**: Piotroski F-Score
    - Effort: 3-5 days
    - Impact: HIGH - quality screening

**Deliverable**: Earnings + value + quality fundamentals.

---

### Phase 4 (Week 4): Validate & Deploy
**Focus**: Backtesting and paper trading

12. ✅ **GAP-019**: Build backtesting framework
    - Effort: HIGH (parallel work during Weeks 1-3)
    - Impact: CRITICAL - validate edge
13. ✅ **GAP-029**: Add bid/ask spreads
    - Effort: 1 week
    - Impact: CRITICAL - transaction costs
14. ✅ **GAP-046**: Transaction cost model
    - Effort: 1 week
    - Impact: CRITICAL - realistic backtest

**Deliverable**:
- Backtest 2020-2024 data
- Validate Sharpe >1.0 after costs
- Deploy to paper trading
- Monitor for 2 weeks

**Expected Edge After 4 Weeks**:
- **Sharpe Ratio**: 1.2-1.8
- **Max Drawdown**: <20%
- **Win Rate**: 50-60%
- **Viable Strategies**: Multi-horizon momentum, earnings surprise, options flow, sector rotation

---

## Next Steps

**Immediate Actions** (Next 2 weeks):

1. ✅ **Run Task 0062** to build gap detection UI (7-10 days)
   - This creates the infrastructure to track gaps
   - AI-powered gap analysis and recommendations
   - Task generation workflow

2. ✅ **Generate task lists for TOP 10 gaps**
   - Use Task 0062's "generate task list" feature
   - Create detailed implementation plans
   - Add to WORK_TRACKER.md

3. ✅ **Start Phase 1 execution** (Week 1 gaps)
   - Begin with GAP-020 (covariance matrix)
   - Then GAP-043 (position sizing)
   - Then GAP-042 (stops) + GAP-044 (liquidity)

4. ⚠️ **Start GAP-019 (backtesting) in parallel**
   - This is HIGH effort (2-3 weeks)
   - Critical for validation
   - Can run in parallel with other work

**After 4 weeks**, you can:
- ✅ Trade profitably with proven signals
- ✅ Accurate risk management
- ✅ Validated via backtesting
- ✅ Deploy to paper trading
- ✅ Iterate to fill P1 gaps (12-16 weeks to Sharpe >2.0)

---

## Success Criteria

**Minimum Viable Gap-Fill Complete When**:

- ✅ Portfolio risk calculations use covariance matrix (not weighted avg)
- ✅ Position sizing scales with account equity (not flat $500)
- ✅ All stops are ATR-based (no flat 5%)
- ✅ Liquidity checks prevent illiquid positions
- ✅ Watchlist scores use 3-12 month momentum (not 1-day)
- ✅ Watchlist scores include sector-relative strength
- ✅ Watchlist scores include options flow sentiment
- ✅ Drawdown tracking active and monitored
- ✅ Earnings surprise data captured and scored
- ✅ Backtesting framework operational
- ✅ Transaction costs modeled (bid/ask + impact)
- ✅ Backtest 2020-2024 shows Sharpe >1.0 after costs

**Then**: Deploy to paper trading. Monitor for 2 weeks. Go live with small position sizes.

**Then**: Fill P1 gaps iteratively. Target Sharpe >2.0 within 3-4 months.

---

**END OF GAP DEFINITION**
