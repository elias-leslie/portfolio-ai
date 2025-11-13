"""Fear & Greed Index service.

Queries the fear_greed_daily table for the latest Fear & Greed Index score.
The score is computed by Celery tasks and stored in the database.

See ARCHITECTURE.md lines 475-671 for complete specification.
"""

from __future__ import annotations

import datetime as dt

from app.storage import get_storage


class FearGreedReading:
    """Fear & Greed Index reading with staleness tracking."""

    def __init__(
        self,
        score: int,
        label: str,
        score_change: float | None = None,
        signal_count: int = 4,
        is_stale: bool = False,
        age_days: int = 0,
    ):
        self.score = score
        self.label = label
        self.score_change = score_change
        self.signal_count = signal_count
        self.is_stale = is_stale
        self.age_days = age_days
        self.date = dt.datetime.now(dt.UTC).isoformat()


def get_fear_greed_score() -> FearGreedReading:
    """Get current Fear & Greed Index score from database with staleness tracking.

    Queries the fear_greed_daily table for the most recent score.
    Falls back to neutral (50) if no data is available.

    Data is considered stale if >2 days old (trading days, not calendar days).

    Returns:
        FearGreedReading with score, label, staleness info, and metadata
    """
    storage = get_storage()

    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT score, label, score_change, signal_count, as_of_date
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            row = result.fetchone()

            if row:
                # Calculate age in days
                as_of_date = row[4]  # as_of_date column
                today = dt.date.today()
                age_days = (today - as_of_date).days

                # Flag as stale if >2 days old
                is_stale = age_days > 2

                return FearGreedReading(
                    score=int(row[0]),
                    label=row[1],
                    score_change=float(row[2]) if row[2] is not None else 0.0,
                    signal_count=int(row[3]) if row[3] is not None else 4,
                    is_stale=is_stale,
                    age_days=age_days,
                )
    except Exception:
        # Fall through to default if query fails
        pass

    # Fallback: Return neutral score if no data available
    # Mark as stale since we have no real data
    return FearGreedReading(
        score=50,
        label="Neutral",
        score_change=0.0,
        signal_count=4,
        is_stale=True,
        age_days=999,  # Large number to indicate no data
    )
