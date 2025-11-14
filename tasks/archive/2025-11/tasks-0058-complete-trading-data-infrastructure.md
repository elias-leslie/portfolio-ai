# Complete Trading Data Infrastructure

**Created**: 2025-11-13
**Priority**: P0 (Critical - Blocking AI Trading Decisions)
**Objective**: Fill critical data gaps preventing informed trading decisions and AI-driven stock recommendations

**Context**: Market analyst AI cannot make informed trading decisions due to:
- Fear & Greed Index broken (only 1 of 5 components working)
- Watchlist score breakdown shows N/A for Valuation/Growth/Health/Sentiment
- Missing earnings calendar, P/E ratios, analyst consensus
- No insider trading, short interest, or transaction history

**Success Criteria**:
- ✅ Watchlist score breakdown shows actual values (not N/A)
- ✅ Fear & Greed Index fully functional (all 5 components populated)
- ✅ Can see upcoming earnings dates for any watchlist stock
- ✅ Have P/E, P/S, P/B ratios for stock valuation
- ✅ Can track insider buying/selling
- ✅ Can identify heavily shorted stocks
- ✅ Portfolio transaction history tracked over time

---

## Phase 1: Fix Existing Features (P0 - Critical)

### Task 1: Investigate Watchlist Score Breakdown (N/A Values)

**Problem**: Watchlist page shows:
- Price score: ✅ Has value
- Technical score: ✅ Has value
- Fundamental score: ✅ Has value
- **But breakdown shows**: Valuation (N/A), Growth (N/A), Health (N/A), Sentiment (N/A)

**Investigation Steps**:
1. Check frontend component that displays score breakdown
   - File: `frontend/components/watchlist/WatchlistItemCard.tsx` or similar
   - Look for where Valuation/Growth/Health/Sentiment are rendered
   - Check if data is being passed but not displayed, or not fetched at all

2. Check API endpoint that returns watchlist data
   - File: `backend/app/api/watchlist.py`
   - Endpoint: `/api/watchlist` or `/api/watchlist/{id}`
   - Verify what fields are returned in response

3. Check database schema and data
   - Table: `watchlist_items` and `watchlist_snapshots`
   - Verify if valuation_score, growth_score, health_score, sentiment_score columns exist
   - Check if data is populated or NULL

4. Check scoring calculation code
   - File: `backend/app/services/watchlist_scorer.py` or similar
   - Look for functions that calculate sub-scores
   - Verify if calculation is disabled or broken

**Expected Outcome**:
- Identify root cause: Missing data vs. broken calculation vs. disconnected frontend
- Fix or document what needs to be rebuilt

**Files to Check**:
- `frontend/components/watchlist/*.tsx`
- `backend/app/api/watchlist.py`
- `backend/app/services/watchlist*.py`
- `backend/app/models/watchlist.py`
- Database: `watchlist_items`, `watchlist_snapshots` schemas

**Acceptance Criteria**:
- [ ] Root cause identified and documented
- [ ] Score breakdown shows actual values (not N/A)
- [ ] All sub-scores (Valuation, Growth, Health, Sentiment) populated
- [ ] Frontend displays breakdown correctly

---

### Task 2: Fix Fear & Greed Index Data Pipeline

**Problem**: Only 1 of 5 components working
```sql
as_of_date | vix_close | put_call_ratio | hy_spread | breadth_pct
2025-11-12 |   NULL    |      1.04      |   NULL    |    NULL
```

**Components Broken**:
1. ❌ VIX Close (vix_close)
2. ✅ Put/Call Ratio (put_call_ratio) - WORKING
3. ❌ HY Spread (hy_spread)
4. ❌ Market Breadth (breadth_pct)
5. ❌ SPY/RSI data (spy_close, spy_sma_200, rsi_14)

**Root Cause Analysis**:

**2.1: Check if scheduled tasks are running**
- Task: `maintain-historical-market-data` (runs at 04:00 UTC)
- Task: `calculate-fear-greed-daily` (runs at 03:00 UTC)
- Verify via: `celery -A app.celery_app inspect active`
- Check logs: `/var/log/portfolio-ai/celery-worker.log`

**2.2: Check SPY/VIX data in day_bars table**
```sql
SELECT as_of_date, symbol, close, volume
FROM day_bars
WHERE symbol IN ('SPY', '^VIX', '^GSPC')
ORDER BY as_of_date DESC LIMIT 10;
```
- If missing: `maintain-historical-market-data` not running or failing
- If present: Data exists but not being copied to fear_greed_inputs

**2.3: Check HY Spread from FRED**
- File: `backend/app/sources/fred.py`
- Check if FRED_API_KEY is set in environment
- Test FRED fetch: `curl "https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&api_key=XXX"`
- Verify if data is fetched but not stored

**2.4: Check market breadth calculation**
- Currently NULL everywhere - may never have been implemented
- Check if there's code to calculate NYSE advance/decline ratio
- Likely need to add this as new data source

