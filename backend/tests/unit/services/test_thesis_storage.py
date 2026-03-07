"""Unit tests for thesis storage normalization."""

from __future__ import annotations

import pytest

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
