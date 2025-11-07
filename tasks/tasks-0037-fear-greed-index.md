# Task List: Fear & Greed Index (5-Signal + Optional Breadth)

**PRD**: `tasks/prd-fear_and_greed.md` (simplified to 5 core signals)
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: MEDIUM (6-8 hours core, +2-3 hours if breadth included)
**Created**: 2025-11-07
**Updated**: 2025-11-07

---

## Summary

Implement a simplified Fear & Greed Index using 5 proven signals that capture market sentiment without institutional overkill. Start with breadth feasibility test - if easy, include it (6 signals); if complex, defer to optional Phase 7.

**Core 5 Signals (MUST HAVE)**:
1. **VIX** - Fear gauge (FRED `VIXCLS`) - *Already have*
2. **SPY Momentum** - Trend (price vs SMA_200) - *Already have*
3. **RSI** - Overextension (already calculating) - *Already have*
4. **Put/Call Ratio** - Options sentiment (Cboe free CSV) - *New*
5. **Credit Spreads** - Early warning (FRED `BAMLH0A0HYM2`) - *New*

**Optional 6th Signal (TEST FIRST)**:
6. **Market Breadth** - Rally health (% S&P 500 > 50-day MA) - *Complex*

**What You'll Know**:
- ✅ Fear level (VIX)
- ✅ Trend direction (Momentum)
- ✅ Overextension (RSI)
- ✅ Options sentiment (Put/Call)
- ✅ Institutional worry / early warning (Credit Spreads)
- ⚠️ Rally breadth (optional, if test passes)

---

## Relevant Files

### Create (11 files core, +2 if breadth)

**Backend - Database**:
- `backend/migrations/016_fear_greed_index.sql` (~120 lines) - 3 tables + indexes

**Backend - Core Logic**:
- `backend/app/market/fear_greed.py` (~200 lines) - Calculation engine, percentile ranking
- `backend/app/market/fear_greed_data.py` (~180 lines) - Data fetching (VIX, credit, put/call, RSI, momentum)
- `backend/app/market/fear_greed_service.py` (~150 lines) - Orchestration, caching, idempotent writes

**Backend - API**:
- `backend/app/api/market_fng.py` (~120 lines) - 3 REST endpoints
- `backend/app/models/fear_greed.py` (~80 lines) - Pydantic models

**Backend - Tasks**:
- `backend/app/tasks/fear_greed_tasks.py` (~100 lines) - Celery daily compute task

**Backend - Tests**:
- `backend/tests/market/test_fear_greed.py` (~150 lines) - Core logic tests
- `backend/tests/market/test_fear_greed_data.py` (~100 lines) - Data fetching tests
- `backend/tests/api/test_market_fng.py` (~80 lines) - API endpoint tests

**Frontend**:
- `frontend/components/market/FearGreedGauge.tsx` (~150 lines) - Gauge component with emoji/label
- `frontend/lib/hooks/useFearGreed.ts` (~60 lines) - TanStack Query hooks

**Optional (if breadth test passes)**:
- `backend/app/market/sp500_constituents.py` (~120 lines) - S&P 500 list management
- `backend/app/market/breadth_calculator.py` (~100 lines) - Breadth calculation logic

### Update (8 files)

**Backend**:
- `backend/app/celery_app.py` - Add fear_greed_tasks import + beat schedule
- `backend/app/api/__init__.py` - Register market_fng router
- `backend/app/sources/fred.py` - Add BAMLH0A0HYM2 (HY spread) to INDICATORS dict (if not present)

**Frontend**:
- `frontend/app/page.tsx` - Add FearGreedGauge after MarketConditions (line ~53)
- `frontend/lib/api/market.ts` - Add fetchFearGreed function
- `frontend/components/watchlist/WatchlistTable.tsx` - Optional: Add F&G chip to Symbol column

**Docs**:
- `docs/core/API_REFERENCE.md` - Document 3 new endpoints
- `docs/core/ARCHITECTURE.md` - Add Fear & Greed section

---

## Tasks

### Phase 0: Breadth Feasibility Test (30 min) - DECISION GATE

**Goal**: Test if 500-stock breadth calculation is fast enough to include in v1

- [ ] **0.1 Test S&P 500 constituent fetch** (10 min)
  - [ ] 0.1.1 Test FMP endpoint with existing API key
    ```bash
    curl -s "https://financialmodelingprep.com/api/v3/sp500_constituent?apikey=$FMP_API_KEY" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'✅ {len(data)} constituents' if isinstance(data, list) else f'❌ Error: {data}')"
    ```
  - [ ] 0.1.2 If FMP fails, test Wikipedia fallback
    ```python
    import pandas as pd
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    tables = pd.read_html(url)
    sp500 = tables[0]  # First table
    print(f"✅ {len(sp500)} constituents from Wikipedia")
    ```
  - [ ] 0.1.3 Document which source works and store sample data

