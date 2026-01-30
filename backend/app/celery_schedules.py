"""Celery Beat periodic task schedules.

This module contains all periodic task definitions for Celery Beat.
Extracted from celery_app.py to improve maintainability and readability.

REFRESH ARCHITECTURE:
---------------------
Backend refresh (expensive API calls): Controlled by user preferences
  - Global default: default_refresh_minutes (15 min default)
  - Per-feature overrides: watchlist_refresh_override, portfolio_refresh_override, news_refresh_override
  - Tasks check preference hierarchy: override → default → hardcoded fallback

Frontend polling (cheap DB reads): Fixed at 30 seconds for responsiveness
  - Controlled by frontend_poll_interval in user_preferences (default: 30s)
  - Independent of backend refresh schedule

PERIODIC TASK TYPES:
--------------------
1. User-Configurable Backend Refresh (respects preferences)
   - Watchlist scores: polls every 60s, honors user's refresh_interval
   - Portfolio analytics: (future) polls every 60s, honors user's refresh_interval
   - News sentiment: (future) polls every 60s, honors user's refresh_interval

2. Static Schedules (not configurable)
   - Paper trades update: Daily at 4:30 PM ET (market close + 30 min)
   - Data cleanup: Weekly on Sunday 2:00 AM

DESIGN RATIONALE:
-----------------
Why separate polling (60s) from execution (15+ min)?
  - Beat is cheap (schedule check only)
  - Task execution is expensive (DB queries, API calls)
  - Decoupling allows dynamic adjustment without Beat restart
  - Task can decide to skip execution based on runtime conditions

PREVIOUSLY DISABLED TASKS (now fixed):
--------------------------------------
  - fetch-putcall-ratio: Was disabled due to CBOE HTTP 403 blocks.
    Fixed 2025-12-01: Now uses yfinance options chains (SPY+QQQ+IWM aggregate).
    See backend/app/tasks/market_data/options_pipeline.py for implementation.

REMOVED TASKS (migrated elsewhere):
-----------------------------------
  - AI analyzer and gap detection: Migrated to [DEBT] subtasks on features.
    See tasks/tasks-tech-debt-to-feature-subtasks-migration.md
  - Daily gap analysis workflow: Migrated to feature-based tracking.

MARKET HOURS AWARENESS:
-----------------------
The system is market-hours aware to prevent thrashing on weekends/holidays:

1. Data Freshness Monitoring (data_freshness_service.py):
   - Uses market-aware age calculation for market_data tables
   - On weekends, data from Friday is considered "fresh" (not stale)
   - Skips remediation alerts for market data when market is closed

2. Remediation Thrashing Protection:
   - Cooldown period: 30 minutes between remediation attempts per table
   - Market check: Won't trigger market data remediation when market closed
   - Cooldowns clear on successful data refresh

3. Holiday Calendar:
   - Full NYSE/NASDAQ holiday support (2024-2026)
   - Early close days (1 PM close) handled separately
   - See app/utils/market_hours.py for complete calendar

4. API Endpoint:
   - GET /api/market/status - Returns current market status, last/next trading days
   - Used by frontend MarketStatusBadge component in navigation
"""

from typing import Any

from app.celery_schedules_modules import get_beat_schedule as _get_beat_schedule

__all__ = ["get_beat_schedule"]


def get_beat_schedule() -> dict[str, dict[str, Any]]:
    """Get Celery Beat schedule configuration.

    Merges all categorized task modules into a single beat schedule.
    See individual modules under app.celery_schedules_modules.* for task details.

    Returns:
        dict: Beat schedule with all periodic tasks
    """
    return _get_beat_schedule()
