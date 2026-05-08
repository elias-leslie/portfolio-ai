"""Unit tests for the market pulse scout service."""

from __future__ import annotations

from threading import Lock
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.market_pulse_research_service import MarketPulseResearchService


class _PersistedCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _PersistedConnection:
    def __init__(self, row):
        self.row = row
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, _query, params):
        self.params = params
        return _PersistedCursor(self.row)


class _PersistedStorage:
    def __init__(self, row):
        self.connection_instance = _PersistedConnection(row)

    def connection(self):
        return self.connection_instance


def test_get_cached_research_loads_persisted_success() -> None:
    payload = {
        "summary": "Cached scout read",
        "catalysts": [],
        "watch_items": [],
        "sources": [{"id": "source-1"}],
    }
    service = object.__new__(MarketPulseResearchService)
    service.storage = _PersistedStorage(({"payload": payload},))
    service._lock = Lock()
    service._cache = None
    service._cache_key = None
    service._cached_at = None
    service._cooldown_until = None

    result, fresh = service.get_cached_research("cache-key")

    assert fresh is True
    assert result == payload
    assert service._cache == payload
    params = service.storage.connection_instance.params
    assert params is not None
    assert params[0] == "cache-key"


def test_build_research_uses_scout_agent_slug_and_hub_tools(monkeypatch) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(
        content="""
        {
          "summary": "Fresh market scout read",
          "catalysts": [],
          "watch_items": [],
          "sources": [
            {
              "id": "fed",
              "label": "Federal Reserve",
              "url": "https://www.federalreserve.gov/monetarypolicy.htm",
              "published_at": null,
              "kind": "official"
            }
          ]
        }
        """,
        provider="served-provider",
        model="served-scout-model",
        usage=SimpleNamespace(
            input_tokens=42,
            output_tokens=24,
            output_tokens_details=SimpleNamespace(reasoning_tokens=8),
        ),
    )
    client_cls = Mock(return_value=client)
    monkeypatch.setattr(
        "app.services.market_pulse_research_service.AgentHubAPIClient",
        client_cls,
    )

    service = object.__new__(MarketPulseResearchService)
    service.storage = Mock()
    service._lock = Lock()
    service._cache = None
    service._cache_key = None
    service._cached_at = None
    service._cooldown_until = None
    service._trusted_source_seed = Mock(return_value=[])
    service._upsert_source_profiles = Mock()
    service._record_success = Mock()
    service._record_failure = Mock()

    result = service.build_research(
        cache_key="cache-key",
        household={"generated_at": "2026-04-16T00:00:00+00:00"},
        portfolio={"quotes_updated_at": "2026-04-16T00:00:00+00:00", "positions": []},
        market={"last_updated": "2026-04-16T00:00:00+00:00"},
        articles=[],
        official_sources=[],
        upcoming_events=[],
    )

    assert result is not None
    assert result["summary"] == "Fresh market scout read"
    client_cls.assert_called_once_with(
        agent_slug="market-pulse-scout",
    )
    assert "model" not in client_cls.call_args.kwargs

    call = client.complete_messages.call_args
    assert call is not None
    assert call.kwargs["execute_tools"] is True
    assert call.kwargs["enable_programmatic_tools"] is True
    assert call.kwargs["max_turns"] == 4
    assert "system_prompt" not in call.kwargs
