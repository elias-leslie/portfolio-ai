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
        "initialize_data_sources",
        lambda: [
            SimpleNamespace(name="yfinance", supports_day=True, supports_reference=True),
            SimpleNamespace(name="polygon", supports_day=True, supports_reference=True),
        ],
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
