import datetime as dt
from typing import Any, cast
from unittest.mock import Mock

import polars as pl

from app.sources.base import DATASET_DAY, DatasetRequest
from app.tasks import source_health_tasks
from app.tasks.source_health_tasks import _check_single_source


class _HealthySource:
    name = "demo"

    def fetch_day_bars(self, _request: DatasetRequest) -> pl.DataFrame:
        return pl.DataFrame({"symbol": ["SPY"], "close": [500.0]})


class _FailingSource:
    name = "demo"

    def fetch_day_bars(self, _request: DatasetRequest) -> pl.DataFrame:
        raise RuntimeError("provider down")


def _request() -> DatasetRequest:
    today = dt.date(2026, 6, 30)
    return DatasetRequest(dataset=DATASET_DAY, profile=None, symbols=["SPY"], start=today, end=today)


def test_source_health_probe_records_metric_success() -> None:
    metrics = Mock()
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    _check_single_source(_HealthySource(), _request(), results, errors, metrics)

    assert results == {"demo": "healthy"}
    assert errors == {}
    metrics.record_success.assert_called_once()
    assert metrics.record_success.call_args.args[0] == "demo"


def test_source_health_probe_records_metric_failure() -> None:
    metrics = Mock()
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    _check_single_source(_FailingSource(), _request(), results, errors, metrics)

    assert results == {"demo": "down"}
    assert errors == {"demo": "provider down"}
    metrics.record_failure.assert_called_once()
    assert metrics.record_failure.call_args.args[0] == "demo"


def test_source_health_fetcher_loads_database_credentials(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        source_health_tasks,
        "load_credentials_from_database",
        lambda: calls.append("loaded"),
    )
    monkeypatch.setattr(source_health_tasks, "PortfolioStorage", lambda: "storage")
    monkeypatch.setattr(source_health_tasks, "YFinanceSource", lambda: "yfinance")
    monkeypatch.setattr(source_health_tasks, "TwelveDataSource", lambda: "twelvedata")
    monkeypatch.setattr(source_health_tasks, "FMPSource", lambda: "fmp")
    monkeypatch.setattr(source_health_tasks, "PolygonSource", lambda: "polygon")
    monkeypatch.setattr(source_health_tasks, "FinnhubSource", lambda: "finnhub")
    monkeypatch.setattr(source_health_tasks, "AlphaVantageSource", lambda: "alphavantage")

    def fake_fetcher(sources, storage):
        return {"sources": sources, "storage": storage}

    monkeypatch.setattr(source_health_tasks, "MultiSourceFetcher", fake_fetcher)

    result = cast(dict[str, Any], source_health_tasks._build_fetcher())

    assert calls == ["loaded"]
    assert result["storage"] == "storage"
    assert result["sources"] == [
        "yfinance",
        "twelvedata",
        "fmp",
        "polygon",
        "finnhub",
        "alphavantage",
    ]
