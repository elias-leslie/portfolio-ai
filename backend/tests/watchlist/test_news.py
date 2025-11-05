"""Tests for NewsService sentiment scoring and caching."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.news_service import (
    FinBertUnavailableError,
    NewsService,
    SentimentScore,
)
from app.storage import get_storage


@pytest.fixture()
def storage():
    return get_storage()


class StubAnalyzer:
    def __init__(self, scores: list[SentimentScore]) -> None:
        self._scores = scores

    def score_batch(self, texts: list[str]):  # pragma: no cover - simple stub
        assert len(texts) == len(self._scores)
        return self._scores


class FailingAnalyzer:
    def score_batch(self, texts: list[str]):  # pragma: no cover - simple stub
        raise FinBertUnavailableError("finbert unavailable")

    def is_available(self) -> bool:  # pragma: no cover - simple stub
        return False


def _format_gmt(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _sample_entries(now: datetime | None = None) -> list[dict[str, str]]:
    """Generate sample feed entries with recent timestamps to satisfy TTL filtering."""

    reference = now or datetime.now(UTC)
    recent = reference - timedelta(minutes=30)
    earlier = reference - timedelta(hours=1)

    return [
        {
            "title": "NVDA beats earnings expectations",
            "link": "https://example.com/nvda-earnings",
            "published": _format_gmt(recent),
            "summary": "Shares surge after another strong quarter.",
            "source": {"title": "Example News"},
        },
        {
            "title": "NVIDIA announces new AI chip",
            "link": "https://example.com/nvda-chip",
            "published": _format_gmt(earlier),
            "summary": "Launch targets data center workloads",
            "source": {"title": "TechWire"},
        },
    ]


def _build_entry(title: str, published: datetime) -> dict[str, str]:
    return {
        "title": title,
        "link": f"https://example.com/{title.lower().replace(' ', '-')}",
        "published": _format_gmt(published),
        "summary": f"Summary for {title}.",
        "source": {"title": "Example News"},
    }


def test_news_service_caches_articles(storage):
    news_source = MagicMock()
    news_source.fetch_headlines.return_value = _sample_entries()

    analyzer = StubAnalyzer(
        [
            SentimentScore(score=0.6, label="positive", confidence=0.9, model="finbert"),
            SentimentScore(score=0.2, label="positive", confidence=0.7, model="finbert"),
        ]
    )
    fallback = StubAnalyzer(
        [
            SentimentScore(score=0.1, label="neutral", confidence=0.5, model="vader"),
            SentimentScore(score=-0.1, label="neutral", confidence=0.5, model="vader"),
        ]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        news_source=news_source,
        finbert_analyzer=analyzer,
        fallback_analyzer=fallback,
    )

    bundle = service.get_symbol_news("NVDA", max_articles=5, force_refresh=True)
    assert bundle.summary.article_count == 2
    assert bundle.summary.model_breakdown.get("finbert") == 2
    assert bundle.summary.score is not None
    news_source.fetch_headlines.assert_called_once()

    # Cached call should not hit upstream source
    news_source.fetch_headlines.reset_mock()
    cached_bundle = service.get_symbol_news("NVDA", max_articles=5)
    news_source.fetch_headlines.assert_not_called()
    assert len(cached_bundle.articles) == len(bundle.articles)


def test_news_service_falls_back_to_vader(storage):
    news_source = MagicMock()
    seed_entry = _sample_entries()[0]
    news_source.fetch_headlines.return_value = [copy.deepcopy(seed_entry)]

    failing_finbert = FailingAnalyzer()
    vader_analyzer = StubAnalyzer(
        [SentimentScore(score=-0.4, label="negative", confidence=0.8, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        news_source=news_source,
        finbert_analyzer=failing_finbert,  # type: ignore[arg-type]
        fallback_analyzer=vader_analyzer,
    )

    bundle = service.get_symbol_news("TSLA", max_articles=1, force_refresh=True)
    assert bundle.summary.article_count == 1
    assert bundle.summary.model_breakdown.get("vader") == 1
    assert bundle.summary.score is not None and bundle.summary.score < 0

    fallback_meta = bundle.articles[0].raw.get("sentiment_fallback")
    assert fallback_meta is not None
    assert fallback_meta.get("reason") == "unavailable"
    assert fallback_meta.get("rate") == pytest.approx(1.0)
    assert fallback_meta.get("latency_ms") is not None


def test_news_health_reports_fallback_metrics(storage):
    news_source = MagicMock()
    seed_entry = _sample_entries()[0]
    news_source.fetch_headlines.return_value = [copy.deepcopy(seed_entry)]

    failing_finbert = FailingAnalyzer()
    vader_analyzer = StubAnalyzer(
        [SentimentScore(score=-0.2, label="negative", confidence=0.6, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        news_source=news_source,
        finbert_analyzer=failing_finbert,  # type: ignore[arg-type]
        fallback_analyzer=vader_analyzer,
    )

    service.get_symbol_news("GOOG", max_articles=1, force_refresh=True)

    health = service.get_health()
    assert health["fallback_headlines_24h"] >= 1
    assert health["headlines_24h"] >= 1
    assert 0 < health["fallback_rate_24h"] <= 1
    assert health["fallback_avg_latency_ms_24h"] is not None
    assert health["fallback_p95_latency_ms_24h"] is not None
    assert health["fallback_last_event_at"] is not None
    assert health["lookback_window_hours"] == service.lookback_hours


def test_news_service_tracks_score_change(storage):
    news_source = MagicMock()
    seed_entry = _sample_entries()[0]
    news_source.fetch_headlines.return_value = [copy.deepcopy(seed_entry)]

    positive_analyzer = StubAnalyzer(
        [SentimentScore(score=0.6, label="positive", confidence=0.9, model="finbert")]
    )
    negative_analyzer = StubAnalyzer(
        [SentimentScore(score=-0.6, label="negative", confidence=0.9, model="finbert")]
    )
    fallback = StubAnalyzer(
        [SentimentScore(score=0.0, label="neutral", confidence=0.5, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=1),
        news_source=news_source,
        finbert_analyzer=positive_analyzer,
        fallback_analyzer=fallback,
    )

    # Initial refresh (positive sentiment)
    service.get_symbol_news("AMD", max_articles=1, force_refresh=True)

    # Age the existing entries into the "previous" window
    ninety_minutes = datetime.now(UTC) - timedelta(minutes=90)
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE news_cache
            SET fetched_at = %s
            WHERE ticker = %s
            """,
            [ninety_minutes, "AMD"],
        )
        conn.commit()

    # Next refresh with negative sentiment should produce score change
    negative_entry = copy.deepcopy(seed_entry)
    negative_entry.update(
        {
            "title": "AMD faces supply chain headwinds",
            "link": "https://example.com/amd-headwinds",
            "published": _format_gmt(datetime.now(UTC) - timedelta(minutes=10)),
        }
    )
    news_source.fetch_headlines.return_value = [negative_entry]
    service.finbert_analyzer = negative_analyzer

    bundle = service.get_symbol_news("AMD", max_articles=1, force_refresh=True)
    assert bundle.summary.article_count == 1
    assert bundle.summary.score is not None and bundle.summary.score < 0
    assert bundle.summary.score_change is not None
    assert bundle.summary.score_change < 0


