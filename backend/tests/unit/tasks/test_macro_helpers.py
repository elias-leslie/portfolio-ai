"""Tests for macro indicator ingestion helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.tasks.ingestion._macro_helpers import (
    fetch_and_store_indicators,
    fetch_and_store_yield_curve,
)


class _StorageStub:
    def __init__(self) -> None:
        self.executions: list[tuple[str, list[Any]]] = []

    def execute(self, query: str, params: list[Any]) -> None:
        self.executions.append((query, params))


class _FredStub:
    def __init__(self, latest_values: dict[str, tuple[date, float] | None]) -> None:
        self.latest_values = latest_values

    def get_latest_value(self, indicator: str) -> tuple[date, float] | None:
        return self.latest_values.get(indicator)


def test_fetch_and_store_indicators_uses_fred_observation_date() -> None:
    storage: Any = _StorageStub()
    fred: Any = _FredStub(
        {
            "CPI": (date(2026, 4, 1), 313.9),
            "CORE_CPI": None,
            "PCE": (date(2026, 3, 1), 128.4),
            "BREAKEVEN_5Y": None,
            "BREAKEVEN_10Y": None,
        }
    )
    stats: dict[str, Any] = {
        "indicators_inserted": 0,
        "inflation_updated": False,
        "errors": [],
    }

    fetch_and_store_indicators(
        storage,
        fred,
        date(2026, 5, 4),
        stats,
        "fetch_inflation_data",
        "inflation_updated",
    )

    assert stats["inflation_updated"] is True
    assert stats["indicators_inserted"] == 2
    assert [params[0] for _, params in storage.executions] == ["CPI", "PCE"]
    assert [params[2].date() for _, params in storage.executions] == [
        date(2026, 4, 1),
        date(2026, 3, 1),
    ]


def test_fetch_and_store_yield_curve_uses_conservative_component_observation_date() -> None:
    storage: Any = _StorageStub()
    fred: Any = _FredStub(
        {
            "YIELD_3M": (date(2026, 5, 1), 4.25),
            "YIELD_2Y": (date(2026, 5, 4), 3.9),
            "YIELD_5Y": (date(2026, 5, 4), 4.0),
            "YIELD_10Y": (date(2026, 5, 4), 4.35),
            "YIELD_30Y": (date(2026, 5, 4), 4.75),
        }
    )
    stats: dict[str, Any] = {
        "indicators_inserted": 0,
        "yield_curve_updated": False,
        "errors": [],
    }

    fetch_and_store_yield_curve(
        storage,
        fred,
        date(2026, 5, 5),
        stats,
    )

    assert stats["yield_curve_updated"] is True
    assert stats["indicators_inserted"] == 5
    assert len(storage.executions) == 1
    params = storage.executions[0][1]
    assert params[0].date() == date(2026, 5, 1)
    assert params[6] == pytest.approx(0.45)
    assert params[7] == pytest.approx(0.1)