**Implementation Steps**:

**Step 1: Debug VIX/SPY population**
- File: `backend/app/tasks/indicator_tasks.py` (likely location)
- Find function that populates `fear_greed_inputs`
- Add logging to see why VIX/SPY not being inserted
- Verify `day_bars` -> `fear_greed_inputs` data flow

**Step 2: Debug HY Spread population**
- File: `backend/app/sources/fred.py`
- Verify FRED API key is valid
- Check if data is fetched successfully
- Find where HY spread should be inserted into `fear_greed_inputs`
- Add error handling and logging

**Step 3: Implement Market Breadth (if missing)**
- Research NYSE advance/decline data source
- Options: yfinance ($ADVN, $DECN), Alpha Vantage, or manual calculation from sector ETFs
- Create function to fetch and store breadth_pct
- Add to scheduled tasks

**Step 4: Verify RSI calculation**
- RSI should come from `technical_indicators` table for SPY
- Check if SPY RSI is calculated daily
- Verify it's being copied to `fear_greed_inputs.rsi_14`

**Acceptance Criteria**:
- [ ] All 5 components of fear_greed_inputs populated daily
- [ ] VIX close fetched and stored
- [ ] HY spread fetched from FRED
- [ ] Market breadth calculated (or documented as N/A if no source)
- [ ] SPY close, SMA_200, RSI_14 populated
- [ ] `fear_greed_daily` table shows complete scores (0-100)
- [ ] 7-day trend working
- [ ] `/api/market/intelligence` returns valid Fear & Greed data

---

## Phase 2: Add Critical Trading Data (P0)

### Task 3: Add Earnings Calendar

**Objective**: Track upcoming earnings dates and results to avoid surprises

**Data Needed**:
- Earnings date (next report date)
- Fiscal quarter/year
- EPS estimate (consensus)
- EPS actual (after report)
- Revenue estimate
- Revenue actual
- Surprise % (actual vs estimate)

**Schema Design**:

```sql
CREATE TABLE earnings_calendar (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL,  -- 1, 2, 3, 4
    report_date DATE NOT NULL,
    report_time VARCHAR(10),  -- 'BMO' (before market open) or 'AMC' (after market close)

    -- Estimates (populated before earnings)
    eps_estimate DOUBLE PRECISION,
    revenue_estimate DOUBLE PRECISION,

    -- Actuals (populated after earnings)
    eps_actual DOUBLE PRECISION,
    revenue_actual DOUBLE PRECISION,
    eps_surprise_pct DOUBLE PRECISION,  -- (actual - estimate) / estimate * 100
    revenue_surprise_pct DOUBLE PRECISION,

    -- Metadata
    source VARCHAR(50),  -- 'yfinance', 'fmp', 'polygon'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, fiscal_year, fiscal_quarter)
);

CREATE INDEX idx_earnings_calendar_ticker ON earnings_calendar(ticker);
CREATE INDEX idx_earnings_calendar_date ON earnings_calendar(report_date);
CREATE INDEX idx_earnings_upcoming ON earnings_calendar(report_date)
    WHERE report_date >= CURRENT_DATE;
```

**Data Sources**:

1. **yfinance** (Free, unlimited):
   - `ticker.earnings_dates` - Returns DataFrame with earnings calendar
   - `ticker.calendar` - Next earnings date
   - `ticker.earnings_history` - Historical EPS surprises

2. **FMP** (250/day limit):
   - `/v3/earning_calendar` - Comprehensive earnings calendar
   - `/v4/earnings_surprises/{ticker}` - Historical surprises

3. **Polygon** (5/min limit):
   - `/v2/reference/financials` - Quarterly/annual financials with dates

**Implementation**:

**File**: `backend/app/sources/earnings_source.py`
```python
class EarningsSource:
    """Fetch earnings calendar data from multiple sources."""

    def fetch_upcoming_earnings(self, ticker: str) -> dict:
        """Get next earnings date and estimates."""

    def fetch_earnings_history(self, ticker: str, years: int = 2) -> list[dict]:
        """Get historical earnings and surprises."""

    def update_earnings_actual(self, ticker: str, fiscal_quarter: str,
                               eps: float, revenue: float):
        """Update with actual results after earnings report."""
```

**Scheduled Task**:
```python
@celery_app.task(name="fetch_earnings_calendar_daily")
def fetch_earnings_calendar():
    """Fetch earnings dates for all watchlist + portfolio tickers.

    Runs daily at 05:00 UTC.
    """
    # Get all unique tickers from watchlist + portfolio
    # Fetch earnings calendar from yfinance/FMP
    # Insert/update earnings_calendar table
```

**API Endpoints**:

1. **GET /api/earnings/upcoming?days=30** - Next 30 days earnings
   - Returns: ticker, date, time, EPS estimate

