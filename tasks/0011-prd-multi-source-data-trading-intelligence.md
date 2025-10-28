# PRD #0011: Multi-Source Data Infrastructure & Trading Intelligence System

**Status**: Draft
**Created**: 2025-01-28
**Priority**: P0 - Critical
**Complexity**: HIGH
**Estimated Effort**: 3-4 weeks

---

## 1. Introduction/Overview

This PRD defines a comprehensive data infrastructure system that maximizes success in picking profitable trades by implementing battle-tested multi-source architecture from market-sim. This completes the deferred multi-source price data implementation from PRD #0010 (Task 7.0) and adds critical enhancements for technical analysis, risk management, performance tracking, and cost optimization through local AI models.

**Problem Statement**: Portfolio-AI currently relies solely on yfinance for price data (single point of failure), lacks technical indicators for trade validation, has no automated performance tracking for agent ideas, and has no risk management tools for professional-grade portfolio management. Additionally, API costs for AI models can be reduced by using local models for validation before enabling expensive API calls.

**Solution**: Implement a comprehensive trading intelligence system with:
- Multi-source data failover (9 sources with automatic fallback)
- Technical indicators library for trade validation
- Automated paper trading for idea performance tracking
- Professional risk management suite
- Local AI models (QWEN) for cost optimization and sentiment analysis
- MCP server for efficient data access from Claude/ChatGPT Desktop

---

## 2. Goals

1. **Eliminate single point of failure**: Achieve 99.9% data availability through multi-source failover
2. **Enable technical validation**: Provide RSI, MACD, Bollinger Bands, etc. for validating agent trading ideas
3. **Track idea performance**: Implement automated paper trading to measure agent idea success rates and returns
4. **Professional risk management**: Provide position sizing, stop-loss suggestions, correlation analysis, and risk-adjusted metrics
5. **Reduce API costs**: Use local QWEN model for validation, tool use, and sentiment analysis before enabling expensive API models
6. **Optimize data access**: Provide MCP server for flat-cost data access from Claude/ChatGPT Desktop
7. **Maintain performance**: Keep test suite <5 seconds, daily updates <30 seconds, historical backfill <5 minutes

---

## 3. User Stories

### Data Engineer
- As a data engineer, I want automatic failover across 9 data sources so that price data is always available even if yfinance is blocked
- As a data engineer, I want to track source performance metrics (success rate, latency) so I can optimize the failover chain
- As a data engineer, I want 252 trading days of historical data so I can calculate meaningful technical indicators

### Trader
- As a trader, I want RSI, MACD, and Bollinger Bands calculated automatically so I can validate AI agent trading ideas
- As a trader, I want automated paper trading tracking so I know which agent strategies actually work
- As a trader, I want position sizing recommendations (Kelly Criterion) so I can optimize risk/reward
- As a trader, I want stop-loss suggestions based on ATR so I can protect against downside risk
- As a trader, I want to see portfolio correlation so I can identify concentration risk

### AI Agent Developer
- As an AI agent developer, I want sentiment scores for news articles so agents can factor in market sentiment
- As an AI agent developer, I want idea performance feedback so agents can learn from past successes/failures
- As an AI agent developer, I want to use local QWEN model first so I can validate agent logic without API costs

### System Administrator
- As a system administrator, I want MCP server support so Claude/ChatGPT Desktop can access portfolio data efficiently
- As a system administrator, I want fast tests (<5s) so I can iterate quickly on new features

---

## 4. Functional Requirements

### Feature 1: Multi-Source Price Data Infrastructure (Complete PRD #0010 Task 7.0)

**FR-1.1**: Port market-sim source infrastructure files to portfolio-ai:
- `rest_api_source.py` (~740 lines) - Dynamic REST endpoint execution from YAML configs
- `polygon_source.py` (~150 lines) - Polygon API integration with rate limiting
- `polygon_client.py` (~100 lines) - Polygon API client with 5/min rate limit tracking
- `multi_source_fetcher.py` (~587 lines) - Priority-based failover with 60s cooldown management
- `jsonpath_mapper.py` (~100 lines) - YAML-driven field mapping from API responses to DB schema

**FR-1.2**: Adapt imports for portfolio-ai structure:
- Remove `perf_profiler` dependency (use time.time() for duration tracking)
- Remove `job_queue` dependency (use Celery directly)
- Use portfolio-ai's `logging_config.get_logger()` for structured logging
- Use portfolio-ai's `DuckDBStorage` class for database operations

**FR-1.3**: Update `backend/app/portfolio/price_fetcher.py` to use `MultiSourceFetcher`:
- Replace direct `yf.Ticker()` calls with `MultiSourceFetcher.fetch_reference_data()`
- Keep existing 15-minute cache logic
- Keep existing error caching (5-minute TTL)
- Add source lineage tracking (record which source provided each data point)

**FR-1.4**: Implement priority-based failover chain:
- Priority 1: yfinance (unlimited, 10yr history, FREE)
- Priority 2: Twelve Data (800/day rate limit)
- Priority 3: FMP (250/day rate limit)
- Priority 10: Polygon (5/min rate limit)
- Priority 10: Finnhub (60/min rate limit)
- Priority 25: NewsAPI (100/day)
- Priority 28: Google News RSS (2s delay)
- Priority 30: Alpha Vantage (25/day, 500/day)
- Priority 5: FRED (120/min, economic indicators only)

