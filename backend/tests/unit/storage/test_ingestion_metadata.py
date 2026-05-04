"""Unit tests for ingestion metadata persistence."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import polars as pl

from app.storage.ingestion import IngestionManager


class _FakeCursor:
    def __init__(self, row: tuple[int]) -> None:
        self._row = row

    def fetchone(self) -> tuple[int]:
        return self._row


class _FakeConnection:
    def __init__(self) -> None:
        self.commit_count = 0
        self.inserted: list[tuple[str, pl.DataFrame, str]] = []

    def execute(self, _query: str, _params: Any = None) -> _FakeCursor:
        return _FakeCursor((1,))

    def insert_dataframe(self, table_name: str, df: pl.DataFrame, if_exists: str) -> None:
        self.inserted.append((table_name, df, if_exists))

    def commit(self) -> None:
        self.commit_count += 1


class _FakeConnectionManager:
    def __init__(self, conn: _FakeConnection) -> None:
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


class _FakeMetadataManager:
    def __init__(self) -> None:
        self.updated_tables: list[str] = []

    def update_table_metadata(self, _conn: _FakeConnection, table_name: str) -> None:
        self.updated_tables.append(table_name)


def test_insert_dataframe_commits_metadata_update() -> None:
    conn = _FakeConnection()
    metadata = _FakeMetadataManager()
    manager = IngestionManager(_FakeConnectionManager(conn), metadata)
    frame = pl.DataFrame([{"symbol": "SPY", "value": 1}])

    rows = manager.insert_dataframe("day_bars", frame)

    assert rows == 1
    assert metadata.updated_tables == ["day_bars"]
    assert conn.commit_count == 2
