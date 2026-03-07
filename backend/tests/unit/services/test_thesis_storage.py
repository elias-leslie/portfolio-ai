"""Unit tests for thesis storage normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.thesis import ThesisAction, ThesisStatus
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
