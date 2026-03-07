"""Unit tests for thesis storage normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.thesis import Thesis, ThesisAction, ThesisStatus
from app.services.thesis.thesis_storage import ThesisStorageManager


@pytest.mark.parametrize(
    ("raw_reason", "expected"),
    [
        ("created", "created"),
        ("Generated new thesis", "created"),
        ("updated", "updated"),
        ("Invalidated: price broke thesis", "invalidated"),
    ],
)
def test_normalize_change_reason_maps_runtime_labels(raw_reason: str, expected: str) -> None:
    """Runtime thesis labels should be coerced to valid schema values."""
    storage = object.__new__(ThesisStorageManager)

    assert storage._normalize_change_reason(raw_reason) == expected


def test_normalize_change_reason_rejects_unknown_values() -> None:
    """Unexpected change reasons should fail fast before hitting the database."""
    storage = object.__new__(ThesisStorageManager)

    with pytest.raises(ValueError, match="Unsupported thesis version change reason"):
        storage._normalize_change_reason("manual note")


def test_row_to_thesis_stringifies_uuid_primary_key() -> None:
    """Database UUID values should be rehydrated into the string-backed Thesis model."""
    storage = object.__new__(ThesisStorageManager)
    thesis_id = uuid4()
    now = datetime.now(UTC)

    thesis = storage._row_to_thesis(
        (
            thesis_id,
            "AAPL",
            2,
            ThesisStatus.ACTIVE.value,
            ThesisAction.BUY.value,
            [],
            [],
            [],
            None,
            18.5,
            90,
            None,
            None,
            0.81,
            None,
            None,
            now,
            now,
        )
    )

    assert thesis.id == str(thesis_id)
    assert thesis.symbol == "AAPL"
    assert thesis.status is ThesisStatus.ACTIVE
    assert thesis.action is ThesisAction.BUY


def test_save_version_uses_upsert_for_duplicate_thesis_versions(mocker) -> None:
    """Saving the same thesis/version again should update the snapshot instead of failing."""
    conn = mocker.Mock()
    conn_mgr = mocker.MagicMock()
    conn_mgr.connection.return_value.__enter__.return_value = conn
    storage = object.__new__(ThesisStorageManager)
    storage._conn_mgr = conn_mgr

    thesis = Thesis(
        id="thesis-1",
        symbol="AAPL",
        version=5,
        status=ThesisStatus.ACTIVE,
        action=ThesisAction.BUY,
        core_reasons=[],
        key_catalysts=[],
        risks=[],
        value_drivers=None,
        expected_return_pct=12.5,
        expected_timeframe_days=60,
        claude_validation=None,
        gemini_validation=None,
        cross_validation_score=0.7,
        invalidation_reason=None,
        invalidated_at=None,
        created_at="2026-03-07T16:00:00+00:00",
        updated_at="2026-03-07T16:00:00+00:00",
    )

    storage.save_version(thesis, "updated")

    executed_sql = conn.execute.call_args.args[0]
    assert "ON CONFLICT (thesis_id, version) DO UPDATE SET" in executed_sql
    conn.commit.assert_called_once()
