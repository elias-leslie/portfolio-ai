from __future__ import annotations

from datetime import UTC, datetime

import pytest

import app.api.news_profiling as news_profiling_mod
from app.api.news_profiling import (
    ArticleFeedbackRequest,
    get_article_feedback,
    reset_source_metrics,
    submit_article_feedback,
    trigger_profiling,
)


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, rows: list[tuple | None]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, list[str | bool | None] | None]] = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, query: str, params=None):
        self.calls.append((query, params))
        row = self._rows.pop(0) if self._rows else None
        return _FakeResult(row)

    def commit(self) -> None:
        self.committed = True


class _FakeStorage:
    def __init__(self, conn: _FakeConnection) -> None:
        self._conn = conn

    def connection(self) -> _FakeConnection:
        return self._conn


@pytest.mark.asyncio
async def test_trigger_profiling_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_in_threadpool(func, *args):
        assert func.__name__ == "profile_news_sources_task"
        assert args == ("default",)
        return {"status": "completed", "task_id": "profile-123"}

    monkeypatch.setattr(news_profiling_mod, "run_in_threadpool", fake_run_in_threadpool)

    response = await trigger_profiling()

    assert response.status == "completed"
    assert response.task_id == "profile-123"
    assert response.message == "Profiling task completed successfully."


@pytest.mark.asyncio
async def test_reset_source_metrics_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_in_threadpool(func, *args):
        assert func.__name__ == "reset_source_metrics_task"
        assert args == ()
        return {"status": "completed", "task_id": "reset-456"}

    monkeypatch.setattr(news_profiling_mod, "run_in_threadpool", fake_run_in_threadpool)

    response = await reset_source_metrics()

    assert response["status"] == "completed"
    assert response["task_id"] == "reset-456"
    assert response["message"] == "Reset task completed. All metrics and feedback have been deleted."


@pytest.mark.asyncio
async def test_submit_article_feedback_persists_feedback_and_returns_vendor_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_conn = _FakeConnection(rows=[None, (0.75,)])
    monkeypatch.setattr(news_profiling_mod, "_storage", lambda: _FakeStorage(fake_conn))

    response = await submit_article_feedback(
        ArticleFeedbackRequest(
            article_url="https://example.com/aapl",
            article_hash="aapl-hash",
            vendor="rss",
            is_useful=True,
        )
    )

    assert response.status == "success"
    assert response.vendor == "rss"
    assert response.updated_useful_rate == 0.75
    assert fake_conn.committed is True
    assert len(fake_conn.calls) == 2
    assert "INSERT INTO user_article_feedback" in fake_conn.calls[0][0]


@pytest.mark.asyncio
async def test_get_article_feedback_returns_existing_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_at = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)
    fake_conn = _FakeConnection(rows=[("rss", True, created_at)])
    monkeypatch.setattr(news_profiling_mod, "_storage", lambda: _FakeStorage(fake_conn))

    response = await get_article_feedback("aapl-hash")

    assert response == {
        "exists": True,
        "vendor": "rss",
        "is_useful": True,
        "created_at": created_at.isoformat(),
    }