- [ ] **0.2 Test breadth calculation performance** (15 min)
  - [ ] 0.2.1 Query existing data: How many S&P 500 tickers in `day_bars`?
    ```sql
    SELECT COUNT(DISTINCT ticker) FROM day_bars
    WHERE ticker IN (SELECT symbol FROM <sp500_list>);
    ```
  - [ ] 0.2.2 Test 50-day MA calculation speed for 100 stocks
    ```python
    # For 100 random tickers, calculate if price > 50-day MA
    # Time this operation
    import time
    start = time.time()
    # ... calculation ...
    elapsed = time.time() - start
    print(f"100 stocks: {elapsed:.2f}s")
    # Extrapolate: 500 stocks = ~{elapsed * 5}s
    ```
  - [ ] 0.2.3 Check if technical_indicators has sma_50 for S&P stocks
    ```sql
    SELECT COUNT(*) FROM technical_indicators
    WHERE sma_50 IS NOT NULL AND date = (SELECT MAX(date) FROM technical_indicators);
    ```

- [ ] **0.3 Make decision** (5 min)
  - [ ] 0.3.1 If breadth calculation < 5 seconds: ✅ INCLUDE in Phase 1-6
  - [ ] 0.3.2 If breadth calculation > 5 seconds: ⏸️ DEFER to Phase 7 (optional)
  - [ ] 0.3.3 Document decision and reasoning in task file
  - [ ] 0.3.4 Update signal count (5 or 6) in task summary

**Decision Criteria**:
- ✅ INCLUDE if: Constituent fetch works + calculation < 5s + data available
- ⏸️ DEFER if: Slow calculation OR missing data OR complex setup

---

### Phase 1: Database Schema (30 min)

**Goal**: Create 3 tables to store Fear & Greed data

- [ ] **1.1 Create migration file** (5 min)
  - [ ] 1.1.1 Create `backend/migrations/016_fear_greed_index.sql`
  - [ ] 1.1.2 Add header comment with description and date
  - [ ] 1.1.3 Add `BEGIN;` and `COMMIT;` wrapper

- [ ] **1.2 Create fear_greed_inputs table** (10 min)
  - [ ] 1.2.1 Define table schema:
    ```sql
    CREATE TABLE IF NOT EXISTS fear_greed_inputs (
      as_of_date DATE PRIMARY KEY,
      vix_close DOUBLE PRECISION,
      spy_close DOUBLE PRECISION,
      spy_sma_200 DOUBLE PRECISION,
      rsi_14 DOUBLE PRECISION,
      put_call_ratio DOUBLE PRECISION,
      hy_spread DOUBLE PRECISION,
      breadth_pct DOUBLE PRECISION,  -- Optional, NULL if not calculated
      source_map JSONB DEFAULT '{}'::jsonb,  -- Track data sources
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```
  - [ ] 1.2.2 Add comment explaining each field
  - [ ] 1.2.3 Add index: `CREATE INDEX idx_fng_inputs_date ON fear_greed_inputs(as_of_date DESC);`

- [ ] **1.3 Create fear_greed_components table** (10 min)
  - [ ] 1.3.1 Define table schema:
    ```sql
    CREATE TABLE IF NOT EXISTS fear_greed_components (
      as_of_date DATE PRIMARY KEY,
      vix_pct SMALLINT,           -- 0-100 percentile
      momentum_pct SMALLINT,      -- SPY vs SMA_200
      rsi_pct SMALLINT,           -- RSI overbought/oversold
      pcr_pct SMALLINT,           -- Put/call ratio
      credit_pct SMALLINT,        -- HY spread
      breadth_pct SMALLINT,       -- Optional, NULL if not calculated
      window_days INT DEFAULT 252,  -- Lookback for percentiles
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```
  - [ ] 1.3.2 Add comment explaining percentile methodology
  - [ ] 1.3.3 Add check constraints: `CHECK (vix_pct >= 0 AND vix_pct <= 100)` (repeat for all _pct fields)

- [ ] **1.4 Create fear_greed_daily table** (5 min)
  - [ ] 1.4.1 Define table schema:
    ```sql
    CREATE TABLE IF NOT EXISTS fear_greed_daily (
      as_of_date DATE PRIMARY KEY,
      score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 100),
      label TEXT NOT NULL CHECK (label IN ('Extreme Fear', 'Fear', 'Neutral', 'Greed', 'Extreme Greed')),
      previous_score DOUBLE PRECISION,  -- Yesterday's score for trend
      score_change DOUBLE PRECISION,    -- Daily change
      signal_count SMALLINT DEFAULT 5,  -- 5 or 6 depending on breadth
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
    ```
  - [ ] 1.4.2 Add index: `CREATE INDEX idx_fng_daily_date ON fear_greed_daily(as_of_date DESC);`
  - [ ] 1.4.3 Add comment explaining score ranges (0-25 Extreme Fear, 25-45 Fear, etc.)

- [ ] **1.5 Run migration** (5 min)
  - [ ] 1.5.1 Apply migration: `psql -U portfolio_ai_user -d portfolio_ai -f migrations/016_fear_greed_index.sql`
  - [ ] 1.5.2 Verify tables: `\dt fear_greed*`
  - [ ] 1.5.3 Verify indexes: `\di idx_fng*`
  - [ ] 1.5.4 Test insert/select on each table