2. **GET /api/earnings/{ticker}** - Earnings history for ticker
   - Returns: Last 8 quarters with EPS/revenue actual vs estimate

3. **GET /api/watchlist** - Add `next_earnings_date` field
   - Enhance existing watchlist response with earnings date

**Frontend Display**:

1. **Watchlist Table**: Add "Next Earnings" column
   - Show date and days until earnings
   - Color code: <7 days (red), 7-14 days (yellow), >14 days (green)

2. **Watchlist Card Expansion**: Add "Earnings" section
   - Next earnings date and time (BMO/AMC)
   - EPS estimate
   - Historical beat/miss record (e.g., "Beat 3 of last 4")
   - Chart of EPS trend over last 8 quarters

**Acceptance Criteria**:
- [ ] `earnings_calendar` table created
- [ ] Earnings dates fetched for all watchlist stocks
- [ ] Next earnings date shown in watchlist
- [ ] Historical earnings surprises available via API
- [ ] Scheduled task runs daily at 05:00 UTC
- [ ] Frontend shows earnings countdown (days until report)

---

### Task 4: Add Valuation Metrics (P/E, P/S, P/B)

**Objective**: Enable value investing and stock comparison

**Data Needed**:
- **P/E Ratio** (Price-to-Earnings): Stock price / EPS
  - Trailing P/E (last 12 months actual)
  - Forward P/E (next 12 months estimate)
- **P/S Ratio** (Price-to-Sales): Market cap / Revenue
- **P/B Ratio** (Price-to-Book): Market cap / Book value
- **PEG Ratio** (P/E to Growth): P/E ratio / Earnings growth rate
- **Dividend Yield**: Annual dividend / Stock price
- **Payout Ratio**: Dividends / Earnings

**Schema Enhancement**:

Add to `reference_cache` or create new `fundamental_metrics` table:

```sql
-- Option 1: Add to existing reference_cache (quick)
ALTER TABLE reference_cache ADD COLUMN pe_ratio_trailing DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN pe_ratio_forward DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN ps_ratio DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN pb_ratio DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN peg_ratio DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN dividend_yield DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN payout_ratio DOUBLE PRECISION;
ALTER TABLE reference_cache ADD COLUMN earnings_growth_yoy DOUBLE PRECISION;

-- Option 2: New table (better long-term)
CREATE TABLE fundamental_metrics (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    as_of_date DATE NOT NULL,

    -- Valuation
    pe_ratio_trailing DOUBLE PRECISION,
    pe_ratio_forward DOUBLE PRECISION,
    ps_ratio DOUBLE PRECISION,
    pb_ratio DOUBLE PRECISION,
    peg_ratio DOUBLE PRECISION,
    ev_to_ebitda DOUBLE PRECISION,

    -- Profitability
    profit_margin DOUBLE PRECISION,
    operating_margin DOUBLE PRECISION,
    gross_margin DOUBLE PRECISION,
    roe DOUBLE PRECISION,  -- Return on Equity
    roa DOUBLE PRECISION,  -- Return on Assets
    roic DOUBLE PRECISION, -- Return on Invested Capital

    -- Growth
    revenue_growth_yoy DOUBLE PRECISION,
    earnings_growth_yoy DOUBLE PRECISION,
    revenue_growth_qoq DOUBLE PRECISION,

    -- Financial Health
    debt_to_equity DOUBLE PRECISION,
    current_ratio DOUBLE PRECISION,
    quick_ratio DOUBLE PRECISION,

    -- Dividend
    dividend_yield DOUBLE PRECISION,
    payout_ratio DOUBLE PRECISION,

    -- Metadata
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, as_of_date)
);

CREATE INDEX idx_fundamental_metrics_ticker ON fundamental_metrics(ticker);
CREATE INDEX idx_fundamental_metrics_date ON fundamental_metrics(as_of_date DESC);
```

**Data Sources**:

1. **yfinance** (Free):
   - `ticker.info` contains: trailingPE, forwardPE, priceToBook, dividendYield, payoutRatio
   - Already fetched, just need to parse and store

2. **FMP** (250/day):
   - `/v3/ratios/{ticker}` - Comprehensive financial ratios
   - `/v3/key-metrics/{ticker}` - Valuation metrics

3. **Polygon** (5/min):
   - `/v2/reference/financials` - Can calculate ratios from financials

**Implementation**:

**File**: `backend/app/sources/fundamental_source.py`
```python
class FundamentalSource:
    """Fetch fundamental metrics and ratios."""

    def fetch_valuation_ratios(self, ticker: str) -> dict:
        """Get P/E, P/S, P/B, PEG ratios."""
        # Priority: yfinance -> FMP -> calculate from financials

    def fetch_profitability_metrics(self, ticker: str) -> dict:
        """Get margins, ROE, ROA, ROIC."""

    def fetch_financial_health(self, ticker: str) -> dict:
        """Get debt ratios, liquidity ratios."""
```

**Parse Existing yfinance Data**:

