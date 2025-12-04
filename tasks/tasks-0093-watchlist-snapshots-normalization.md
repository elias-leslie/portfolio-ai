# Task List: Watchlist Snapshots Normalization

**Source**: /data_check analysis (2025-12-04) - Critical Issue #1
**Complexity**: Complex
**Effort**: HIGH (~6-8 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 15:45

---

## Summary

**Goal**: Split the massively denormalized `watchlist_snapshots` table (60+ columns) into focused, normalized tables
**Approach**: Create 4 separate tables, migrate data, update all queries and API endpoints
**Scope Discovery**: Required - need to find all code that reads/writes watchlist_snapshots

---

## Background

The `watchlist_snapshots` table conflates multiple concerns:
- Core snapshot data (item_id, fetched_at, price, score)
- Technical indicators (34 columns from migration 008)
- Narrative intelligence (headline, why_bullets, action_plan, etc.)
- News sentiment (news_sentiment_score, recent_news_headlines)
- Trade calculations (entry_price, stop_loss, profit_target, position_size)

This causes:
- 2-4KB per row (storage waste)
- Complex updates when only one aspect changes
- Stale data risk across unrelated fields
- Maintenance nightmare

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: `watchlist_snapshots` table usage across entire codebase
  - Find: ALL queries (SELECT, INSERT, UPDATE)
  - Find: ALL Pydantic models referencing this table
  - Find: ALL API endpoints that return snapshot data
- [ ] 0.2 Document current column usage
  - Group columns by logical domain (core, technical, narrative, news, trade)
  - Identify which columns are frequently accessed together
  - Note any computed columns that could be views
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD]
  - Queries to update: [TBD]
  - API endpoints to update: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Design New Schema

- [ ] 1.1 Design `watchlist_snapshots_core` table
  - Columns: id, item_id, fetched_at, price, change_pct, score, signal_type, signal_strength
  - Primary key: id
  - Index: (item_id, fetched_at DESC)
- [ ] 1.2 Design `watchlist_technical_snapshot` table
  - Columns: snapshot_id (FK), raw_metrics (JSONB), beta, volatility, percentile_rank_30d
  - Plus: volume_relative, timeframe_short_aligned, timeframe_long_aligned
- [ ] 1.3 Design `watchlist_narrative` table
  - Columns: snapshot_id (FK), narrative_headline, narrative_why_bullets, narrative_company_health
  - Plus: narrative_technical, narrative_action_plan, narrative_position_sizing, narrative_special_notes
  - Plus: entry_price, stop_loss, profit_target, position_size_shares
  - Plus: recommended_style, style_confidence, optimal_holding_period, risk_level, company_health
- [ ] 1.4 Design `watchlist_news_summary` table
  - Columns: snapshot_id (FK), news_sentiment_score, recent_news_headlines, news_intelligence (JSONB)
  - Plus: news_score, earnings_date, earnings_days_away
- [ ] 1.5 Create migration file with all 4 tables

### 2.0 Create Migration

- [ ] 2.1 Create migration 070_split_watchlist_snapshots.sql
  - Create 4 new tables with FKs to watchlist_snapshots_core
  - Add appropriate indexes
- [ ] 2.2 Create data migration script
  - Copy existing data to new tables
  - Preserve all historical snapshots
- [ ] 2.3 Test migration on copy of production data
- [ ] 2.4 Create rollback script (in case of issues)

### 3.0 Update Backend Code

- [ ] 3.1 Create new Pydantic models for each table
  - WatchlistSnapshotCore, TechnicalSnapshot, NarrativeSnapshot, NewsSummary
- [ ] 3.2 Update repository layer
  - New methods for each table
  - Composite query for full snapshot (JOIN all 4 tables)
- [ ] 3.3 Update Celery tasks that write snapshots
  - Modify to write to 4 tables instead of 1
- [ ] 3.4 Update API endpoints
  - Ensure responses still include all data (via JOINs)

### 4.0 Update Frontend (if needed)

- [ ] 4.1 Check if any frontend code assumes column structure
- [ ] 4.2 Update TypeScript types if API response changes
- [ ] 4.3 Test all watchlist-related pages

### 5.0 Cleanup

- [ ] 5.1 Add deprecation notice to old table
- [ ] 5.2 Create view for backwards compatibility (optional)
- [ ] 5.3 Plan future migration to drop old table

---

## Verification

- [ ] Functional: All watchlist features work as before
- [ ] Tests: All existing tests pass, add new tests for split tables
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] Services: Restarted and verified
- [ ] Performance: Query performance same or better
- [ ] Data: All historical snapshots preserved

---

## Notes

- This is a HIGH effort task - consider breaking into phases
- Phase 1: Create new tables, write to both old and new
- Phase 2: Migrate reads to new tables
- Phase 3: Deprecate and remove old table
- Keep old table as backup initially