**FR-1.5**: Implement 60-second rate limit cooldown:
- On HTTP 429 response, skip source for 60 seconds
- Automatically try next priority source
- Log cooldown events with structured logging

**FR-1.6**: Track source performance metrics:
- Success rate per source (successful fetches / total attempts)
- Average latency per source (milliseconds)
- Rate limit hit count per source
- Last successful fetch timestamp per source
- Store in `source_performance` table

**FR-1.7**: Write comprehensive tests:
- Test yfinance primary success path
- Test Polygon failover when yfinance returns 429
- Test Polygon failover when yfinance times out
- Test all sources fail scenario (return last known data with stale indicator)
- Test rate limit cooldown (verify source skipped for 60s after 429)
- Test source performance tracking (verify metrics recorded correctly)

**FR-1.8**: Update health check endpoint (`GET /api/health`):
- Check availability for all 9 data sources
- Report last successful fetch timestamp per source
- Report source status: "ok" (recently successful), "degraded" (old data), "down" (failing)
- Report rate limit status per source (current cooldown if any)
- Display failover chain effectiveness (% of requests handled by each source)

### Feature 2: Historical Data & Trading Signals

**FR-2.1**: Create YFinance adapter (`backend/app/sources/yfinance_source.py`):
- Wrap yfinance Python library
- Implement `fetch_day_bars()` method (252-day lookback)
- Implement `fetch_reference_payload()` method (company metadata)
- Handle yfinance quirks (0.5-2s delays between requests)
- Return Polars DataFrame with portfolio-ai schema

**FR-2.2**: Create Twelve Data adapter (`backend/app/sources/twelvedata_source.py`):
- REST API implementation using requests library
- Implement `fetch_day_bars()` method
- Implement `fetch_reference_payload()` method
- Track 800/day rate limit (8/min sub-limit)
- Return Polars DataFrame with portfolio-ai schema

**FR-2.3**: Implement historical backfill pipeline:
- Celery task: `ingest_historical_ohlcv(tickers: list[str], days: int = 252)`
- Use MultiSourceFetcher for failover
- Store in `day_bars` table with source lineage
- Log progress: "Backfilled 252 days for 10 tickers in 2m 15s"

**FR-2.4**: Implement intraday data pipeline:
- Celery task: `ingest_intraday_bars(tickers: list[str], date: str)`
- Fetch Polygon minute_bars (includes pre-calculated VWAP)
- Store in `minute_bars` table
- Schedule: Optional (user can enable for day trading features)

**FR-2.5**: Implement reference data pipeline:
- Celery task: `ingest_reference_data(tickers: list[str])`
- Fetch Finnhub company profiles (sector, industry, market cap)
- Store in `reference_cache` table
- Schedule: Weekly (sector classification changes slowly)

**FR-2.6**: Create RVOL calculator (`backend/app/analytics/volume.py`):
- Function: `calculate_rvol(ticker: str, date: str, lookback_days: int = 20) -> float`
- Formula: `current_volume / avg(volume, lookback_days)`
- SQL query from `day_bars` table
- Return: RVOL value (2.0 = 2x normal volume)

**FR-2.7**: Create sector rotation analyzer (`backend/app/analytics/sectors.py`):
- Function: `get_sector_rotation(date: str, lookback_days: int = 20) -> pl.DataFrame`
- Aggregate `day_bars` returns by sector (from `reference_cache`)
- Calculate 5-day, 20-day, 60-day sector momentum
- Return: DataFrame with sectors ranked by momentum

**FR-2.8**: Create peer comparison engine (`backend/app/analytics/peers.py`):
- Function: `get_peer_comparison(ticker: str, date: str) -> pl.DataFrame`
- Group tickers by sector/industry (from `reference_cache`)
- Calculate relative performance: `(ticker_return - sector_avg_return)`
- Return: DataFrame showing ticker's rank within peer group

**FR-2.9**: Expose analytics via API:
- `GET /api/analytics/rvol/{ticker}` - Current RVOL
- `GET /api/analytics/rvol/{ticker}?date=2025-01-15` - Historical RVOL
- `GET /api/analytics/sectors/rotation` - Current sector momentum
- `GET /api/analytics/peers/{ticker}` - Peer comparison

### Feature 3: Technical Indicators Library

**FR-3.1**: Add `pandas_ta>=0.3.14b` to `backend/requirements.txt`

**FR-3.2**: Create indicator calculation wrapper (`backend/app/analytics/indicators.py`):
- Function: `calculate_indicators(ticker: str, indicators: list[str]) -> dict`
- Supported indicators:
  - RSI (14-period): Relative Strength Index (0-100, <30 oversold, >70 overbought)
  - MACD (12/26/9): Moving Average Convergence Divergence (trend indicator)
  - BB (20, 2σ): Bollinger Bands (volatility bands)
  - SMA (20/50/200): Simple Moving Averages (trend confirmation)
  - EMA (20/50/200): Exponential Moving Averages (trend with recent emphasis)
  - ATR (14): Average True Range (volatility measure for stop-losses)
  - Stochastic (14/3/3): Stochastic Oscillator (overbought/oversold)
- Fetch OHLCV from `day_bars` table
- Calculate indicators using pandas_ta
- Return: Dict with indicator values and interpretations

