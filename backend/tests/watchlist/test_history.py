from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.watchlist.history import build_score_timeline, detect_score_alerts
from app.watchlist.models import WatchlistSnapshot


def make_snapshot(
    *, item_id: str, fetched_at: datetime, overall: float, price: float, technical: float
) -> WatchlistSnapshot:
    return WatchlistSnapshot(
        item_id=item_id,
        fetched_at=fetched_at,
        price=180.0,
        change_pct=1.0,
        overall_score=overall,
        technical_score=technical,
        raw_metrics={
            "price": {"score": price},
            "technical": {"score": technical},
        },
    )


def test_build_score_timeline_groups_by_day() -> None:
    # Use fixed time at noon UTC to avoid day boundary issues
    now = datetime(2025, 11, 3, 12, 0, 0, tzinfo=UTC)
    snapshots = [
        make_snapshot(
            item_id="item-1",
            fetched_at=now - timedelta(hours=2),  # Nov 3, 10:00 UTC
            overall=75.0,
            price=70.0,
            technical=80.0,
        ),
        make_snapshot(
            item_id="item-1",
            fetched_at=now - timedelta(hours=1),  # Nov 3, 11:00 UTC
            overall=77.0,
            price=72.0,
            technical=82.0,
        ),
        make_snapshot(
            item_id="item-1",
            fetched_at=now - timedelta(days=2),  # Nov 1, 12:00 UTC
            overall=60.0,
            price=58.0,
            technical=62.0,
        ),
    ]

    timeline = build_score_timeline(snapshots, window_days=7, now=now)

    assert len(timeline) == 2  # Nov 3 (2 snapshots) and Nov 1 (1 snapshot)
    today_point = max(timeline, key=lambda point: point.date)
    assert round(today_point.overall_score, 2) == 76.0
    assert round(today_point.price_score or 0, 2) == 71.0
    assert round(today_point.technical_score or 0, 2) == 81.0


def test_detect_score_alerts_flags_large_swings() -> None:
    now = datetime.now(UTC)
    timeline = build_score_timeline(
        [
            make_snapshot(
                item_id="item-1",
                fetched_at=now - timedelta(days=2),
                overall=85.0,
                price=80.0,
                technical=90.0,
            ),
            make_snapshot(
                item_id="item-1",
                fetched_at=now - timedelta(days=1),
                overall=70.0,
                price=68.0,
                technical=72.0,
            ),
        ],
        window_days=7,
        now=now,
    )

    alerts = detect_score_alerts(timeline, threshold=10.0)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["delta"] == pytest.approx(-15.0, rel=1e-6)
