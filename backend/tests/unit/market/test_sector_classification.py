"""Tests for canonical market sector classification."""

from __future__ import annotations

from app.market.intelligence import group_sectors_by_performance
from app.market.sentiment import calculate_sector_scores


def test_sector_rotation_grouping_matches_market_health_signals() -> None:
    """Market health and sector rotation should not disagree on leaders."""
    sector_data = {
        "XLE": (100.0, 0.9, "2026-04-10T16:00:00Z"),
        "XLF": (100.0, 0.8, "2026-04-10T16:00:00Z"),
        "XLU": (100.0, 0.7, "2026-04-10T16:00:00Z"),
        "XLK": (100.0, 0.6, "2026-04-10T16:00:00Z"),
        "XLY": (100.0, 0.2, "2026-04-10T16:00:00Z"),
        "XLP": (100.0, 0.1, "2026-04-10T16:00:00Z"),
        "XLI": (100.0, 0.0, "2026-04-10T16:00:00Z"),
        "XLV": (100.0, -0.1, "2026-04-10T16:00:00Z"),
        "XLRE": (100.0, -0.2, "2026-04-10T16:00:00Z"),
        "XLB": (100.0, -0.3, "2026-04-10T16:00:00Z"),
        "XLC": (100.0, -0.4, "2026-04-10T16:00:00Z"),
    }

    market_health_signals = {
        sector.symbol: sector.signal for sector in calculate_sector_scores(sector_data)
    }
    leading, neutral, lagging = group_sectors_by_performance(
        [(symbol, *values) for symbol, values in sector_data.items()]
    )
    rotation_signals = {
        sector.symbol: sector.signal for sector in [*leading, *neutral, *lagging]
    }

    assert rotation_signals == market_health_signals
    assert "XLK" in {sector.symbol for sector in leading}
    assert "XLK" not in {sector.symbol for sector in neutral}
