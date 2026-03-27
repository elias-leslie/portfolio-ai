"""Shared types and constants for core market helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from app.market import intelligence

# Market indicator symbols
CORE_MARKET_SYMBOLS = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]

# Indicator symbol to key mapping
INDICATOR_SYMBOLS: dict[str, str] = {
    "vix": "^VIX",
    "sp500": "^GSPC",
    "tnx": "^TNX",
    "dxy": "DX-Y.NYB",
}

# Enrichment functions by indicator key
INDICATOR_ENRICH_FUNCS: dict[str, object] = {
    "vix": intelligence.enrich_vix_indicator,
    "sp500": intelligence.enrich_sp500_indicator,
    "tnx": intelligence.enrich_tnx_indicator,
    "dxy": intelligence.enrich_dxy_indicator,
}


class OptionsActivityData(TypedDict):
    """Return type for get_options_activity_metrics."""

    near_term_pct: float
    concentration_pct: float
    near_term_signal: str
    concentration_signal: str
    top_sectors: list[dict[str, object]]
    last_updated: str


@dataclass
class CoreMarketData:
    """Core market indicators fetched from price service."""

    sp500_data: object | None
    vix_data: object | None
    tnx_data: object | None
    dxy_data: object | None
    sector_data: dict[str, tuple[float | None, float | None, str | None]]
    current_timestamp: str
