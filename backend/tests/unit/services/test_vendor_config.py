"""Vendor configuration tests."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

import polars as pl

from app.services import vendor_config
from app.sources.base import BaseSource, DatasetRequest


class DummySource(BaseSource):
    """Minimal source for vendor initialization tests."""

    name = "dummy"

    def __init__(self, storage: object | None = None) -> None:
        self.storage = storage

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        return None

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        return None

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        return None


def test_sec_edgar_requires_configured_user_agent(monkeypatch: Any) -> None:
    monkeypatch.setattr(vendor_config, "SEC_USER_AGENT", "")
    sources: list[BaseSource] = []
    captured: dict[str, Any] = {}

    vendor_config.init_free_vendor(
        "sec_edgar",
        DummySource,
        "SEC_EDGAR_ENABLED",
        "SEC filings",
        object(),
        sources=sources,
        register_callback=lambda name, **config: captured.update({"name": name, **config}),
    )

    assert sources == []
    assert captured["name"] == "sec_edgar"
    assert captured["configured"] is False
    assert captured["enabled"] is False
    assert captured["reason"] == "missing_sec_user_agent"


def test_sec_edgar_uses_source_when_user_agent_is_configured(monkeypatch: Any) -> None:
    monkeypatch.setattr(vendor_config, "SEC_USER_AGENT", "Portfolio AI contact@example.com")
    storage = object()
    sources: list[BaseSource] = []
    captured: dict[str, Any] = {}

    vendor_config.init_free_vendor(
        "sec_edgar",
        DummySource,
        "SEC_EDGAR_ENABLED",
        "SEC filings",
        storage,
        sources=sources,
        register_callback=lambda name, **config: captured.update({"name": name, **config}),
    )

    assert len(sources) == 1
    assert isinstance(sources[0], DummySource)
    assert sources[0].storage is storage
    assert captured["configured"] is True
    assert captured["enabled"] is True
    assert captured["reason"] is None