**FR-3.3**: Create `technical_indicators` table in DuckDB schema:
```sql
CREATE TABLE technical_indicators (
    ticker           TEXT NOT NULL,
    date             DATE NOT NULL,
    rsi_14           DOUBLE,
    macd             DOUBLE,
    macd_signal      DOUBLE,
    macd_histogram   DOUBLE,
    bb_upper         DOUBLE,
    bb_middle        DOUBLE,
    bb_lower         DOUBLE,
    sma_20           DOUBLE,
    sma_50           DOUBLE,
    sma_200          DOUBLE,
    ema_20           DOUBLE,
    ema_50           DOUBLE,
    ema_200          DOUBLE,
    atr_14           DOUBLE,
    stoch_k          DOUBLE,
    stoch_d          DOUBLE,
    calculated_at    TIMESTAMP NOT NULL,
    PRIMARY KEY (ticker, date)
)
```

**FR-3.4**: Cache calculated indicators:
- Celery task: `update_technical_indicators(tickers: list[str])`
- Calculate indicators for each ticker using latest 200 days of OHLCV
- Store in `technical_indicators` table
- Schedule: Daily at market close + 30 minutes

**FR-3.5**: Expose indicators via API:
- `GET /api/symbols/{ticker}/indicators` - All indicators for latest date
- `GET /api/symbols/{ticker}/indicators?date=2025-01-15` - Historical indicators
- `GET /api/symbols/{ticker}/indicators?indicators=rsi,macd` - Specific indicators only
- Response format:
```json
{
  "ticker": "AAPL",
  "date": "2025-01-28",
  "indicators": {
    "rsi_14": 32.5,
    "rsi_interpretation": "oversold",
    "macd": 1.23,
    "macd_signal": 0.95,
    "macd_histogram": 0.28,
    "macd_interpretation": "bullish_cross",
    "bb_upper": 185.50,
    "bb_middle": 180.00,
    "bb_lower": 174.50,
    "price": 182.00,
    "bb_interpretation": "near_lower_band"
  }
}
```

**FR-3.6**: Integrate with AI agent prompts:
- Extend `get_price_data` tool to include indicators
- Agent prompt example: "AAPL current price $182, RSI=32 (oversold), MACD bullish cross, near lower Bollinger Band - potential buy signal"

### Feature 4: Idea Performance Tracking (Automated Paper Trading)

**FR-4.1**: Create `idea_outcomes` table:
```sql
CREATE TABLE idea_outcomes (
    idea_id              TEXT NOT NULL PRIMARY KEY,
    agent_run_id         TEXT NOT NULL,
    ticker               TEXT NOT NULL,
    idea_type            TEXT NOT NULL,  -- 'buy', 'sell', 'hold'
    entry_price          DOUBLE,
    entry_date           DATE,
    target_price         DOUBLE,
    stop_loss_price      DOUBLE,
    current_price        DOUBLE,
    current_return_pct   DOUBLE,
    status               TEXT NOT NULL,  -- 'open', 'target_hit', 'stop_hit', 'expired'
    exit_price           DOUBLE,
    exit_date            DATE,
    exit_reason          TEXT,  -- 'target', 'stop', 'time_limit', 'manual'
    realized_return_pct  DOUBLE,
    holding_days         INTEGER,
    max_favorable_pct    DOUBLE,  -- Best unrealized return
    max_adverse_pct      DOUBLE,  -- Worst unrealized return
    created_at           TIMESTAMP NOT NULL,
    updated_at           TIMESTAMP NOT NULL,
    FOREIGN KEY (idea_id) REFERENCES agent_ideas(id)
)
```

**FR-4.2**: Create paper trading tracker (`backend/app/analytics/paper_trading.py`):
- Function: `create_paper_trade(idea_id: str) -> None`
  - Extract ticker, idea_type, target_price from agent_ideas table
  - Fetch current price from price_fetcher
  - Calculate stop_loss_price using ATR (2x ATR below entry)
  - Insert into idea_outcomes table with status='open'
- Function: `update_paper_trades() -> None`
  - Fetch all open paper trades
  - Get current prices for all tickers
  - Update current_price, current_return_pct
  - Track max_favorable_pct and max_adverse_pct
  - Check if target_price or stop_loss_price hit
  - Update status to 'target_hit' or 'stop_hit' if triggered
  - Calculate realized_return_pct when closed

**FR-4.3**: Automatically create paper trades:
- When Discovery Agent creates new idea, call `create_paper_trade(idea_id)`
- When Portfolio Analyzer creates new idea, call `create_paper_trade(idea_id)`
- Paper trade entry price = current market price at idea creation time

**FR-4.4**: Schedule daily paper trade updates:
- Celery periodic task: `update_paper_trades()` at 4:30 PM ET daily
- Update all open paper trades with current prices
- Close trades if target/stop hit or 60 days elapsed (configurable)

**FR-4.5**: Calculate agent performance metrics (`backend/app/analytics/agent_performance.py`):
- Function: `get_agent_performance(agent_type: str, days: int = 90) -> dict`
- Metrics:
  - Win rate: % of closed trades with realized_return_pct > 0
  - Average return: Mean realized_return_pct of all closed trades
  - Average winner: Mean return of winning trades
  - Average loser: Mean return of losing trades
  - Win/loss ratio: avg_winner / abs(avg_loser)
  - Total ideas: Count of all ideas
  - Open ideas: Count of open trades
  - Closed ideas: Count of closed trades
  - Best trade: Highest realized_return_pct
  - Worst trade: Lowest realized_return_pct