Current `reference_cache.reference_payload` (JSON) already contains:
- `trailingPE`, `forwardPE`, `priceToBook`, `dividendYield`, `payoutRatio`

**Quick Win**: Parse this JSON and extract to dedicated columns!

```python
def parse_yfinance_fundamentals():
    """Extract fundamental metrics from existing reference_payload JSON."""
    conn.execute("""
        UPDATE reference_cache
        SET
            pe_ratio_trailing = (reference_payload->>'trailingPE')::DOUBLE PRECISION,
            pe_ratio_forward = (reference_payload->>'forwardPE')::DOUBLE PRECISION,
            pb_ratio = (reference_payload->>'priceToBook')::DOUBLE PRECISION,
            dividend_yield = (reference_payload->>'dividendYield')::DOUBLE PRECISION,
            payout_ratio = (reference_payload->>'payoutRatio')::DOUBLE PRECISION
        WHERE reference_payload IS NOT NULL
    """)
```

**Scheduled Task**:
```python
@celery_app.task(name="update_fundamental_metrics_daily")
def update_fundamental_metrics():
    """Refresh fundamental metrics for all watchlist + portfolio tickers.

    Runs daily at 05:30 UTC.
    """
```

**API Enhancement**:

Add to existing endpoints:
- **GET /api/watchlist** - Include P/E, P/S, P/B in response
- **GET /api/market/prices** - Add valuation ratios
- **GET /api/analytics/valuation/{ticker}** - Detailed valuation analysis
  - Compare P/E to sector average
  - Show P/E percentile rank (vs 52-week range)
  - PEG ratio interpretation

**Frontend Display**:

1. **Watchlist Card**: Add "Valuation" section in breakdown
   - P/E ratio with color coding (undervalued/overvalued vs sector)
   - P/S, P/B ratios
   - Dividend yield (if applicable)

2. **Stock Detail Page**: Add "Fundamentals" tab
   - Valuation metrics table
   - Comparison to sector averages
   - Historical P/E chart (if available)

**Acceptance Criteria**:
- [ ] P/E, P/S, P/B ratios available for all watchlist stocks
- [ ] Ratios refreshed daily
- [ ] API returns valuation metrics
- [ ] Watchlist "Valuation" score shows actual value (not N/A)
- [ ] Can compare P/E to sector average
- [ ] Frontend displays valuation metrics with interpretation

---

## Phase 3: Enhanced Positioning Data (P1)

### Task 5: Add Analyst Ratings & Price Targets

**Objective**: Know what Wall Street thinks (consensus view)

**Data Needed**:
- Number of analyst ratings (buy/hold/sell breakdown)
- Consensus rating (Strong Buy to Strong Sell, 1-5 scale)
- Average price target
- High/low price target range
- Recent upgrades/downgrades

**Schema**:

```sql
CREATE TABLE analyst_ratings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    as_of_date DATE NOT NULL,

    -- Consensus
    num_analysts INTEGER,
    strong_buy INTEGER,
    buy INTEGER,
    hold INTEGER,
    sell INTEGER,
    strong_sell INTEGER,
    consensus_rating DOUBLE PRECISION,  -- 1.0 (Strong Buy) to 5.0 (Strong Sell)
    consensus_label VARCHAR(20),  -- 'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'

    -- Price Targets
    target_price_mean DOUBLE PRECISION,
    target_price_median DOUBLE PRECISION,
    target_price_high DOUBLE PRECISION,
    target_price_low DOUBLE PRECISION,
    target_upside_pct DOUBLE PRECISION,  -- (mean - current_price) / current_price * 100

    -- Recent Activity
    recent_upgrades INTEGER,  -- Last 30 days
    recent_downgrades INTEGER,

    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, as_of_date)
);

CREATE INDEX idx_analyst_ratings_ticker ON analyst_ratings(ticker);
CREATE INDEX idx_analyst_ratings_date ON analyst_ratings(as_of_date DESC);
```

**Data Sources**:

1. **yfinance** (Free):
   - `ticker.recommendations` - Historical analyst recommendations
   - `ticker.analyst_price_target` - Price targets (mean, high, low)
   - Already have in `reference_cache`: `recommendation_key`, `recommendation_mean`, `target_mean_price`

2. **FMP** (250/day):
   - `/v3/analyst-stock-recommendations/{ticker}` - Detailed analyst data
   - `/v3/upgrades-downgrades/{ticker}` - Recent rating changes

**Implementation**: Similar to fundamental metrics (parse existing yfinance data, enhance with FMP)

**Acceptance Criteria**:
- [ ] Analyst consensus rating available for all watchlist stocks
- [ ] Price target upside % calculated
- [ ] Can see recent upgrades/downgrades
- [ ] API endpoint: GET /api/analytics/analysts/{ticker}

---

### Task 6: Add Insider Trading Tracker (SEC Form 4)

**Objective**: Track insider buying/selling (smart money indicator)

