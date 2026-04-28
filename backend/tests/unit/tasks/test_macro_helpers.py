from __future__ import annotations

from datetime import date
from typing import Any, cast

from app.tasks.ingestion._macro_helpers import fetch_and_store_indicators


class _FakeStorage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    def execute(self, query: str, params: list[Any]) -> None:
        self.calls.append((query, params))


class _FakeFred:
    def __init__(self) -> None:
        self.latest = {
            "CPI": (date(2026, 3, 1), 319.799),
            "CORE_CPI": (date(2026, 3, 1), 334.165),
            "PCE": (date(2026, 2, 1), 126.5),
            "BREAKEVEN_5Y": (date(2026, 4, 27), 2.34),
            "BREAKEVEN_10Y": (date(2026, 4, 27), 2.42),
        }

    def get_latest_value(self, indicator: str) -> tuple[date, float] | None:
        return self.latest.get(indicator)

    def fetch_custom_data(self) -> dict[str, float]:
        return {"custom": 1.23}


def test_fetch_and_store_indicators_uses_fred_observation_date() -> None:
    storage = _FakeStorage()
    stats: dict[str, Any] = {"indicators_inserted": 0, "inflation_updated": False, "errors": []}

    fetch_and_store_indicators(
        storage,
        cast(Any, _FakeFred()),
        date(2026, 4, 28),
        stats,
        "fetch_inflation_data",
        "inflation_updated",
    )

    persisted = {params[0]: params[2].date() for _query, params in storage.calls}
    assert persisted["CPI"] == date(2026, 3, 1)
    assert persisted["CORE_CPI"] == date(2026, 3, 1)
    assert persisted["PCE"] == date(2026, 2, 1)
    assert persisted["BREAKEVEN_10Y"] == date(2026, 4, 27)
    assert stats["indicators_inserted"] == 5
    assert stats["inflation_updated"] is True


def test_fetch_and_store_indicators_falls_back_for_legacy_value_only_fetchers() -> None:
    storage = _FakeStorage()
    stats: dict[str, Any] = {"indicators_inserted": 0, "custom_updated": False, "errors": []}

    fetch_and_store_indicators(
        storage,
        cast(Any, _FakeFred()),
        date(2026, 4, 28),
        stats,
        "fetch_custom_data",
        "custom_updated",
    )

    assert storage.calls[0][1][0] == "CUSTOM"
    assert storage.calls[0][1][2].date() == date(2026, 4, 28)
    assert storage.calls[0][1][3] == 1.23
    assert stats["custom_updated"] is True
