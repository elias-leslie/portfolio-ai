"""Options market context calculations.

Provides historical context for options metrics:
- Put/Call ratio trends
- Percentile rankings
- Time-based comparisons
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Literal, TypedDict

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


class PutCallContext(TypedDict):
    """Historical context for Put/Call ratio."""

    trend: Literal["up", "down", "flat"]
    trend_pct: float
    percentile_rank: int


def calculate_putcall_context(
    current_ratio: float,
    as_of_date: dt.date,
    storage: PortfolioStorage,
) -> PutCallContext:
    """Calculate historical context for Put/Call ratio.

    Args:
        current_ratio: Current put/call ratio value
        as_of_date: Date of current ratio
        storage: Database storage for historical queries

    Returns:
        Dict with context:
        {
            "trend": "up" | "down" | "flat",
            "trend_pct": 12.3,  # % change over 7 days
            "percentile_rank": 78  # Where current sits in 90-day distribution
        }
    """
    with storage.connection() as conn:
        # Get 7-day ago ratio for trend calculation
        result_7d = conn.execute(
            """
            SELECT put_call_ratio
            FROM fear_greed_inputs
            WHERE as_of_date = %s AND put_call_ratio IS NOT NULL
            """,
            [(as_of_date - dt.timedelta(days=7)).isoformat()],
        ).fetchone()

        ratio_7d_ago = result_7d[0] if result_7d else None

        # Get 90-day historical ratios for percentile calculation
        result_90d = conn.execute(
            """
            SELECT put_call_ratio
            FROM fear_greed_inputs
            WHERE as_of_date >= %s
              AND as_of_date <= %s
              AND put_call_ratio IS NOT NULL
            ORDER BY put_call_ratio ASC
            """,
            [
                (as_of_date - dt.timedelta(days=90)).isoformat(),
                as_of_date.isoformat(),
            ],
        ).fetchall()

        historical_ratios = [row[0] for row in result_90d]

    # Calculate 7-day trend
    trend: Literal["up", "down", "flat"]
    if ratio_7d_ago and ratio_7d_ago > 0:
        trend_pct = ((current_ratio - ratio_7d_ago) / ratio_7d_ago) * 100

        if abs(trend_pct) < 2.0:  # Less than 2% change is "flat"
            trend = "flat"
        elif trend_pct > 0:
            trend = "up"  # Increasing put/call = more defensive
        else:
            trend = "down"  # Decreasing put/call = less defensive
    else:
        trend = "flat"
        trend_pct = 0.0

    # Calculate percentile rank
    if historical_ratios and len(historical_ratios) >= 10:  # Need minimum data
        # Count how many historical values are below current
        below_count = sum(1 for r in historical_ratios if r < current_ratio)
        percentile_rank = int((below_count / len(historical_ratios)) * 100)
    else:
        percentile_rank = 50  # Default to median if insufficient data

    logger.info(
        "putcall_context_calculated",
        current_ratio=current_ratio,
        trend=trend,
        trend_pct=round(trend_pct, 2),
        percentile_rank=percentile_rank,
        historical_samples=len(historical_ratios),
    )

    return {
        "trend": trend,
        "trend_pct": round(trend_pct, 2),
        "percentile_rank": percentile_rank,
    }
