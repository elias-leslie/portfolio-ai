# Task List: Data Redundancy Fixes

**Source**: /data_check analysis (2025-12-04) - High Priority Issues #3, #7, #8
**Complexity**: Simple (3 independent MEDIUM effort fixes)
**Effort**: MEDIUM (~3-4 hours total)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 15:45

---

## Summary

**Goal**: Reduce data redundancy by consolidating reference_cache, removing price duplication, and standardizing news sentiment storage
**Approach**: Refactor each redundancy independently, update queries to use single source of truth
**Scope Discovery**: Required for each issue

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent for reference_cache usage
  - Find: ALL queries reading/writing reference_cache
  - Find: Which columns are actually used
  - Goal: Understand current access patterns
- [ ] 0.2 Run Explore subagent for price data locations
  - Tables: day_bars, price_cache, watchlist_snapshots
  - Find: Which queries read price from each location
  - Goal: Identify single source of truth candidates
- [ ] 0.3 Run Explore subagent for news sentiment
  - Tables: news_cache, news_summary_log, watchlist_snapshots
  - Find: Where sentiment is stored vs calculated
  - Goal: Identify redundant storage
- [ ] 0.4 Checkpoint: Confirm scope
  - reference_cache queries: [TBD]
  - price data queries: [TBD]
  - news sentiment queries: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Refactor reference_cache (30+ columns → domain tables)

**Issue**: Single table mixing valuation, health scores, and fundamental metrics
**Files**:
- `backend/migrations/041_valuation_metrics.sql` (7 valuation columns)
- `backend/migrations/066_financial_health_scores.sql` (4 health columns)
- `backend/migrations/068_fundamental_data_tables.sql` (7 fundamental columns)

- [ ] 1.1 Create `valuation_metrics` table
  - Columns: symbol, as_of_date, pe_ratio_trailing, pe_ratio_forward, ps_ratio, pb_ratio, peg_ratio, dividend_yield, payout_ratio
  - Index: (symbol, as_of_date DESC)
- [ ] 1.2 Create `financial_health` table
  - Columns: symbol, as_of_date, f_score, f_score_components (JSONB), z_score, z_score_zone
  - Index: (symbol, as_of_date DESC)
- [ ] 1.3 Keep reference_cache for core data only
  - Retain: symbol, company_name, sector, industry, exchange, market_cap
  - Remove: valuation and health columns (after migration)
- [ ] 1.4 Create migration to split data
- [ ] 1.5 Update queries to use new tables

### 2.0 Consolidate Price Data Storage

**Issue**: Price stored in 3+ locations (day_bars, price_cache, watchlist_snapshots)
**Goal**: Single source of truth with cache layer

- [ ] 2.1 Analyze current price access patterns
  - day_bars: Historical OHLCV (keep as-is)
  - price_cache: Latest snapshot (keep for real-time)
  - watchlist_snapshots: Denormalized copy (remove)
- [ ] 2.2 Update watchlist_snapshots to reference day_bars
  - Remove: price, change_pct, beta, volatility columns
  - Add: latest_bar_id (FK to day_bars) OR calculate on demand
- [ ] 2.3 Update queries to JOIN day_bars for price
- [ ] 2.4 Verify no price staleness issues

### 3.0 Standardize News Sentiment Storage

**Issue**: Sentiment stored in 3 tables (news_cache, news_summary_log, watchlist_snapshots)

- [ ] 3.1 Analyze sentiment usage patterns
  - news_cache.sentiment_score: Per-article sentiment (keep)
  - news_summary_log: Aggregated window (keep for historical trends)
  - watchlist_snapshots.news_sentiment_score: Denormalized copy (remove)
- [ ] 3.2 Update watchlist to calculate sentiment on demand
  - Query news_cache for recent articles
  - Aggregate sentiment in real-time OR from news_summary_log
- [ ] 3.3 Remove redundant columns from watchlist_snapshots
- [ ] 3.4 Update API to return calculated sentiment

---

## Verification

- [ ] Functional: All features work with new data structure
- [ ] Tests: All existing tests pass
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] Services: Restarted and verified
- [ ] Performance: No degradation from additional JOINs
- [ ] Data: No data loss during migration

---

## Notes

- Task 1 (reference_cache) is independent
- Tasks 2 and 3 depend on watchlist_snapshots normalization (tasks-0093)
- Consider implementing Task 1 first, then 2 and 3 after tasks-0093 completes
- All changes should be backwards compatible initially
