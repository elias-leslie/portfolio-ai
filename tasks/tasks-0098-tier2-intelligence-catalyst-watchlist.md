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

### 0.0 Scope Discovery for Watchlist Automation (MANDATORY)

- [ ] 0.1 Research available discovery data sources
  - Top gainers: Which API provides this? (yfinance? twelvedata?)
  - Volume spikes: How to detect 2x average volume?
  - News mentions: Can we count headlines per ticker?
  - Sector rotation: Do we have sector momentum data?
- [ ] 0.2 Document existing watchlist infrastructure
  - Current tables: watchlist_items, watchlist_snapshots
  - Current tasks: refresh_watchlist_scores, refresh_watchlist_ohlcv
  - Agent tools: execute_add_ticker, execute_remove_ticker (exist but not scheduled)
- [ ] 0.3 Checkpoint: Confirm approach
  - Discovery sources available: [TBD]
  - Trimming criteria feasible: [TBD]
  - Estimated integration effort: [TBD]

**DO NOT PROCEED TO TASK 2 UNTIL SCOPE CONFIRMED**

---

### 1.0 Complete Catalyst Detection System (Section 2.1)

**Current State**: 24 event categories detected, impact summaries generated, no scoring

- [ ] 1.1 Define catalyst impact scoring config
  - Add to rules.yaml (or create catalyst_impacts.yaml):
  ```yaml
  catalyst_impacts:
    regulatory:
      fda_approval: { impact: +3.0, duration_days: 5 }
      fda_rejection: { impact: -4.0, duration_days: 3 }
      sec_investigation: { impact: -2.5, duration_days: 7 }
    earnings:
      earnings_beat: { impact: +1.5, duration_days: 2 }
      earnings_miss: { impact: -2.0, duration_days: 2 }
      beat_and_raise: { impact: +2.5, duration_days: 3 }
      miss_and_lower: { impact: -3.5, duration_days: 3 }
    corporate:
      acquisition_announced: { impact: +1.5, duration_days: 5 }
      ceo_departure: { impact: -1.0, duration_days: 3 }
      major_contract: { impact: +1.5, duration_days: 3 }
      layoffs: { impact: -0.5, duration_days: 2 }
  ```
- [ ] 1.2 Create catalyst impact calculator
  - New function: calculate_catalyst_impact(event_category, event_date)
  - Apply time decay: impact * (1 - days_since_event / duration_days)
  - Return 0 if event expired
- [ ] 1.3 Add catalyst_impact to NewsArticle model
  - Edit news_models.py NewsArticle
  - Add fields: catalyst_impact_score, catalyst_expires_at
- [ ] 1.4 Integrate catalyst into watchlist scoring
  - Edit watchlist/scoring.py or signal_classifier.py
  - Add catalyst_score component (weight: 0.20 per trading_requirements.yaml)
  - Formula: overall = price*0.35 + technical*0.25 + fundamental*0.20 + catalyst*0.20
- [ ] 1.5 Update priority indicators
  - Edit watchlist/priority.py
  - Add positive catalyst check (not just negative)
  - Show catalyst type and expiration in indicator
- [ ] 1.6 Test catalyst scoring
  - Create test news with FDA_APPROVAL event
  - Verify score increases by expected amount
  - Verify decay over duration_days

---

### 2.0 Implement Watchlist Discovery (Section 2.2)

- [ ] 2.1 Create discovery scanner module
  - New file: backend/app/tasks/watchlist_discovery.py
  - Discovery sources:
    - top_gainers: Tickers with >5% daily gain
    - top_volume: Tickers with >2x average volume
    - news_mentions: Tickers with >3 headlines today
- [ ] 2.2 Create discovery scoring function
  - Combine signals: discovery_score = gainers_boost + volume_boost + news_boost
  - Threshold: Only consider if discovery_score > 6.0
- [ ] 2.3 Create auto-add logic
  - Check if ticker already in watchlist
  - Check if watchlist at max size (50)
  - Add with metadata: source="discovery", discovery_score, discovery_date
- [ ] 2.4 Create Celery task: discover_watchlist_candidates
  - Schedule: Daily 04:00 UTC
  - Process: Scan sources → Score → Add qualifying tickers
  - Limit: Max 5 additions per day
- [ ] 2.5 Test discovery automation
  - Manually trigger task
  - Verify qualifying tickers added
  - Verify metadata populated

---

### 3.0 Implement Watchlist Trimming (Section 2.2)

- [ ] 3.1 Define trimming rules
  - Add to rules.yaml:
  ```yaml
  watchlist_management:
    max_watchlist_size: 50
    auto_remove:
      enabled: true
      min_days_watched: 7
      min_score_threshold: 4.0
      exclude_portfolio_holdings: true
  ```
- [ ] 3.2 Create trim candidates function
  - Query watchlist_items joined with latest snapshot scores
  - Filter: age >= min_days_watched AND avg_score < threshold
  - Exclude: Tickers in portfolio_positions
- [ ] 3.3 Create auto-remove logic
  - Remove ticker from watchlist_items
  - Log removal: ticker, reason, final_score, days_watched
- [ ] 3.4 Create Celery task: trim_underperforming_watchlist
  - Schedule: Daily 04:30 UTC (after discovery)
  - Process: Find underperformers → Validate exclusions → Remove
  - Limit: Max 3 removals per day (prevent mass deletion)
- [ ] 3.5 Test trimming automation
  - Add test ticker with low score, age > 7 days
  - Trigger trim task
  - Verify ticker removed

---

### 4.0 Daily Watchlist Report (Optional)

- [ ] 4.1 Create daily summary generator
  - Report: Tickers added, removed, score changes
  - Format: Markdown for logging or notification
- [ ] 4.2 Schedule report generation
  - Daily 05:00 UTC (after discovery + trim)
  - Store in watchlist_daily_reports table or log

---

### 5.0 Agent Telemetry Dashboard (From Second Pass)

**Current State**: Backend API complete, frontend missing

- [ ] 5.1 Create /agents page
  - New file: frontend/app/agents/page.tsx
  - Import existing telemetry types from frontend/lib/api/
- [ ] 5.2 Add telemetry summary card
  - Total runs, success rate, avg duration
  - Provider breakdown (Gemini vs Claude)
  - Use existing endpoint: GET /api/agents/telemetry/summary
- [ ] 5.3 Add run history table
  - Paginated list of agent runs
  - Filterable by provider, status, agent_type
  - Use existing endpoint: GET /api/agents/telemetry/history
- [ ] 5.4 Add token usage chart
  - Daily trend of input/output tokens
  - Use existing endpoint daily_data from summary
- [ ] 5.5 Add agent performance metrics
  - Win rate, avg return for each agent type
  - Use existing endpoint: GET /api/ideas/agents/performance/summary

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
