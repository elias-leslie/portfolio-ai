from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

from app.services.automation_center_service import AutomationCenterService


def _fake_storage(*, jenny_rows: list[tuple], maintenance_rows: list[tuple], failure_rows: list[tuple], stale_rows: list[tuple]):
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(fetchall=MagicMock(return_value=jenny_rows)),
        MagicMock(fetchall=MagicMock(return_value=maintenance_rows)),
        MagicMock(fetchall=MagicMock(return_value=failure_rows)),
        MagicMock(fetchall=MagicMock(return_value=stale_rows)),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = MagicMock()
    fake_storage.connection.side_effect = fake_connection
    return fake_storage


def test_recent_runs_collapse_duplicate_maintenance_errors() -> None:
    service = AutomationCenterService()
    service.storage = _fake_storage(
        jenny_rows=[],
        maintenance_rows=[
            (3, "check_all_data_freshness", "error", datetime(2026, 4, 8, 22, 0, tzinfo=UTC), datetime(2026, 4, 8, 22, 1, tzinfo=UTC)),
            (2, "check_all_data_freshness", "error", datetime(2026, 4, 8, 20, 0, tzinfo=UTC), datetime(2026, 4, 8, 20, 1, tzinfo=UTC)),
            (1, "check_all_data_freshness", "error", datetime(2026, 4, 8, 18, 0, tzinfo=UTC), datetime(2026, 4, 8, 18, 1, tzinfo=UTC)),
        ],
        failure_rows=[],
        stale_rows=[],
    )

    runs = service._recent_runs()

    assert len(runs) == 1
    assert runs[0].label == "check all data freshness"
    assert "Repeated 3 times in recent runs." in runs[0].detail


def test_recent_runs_use_failure_summary_for_failed_jenny_runs() -> None:
    service = AutomationCenterService()
    service.storage = _fake_storage(
        jenny_rows=[
            (
                "routine-1",
                "daily_operator",
                "failed",
                "scheduled",
                datetime(2026, 4, 8, 22, 0, tzinfo=UTC),
                datetime(2026, 4, 8, 22, 1, tzinfo=UTC),
                0,
                0,
                "Jenny routine failed: timed out fetching intelligence.",
            ),
        ],
        maintenance_rows=[],
        failure_rows=[],
        stale_rows=[],
    )

    runs = service._recent_runs()

    assert len(runs) == 1
    assert runs[0].detail == "Jenny routine failed: timed out fetching intelligence."


def test_center_exposes_background_agent_guardrails(monkeypatch) -> None:
    service = AutomationCenterService()
    service.storage = _fake_storage(
        jenny_rows=[],
        maintenance_rows=[],
        failure_rows=[],
        stale_rows=[],
    )
    monkeypatch.setattr(
        "app.services.automation_center_service.get_or_create_preferences",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.services.automation_center_service.get_automation_preferences",
        lambda _prefs=None: {
            "thesis_generation_enabled": {"enabled": False, "source": "preferences"},
            "auto_remove_on_invalidation": {"enabled": True, "source": "rules_default"},
            "auto_trim_enabled": {"enabled": True, "source": "rules_default"},
            "scheduled_jenny_operator_enabled": {"enabled": False, "source": "rules_default"},
            "scheduled_ml_labeling_enabled": {"enabled": False, "source": "rules_default"},
            "scheduled_strategy_research_enabled": {"enabled": False, "source": "rules_default"},
        },
    )

    center = service.get_center()
    raw_guardrails = cast(list[dict[str, object]], center["guardrails"])
    guardrails = {str(item["key"]): item for item in raw_guardrails}

    assert guardrails["scheduled_jenny_operator_enabled"]["enabled"] is False
    assert guardrails["scheduled_ml_labeling_enabled"]["enabled"] is False
    assert guardrails["scheduled_strategy_research_enabled"]["enabled"] is False


def test_warnings_dedupe_repeated_failures() -> None:
    service = AutomationCenterService()
    fake_conn = MagicMock()
    fake_conn.execute.side_effect = [
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    ("data_freshness_alert_news_cache", "error"),
                    ("check_all_data_freshness", "error"),
                    ("data_freshness_alert_news_cache", "error"),
                ]
            )
        ),
        MagicMock(
            fetchall=MagicMock(
                return_value=[
                    ("cleanup_debug_captures", datetime(2026, 3, 11, 6, 15, tzinfo=UTC)),
                ]
            )
        ),
    ]

    @contextmanager
    def fake_connection():
        yield fake_conn

    service.storage = MagicMock()
    service.storage.connection.side_effect = fake_connection

    warnings = service._warnings()

    assert warnings == [
        "data freshness alert news cache reported error. Repeated 2 times.",
        "check all data freshness reported error.",
        "cleanup debug captures has been running since 2026-03-11T06:15:00+00:00.",
    ]
