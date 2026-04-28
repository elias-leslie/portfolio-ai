from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from app.constants import PREDICTION_TARGET_SYMBOLS
from app.services import data_freshness_service


def test_trigger_remediation_uses_backfill_workflow_for_technical_indicators(
    monkeypatch,
) -> None:
    fake_admin = Mock()
    fake_admin.run_workflow.return_value = SimpleNamespace(workflow_run_id="run-123")

    data_freshness_service._remediation_cooldowns.clear()
    monkeypatch.setattr("app.services.data_freshness_service.get_admin_client", lambda: fake_admin)
    monkeypatch.setattr("app.services.data_freshness_service.is_market_open", lambda _: True)

    task_id = data_freshness_service.trigger_remediation(
        table_name="technical_indicators",
        age_hours=52.0,
        is_market_data=True,
    )

    assert task_id == "run-123"
    fake_admin.run_workflow.assert_called_once_with("portfolio-backfill-indicators", "{}")


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
    assert result["age_hours"] == 23.07


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

    assert config_by_table["fear_greed_inputs"]["availability_delay_hours"] == 6.5
    assert "vix_close IS NOT NULL" in config_by_table["fear_greed_inputs"]["where_clause"]
    assert config_by_table["fear_greed_daily"]["availability_delay_hours"] == 6.5
    assert config_by_table["fear_greed_components"]["availability_delay_hours"] == 6.5
    assert config_by_table["technical_indicators"]["availability_delay_hours"] == 6.5
    assert config_by_table["options_market_metrics"]["date_column"] == "source_timestamp"
    assert config_by_table["reference_cache"]["date_column"] == "created_at"
    assert config_by_table["reference_cache"]["where_clause"] == "source = 'yfinance'"


def test_decision_symbol_day_bars_freshness_marks_missing_symbol_critical(monkeypatch) -> None:
    rows = [
        {"symbol": symbol, "last_update": dt.date(2026, 4, 27)}
        for symbol in PREDICTION_TARGET_SYMBOLS
    ]
    rows.append({"symbol": "VTI", "last_update": None})
    monkeypatch.setattr(
        data_freshness_service,
        "_fetch_decision_symbol_rows",
        lambda _storage: rows,
    )

    result = data_freshness_service.check_decision_symbol_day_bars_freshness(
        Mock(),
        dt.datetime(2026, 4, 28, 13, 0, tzinfo=dt.UTC),
    )

    assert result["is_stale"] is True
    assert result["is_critical"] is True
    assert result["reason"] == "missing_symbols"
    assert result["missing_symbols"] == ["VTI"]
    assert result["expected_date"] == "2026-04-27"


def test_check_all_tables_freshness_includes_decision_symbol_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        data_freshness_service,
        "TABLE_FRESHNESS_CONFIG",
        [
            {
                "table_name": "day_bars",
                "date_column": "date",
                "expected_hours": 24,
                "critical_hours": 48,
                "market_data": True,
            }
        ],
    )
    monkeypatch.setattr(
        data_freshness_service,
        "_check_one_table",
        lambda *_args, **_kwargs: (
            {
                "table_name": "day_bars",
                "last_update": "2026-04-27T16:00:00-04:00",
                "age_hours": 12.0,
                "is_stale": False,
                "is_critical": False,
                "reason": None,
            },
            0,
            0,
        ),
    )
    monkeypatch.setattr(
        data_freshness_service,
        "check_decision_symbol_day_bars_freshness",
        lambda *_args, **_kwargs: {
            "table_name": "decision_symbol_day_bars",
            "last_update": "2026-03-23",
            "age_hours": 600.0,
            "is_stale": True,
            "is_critical": True,
            "reason": "critical_symbols",
            "symbols_checked": 13,
            "missing_symbols": [],
            "stale_symbols": ["SPY"],
            "critical_symbols": ["SPY"],
        },
    )
    monkeypatch.setattr(data_freshness_service, "_handle_critical_result", lambda *_args, **_kwargs: 0)

    result = data_freshness_service.check_all_tables_freshness(Mock(), auto_remediate=False)

    assert result["tables_checked"] == 2
    assert result["fresh"] == 1
    assert result["stale"] == 1
    assert result["critical"] == 1
    details = result["details"]
    assert isinstance(details, list)
    decision_detail = details[-1]
    assert isinstance(decision_detail, dict)
    assert decision_detail["table_name"] == "decision_symbol_day_bars"
