"""Unit tests for watchlist score history functionality (FEAT-125)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.watchlist.history import (
    ScoreTimelinePoint,
    build_score_timeline,
    detect_score_alerts,
)
from app.watchlist.models import WatchlistSnapshot


class TestBuildScoreTimeline:
    """Tests for build_score_timeline function."""

    @pytest.fixture
    def sample_snapshots(self) -> list[WatchlistSnapshot]:
        """Create sample snapshots for testing."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        return [
            WatchlistSnapshot(
                item_id="item-1",
                fetched_at=now - timedelta(hours=2),
                price=180.0,
                overall_score=75.0,
                technical_score=80.0,
                raw_metrics={
                    "price": {"score": 70.0},
                    "technical": {"score": 80.0},
                },
            ),
            WatchlistSnapshot(
                item_id="item-1",
                fetched_at=now - timedelta(hours=1),
                price=182.0,
                overall_score=77.0,
                technical_score=82.0,
                raw_metrics={
                    "price": {"score": 72.0},
                    "technical": {"score": 82.0},
                },
            ),
            WatchlistSnapshot(
                item_id="item-1",
                fetched_at=now - timedelta(days=2),
                price=175.0,
                overall_score=60.0,
                technical_score=62.0,
                raw_metrics={
                    "price": {"score": 58.0},
                    "technical": {"score": 62.0},
                },
            ),
        ]

    def test_groups_snapshots_by_day(self, sample_snapshots: list[WatchlistSnapshot]) -> None:
        """Test that snapshots are grouped by day."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        timeline = build_score_timeline(sample_snapshots, window_days=7, now=now)

        # Should have 2 days: Dec 10 (2 snapshots) and Dec 8 (1 snapshot)
        assert len(timeline) == 2

    def test_calculates_daily_averages(self, sample_snapshots: list[WatchlistSnapshot]) -> None:
        """Test that daily averages are calculated correctly."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        timeline = build_score_timeline(sample_snapshots, window_days=7, now=now)

        # Get today's point (2 snapshots: 75.0 and 77.0)
        today_point = max(timeline, key=lambda pt: pt.date)
        expected_overall = (75.0 + 77.0) / 2
        assert round(today_point.overall_score, 2) == round(expected_overall, 2)

    def test_extracts_price_and_technical_scores(
        self, sample_snapshots: list[WatchlistSnapshot]
    ) -> None:
        """Test that price and technical scores are extracted from raw_metrics."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        timeline = build_score_timeline(sample_snapshots, window_days=7, now=now)

        today_point = max(timeline, key=lambda pt: pt.date)

        # Price average: (70.0 + 72.0) / 2 = 71.0
        assert today_point.price_score is not None
        assert round(today_point.price_score, 2) == 71.0

        # Technical average: (80.0 + 82.0) / 2 = 81.0
        assert today_point.technical_score is not None
        assert round(today_point.technical_score, 2) == 81.0

    def test_respects_window_days_filter(
        self, sample_snapshots: list[WatchlistSnapshot]
    ) -> None:
        """Test that only snapshots within window_days are included."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)

        # Use 1-day window - should only include Dec 10
        timeline = build_score_timeline(sample_snapshots, window_days=1, now=now)
        assert len(timeline) == 1

        # Use 7-day window - should include both Dec 10 and Dec 8
        timeline = build_score_timeline(sample_snapshots, window_days=7, now=now)
        assert len(timeline) == 2

    def test_handles_empty_snapshots(self) -> None:
        """Test that empty snapshot list returns empty timeline."""
        timeline = build_score_timeline([])
        assert len(timeline) == 0

    def test_handles_empty_raw_metrics(self) -> None:
        """Test that snapshots with empty raw_metrics don't cause errors."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        snapshots = [
            WatchlistSnapshot(
                item_id="item-1",
                fetched_at=now,
                price=180.0,
                overall_score=75.0,
                technical_score=80.0,
                raw_metrics={},  # Empty raw metrics (no price/technical keys)
            ),
        ]

        timeline = build_score_timeline(snapshots, window_days=7, now=now)
        assert len(timeline) == 1

        point = timeline[0]
        assert point.overall_score == 75.0
        assert point.price_score is None  # Should handle gracefully
        assert point.technical_score is None

    def test_handles_missing_score_keys_in_raw_metrics(self) -> None:
        """Test that missing score keys in raw_metrics are handled."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        snapshots = [
            WatchlistSnapshot(
                item_id="item-1",
                fetched_at=now,
                price=180.0,
                overall_score=75.0,
                technical_score=80.0,
                raw_metrics={"price": {}},  # Missing 'score' key
            ),
        ]

        timeline = build_score_timeline(snapshots, window_days=7, now=now)
        assert len(timeline) == 1

        point = timeline[0]
        assert point.price_score is None

    def test_uses_latest_snapshot_fetched_at_for_bucket(
        self, sample_snapshots: list[WatchlistSnapshot]
    ) -> None:
        """Test that the latest fetched_at is used for each day bucket."""
        now = datetime(2025, 12, 10, 12, 0, 0, tzinfo=UTC)
        timeline = build_score_timeline(sample_snapshots, window_days=7, now=now)

        today_point = max(timeline, key=lambda pt: pt.date)

        # Latest snapshot for Dec 10 is at now - 1 hour
        assert today_point.fetched_at == now - timedelta(hours=1)


