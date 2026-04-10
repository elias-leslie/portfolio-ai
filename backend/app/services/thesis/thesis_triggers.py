"""Thesis invalidation trigger checks and related constants."""

from __future__ import annotations

from datetime import UTC, datetime

from ...models.thesis import Thesis, ThesisStatus

# Thresholds
THESIS_RECENCY_HOURS = 24
CROSS_VAL_SCORE_THRESHOLD = 0.5
SENTIMENT_SHIFT_THRESHOLD = 0.3

# Signal type constants
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_AVOID = "AVOID"


def is_thesis_recent(thesis: Thesis) -> bool:
    """Return True if thesis was created less than THESIS_RECENCY_HOURS ago."""
    created = datetime.fromisoformat(thesis.created_at)
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age_hours = (datetime.now(UTC) - created).total_seconds() / 3600
    return age_hours < THESIS_RECENCY_HOURS


def apply_invalidation(thesis: Thesis, reason: str) -> None:
    """Mutate thesis in-place to mark it as invalidated."""
    now = datetime.now(UTC).isoformat()
    thesis.status = ThesisStatus.INVALIDATED
    thesis.invalidation_reason = reason
    thesis.invalidated_at = now
    thesis.updated_at = now
    thesis.version += 1


def check_signal_triggers(thesis_action: str, current_signal: str | None) -> list[str]:
    """Return trigger reasons if signal type changed significantly."""
    if current_signal == SIGNAL_AVOID and thesis_action == SIGNAL_BUY:
        return ["Signal changed from BUY to AVOID"]
    if current_signal == SIGNAL_SELL and thesis_action == SIGNAL_BUY:
        return ["Signal changed from BUY to SELL"]
    if current_signal == SIGNAL_BUY and thesis_action == SIGNAL_SELL:
        return ["Signal changed from SELL to BUY"]
    return []


def check_sentiment_triggers(thesis_action: str, sentiment_score: float | None) -> list[str]:
    """Return trigger reasons if news sentiment shifted significantly."""
    if sentiment_score is None:
        return []
    if thesis_action == SIGNAL_BUY and sentiment_score < -SENTIMENT_SHIFT_THRESHOLD:
        return [f"Negative news sentiment: {sentiment_score:.2f}"]
    if thesis_action == SIGNAL_SELL and sentiment_score > SENTIMENT_SHIFT_THRESHOLD:
        return [f"Positive news sentiment: {sentiment_score:.2f}"]
    return []


def check_cross_val_trigger(thesis: Thesis) -> list[str]:
    """Return trigger reason if cross-validation score is below threshold."""
    score = thesis.cross_validation_score
    if score is not None and score < CROSS_VAL_SCORE_THRESHOLD and is_thesis_recent(thesis):
        return [f"Low cross-validation score: {score:.2f}"]
    return []
