"""Fear & Greed Index service.

Queries the fear_greed_daily table for the latest Fear & Greed Index score.
The score is computed by Celery tasks and stored in the database.

See ARCHITECTURE.md lines 475-671 for complete specification.
"""

from __future__ import annotations

from datetime import datetime

from app.storage import get_storage


class FearGreedReading:
    """Fear & Greed Index reading."""

    def __init__(
        self,
        score: int,
        label: str,
        score_change: float | None = None,
        signal_count: int = 4,
    ):
        self.score = score
        self.label = label
        self.score_change = score_change
        self.signal_count = signal_count
        self.date = datetime.utcnow().isoformat()


def get_fear_greed_score() -> FearGreedReading:
    """Get current Fear & Greed Index score from database.

    Queries the fear_greed_daily table for the most recent score.
    Falls back to neutral (50) if no data is available.

    Returns:
        FearGreedReading with score, label, and metadata
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
                return FearGreedReading(
                    score=int(row[0]),
                    label=row[1],
                    score_change=float(row[2]) if row[2] is not None else 0.0,
                    signal_count=int(row[3]) if row[3] is not None else 4,
                )
    except Exception:
        # Fall through to default if query fails
        pass

    # Fallback: Return neutral score if no data available
    return FearGreedReading(
        score=50,
        label="Neutral",
        score_change=0.0,
        signal_count=4,
    )