---

### Phase 2: Data Fetching Module (1.5 hours)

**Goal**: Fetch all 5-6 signals from various sources

- [ ] **2.1 Create fear_greed_data.py skeleton** (5 min)
  - [ ] 2.1.1 Create `backend/app/market/fear_greed_data.py`
  - [ ] 2.1.2 Add imports: structlog, datetime, httpx, FREDSource, PortfolioStorage
  - [ ] 2.1.3 Add logger: `logger = get_logger(__name__)`
  - [ ] 2.1.4 Define `FearGreedDataFetcher` class with `__init__(storage, fred_source)`

- [ ] **2.2 Implement VIX fetching** (10 min)
  - [ ] 2.2.1 Add method `fetch_vix(date: date) -> float | None`
  - [ ] 2.2.2 Use FREDSource to fetch `VIXCLS` for given date
  - [ ] 2.2.3 Handle errors: log and return None on failure
  - [ ] 2.2.4 Add unit test: mock FRED response

- [ ] **2.3 Implement HY spread fetching** (10 min)
  - [ ] 2.3.1 Add `BAMLH0A0HYM2` to fred.py INDICATORS if not present
  - [ ] 2.3.2 Add method `fetch_hy_spread(date: date) -> float | None`
  - [ ] 2.3.3 Use FREDSource to fetch HY OAS series
  - [ ] 2.3.4 Add unit test: mock FRED response

- [ ] **2.4 Implement Put/Call ratio fetching** (20 min)
  - [ ] 2.4.1 Add method `fetch_put_call_ratio(date: date) -> float | None`
  - [ ] 2.4.2 Fetch Cboe CSV: `https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv`
  - [ ] 2.4.3 Parse CSV with pandas: `df = pd.read_csv(url, parse_dates=['DATE'])`
  - [ ] 2.4.4 Filter to requested date, extract P/C Ratio column
  - [ ] 2.4.5 Cache result in memory (CSV has historical data, no need to refetch)
  - [ ] 2.4.6 Handle errors: log and return None
  - [ ] 2.4.7 Add unit test: mock CSV response

- [ ] **2.5 Implement SPY data fetching** (15 min)
  - [ ] 2.5.1 Add method `fetch_spy_data(date: date) -> dict | None`
  - [ ] 2.5.2 Query `day_bars` for SPY close price on date
  - [ ] 2.5.3 Query `technical_indicators` for SPY sma_200 and rsi_14 on date
  - [ ] 2.5.4 Return dict: `{close, sma_200, rsi_14}` or None if data missing
  - [ ] 2.5.5 Add unit test: mock database queries

- [ ] **2.6 Implement breadth fetching (OPTIONAL)** (30 min - skip if Phase 0 deferred)
  - [ ] 2.6.1 Add method `fetch_market_breadth(date: date) -> float | None`
  - [ ] 2.6.2 Query S&P 500 constituents (from new table or cached list)
  - [ ] 2.6.3 For each ticker, query if price > sma_50 on date
  - [ ] 2.6.4 Calculate percentage: `(count_above_sma / total_count) * 100`
  - [ ] 2.6.5 Return breadth percentage or None if insufficient data
  - [ ] 2.6.6 Add unit test: mock constituent list and prices

- [ ] **2.7 Implement orchestration method** (10 min)
  - [ ] 2.7.1 Add method `fetch_all_inputs(date: date) -> dict`
  - [ ] 2.7.2 Call all fetch methods concurrently or sequentially
  - [ ] 2.7.3 Return dict with all signals + source_map tracking
  - [ ] 2.7.4 Log missing data warnings
  - [ ] 2.7.5 Add integration test: test with real database (if available)

---

### Phase 3: Calculation Engine (1 hour)

**Goal**: Calculate percentiles and compose Fear & Greed score

- [ ] **3.1 Create fear_greed.py skeleton** (5 min)
  - [ ] 3.1.1 Create `backend/app/market/fear_greed.py`
  - [ ] 3.1.2 Add imports: numpy, pandas, structlog, datetime
  - [ ] 3.1.3 Define `FearGreedEngine` class
  - [ ] 3.1.4 Add constants for regime labels and weights

- [ ] **3.2 Implement percentile calculation** (20 min)
  - [ ] 3.2.1 Add method `calculate_percentile(value: float, historical_series: list[float], invert: bool) -> int`
  - [ ] 3.2.2 Use numpy: `percentile = np.percentile(historical_series + [value], value) * 100`
  - [ ] 3.2.3 If invert=True (for VIX, HY spread, Put/Call), return `100 - percentile`
  - [ ] 3.2.4 Clamp result to 0-100
  - [ ] 3.2.5 Add unit tests: test normal distribution, edge cases (min/max values)

