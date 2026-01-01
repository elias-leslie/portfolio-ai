# Holistic Automation Alignment

**Implements**: FEAT-220
**Status**: planned
**Effort**: HIGH
**Priority**: P4

## Context
Portfolio AI has 61 scheduled Celery tasks that run independently. This feature connects them into a coherent pipeline where:
- Watchlist scores trigger strategy generation for top symbols
- Strategy performance feeds back to influence watchlist scores
- Event-driven triggers replace time-based where sensible

The goal is to create a closed-loop system where AI outputs drive actions and results inform future analysis.

## 0.0 Scope Discovery (MANDATORY)
- [ ] Run 2-3 "very thorough" Explore agents on:
  - Celery schedules (`backend/app/celery_schedules.py`)
  - Watchlist scoring (`backend/app/services/watchlist_service.py`)
  - Strategy generation (`backend/app/tasks/strategy_tasks.py`)
  - Strategy monitoring (`backend/app/tasks/strategy_monitoring_tasks.py`)
- [ ] Document all files to modify with line ranges
- [ ] Map current task dependencies
- [ ] Identify opportunities for event-driven triggers

## Files to Modify
[Populated after scope discovery]
- backend/app/celery_schedules.py - Add trigger-based tasks
- backend/app/tasks/strategy_tasks.py - Auto-generate for top watchlist
- backend/app/services/watchlist_service.py - Include strategy performance in scoring
- backend/app/tasks/triggers.py (NEW) - Event-driven trigger handlers

## Current State: 61 Scheduled Tasks

**What's Working Well:**
- Strategy signals generated daily (21:30 UTC)
- Auto paper trading from BUY signals (21:45 UTC)
- Performance monitoring + archiving (04:00 UTC)
- Watchlist scoring (60s continuous)
- Fear & Greed index (3x daily)
- Discovery + Portfolio Analyzer agents run daily (03:30 UTC)

**Critical Gaps:**
| Gap | Impact | This Feature Fixes |
|-----|--------|-------------------|
| Watchlist → Strategies disconnected | High-scoring symbols don't auto-generate strategies | auto-001 |
| No feedback loop | Strategy performance doesn't influence watchlist | auto-002 |
| Time-based only | Systems don't react to events | auto-003 |

## Steps

### auto-001-watchlist-trigger: Auto-generate Strategies for Top Watchlist (MEDIUM)
**What**: Top 10 watchlist symbols automatically generate strategies if none exist
**Why**: Close the gap - watchlist identifies opportunities, strategies should follow
**How**:
- After watchlist scoring completes, check top 10 by composite score
- For each symbol without an active strategy, trigger `strategy_research_workflow()`
- Add rate limiting (max 3 new strategies per day to prevent overwhelm)
- Track which strategies were auto-generated vs user-requested
**Files**:
- `backend/app/tasks/watchlist_tasks.py` - add trigger after scoring
- `backend/app/tasks/strategy_tasks.py` - accept trigger from watchlist
**Verification**: New strategies appear for high-scoring watchlist symbols (no manual trigger)

### auto-002-feedback-loop: Strategy Performance Influences Watchlist Scores (MEDIUM)
**What**: Symbols with successful strategies get boosted in watchlist composite score
**Why**: Feedback loop - proven strategies validate the symbol quality
**How**:
- Add `performance_factor` to watchlist scoring pillars
- Calculate from: strategy win rate, Sharpe ratio, active status
- Weight: 10-15% of composite score
- Negative signals also affect score (underperforming strategies)
**Files**:
- `backend/app/services/watchlist_service.py` - add performance_factor pillar
- `backend/app/tasks/watchlist_tasks.py` - include strategy performance in scoring
**Verification**: Watchlist API shows `performance_factor` in score breakdown

### auto-003-event-driven: Add Event-Driven Triggers (HIGH)
**What**: Replace time-based with event-driven triggers where sensible
**Why**: React to events (earnings, price moves) not just clock time
**How**:
- Create `backend/app/tasks/triggers.py` with event handlers
- Events to support:
  - `strategy_performance_updated` → re-score affected watchlist symbol
  - `seed_created` (confidence >= 7) → trigger strategy workflow
  - `earnings_released` → re-run Discovery Agent for symbol
  - `price_alert_triggered` → re-evaluate strategies for symbol
- Use Celery signals or explicit task chaining
- Preserve time-based for things that must run on schedule (market open/close)
**Files**:
- `backend/app/tasks/triggers.py` (NEW) - event handlers
- `backend/app/celery_schedules.py` - reduce redundant time-based tasks
**Verification**: journalctl shows trigger cascade after strategy performance update

## Verification
- [ ] ac-001: Check that new strategies appear for high-scoring watchlist symbols (no manual trigger)
- [ ] ac-002: Watchlist API shows performance_factor in score breakdown
- [ ] ac-003: journalctl shows trigger cascade after strategy performance update

## Rollback
If issues occur: `git reset --hard HEAD~1`

## Dependencies
- FEAT-218 (Strategy Seed Pipeline) - Must be working first
- Existing 61 scheduled tasks
