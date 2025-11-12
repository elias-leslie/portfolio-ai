"""Fear & Greed Index stub service.

IMPORTANT: This is a STUB implementation for cloud agent development.
The local agent must implement the full Fear & Greed calculation based on ARCHITECTURE.md.

Real implementation should:
1. Fetch VIX from FRED (VIXCLS indicator)
2. Fetch HY Spread from FRED (BAMLH0A0HYM2 indicator)
3. Fetch SPY price, SMA_200, RSI_14 from local database
4. Calculate percentile rankings for each signal (252-day window)
5. Compute composite score: equal-weighted average
6. Map to label (Extreme Fear → Fear → Neutral → Greed → Extreme Greed)

See ARCHITECTURE.md lines 475-671 for complete specification.
"""

from __future__ import annotations

from datetime import datetime


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
    """Get current Fear & Greed Index score.

    STUB IMPLEMENTATION - Returns mock neutral score.
    Local agent must implement real calculation from database.

    Returns:
        FearGreedReading with score, label, and metadata
    """
    # TODO (LOCAL AGENT): Implement real Fear & Greed calculation
    # 1. Query fear_greed_daily table for latest score
    # 2. If no recent data, trigger computation via Celery task
    # 3. Return actual score with components

    # STUB: Return neutral score for now
    return FearGreedReading(
        score=50,
        label="Neutral",
        score_change=0.0,
        signal_count=4,
    )
