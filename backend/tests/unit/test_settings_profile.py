"""Unit tests for psycopg-backed settings profile helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models.settings_profile import create_profile, get_all_profiles, update_profile


class FakeCursor:
    """Minimal psycopg-like cursor for settings profile tests."""

    def __init__(
        self,
        *,
        fetchone_result: dict[str, Any] | None = None,
        fetchall_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.execute_calls: list[tuple[str, object]] = []
        self.rowcount = 0

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        pass

    def execute(self, query: str, params: object = None) -> None:
        self.execute_calls.append((query, params))

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_result

    def fetchall(self) -> list[dict[str, Any]]:
        return self.fetchall_result


class FakeConnection:
    """Minimal psycopg-like connection for settings profile tests."""

    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commit_calls = 0
        self.cursor_kwargs: list[dict[str, object]] = []

    def cursor(self, *args: object, **kwargs: object) -> FakeCursor:
        self.cursor_kwargs.append(dict(kwargs))
        return self._cursor

    def commit(self) -> None:
        self.commit_calls += 1


def _profile_row(profile_data: dict[str, Any] | None = None) -> dict[str, Any]:
    timestamp = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
    return {
        "id": 7,
        "user_id": 11,
        "name": "Balanced",
        "description": "Default profile",
        "profile_data": profile_data or {"risk": "medium"},
        "is_active": True,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_get_all_profiles_uses_dict_row_factory() -> None:
    """Profile reads should request dict rows so column names survive."""
    cursor = FakeCursor(fetchall_result=[_profile_row()])
    conn = FakeConnection(cursor)

    profiles = get_all_profiles(conn, user_id=11)

    assert conn.cursor_kwargs == [{"row_factory": dict_row}]
    assert cursor.execute_calls[0][1] == (11,)
    assert profiles[0].name == "Balanced"
    assert profiles[0].profile_data == {"risk": "medium"}


def test_create_profile_wraps_profile_data_in_jsonb_and_commits() -> None:
    """Profile inserts should serialize JSON via psycopg and commit once."""
    payload = {"risk": "high", "max_position": 0.08}
    cursor = FakeCursor(fetchone_result=_profile_row(payload))
    conn = FakeConnection(cursor)

    profile = create_profile(
        conn,
        user_id=11,
        name="Aggressive",
        profile_data=payload,
        description="High conviction",
        is_active=True,
    )

    params = cursor.execute_calls[0][1]
    assert conn.cursor_kwargs == [{"row_factory": dict_row}]
    assert isinstance(params[3], Jsonb)
    assert conn.commit_calls == 1
    assert profile.profile_data == payload


def test_update_profile_wraps_json_payload_in_jsonb() -> None:
    """Profile updates should keep psycopg JSONB adaptation on partial writes."""
    payload = {"risk": "low"}
    cursor = FakeCursor(fetchone_result=_profile_row(payload))
    conn = FakeConnection(cursor)

    profile = update_profile(
        conn,
        profile_id=7,
        user_id=11,
        profile_data=payload,
        is_active=False,
    )

    params = cursor.execute_calls[0][1]
    assert conn.cursor_kwargs == [{"row_factory": dict_row}]
    assert isinstance(params[0], Jsonb)
    assert params[-2:] == [7, 11]
    assert conn.commit_calls == 1
    assert profile is not None
    assert profile.profile_data == payload
