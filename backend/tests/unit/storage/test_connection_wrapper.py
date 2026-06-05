"""Unit tests for PostgreSQL connection wrapper dataframe inserts."""

from __future__ import annotations

import math
from typing import Any

import polars as pl

from app.storage._connection_wrapper import PostgreSQLConnectionWrapper


class _FakeCursor:
    def __init__(self) -> None:
        self.query: str | None = None
        self.data: list[list[Any]] | None = None

    def executemany(self, query: str, data: list[list[Any]]) -> None:
        self.query = query
        self.data = data


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.rollback_count = 0

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def rollback(self) -> None:
        self.rollback_count += 1


def test_insert_dataframe_writes_missing_numeric_values_as_db_nulls() -> None:
    conn = _FakeConnection()
    wrapper = PostgreSQLConnectionWrapper(conn)
    frame = pl.DataFrame(
        [
            {"symbol": "^VIX", "bid": 0.0, "bid_size": 0},
            {"symbol": "^GSPC", "bid": float("nan"), "bid_size": None},
        ]
    )

    row_count = wrapper.insert_dataframe("price_cache", frame)

    assert row_count == 2
    assert conn.cursor_obj.query == (
        "INSERT INTO price_cache (symbol, bid, bid_size) VALUES (%s, %s, %s)"
    )
    inserted = conn.cursor_obj.data
    assert inserted == [["^VIX", 0.0, 0], ["^GSPC", None, None]]
    assert inserted is not None
    assert not any(
        isinstance(value, float) and math.isnan(value)
        for row in inserted
        for value in row
    )
