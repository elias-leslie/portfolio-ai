"""Unit tests for committee stage Agent Hub wrappers."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.committee import stages


@pytest.mark.asyncio
async def test_complete_times_out_and_closes_agent_hub_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class SlowAgentHubClient:
        def __init__(self, **_kw: Any) -> None:
            return None

        async def complete_messages_async(self, **_kw: Any) -> Any:
            await asyncio.sleep(1)

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    monkeypatch.setattr(stages, "AgentHubAPIClient", SlowAgentHubClient)
    monkeypatch.setattr(stages, "_AGENT_COMPLETION_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(TimeoutError, match="committee.test timed out after 0.01s"):
        await stages._complete("test-agent", {"symbol": "NVDA"}, purpose="committee.test")

    assert closed is True