- Return: Dict with all metrics

**FR-4.6**: Expose performance API:
- `GET /api/agents/{agent_type}/performance` - Performance metrics
- `GET /api/agents/{agent_type}/performance?days=30` - Last 30 days only
- Response format:
```json
{
  "agent_type": "DiscoveryAgent",
  "period_days": 90,
  "metrics": {
    "win_rate": 0.68,
    "average_return": 5.2,
    "average_winner": 12.3,
    "average_loser": -4.1,
    "win_loss_ratio": 3.0,
    "total_ideas": 25,
    "open_ideas": 5,
    "closed_ideas": 20,
    "best_trade": {"ticker": "NVDA", "return": 28.5},
    "worst_trade": {"ticker": "TSLA", "return": -8.2}
  }
}
```

**FR-4.7**: Dashboard widget for agent performance:
- Display: "Agent Performance: 68% win rate, avg +5.2% return, 20 ideas tracked"
- Link to detailed performance breakdown
- Chart showing cumulative returns over time

**FR-4.8**: Feed performance back to agent prompts:
- Include in system prompt: "Your last 10 ideas: 7 wins (avg +12.3%), 3 losses (avg -4.1%)"
- Include context on best/worst trades: "Your best trade was NVDA +28.5%, worst was TSLA -8.2%"
- Encourage learning: "Focus on patterns from your winning trades"

### Feature 5: Risk Management Suite

**FR-5.1**: Create position sizing calculator (`backend/app/analytics/risk_management.py`):
- Function: `calculate_position_size(ticker: str, strategy: str, risk_pct: float = 2.0) -> dict`
- Strategies:
  - `kelly`: Kelly Criterion (win_rate * (avg_winner / avg_loser) - (1 - win_rate)) / (avg_winner / avg_loser)
  - `fixed_pct`: Fixed % of portfolio (e.g., 5%)
  - `volatility_adjusted`: Position size inversely proportional to ATR (higher volatility = smaller position)
- Inputs: Portfolio value, ticker, risk_pct (max % of portfolio to risk)
- Output: Dict with recommended position size (shares, dollars, % of portfolio)

**FR-5.2**: Create stop-loss suggestion engine:
- Function: `suggest_stop_loss(ticker: str, entry_price: float, method: str = 'atr') -> dict`
- Methods:
  - `atr`: Entry price - (2 × ATR) [most common]
  - `percent`: Entry price × (1 - stop_loss_pct) [fixed %]
  - `support`: Nearest technical support level (from day_bars low prices)
- Output: Dict with stop price, stop distance ($), stop distance (%), risk/reward ratio

**FR-5.3**: Create portfolio correlation matrix calculator:
- Function: `calculate_correlation_matrix(tickers: list[str], days: int = 30) -> pl.DataFrame`
- Calculate pairwise correlation of daily returns (rolling 30-day window)
- Identify high correlation pairs (>0.8) as concentration risk
- Return: DataFrame with correlation matrix

**FR-5.4**: Create max drawdown tracker:
- Function: `calculate_max_drawdown(portfolio_value_history: pl.DataFrame) -> dict`
- Track peak portfolio value
- Calculate drawdown: (current_value - peak_value) / peak_value
- Track max drawdown: Largest peak-to-trough decline
- Return: Dict with current_drawdown_pct, max_drawdown_pct, peak_date, trough_date

**FR-5.5**: Calculate risk-adjusted metrics:
- Function: `calculate_risk_metrics(returns: pl.DataFrame) -> dict`
- Metrics:
  - Sharpe ratio: (mean_return - risk_free_rate) / std_dev_return
  - Sortino ratio: (mean_return - risk_free_rate) / downside_deviation
  - Calmar ratio: mean_annual_return / max_drawdown
- Assume risk_free_rate = 4.5% (current 10-year Treasury yield from FRED)
- Return: Dict with all ratios

**FR-5.6**: Create risk dashboard API:
- `GET /api/risk/position-size?ticker=AAPL&strategy=kelly` - Position sizing recommendation
- `GET /api/risk/stop-loss?ticker=AAPL&entry_price=180&method=atr` - Stop-loss suggestion
- `GET /api/risk/correlation` - Portfolio correlation matrix
- `GET /api/risk/drawdown` - Current and max drawdown
- `GET /api/risk/metrics` - Risk-adjusted performance metrics (Sharpe, Sortino, Calmar)

**FR-5.7**: Risk alerts:
- Alert if any position exceeds 30% of portfolio (concentration risk)
- Alert if correlation between any 2 positions exceeds 0.8 (diversification risk)
- Alert if current drawdown exceeds 15% (significant loss)
- Alert if Sharpe ratio falls below 1.0 (underperforming risk-free rate on risk-adjusted basis)

**FR-5.8**: Risk dashboard widget:
- Display: "Max Drawdown: -8.2%, Sharpe Ratio: 1.8, Highest Correlation: AAPL/MSFT (0.72)"
- Visual: Correlation heatmap, drawdown chart over time

### Feature 6: News Sentiment Scoring & Local AI Cost Optimization

