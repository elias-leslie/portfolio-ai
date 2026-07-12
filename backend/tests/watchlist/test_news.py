"""Tests for NewsService sentiment scoring and caching."""

from __future__ import annotations

import copy
import datetime as dt
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

from app.services.news_cache import NewsCacheManager
from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore
from app.services.news_processing import FinBertUnavailableError
from app.services.news_service import NewsService
from app.services.preferences_service import get_or_create_preferences
from app.sources.base import BaseSource, DatasetRequest
from app.storage import get_storage
from app.watchlist.refresh_builders import build_recent_news_payload

NEWS_TEST_SYMBOLS = ("AAPL", "AMD", "GOOG", "MSFT", "NVDA", "TSLA")


def _ensure_symbols(storage: Any, symbols: Sequence[str]) -> None:
    with storage.connection() as conn:
        for symbol in symbols:
            conn.execute(
                """
                INSERT INTO symbols (symbol, company_name)
                VALUES (%s, %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                [symbol, f"{symbol} Test Symbol"],
            )
        conn.commit()


@pytest.fixture()
def storage() -> Any:
    storage_instance = get_storage()
    _ensure_symbols(storage_instance, NEWS_TEST_SYMBOLS)
    return storage_instance



class StubAnalyzer:
    def __init__(self, scores: list[SentimentScore]) -> None:
        self._scores = scores

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return True

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        assert len(texts) == len(self._scores)
        return self._scores


class FailingAnalyzer:
    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        raise FinBertUnavailableError("finbert unavailable")

    def is_available(self) -> bool:
        return False

    def is_loaded(self) -> bool:
        return False


def _format_gmt(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _sample_entries(now: datetime | None = None) -> list[dict[str, Any]]:
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


def _build_entry(title: str, published: datetime) -> dict[str, Any]:
    return {
        "title": title,
        "link": f"https://example.com/{title.lower().replace(' ', '-')}",
        "published": _format_gmt(published),
        "summary": f"Summary for {title}.",
        "source": {"title": "Example News"},
    }


def _news_article(
    *,
    symbol: str,
    content_hash: str,
    headline: str,
    summary: str,
    fetched_at: datetime,
    sentiment: SentimentScore | None = None,
    raw: dict[str, Any] | None = None,
) -> NewsArticle:
    return NewsArticle(
        symbol=symbol,
        headline=headline,
        url="https://example.com/news-cache-upsert",
        summary=summary,
        source="test-source",
        author=None,
        image_url=None,
        published_at=fetched_at,
        fetched_at=fetched_at,
        sentiment=sentiment
        or SentimentScore(
            score=0.2,
            label="positive",
            confidence=0.8,
            model="test-model",
        ),
        content_hash=content_hash,
        raw=raw if raw is not None else {"raw": {"vendor": "test-source"}},
        vendor="test-source",
    )


class StubNewsSource(BaseSource):
    """Minimal BaseSource implementation for news unit tests."""

    name = "stub_news"
    priority = 1
    supports_news = True

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._entries = entries or []
        self.fetch_call_count = 0

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        self._entries = entries

    def reset_calls(self) -> None:
        self.fetch_call_count = 0

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        return pl.DataFrame()

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        return pl.DataFrame()

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        self.fetch_call_count += 1
        rows: list[dict[str, str | None]] = []
        for ticker in symbols:
            for entry in self._entries:
                source_info = entry.get("source")
                source_name = (
                    source_info.get("title")
                    if isinstance(source_info, dict)
                    else str(source_info)
                    if source_info
                    else "stub_vendor"
                )
                rows.append(
                    {
                        "symbol": ticker,
                        "headline": entry.get("title"),
                        "summary": entry.get("summary"),
                        "url": entry.get("link"),
                        "published_at": entry.get("published"),
                        "source": source_name,
                    }
                )
        return pl.from_dicts(rows) if rows else pl.DataFrame()


def test_news_service_caches_articles(storage: Any) -> None:
    news_source = StubNewsSource(_sample_entries())

    # Stubs satisfy SentimentAnalyzer Protocol at runtime; NewsService.__init__
    # uses concrete types (FinBert/Vader) because it calls .is_available().
    analyzer: Any = StubAnalyzer(
        [
            SentimentScore(score=0.6, label="positive", confidence=0.9, model="finbert"),
            SentimentScore(score=0.2, label="positive", confidence=0.7, model="finbert"),
        ]
    )
    fallback: Any = StubAnalyzer(
        [
            SentimentScore(score=0.1, label="neutral", confidence=0.5, model="vader"),
            SentimentScore(score=-0.1, label="neutral", confidence=0.5, model="vader"),
        ]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        vendor_sources=[news_source],
        finbert_analyzer=analyzer,
        fallback_analyzer=fallback,
        auto_load_credentials=False,
    )

    bundle = service.get_news_intelligence("NVDA", max_articles=5, force_refresh=True)
    assert bundle.summary.article_count == 2
    assert bundle.summary.model_breakdown.get("finbert") == 2
    assert bundle.summary.score is not None
    assert news_source.fetch_call_count == 1

    # Cached call should not hit upstream source
    news_source.reset_calls()
    cached_bundle = service.get_news_intelligence("NVDA", max_articles=5)
    assert news_source.fetch_call_count == 0
    assert len(cached_bundle.articles) == len(bundle.articles)


def test_news_service_falls_back_to_vader(storage: Any) -> None:
    news_source = StubNewsSource()
    seed_entry = _sample_entries()[0]
    seed_entry.update(
        {
            "title": "TSLA misses delivery expectations",
            "link": "https://example.com/tsla-deliveries",
        }
    )
    news_source.set_entries([copy.deepcopy(seed_entry)])

    failing_finbert: Any = FailingAnalyzer()
    vader_analyzer: Any = StubAnalyzer(
        [SentimentScore(score=-0.4, label="negative", confidence=0.8, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        vendor_sources=[news_source],
        finbert_analyzer=failing_finbert,
        fallback_analyzer=vader_analyzer,
        auto_load_credentials=False,
    )

    bundle = service.get_news_intelligence("TSLA", max_articles=1, force_refresh=True)
    assert bundle.summary.article_count == 1
    assert bundle.summary.model_breakdown.get("vader") == 1
    assert bundle.summary.score is not None and bundle.summary.score < 0

    fallback_meta = bundle.articles[0].raw.get("sentiment_fallback")
    assert fallback_meta is not None
    assert fallback_meta.get("reason") == "unavailable"
    assert fallback_meta.get("rate") == pytest.approx(1.0)
    assert fallback_meta.get("latency_ms") is not None


def test_news_health_reports_fallback_metrics(storage: Any) -> None:
    news_source = StubNewsSource()
    seed_entry = _sample_entries()[0]
    seed_entry.update(
        {
            "title": "GOOG faces advertising slowdown",
            "link": "https://example.com/goog-advertising",
        }
    )
    news_source.set_entries([copy.deepcopy(seed_entry)])

    failing_finbert: Any = FailingAnalyzer()
    vader_analyzer: Any = StubAnalyzer(
        [SentimentScore(score=-0.2, label="negative", confidence=0.6, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        vendor_sources=[news_source],
        finbert_analyzer=failing_finbert,
        fallback_analyzer=vader_analyzer,
        auto_load_credentials=False,
    )

    service.get_news_intelligence("GOOG", max_articles=1, force_refresh=True)

    health = service.get_health()
    assert health["fallback_headlines_24h"] >= 1
    assert health["headlines_24h"] >= 1
    assert 0 < health["fallback_rate_24h"] <= 1
    assert health["fallback_avg_latency_ms_24h"] is not None
    assert health["fallback_p95_latency_ms_24h"] is not None
    assert health["fallback_last_event_at"] is not None
    assert health["lookback_window_hours"] == service.lookback_hours
    assert "vendors" in health
    assert news_source.name in health["vendors"]


def test_news_service_tracks_score_change(storage: Any) -> None:
    news_source = StubNewsSource()
    seed_entry = _sample_entries()[0]
    seed_entry.update(
        {
            "title": "AMD beats earnings expectations",
            "link": "https://example.com/amd-earnings",
        }
    )
    news_source.set_entries([copy.deepcopy(seed_entry)])

    positive_analyzer: Any = StubAnalyzer(
        [SentimentScore(score=0.6, label="positive", confidence=0.9, model="finbert")]
    )
    negative_analyzer: Any = StubAnalyzer(
        [SentimentScore(score=-0.6, label="negative", confidence=0.9, model="finbert")]
    )
    fallback: Any = StubAnalyzer(
        [SentimentScore(score=0.0, label="neutral", confidence=0.5, model="vader")]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=1),
        vendor_sources=[news_source],
        finbert_analyzer=positive_analyzer,
        fallback_analyzer=fallback,
        auto_load_credentials=False,
    )

    # Initial refresh (positive sentiment)
    service.get_news_intelligence("AMD", max_articles=1, force_refresh=True)

    # Age the existing entries into the "previous" window
    ninety_minutes = datetime.now(UTC) - timedelta(minutes=90)
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE news_cache
            SET fetched_at = %s,
                published_at = %s
            WHERE symbol = %s
            """,
            [ninety_minutes, ninety_minutes, "AMD"],
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
    news_source.set_entries([negative_entry])
    service.finbert_analyzer = negative_analyzer
    service.processor.finbert_analyzer = negative_analyzer

    bundle = service.get_news_intelligence("AMD", max_articles=1, force_refresh=True)
    assert bundle.summary.article_count == 1
    assert bundle.summary.score is not None and bundle.summary.score < 0
    assert bundle.summary.score_change is not None
    assert bundle.summary.score_change < 0


def test_recent_selection_backfills_with_stale_articles(storage: Any) -> None:
    now = datetime.now(UTC)
    stale_base = now - timedelta(hours=5)

    entries = [
        _build_entry("MSFT earnings beat", now - timedelta(minutes=20)),
        _build_entry("MSFT launches new cloud", now - timedelta(minutes=50)),
        _build_entry("MSFT historical analysis", stale_base),
        _build_entry("MSFT legacy revenue report", stale_base - timedelta(hours=1)),
        _build_entry("MSFT old partnership news", stale_base - timedelta(hours=2)),
    ]

    news_source = StubNewsSource(copy.deepcopy(entries))

    analyzer: Any = StubAnalyzer(
        [
            SentimentScore(score=0.3, label="positive", confidence=0.8, model="finbert"),
            SentimentScore(score=-0.1, label="negative", confidence=0.6, model="finbert"),
            SentimentScore(score=-0.2, label="negative", confidence=0.7, model="finbert"),
            SentimentScore(score=-0.3, label="negative", confidence=0.7, model="finbert"),
            SentimentScore(score=0.05, label="neutral", confidence=0.5, model="finbert"),
        ]
    )

    service = NewsService(
        storage,
        ttl=timedelta(hours=2),
        vendor_sources=[news_source],
        finbert_analyzer=analyzer,
        fallback_analyzer=analyzer,
        auto_load_credentials=False,
    )

    bundle = service.get_news_intelligence("MSFT", max_articles=5, force_refresh=True)
    assert len(bundle.articles) == 5

    stale_count = sum(1 for article in bundle.articles if article.raw.get("stale"))
    assert stale_count == 3

    assert bundle.summary.article_count == 2
    assert bundle.summary.model_breakdown.get("finbert") == 2
    assert bundle.summary.top_positive is not None
    assert bundle.summary.top_positive.raw.get("stale") is not True
    assert bundle.summary.top_negative is not None
    assert bundle.summary.top_negative.raw.get("stale") is not True


def test_build_recent_news_payload_includes_vendor_and_publisher() -> None:
    now = datetime.now(UTC)
    summary = NewsSummary(
        symbol="AAPL",
        score=0.42,
        score_change=0.1,
        positive_count=1,
        neutral_count=0,
        negative_count=0,
        article_count=1,
        latest_published_at=now,
        model_breakdown={"finbert": 1},
        top_positive=None,
        top_negative=None,
    )
    sentiment = SentimentScore(
        score=0.6,
        label="positive",
        confidence=0.9,
        model="finbert",
        probabilities={"positive": 0.9, "neutral": 0.08, "negative": 0.02},
    )
    raw_entry = {
        "vendor": "polygon",
        "source": {"title": "Example Publisher"},
    }
    article = NewsArticle(
        symbol="AAPL",
        headline="Example headline",
        url="https://example.com/article",
        summary="Example summary",
        source=None,
        author="Reporter",
        image_url=None,
        published_at=now,
        fetched_at=now,
        sentiment=sentiment,
        content_hash="hash-123",
        raw={"raw": raw_entry},
        vendor=None,
    )
    bundle = NewsBundle(symbol="AAPL", summary=summary, articles=[article])

    payload = build_recent_news_payload(bundle, max_articles=5)
    assert payload["summary"]["symbol"] == "AAPL"
    assert len(payload["articles"]) == 1
    article_payload = payload["articles"][0]
    assert article_payload["vendor"] == "polygon"
    assert article_payload["source"] == "Example Publisher"
    assert article_payload["publisher"] == "Example Publisher"


def test_news_cache_save_articles_upserts_by_symbol_content_hash(storage: Any) -> None:
    symbol = "ZZZNEWS"
    content_hash = "news-cache-upsert-test"
    first_fetch = datetime.now(UTC) - timedelta(minutes=10)
    second_fetch = datetime.now(UTC)
    manager = NewsCacheManager(storage)

    with storage.connection() as conn:
        conn.execute("DELETE FROM news_cache WHERE symbol = %s", [symbol])
        conn.execute(
            """
            INSERT INTO symbols (symbol, company_name)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            [symbol, "News Cache Upsert Test"],
        )
        conn.commit()

    try:
        manager.save_articles(
            [
                _news_article(
                    symbol=symbol,
                    content_hash=content_hash,
                    headline="Original headline",
                    summary="Original summary",
                    fetched_at=first_fetch,
                )
            ]
        )
        manager.save_articles(
            [
                _news_article(
                    symbol=symbol,
                    content_hash=content_hash,
                    headline="Updated headline",
                    summary="Updated summary",
                    fetched_at=second_fetch,
                )
            ]
        )

        with storage.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*), MAX(summary), MAX(fetched_at)
                FROM news_cache
                WHERE symbol = %s AND content_hash = %s
                """,
                [symbol, content_hash],
            ).fetchone()

        assert row is not None
        assert row[0] == 1
        assert row[1] == "Updated summary"
        assert row[2] == second_fetch
    finally:
        with storage.connection() as conn:
            conn.execute("DELETE FROM news_cache WHERE symbol = %s", [symbol])
            conn.execute("DELETE FROM symbols WHERE symbol = %s", [symbol])
            conn.commit()


def test_news_service_rescores_cached_fallback_sentiment(storage: Any) -> None:
    symbol = "ZZZRESCORE"
    content_hash = "news-cache-rescore-test"
    fetched_at = datetime.now(UTC) - timedelta(minutes=10)
    manager = NewsCacheManager(storage)

    with storage.connection() as conn:
        conn.execute("DELETE FROM news_cache WHERE symbol = %s", [symbol])
        conn.execute(
            """
            INSERT INTO symbols (symbol, company_name)
            VALUES (%s, %s)
            ON CONFLICT (symbol) DO NOTHING
            """,
            [symbol, "News Cache Rescore Test"],
        )
        conn.commit()

    try:
        manager.save_articles(
            [
                _news_article(
                    symbol=symbol,
                    content_hash=content_hash,
                    headline="ZZZRESCORE cached fallback headline",
                    summary="The old cache row used the backup sentiment analyzer.",
                    fetched_at=fetched_at,
                    sentiment=SentimentScore(
                        score=-0.2,
                        label="negative",
                        confidence=0.6,
                        model="vader",
                    ),
                    raw={
                        "raw": {
                            "vendor": "test-source",
                            "vendor_payload": {"ticker": symbol},
                        },
                        "sentiment_model": "vader",
                        "sentiment_fallback": {
                            "reason": "unavailable",
                            "article_count": 1,
                        },
                    },
                )
            ]
        )

        primary: Any = StubAnalyzer(
            [
                SentimentScore(
                    score=0.7,
                    label="positive",
                    confidence=0.9,
                    model="finbert",
                    probabilities={"positive": 0.9, "neutral": 0.08, "negative": 0.02},
                )
            ]
        )
        fallback: Any = StubAnalyzer([])
        service = NewsService(
            storage,
            ttl=timedelta(hours=6),
            vendor_sources=[],
            finbert_analyzer=primary,
            fallback_analyzer=fallback,
            auto_load_credentials=False,
        )

        bundle = service.get_news_intelligence(symbol, max_articles=1)

        assert bundle.summary.model_breakdown == {"finbert": 1}
        assert bundle.articles[0].sentiment.model == "finbert"

        reloaded = manager.load_cached_articles(symbol, limit=1).articles[0]
        assert reloaded.sentiment.model == "finbert"
        assert reloaded.sentiment.score == 0.7
        assert reloaded.raw.get("sentiment_fallback") is None
        assert reloaded.raw["sentiment_rescore"]["previous_model"] == "vader"
    finally:
        with storage.connection() as conn:
            conn.execute("DELETE FROM news_cache WHERE symbol = %s", [symbol])
            conn.execute("DELETE FROM symbols WHERE symbol = %s", [symbol])
            conn.commit()


def test_vendor_entries_round_robin_selection(storage: Any) -> None:
    now = datetime.now(UTC)
    rows = [
        {
            "symbol": "AAPL",
            "headline": "AAPL Polygon headline 1",
            "url": "https://example.com/polygon-1",
            "summary": "P1 summary",
            "news_source_name": "Polygon Publisher",
            "author": None,
            "image_url": None,
            "published_at": now,
            "source": "polygon",
            "vendor_payload": {"tickers": ["AAPL"]},
        },
        {
            "symbol": "AAPL",
            "headline": "AAPL Polygon headline 2",
            "url": "https://example.com/polygon-2",
            "summary": "P2 summary",
            "news_source_name": "Polygon Publisher",
            "author": None,
            "image_url": None,
            "published_at": now - timedelta(minutes=5),
            "source": "polygon",
            "vendor_payload": {"tickers": ["AAPL"]},
        },
        {
            "symbol": "AAPL",
            "headline": "AAPL Finnhub headline 1",
            "url": "https://example.com/finnhub-1",
            "summary": "F1 summary",
            "news_source_name": "Finnhub Publisher",
            "author": None,
            "image_url": None,
            "published_at": now - timedelta(minutes=2),
            "source": "finnhub",
            "vendor_payload": {"tickers": ["AAPL"]},
        },
    ]
    dataframe = pl.from_dicts(rows)

    class StubFetcher:
        def __init__(self) -> None:
            self.sources = [
                SimpleNamespace(name="polygon", priority=10),
                SimpleNamespace(name="finnhub", priority=20),
            ]

        def fetch_with_fallback(self, request: Any, verbose: bool = False) -> tuple[Any, dict[str, Any]]:
            return dataframe, {}

    news_source = StubNewsSource([])

    with storage.connection() as conn:
        conn.execute("DELETE FROM news_cache WHERE symbol = %s", ["AAPL"])
        conn.commit()

    stub_fetcher: Any = StubFetcher()
    analyzer: Any = StubAnalyzer(
        [
            SentimentScore(score=0.3, label="positive", confidence=0.8, model="finbert"),
            SentimentScore(score=0.2, label="positive", confidence=0.7, model="finbert"),
            SentimentScore(score=0.1, label="neutral", confidence=0.6, model="finbert"),
        ]
    )
    service = NewsService(
        storage,
        ttl=timedelta(hours=6),
        vendor_sources=[news_source],
        multi_source_fetcher=stub_fetcher,
        finbert_analyzer=analyzer,
        fallback_analyzer=analyzer,
        selection_overfetch=1,
        auto_load_credentials=False,
    )
    service.quality_scorer.quality_model = None
    service.quality_scorer.mode = "heuristic"
    service.quality_model = None

    bundle = service.get_news_intelligence("AAPL", max_articles=3, force_refresh=True)
    vendors = {article.vendor for article in bundle.articles}

    assert vendors == {"polygon", "finnhub"}
    assert len(bundle.articles) == 3


def test_refresh_max_articles_from_preferences(storage: Any) -> None:
    service = NewsService(storage, auto_load_credentials=False)
    get_or_create_preferences()
    with storage.connection() as conn:
        conn.execute(
            "UPDATE user_preferences SET news_max_articles = %s",
            [15],
        )
        conn.commit()

    assert service.refresh_max_articles_from_preferences() == 15
    assert service.max_articles == 15
