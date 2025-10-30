# PRD #0016: Complete Multi-Source Failover for PriceDataFetcher

**Status**: Draft
**Created**: 2025-10-30
**Priority**: High
**Effort**: Medium (2-3 days)
**Dependencies**: PRD #0011 (Multi-Source Infrastructure - 85% complete)

---

## Introduction/Overview

Currently, `PriceDataFetcher` only uses 2 of 6 available data sources (YFinance and Polygon) for real-time price fetching in the watchlist feature. However, all 6 source adapters (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage) are implemented, tested, and working for historical data ingestion via Celery tasks.

This incomplete implementation creates a reliability gap: when YFinance fails or returns stale/incomplete data for certain tickers (like VTI showing "!" alerts), the system cannot failover to backup sources for real-time price fetching, even though those sources are available and functional.

**Goal**: Complete the multi-source failover implementation for `PriceDataFetcher` to match the reliability already achieved in historical data ingestion, ensuring correct, complete, and fresh price data flows through the entire pipeline (backend → calculations → frontend display).

---

## Goals

1. **Reliability**: Enable automatic failover across all 6 data sources when YFinance fails or returns incomplete data
2. **Data Quality**: Ensure price data is complete (all required fields), fresh (not stale), and correct (validated)
3. **Observability**: Track source performance metrics to enable continuous profiling and optimization
4. **Load Balancing**: Distribute requests efficiently across sources based on rate limits and performance
5. **Backward Compatibility**: Maintain existing behavior while adding robustness (no breaking changes)
6. **Full Pipeline**: Ensure data quality from backend fetch → technical calculations → frontend display

---

## User Stories

1. **As a portfolio manager**, I want the watchlist to show accurate scores for all tickers, so that I can trust the system even when primary data sources have issues.

2. **As a system operator**, I want visibility into which data sources are being used and their performance, so that I can optimize API usage and costs.

3. **As a developer**, I want the system to automatically failover to backup sources when YFinance fails, so that users don't see degraded scores or "!" alerts due to missing data.

4. **As a user**, I want fresh price data that updates reliably every 15 minutes, so that my investment decisions are based on current market conditions.

---

## Functional Requirements

### Phase 1: Core Multi-Source Integration

**FR-1.1**: `PriceDataFetcher` MUST initialize all 6 data sources in priority order from YAML configuration:
- Priority 1: YFinance (no API key required)
- Priority 2: TwelveData (requires API key)
- Priority 3: FMP (requires API key)
- Priority 4: Polygon (requires API key)
- Priority 5: Finnhub (requires API key)
- Priority 6: AlphaVantage (requires API key)

**FR-1.2**: The system MUST skip sources that REQUIRE an API key but don't have one configured, while still attempting sources that can work without keys (YFinance only).

**FR-1.3**: Failover MUST occur when:
- Source completely fails (HTTP errors, timeouts, exceptions)
- Source returns missing/incomplete data (null prices, zero prices, missing required fields)
- Source returns stale data (timestamp older than cache TTL threshold)

**FR-1.4**: The system MUST attempt sources in priority order until one returns complete, fresh, valid data.

**FR-1.5**: If all sources fail, the system MUST return cached data (if available) with a stale flag, OR return an error with detailed failure reasons.

### Phase 2: Performance Metrics & Profiling

**FR-2.1**: The system MUST track and persist source performance metrics in the `source_performance` table:
- Source name
- Success/failure rates
- Average response time (latency)
- Last success timestamp
- Error counts by type

**FR-2.2**: Performance metrics MUST be updated after every source attempt (success or failure).

**FR-2.3**: The system MUST log comprehensive failover events including:
- Source attempts (which sources tried, in what order)
- Failure reasons for each source
- Final source used successfully
- Total latency for the entire failover chain

**FR-2.4**: Metrics MUST enable future optimization of source priorities based on real-world performance.

### Phase 3: Health Checks & Monitoring

**FR-3.1**: The health check endpoint (`/health`) MUST be updated to show status for all 6 sources:
- Source name and priority
- API key configured (yes/no)
- Recent success rate (last 100 requests)
- Average latency
- Last successful fetch timestamp

