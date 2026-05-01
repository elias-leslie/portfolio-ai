from __future__ import annotations

from datetime import date

from app.constants import ALL_MARKET_SYMBOLS, DEFAULT_DAILY_REFRESH_DAYS, PREDICTION_DRIVER_SYMBOLS
from app.tasks.ingestion import price_ingestion
from app.tasks.market_data import historical_ohlcv_pipeline


class _FakeConnection:
    def __init__(self, row: tuple[object, ...] | None = None, rows: list[tuple[object, ...]] | None = None) -> None:
        self.row = row
        self.rows = rows or []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, *_args: object) -> _FakeConnection:
        return self

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class _FakeStorage:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    def connection(self) -> _FakeConnection:
        return self._connection


def test_daily_ohlcv_refresh_uses_canonical_market_symbols(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_ingest(symbols: list[str], days: int, task_id: str | None = None) -> dict[str, object]:
        recorded.update({"symbols": symbols, "days": days, "task_id": task_id})
        return {"status": "ok"}

    monkeypatch.setattr(price_ingestion, "_ingest_historical_ohlcv_impl", fake_ingest)
    monkeypatch.setattr(price_ingestion, "task_cleanup", lambda _name: None)

    result = price_ingestion.refresh_daily_ohlcv()

    assert result == {"status": "ok"}
    assert recorded["symbols"] == ALL_MARKET_SYMBOLS
    assert recorded["days"] == DEFAULT_DAILY_REFRESH_DAYS


def test_historical_maintenance_symbol_set_includes_prediction_drivers(monkeypatch) -> None:
    storage = _FakeStorage(_FakeConnection(rows=[("WATCH",)]))
    monkeypatch.setattr(historical_ohlcv_pipeline, "get_storage", lambda: storage)

    symbols = historical_ohlcv_pipeline._get_all_symbols()

    assert set(PREDICTION_DRIVER_SYMBOLS).issubset(set(symbols))
    assert "WATCH" in symbols


def test_historical_maintenance_uses_expected_market_data_date(monkeypatch) -> None:
    storage = _FakeStorage(_FakeConnection(row=(1300, date(2026, 4, 30))))
    monkeypatch.setattr(historical_ohlcv_pipeline, "get_storage", lambda: storage)
    monkeypatch.setattr(
        historical_ohlcv_pipeline,
        "get_expected_data_date",
        lambda _now: date(2026, 4, 30),
    )

    needs_backfill, days_available = historical_ohlcv_pipeline._check_symbol_data("SPY")

    assert needs_backfill is False
    assert days_available == 1300