**FR-6.1**: Add local AI model dependencies:
- Add `transformers>=4.30.0` to requirements.txt (HuggingFace)
- Add `torch>=2.0.0` (PyTorch for model inference)
- Add `qwen-agent>=0.0.3` (QWEN local model for tool use) [OPTIONAL - evaluate if needed]

**FR-6.2**: Create local model manager (`backend/app/ai/local_models.py`):
- Function: `load_finbert_model() -> tuple[model, tokenizer]`
  - Download ProsusAI/finbert sentiment model (122MB)
  - Load into memory on first use
  - Cache for subsequent calls
- Function: `load_qwen_model() -> model` [OPTIONAL]
  - Download QWEN model for tool use (if using local QWEN)
  - Evaluate QWEN performance vs OpenAI/Anthropic APIs
  - Document cost/performance tradeoffs

**FR-6.3**: Create sentiment scoring service (`backend/app/ai/sentiment.py`):
- Function: `score_sentiment(text: str, model: str = 'finbert') -> float`
  - Input: News article text (title + summary)
  - Models:
    - `finbert`: Use FinBERT model (-1 to +1 scale)
    - `qwen`: Use QWEN for sentiment (if implemented)
  - Output: Sentiment score (-1 = bearish, 0 = neutral, +1 = bullish)
  - Inference time: ~200ms per article on CPU, ~20ms on GPU

**FR-6.4**: Score news articles on fetch:
- Update `GoogleNewsSource.fetch_news()` to score sentiment
- Add `sentiment_score` column to `news_cache` table
- Store: ticker, title, summary, sentiment_score, scored_at

**FR-6.5**: Calculate sentiment aggregates:
- Function: `get_sentiment_aggregates(ticker: str, days: int) -> dict`
  - 1-day average sentiment (last 24 hours of news)
  - 5-day average sentiment
  - 20-day average sentiment
  - Sentiment trend: Is sentiment improving or declining?
  - Sentiment inflection: Has sentiment changed >2 std dev recently?

**FR-6.6**: Expose sentiment API:
- `GET /api/sentiment/{ticker}` - Current sentiment aggregates
- `GET /api/sentiment/{ticker}/history` - Historical sentiment over time
- `GET /api/sentiment/{ticker}/inflections` - Recent sentiment inflections (>2σ)

**FR-6.7**: Integrate with AI agent prompts:
- Include in agent context: "Recent news sentiment for AAPL: +0.65 (bullish), trending up from +0.32 last week"
- Alert on inflections: "Sentiment inflection detected: TSLA sentiment dropped from +0.5 to -0.3 (>2σ shift)"

**FR-6.8**: Cost optimization strategy (CRITICAL):
- **Phase 1 - Local Validation**: Use local QWEN model for ALL agent tool use and idea generation
  - Validate that agent logic works correctly
  - Generate ideas using local model
  - Track local model performance (quality, latency)
  - Cost: $0 (local inference only)
- **Phase 2 - API Model Enablement**: After validating locally, enable API models as option
  - User can choose: local model (free, slower) or API model (paid, faster)
  - Default: local model
  - Track API costs in database
  - Alert when approaching API budget limits
- Record decision in `ARCHITECTURE.md` and `DEVELOPMENT.md`

### Feature 7: Protocol-Based Storage Mocking (Test Performance)

**FR-7.1**: Create `StorageProtocol` interface (`backend/app/storage/protocols.py`):
```python
from typing import Protocol
import polars as pl

class StorageProtocol(Protocol):
    def query(self, sql: str, params: list | None = None) -> pl.DataFrame: ...
    def insert_dict(self, table: str, data: dict) -> None: ...
    def insert_dataframe(self, table: str, df: pl.DataFrame, mode: str = "append") -> None: ...
    def connection(self) -> ContextManager: ...
```

**FR-7.2**: Create `InMemoryStorage` mock (`tests/mocks/in_memory_storage.py`):
- Implement `StorageProtocol` using Python dicts
- Support core CRUD operations (INSERT, SELECT, UPDATE, DELETE)
- Support simple WHERE clauses (equality only)
- No need for JOIN, GROUP BY, or complex queries (use real DB for integration tests)
- ~100-200 lines of code

**FR-7.3**: Update test fixtures (`tests/conftest.py`):
```python
@pytest.fixture
def fast_storage() -> InMemoryStorage:
    """Fast in-memory storage for unit tests."""
    return InMemoryStorage()

@pytest.fixture
def real_storage() -> DuckDBStorage:
    """Real DuckDB storage for integration tests."""
    return DuckDBStorage(":memory:")
```

**FR-7.4**: Update existing tests:
- Unit tests: Use `fast_storage` fixture (20x faster)
- Integration tests: Use `real_storage` fixture (real SQL)
- Mark integration tests with `@pytest.mark.integration`

**FR-7.5**: Test performance target:
- Unit tests: <2 seconds (using InMemoryStorage)
- Integration tests: <3 seconds (using DuckDB :memory:)
- Total: <5 seconds for full test suite

### Feature 8: MCP Server for Claude/ChatGPT Desktop Data Access

**FR-8.1**: Create MCP server (`backend/app/mcp_server.py`):
- Implement Model Context Protocol server specification
- Expose portfolio data (positions, analytics, ideas) via MCP
- Expose market data (prices, indicators, news) via MCP
- Enable Claude Desktop and ChatGPT Desktop to query data via MCP instead of API calls

