"""Tests for Google News source integration."""

from __future__ import annotations

from typing import ClassVar

from app.sources.news import GoogleNewsSource


def test_google_news_source_url_is_encoded(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class DummyFeed:
        entries: ClassVar[list[dict[str, str]]] = []

    def fake_fetch(
        self: GoogleNewsSource, url: str
    ) -> DummyFeed:  # pragma: no cover - trivial stub
        captured["url"] = url
        return DummyFeed()

    monkeypatch.setattr("app.sources.news.GoogleNewsSource._fetch_feed", fake_fetch)

    source = GoogleNewsSource()
    headlines = source.fetch_headlines("stock market", max_results=1)

    assert headlines == []
    assert "stock+market" in captured["url"], captured["url"]
