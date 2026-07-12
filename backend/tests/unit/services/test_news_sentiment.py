"""Unit tests for optional news sentiment dependencies."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import ANY, Mock

from app.services.news_sentiment import _load_finbert_dependencies
from app.services.news_service import NewsService


class _UnavailableFinBert:
    def is_loaded(self) -> bool:
        return False

    def is_available(self) -> bool:
        raise AssertionError("health checks must not initialize FinBERT")


def test_load_finbert_dependencies_returns_none_when_optional_packages_missing(mocker) -> None:
    """FinBERT helpers should degrade cleanly when heavy packages are absent."""

    def raise_import_error(name: str):
        raise ImportError(f"missing {name}")

    mocker.patch("app.services.news_sentiment.import_module", side_effect=raise_import_error)

    torch, auto_tokenizer, auto_model = _load_finbert_dependencies()

    assert torch is None
    assert auto_tokenizer is None
    assert auto_model is None


def test_news_health_includes_ml_install_hint_when_finbert_unavailable(mocker) -> None:
    news_service = NewsService(Mock())
    news_service.finbert_analyzer = _UnavailableFinBert()
    news_service.quality_scorer = Mock()
    news_service.quality_scorer.is_model_available.return_value = False
    news_service.quality_scorer.mode = "heuristic"
    news_service.cache_refresher = Mock()
    news_service.cache_refresher.latest_fetched_at.return_value = datetime.fromisoformat(
        "2026-03-10T00:00:00+00:00"
    )
    news_service.health_metrics = Mock()
    news_service.health_metrics.get_fallback_metrics.return_value = {
        "fallback_count": 2,
        "total_count": 10,
        "fallback_rate": 0.2,
        "avg_latency_ms": 15.0,
        "p95_latency_ms": 30.0,
        "last_fallback_at": None,
    }
    news_service.health_metrics.get_article_mix_metrics.return_value = {
        "total_pre": 10,
        "total_post": 8,
        "vendor_pre": {},
        "vendor_post": {},
        "last_timestamp": None,
    }
    news_service.health_metrics.get_vendor_stats.return_value = {}
    news_service.health_metrics.build_vendor_health.return_value = {}
    news_service.health_metrics.build_pipeline_health.return_value = {
        "status": "healthy",
        "message": "10 headlines refreshed in 24h.",
        "latest_refreshed_at": datetime.fromisoformat("2026-03-10T00:00:00+00:00"),
        "latest_refresh_age_hours": 1.0,
    }
    news_service.health_metrics.to_iso.side_effect = (
        lambda value: value.isoformat() if value is not None else None
    )
    mocker.patch.object(
        news_service,
        "rescore_recent_fallback_sentiment",
        side_effect=AssertionError("health checks must not rescore or write articles")
    )

    health = news_service.get_health()

    assert health["status"] == "healthy"
    assert health["message"] == (
        "10 headlines refreshed in 24h. Article quality scoring is running in heuristic mode."
    )
    assert health["finbert_available"] is False
    assert health["quality_model_available"] is False
    assert health["quality_scoring_mode"] == "heuristic"
    assert health["finbert_install_hint"] == "uv sync --extra dev --extra ml"
    news_service.health_metrics.build_pipeline_health.assert_called_once_with(
        now=ANY,
        ttl=news_service.ttl,
        headlines_24h=10,
        fallback_headlines_24h=2,
        market_last_refreshed_at=datetime.fromisoformat("2026-03-10T00:00:00+00:00"),
        watchlist_last_refreshed_at=datetime.fromisoformat("2026-03-10T00:00:00+00:00"),
        primary_sentiment_available=False,
    )
