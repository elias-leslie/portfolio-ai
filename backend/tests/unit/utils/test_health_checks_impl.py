from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import polars as pl

from app.utils import health_checks_impl


class _FrozenDateTime(dt.datetime):
    @classmethod
    def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
        current = dt.datetime(2026, 3, 11, 3, 0, tzinfo=dt.UTC)
        if tz is None:
            return current.replace(tzinfo=None)
        return current.astimezone(tz)


def test_check_sources_excludes_news_only_vendors(monkeypatch) -> None:
    rows = pl.DataFrame(
        [
            {
                "source_name": "yfinance",
                "success_count": 10,
                "failure_count": 0,
                "total_latency_ms": 1000,
                "rate_limit_hits": 0,
                "last_success_at": dt.datetime(2026, 3, 11, 2, 0, tzinfo=dt.UTC),
            },
            {
                "source_name": "sec_edgar",
                "success_count": 7,
                "failure_count": 0,
                "total_latency_ms": 3500,
                "rate_limit_hits": 0,
                "last_success_at": dt.datetime(2026, 3, 10, 1, 25, tzinfo=dt.UTC),
            },
            {
                "source_name": "cboe_most_active",
                "success_count": 1,
                "failure_count": 0,
                "total_latency_ms": 226,
                "rate_limit_hits": 0,
                "last_success_at": dt.datetime(2026, 3, 10, 21, 15, tzinfo=dt.UTC),
            },
        ]
    )

    fake_storage = SimpleNamespace(query=lambda *_args, **_kwargs: rows)

    monkeypatch.setattr(
        health_checks_impl,
        "_load_api_sources_registry",
        lambda: {
            "providers": {
                "yfinance": {"capabilities": {"ohlcv": True, "reference": True}},
                "polygon": {"capabilities": {"ohlcv": True, "reference": True}},
                "sec_edgar": {"capabilities": {"news": True, "filings": True}},
                "cboe_most_active": {"capabilities": {"options": True}},
            }
        },
    )
    monkeypatch.setattr(health_checks_impl, "datetime", _FrozenDateTime)

    sources = health_checks_impl.check_sources(fake_storage)

    assert set(sources) == {"yfinance", "cboe_most_active"}
    assert sources["yfinance"].status == "ok"
    assert sources["cboe_most_active"].status == "ok"


def test_determine_source_status_uses_source_specific_windows(monkeypatch) -> None:
    monkeypatch.setattr(health_checks_impl, "datetime", _FrozenDateTime)

    policy = health_checks_impl.SourceHealthPolicy(
        ok_window=dt.timedelta(hours=30),
        degraded_window=dt.timedelta(hours=48),
    )

    assert (
        health_checks_impl._determine_source_status(
            dt.datetime(2026, 3, 10, 2, 30, tzinfo=dt.UTC),
            100.0,
            policy=policy,
        )
        == "ok"
    )
    assert (
        health_checks_impl._determine_source_status(
            dt.datetime(2026, 3, 9, 15, 0, tzinfo=dt.UTC),
            100.0,
            policy=policy,
        )
        == "degraded"
    )
    assert (
        health_checks_impl._determine_source_status(
            dt.datetime(2026, 3, 9, 1, 0, tzinfo=dt.UTC),
            100.0,
            policy=policy,
        )
        == "down"
    )


def test_source_health_check_explains_stale_provider_with_strong_history(monkeypatch) -> None:
    monkeypatch.setattr(health_checks_impl, "datetime", _FrozenDateTime)

    health = health_checks_impl._build_source_health_check(
        {
            "success_count": 10,
            "failure_count": 0,
            "total_latency_ms": 1000,
            "rate_limit_hits": 0,
            "last_success_at": dt.datetime(2026, 3, 9, 2, 59, tzinfo=dt.UTC),
        },
        health_checks_impl.SourceHealthPolicy(),
    )

    assert health.status == "down"
    assert health.success_rate == 100.0
    assert health.status_reason == "Last good update is older than 24h."


def test_source_health_check_explains_recent_low_success_rate(monkeypatch) -> None:
    monkeypatch.setattr(health_checks_impl, "datetime", _FrozenDateTime)

    health = health_checks_impl._build_source_health_check(
        {
            "success_count": 6,
            "failure_count": 4,
            "total_latency_ms": 900,
            "rate_limit_hits": 0,
            "last_success_at": dt.datetime(2026, 3, 11, 2, 50, tzinfo=dt.UTC),
        },
        health_checks_impl.SourceHealthPolicy(),
    )

    assert health.status == "degraded"
    assert health.success_rate == 60.0
    assert health.status_reason == "Request success rate is below 80%."


def test_standby_source_health_ignores_stale_age_for_backup_only_provider(monkeypatch) -> None:
    monkeypatch.setattr(health_checks_impl, "datetime", _FrozenDateTime)

    health = health_checks_impl._build_source_health_check(
        {
            "success_count": 1,
            "failure_count": 0,
            "total_latency_ms": 175,
            "rate_limit_hits": 0,
            "last_success_at": dt.datetime(2026, 3, 6, 22, 57, tzinfo=dt.UTC),
        },
        health_checks_impl.SourceHealthPolicy(monitoring_mode="standby"),
    )

    assert health.status == "ok"
    assert health.success_rate == 100.0
    assert health.status_reason == "Backup-only source; freshness is checked on demand."