**FR-8.2**: MCP vs API dual access pattern:
- Function: `get_portfolio_data(source: str = 'auto') -> dict`
  - `source='mcp'`: Use MCP protocol (flat cost, desktop apps)
  - `source='api'`: Use HTTP API (metered cost)
  - `source='auto'`: Auto-detect most efficient method
- Both access methods return identical data
- MCP optimizes for flat-cost desktop AI app usage
- API optimizes for programmatic/web access

**FR-8.3**: MCP server endpoints:
- `mcp://portfolio-ai/portfolio/summary` - Portfolio summary
- `mcp://portfolio-ai/portfolio/positions` - All positions
- `mcp://portfolio-ai/ideas/recent` - Recent AI agent ideas
- `mcp://portfolio-ai/market/prices/{ticker}` - Current prices
- `mcp://portfolio-ai/market/indicators/{ticker}` - Technical indicators
- `mcp://portfolio-ai/market/news/{ticker}` - Recent news with sentiment

**FR-8.4**: Configuration for Claude/ChatGPT Desktop:
- Document MCP server setup in `CLAUDE.md` and `docs/core/SETUP.md`
- Provide MCP config file for Claude Desktop (`~/.claude/mcp_servers.json`)
- Provide MCP config file for ChatGPT Desktop (if applicable)

**FR-8.5**: Performance comparison:
- Measure latency: MCP vs HTTP API
- Measure cost: MCP (flat) vs API (per-request)
- Document when to use each method

---

## 5. Non-Goals (Out of Scope)

**NG-1**: Options Greeks/IV calculation (Phase 3 - defer until user trades options frequently)

**NG-2**: Insider trading data from SEC EDGAR (Phase 3 - niche use case, complex XML parsing)

**NG-3**: Earnings calendar integration (Phase 2 - nice to have but not critical for MVP)

**NG-4**: Reinforcement learning models for trade selection (Future - research project)

**NG-5**: Real-time streaming data (intraday second-by-second) (Future - day trading only)

**NG-6**: Multi-user support with user-specific portfolios (Future - MVP is single-user)

**NG-7**: Mobile app (Future - web dashboard first)

**NG-8**: Automated trade execution (Future - paper trading only for MVP)

---

## 6. Design Considerations

### Database Schema Updates

**New Tables**:
1. `day_bars` - Daily OHLCV data (ticker, date, open, high, low, close, volume, vwap, source, ingest_run_id)
2. `minute_bars` - Intraday minute-level data (ticker, ts_utc, ohlcv, vwap, source)
3. `technical_indicators` - Cached indicator values (ticker, date, rsi, macd, bb, sma, ema, atr, stoch)
4. `idea_outcomes` - Paper trading results (idea_id, entry_price, exit_price, realized_return_pct, status)
5. `source_performance` - Source metrics (source_name, success_rate, avg_latency_ms, rate_limit_hits, last_success_at)

**Schema Migrations**:
- Use existing migration system from PRD #0010 Feature 5
- Create migrations: `002_add_ohlcv_tables.sql`, `003_add_indicators_table.sql`, `004_add_idea_outcomes.sql`

### API Design

**RESTful Endpoints**:
- `GET /api/analytics/rvol/{ticker}` - RVOL calculation
- `GET /api/analytics/sectors/rotation` - Sector momentum
- `GET /api/analytics/peers/{ticker}` - Peer comparison
- `GET /api/symbols/{ticker}/indicators` - Technical indicators
- `GET /api/agents/{agent_type}/performance` - Agent performance metrics
- `GET /api/risk/position-size` - Position sizing recommendation
- `GET /api/risk/stop-loss` - Stop-loss suggestion
- `GET /api/risk/correlation` - Correlation matrix
- `GET /api/risk/drawdown` - Drawdown metrics
- `GET /api/risk/metrics` - Risk-adjusted metrics
- `GET /api/sentiment/{ticker}` - Sentiment aggregates

**Response Format** (consistent across all endpoints):
```json
{
  "status": "success",
  "data": { ... },
  "metadata": {
    "timestamp": "2025-01-28T16:30:00Z",
    "source": "yfinance",
    "cached": false
  }
}
```

### Frontend Components

**New Dashboard Widgets**:
1. Agent Performance Card - Win rate, avg return, total ideas
2. Risk Dashboard - Drawdown, Sharpe ratio, correlation heatmap
3. Technical Indicators Panel - RSI, MACD, BB charts
4. Sector Rotation Heatmap - Top/bottom sectors by momentum
5. Paper Trading Results Table - Idea performance tracking

---

## 7. Technical Considerations

### Architecture Decisions

**1. Multi-Source Failover Pattern** (from market-sim):
- Never call data source APIs directly
- Always use `MultiSourceFetcher` with priority-based chain
- Automatic 60-second cooldown on rate limit (429) errors
- Log all failover events for observability

**2. Database-Driven Configuration**:
- YAML files seed initial config
- DuckDB stores runtime state (source priorities, credentials, rate limits)
- No code changes to add/remove sources

**3. Source Lineage Tracking**:
- Every data point records which source provided it
- Enables data quality analysis per source
- Helps debug issues ("Polygon had bad VWAP on 2025-03-15")

**4. Protocol-Based Storage Abstraction**:
- `StorageProtocol` interface for dependency injection
- `InMemoryStorage` mock for fast unit tests (20x speedup)
- `DuckDBStorage` real implementation for integration tests