**Data Needed**:
- Insider name and title
- Transaction date
- Transaction type (Buy/Sell/Option Exercise)
- Shares traded
- Price per share
- Total value
- Shares owned after transaction

**Schema**:

```sql
CREATE TABLE insider_transactions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    transaction_date DATE NOT NULL,
    filing_date DATE NOT NULL,

    -- Insider Info
    insider_name VARCHAR(255),
    insider_title VARCHAR(255),
    is_director BOOLEAN,
    is_officer BOOLEAN,
    is_ten_percent_owner BOOLEAN,

    -- Transaction
    transaction_type VARCHAR(50),  -- 'P' (Purchase), 'S' (Sale), 'A' (Award), etc.
    transaction_code VARCHAR(10),
    shares DOUBLE PRECISION,
    price_per_share DOUBLE PRECISION,
    total_value DOUBLE PRECISION,
    shares_owned_after DOUBLE PRECISION,

    -- Metadata
    source VARCHAR(50),  -- 'sec_edgar', 'fmp', 'polygon'
    form_type VARCHAR(10),  -- 'Form 4', 'Form 3', 'Form 5'
    sec_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, transaction_date, insider_name, shares)
);

CREATE INDEX idx_insider_ticker ON insider_transactions(ticker);
CREATE INDEX idx_insider_date ON insider_transactions(transaction_date DESC);
CREATE INDEX idx_insider_type ON insider_transactions(transaction_type);
```

**Data Sources**:

1. **SEC EDGAR** (Free, unlimited):
   - Already have `sec_edgar_source.py` and `sec_cik_fetcher.py`
   - Form 4 filings: Recent insider transactions
   - Need to parse XML/HTML forms

2. **FMP** (250/day):
   - `/v4/insider-trading` - Pre-parsed insider data
   - Easier than parsing SEC directly

3. **Polygon** (5/min):
   - `/v2/reference/insiders` - Insider ownership data

**Implementation**:

Use FMP for quick win, fall back to SEC EDGAR parsing if needed.

**Sentiment Calculation**:
- Net insider buying = Sum(Purchases) - Sum(Sales) over last 90 days
- Insider sentiment score: 0-100 based on buy/sell ratio

**Acceptance Criteria**:
- [ ] Track insider transactions for watchlist stocks
- [ ] Calculate insider sentiment score (net buying/selling)
- [ ] API endpoint: GET /api/analytics/insiders/{ticker}
- [ ] Watchlist shows insider activity indicator (e.g., "🔥 Heavy Buying")

---

### Task 7: Add Short Interest Data

**Objective**: Identify short squeeze candidates and crowded shorts

**Data Needed**:
- Short interest (shares sold short)
- Shares float (total shares available for trading)
- Short % of float (short interest / float * 100)
- Days to cover (short interest / avg daily volume)
- Change in short interest (vs last report)

**Schema**:

```sql
CREATE TABLE short_interest (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL,

    -- Short Data
    short_interest BIGINT,  -- Shares sold short
    shares_float BIGINT,
    short_pct_float DOUBLE PRECISION,
    days_to_cover DOUBLE PRECISION,

    -- Change Analysis
    prev_short_interest BIGINT,
    short_interest_change_pct DOUBLE PRECISION,

    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, report_date)
);

CREATE INDEX idx_short_ticker ON short_interest(ticker);
CREATE INDEX idx_short_date ON short_interest(report_date DESC);
CREATE INDEX idx_short_pct ON short_interest(short_pct_float DESC);  -- Find most shorted
```

**Data Sources**:

1. **FMP** (250/day):
   - `/v4/shares_float` - Shares float data
   - Combined with short interest from other sources

2. **yfinance** (Free):
   - `ticker.info` has `shortPercentOfFloat`, `sharesShort`, `sharesOutstanding`
   - Already fetched, need to parse

3. **FINRA** (Free, official):
   - Short interest reported twice monthly
   - Can scrape or use API

**Acceptance Criteria**:
- [ ] Short % of float available for watchlist stocks
- [ ] Days to cover calculated
- [ ] API endpoint: GET /api/analytics/short/{ticker}
- [ ] Watchlist flags high short interest (>20% of float)
- [ ] Can sort watchlist by short % (identify squeeze candidates)

---

## Phase 4: Portfolio & Performance Tracking (P2)

### Task 8: Add Portfolio Transaction Ledger

**Objective**: Track all trades, calculate realized/unrealized P&L over time

**Schema**:

