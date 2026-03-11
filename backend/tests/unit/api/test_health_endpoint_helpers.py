from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.health import get_recent_remediations


@pytest.mark.asyncio
async def test_get_recent_remediations_dedupes_tables_and_counts_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = [
        (
            "data_freshness_alert_technical_indicators",
            datetime(2026, 3, 11, 0, 0, tzinfo=UTC),
            "error",
            {
                "age_hours": 52.0,
                "threshold_hours": 48.0,
                "reason": "age",
            },
            "latest failure",
        ),
        (
            "data_freshness_alert_technical_indicators",
            datetime(2026, 3, 10, 22, 0, tzinfo=UTC),
            "error",
            {
                "age_hours": 50.0,
                "threshold_hours": 48.0,
                "reason": "age",
            },
            "older failure",
        ),
        (
            "data_freshness_alert_fear_greed_daily",
            datetime(2026, 3, 10, 21, 0, tzinfo=UTC),
            "error",
            {
                "age_hours": 52.0,
                "threshold_hours": 48.0,
                "reason": "age",
            },
            "another failure",
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    remediations = await get_recent_remediations()

    assert [event["table_name"] for event in remediations] == [
        "technical_indicators",
        "fear_greed_daily",
    ]
    assert remediations[0]["triggered_at"] == "2026-03-11T00:00:00+00:00"
    assert remediations[0]["occurrence_count"] == 2
    assert remediations[0]["error_message"] == "latest failure"
    assert remediations[1]["occurrence_count"] == 1
