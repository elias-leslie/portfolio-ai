# FUTURE TASK: Market-Sim Data Sources Migration

**Purpose**: Document the data sources from market-sim that should be migrated to portfolio-ai when implementing the full multi-source architecture (PRD #0010).

**Status**: Reference Document (Not yet a PRD/Task List)

---

## Market-Sim Data Sources Inventory

### Source Files (from ~/market-sim/app/sources/)
1. **base.py** - Abstract base class, SourceManager, DatasetRequest
2. **rest_api_source.py** - Generic REST API source adapter (database-driven configuration)
3. **polygon_source.py** - Polygon.io integration
4. **yfinance_source.py** - Yahoo Finance integration
5. **finnhub_source.py** - Finnhub integration
6. **fred_source.py** - FRED economic data
7. **google_news_source.py** - Google News RSS
8. **rss_feed_source.py** - Generic RSS feed source

### Multi-Source Infrastructure
- **multi_source_fetcher.py** - Intelligent failover, rate limit handling, priority-based routing
- **polygon_client.py** - Polygon REST client with rate limiting and retries
- **source_cache.py** - Source-specific caching layer

### Database Schema (DuckDB Tables)
From market-sim's database, need to extract:

1. **source_registry** - Source configuration, priority, enabled flag, definition JSON
2. **source_credentials** - API keys and auth tokens (encrypted/secure)
3. **endpoint_catalog** - Endpoint definitions, path templates, field mappings, target tables

### Source YAML Configurations

**Location**: `~/market-sim/config/sources/*.yaml`

All data sources are configured via YAML files that define:
- Connection details (base_url, auth, timeout)
- Field mappings (JSONPath → DuckDB columns)
- Rate limits
- Capabilities (minute/day/reference/news)
- Priority ordering

**Available Source Configs** (12 total from market-sim):

**ENABLED Sources (9 viable on free tier):**
1. **yfinance.yaml** - Yahoo Finance (priority: 1, FREE, unlimited with delays, 10+ years history)
2. **twelvedata.yaml** - Twelve Data (priority: 2, 8 req/min, 800/day - SECONDARY OHLCV)
3. **fmp.yaml** - Financial Modeling Prep (priority: 3, 250/day - TERTIARY OHLCV + METADATA)
4. **polygon.yaml** - Polygon.io (priority: 10, 5 req/min - PRIMARY fallback)
5. **finnhub.yaml** - Finnhub (priority: 10, 60 req/min - News + metadata)
6. **newsapi.yaml** - NewsAPI (priority: 25, 100 req/day - Global news)
7. **alphavantage.yaml** - Alpha Vantage (priority: 30, 5 req/min, 500/day - Reliable fallback)
8. **fred.yaml** - FRED economic data (FREE - Economic indicators)
9. **google_news.yaml** - Google News RSS (FREE - RSS news feed)

**DISABLED Sources (not viable on free tier):**
10. **alpaca.yaml** - Alpaca Markets (DISABLED - free tier blocks historical 403)
11. **stockdata.yaml** - StockData.org (DISABLED - 100 req/day insufficient)
12. **filter_engine.yaml** - Internal filter (not a data source)

### API Keys to Extract from Market-Sim

**Action Required**: When ready to implement PRD #0010:

```bash
# 1. Copy YAML configs
cp ~/market-sim/config/sources/*.yaml ~/portfolio-ai/config/sources/

# 2. Extract API keys from environment or Docker
cd ~/market-sim
docker-compose up -d
docker exec market-sim-app env | grep -E "POLYGON|FINNHUB|FRED|NEWSAPI|ALPHAVANTAGE|FMP|TWELVEDATA|STOCKDATA|ALPACA"

# 3. If keys stored in DuckDB, extract credentials table
docker exec market-sim-app python -c "
import duckdb
conn = duckdb.connect('data/market_data.duckdb')
print(conn.execute('SELECT * FROM source_credentials').fetchdf().to_markdown())
print(conn.execute('SELECT * FROM source_registry').fetchdf().to_markdown())
print(conn.execute('SELECT * FROM endpoint_catalog').fetchdf().to_markdown())
"
```

### Data Sources to Migrate (by Capability & Load Balancing)

**Load Balancing Strategy**: Multi-source fetcher uses priority-based failover with rate limit awareness. Lower priority number = tried first. When primary hits rate limit (429), automatically fails over to next source.

**TIER 1 - Primary OHLCV Sources** (Daily price + reference data):
1. **yfinance** (priority: 1) - FREE, unlimited with 0.5s delays, 10+ years history, NO auth
2. **twelvedata** (priority: 2) - 8 req/min, 800/day (sufficient for 50-100 tickers)
3. **fmp** (priority: 3) - 250 req/day, EOD + VWAP, comprehensive company profiles

**TIER 2 - Backup OHLCV Sources** (Failover when Tier 1 rate-limited):
4. **polygon** (priority: 10) - 5 req/min, minute + day bars, reference data, news
5. **alphavantage** (priority: 30) - 5 req/min, 500/day, reliable fallback, fundamentals

**TIER 3 - News Sources** (Load balanced for company news):
6. **finnhub** (priority: 10) - 60 req/min, company-specific news + metadata
7. **polygon** (priority: 10) - Also provides news (shared with OHLCV)
8. **newsapi** (priority: 25) - 100 req/day, global news search with query
9. **google_news** (priority: N/A) - FREE RSS, no auth, general market news

**TIER 4 - Economic Data**:
10. **fred** (priority: N/A) - FREE FRED API, economic indicators (VIX, DXY, TNX, etc.)

**DISABLED** (document but don't implement):
- **alpaca** - Free tier blocks historical endpoints (403 Forbidden on /bars)
- **stockdata** - 100 req/day insufficient for daily operations

**Why Multiple Sources Matter**:
- **Resilience**: If yfinance down/rate-limited, fails over to twelvedata → fmp → polygon → alphavantage
- **Load Balancing**: Distribute requests across sources to avoid hitting any single rate limit
- **Cost Optimization**: Use free sources first, paid fallback only when needed
- **Data Quality**: Cross-validate prices across sources, detect anomalies

### Key Features from Market-Sim to Preserve

1. **Database-Driven Configuration**
   - No hardcoded API keys in code
   - All sources configured via DuckDB tables
   - Field mappings stored in endpoint_catalog

2. **Intelligent Failover**
   - Priority-based source selection
   - Automatic retry with next source on rate limit (429)
   - Per-source cooldown tracking (60s default)
   - Success/failure statistics

3. **Rate Limiting**
   - Per-source rate limits (configurable)
   - Automatic throttling
   - Exponential backoff with retries (tenacity library)

4. **Generic REST API Adapter**
   - RestApiSource class configurable via JSON
   - JSONPath field mapping
   - Supports query params, headers, bearer tokens
   - Placeholder resolution for credentials

5. **Caching Layer**
   - Source-specific cache (e.g., news_count cache)
   - TTL-based invalidation
   - Cache hits logged for monitoring

---

## Migration Strategy (When Implementing PRD #0010)

### Phase 1: Extract Credentials
- [ ] Start market-sim Docker container
- [ ] Extract source_credentials table → CSV/JSON
- [ ] Extract source_registry table → CSV/JSON
- [ ] Extract endpoint_catalog table → CSV/JSON
- [ ] Document API key sources (where to get new keys if needed)

### Phase 2: Create Portfolio-AI Schema
- [ ] Add source_registry table to portfolio-ai schema.py
- [ ] Add source_credentials table (with encryption consideration)
- [ ] Add endpoint_catalog table
- [ ] Create migration script to import market-sim data

### Phase 3: Port Source Infrastructure
- [ ] Copy multi_source_fetcher.py → backend/app/sources/
- [ ] Copy rest_api_source.py → backend/app/sources/
- [ ] Adapt for portfolio-ai patterns (Pydantic models, storage facade)
- [ ] Add unit tests for failover logic

### Phase 4: Port Individual Sources
- [ ] polygon_source.py + polygon_client.py
- [ ] yfinance_source.py (replace existing simple implementation)
- [ ] finnhub_source.py
- [ ] Enhance fred_source.py with registry pattern
- [ ] Enhance google_news_source.py with registry pattern

### Phase 5: Integration
- [ ] Update PriceDataFetcher to use MultiSourceFetcher
- [ ] Update AgentTools to use multi-source for all data
- [ ] Add source performance tracking to health check
- [ ] Update documentation

---

## Notes

- **Why this matters**: Market-sim spent significant effort building robust multi-source failover. Don't recreate from scratch.
- **Security**: source_credentials table contains API keys. Consider encryption at rest.
- **Cost tracking**: Some sources (Polygon, Finnhub) have paid tiers. Track API usage.
- **Testing**: Market-sim has extensive tests for failover logic. Port those too.

---

**Created**: 2025-10-27
**For**: PRD #0010 - Multi-Source Data Architecture
**Reference**: ~/market-sim/app/sources/, ~/market-sim/app/multi_source_fetcher.py
