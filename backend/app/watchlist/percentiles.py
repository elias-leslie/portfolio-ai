"""Percentile rank calculation for watchlist scores."""

from __future__ import annotations


def calculate_percentile_rank(
    current_score: float,
    historical_scores: list[float],
) -> float:
    """Calculate percentile rank of current score vs historical scores.

    Args:
        current_score: Today's overall score
        historical_scores: List of scores from last 30 days

    Returns:
        Percentile rank 0-100 (e.g., 85.0 = top 15%)
    """
    if not historical_scores:
        return 50.0  # Default to median if no history

    # Count how many historical scores are below current
    below_count = sum(1 for score in historical_scores if score < current_score)

    # Percentile = (count below / total count) * 100
    percentile = (below_count / len(historical_scores)) * 100.0

    return percentile
