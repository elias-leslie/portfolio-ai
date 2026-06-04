from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from app.services import data_freshness_service
from app.utils.market_hours import NY_TZ


def test_trigger_remediation_uses_backfill_workflow_for_technical_indicators(
    monkeypatch,
) -> None:
    fake_admin = Mock()
    fake_admin.run_workflow.return_value = SimpleNamespace(workflow_run_id="run-123")

    data_freshness_service._remediation_cooldowns.clear()
    monkeypatch.setattr("app.services.data_freshness_service.get_admin_client", lambda: fake_admin)
    monkeypatch.setattr("app.services.data_freshness_service.record_maintenance_start", lambda **_: 101)
    monkeypatch.setattr(
        "app.services.data_freshness_service.record_maintenance_completion",
        lambda **_: None,
    )

    task_id = data_freshness_service.trigger_remediation(
        table_name="technical_indicators",
        age_hours=52.0,
        is_market_data=True,
    )

    assert task_id == "run-123"
    fake_admin.run_workflow.assert_called_once_with("portfolio-backfill-indicators", "{}")


def test_trigger_remediation_records_workflow_run_id(monkeypatch) -> None:
    fake_admin = Mock()
    fake_admin.run_workflow.return_value = SimpleNamespace(workflow_run_id="run-456")
    completions: list[dict[str, object]] = []

    data_freshness_service._remediation_cooldowns.clear()
    monkeypatch.setattr("app.services.data_freshness_service.get_admin_client", lambda: fake_admin)
    monkeypatch.setattr("app.services.data_freshness_service.record_maintenance_start", lambda **_: 101)
    monkeypatch.setattr(
        "app.services.data_freshness_service.record_maintenance_completion",
        lambda **_: None,
    )
    monkeypatch.setattr("app.services.data_freshness_service.record_maintenance_start", lambda **_: 101)
    monkeypatch.setattr(
        "app.services.data_freshness_service.record_maintenance_completion",
        lambda **kwargs: completions.append(kwargs),
    )

    task_id = data_freshness_service.trigger_remediation(
        table_name="symbol_risk_metrics",
        age_hours=200.0,
        is_market_data=False,
    )

    assert task_id == "run-456"
    assert completions == [
        {
            "log_id": 101,
            "status": "success",
            "summary": {
                "table_name": "symbol_risk_metrics",
                "age_hours": 200.0,
                "remediation_task_name": "portfolio-risk-metrics",
                "workflow_run_id": "run-456",
                "trigger_status": "triggered",
            },
            "error_message": None,
        }
    ]


def test_trigger_remediation_uses_reference_workflow_for_risk_metrics(monkeypatch) -> None:
    fake_admin = Mock()
    fake_admin.run_workflow.return_value = SimpleNamespace(workflow_run_id="run-risk")

    data_freshness_service._remediation_cooldowns.clear()
    monkeypatch.setattr("app.services.data_freshness_service.get_admin_client", lambda: fake_admin)

    task_id = data_freshness_service.trigger_remediation(
        table_name="symbol_risk_metrics",
        age_hours=200.0,
        is_market_data=False,
    )

    assert task_id == "run-risk"
    fake_admin.run_workflow.assert_called_once_with("portfolio-risk-metrics", "{}")


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

    assert result["is_stale"] is False
    assert result["is_critical"] is False
    assert result["age_hours"] == 5.57


def test_check_table_freshness_respects_fear_greed_post_close_delay() -> None:
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
        "availability_delay_hours": 6.5,
    }
    now = dt.datetime(2026, 3, 11, 1, 34, tzinfo=dt.UTC)

    result = data_freshness_service.check_table_freshness(fake_storage, config, now)

    assert result["is_stale"] is False
    assert result["is_critical"] is False
    assert result["age_hours"] == 0.0


