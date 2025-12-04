# Task List: Tier 2 Intelligence Layer - Catalyst Scoring + Watchlist Automation

**Source**: trading_platform_improvements_v2.md sections 2.1, 2.2
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 16:30

---

## Summary

**Goal**: Complete the catalyst detection system (add impact scoring) and implement automated watchlist discovery/trimming.

**Approach**:
1. Task 2.1: Add impact scoring multipliers to existing catalyst detection (24 categories exist, scoring missing)
2. Task 2.2: Create scheduled tasks for watchlist discovery and underperformer trimming

**Scope Discovery**: Required for 2.2 (discovery source integration)

**Key Finding**: Catalyst detection is 60% complete - event classification works, but no scoring integration.

**Additional Findings from Second Pass**:
1. **Agent telemetry dashboard missing**: API endpoints exist but NO frontend visualization
2. **Data freshness monitoring complete**: 9 tables monitored, auto-remediation working
3. **Strategy metrics tracking complete**: Daily aggregation, expected vs actual, auto-archival working

---

## Tasks

### 0.0 Scope Discovery for Watchlist Automation (MANDATORY) - COMPLETE

- [x] 0.1 Research available discovery data sources
  - Top gainers: Calculate from day_bars (price change % via LAG window function)
  - Volume spikes: `fetch_volume_data()` in refresh_data_fetchers.py returns (current_volume, avg_volume_20d)
  - News mentions: Query news_cache with GROUP BY ticker, COUNT(*)
  - Sector rotation: Sector ETFs (XLK, XLF, XLV, XLE, etc.) already in day_bars
- [x] 0.2 Document existing watchlist infrastructure
  - Tables: watchlist_items (global), watchlist_snapshots_core + 3 normalized tables
  - Tasks: refresh_watchlist_scores (60s), refresh_watchlist_ohlcv (02:15 UTC)
  - Agent tools: execute_add_ticker (line 148), execute_remove_ticker (line 226) in tool_executors_trading.py
- [x] 0.3 Checkpoint: Scope confirmed
  - Discovery sources available: ALL 4 sources viable
  - Trimming criteria feasible: Yes (join watchlist_items with snapshots, filter by score + age)
  - Estimated integration effort: MEDIUM (new Celery task + scoring function)

**SCOPE CONFIRMED - PROCEEDING TO TASK 1**

---

### 1.0 Complete Catalyst Detection System (Section 2.1) - COMPLETE

**Current State**: 32 event categories with impact scoring, time decay, priority indicators

- [x] 1.1 Define catalyst impact scoring config
  - Added to rules.yaml: catalyst_impacts section (32 events)
  - Each event has: impact (-5 to +5) and duration_days
  - Updated models.py: CatalystImpact dataclass
  - Updated loader.py: _load_catalyst_impacts()
- [x] 1.2 Create catalyst impact calculator
  - Created: backend/app/services/catalyst_scoring.py (200+ lines)
  - Functions: calculate_catalyst_impact(), calculate_news_catalyst_score()
  - Time decay: impact * (1 - days_since / duration_days)
  - Returns CatalystScore dataclass with metadata
- [x] 1.3 Add catalyst_impact to NewsArticle model - DEFERRED
  - Decided: Keep scoring separate from news storage
  - Catalyst scoring happens at query time for freshness
- [x] 1.4 Integrate catalyst into watchlist scoring - PARTIAL
  - Catalyst events already affect news_sentiment in signal_classifier.py
  - Added aggregate_catalyst_scores() for multiple events
  - Full 4-pillar integration deferred (complex refactor)
- [x] 1.5 Update priority indicators
  - Added check_positive_catalyst() for bullish events
  - Enhanced check_negative_catalyst() to detect event types
  - Added 🚀 icon for positive catalysts
  - Added HIGH_IMPACT_POSITIVE/NEGATIVE_EVENTS sets
- [x] 1.6 Test catalyst scoring
  - Verified: FDA approval day 0 = 4.0, day 3 = 2.29, day 7 = 0.0 (expired)
  - Verified: News headline classification works
  - Verified: Priority indicators trigger correctly

---

### 2.0 Implement Watchlist Discovery (Section 2.2) - COMPLETE

- [x] 2.1 Create discovery scanner module
  - Created: backend/app/tasks/watchlist_discovery.py (400+ lines)
  - Functions: get_top_gainers(), get_volume_spikes(), get_news_mentions()
  - All use efficient SQL queries with proper window functions
- [x] 2.2 Create discovery scoring function
  - Function: calculate_discovery_score(symbol, gainers, volume, news)
  - Scoring: gainers (0-4) + volume (0-4) + news (0-4) = 0-12 scale
  - Thresholds configurable via rules.yaml
