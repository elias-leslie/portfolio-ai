# Task List: DataFountain Service Extraction (P4)

**PRD**: Architecture Modularity Review - Priority 4 (Foundation)
**Status**: Ready
**Completion**: 0%
**Effort to Complete**: Medium (1-2 week sprint)
**Last Updated**: 2025-12-16

---

## MANDATORY: Verify Before Starting

**⚠️ LOCAL AGENT: Before implementing ANY step below, you MUST:**

1. **Analyze current data ingestion system**:
   ```bash
   # Review source adapters
   find ~/portfolio-ai/backend/app/sources -name "*.py" -exec wc -l {} +

   # Review ingestion tasks
   find ~/portfolio-ai/backend/app/tasks/ingestion -name "*.py"

   # Understand caching layer
   psql -d portfolio_ai -c "\d+ price_cache"
   psql -d portfolio_ai -c "\d+ day_bars"
   psql -d portfolio_ai -c "\d+ reference_cache"

   # Review multi-source failover logic
   grep -r "failover\|priority" ~/portfolio-ai/backend/app/sources/
   ```

2. **Map data sources**:
   - YFinance (free, primary)
   - Polygon (API key)
   - TwelveData (API key)
   - FMP (API key)
   - Finnhub (API key)
   - AlphaVantage (API key)
   - FRED (economic data)

3. **Understand dependencies**:
   - Who calls the data fetchers?
   - How is caching implemented?
   - What's the failover priority?

4. **Update this plan** and **create beads**

---

## Summary

**Goal**: Extract data ingestion layer into standalone **DataFountain** service that can serve market data to multiple applications.

**Why extract:**
- Reusable across multiple portfolio apps
- Could serve clients, research tools, other projects
- Potential commercial product (data-as-a-service)
- Clean separation of concerns

**✅ COMPLETE:** (None yet)
**🔄 IN PROGRESS:** Initial planning
**⚠️ NEXT STEPS:** Verify data sources, create beads, begin Phase 1

**⏱️ ESTIMATED REMAINING:** Medium complexity - 1-2 week sprint

---

## What Gets Extracted

### Backend Components (~10k LOC)
```
backend/app/
├── sources/                → datafountain/backend/app/adapters/
│   ├── base.py             (base adapter class)
│   ├── yfinance.py         (YFinance adapter)
│   ├── polygon.py          (Polygon adapter)
│   ├── twelvedata.py       (TwelveData adapter)
│   ├── fmp.py              (FMP adapter)
│   ├── finnhub.py          (Finnhub adapter)
│   ├── alphavantage.py     (AlphaVantage adapter)
│   └── fred.py             (FRED adapter)
├── tasks/ingestion/        → datafountain/backend/app/tasks/
│   ├── price_tasks.py      (price fetching tasks)
│   ├── reference_tasks.py  (fundamentals/reference data)
│   └── ohlcv_tasks.py      (OHLCV bars)
└── (caching logic)         → datafountain/backend/app/cache/
```

### Database Tables
```sql
-- Move these to DataFountain
CREATE TABLE price_cache (...)
CREATE TABLE day_bars (...)
CREATE TABLE minute_bars (...)
CREATE TABLE reference_cache (...)
CREATE TABLE source_registry (...)
CREATE TABLE source_credentials (...)
CREATE TABLE endpoint_catalog (...)
CREATE TABLE source_performance (...)
```

---

## Phase 1: DataFountain Repository Setup

### Phase 1.1: Initialize Repository

**Bead**: Create `Phase 1.1: DataFountain repo setup` with `complexity:small`

- [ ] Create repository
- [ ] Backend structure (FastAPI + Python 3.13)
- [ ] Database schema (PostgreSQL)
- [ ] Core documentation

### Phase 1.2: Define API Contract

**Bead**: Create `Phase 1.2: DataFountain API design` with `complexity:medium,domains:backend`

```python
# API Design
GET /api/prices?symbols=AAPL,MSFT,GOOGL
GET /api/ohlcv/{symbol}?interval=1d&start=2024-01-01&end=2024-12-31
GET /api/fundamentals/{symbol}
GET /api/economic/{indicator}  # FRED data
POST /api/refresh  # Trigger cache refresh
GET /api/sources/status  # Health of data sources
```

---

## Phase 2: Extract Source Adapters

### Phase 2.1: Copy Adapter Code

**Bead**: Create `Phase 2.1: Extract source adapters` with `complexity:large,domains:backend`

- [ ] Copy all adapters from portfolio-ai
- [ ] Refactor to remove portfolio-specific logic
- [ ] Make them pure data fetchers

### Phase 2.2: Multi-Source Failover

**Bead**: Create `Phase 2.2: Failover orchestration` with `complexity:medium,domains:backend`

- [ ] Implement priority-based failover
- [ ] Rate limiting per source
- [ ] Cooldown after failures
- [ ] Performance tracking

---

## Phase 3: Extract Caching Layer

**Bead**: Create `Phase 3: Caching layer` with `complexity:medium,domains:backend,domains:database`

- [ ] Migrate caching tables
- [ ] Implement cache strategies (15-min TTL for prices, 24h for fundamentals)
- [ ] Cache invalidation logic

---

## Phase 4: Client Library for Portfolio AI

**Bead**: Create `Phase 4: DataFountain client` with `complexity:small,domains:backend`

```python
# portfolio-ai uses DataFountain client
from datafountain import DataFountainClient

client = DataFountainClient(api_url="http://localhost:9000")
prices = await client.get_prices(["AAPL", "MSFT"])
```

---

## Success Criteria

1. ✅ DataFountain serves data to Portfolio AI
2. ✅ Multi-source failover works
3. ✅ Caching reduces API calls by 80%+
4. ✅ Can add second client application
5. ✅ Portfolio AI codebase reduced by ~10k LOC

---

**Version:** 1.0.0 | **Updated:** 2025-12-16
