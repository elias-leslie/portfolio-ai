from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from app.services import data_freshness_service


def test_trigger_remediation_uses_backfill_workflow_for_technical_indicators(
    monkeypatch,
) -> None:
    fake_admin = Mock()
    fake_admin.run_workflow.return_value = SimpleNamespace(workflow_run_id="run-123")

    data_freshness_service._remediation_cooldowns.clear()
    monkeypatch.setattr("app.services.data_freshness_service.get_admin_client", lambda: fake_admin)
    monkeypatch.setattr("app.services.data_freshness_service.is_trading_day", lambda _: True)

    task_id = data_freshness_service.trigger_remediation(
        table_name="technical_indicators",
        age_hours=52.0,
        is_market_data=True,
    )

    assert task_id == "run-123"
    fake_admin.run_workflow.assert_called_once_with("portfolio-backfill-indicators", {})


def test_check_table_freshness_treats_market_dates_as_close_time(monkeypatch) -> None:
    fake_conn = Mock()
    fake_conn.execute.return_value.fetchone.return_value = (dt.date(2026, 3, 9),)

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "fear_greed_daily",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    }
    now = dt.datetime(2026, 3, 11, 1, 34, tzinfo=dt.UTC)

    result = data_freshness_service.check_table_freshness(fake_storage, config, now)

    assert result["is_stale"] is True
    assert result["is_critical"] is False
    assert result["age_hours"] == 29.57
