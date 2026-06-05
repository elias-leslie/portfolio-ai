"""Utilities for building watchlist score timelines and alerts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from .models import WatchlistSnapshot


@dataclass
class ScoreTimelinePoint:
    date: datetime
    overall_score: float
    price_score: float | None = None
    technical_score: float | None = None
    price: float | None = None
    fetched_at: datetime | None = None


def _average(values: Iterable[float | None]) -> float | None:
    numeric = [v for v in values if v is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def build_score_timeline(
    snapshots: Iterable[WatchlistSnapshot],
    *,
    window_days: int = 7,
    now: datetime | None = None,
) -> list[ScoreTimelinePoint]:
    """Aggregate snapshots into a daily timeline."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)

    buckets: dict[datetime, list[WatchlistSnapshot]] = defaultdict(list)

    for snap in snapshots:
        if snap.fetched_at < cutoff:
            continue
        bucket_key = datetime.combine(snap.fetched_at.date(), datetime.min.time(), tzinfo=UTC)
        buckets[bucket_key].append(snap)

    timeline: list[ScoreTimelinePoint] = []
    for bucket_date in sorted(buckets.keys()):
        bucket = buckets[bucket_date]
        if not bucket:
            continue

        overall_avg = _average(snap.overall_score for snap in bucket) or 0.0

        price_scores = (
            (
                cast(dict[str, Any], snap.raw_metrics).get("price", {}).get("score")
                if snap.raw_metrics and isinstance(snap.raw_metrics, dict)
                else None
            )
            for snap in bucket
        )
        technical_scores = (
            (
                cast(dict[str, Any], snap.raw_metrics).get("technical", {}).get("score")
                if snap.raw_metrics and isinstance(snap.raw_metrics, dict)
                else None
            )
            for snap in bucket
        )

        price_avg = _average(price_scores)
        technical_avg = _average(technical_scores)
        close_price_avg = _average(snap.price for snap in bucket)

        last_snapshot = max(bucket, key=lambda s: s.fetched_at)

        timeline.append(
            ScoreTimelinePoint(
                date=bucket_date,
                overall_score=overall_avg,
                price_score=price_avg,
                technical_score=technical_avg,
                price=close_price_avg,
                fetched_at=last_snapshot.fetched_at,
            )
        )

    return timeline


def detect_score_alerts(
    timeline: Iterable[ScoreTimelinePoint],
    *,
    threshold: float = 10.0,
) -> list[dict[str, float]]:
    """Detect alerts where score changed more than threshold between days."""
    points = sorted(timeline, key=lambda pt: pt.date)

    alerts: list[dict[str, float]] = []
    for idx in range(1, len(points)):
        prev = points[idx - 1]
        curr = points[idx]
        delta = curr.overall_score - prev.overall_score
        if abs(delta) >= threshold:
            alerts.append(
                {
                    "date": curr.date.timestamp(),
                    "delta": delta,
                    "previous": prev.overall_score,
                    "current": curr.overall_score,
                }
            )

    return alerts
