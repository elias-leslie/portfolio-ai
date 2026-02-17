"""Plain-language mappings for market indicators and sectors.

This module provides zero-jargon labels and educational tooltips for all market terminology.
Designed for amateur personal investors who want to understand without technical jargon.
"""

from __future__ import annotations

from typing import TypedDict


class IndicatorLabel(TypedDict):
    """Plain-language label for a market indicator."""

    label: str  # Full label: "Market Volatility"
    short: str  # Short label: "Volatility"
    tooltip: str  # Educational description


class SectorLabel(TypedDict):
    """Plain-language label for a market sector."""

    name: str  # Plain name: "Technology"
    description: str  # What companies: "Apple, Microsoft, NVIDIA, software companies"


# Indicator mappings: symbol → plain language + tooltip
INDICATOR_LABELS: dict[str, IndicatorLabel] = {
    "vix": {
        "label": "Market Volatility",
        "short": "Volatility",
        "tooltip": (
            "Measures how much stocks are bouncing around. "
            "Low volatility (under 15) = calm markets. "
            "High volatility (over 25) = choppy, uncertain markets."
        ),
    },
    "sp500": {
        "label": "S&P 500 Level",
        "short": "S&P 500",
        "tooltip": (
            "The main US stock market index tracking 500 large companies. "
            "Higher levels = stocks are doing well overall. "
            "This is the benchmark most investors watch."
        ),
    },
    "tnx": {
        "label": "Bond Yields",
        "short": "10Y Yield",
        "tooltip": (
            "Interest rates on safe 10-year government bonds. "
            "Higher yields = more competition for stocks (bonds become more attractive). "
            "Moderate yields (3-4.5%) are usually good for stocks."
        ),
    },
    "dxy": {
        "label": "Dollar Strength",
        "short": "Dollar",
        "tooltip": (
            "How strong the US dollar is compared to other currencies. "
            "Strong dollar = harder for US companies selling overseas. "
            "Weak dollar = helps US exports and international stocks."
        ),
    },
    "putcall": {
        "label": "Put/Call Ratio",
        "short": "Put/Call",
        "tooltip": (
            "Ratio of bearish bets (puts) to bullish bets (calls) in the options market. "
            "Above 1.0 = more bearish bets than bullish (fearful sentiment). "
            "0.7-1.0 = balanced sentiment. "
            "Below 0.7 = more bullish bets than bearish (optimistic sentiment)."
        ),
    },
}

# Sector ETF mappings: symbol → plain language name + description
SECTOR_LABELS: dict[str, SectorLabel] = {
    "XLK": {
        "name": "Technology",
        "description": "Apple, Microsoft, NVIDIA, software companies, semiconductors",
    },
    "XLF": {
        "name": "Financials",
        "description": "Banks like JPMorgan, investment firms, insurance companies",
    },
    "XLE": {
        "name": "Energy",
        "description": "Oil and gas companies like Exxon, Chevron, energy producers",
    },
    "XLV": {
        "name": "Healthcare",
        "description": "Hospitals, drug makers like Pfizer, medical device companies",
    },
    "XLY": {
        "name": "Consumer Discretionary",
        "description": "Retailers like Amazon, restaurants, entertainment, things people want",
    },
    "XLP": {
        "name": "Consumer Staples",
        "description": "Groceries, household goods, basic needs like Procter & Gamble",
    },
    "XLI": {
        "name": "Industrials",
        "description": "Manufacturing, construction, aerospace companies like Boeing",
    },
    "XLU": {
        "name": "Utilities",
        "description": "Electric, water, and gas companies providing essential services",
    },
    "XLRE": {
        "name": "Real Estate",
        "description": "Property companies, REITs, commercial and residential real estate",
    },
    "XLB": {
        "name": "Materials",
        "description": "Mining companies, chemicals, raw materials like steel and copper",
    },
    "XLC": {
        "name": "Communication Services",
        "description": "Telecom, media companies, Google, Meta, streaming services",
    },
}


def get_indicator_label(symbol: str) -> IndicatorLabel:
    """Get plain-language label for a market indicator.

    Args:
        symbol: Indicator symbol (e.g., "vix", "sp500", "tnx", "dxy")

    Returns:
        IndicatorLabel with label, short form, and tooltip

    Example:
        >>> label = get_indicator_label("vix")
        >>> print(label["label"])
        Market Volatility
        >>> print(label["tooltip"])
        Measures how much stocks are bouncing around. Low volatility...
    """
    symbol_lower = symbol.lower()
    return INDICATOR_LABELS.get(
        symbol_lower,
        {
            "label": symbol.upper(),
            "short": symbol.upper(),
            "tooltip": f"Market indicator: {symbol.upper()}",
        },
    )


def get_sector_label(symbol: str) -> SectorLabel:
    """Get plain-language label for a sector ETF.

    Args:
        symbol: Sector ETF symbol (e.g., "XLK", "XLF", "XLE")

    Returns:
        SectorLabel with name and description

    Example:
        >>> label = get_sector_label("XLK")
        >>> print(label["name"])
        Technology
        >>> print(label["description"])
        Apple, Microsoft, NVIDIA, software companies, semiconductors
    """
    symbol_upper = symbol.upper()
    return SECTOR_LABELS.get(
        symbol_upper,
        {
            "name": symbol_upper,
            "description": f"Sector: {symbol_upper}",
        },
    )