def test_check_table_freshness_uses_indicator_date_for_staleness(monkeypatch) -> None:
    fake_conn = Mock()
    fake_conn.execute.return_value.fetchone.return_value = (dt.date(2026, 3, 9),)

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "technical_indicators",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "availability_delay_hours": 6.5,
    }

    before_due = dt.datetime(2026, 3, 11, 1, 45, tzinfo=dt.UTC)
    before_due_result = data_freshness_service.check_table_freshness(fake_storage, config, before_due)

    assert before_due_result["age_hours"] == 0.0
    assert before_due_result["is_stale"] is False
    assert before_due_result["is_critical"] is False

    after_due = dt.datetime(2026, 3, 12, 3, 0, tzinfo=dt.UTC)
    after_due_result = data_freshness_service.check_table_freshness(fake_storage, config, after_due)

    assert after_due_result["age_hours"] == 24.5
    assert after_due_result["is_stale"] is True
    assert after_due_result["is_critical"] is False

    executed_query = fake_conn.execute.call_args[0][0]
    assert "MAX(date)" in executed_query
    assert "calculated_at" not in executed_query
    assert "date <= DATE '2026-03-11'" in executed_query


def test_check_table_freshness_marks_missing_required_symbol_coverage() -> None:
    fake_conn = Mock()
    freshness_cursor = Mock()
    freshness_cursor.fetchone.return_value = (dt.date(2026, 5, 1),)
    coverage_cursor = Mock()
    coverage_cursor.fetchone.return_value = (2, 1, None, ["NVDA"])
    fake_conn.execute.side_effect = [freshness_cursor, coverage_cursor]

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "day_bars",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
        "required_symbols_query": "SELECT symbol FROM watchlist_items",
    }

    result = data_freshness_service.check_table_freshness(
        fake_storage,
        config,
        dt.datetime(2026, 5, 4, 16, 0, tzinfo=dt.UTC),
    )

    assert result["is_stale"] is True
    assert result["is_critical"] is False
    assert result["reason"] == "symbol_coverage"
    assert result["coverage"] == {
        "required_symbols": 2,
        "current_symbols": 1,
        "expected_date": "2026-05-01",
        "stale_symbols": ["NVDA"],
        "missing_symbols": [],
        "stale_symbol_count": 1,
    }


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
            "required_symbols_query": config.get("required_symbols_query"),
            "where_clause": config.get("where_clause"),
        }
        for config in data_freshness_service.TABLE_FRESHNESS_CONFIG
    }

    assert config_by_table["day_bars"]["required_symbols_query"]
    assert config_by_table["fear_greed_inputs"]["availability_delay_hours"] == 6.5
    assert "vix_close IS NOT NULL" in config_by_table["fear_greed_inputs"]["where_clause"]
    assert config_by_table["fear_greed_daily"]["availability_delay_hours"] == 6.5
    assert config_by_table["fear_greed_components"]["availability_delay_hours"] == 6.5
    assert config_by_table["technical_indicators"]["date_column"] == "date"
    assert config_by_table["technical_indicators"]["availability_delay_hours"] == 6.5
    assert config_by_table["technical_indicators"]["required_symbols_query"]
    assert config_by_table["options_market_metrics"]["date_column"] == "source_timestamp"
    assert config_by_table["news_cache"]["date_column"] == "fetched_at"
    assert config_by_table["reference_cache"]["date_column"] == "created_at"
    assert config_by_table["reference_cache"]["where_clause"] == "source = 'yfinance'"
    assert config_by_table["cash_flow_metrics"]["date_column"] == "updated_at"
    assert config_by_table["financial_health_scores"]["date_column"] == "updated_at"
    assert config_by_table["symbol_risk_metrics"]["date_column"] == "as_of_date"


