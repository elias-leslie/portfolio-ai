from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from app.tasks.data_freshness_tasks import check_all_data_freshness


def test_check_all_data_freshness_persists_table_details(monkeypatch) -> None:
    recorded_completion: dict[str, object] = {}
    details = [
        {
            "table_name": "news_cache",
            "last_update": "2026-04-10T20:30:00+00:00",
            "age_hours": 1.5,
            "is_stale": False,
            "is_critical": False,
            "reason": None,
        },
        {
            "table_name": "reference_cache",
            "last_update": "2026-04-09T20:30:00+00:00",
            "age_hours": 25.0,
            "is_stale": True,
            "is_critical": False,
            "reason": None,
        },
    ]
    fake_connection_manager = MagicMock()

    def fake_get_connection_manager() -> MagicMock:
        return fake_connection_manager

    def fake_record_maintenance_start(**_kwargs) -> int:
        return 123

    def fake_record_maintenance_completion(**kwargs) -> None:
        recorded_completion.update(kwargs)

    def fake_check_all_tables_freshness(*_args, **_kwargs) -> dict[str, object]:
        return {
            "tables_checked": 2,
            "fresh": 1,
            "stale": 1,
            "critical": 0,
            "alerts_created": 0,
            "remediations_triggered": 0,
            "details": details,
        }

    monkeypatch.setattr(
        "app.tasks.data_freshness_tasks.get_connection_manager",
        fake_get_connection_manager,
    )
    monkeypatch.setattr(
        "app.tasks.data_freshness_tasks.record_maintenance_start",
        fake_record_maintenance_start,
    )
    monkeypatch.setattr(
        "app.tasks.data_freshness_tasks.record_maintenance_completion",
        fake_record_maintenance_completion,
    )
    monkeypatch.setattr(
        "app.tasks.data_freshness_tasks.check_all_tables_freshness",
        fake_check_all_tables_freshness,
    )

    result = cast(dict[str, Any], check_all_data_freshness(auto_remediate=False))
    summary = recorded_completion["summary"]

    assert result["details"] == details
    assert recorded_completion["status"] == "success"
    assert isinstance(summary, dict)
    assert summary["details"] == details