**5. Local AI Model First**:
- Use local QWEN model to validate agent logic
- Zero API costs during development/testing
- Enable API models (OpenAI/Anthropic) as optional upgrade
- Record costs in database, alert on budget limits

### Data Retention Policy

**Forever retention with optional cleanup** (10-ticker portfolio = minimal disk space):
- `day_bars`: Keep all (252 days × 10 tickers × 365 days = ~1MB per year)
- `minute_bars`: Keep 30 days (optional intraday data, ~100MB for 10 tickers)
- `news_cache`: Keep 90 days (~10MB for 10 tickers)
- `technical_indicators`: Keep all (lightweight, ~500KB per year)
- `idea_outcomes`: Keep all (critical for learning, ~1MB per year)

Provide manual cleanup tools: `python -m app.scripts.cleanup_old_data --table=minute_bars --days=30`

### Error Handling Strategy

**Retry with exponential backoff, then fail gracefully**:
- On transient errors (timeout, 503): Retry 3 times with exponential backoff (1s, 2s, 4s)
- On rate limits (429): Skip source for 60 seconds, try next priority source
- On permanent errors (404, 401): Don't retry, log error, try next source
- If all sources fail: Return last known good data with staleness indicator
- Example response:
```json
{
  "status": "degraded",
  "data": { "price": 180.0, "timestamp": "2025-01-27T16:00:00Z" },
  "warning": "Using stale data (24 hours old). All sources failed.",
  "stale_hours": 24
}
```

### Performance Targets

- **Test suite**: <5 seconds (unit + integration)
- **Daily data updates**: <30 seconds (10 tickers, yfinance)
- **Historical backfill**: <5 minutes (252 days, 10 tickers)
- **Indicator calculation**: <10 seconds (10 tickers, all indicators)
- **API latency**: <200ms (p95), <500ms (p99)
- **Paper trade updates**: <5 seconds (check all open trades)

### Dependencies

**Python Packages** (add to `backend/requirements.txt`):
```
pandas_ta>=0.3.14b         # Technical indicators
transformers>=4.30.0       # HuggingFace models (FinBERT)
torch>=2.0.0              # PyTorch (for model inference)
sentencepiece>=0.1.99     # Tokenizer for FinBERT
```

**Optional**:
```
qwen-agent>=0.0.3         # QWEN local model (evaluate if needed)
```

### Security