- [ ] **3.3 Implement signal scoring** (15 min)
  - [ ] 3.3.1 Add method `score_signals(inputs: dict, window_days: int = 252) -> dict`
  - [ ] 3.3.2 For each signal, fetch historical data from database (last window_days)
  - [ ] 3.3.3 Calculate percentile for current value
  - [ ] 3.3.4 Apply inversion for fear signals (VIX, HY spread, Put/Call)
  - [ ] 3.3.5 Return dict: `{vix_pct, momentum_pct, rsi_pct, pcr_pct, credit_pct, breadth_pct?}`
  - [ ] 3.3.6 Add unit test: test with mock historical data

- [ ] **3.4 Implement momentum scoring** (10 min)
  - [ ] 3.4.1 Add method `score_momentum(spy_close: float, spy_sma_200: float) -> int`
  - [ ] 3.4.2 Calculate: `pct_above = ((spy_close / sma_200) - 1) * 100`
  - [ ] 3.4.3 Convert to 0-100 score: `score = min(100, max(0, 50 + (pct_above * 2)))`
  - [ ] 3.4.4 Return score
  - [ ] 3.4.5 Add unit tests: test above/below/at SMA_200

- [ ] **3.5 Implement composition** (10 min)
  - [ ] 3.5.1 Add method `compose_score(components: dict) -> float`
  - [ ] 3.5.2 Calculate weights based on signal_count (5 or 6)
    ```python
    if breadth_pct is None:
        # 5 signals: equal weight 20% each
        weights = [0.2, 0.2, 0.2, 0.2, 0.2]
    else:
        # 6 signals: equal weight ~16.67% each
        weights = [0.167, 0.167, 0.167, 0.167, 0.167, 0.165]
    ```
  - [ ] 3.5.3 Calculate: `score = sum(component * weight for component, weight in zip(components.values(), weights))`
  - [ ] 3.5.4 Round to 1 decimal place
  - [ ] 3.5.5 Add unit test: test with sample components

- [ ] **3.6 Implement label assignment** (5 min)
  - [ ] 3.6.1 Add method `assign_label(score: float) -> str`
  - [ ] 3.6.2 Apply thresholds:
    ```python
    if score >= 75: return "Extreme Greed"
    elif score >= 55: return "Greed"
    elif score >= 45: return "Neutral"
    elif score >= 25: return "Fear"
    else: return "Extreme Fear"
    ```
  - [ ] 3.6.3 Add unit test: test all boundary conditions

- [ ] **3.7 Implement full calculation pipeline** (10 min)
  - [ ] 3.7.1 Add method `calculate(inputs: dict, date: date) -> dict`
  - [ ] 3.7.2 Call score_signals() to get percentiles
  - [ ] 3.7.3 Call compose_score() to get final score
  - [ ] 3.7.4 Call assign_label() to get regime
  - [ ] 3.7.5 Fetch previous score for trend calculation
  - [ ] 3.7.6 Return full result dict with all fields
  - [ ] 3.7.7 Add integration test: end-to-end calculation

---

### Phase 4: Service Layer (45 min)

**Goal**: Orchestrate fetching, calculation, and persistence

- [ ] **4.1 Create fear_greed_service.py skeleton** (5 min)
  - [ ] 4.1.1 Create `backend/app/market/fear_greed_service.py`
  - [ ] 4.1.2 Add imports: datetime, FearGreedDataFetcher, FearGreedEngine, PortfolioStorage
  - [ ] 4.1.3 Define `FearGreedService` class with storage, fetcher, engine

- [ ] **4.2 Implement input persistence** (10 min)
  - [ ] 4.2.1 Add method `persist_inputs(date: date, inputs: dict) -> None`
  - [ ] 4.2.2 Upsert into fear_greed_inputs table
  - [ ] 4.2.3 Use ON CONFLICT DO UPDATE for idempotency
  - [ ] 4.2.4 Add unit test: verify database insert

- [ ] **4.3 Implement component persistence** (10 min)
  - [ ] 4.3.1 Add method `persist_components(date: date, components: dict) -> None`
  - [ ] 4.3.2 Upsert into fear_greed_components table
  - [ ] 4.3.3 Use ON CONFLICT DO UPDATE
  - [ ] 4.3.4 Add unit test: verify database insert

- [ ] **4.4 Implement score persistence** (10 min)
  - [ ] 4.4.1 Add method `persist_score(date: date, result: dict) -> None`
  - [ ] 4.4.2 Upsert into fear_greed_daily table
  - [ ] 4.4.3 Include score, label, previous_score, score_change, signal_count
  - [ ] 4.4.4 Use ON CONFLICT DO UPDATE
  - [ ] 4.4.5 Add unit test: verify database insert

- [ ] **4.5 Implement compute method** (15 min)
  - [ ] 4.5.1 Add method `compute_for_date(date: date) -> dict`
  - [ ] 4.5.2 Fetch inputs via FearGreedDataFetcher
  - [ ] 4.5.3 Calculate components and score via FearGreedEngine
  - [ ] 4.5.4 Persist all results (inputs, components, score)
  - [ ] 4.5.5 Emit telemetry logs
  - [ ] 4.5.6 Return final result dict
  - [ ] 4.5.7 Handle partial failures gracefully (log and continue)
  - [ ] 4.5.8 Add integration test: full compute cycle