class TestDetectScoreAlerts:
    """Tests for detect_score_alerts function."""

    def test_detects_large_positive_swing(self) -> None:
        """Test that large positive score swings are detected."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=60.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
            ),
        ]

        alerts = detect_score_alerts(timeline, threshold=10.0)
        assert len(alerts) == 1

        alert = alerts[0]
        assert alert["delta"] == pytest.approx(15.0, rel=1e-6)
        assert alert["previous"] == 60.0
        assert alert["current"] == 75.0

    def test_detects_large_negative_swing(self) -> None:
        """Test that large negative score swings are detected."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=85.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=70.0,
            ),
        ]

        alerts = detect_score_alerts(timeline, threshold=10.0)
        assert len(alerts) == 1

        alert = alerts[0]
        assert alert["delta"] == pytest.approx(-15.0, rel=1e-6)

    def test_ignores_swings_below_threshold(self) -> None:
        """Test that swings below threshold are ignored."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=70.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
            ),
        ]

        alerts = detect_score_alerts(timeline, threshold=10.0)
        assert len(alerts) == 0  # Delta is only 5.0

    def test_handles_empty_timeline(self) -> None:
        """Test that empty timeline returns no alerts."""
        alerts = detect_score_alerts([])
        assert len(alerts) == 0

    def test_handles_single_point_timeline(self) -> None:
        """Test that single-point timeline returns no alerts."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
            ),
        ]
        alerts = detect_score_alerts(timeline)
        assert len(alerts) == 0

    def test_detects_multiple_alerts(self) -> None:
        """Test that multiple swings are all detected."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 7, 0, 0, 0, tzinfo=UTC),
                overall_score=60.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,  # +15 delta
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=85.0,  # +10 delta
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 10, 0, 0, 0, tzinfo=UTC),
                overall_score=70.0,  # -15 delta
            ),
        ]

        alerts = detect_score_alerts(timeline, threshold=10.0)
        assert len(alerts) == 3  # Three swings >= 10.0

    def test_custom_threshold(self) -> None:
        """Test that custom threshold values work correctly."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=60.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,  # +15 delta
            ),
        ]

        # With threshold=20.0, should not trigger
        alerts = detect_score_alerts(timeline, threshold=20.0)
        assert len(alerts) == 0

        # With threshold=15.0, should trigger
        alerts = detect_score_alerts(timeline, threshold=15.0)
        assert len(alerts) == 1

    def test_alert_contains_timestamp(self) -> None:
        """Test that alerts include timestamp in the expected format."""
        timeline = [
            ScoreTimelinePoint(
                date=datetime(2025, 12, 8, 0, 0, 0, tzinfo=UTC),
                overall_score=60.0,
            ),
            ScoreTimelinePoint(
                date=datetime(2025, 12, 9, 0, 0, 0, tzinfo=UTC),
                overall_score=75.0,
            ),
        ]

        alerts = detect_score_alerts(timeline, threshold=10.0)
        alert = alerts[0]

        # Check that date is present as timestamp
        assert "date" in alert
        assert isinstance(alert["date"], float)  # Unix timestamp


class TestScoreTimelinePoint:
    """Tests for ScoreTimelinePoint dataclass."""

    def test_creates_with_required_fields(self) -> None:
        """Test that ScoreTimelinePoint can be created with required fields."""
        now = datetime.now(UTC)
        point = ScoreTimelinePoint(date=now, overall_score=75.0)

        assert point.date == now
        assert point.overall_score == 75.0
        assert point.price_score is None
        assert point.technical_score is None
        assert point.fetched_at is None

    def test_creates_with_all_fields(self) -> None:
        """Test that ScoreTimelinePoint can be created with all fields."""
        now = datetime.now(UTC)
        fetched = now - timedelta(hours=1)

        point = ScoreTimelinePoint(
            date=now,
            overall_score=75.0,
            price_score=70.0,
            technical_score=80.0,
            fetched_at=fetched,
        )

        assert point.date == now
        assert point.overall_score == 75.0
        assert point.price_score == 70.0
        assert point.technical_score == 80.0
        assert point.fetched_at == fetched