**API Keys** (already in `backend/.env` from PRD #0010 Task 7.1):
- POLYGON_API_KEY
- FINNHUB_API_KEY
- TWELVEDATA_API_KEY
- FMP_API_KEY
- NEWSAPI_API_KEY
- ALPHAVANTAGE_API_KEY
- FRED_API_KEY

**Model Storage**:
- FinBERT model cached in `~/.cache/huggingface/` (122MB)
- QWEN model cached in `~/.cache/qwen/` if used (~2-4GB)

---

## 8. Success Metrics

### Data Reliability
- **99.9% uptime**: Data available 99.9% of the time (failover works)
- **<1% fetch failures**: Less than 1% of data fetches fail after all sources tried
- **Zero stale data**: No data >24 hours old during market hours

### Performance
- **<30s daily updates**: Daily price/indicator updates complete in <30 seconds
- **<5min backfill**: Historical data backfill (252 days) completes in <5 minutes
- **<5s test suite**: Full test suite runs in <5 seconds

### Trading Intelligence
- **Agent win rate >60%**: Paper trading shows >60% of agent ideas are winners
- **Avg return >5%**: Average realized return per closed idea >5%
- **Sharpe ratio >1.5**: Portfolio achieves Sharpe ratio >1.5 (good risk-adjusted performance)

### Cost Optimization
- **$0 local model costs**: QWEN local model validation costs $0
- **<$10/month API costs**: After enabling API models, costs stay below $10/month for 10-ticker portfolio
- **Track API spend**: Database records every API call cost

### User Experience
- **<200ms API latency**: 95th percentile API response time <200ms
- **Dashboard loads <2s**: All dashboard widgets load in <2 seconds
- **No manual data refresh**: Background jobs keep data current without user intervention

---

## 9. Open Questions

**Q1**: Should we implement QWEN local model integration now or defer until after validating with FinBERT only?

**Recommendation**: Start with FinBERT for sentiment only (proven model, simple integration). Defer QWEN for tool use until Phase 2 unless API costs become prohibitive during development.

**Q2**: For paper trading, should we auto-close trades after N days or keep them open indefinitely?

**Recommendation**: Auto-close after 60 days (configurable). Most swing trading ideas play out within 30-60 days. Keeping trades open indefinitely makes performance metrics harder to interpret.

**Q3**: Should MCP server run as separate process or embedded in FastAPI app?

**Recommendation**: Embedded in FastAPI app initially (simpler deployment). Can split to separate process later if MCP traffic is high.

**Q4**: For technical indicators, should we support custom indicator parameters (e.g., RSI-9 instead of RSI-14)?

**Recommendation**: MVP uses standard parameters only (RSI-14, MACD 12/26/9, etc.). Add custom parameters in Phase 2 if users request it.

**Q5**: Should we implement real-time paper trading tracking (check every minute) or daily updates only?

**Recommendation**: Daily updates at market close initially (simpler, sufficient for swing trading). Add intraday tracking in Phase 2 if users want day trading features.

---

## 10. Implementation Notes

### File Organization

```
backend/app/
├── sources/
│   ├── base.py                    (✅ exists - adapted from market-sim)
│   ├── rest_api_source.py         (NEW - port from market-sim)
│   ├── polygon_source.py          (NEW - port from market-sim)
│   ├── yfinance_source.py         (NEW - wrap yfinance library)
│   ├── twelvedata_source.py       (NEW - Twelve Data REST API)
│   └── multi_source_fetcher.py    (NEW - port from market-sim)
├── analytics/
│   ├── volume.py                  (NEW - RVOL calculator)
│   ├── sectors.py                 (NEW - sector rotation)
│   ├── peers.py                   (NEW - peer comparison)
│   ├── indicators.py              (NEW - technical indicators)
│   ├── paper_trading.py           (NEW - paper trade tracker)
│   ├── agent_performance.py       (NEW - agent metrics)
│   └── risk_management.py         (NEW - position sizing, stop-loss, correlation)
├── ai/
│   ├── local_models.py            (NEW - model loading)
│   └── sentiment.py               (NEW - sentiment scoring)
├── mcp_server.py                  (NEW - MCP protocol server)
├── storage/
│   └── protocols.py               (NEW - StorageProtocol interface)
└── api/
    ├── analytics.py               (NEW - analytics endpoints)
    ├── risk.py                    (NEW - risk endpoints)
    └── sentiment.py               (NEW - sentiment endpoints)

tests/
├── mocks/
│   └── in_memory_storage.py       (NEW - fast test mock)
├── test_multi_source.py           (NEW - failover tests)
├── test_indicators.py             (NEW - indicator tests)
├── test_paper_trading.py          (NEW - paper trading tests)
└── test_risk_management.py        (NEW - risk management tests)
```

### Testing Strategy

**Unit Tests** (use InMemoryStorage mock):
- Test indicator calculations with known OHLCV data
- Test RVOL calculation with controlled volume data
- Test position sizing formulas
- Test sentiment scoring with sample news text
- Target: <2 seconds runtime

**Integration Tests** (use real DuckDB :memory:):
- Test multi-source failover with mocked HTTP responses
- Test paper trading workflow (create → update → close)
- Test agent performance calculation with real DB queries
- Target: <3 seconds runtime

**Manual Testing Checklist**:
- [ ] Historical backfill: Run for 10 tickers, verify 252 days fetched from yfinance
- [ ] Multi-source failover: Block yfinance (mock 429), verify Polygon called
- [ ] Technical indicators: Verify RSI, MACD, BB calculated correctly for AAPL
- [ ] Paper trading: Create idea, verify outcome tracked, close trade manually
- [ ] Agent performance: Generate 10 ideas, close 5 as wins/losses, verify metrics correct
- [ ] Risk dashboard: Verify position sizing, stop-loss, correlation calculations
- [ ] Sentiment scoring: Fetch news for AAPL, verify sentiment scores reasonable
- [ ] MCP server: Connect from Claude Desktop, query portfolio data

---

## 11. Rollout Plan

### Phase 1: Core Infrastructure (Week 1)
- Port market-sim source infrastructure (Tasks 7.5.1-7.5.6)
- Update price_fetcher.py to use MultiSourceFetcher
- Write multi-source failover tests
- Update health check endpoint

**Success Criteria**: yfinance → Polygon failover works, tests pass

### Phase 2: Historical Data & Indicators (Week 2)
- Create YFinance and Twelve Data adapters
- Implement historical backfill pipeline
- Add technical indicators library
- Create indicators API endpoints

**Success Criteria**: 252 days of OHLCV + indicators available for 10-ticker portfolio

### Phase 3: Paper Trading & Performance (Week 2-3)
- Create idea_outcomes table and paper trading tracker
- Implement daily paper trade update job
- Calculate agent performance metrics
- Build performance dashboard

**Success Criteria**: Ideas automatically tracked, agent performance displayed

### Phase 4: Risk Management & Sentiment (Week 3)
- Implement position sizing and stop-loss calculators
- Create correlation matrix and drawdown tracking
- Add FinBERT sentiment scoring
- Build risk dashboard

**Success Criteria**: Risk metrics available, news sentiment scored

### Phase 5: Cost Optimization & MCP (Week 3-4)
- Implement protocol-based storage mocking
- Create MCP server for Claude/ChatGPT Desktop
- Document local AI model strategy
- Optimize test suite to <5 seconds

**Success Criteria**: Tests run fast, MCP server accessible from desktop apps

---

## 12. References

- **PRD #0010**: Quick Wins & Infrastructure Improvements (deferred Task 7.0)
- **market-sim codebase**: `/home/kasadis/market-sim/` (source architecture reference)
- **market-sim docs**: `~/market-sim/docs/archive/legacy-20251025/data_sources_strategy.md`
- **Source profiling**: `~/market-sim/docs/archive/legacy-20251025/source_profiling_complete_results.md`
- **ARCHITECTURE.md**: Portfolio-AI architecture principles
- **DEVELOPMENT.md**: Development workflows and standards

---

**END OF PRD**

**Next Step**: Run `/task_it tasks/0011-prd-multi-source-data-trading-intelligence.md` to generate detailed task list.