```sql
CREATE TABLE portfolio_transactions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES portfolio_accounts(id),
    ticker VARCHAR(10) NOT NULL,
    transaction_date DATE NOT NULL,
    transaction_time TIME,

    -- Transaction Details
    transaction_type VARCHAR(10) NOT NULL,  -- 'BUY', 'SELL'
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION DEFAULT 0,
    total_amount DOUBLE PRECISION NOT NULL,  -- quantity * price + commission

    -- P&L (for sells)
    cost_basis DOUBLE PRECISION,  -- Average cost of shares sold
    realized_gain_loss DOUBLE PRECISION,  -- (price - cost_basis) * quantity - commission

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transactions_account ON portfolio_transactions(account_id);
CREATE INDEX idx_transactions_ticker ON portfolio_transactions(ticker);
CREATE INDEX idx_transactions_date ON portfolio_transactions(transaction_date DESC);
CREATE INDEX idx_transactions_type ON portfolio_transactions(transaction_type);

-- Portfolio Performance Snapshots (daily)
CREATE TABLE portfolio_snapshots (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES portfolio_accounts(id),
    snapshot_date DATE NOT NULL,

    -- Portfolio Value
    total_value DOUBLE PRECISION NOT NULL,
    cash_balance DOUBLE PRECISION DEFAULT 0,
    positions_value DOUBLE PRECISION NOT NULL,

    -- Performance
    daily_return_pct DOUBLE PRECISION,
    total_return_pct DOUBLE PRECISION,
    realized_gains DOUBLE PRECISION,
    unrealized_gains DOUBLE PRECISION,

    -- Risk Metrics
    portfolio_beta DOUBLE PRECISION,
    portfolio_volatility DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown_pct DOUBLE PRECISION,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (account_id, snapshot_date)
);

CREATE INDEX idx_snapshots_account ON portfolio_snapshots(account_id);
CREATE INDEX idx_snapshots_date ON portfolio_snapshots(snapshot_date DESC);
```

**Acceptance Criteria**:
- [ ] Can log buy/sell transactions
- [ ] Realized P&L calculated automatically on sells
- [ ] Daily portfolio snapshots capture performance
- [ ] Can view transaction history
- [ ] API endpoint: GET /api/portfolio/transactions
- [ ] API endpoint: GET /api/portfolio/performance?days=30

---

## Phase 5: Historical Depth & Quality (P2)

### Task 9: Extend Historical Data Coverage

**Objective**: Ensure 252+ trading days (1 year) for all market symbols

**Current State**:
- SPY: 259 days (good)
- Other symbols: Varies, some only have a few days

**Action**:
- Run `maintain-historical-market-data` task manually for all symbols
- Verify 252+ days for: SPY, ^GSPC, ^VIX, ^TNX, DX-Y.NYB, all 11 sector ETFs
- Backfill watchlist symbols to 252 days
- Add health check to alert if data falls below 200 days

**Acceptance Criteria**:
- [ ] All market symbols have 252+ days of OHLCV data
- [ ] All watchlist symbols have 252+ days
- [ ] Technical indicators (SMA_200) can be calculated accurately
- [ ] Fear & Greed percentile rankings work correctly (need 252-day window)

---

## Task 0: Fix Real-Time Data Pipeline (CRITICAL - Do This FIRST!)

**Problem**: Fear & Greed showing "3 days old" on dashboard

**Root Causes**:
1. **❌ Scheduled tasks run ONCE daily** at 02:00-04:00 UTC (before US market opens)
2. **❌ Always fetch YESTERDAY's data** (not today's)
3. **❌ No intraday updates** during market hours
4. **❌ Data sits stale** from Friday close until Monday update

**Current Behavior**:
- Nov 13 (today): Dashboard shows Nov 10 data (3 days old!)
- Scheduled update at 03:00 UTC Nov 14 will show Nov 13 data (still 1 day behind)
- Always AT LEAST 1 day old, up to 3 days on weekends

**Required Behavior**:

**During Market Hours** (9:30 AM - 4:00 PM ET, Mon-Fri):
- Fetch current prices every 15-30 minutes
- Update Fear & Greed hourly
- Show LIVE market sentiment

**At Market Close** (4:00 PM ET):
- Immediate update within 15 min of close
- Calculate Fear & Greed with TODAY's final data
- Dashboard shows "As of today's close" within 30 min

**Pre-Market** (Before 9:30 AM ET):
- Use previous trading day's close (acceptable)
- Label clearly: "As of [date] close"

**Implementation**:

**0.1: Add Intraday Price Cache Updates**
```python
# New task: runs every 15 min during market hours
@celery_app.task(name="refresh_intraday_prices")
def refresh_intraday_prices():
    """Fetch current prices for market symbols + watchlist.

    Runs: Every 15 min, 9:30 AM - 4:00 PM ET, Mon-Fri
    Updates: price_cache table with current bid/ask/last
    """
```

**0.2: Add Market-Close Trigger**
```python
# New task: runs at 4:15 PM ET (15 min after close)
@celery_app.task(name="update_end_of_day_data")
def update_end_of_day_data():
    """Fetch final close prices and update all calculated metrics.

    Runs: 4:15 PM ET (16:15 ET, 21:15 UTC) Mon-Fri
    Sequence:
      1. Fetch today's OHLCV for all market symbols
      2. Update technical indicators (RSI, MACD, etc.)
      3. Calculate Fear & Greed with TODAY's data
      4. Update market intelligence
    """
```