- [ ] **4.6 Implement retrieval methods** (10 min)
  - [ ] 4.6.1 Add method `get_latest() -> dict | None`
  - [ ] 4.6.2 Query fear_greed_daily ORDER BY as_of_date DESC LIMIT 1
  - [ ] 4.6.3 Add method `get_by_date(date: date) -> dict | None`
  - [ ] 4.6.4 Add method `get_history(start: date, end: date) -> list[dict]`
  - [ ] 4.6.5 Add unit tests: verify queries

---

### Phase 5: API & Tasks (1 hour)

**Goal**: Expose REST endpoints and schedule daily compute

- [ ] **5.1 Create Pydantic models** (15 min)
  - [ ] 5.1.1 Create `backend/app/models/fear_greed.py`
  - [ ] 5.1.2 Define `FearGreedReading` model:
    ```python
    class FearGreedReading(BaseModel):
        date: date
        score: float
        label: Literal["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
        previous_score: float | None = None
        score_change: float | None = None
        signal_count: int = 5
    ```
  - [ ] 5.1.3 Define `FearGreedComponent` model with percentile details
  - [ ] 5.1.4 Define `FearGreedResponse` model wrapping reading + optional components

- [ ] **5.2 Create API router** (20 min)
  - [ ] 5.2.1 Create `backend/app/api/market_fng.py`
  - [ ] 5.2.2 Add FastAPI router: `router = APIRouter(prefix="/api/market", tags=["market"])`
  - [ ] 5.2.3 Implement `GET /api/market/fear-greed`
    - Query params: `date: date | None`, `include_components: bool = False`
    - Return FearGreedResponse
    - Default to latest if date not provided
  - [ ] 5.2.4 Implement `GET /api/market/fear-greed/history`
    - Query params: `start: date`, `end: date`
    - Return list[FearGreedReading]
  - [ ] 5.2.5 Implement `GET /api/market/fear-greed/components`
    - Query params: `date: date | None`
    - Return component percentiles
  - [ ] 5.2.6 Add error handling: 404 if no data, 500 on server errors

- [ ] **5.3 Register API router** (5 min)
  - [ ] 5.3.1 Open `backend/app/api/__init__.py`
  - [ ] 5.3.2 Import market_fng router
  - [ ] 5.3.3 Add to app.include_router() calls

- [ ] **5.4 Create Celery task** (15 min)
  - [ ] 5.4.1 Create `backend/app/tasks/fear_greed_tasks.py`
  - [ ] 5.4.2 Define `compute_fear_greed_daily` task:
    ```python
    @celery_app.task(bind=True)
    def compute_fear_greed_daily(self):
        service = FearGreedService(...)
        result = service.compute_for_date(date.today())
        logger.info("fear_greed_computed", result=result)
        return result
    ```
  - [ ] 5.4.3 Add error handling and retries

- [ ] **5.5 Schedule Celery Beat** (10 min)
  - [ ] 5.5.1 Open `backend/app/celery_app.py`
  - [ ] 5.5.2 Import fear_greed_tasks
  - [ ] 5.5.3 Add to CELERY_BEAT_SCHEDULE:
    ```python
    'compute-fear-greed-daily': {
        'task': 'app.tasks.fear_greed_tasks.compute_fear_greed_daily',
        'schedule': crontab(hour=3, minute=30),  # 03:30 UTC daily
    }
    ```
  - [ ] 5.5.4 Test: Restart Celery and verify schedule

- [ ] **5.6 Test API endpoints** (10 min)
  - [ ] 5.6.1 Start backend server
  - [ ] 5.6.2 Test: `curl http://localhost:8000/api/market/fear-greed`
  - [ ] 5.6.3 Test: `curl http://localhost:8000/api/market/fear-greed/history?start=2025-11-01&end=2025-11-07`
  - [ ] 5.6.4 Test: `curl http://localhost:8000/api/market/fear-greed?include_components=true`
  - [ ] 5.6.5 Verify responses match Pydantic schemas

---

### Phase 6: Frontend (1.5 hours)

**Goal**: Display Fear & Greed gauge on dashboard

- [ ] **6.1 Create API client function** (10 min)
  - [ ] 6.1.1 Open `frontend/lib/api/market.ts`
  - [ ] 6.1.2 Add interface:
    ```typescript
    export interface FearGreedResponse {
      date: string;
      score: number;
      label: "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed";
      previous_score?: number;
      score_change?: number;
      signal_count: number;
    }
    ```
  - [ ] 6.1.3 Add function:
    ```typescript
    export async function fetchFearGreed(): Promise<FearGreedResponse> {
      return apiRequest<FearGreedResponse>("/api/market/fear-greed");
    }
    ```

