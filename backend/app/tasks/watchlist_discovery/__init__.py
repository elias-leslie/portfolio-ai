"""Watchlist Discovery and Trimming Module.

Automated watchlist management:
1. Discovery: Find high-potential symbols from top gainers, volume spikes, news mentions
2. Trimming: Remove underperforming symbols after minimum hold period
3. Reporting: Generate daily reports of watchlist changes

Scheduled via Celery Beat:
- discover_watchlist_candidates: Daily 08:00 UTC
- trim_underperforming_watchlist: Daily 08:30 UTC
- generate_daily_watchlist_report: Daily 09:00 UTC
"""

from app.tasks.watchlist_discovery.discovery import (
    discover_watchlist_candidates_task,
)
from app.tasks.watchlist_discovery.reporting import (
    generate_daily_watchlist_report_task,
)
from app.tasks.watchlist_discovery.trimming import (
    trim_underperforming_watchlist_task,
)

__all__ = [
    "discover_watchlist_candidates_task",
    "generate_daily_watchlist_report_task",
    "trim_underperforming_watchlist_task",
]