def test_check_table_freshness_flags_intraday_quote_stale_during_market_hours() -> None:
    fake_conn = Mock()
    # quote_time 90 min before "now", both inside the regular session.
    fake_conn.execute.return_value.fetchone.return_value = (
        dt.datetime(2026, 3, 11, 12, 30, tzinfo=NY_TZ),
    )

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "price_cache",
        "date_column": "quote_time",
        "expected_hours": 0.5,
        "critical_hours": 1.0,
        "market_data": True,
        "intraday": True,
        "where_clause": "UPPER(symbol) = '^VIX' AND quote_time IS NOT NULL",
    }
    now = dt.datetime(2026, 3, 11, 14, 0, tzinfo=NY_TZ)  # Wed, market open

    result = data_freshness_service.check_table_freshness(fake_storage, config, now)

    assert result["age_hours"] == 1.5
    assert result["is_stale"] is True
    assert result["is_critical"] is True
    executed_query = fake_conn.execute.call_args[0][0]
    assert "MAX(quote_time)" in executed_query
    assert "UPPER(symbol) = '^VIX'" in executed_query


def test_check_table_freshness_keeps_intraday_quote_fresh_after_close() -> None:
    fake_conn = Mock()
    # Same-day quote stamped at the session; market is now closed for the day.
    fake_conn.execute.return_value.fetchone.return_value = (
        dt.datetime(2026, 3, 11, 13, 0, tzinfo=NY_TZ),
    )

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "price_cache",
        "date_column": "quote_time",
        "expected_hours": 0.5,
        "critical_hours": 1.0,
        "market_data": True,
        "intraday": True,
        "where_clause": "UPPER(symbol) = '^VIX' AND quote_time IS NOT NULL",
    }
    now = dt.datetime(2026, 3, 11, 18, 0, tzinfo=NY_TZ)  # after the 4pm ET close

    result = data_freshness_service.check_table_freshness(fake_storage, config, now)

    assert result["age_hours"] == 0.0
    assert result["is_stale"] is False
    assert result["is_critical"] is False


def test_check_table_freshness_intraday_absent_quote_warns_only_during_session() -> None:
    fake_conn = Mock()
    fake_conn.execute.return_value.fetchone.return_value = (None,)

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_storage = Mock()
    fake_storage.connection.side_effect = fake_connection

    config = {
        "table_name": "price_cache",
        "date_column": "quote_time",
        "expected_hours": 0.5,
        "critical_hours": 1.0,
        "market_data": True,
        "intraday": True,
        "where_clause": "UPPER(symbol) = '^VIX' AND quote_time IS NOT NULL",
    }

    open_result = data_freshness_service.check_table_freshness(
        fake_storage, config, dt.datetime(2026, 3, 11, 14, 0, tzinfo=NY_TZ)
    )
    assert open_result["is_stale"] is True
    assert open_result["is_critical"] is False
    assert open_result["reason"] == "no_live_quote"

    closed_result = data_freshness_service.check_table_freshness(
        fake_storage, config, dt.datetime(2026, 3, 11, 18, 0, tzinfo=NY_TZ)
    )
    assert closed_result["is_stale"] is False
    assert closed_result["is_critical"] is False
    assert closed_result["reason"] is None


def test_shared_remediation_workflow_runs_once_per_freshness_pass(monkeypatch) -> None:
    calls: list[str] = []

    def fake_trigger_remediation(table_name: str, age_hours: float | None, is_market_data: bool) -> str:
        calls.append(table_name)
        return f"run-{table_name}"

    monkeypatch.setattr(data_freshness_service, "trigger_remediation", fake_trigger_remediation)
    triggered_task_names: set[str] = set()

    triggered = sum(
        data_freshness_service._trigger_remediation_once(
            config={
                "table_name": table_name,
                "date_column": "as_of_date",
                "expected_hours": 24,
                "critical_hours": 48,
                "market_data": True,
            },
            age_hours=52.0,
            triggered_task_names=triggered_task_names,
        )
        for table_name in ("fear_greed_inputs", "fear_greed_daily", "fear_greed_components")
    )

    assert triggered == 1
    assert calls == ["fear_greed_inputs"]
