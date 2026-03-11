from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.tasks.maintenance_operations import (
    cleanup_old_news,
    cleanup_orphaned_data,
    get_database_size,
    vacuum_tables,
)


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


def test_cleanup_old_news_respects_recent_refetches(monkeypatch) -> None:
    fake_conn = MagicMock()
    count_result = MagicMock()
    count_result.fetchone.return_value = (7,)
    fake_conn.execute.return_value = count_result

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    result = cleanup_old_news(days=30, dry_run=True)

    executed_sql = fake_conn.execute.call_args[0][0]
    assert "COALESCE(published_at, fetched_at) < %s" in executed_sql
    assert "AND fetched_at < %s" in executed_sql
    assert result["rows_to_delete"] == 7


def test_vacuum_tables_uses_raw_connection_and_reports_processed(monkeypatch) -> None:
    fake_query_conn = MagicMock()
    query_result = MagicMock()
    query_result.fetchall.return_value = [("news_cache",), ("day_bars",)]
    fake_query_conn.execute.return_value = query_result

    fake_raw_connection = MagicMock()
    fake_raw_connection.autocommit = False
    fake_cursor_cm = MagicMock()
    fake_raw_connection.cursor.return_value.__enter__.return_value = fake_cursor_cm
    fake_conn = MagicMock()
    fake_conn.raw_connection = fake_raw_connection

    manager_calls = iter([fake_query_conn, fake_conn, fake_conn])

    @contextmanager
    def fake_connection():
        yielded = next(manager_calls)
        yield yielded

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    result = vacuum_tables()

    assert result["tables_processed"] == 2
    assert result["failed_tables_count"] == 0
    assert fake_cursor_cm.execute.call_count == 2
    assert fake_raw_connection.autocommit is False


def test_vacuum_tables_raises_when_any_table_fails(monkeypatch) -> None:
    fake_query_conn = MagicMock()
    query_result = MagicMock()
    query_result.fetchall.return_value = [("news_cache",)]
    fake_query_conn.execute.return_value = query_result

    fake_raw_connection = MagicMock()
    fake_raw_connection.autocommit = False
    fake_cursor_cm = MagicMock()
    fake_cursor_cm.execute.side_effect = RuntimeError("boom")
    fake_raw_connection.cursor.return_value.__enter__.return_value = fake_cursor_cm
    fake_conn = MagicMock()
    fake_conn.raw_connection = fake_raw_connection

    manager_calls = iter([fake_query_conn, fake_conn])

    @contextmanager
    def fake_connection():
        yielded = next(manager_calls)
        yield yielded

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    with pytest.raises(RuntimeError, match="VACUUM ANALYZE failed"):
        vacuum_tables()


def test_cleanup_orphaned_data_dry_run_reports_only_stale_runs(monkeypatch) -> None:
    fake_conn = MagicMock()
    fake_conn.execute.return_value = MagicMock(fetchone=MagicMock(return_value=(11,)))

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    result = cleanup_orphaned_data(dry_run=True)

    orphan_sql = fake_conn.execute.call_args_list[0][0][0]
    assert "FROM agent_runs" in orphan_sql
    assert "status IN ('running', 'error')" in orphan_sql
    assert result["zombie_runs_to_fix"] == 11


def test_cleanup_orphaned_data_live_commits_deleted_counts(monkeypatch) -> None:
    fake_conn = MagicMock()
    fake_conn._cursor.rowcount = 2

    def execute_side_effect(sql: str, *_args, **_kwargs):
        if "UPDATE agent_runs" in sql:
            fake_conn._cursor.rowcount = 2
        return MagicMock()

    fake_conn.execute.side_effect = execute_side_effect

    @contextmanager
    def fake_connection():
        yield fake_conn

    fake_manager = MagicMock()
    fake_manager.connection.side_effect = fake_connection

    monkeypatch.setattr(
        "app.tasks.maintenance_operations.get_connection_manager",
        lambda: fake_manager,
    )

    result = cleanup_orphaned_data(dry_run=False)

    assert result == {
        "zombie_runs_fixed": 2,
    }
    fake_conn.commit.assert_called_once()