**0.3: Update Fear & Greed to Use TODAY's Data**

Current code fetches from `fear_greed_inputs` WHERE `as_of_date = yesterday`
Change to: `as_of_date = today` and fall back to yesterday if today not available

**0.4: Add Celery Beat Schedule**
```python
# In celery_app.py beat_schedule
'refresh-intraday-prices': {
    'task': 'refresh_intraday_prices',
    'schedule': crontab(minute='*/15', hour='13-20', day_of_week='1-5'),  # 9:30 AM - 4:00 PM ET
},
'update-end-of-day-data': {
    'task': 'update_end_of_day_data',
    'schedule': crontab(hour=21, minute=15, day_of_week='1-5'),  # 4:15 PM ET daily
},
```

**Acceptance Criteria**:
- [ ] During market hours: Fear & Greed updates hourly with current prices
- [ ] At 4:15 PM ET: Dashboard shows TODAY's close data within 30 min
- [ ] Dashboard shows age: "As of 4:00 PM ET today" (not "3 days old")
- [ ] Weekends show: "As of Friday close" (acceptable 1-2 day lag)
- [ ] No more manual task triggering needed

**Priority**: **P0 - BLOCKING** - Do this BEFORE all other tasks!

---

## Parallel Agent Orchestration

**Objective**: Execute tasks concurrently using multiple explore/general agents to maximize throughput

**Why**: 60-80 hours of work can be reduced to 1-2 weeks with parallel execution

### Parallelization Strategy

**Rules**:
1. **Independent tasks run in parallel** (no data dependencies)
2. **Sequential tasks run in series** (one depends on output of another)
3. **Each agent gets complete task context** (self-contained work units)
4. **All agents report back** to main orchestrator for integration

### Execution Batches

**Batch 1: Critical Fixes (Run in Parallel)**

Agent assignments:
- **Agent 1 (Explore)**: Task 0 - Fix real-time data pipeline
  - Investigate current scheduling
  - Add intraday refresh tasks
  - Test end-of-day trigger

- **Agent 2 (Explore)**: Task 1 - Fix watchlist score breakdown
  - Investigate why Valuation/Growth/Health/Sentiment show N/A
  - Find root cause (frontend vs backend vs data)
  - Implement fix

- **Agent 3 (General)**: Task 4 - Parse existing yfinance valuation data
  - Extract P/E, P/S, P/B from reference_cache JSON
  - Add columns to database
  - Update API endpoints

**Dependencies**: None - all independent
**Duration**: 4-8 hours (parallel)
**Outcome**: Real-time data + fixed watchlist + valuation metrics

---

**Batch 2: Data Foundation (Run in Parallel after Batch 1)**

Agent assignments:
- **Agent 1 (Explore)**: Task 2 - Fix Fear & Greed Index data pipeline
  - Debug why VIX/SPY/HY_spread not populating
  - Ensure all 5 components working
  - Verify calculation with fresh data

- **Agent 2 (General)**: Task 9 - Extend historical data to 252+ days
  - Backfill SPY, VIX, sectors to 252 days
  - Add watchlist symbols
  - Verify data quality

- **Agent 3 (General)**: Task 3 - Add earnings calendar
  - Create earnings_calendar table
  - Fetch from yfinance/FMP
  - Add API endpoints
  - Update frontend to show earnings dates

**Dependencies**: Batch 1 must complete (need real-time pipeline working)
**Duration**: 6-10 hours (parallel)
**Outcome**: Complete Fear & Greed + historical depth + earnings calendar

---

**Batch 3: Enhanced Metrics (Run in Parallel after Batch 2)**

Agent assignments:
- **Agent 1 (General)**: Task 5 - Analyst ratings & price targets
  - Parse existing yfinance analyst data
  - Create analyst_ratings table
  - Add API endpoints

- **Agent 2 (General)**: Task 6 - Insider trading tracker
  - Create insider_transactions table
  - Integrate FMP insider data API
  - Calculate insider sentiment score

- **Agent 3 (General)**: Task 7 - Short interest data
  - Create short_interest table
  - Parse yfinance short data
  - Add "high short %" flags to watchlist

**Dependencies**: Batch 2 complete (need fundamental infrastructure)
**Duration**: 8-12 hours (parallel)
**Outcome**: Analyst consensus + insider activity + short interest

---

**Batch 4: Portfolio Tracking (Run After Batch 3)**

Agent assignment:
- **Agent 1 (General)**: Task 8 - Portfolio transaction ledger
  - Create portfolio_transactions table
  - Create portfolio_snapshots table
  - Add P&L tracking
  - Calculate risk metrics (Sharpe, max drawdown)

