"""Unit tests for market history transformers."""

from __future__ import annotations

from datetime import date

from app.api.market_transformers import (
    build_indicator_data_points,
    build_sector_history,
)


def test_build_sector_history_drops_nan_close_rows() -> None:
    rows = [
        (date(2026, 6, 8), 100.0),
        (date(2026, 6, 10), float("nan")),
        (date(2026, 6, 11), 110.0),
    ]

    sector, period_start, period_end = build_sector_history("XLK", "Technology", rows, "", "")

    assert [dp.date for dp in sector.data] == ["2026-06-08", "2026-06-11"]
    assert sector.current_pct == 10.0
    assert period_start == "2026-06-08"
    assert period_end == "2026-06-11"


def test_build_indicator_data_points_drops_nan_close_rows() -> None:
    rows = [
        (date(2026, 6, 10), float("nan")),
        (date(2026, 6, 11), 50.0),
    ]

    data_points, period_start, period_end = build_indicator_data_points(rows, "", "")

    assert data_points == [{"date": "2026-06-11", "close": 50.0, "pct_change": 0.0}]
    assert period_start == "2026-06-11"
    assert period_end == "2026-06-11"
