"""Centralized market symbol constants.

Single source of truth for all market indicators, sector ETFs, and benchmark symbols.
Import from app.constants instead of defining these inline.

Usage:
    from app.constants import SECTOR_ETFS, MARKET_INDICATORS, ALL_MARKET_SYMBOLS
"""

from __future__ import annotations

# =============================================================================
# MARKET BENCHMARK SYMBOLS
# =============================================================================

# Primary S&P 500 ETF - used for RSI calculations, benchmark comparisons
BENCHMARK_SPY = "SPY"

# Market indices
INDEX_SP500 = "^GSPC"  # S&P 500 Index
INDEX_VIX = "^VIX"  # CBOE Volatility Index
INDEX_TNX = "^TNX"  # 10-Year Treasury Note Yield
INDEX_DXY = "DX-Y.NYB"  # US Dollar Index

# Combined market indicators list
MARKET_INDICATORS: list[str] = [
    BENCHMARK_SPY,
    INDEX_SP500,
    INDEX_VIX,
    INDEX_TNX,
    INDEX_DXY,
]

# =============================================================================
# SECTOR ETFs (S&P 500 GICS Sectors)
# =============================================================================

# Sector ETF symbols mapped to human-readable names
SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication Services",
}

# Extended sector labels with descriptions for UI display
SECTOR_LABELS: dict[str, dict[str, str]] = {
    "XLK": {
        "name": "Technology",
        "description": "Software, hardware, semiconductors, IT services",
    },
    "XLF": {
        "name": "Financials",
        "description": "Banks, insurance, diversified financials, real estate services",
    },
    "XLE": {
        "name": "Energy",
        "description": "Oil, gas, consumable fuels, energy equipment",
    },
    "XLV": {
        "name": "Healthcare",
        "description": "Pharmaceuticals, biotech, healthcare equipment, providers",
    },
    "XLY": {
        "name": "Consumer Discretionary",
        "description": "Retail, automobiles, leisure, consumer durables",
    },
    "XLP": {
        "name": "Consumer Staples",
        "description": "Food, beverages, tobacco, household products",
    },
    "XLI": {
        "name": "Industrials",
        "description": "Aerospace, defense, machinery, construction, transportation",
    },
    "XLU": {
        "name": "Utilities",
        "description": "Electric, gas, water utilities, independent power producers",
    },
    "XLRE": {
        "name": "Real Estate",
        "description": "REITs, real estate management and development",
    },
    "XLB": {
        "name": "Materials",
        "description": "Chemicals, construction materials, metals, mining, packaging",
    },
    "XLC": {
        "name": "Communication Services",
        "description": "Telecom, media, entertainment, interactive services",
    },
}

# =============================================================================
# COMBINED SYMBOL LISTS
# =============================================================================

# All market symbols for historical data ingestion
# Includes both market indicators and sector ETFs
ALL_MARKET_SYMBOLS: list[str] = MARKET_INDICATORS + list(SECTOR_ETFS.keys())

# Sector ETF symbols only (for iteration)
SECTOR_ETF_SYMBOLS: list[str] = list(SECTOR_ETFS.keys())

# Canonical target universe for the market-prediction committee v1.
# Keeps the scope explicit and aligned with the approved product contract.
PREDICTION_TARGET_SYMBOLS: list[str] = [BENCHMARK_SPY, *SECTOR_ETF_SYMBOLS]