**FR-3.2**: Health checks MUST indicate which sources are currently functional vs degraded/failing.

**FR-3.3**: Health dashboard MUST show source distribution (how many requests each source handled).

### Phase 4: Frontend Indicators

**FR-4.1**: The watchlist UI MUST display which source was used for each ticker's data:
- Show source name as a small badge/indicator
- Color-code by priority (green=YFinance, yellow=backup source, red=cached/stale)

**FR-4.2**: When data is stale or from cache, the UI MUST clearly indicate this to the user.

**FR-4.3**: The UI MUST show when failover occurred (e.g., "Data from TwelveData (YFinance unavailable)").

### Phase 5: Testing

**FR-5.1**: Unit tests MUST verify each source initializes correctly with/without API keys.

**FR-5.2**: Integration tests MUST simulate source failures and verify correct failover behavior:
- Test YFinance failure → TwelveData success
- Test all sources fail → return cached data
- Test source returns incomplete data → try next source

**FR-5.3**: End-to-end tests MUST verify watchlist operations with multi-source failover:
- Add ticker → fetch from best available source
- Refresh watchlist → distribute load across sources
- Handle source failure → no degraded scores

**FR-5.4**: All tests MUST follow guidance from `/do_it` command for AI agent execution.

---

## Non-Goals (Out of Scope)

1. **Changing source priorities**: Priorities are defined in YAML configs and should remain fixed for this PRD
2. **Adding new data sources**: Only use the existing 6 sources
3. **Real-time streaming**: Continue using polling-based 15-minute refresh cycle
4. **User-configurable sources**: Source selection remains automatic based on priority/availability
5. **Historical data changes**: Only update real-time price fetching (`PriceDataFetcher`), not historical ingestion (already works)

---

## Design Considerations

### Source Priority Logic

Based on YAML configurations (`config/sources/*.yaml`):

```yaml
1. YFinance (priority: 1)
   - Rate limit: Unlimited (60 req/min conservative)
   - Auth: None required
   - Notes: Primary source, best coverage

2. TwelveData (priority: 2)
   - Rate limit: 8 req/min, 800 req/day
   - Auth: API key required
   - Notes: Good backup, reasonable limits

3. FMP (priority: 3)
   - Rate limit: 250 req/day
   - Auth: API key required
   - Notes: Limited free tier, tertiary source

4. Polygon (priority: 10)
   - Rate limit: 5 req/min
   - Auth: API key required
   - Notes: Very limited free tier

5. Finnhub (priority: 10)
   - Rate limit: 60 req/min
   - Auth: API key required
   - Notes: Good limits but lower priority

6. AlphaVantage (priority: 30)
   - Rate limit: 5 req/min, 500 req/day
   - Auth: API key required
   - Notes: Last resort, very limited
```

### API Key Handling

- **YFinance**: No API key needed → always include
- **All others**: Check for API key in environment/database → skip if missing

### Caching Strategy

- Keep existing 15-minute cache TTL
- Add source performance metrics to inform caching decisions
- Consider per-source cache TTLs in future iterations (out of scope for this PRD)

---

## Technical Considerations

### Files to Modify

1. **backend/app/portfolio/price_fetcher.py** (Phase 1)
   - Update `__init__` to initialize all 6 sources
   - Add API key checks per source
   - Update logging for comprehensive observability

2. **backend/app/storage/queries.py** (Phase 2)
   - Add methods to query/update source_performance table
   - Add source metrics aggregation queries

3. **backend/app/api/health.py** (Phase 3)
   - Extend health check to include all 6 sources
   - Add source performance summary

4. **frontend/components/watchlist/WatchlistTable.tsx** (Phase 4)
   - Add source indicator badge to each row
   - Color-code by priority/freshness
   - Show failover messages

5. **backend/tests/test_multi_source_failover.py** (Phase 5)
   - New test file for comprehensive failover scenarios

### Dependencies

