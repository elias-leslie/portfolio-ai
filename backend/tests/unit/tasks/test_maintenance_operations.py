from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

from app.tasks.maintenance_operations import get_database_size


def test_get_database_size_reads_size_without_writing_metrics(monkeypatch) -> None:
    execute_calls: list[str] = []
    fake_conn = MagicMock()

    size_result = MagicMock()
    size_result.fetchone.return_value = (1024,)

    tables_result = MagicMock()
    tables_result.fetchall.return_value = [
        ("news_cache", 512, "512 bytes"),
        ("watchlist_items", 256, "256 bytes"),
    ]

    execute_results = iter([size_result, tables_result])

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    def tracking_execute(sql: str, *args, **kwargs):
        execute_calls.append(sql)
        return next(execute_results)

    fake_conn.execute.side_effect = tracking_execute

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    result = get_database_size()

    assert result["database_size_bytes"] == 1024
    assert result["database_size_mb"] == 0.0
    assert len(result["top_tables"]) == 2
    assert all("INSERT INTO maintenance_stats" not in sql for sql in execute_calls)
    fake_conn.commit.assert_not_called()
