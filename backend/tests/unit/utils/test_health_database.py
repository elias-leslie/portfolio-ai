from __future__ import annotations

from types import SimpleNamespace

import polars as pl

from app.utils.health_database import check_database


def _storage_with_connection_usage(used: int, maximum: int) -> SimpleNamespace:
    return SimpleNamespace(
        query=lambda _sql: pl.DataFrame(
            [
                {
                    "test": 1,
                    "used_connections": used,
                    "max_connections": maximum,
                }
            ]
        )
    )


def test_database_health_reports_connection_budget_details() -> None:
    result = check_database(_storage_with_connection_usage(54, 100))

    assert result.status == "ok"
    assert result.message is None
    assert result.details == {
        "used_connections": 54,
        "max_connections": 100,
        "utilization_pct": 54.0,
    }


def test_database_health_degrades_before_connections_are_exhausted() -> None:
    result = check_database(_storage_with_connection_usage(82, 100))

    assert result.status == "degraded"
    assert result.message == "PostgreSQL connection usage is 82.0% (82/100)."
    assert result.details == {
        "used_connections": 82,
        "max_connections": 100,
        "utilization_pct": 82.0,
    }