- [ ] **6.2 Create TanStack Query hook** (10 min)
  - [ ] 6.2.1 Create `frontend/lib/hooks/useFearGreed.ts`
  - [ ] 6.2.2 Implement hook:
    ```typescript
    export function useFearGreed() {
      return useQuery({
        queryKey: ["market", "fear-greed"],
        queryFn: fetchFearGreed,
        staleTime: 1000 * 60 * 60,  // 1 hour (updates daily)
        refetchInterval: 1000 * 60 * 60 * 4,  // Refetch every 4 hours
      });
    }
    ```

- [ ] **6.3 Create FearGreedGauge component** (45 min)
  - [ ] 6.3.1 Create `frontend/components/market/FearGreedGauge.tsx`
  - [ ] 6.3.2 Import Card, Badge, useFearGreed
  - [ ] 6.3.3 Implement loading skeleton (animated pulse)
  - [ ] 6.3.4 Implement getDisplay helper:
    ```typescript
    const getDisplay = (score: number) => {
      if (score >= 75) return { emoji: "😱", label: "Extreme Greed", color: "gain" };
      if (score >= 55) return { emoji: "😃", label: "Greed", color: "gain" };
      if (score >= 45) return { emoji: "😐", label: "Neutral", color: "neutral" };
      if (score >= 25) return { emoji: "😟", label: "Fear", color: "loss" };
      return { emoji: "😨", label: "Extreme Fear", color: "loss" };
    };
    ```
  - [ ] 6.3.5 Implement component layout:
    - Card with title "Fear & Greed Index"
    - Large score number (text-6xl)
    - Badge with emoji + label
    - Trend indicator (↑/↓ score_change)
    - Signal count note (5 or 6 signals)
  - [ ] 6.3.6 Style with Tailwind classes matching existing patterns
  - [ ] 6.3.7 Add error state handling

- [ ] **6.4 Integrate into dashboard** (10 min)
  - [ ] 6.4.1 Open `frontend/app/page.tsx`
  - [ ] 6.4.2 Import FearGreedGauge component
  - [ ] 6.4.3 Add after MarketConditions (line ~53):
    ```tsx
    {/* Fear & Greed Index */}
    <div className="mb-10">
      <FearGreedGauge />
    </div>
    ```
  - [ ] 6.4.4 Save and verify no TypeScript errors

- [ ] **6.5 Test frontend UI** (15 min)
  - [ ] 6.5.1 Start frontend dev server: `npm run dev`
  - [ ] 6.5.2 Navigate to http://localhost:3000
  - [ ] 6.5.3 Verify Fear & Greed card displays between MarketConditions and Portfolio
  - [ ] 6.5.4 Check loading state appears briefly
  - [ ] 6.5.5 Verify score, label, emoji, and trend display correctly
  - [ ] 6.5.6 Test responsive layout (mobile/tablet/desktop)
  - [ ] 6.5.7 Screenshot for docs

- [ ] **6.6 Optional: Add watchlist chip** (15 min - SKIP if time constrained)
  - [ ] 6.6.1 Open `frontend/components/watchlist/WatchlistTable.tsx`
  - [ ] 6.6.2 Import useFearGreed hook
  - [ ] 6.6.3 Call hook at component level
  - [ ] 6.6.4 Add small badge in Symbol column (line ~356):
    ```tsx
    {fearGreed && (
      <Badge variant={fearGreed.score >= 50 ? "gain" : "loss"} className="text-xs">
        {getDisplay(fearGreed.score).emoji} {fearGreed.score.toFixed(0)}
      </Badge>
    )}
    ```
  - [ ] 6.6.5 Test: Verify chip appears in watchlist table

---

### Phase 7: Testing & Validation (1 hour)

**Goal**: Comprehensive tests and quality checks

- [ ] **7.1 Unit tests - Data fetching** (15 min)
  - [ ] 7.1.1 Write tests for `fear_greed_data.py` (file already created in Phase 2)
  - [ ] 7.1.2 Mock FRED API responses
  - [ ] 7.1.3 Mock Cboe CSV responses
  - [ ] 7.1.4 Mock database queries
  - [ ] 7.1.5 Test error handling (network failures, missing data)

- [ ] **7.2 Unit tests - Calculation engine** (15 min)
  - [ ] 7.2.1 Write tests for `fear_greed.py` (file already created in Phase 3)
  - [ ] 7.2.2 Test percentile calculation with known distributions
  - [ ] 7.2.3 Test signal inversion (VIX, HY spread, Put/Call)
  - [ ] 7.2.4 Test momentum scoring edge cases
  - [ ] 7.2.5 Test composition with 5 and 6 signals
  - [ ] 7.2.6 Test label assignment boundary conditions

- [ ] **7.3 Integration tests - Service** (15 min)
  - [ ] 7.3.1 Write tests for `fear_greed_service.py`
  - [ ] 7.3.2 Test full compute_for_date() pipeline
  - [ ] 7.3.3 Test database persistence (use test database)
  - [ ] 7.3.4 Test idempotency (run compute twice, verify same result)
  - [ ] 7.3.5 Test partial data scenarios (some signals missing)

