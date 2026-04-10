"""Unit tests for thesis invalidation trigger helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.thesis import Thesis, ThesisAction, ThesisStatus
from app.services.thesis.thesis_triggers import check_cross_val_trigger


def _thesis(*, hours_old: float, cross_validation_score: float | None) -> Thesis:
    created_at = (datetime.now(UTC) - timedelta(hours=hours_old)).isoformat()
    return Thesis(
        id="thesis-1",
        symbol="NVDA",
        version=1,
        status=ThesisStatus.ACTIVE,
        action=ThesisAction.BUY,
        cross_validation_score=cross_validation_score,
        created_at=created_at,
        updated_at=created_at,
    )


def test_check_cross_val_trigger_flags_recent_low_score() -> None:
    thesis = _thesis(hours_old=2, cross_validation_score=0.32)

    assert check_cross_val_trigger(thesis) == ["Low cross-validation score: 0.32"]


def test_check_cross_val_trigger_ignores_stale_low_score() -> None:
    thesis = _thesis(hours_old=72, cross_validation_score=0.32)

    assert check_cross_val_trigger(thesis) == []
