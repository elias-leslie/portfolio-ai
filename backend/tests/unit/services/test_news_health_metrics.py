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
