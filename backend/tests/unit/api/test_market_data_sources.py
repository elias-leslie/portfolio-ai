"""Tests for market data source timestamp semantics."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.api.market_data_sources import calculate_daily_change_pct, fetch_sector_data_with_changes
from app.portfolio.models import PriceData


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def execute(self, _sql: str, _params: list[Any]) -> _Result:
        return _Result(self._rows)


class _Storage:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    @contextmanager
    def connection(self) -> Any:
        yield _Connection(self._rows)


def test_daily_change_uses_latest_close_for_intraday_quote() -> None:
    rows = [(date(2026, 5, 1), 100.0), (date(2026, 4, 30), 80.0)]

    change_pct = calculate_daily_change_pct(
        _Storage(rows),
        "^GSPC",
        110.0,
        datetime(2026, 5, 4, 19, 30, tzinfo=UTC),
    )

    assert change_pct == pytest.approx(10.0)


def test_daily_change_uses_prior_close_for_same_day_close_quote() -> None:
    rows = [(date(2026, 5, 1), 100.0), (date(2026, 4, 30), 80.0)]

    change_pct = calculate_daily_change_pct(
        _Storage(rows),
        "^GSPC",
        100.0,
        datetime(2026, 5, 1, 21, 30, tzinfo=UTC),
    )

    assert change_pct == pytest.approx(25.0)


def test_sector_changes_use_latest_close_for_intraday_quotes() -> None:
    rows = [("XLK", date(2026, 6, 3), 196.23), ("XLK", date(2026, 6, 2), 198.21)]

    sector_data = fetch_sector_data_with_changes(
        _Storage(rows),
        ["XLK"],
        {
            "XLK": PriceData(
                symbol="XLK",
                price=190.74,
                cached_at=datetime(2026, 6, 4, 14, 23, tzinfo=UTC),
            )
        },
    )

    assert sector_data["XLK"][1] == pytest.approx(-2.7977373490291906)
