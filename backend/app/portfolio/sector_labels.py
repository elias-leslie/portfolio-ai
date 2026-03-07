"""Shared sector/category labels for portfolio-facing symbol classification."""

from __future__ import annotations

from app.analytics._sector_ticker_map import TICKER_SECTOR_MAP
from app.constants import SECTOR_ETFS

FUND_CATEGORY_LABELS: dict[str, str] = {
    "SPY": "Broad Market Index",
    "VOO": "Broad Market Index",
    "VTI": "Broad Market Index",
    "QQQ": "Growth Index Fund",
    "IWM": "Small-Cap Index Fund",
    "DIA": "Large-Cap Index Fund",
    "AGG": "Bond Fund",
    "BND": "Bond Fund",
    "VUG": "Large-Cap Growth Fund",
    "VTV": "Large-Cap Value Fund",
}


def resolve_sector_label(symbol: str, sector: str | None) -> str | None:
    """Return the best available user-facing sector/category label for a symbol."""
    if sector:
        normalized = sector.strip()
        if normalized:
            return normalized

    normalized_symbol = symbol.upper()
    if normalized_symbol in SECTOR_ETFS:
        return SECTOR_ETFS[normalized_symbol]

    sector_etf = TICKER_SECTOR_MAP.get(normalized_symbol)
    if sector_etf:
        return SECTOR_ETFS.get(sector_etf)

    return FUND_CATEGORY_LABELS.get(normalized_symbol)
