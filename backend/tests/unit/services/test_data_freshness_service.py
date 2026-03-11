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


def test_check_table_freshness_respects_post_close_availability_delay(monkeypatch) -> None:
    fake_conn = Mock()
    fake_conn.execute.return_value.fetchone.return_value = (
        dt.datetime(2026, 3, 10, 2, 30, tzinfo=dt.UTC),
    )

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "technical_indicators",
        "date_column": "calculated_at",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
    }

    before_due = dt.datetime(2026, 3, 11, 1, 45, tzinfo=dt.UTC)
    before_due_result = data_freshness_service.check_table_freshness(fake_storage, config, before_due)

    assert before_due_result["age_hours"] == 23.25
    assert before_due_result["is_stale"] is False
    assert before_due_result["is_critical"] is False

    after_due = dt.datetime(2026, 3, 11, 3, 0, tzinfo=dt.UTC)
    after_due_result = data_freshness_service.check_table_freshness(fake_storage, config, after_due)

    assert after_due_result["age_hours"] == 24.5
    assert after_due_result["is_stale"] is True
    assert after_due_result["is_critical"] is False


def test_check_table_freshness_applies_where_clause_for_shared_table() -> None:
    fake_conn = Mock()
    fake_conn.execute.return_value.fetchone.return_value = (
        dt.datetime(2026, 3, 10, 4, 2, tzinfo=dt.UTC),
    )

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "reference_cache",
        "date_column": "created_at",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": False,
        "where_clause": "source = 'yfinance'",
    }

    data_freshness_service.check_table_freshness(
        fake_storage,
        config,
        dt.datetime(2026, 3, 11, 1, 0, tzinfo=dt.UTC),
    )

    executed_query = fake_conn.execute.call_args[0][0]
    assert "MAX(created_at)" in executed_query
    assert "FROM reference_cache" in executed_query
    assert "WHERE source = 'yfinance'" in executed_query


def test_table_freshness_config_uses_live_options_and_reference_columns() -> None:
    config_by_table = {
        config["table_name"]: {
            "date_column": config["date_column"],
            "availability_delay_hours": config.get("availability_delay_hours"),
            "where_clause": config.get("where_clause"),
        }
        for config in data_freshness_service.TABLE_FRESHNESS_CONFIG
    }

    assert config_by_table["technical_indicators"]["availability_delay_hours"] == 6.5
    assert config_by_table["options_market_metrics"]["date_column"] == "source_timestamp"
    assert config_by_table["reference_cache"]["date_column"] == "created_at"
    assert config_by_table["reference_cache"]["where_clause"] == "source = 'yfinance'"
