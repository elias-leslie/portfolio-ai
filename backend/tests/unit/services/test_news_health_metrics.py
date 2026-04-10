"""Unit tests for news health metrics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from app.services.news_health_metrics import NewsHealthMetrics
from app.services.news_types import VendorStatsDict


def test_build_vendor_health_uses_persisted_article_time_when_runtime_success_missing() -> None:
    vendor_manager = Mock()
    vendor_manager.get_vendor_config.return_value = {
        "polygon": {
            "configured": True,
            "enabled": True,
            "notes": None,
            "reason": None,
        }
    }
    vendor_manager.get_vendor_runtime.return_value = {
        "polygon": {
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
            "articles_last_fetch": 0,
            "articles_last_fetch_post": 0,
        }
    }

    metrics = NewsHealthMetrics(storage=Mock(), vendor_manager=vendor_manager, ttl=timedelta(hours=6))
    now = datetime(2026, 3, 11, 0, 0, tzinfo=UTC)
    vendor_stats: dict[str, VendorStatsDict] = {
        "polygon": {
            "articles_last_24h": 1106,
            "last_article_at": datetime(2026, 3, 10, 23, 24, tzinfo=UTC),
        }
    }

    health = metrics.build_vendor_health(vendor_stats, now=now)

    assert health["polygon"]["last_success_at"] == "2026-03-10T23:24:00Z"
    assert health["polygon"]["last_article_at"] == "2026-03-10T23:24:00Z"
    assert health["polygon"]["active"] is True


def test_build_vendor_health_prefers_newest_success_timestamp() -> None:
    vendor_manager = Mock()
    vendor_manager.get_vendor_config.return_value = {
        "polygon": {
            "configured": True,
            "enabled": True,
            "notes": None,
            "reason": None,
        }
    }
    vendor_manager.get_vendor_runtime.return_value = {
        "polygon": {
            "last_attempt_at": datetime(2026, 3, 10, 23, 26, tzinfo=UTC),
            "last_success_at": datetime(2026, 3, 10, 23, 25, tzinfo=UTC),
            "last_error_at": None,
            "last_error": None,
            "articles_last_fetch": 5,
            "articles_last_fetch_post": 3,
        }
    }

    metrics = NewsHealthMetrics(storage=Mock(), vendor_manager=vendor_manager, ttl=timedelta(hours=6))
    now = datetime(2026, 3, 11, 0, 0, tzinfo=UTC)
    vendor_stats: dict[str, VendorStatsDict] = {
        "polygon": {
            "articles_last_24h": 1106,
            "last_article_at": datetime(2026, 3, 10, 23, 24, tzinfo=UTC),
        }
    }

    health = metrics.build_vendor_health(vendor_stats, now=now)

    assert health["polygon"]["last_success_at"] == "2026-03-10T23:25:00Z"
    assert health["polygon"]["last_attempt_at"] == "2026-03-10T23:26:00Z"
    assert health["polygon"]["articles_last_fetch_post_dedupe"] == 3


def test_build_pipeline_health_marks_empty_stale_news_down() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)
    old_refresh = now - timedelta(hours=30)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=0,
        fallback_headlines_24h=0,
        market_last_refreshed_at=old_refresh,
        watchlist_last_refreshed_at=None,
    )

    assert health["status"] == "down"
    assert health["latest_refreshed_at"] == old_refresh
    assert health["latest_refresh_age_hours"] == 30
    assert health["message"] == (
        "No fresh news in 24h. Latest refresh 1.2d ago; expected every 6h."
    )


def test_build_pipeline_health_marks_populated_but_late_news_degraded() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=42,
        fallback_headlines_24h=0,
        market_last_refreshed_at=now - timedelta(hours=8),
        watchlist_last_refreshed_at=now - timedelta(hours=10),
    )

    assert health["status"] == "degraded"
    assert health["latest_refresh_age_hours"] == 8
    assert health["message"] == (
        "42 headlines cached in 24h. Latest refresh 8h ago; expected every 6h."
    )


def test_build_pipeline_health_reports_sentiment_fallback_without_source_backup_copy() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=120,
        fallback_headlines_24h=3,
        market_last_refreshed_at=now - timedelta(hours=1),
        watchlist_last_refreshed_at=now - timedelta(hours=2),
    )

    assert health["status"] == "healthy"
    assert health["latest_refresh_age_hours"] == 1
    assert health["message"] == (
        "120 headlines refreshed in 24h. 3 used backup sentiment scoring."
    )


def test_build_pipeline_health_degrades_when_primary_sentiment_is_unavailable() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=107,
        fallback_headlines_24h=107,
        market_last_refreshed_at=now - timedelta(minutes=20),
        watchlist_last_refreshed_at=now - timedelta(minutes=30),
        primary_sentiment_available=False,
    )

    assert health["status"] == "degraded"
    assert health["latest_refresh_age_hours"] == 0.33
    assert health["message"] == (
        "107 headlines refreshed in 24h, but primary sentiment scoring is unavailable. "
        "107 used backup sentiment scoring."
    )


def test_build_pipeline_health_degrades_when_all_fresh_sentiment_is_backup() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=107,
        fallback_headlines_24h=107,
        market_last_refreshed_at=now - timedelta(minutes=20),
        watchlist_last_refreshed_at=now - timedelta(minutes=30),
        primary_sentiment_available=True,
    )

    assert health["status"] == "degraded"
    assert health["message"] == (
        "107 headlines refreshed in 24h, but cached headlines have not been rescored "
        "by primary sentiment yet. 107 used backup sentiment scoring."
    )


def test_build_pipeline_health_degrades_when_article_quality_is_unavailable() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=120,
        fallback_headlines_24h=0,
        market_last_refreshed_at=now - timedelta(minutes=20),
        watchlist_last_refreshed_at=now - timedelta(minutes=30),
        article_quality_available=False,
    )

    assert health["status"] == "degraded"
    assert health["latest_refresh_age_hours"] == 0.33
    assert health["message"] == (
        "120 headlines refreshed in 24h, but article quality scoring is unavailable."
    )


def test_build_pipeline_health_appends_quality_gap_to_existing_degradation() -> None:
    now = datetime(2026, 4, 10, 16, 0, tzinfo=UTC)

    health = NewsHealthMetrics.build_pipeline_health(
        now=now,
        ttl=timedelta(hours=6),
        headlines_24h=42,
        fallback_headlines_24h=0,
        market_last_refreshed_at=now - timedelta(hours=8),
        watchlist_last_refreshed_at=now - timedelta(hours=10),
        article_quality_available=False,
    )

    assert health["status"] == "degraded"
    assert health["message"] == (
        "42 headlines cached in 24h. Latest refresh 8h ago; expected every 6h. "
        "Article quality scoring is unavailable."
    )