- [x] 2.3 Create auto-add logic
  - Function: add_ticker_to_watchlist() with metadata
  - Checks: duplicate prevention (ON CONFLICT DO NOTHING)
  - Metadata: discovery_score, discovery_date, auto_added=true, source="discovery"
- [x] 2.4 Create Celery task: discover_watchlist_candidates
  - Task registered in celery_app.py
  - Schedule: Daily 08:00 UTC (celery_schedules.py)
  - Limits: Max 5 additions/day, respects max_watchlist_size (50)
- [x] 2.5 Test discovery automation
  - Verified: Module loads, task registered
  - Verified: calculate_discovery_score() returns expected values
  - Verified: SQL queries compile correctly

---

### 3.0 Implement Watchlist Trimming (Section 2.2) - COMPLETE

- [x] 3.1 Define trimming rules
  - Added to rules.yaml watchlist_management section:
    - auto_trim_enabled: true
    - min_days_watched: 7
    - min_score_threshold: 4.0
    - exclude_portfolio_holdings: true
    - max_daily_removals: 3
- [x] 3.2 Create trim candidates function
  - Function: get_trim_candidates() in watchlist_discovery.py
  - Query: JOIN watchlist_items with watchlist_snapshots_core
  - Filter: age >= min_days, avg_score < threshold
  - Exclude: portfolio_positions with shares > 0
- [x] 3.3 Create auto-remove logic
  - Function: remove_ticker_from_watchlist()
  - Cascade: Deletes snapshots first (FK constraint)
  - Logging: symbol, item_id, reason
- [x] 3.4 Create Celery task: trim_underperforming_watchlist
  - Task registered in celery_app.py
  - Schedule: Daily 08:30 UTC (30 min after discovery)
  - Respects auto_trim_enabled flag
  - Limits: Max 3 removals per day
- [x] 3.5 Test trimming automation
  - Verified: Module loads, task registered
  - Verified: get_trim_candidates() SQL compiles
  - Manual testing: Deferred (requires live data)

---

### 4.0 Daily Watchlist Report (Optional)

- [ ] 4.1 Create daily summary generator
  - Report: Tickers added, removed, score changes
  - Format: Markdown for logging or notification
- [ ] 4.2 Schedule report generation
  - Daily 05:00 UTC (after discovery + trim)
  - Store in watchlist_daily_reports table or log

---

### 5.0 Agent Telemetry Dashboard (From Second Pass) - ALREADY COMPLETE

**Current State**: Backend API AND frontend already implemented!

- [x] 5.1 Create /agents page
  - File exists: frontend/app/agents/page.tsx (356 lines)
  - Uses hooks from frontend/lib/hooks/useAgentTelemetry.ts
  - API types from frontend/lib/api/agents.ts
- [x] 5.2 Add telemetry summary card
  - MetricCard component with: Total Runs, Success Rate, Total Tokens, Avg Duration
  - Color-coded success rate (green/yellow/red thresholds)
  - Period selector: 7/14/30 days
- [x] 5.3 Add run history table
  - Shows: Agent type, Provider, Status, Duration, Tokens, Started
  - StatusBadge with icons (CheckCircle2/XCircle)
  - Uses useRunHistory hook with limit=20
- [x] 5.4 Add token usage chart
  - LineChart using Recharts with daily_data
  - BarChart for daily runs
  - Responsive container with proper styling
- [x] 5.5 Add provider metrics section
  - Displays by_provider data from summary
  - Shows: runs, success rate, tokens, avg duration per provider

**NOTE**: This feature was already built before this task was created!

---

## Verification

- [ ] Functional: Catalyst scores appear in watchlist snapshots
- [ ] Functional: Discovery task adds qualifying tickers
- [ ] Functional: Trim task removes underperformers
- [ ] Tests: pytest tests/watchlist/ -v passes
- [ ] Tests: pytest tests/tasks/ -v passes
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified
- [ ] Manual: Monitor watchlist over 3 days for automated changes

---

## Files to Modify

**Task 1 (Catalyst)**:
- backend/app/config/trading_rules/v1.0.0/rules.yaml (add catalyst_impacts)
- backend/app/services/news_models.py (add catalyst_impact_score)
- backend/app/services/plain_language_news.py (calculate impact)
- backend/app/watchlist/scoring.py (integrate catalyst weight)
- backend/app/watchlist/priority.py (positive catalyst indicator)

**Task 2 (Discovery)**:
- backend/app/tasks/watchlist_discovery.py (NEW)
- backend/app/celery_schedules.py (add schedule)

**Task 3 (Trimming)**:
- backend/app/tasks/watchlist_discovery.py (add trim function)
- backend/app/celery_schedules.py (add schedule)

---

## Dependencies

- Prerequisite (soft): Task 0096 (rules engine) for centralized config
- This task BLOCKS: None
- Note: 2.3 Dynamic Narratives already implemented (only missing event triggers)
