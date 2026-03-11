from __future__ import annotations

import pytest

import app.api.news_profiling as news_profiling_mod
from app.api.news_profiling import reset_source_metrics, trigger_profiling


@pytest.mark.asyncio
async def test_trigger_profiling_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_in_threadpool(func, *args):  # type: ignore[no-untyped-def]
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
    async def fake_run_in_threadpool(func, *args):  # type: ignore[no-untyped-def]
        assert func.__name__ == "reset_source_metrics_task"
        assert args == ()
        return {"status": "completed", "task_id": "reset-456"}

    monkeypatch.setattr(news_profiling_mod, "run_in_threadpool", fake_run_in_threadpool)

    response = await reset_source_metrics()

    assert response["status"] == "completed"
    assert response["task_id"] == "reset-456"
    assert response["message"] == "Reset task completed. All metrics and feedback have been deleted."
