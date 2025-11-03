# PRD #0011: Strategic Analytics Features (Backtesting & Historical Tracking)

**Status**: Ready for Implementation (after PRD #0010)
**Created**: 2025-10-27
**Priority**: Medium (Strategic value, high effort)
**Estimated Effort**: Large (2 complex features, 16-20 hours)

---

## Introduction/Overview

This PRD introduces two strategic analytics capabilities that transform portfolio-ai from a point-in-time tool into a comprehensive investment intelligence platform:

1. **Backtesting Framework** - Validate AI-generated investment ideas against historical data
2. **Historical Portfolio Tracking** - Track portfolio performance over time with rich analytics

These features enable users to:
- Test agent ideas before executing them (reduce risk)
- Measure agent accuracy and improve prompts over time
- Visualize portfolio performance trends (not just current snapshot)
- Calculate risk-adjusted returns (Sharpe ratio, drawdown)
- Identify what's working and what's not

**Problem Statement**:
- Agent ideas have no historical validation (users must trust blindly)
- No way to measure agent performance over time
- No portfolio performance history (only current values)
- Can't answer "How did my portfolio perform over the last 30 days?"
- No risk-adjusted return metrics (Sharpe ratio, max drawdown)

---

## Goals

1. **Enable idea validation** - Test agent ideas against historical data before risking capital
2. **Measure agent performance** - Track hit rate, avg gain/loss, time to target for ideas
3. **Portfolio performance tracking** - Daily snapshots with trend analysis
4. **Risk-adjusted analytics** - Calculate Sharpe ratio, max drawdown, rolling returns
5. **Data-driven decision making** - Show users which ideas perform best historically
6. **Visual insights** - Charts showing portfolio growth, drawdown, sector drift over time

---

## User Stories

### As an **investor**:
- I want to backtest an agent idea before executing it so I can estimate potential risk/reward
- I want to see how my portfolio has performed over the last 30/60/90 days
- I want to know my portfolio's Sharpe ratio so I can compare to benchmarks
- I want to see my max drawdown so I know the worst-case scenario I've experienced
- I want charts showing portfolio value over time so I can visualize growth trends

### As a **portfolio manager**:
- I want to track which agent ideas performed well historically so I can refine prompts
- I want to see sector exposure trends over time so I can catch drift early
- I want risk-adjusted metrics (Sharpe, Sortino) so I can evaluate performance properly
- I want to export historical data for external analysis (CSV)

### As a **power user**:
- I want to compare my portfolio's performance to S&P 500
- I want to see correlation between my holdings and market movements
- I want to test "what if" scenarios (e.g., "What if I had bought this idea 30 days ago?")

---

## Functional Requirements

## Feature 1: Backtesting Framework for Agent Ideas

**Priority**: P2 (Strategic, high value)

### 1.1 Historical Data Collection

1.1.1. Add yfinance historical data fetching (up to 10 years lookback)
1.1.2. Cache historical OHLCV data in new `historical_prices` table:
   - `symbol TEXT`, `date DATE`, `open DOUBLE`, `high DOUBLE`, `low DOUBLE`, `close DOUBLE`, `volume DOUBLE`, `source TEXT`
1.1.3. Fetch historical data on-demand when backtesting an idea
1.1.4. Also store forward snapshots going forward (daily price snapshots for all watched symbols)
1.1.5. Add background job to update historical_prices daily for active symbols

### 1.2 Backtest Execution Engine

1.2.1. Create `BacktestEngine` class in `backend/app/analytics/backtest.py`
1.2.2. Implement `backtest_idea(idea_id: str, start_date: date, end_date: date) -> BacktestResult`
1.2.3. Parse idea action field to extract:
   - Symbol(s)
   - Entry price or date
   - Target price or time horizon
   - Stop loss (if specified)
1.2.4. Simulate trade execution:
   - Buy at entry price (or next day's open)
   - Sell at target price, stop loss, or end_date (whichever comes first)
   - Calculate gain/loss %
   - Calculate holding period (days)
1.2.5. Handle different idea types:
   - `long`: Buy symbol, sell at target or time horizon
   - `short`: Short symbol, cover at target or time horizon
   - `pairs_trade`: Long one symbol, short another
1.2.6. Calculate metrics:
   - Total return %
   - Annualized return %
   - Win/loss outcome (target reached vs. not)
   - Days to target (or timeout)
   - Max drawdown during hold period
   - Risk-adjusted return (return / max drawdown)

### 1.3 Backtest Results Storage

1.3.1. Create `backtest_results` table:
   - `id TEXT PRIMARY KEY`
   - `idea_id TEXT` (FK to agent_ideas)
   - `symbol TEXT`
   - `start_date DATE`
   - `end_date DATE`
   - `entry_price DOUBLE`
   - `exit_price DOUBLE`
   - `total_return_pct DOUBLE`
   - `annualized_return_pct DOUBLE`
   - `holding_days INTEGER`
   - `win BOOLEAN` (target reached)
   - `max_drawdown_pct DOUBLE`
   - `risk_adjusted_return DOUBLE`
   - `executed_at TIMESTAMP`
1.3.2. Store detailed trade log (entry/exit prices, dates, events)

### 1.4 API Endpoints

1.4.1. `POST /api/ideas/{id}/backtest` - Run backtest for idea
   - Request body: `{start_date: "2024-01-01", end_date: "2024-10-01"}`
   - Response: BacktestResult with metrics
1.4.2. `GET /api/ideas/{id}/backtest/history` - Get all backtest runs for idea
1.4.3. `GET /api/analytics/backtest/summary` - Get backtest performance summary across all ideas
   - Win rate, avg return, avg holding period

### 1.5 Frontend Integration

1.5.1. Add "Backtest Idea" button on idea details page
1.5.2. Show backtest form: select date range (default: last 90 days)
1.5.3. Display backtest results:
   - Total return % with color coding (green/red)
   - Holding period (days)
   - Win/loss badge
   - Max drawdown %
   - Risk-adjusted return
   - Chart showing price movement during backtest period
1.5.4. Show historical backtest runs table (date, return %, win/loss)
1.5.5. Add backtest summary card on Dashboard:
   - "Agent Ideas Performance: 65% win rate, avg +8.2% return over 90 days"

---

## Feature 2: Historical Portfolio Tracking & Analytics

**Priority**: P2 (Strategic, high value)

### 2.1 Daily Portfolio Snapshots

2.1.1. Create `portfolio_snapshots` table:
   - `id TEXT PRIMARY KEY`
   - `snapshot_date DATE NOT NULL`
   - `total_value DOUBLE`
   - `total_cost_basis DOUBLE`
   - `total_gain DOUBLE`
   - `total_gain_pct DOUBLE`
   - `portfolio_beta DOUBLE`
   - `portfolio_volatility DOUBLE`
   - `num_positions INTEGER`
   - `snapshot_data JSON` (full position details)
   - `created_at TIMESTAMP`
2.1.2. Create `position_snapshots` table (detailed holdings):
   - `id TEXT PRIMARY KEY`
   - `snapshot_date DATE`
   - `symbol TEXT`
   - `shares DOUBLE`
   - `cost_basis DOUBLE`
   - `current_price DOUBLE`
   - `market_value DOUBLE`
   - `gain_pct DOUBLE`
   - `weight_pct DOUBLE` (% of portfolio)
2.1.3. Add background job to create daily snapshots at market close (4:00 PM ET)
2.1.4. Calculate and store all portfolio analytics (reuse existing PortfolioAnalytics)

### 2.2 Historical Analytics Engine

2.2.1. Create `HistoricalAnalytics` class in `backend/app/analytics/historical.py`
2.2.2. Implement time-series metrics:
   - **Portfolio value over time**: List of (date, value) tuples
   - **Cumulative return**: (current_value - initial_value) / initial_value * 100
   - **Annualized return**: ((end_value / start_value) ^ (365 / days)) - 1
   - **Volatility**: Std dev of daily returns
   - **Sharpe ratio**: (annualized_return - risk_free_rate) / volatility
   - **Max drawdown**: Largest peak-to-trough decline
   - **Rolling returns**: 7-day, 30-day, 90-day windows
2.2.3. Implement comparison metrics:
   - Portfolio vs. S&P 500 (fetch SPY prices)
   - Alpha (excess return vs. benchmark)
   - Beta (correlation to benchmark)
2.2.4. Implement sector exposure trends:
   - Track % in each sector over time
   - Identify sector drift (big changes in allocation)
2.2.5. Calculate risk-adjusted metrics:
   - Sortino ratio (downside deviation only)
   - Calmar ratio (return / max drawdown)

### 2.3 API Endpoints

2.3.1. `GET /api/portfolio/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
   - Returns portfolio snapshots for date range
   - Default: Last 90 days
2.3.2. `GET /api/portfolio/analytics/historical?period={7d|30d|90d|1y|all}`
   - Returns calculated metrics (Sharpe, drawdown, volatility, etc.)
2.3.3. `GET /api/portfolio/performance?compare_to=SPY`
   - Returns portfolio vs. benchmark comparison
2.3.4. `GET /api/portfolio/export?format={csv|json}&start_date=YYYY-MM-DD`
   - Export historical snapshots for external analysis

### 2.4 Frontend Visualization

2.4.1. Add "Performance" tab to Portfolio page
2.4.2. Create portfolio value line chart (Recharts):
   - X-axis: Date
   - Y-axis: Portfolio value ($)
   - Line: Portfolio value over time
   - Optional benchmark overlay (SPY)
2.4.3. Create metrics summary cards:
   - Total Return (%, $ gain)
   - Annualized Return (%)
   - Sharpe Ratio (with tooltip explaining)
   - Max Drawdown (%, date range)
   - Current Beta
   - Current Volatility (%)
2.4.4. Create sector exposure area chart:
   - Stacked area showing % in each sector over time
   - Helps visualize rebalancing and drift
2.4.5. Create drawdown chart:
   - Shows peak-to-trough declines over time
   - Highlights max drawdown period
2.4.6. Add time period selector: 7D, 30D, 90D, 1Y, ALL
2.4.7. Add "Export Data" button (download CSV)

### 2.5 Background Jobs

2.5.1. Create `SnapshotScheduler` in `backend/app/jobs/snapshot_scheduler.py`
2.5.2. Schedule daily snapshot job (Celery periodic task):
   - Run at 4:30 PM ET (after market close)
   - Fetch current positions
   - Fetch current prices
   - Calculate analytics
   - Store snapshot
2.5.3. Add snapshot cleanup job (delete snapshots older than 2 years)
2.5.4. Add missing snapshot backfill job (fill gaps in historical data)

---

## Non-Goals (Out of Scope)

- ❌ Real-time backtesting with minute-level data (daily granularity is sufficient)
- ❌ Multi-portfolio tracking (single portfolio only for v1)
- ❌ Custom benchmark comparisons beyond SPY (can add later)
- ❌ Grafana/external dashboards (built-in frontend charts only)
- ❌ Machine learning models to predict idea success (just historical validation)
- ❌ Automated rebalancing based on drift (manual only)
- ❌ Tax lot tracking (FIFO/LIFO accounting)
- ❌ Dividend/split adjustments in backtests (price-only for v1)

---

## Technical Considerations

### Dependencies to Add

```txt
# requirements.txt additions
# No new dependencies required - uses existing libraries:
# - yfinance (already installed)
# - pandas/numpy (via analytics)
# - celery (from PRD #0010 Feature 8)
```

### Database Schema Changes

**Feature 1 - Backtesting**:
```sql
CREATE TABLE IF NOT EXISTS historical_prices (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    source TEXT DEFAULT 'yfinance',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX idx_historical_prices_symbol ON historical_prices(symbol);
CREATE INDEX idx_historical_prices_date ON historical_prices(date);

CREATE TABLE IF NOT EXISTS backtest_results (
    id TEXT PRIMARY KEY,
    idea_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    entry_price DOUBLE,
    exit_price DOUBLE,
    total_return_pct DOUBLE,
    annualized_return_pct DOUBLE,
    holding_days INTEGER,
    win BOOLEAN,
    max_drawdown_pct DOUBLE,
    risk_adjusted_return DOUBLE,
    trade_log JSON,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (idea_id) REFERENCES agent_ideas(id)
);
CREATE INDEX idx_backtest_idea ON backtest_results(idea_id);
```

**Feature 2 - Historical Tracking**:
```sql
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_date DATE NOT NULL UNIQUE,
    total_value DOUBLE NOT NULL,
    total_cost_basis DOUBLE NOT NULL,
    total_gain DOUBLE,
    total_gain_pct DOUBLE,
    portfolio_beta DOUBLE,
    portfolio_volatility DOUBLE,
    num_positions INTEGER,
    snapshot_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshots_date ON portfolio_snapshots(snapshot_date);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id TEXT PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    shares DOUBLE NOT NULL,
    cost_basis DOUBLE NOT NULL,
    current_price DOUBLE,
    market_value DOUBLE,
    gain_pct DOUBLE,
    weight_pct DOUBLE,
    sector TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_date) REFERENCES portfolio_snapshots(snapshot_date)
);
CREATE INDEX idx_position_snapshots_date ON position_snapshots(snapshot_date);
CREATE INDEX idx_position_snapshots_symbol ON position_snapshots(symbol);
```

### Performance Considerations

1. **Historical data caching**: Cache yfinance historical fetches for 24 hours
2. **Snapshot queries**: Index by date for fast range queries
3. **Frontend charts**: Limit to 365 data points max (downsample if needed)
4. **Backtest execution**: Limit to 1-year lookback for MVP (longer = slower)
5. **Daily snapshot job**: Should complete in <30 seconds

### Data Source Dependencies

- **yfinance** for historical OHLCV data (free, unlimited history)
- **yfinance** for SPY benchmark data
- Existing **multi-source price fetcher** (from PRD #0010 Feature 7) for current prices

---

## Success Metrics

### Feature 1: Backtesting
1. **Backtest execution time**: <5 seconds for 90-day backtest ✅
2. **Historical data coverage**: 365+ days for active symbols ✅
3. **Backtest accuracy**: Matches manual calculation within 1% ✅
4. **Agent performance visibility**: Dashboard shows win rate % ✅

### Feature 2: Historical Tracking
1. **Snapshot reliability**: Daily snapshots created 95%+ of days ✅
2. **Chart load time**: <2 seconds for 90-day chart ✅
3. **Metric accuracy**: Sharpe ratio matches manual calculation ✅
4. **Data completeness**: Zero gaps in daily snapshots ✅

---

## Open Questions

1. **TO CLARIFY** - Backtest commission/slippage: Assume zero or model realistic costs?
   - **Recommendation**: Zero for MVP, add 0.1% commission later

2. **TO CLARIFY** - Snapshot storage limit: Keep forever or delete old snapshots?
   - **Recommendation**: Keep 2 years, delete older (configurable)

3. **TO CLARIFY** - Benchmark selection: SPY only or allow user to choose?
   - **Recommendation**: SPY only for MVP, add selector later

4. **TO CLARIFY** - Missing historical data: Backfill from yfinance or fail gracefully?
   - **Recommendation**: Backfill on-demand when backtesting

5. **TO CLARIFY** - Sharpe ratio risk-free rate: Use current Fed Funds rate or hardcode 4%?
   - **Recommendation**: Fetch current Fed Funds rate from FRED (already integrated)

6. **TO CLARIFY** - Chart library: Recharts (existing) or switch to Plotly for more features?
   - **Recommendation**: Recharts (consistent with existing UI)

---

## Design Considerations

### Feature 1: Backtest Example

**Agent Idea**:
- Title: "Long AAPL - AI Momentum Play"
- Action: "Buy AAPL at $170, target $185 (8.8% gain) within 30 days"
- Created: 2024-09-15

**Backtest Request** (90 days prior):
- Start: 2024-06-15
- End: 2024-09-15
- Idea: "Buy AAPL at market, target +8.8%, 30-day horizon"

**Backtest Execution**:
1. Fetch AAPL historical prices (2024-06-15 to 2024-09-15)
2. Entry: 2024-06-17 open = $168.50 (next trading day)
3. Target: $168.50 * 1.088 = $183.33
4. Outcome: AAPL reached $183.50 on 2024-07-10 (23 days)
5. Exit: 2024-07-10 close = $183.50
6. Result:
   - Total return: +8.9% ✅ WIN
   - Holding period: 23 days (within 30-day target)
   - Annualized return: +142%
   - Max drawdown: -2.1% (dipped to $165 on June 20)
   - Risk-adjusted return: 8.9 / 2.1 = 4.24

**Display to User**:
```
Backtest Result: ✅ WIN
Total Return: +8.9%
Holding Period: 23 days (target: 30 days)
Max Drawdown: -2.1%
Risk-Adjusted Return: 4.24x

Conclusion: Idea would have succeeded if executed 90 days ago.
```

### Feature 2: Historical Analytics Example

**Portfolio Snapshots** (Last 30 days):
```
Date         Value      Gain%   Beta   Volatility
2024-09-27   $125,430   +2.4%   1.15   18.5%
2024-09-28   $126,100   +3.0%   1.14   18.2%
...
2024-10-27   $132,850   +8.6%   1.12   17.8%
```

**Calculated Metrics**:
- **30-Day Return**: +5.9% (vs. SPY +3.2%)
- **Annualized Return**: +78.2%
- **Sharpe Ratio**: 2.85 (excellent, >2 is good)
- **Max Drawdown**: -3.2% (occurred Oct 5-8)
- **Alpha**: +2.7% (outperforming SPY)
- **Beta**: 1.12 (12% more volatile than market)

**Chart**:
- Line chart showing portfolio value growing from $125k to $132k over 30 days
- SPY overlay showing $100k hypothetical investment growing to $103k
- Clearly outperforming benchmark

---

## Documentation Updates Required

- `docs/core/API_REFERENCE.md`: Document backtest and historical analytics endpoints
- `docs/core/OPERATIONS.md`: Document snapshot scheduler setup (Celery beat)
- User guide: Create `docs/guides/backtesting.md` explaining how to interpret results
- User guide: Create `docs/guides/performance-tracking.md` explaining metrics (Sharpe, drawdown)

---

## Dependencies on Other PRDs

**Requires PRD #0010** (must be completed first):
- Feature 3 (Structured logging) - Needed for backtest execution logging
- Feature 7 (Multi-source fetcher) - Needed for reliable price data
- Feature 8 (Background tasks) - Needed for daily snapshot job

---

## Implementation Roadmap

### Phase 1: Historical Data Foundation (4 hours)
- [ ] Create `historical_prices` table
- [ ] Implement yfinance historical data fetcher
- [ ] Add caching logic (24-hour TTL)
- [ ] Test with 1-year AAPL data

### Phase 2: Backtesting Engine (6 hours)
- [ ] Create `BacktestEngine` class
- [ ] Implement trade simulation logic
- [ ] Create `backtest_results` table
- [ ] Add API endpoint `POST /api/ideas/{id}/backtest`
- [ ] Add unit tests for backtest calculations
- [ ] Frontend: Add backtest button and results display

### Phase 3: Portfolio Snapshots (4 hours)
- [ ] Create `portfolio_snapshots` and `position_snapshots` tables
- [ ] Implement snapshot creation logic
- [ ] Add Celery periodic task (4:30 PM ET daily)
- [ ] Test snapshot creation with real portfolio
- [ ] Add API endpoint `GET /api/portfolio/history`

### Phase 4: Historical Analytics (4 hours)
- [ ] Create `HistoricalAnalytics` class
- [ ] Implement Sharpe ratio, max drawdown, rolling returns
- [ ] Add benchmark comparison (SPY)
- [ ] Add API endpoint `GET /api/portfolio/analytics/historical`
- [ ] Add export endpoint `GET /api/portfolio/export`

### Phase 5: Frontend Visualization (4 hours)
- [ ] Add "Performance" tab to Portfolio page
- [ ] Create portfolio value chart (Recharts)
- [ ] Create metrics summary cards
- [ ] Create sector exposure area chart
- [ ] Create drawdown chart
- [ ] Add time period selector
- [ ] Add export button

### Phase 6: Testing & Documentation (2 hours)
- [ ] Write integration tests for backtest flow
- [ ] Write integration tests for snapshot flow
- [ ] Test charts with real 90-day data
- [ ] Document backtest interpretation
- [ ] Document performance metrics

**Total estimated effort**: ~20 hours

---

## Related PRDs

- **PRD #0010** (Quick Wins) - Required prerequisite
- **PRD #0009** (Initial MVP) - Extends portfolio analytics

---

**End of PRD #0011**
