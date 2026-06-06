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
ETF_GROWTH = "VUG"  # Vanguard Growth ETF
ETF_TOTAL_MARKET = "VTI"  # Vanguard Total Stock Market ETF

# Overnight / off-hours forward indicators. These are the FUTURES (and crypto)
# that keep trading when U.S. cash markets are shut: CME Globex futures run
# Sun 18:00 ET -> Fri 17:00 ET (daily 17:00-18:00 ET halt) and crypto is 24/7.
# The cash indices (^TNX/^VIX/DX-Y.NYB) only carry the last settle off-hours, so
# the overnight read leans on the live futures instead.
FUTURES_SP500 = "ES=F"  # E-mini S&P 500 futures (overnight equity risk)
FUTURES_NASDAQ = "NQ=F"  # E-mini Nasdaq-100 futures (overnight tech tilt)
FUTURES_CRUDE = "CL=F"  # WTI crude futures (geopolitical / inflation read)
FUTURES_GOLD = "GC=F"  # Gold futures (overnight safe-haven demand)
FUTURES_10Y = "ZN=F"  # 10-Year Treasury Note futures (overnight rates read)
CRYPTO_BTC = "BTC-USD"  # Bitcoin — 24/7 weekend risk-appetite proxy

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
# Includes market indicators, sector ETFs, style ETFs, and prediction drivers.
MAG7_COMPONENT_SYMBOLS: list[str] = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"]

PREDICTION_DRIVER_SYMBOLS: list[str] = [
    INDEX_VIX,
    INDEX_TNX,
    INDEX_DXY,
    ETF_GROWTH,
    ETF_TOTAL_MARKET,
    *MAG7_COMPONENT_SYMBOLS,
    *SECTOR_ETFS.keys(),
]

# Overnight Lean inputs (forward / off-hours read). These are the instruments
# that keep a LIVE print off-hours: equity-index futures, crude, gold and the
# 10Y note future (all on CME Globex, live during the overnight session, closed
# on weekends) plus Bitcoin (24/7 weekend bridge). The cash ^TNX/^VIX/DX-Y.NYB
# are excluded because off-hours they only carry the last settle; the futures on
# the same risk drivers give the honest live read instead. VIX-futures (VX=F) and
# the dollar-index future (DX=F) are NOT served by any configured source, so the
# fear gauge and the dollar are represented as "updates at the open", never faked.
# Order = display order (equities, oil, gold, rates, crypto).
OVERNIGHT_LEAN_SYMBOLS: list[str] = [
    FUTURES_SP500,
    FUTURES_NASDAQ,
    FUTURES_CRUDE,
    FUTURES_GOLD,
    FUTURES_10Y,
    CRYPTO_BTC,
]

ALL_MARKET_SYMBOLS: list[str] = list(
    dict.fromkeys([*MARKET_INDICATORS, *PREDICTION_DRIVER_SYMBOLS, *OVERNIGHT_LEAN_SYMBOLS])
)

# Sector ETF symbols only (for iteration)
SECTOR_ETF_SYMBOLS: list[str] = list(SECTOR_ETFS.keys())
CYCLICAL_SECTOR_SYMBOLS: list[str] = ["XLK", "XLF", "XLY", "XLI", "XLE"]
DEFENSIVE_SECTOR_SYMBOLS: list[str] = ["XLU", "XLP", "XLV"]

PREDICTION_COMPOSITE_FEATURES: list[str] = [
    "MAG7_EQ",
    "SECTOR_EQ",
    "CYCLICAL_DEFENSIVE",
    "GROWTH_MARKET",
]
PREDICTION_DRIVER_FEATURES: list[str] = [
    INDEX_VIX,
    INDEX_TNX,
    INDEX_DXY,
    ETF_GROWTH,
    ETF_TOTAL_MARKET,
    *PREDICTION_COMPOSITE_FEATURES,
    "XLK",
    "XLF",
    "XLE",
    "XLP",
    "XLU",
]

# Canonical target universe for the market-prediction committee v1.
# Keeps the scope explicit and aligned with the approved product contract.
PREDICTION_TARGET_SYMBOLS: list[str] = [BENCHMARK_SPY, *SECTOR_ETF_SYMBOLS]
