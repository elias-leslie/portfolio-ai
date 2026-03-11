from __future__ import annotations

import pytest

from app.api.news_profiling import reset_source_metrics, trigger_profiling


@pytest.mark.asyncio
async def test_trigger_profiling_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(func, *args):  # type: ignore[no-untyped-def]
        assert func.__name__ == "profile_news_sources_task"
        assert args == ("default",)
        return {"status": "completed", "task_id": "profile-123"}

    monkeypatch.setattr("app.api.news_profiling.asyncio.to_thread", fake_to_thread)

    response = await trigger_profiling()

    assert response.status == "completed"
    assert response.task_id == "profile-123"
    assert response.message == "Profiling task completed successfully."


@pytest.mark.asyncio
async def test_reset_source_metrics_returns_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_to_thread(func, *args):  # type: ignore[no-untyped-def]
        assert func.__name__ == "reset_source_metrics_task"
        assert args == ()
        return {"status": "completed", "task_id": "reset-456"}

    monkeypatch.setattr("app.api.news_profiling.asyncio.to_thread", fake_to_thread)

    response = await reset_source_metrics()

    assert response == {
        "status": "completed",
        "task_id": "reset-456",
        "message": "Reset task completed. All metrics and feedback have been deleted.",
    }
