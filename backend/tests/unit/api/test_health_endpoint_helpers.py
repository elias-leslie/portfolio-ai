from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.health import get_recent_remediations, get_stale_maintenance_runs


@pytest.mark.asyncio
async def test_get_recent_remediations_dedupes_tables_and_counts_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
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
            )
        ),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    {
                        "fresh": 9,
                        "stale": 0,
                        "critical": 0,
                    },
                    datetime(2026, 3, 11, 1, 0, tzinfo=UTC),
                    "success",
                )
            )
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
    assert remediations[0]["resolved"] is True
    assert remediations[0]["resolved_at"] == "2026-03-11T01:00:00+00:00"
    assert remediations[1]["occurrence_count"] == 1
    assert remediations[1]["resolved"] is True


@pytest.mark.asyncio
async def test_get_recent_remediations_keeps_active_failures_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    (
                        "data_freshness_alert_reference_cache",
                        datetime(2026, 3, 11, 2, 0, tzinfo=UTC),
                        "error",
                        {
                            "age_hours": 30.0,
                            "threshold_hours": 24.0,
                            "reason": "age",
                        },
                        "still stale",
                    ),
                ]
            )
        ),
        MagicMock(
            fetchone=MagicMock(
                return_value=(
                    {
                        "fresh": 8,
                        "stale": 1,
                        "critical": 0,
                    },
                    datetime(2026, 3, 11, 3, 0, tzinfo=UTC),
                    "success",
                )
            )
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    remediations = await get_recent_remediations()

    assert remediations[0]["table_name"] == "reference_cache"
    assert remediations[0]["resolved"] is False
    assert remediations[0]["resolved_at"] is None


@pytest.mark.asyncio
async def test_get_stale_maintenance_runs_returns_old_running_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = [
        (
            "cleanup_debug_captures",
            datetime(2026, 3, 11, 2, 15, tzinfo=UTC),
            False,
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    stale_runs = await get_stale_maintenance_runs()

    assert stale_runs == [
        {
            "task_name": "cleanup_debug_captures",
            "started_at": "2026-03-11T02:15:00+00:00",
            "dry_run": False,
        }
    ]


@pytest.mark.asyncio
async def test_get_data_freshness_summary_returns_no_data_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchone.return_value = None

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection

    monkeypatch.setattr("app.api.health.get_storage", lambda: fake_storage)

    from app.api.health import get_data_freshness_summary

    summary = await get_data_freshness_summary()

    assert summary == {
        "last_check": None,
        "status": "no_data",
        "message": "No freshness checks have been run yet",
    }


def test_build_deletion_rate_message_uses_threshold_bands() -> None:
    from app.api.health import _build_deletion_rate_message

    assert _build_deletion_rate_message(0, 1) == ("ok", "✅ OK: 0 deletions in last 1h")
    assert _build_deletion_rate_message(10, 4) == (
        "warning",
        "⚠️  WARNING: 10 deletions in last 4h (threshold: 10)",
    )
    assert _build_deletion_rate_message(100, 2) == (
        "critical",
        "🔴 CRITICAL: 100 deletions in last 2h (threshold: 100)",
    )