- [ ] **7.4 API tests** (10 min)
  - [ ] 7.4.1 Write tests for `market_fng.py` endpoints
  - [ ] 7.4.2 Test GET /api/market/fear-greed (with/without data)
  - [ ] 7.4.3 Test GET /api/market/fear-greed/history
  - [ ] 7.4.4 Test GET /api/market/fear-greed/components
  - [ ] 7.4.5 Test error cases (404, 500)

- [ ] **7.5 Run full test suite** (5 min)
  - [ ] 7.5.1 Run: `cd backend && pytest tests/market/ -v`
  - [ ] 7.5.2 Verify all tests pass
  - [ ] 7.5.3 Check coverage: `pytest tests/market/ --cov=app/market --cov-report=term`
  - [ ] 7.5.4 Target: 80%+ coverage

- [ ] **7.6 Quality checks** (10 min)
  - [ ] 7.6.1 Run mypy: `mypy backend/app/market/ --strict`
  - [ ] 7.6.2 Run ruff: `ruff check backend/app/market/`
  - [ ] 7.6.3 Run ruff format: `ruff format backend/app/market/`
  - [ ] 7.6.4 Fix any violations
  - [ ] 7.6.5 Verify all checks pass

- [ ] **7.7 Manual end-to-end test** (10 min)
  - [ ] 7.7.1 Restart all services: `bash ~/portfolio-ai/scripts/restart.sh`
  - [ ] 7.7.2 Trigger manual compute: Run Celery task or call API directly
  - [ ] 7.7.3 Verify database: Query fear_greed_daily table
  - [ ] 7.7.4 Test API: `curl http://localhost:8000/api/market/fear-greed | jq`
  - [ ] 7.7.5 Test frontend: Load http://localhost:3000, verify gauge displays
  - [ ] 7.7.6 Check logs for errors

---

### Phase 8 (OPTIONAL): Market Breadth Implementation

**Goal**: Add 6th signal (breadth) if Phase 0 test passed

**⚠️ ONLY DO THIS PHASE IF Phase 0 decision was "INCLUDE"**

- [ ] **8.1 Create S&P 500 constituent module** (30 min)
  - [ ] 8.1.1 Create `backend/app/market/sp500_constituents.py`
  - [ ] 8.1.2 Add method `fetch_sp500_list() -> list[str]`
  - [ ] 8.1.3 Primary: Try FMP API endpoint
  - [ ] 8.1.4 Fallback: Parse Wikipedia table with pandas
  - [ ] 8.1.5 Cache result in database (new table: `index_constituents`)
  - [ ] 8.1.6 Add refresh schedule (monthly Celery task)

- [ ] **8.2 Create breadth calculator** (30 min)
  - [ ] 8.2.1 Create `backend/app/market/breadth_calculator.py`
  - [ ] 8.2.2 Add method `calculate_breadth(date: date, tickers: list[str]) -> float`
  - [ ] 8.2.3 For each ticker, query if price > sma_50 on date
  - [ ] 8.2.4 Use batch queries for performance (not N+1)
  - [ ] 8.2.5 Calculate percentage: (count_above / total) * 100
  - [ ] 8.2.6 Handle missing data gracefully (skip tickers without data)

- [ ] **8.3 Integrate breadth into data fetcher** (15 min)
  - [ ] 8.3.1 Update `fear_greed_data.py` fetch_all_inputs()
  - [ ] 8.3.2 Call breadth_calculator if enabled
  - [ ] 8.3.3 Add breadth to returned dict
  - [ ] 8.3.4 Update signal_count to 6

- [ ] **8.4 Update calculation engine** (10 min)
  - [ ] 8.4.1 Update `fear_greed.py` compose_score()
  - [ ] 8.4.2 Handle 6-signal weighting (equal weight ~16.67% each)
  - [ ] 8.4.3 Add breadth percentile calculation

- [ ] **8.5 Update tests** (15 min)
  - [ ] 8.5.1 Add tests for sp500_constituents module
  - [ ] 8.5.2 Add tests for breadth_calculator
  - [ ] 8.5.3 Update integration tests to include breadth
  - [ ] 8.5.4 Run full test suite

- [ ] **8.6 Document breadth addition** (10 min)
  - [ ] 8.6.1 Update task summary to reflect 6 signals
  - [ ] 8.6.2 Update API_REFERENCE.md
  - [ ] 8.6.3 Update frontend to show "6 signals" if present
  - [ ] 8.6.4 Add note about S&P 500 constituent refresh schedule

---

## Final Verification (MANDATORY)

- [ ] **V.1 Functional Requirements**
  - [ ] V.1.1 Fear & Greed score calculated daily (0-100)
  - [ ] V.1.2 All 5 core signals working (VIX, Momentum, RSI, Put/Call, Credit)
  - [ ] V.1.3 Label assigned correctly (Extreme Fear → Extreme Greed)
  - [ ] V.1.4 Trend indicator shows daily change
  - [ ] V.1.5 API endpoints return valid data
  - [ ] V.1.6 Frontend gauge displays correctly
  - [ ] V.1.7 Celery task runs daily at 03:30 UTC