**Dependencies**: Batch 3 complete (need all data sources for portfolio analysis)
**Duration**: 6-8 hours (single agent)
**Outcome**: Complete transaction history + performance tracking

---

### Orchestration Commands

**Launch Batch 1** (3 agents in parallel):
```bash
# In a single /do_it or /task_it response, launch all 3:
Task(subagent_type="Explore", description="Fix real-time data pipeline", prompt="...")
Task(subagent_type="Explore", description="Fix watchlist scores", prompt="...")
Task(subagent_type="general-purpose", description="Parse valuation data", prompt="...")
```

**Wait for Batch 1 completion, then launch Batch 2**, etc.

---

### Coordination Requirements

**Each agent receives**:
1. **Complete context**: Full task description from PRD
2. **Acceptance criteria**: Clear definition of done
3. **Database schema**: Current state + required changes
4. **API contracts**: Expected request/response formats
5. **Testing instructions**: How to verify their changes

**Each agent reports back**:
1. **Files changed**: List of all modified files
2. **Database migrations**: SQL scripts to run
3. **API changes**: New/modified endpoints
4. **Test results**: Proof that acceptance criteria met
5. **Integration notes**: What the orchestrator needs to merge their work

**Orchestrator responsibilities**:
1. Launch agents with complete task context
2. Monitor progress (check for failures, ask clarifying questions)
3. Integrate changes (ensure no conflicts)
4. Run final integration tests
5. Deploy to production

---

### Time Savings

**Sequential execution**: 60-80 hours = 7-10 days (8 hrs/day)

**Parallel execution**:
- Batch 1: 8 hours (day 1)
- Batch 2: 10 hours (day 2)
- Batch 3: 12 hours (days 3-4)
- Batch 4: 8 hours (day 5)
- Integration & testing: 4 hours (day 6)

**Total: ~6 days vs 10 days** (40% faster)

**With more agents** (5-6 agents):
- Could compress to 3-4 days

---

## Implementation Order

**REVISED ORDER** (with parallel execution):

**Day 1 (Batch 1 - Critical Fixes)**:
- Task 0: Real-time data pipeline (Agent 1)
- Task 1: Watchlist score breakdown (Agent 2)
- Task 4: Parse yfinance valuation data (Agent 3)

**Day 2 (Batch 2 - Data Foundation)**:
- Task 2: Fear & Greed Index (Agent 1)
- Task 9: Extend historical data (Agent 2)
- Task 3: Earnings calendar (Agent 3)

**Days 3-4 (Batch 3 - Enhanced Metrics)**:
- Task 5: Analyst ratings (Agent 1)
- Task 6: Insider trading (Agent 2)
- Task 7: Short interest (Agent 3)

**Day 5 (Batch 4 - Portfolio)**:
- Task 8: Transaction ledger (Agent 1)

**Day 6 (Integration)**:
- Merge all changes
- Run integration tests
- Deploy

---

## Original Implementation Order (Sequential)

**Week 1 (Critical Fixes)**:
1. Task 1: Fix Watchlist Score Breakdown (2-4 hours)
2. Task 2: Fix Fear & Greed Index (4-8 hours)
3. Task 4: Parse existing yfinance valuation data (2-3 hours)

**Week 2 (Trading Essentials)**:
4. Task 3: Add Earnings Calendar (6-8 hours)
5. Task 5: Enhance Analyst Ratings (4-6 hours)
6. Task 9: Extend Historical Data (2-3 hours)

**Week 3 (Advanced Positioning)**:
7. Task 6: Add Insider Trading (8-10 hours)
8. Task 7: Add Short Interest (4-6 hours)

**Week 4 (Portfolio Enhancement)**:
9. Task 8: Add Transaction Ledger (6-8 hours)
10. Calculate Portfolio Risk Metrics (4-6 hours)

---

## Success Metrics

After completion, AI trading advisor can:
- ✅ Time the market (Fear & Greed fully working)
- ✅ Avoid earnings shocks (know when stocks report)
- ✅ Identify value (P/E, P/S, P/B ratios)
- ✅ Follow smart money (insider buying/selling)
- ✅ Find squeeze candidates (high short interest)
- ✅ Track performance (transaction history, realized P&L)
- ✅ Assess risk (Sharpe ratio, max drawdown)
- ✅ Make data-driven recommendations (no assumptions)

**End Goal**: AI can say "Buy AAPL because..." with real data supporting every claim:
- Earnings in 3 weeks (avoid timing risk)
- P/E of 28 vs sector average 32 (undervalued)
- Insiders bought $2M last month (confidence)
- Short interest 2% (no squeeze risk)
- Target price $280 vs current $265 (5.7% upside)
- Strong Buy rating from 15 analysts

---

**Total Effort Estimate**: 60-80 hours (2-3 weeks for one developer)
**Priority Focus**: Fix existing features (Tasks 1-2) before adding new ones
**Quick Wins**: Parse existing yfinance data (Task 4) - data already fetched, just needs extraction
