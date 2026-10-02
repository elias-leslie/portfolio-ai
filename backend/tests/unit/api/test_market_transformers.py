"""Unit tests for market history transformers."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

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


@pytest.mark.parametrize(
    ("rows", "period_start", "period_end", "expected", "expected_start", "expected_end"),
    [
        ([], "", "", [], "", ""),
        ([], "seed-start", "seed-end", [], "seed-start", "seed-end"),
        (
            [(None, 50), ("2026-06-01", 60), (date(2026, 6, 2), None),
             (date(2026, 6, 3), float("inf")), (date(2026, 6, 4), float("-inf")),
             (date(2026, 6, 5), float("nan"))],
            "seed-start", "seed-end", [], "seed-start", "seed-end",
        ),
        (
            [(date(2026, 6, 1), 3), (date(2026, 6, 2), "4")],
            "", "",
            [{"date": "2026-06-01", "close": 3.0, "pct_change": 0.0},
             {"date": "2026-06-02", "close": 4.0, "pct_change": 33.33}],
            "2026-06-01", "2026-06-02",
        ),
        (
            [(date(2026, 6, 1), 0), (date(2026, 6, 2), 100)],
            "seed-start", "seed-end",
            [{"date": "2026-06-01", "close": 0.0, "pct_change": 0.0},
             {"date": "2026-06-02", "close": 100.0, "pct_change": 0.0}],
            "seed-start", "2026-06-02",
        ),
        (
            [(date(2026, 6, 2), -100), (date(2026, 6, 1), -50)],
            "", "",
            [{"date": "2026-06-02", "close": -100.0, "pct_change": -0.0},
             {"date": "2026-06-01", "close": -50.0, "pct_change": -50.0}],
            "2026-06-02", "2026-06-01",
        ),
        (
            [(datetime(2026, 6, 1, 20, tzinfo=UTC), 100)],
            "", "",
            [{"date": "2026-06-01T20:00:00+00:00", "close": 100.0, "pct_change": 0.0}],
            "2026-06-01T20:00:00+00:00", "2026-06-01T20:00:00+00:00",
        ),
    ],
)
def test_history_builders_preserve_data_and_periods(
    rows, period_start, period_end, expected, expected_start, expected_end,
) -> None:
    original_rows = list(rows)
    points, start, end = build_indicator_data_points(rows, period_start, period_end)
    assert (points, start, end) == (expected, expected_start, expected_end)

    sector, start, end = build_sector_history("XLK", "Technology", rows, period_start, period_end)
    assert sector.model_dump() == {
        "symbol": "XLK", "name": "Technology", "data": expected,
        "current_pct": expected[-1]["pct_change"] if expected else 0.0,
    }
    assert (start, end) == (expected_start, expected_end)
    assert rows == original_rows


@pytest.mark.parametrize("builder", [build_indicator_data_points, build_sector_history])
def test_history_builders_preserve_invalid_number_errors(builder) -> None:
    rows = [(date(2026, 6, 1), "invalid-price")]
    args = ("XLK", "Technology", rows, "", "") if builder is build_sector_history else (rows, "", "")
    with pytest.raises(ValueError):
        builder(*args)