- [ ] **V.2 Data Quality**
  - [ ] V.2.1 VIX data fresh (updated daily from FRED)
  - [ ] V.2.2 SPY data fresh (from day_bars table)
  - [ ] V.2.3 HY spread data fresh (from FRED)
  - [ ] V.2.4 Put/Call ratio data fresh (from Cboe CSV)
  - [ ] V.2.5 No stale data warnings (< 2 days old)
  - [ ] V.2.6 Historical percentiles calculated correctly (252-day window)

- [ ] **V.3 Tests & Quality**
  - [ ] V.3.1 All unit tests pass (80%+ coverage)
  - [ ] V.3.2 All integration tests pass
  - [ ] V.3.3 All API tests pass
  - [ ] V.3.4 mypy --strict passes (no type errors)
  - [ ] V.3.5 ruff check passes (no lint errors)
  - [ ] V.3.6 No TODOs or XXX comments in code

- [ ] **V.4 Documentation**
  - [ ] V.4.1 API_REFERENCE.md updated with 3 endpoints
  - [ ] V.4.2 ARCHITECTURE.md updated with Fear & Greed section
  - [ ] V.4.3 All functions have docstrings
  - [ ] V.4.4 README note added about Fear & Greed feature

- [ ] **V.5 User Experience**
  - [ ] V.5.1 Dashboard gauge loads without errors
  - [ ] V.5.2 Score and label display clearly
  - [ ] V.5.3 Emoji matches regime (😨 Fear → 😱 Greed)
  - [ ] V.5.4 Trend arrow shows correctly (↑/↓)
  - [ ] V.5.5 Responsive layout works (mobile/desktop)
  - [ ] V.5.6 Loading state appears during data fetch

- [ ] **V.6 Production Readiness**
  - [ ] V.6.1 Database migration applied successfully
  - [ ] V.6.2 Celery task scheduled and running
  - [ ] V.6.3 Logs show successful computes
  - [ ] V.6.4 No errors in backend logs
  - [ ] V.6.5 No errors in frontend console
  - [ ] V.6.6 Services restart successfully

---

## Success Criteria

**Core (MUST HAVE)**:
- ✅ 5-signal Fear & Greed Index operational
- ✅ Daily score (0-100) with regime label
- ✅ Dashboard gauge displaying current score
- ✅ API endpoints working (current + history)
- ✅ Celery task running daily
- ✅ 80%+ test coverage
- ✅ All quality checks passing

**Optional (NICE TO HAVE)**:
- ⚠️ 6th signal (market breadth) - Only if Phase 0 test passed
- ⚠️ Watchlist chip showing F&G score - Time permitting
- ⚠️ Historical chart (90-day sparkline) - Defer to v2

---

## Dependencies

**External**:
- FRED API key (already configured)
- FMP API key (already configured) - Used for S&P 500 list if breadth included
- Cboe CSV endpoint (public, no key)

**Internal**:
- FRED integration (`app/sources/fred.py`)
- SPY data in `day_bars` table
- Technical indicators (SMA_200, RSI_14) in `technical_indicators` table
- Celery Beat scheduler
- PostgreSQL database

---

## Notes

**Design Decisions**:
- Equal weight all signals (simpler than complex weighting)
- 252-day window for percentiles (1 year of trading days)
- Daily compute at 03:30 UTC (after market close + data availability)
- Price-only momentum (not total return) - Simpler, 95% accurate
- Skip nowcast/intraday updates for v1 (daily is enough)

**Breadth Decision Gate**:
- Phase 0 tests breadth feasibility FIRST
- If fast (<5s) and data available → Include in main implementation
- If slow or complex → Defer to optional Phase 8
- This prevents wasting time on expensive feature that might not be needed

**Alternative Data Sources** (if needed):
- VIX: Can use YFinance or Polygon if FRED unavailable
- HY Spread: FRED is primary source (no good alternatives)
- Put/Call: Cboe CSV is free and reliable (no API key needed)
- S&P 500 list: Wikipedia fallback if FMP fails

**Performance Considerations**:
- Breadth calculation is most expensive (500 tickers × database queries)
- Use batch queries or sampling to optimize
- Cache S&P 500 list (changes infrequently)
- Cache percentile calculations (reuse historical data)

**Maintenance Notes**:
- Cboe CSV format may change (monitor for breakage)
- S&P 500 membership changes quarterly (refresh constituent list)
- FRED series occasionally revised (historical data may change)
- VIX calculation methodology stable (low maintenance)

---

**Ready to Start**: Run `/do_it tasks/tasks-0037-fear-greed-index.md`

**Total Estimated Time**:
- Phase 0 (Breadth test): 30 min
- Phases 1-7 (Core 5-signal): 6-8 hours
- Phase 8 (Optional breadth): +2 hours if included
- **Total: 6.5 - 10.5 hours depending on breadth decision**