def test_recent_selection_backfills_with_stale_articles(storage):
    now = datetime.now(UTC)
    stale_base = now - timedelta(hours=5)

    entries = [
        _build_entry("MSFT earnings beat", now - timedelta(minutes=20)),
        _build_entry("MSFT launches new cloud", now - timedelta(minutes=50)),
        _build_entry("MSFT historical analysis", stale_base),
        _build_entry("Legacy revenue report", stale_base - timedelta(hours=1)),
        _build_entry("Old partnership news", stale_base - timedelta(hours=2)),
    ]

    news_source = MagicMock()
    news_source.fetch_headlines.return_value = copy.deepcopy(entries)

    analyzer = StubAnalyzer(
        [
            SentimentScore(score=0.3, label="positive", confidence=0.8, model="finbert"),
            SentimentScore(score=0.1, label="neutral", confidence=0.6, model="finbert"),
            SentimentScore(score=-0.2, label="negative", confidence=0.7, model="finbert"),
            SentimentScore(score=-0.3, label="negative", confidence=0.7, model="finbert"),
            SentimentScore(score=0.05, label="neutral", confidence=0.5, model="finbert"),
        ]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=2),
        news_source=news_source,
        finbert_analyzer=analyzer,
        fallback_analyzer=analyzer,
    )

    bundle = service.get_symbol_news("MSFT", max_articles=5, force_refresh=True)
    assert len(bundle.articles) == 5

    stale_count = sum(1 for article in bundle.articles if article.raw.get("stale"))
    assert stale_count == 3

    assert bundle.summary.article_count == 2
    assert bundle.summary.model_breakdown.get("finbert") == 2
