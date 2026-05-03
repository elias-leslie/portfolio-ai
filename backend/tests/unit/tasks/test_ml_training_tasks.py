from __future__ import annotations

from typing import Any

import pytest

from app.tasks.ml_training_tasks import _coerce_progress_value, _update_progress


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any] | None]] = []
        self.committed = 0

    def execute(self, sql: str, parameters: Any = None) -> _FakeConnection:
        self.executed.append((sql, parameters))
        return self

    def commit(self) -> None:
        self.committed += 1


def test_coerce_progress_value_passthrough_types() -> None:
    assert _coerce_progress_value("hello") == "hello"
    assert _coerce_progress_value(42) == 42
    assert _coerce_progress_value(3.14) == 3.14
    assert _coerce_progress_value(True) is True
    assert _coerce_progress_value(None) is None


def test_coerce_progress_value_converts_other_to_str() -> None:
    assert _coerce_progress_value(["a", "b"]) == "['a', 'b']"


def test_update_progress_noop_without_session_id() -> None:
    conn = _FakeConnection()
    _update_progress(conn, None, "querying", "Loading...", 5)
    assert conn.executed == []
    assert conn.committed == 0


def test_update_progress_executes_with_session_id() -> None:
    conn = _FakeConnection()
    _update_progress(conn, "sess-123", "querying", "Loading...", 5)
    assert conn.committed == 1
    sql, params = conn.executed[0]
    assert "UPDATE ml_training_progress SET" in sql
    assert "WHERE session_id = %s" in sql
    assert params is not None
    assert params[-1] == "sess-123"


def test_update_progress_includes_kwargs() -> None:
    conn = _FakeConnection()
    _update_progress(conn, "sess-123", "labeling", "Labeling...", 20, articles_found=50)
    sql, params = conn.executed[0]
    assert "articles_found = %s" in sql
    assert params is not None
    assert 50 in params


def test_update_progress_rejects_disallowed_column() -> None:
    conn = _FakeConnection()
    with pytest.raises(ValueError, match="Disallowed progress column"):
        _update_progress(conn, "sess-123", "training", "Step", 70, evil_column="drop table")