- All 6 source adapter classes already exist and are tested (PRD #0011)
- `MultiSourceFetcher` class already implements priority-based failover
- `source_performance` table already exists in schema
- Frontend UI components (Badge, etc.) already available

---

## Success Metrics

1. **Reliability**: Reduce "!" alerts caused by missing data to <1% of tickers
2. **Coverage**: 95%+ of price fetch requests succeed (across all sources)
3. **Performance**: Average failover chain completes in <3 seconds
4. **Observability**: 100% of source attempts logged with metrics
5. **Load Distribution**:
   - YFinance handles 70-80% of requests (when healthy)
   - Backup sources handle 20-30% (when YFinance degraded)
6. **Data Quality**: 0% of watchlist snapshots with "missing_change_pct" errors after 24 hours

---

## Open Questions

1. **Q**: Should we add circuit breaker logic to temporarily skip consistently failing sources?
   - **A**: Out of scope for this PRD, but track metrics to enable this in future

2. **Q**: Should source priorities be dynamically adjusted based on performance metrics?
   - **A**: Out of scope, priorities remain fixed from YAML configs

3. **Q**: How should we handle sources with very low daily quotas (FMP: 250/day)?
   - **A**: Current rate limiting in `MultiSourceFetcher` already handles this

4. **Q**: Should we pre-warm the cache by fetching from multiple sources simultaneously?
   - **A**: Out of scope, continue with sequential failover

---

## Implementation Phases

### Phase 1: Core Integration (HIGH PRIORITY)
- **Effort**: 0.5-1 day
- **Files**: `price_fetcher.py`
- **Goal**: All 6 sources available for failover
- **Acceptance**: Can fetch prices using any of 6 sources based on availability

### Phase 2: Metrics & Profiling (HIGH PRIORITY)
- **Effort**: 0.5 day
- **Files**: `queries.py`, `price_fetcher.py`
- **Goal**: Track source performance in database
- **Acceptance**: Source metrics visible in `source_performance` table

### Phase 3: Health Checks (MEDIUM PRIORITY)
- **Effort**: 0.5 day
- **Files**: `health.py`
- **Goal**: Visibility into source health
- **Acceptance**: `/health` endpoint shows all 6 sources

### Phase 4: Frontend Indicators (LOW PRIORITY)
- **Effort**: 0.5 day
- **Files**: `WatchlistTable.tsx`
- **Goal**: User sees which source provided data
- **Acceptance**: UI shows source badges and failover messages

### Phase 5: Testing (CRITICAL)
- **Effort**: 1 day
- **Files**: All test files
- **Goal**: Comprehensive test coverage
- **Acceptance**: All tests pass following `/do_it` guidance

---

## Documentation Updates

After Phases 1-5 complete:

1. Update `docs/core/ARCHITECTURE.md`:
   - Document 6-source failover architecture
   - Add source priority decision tree
   - Include performance metrics strategy

2. Update `docs/core/OPERATIONS.md`:
   - Add source health monitoring runbook
   - Document API key configuration for each source
   - Add troubleshooting guide for source failures

3. Update `CLAUDE.md`:
   - Mark PRD #0011 as 100% complete (was 85%)
   - Update multi-source status
   - Document source priorities

4. Update `docs/core/REFACTOR_STATUS.md`:
   - Close PRD #0016 as complete
   - Update tech stack with confirmed 6-source setup

---

## Appendix: Source Comparison Matrix

| Source | Priority | API Key Required | Rate Limit | Best Use Case |
|--------|----------|------------------|------------|---------------|
| YFinance | 1 | ❌ No | 60/min | Primary, unlimited |
| TwelveData | 2 | ✅ Yes | 8/min, 800/day | Backup, good limits |
| FMP | 3 | ✅ Yes | 250/day | Tertiary, limited |
| Polygon | 4 | ✅ Yes | 5/min | Fallback |
| Finnhub | 5 | ✅ Yes | 60/min | Fallback |
| AlphaVantage | 6 | ✅ Yes | 5/min, 500/day | Last resort |

---

**Version**: 1.0
**Last Updated**: 2025-10-30
**Next Review**: After Phase 1 implementation
