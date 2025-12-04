"""Feature engineering pipeline for ML models (GAP-050).

Transforms raw market data into ML-ready features:
- Price-based features (returns, lags, z-scores)
- Technical features (normalized indicators)
- Fundamental features (ratios, rankings)
- Cross-sectional features (sector ranks)

Features are designed to be stationary and normalized for ML models.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


@dataclass
class FeatureSet:
    """Container for computed features."""

    symbol: str
    date: date
    features: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def calculate_returns(prices: list[float], periods: list[int] | None = None) -> dict[str, float]:
    """Calculate returns over various periods.

    Args:
        prices: List of prices (oldest to newest)
        periods: List of lookback periods

    Returns:
        Dict mapping feature name to value
    """
    if periods is None:
        periods = [1, 5, 20, 60]

    features = {}

    for period in periods:
        if len(prices) > period:
            ret = (prices[-1] - prices[-1 - period]) / prices[-1 - period]
            features[f"return_{period}d"] = ret
        else:
            features[f"return_{period}d"] = 0.0

    return features


def calculate_momentum_features(prices: list[float]) -> dict[str, float]:
    """Calculate momentum-based features.

    Features:
    - mom_12_1: 12-month return excluding most recent month (classic momentum)
    - mom_rank: Cross-sectional momentum rank (needs to be calculated across universe)
    - acceleration: Change in momentum

    Args:
        prices: List of daily prices (oldest to newest)

    Returns:
        Dict of momentum features
    """
    features = {}

    # 12-1 momentum (skip most recent month)
    if len(prices) > 252:
        price_12m_ago = prices[-252]
        price_1m_ago = prices[-21]
        mom_12_1 = (price_1m_ago - price_12m_ago) / price_12m_ago if price_12m_ago > 0 else 0
        features["mom_12_1"] = mom_12_1
    else:
        features["mom_12_1"] = 0.0

    # 6-month momentum
    if len(prices) > 126:
        mom_6m = (prices[-1] - prices[-126]) / prices[-126] if prices[-126] > 0 else 0
        features["mom_6m"] = mom_6m
    else:
        features["mom_6m"] = 0.0

    # Momentum acceleration (change in 1-month momentum)
    if len(prices) > 42:
        mom_1m_now = (prices[-1] - prices[-21]) / prices[-21] if prices[-21] > 0 else 0
        mom_1m_prev = (prices[-21] - prices[-42]) / prices[-42] if prices[-42] > 0 else 0
        features["mom_acceleration"] = mom_1m_now - mom_1m_prev
    else:
        features["mom_acceleration"] = 0.0

    return features


def calculate_volatility_features(returns: list[float]) -> dict[str, float]:
    """Calculate volatility-based features.

    Args:
        returns: List of daily returns

    Returns:
        Dict of volatility features
    """
    features = {}

    # Short-term volatility (20-day)
    if len(returns) >= 20:
        recent_returns = returns[-20:]
        mean = sum(recent_returns) / len(recent_returns)
        variance = sum((r - mean) ** 2 for r in recent_returns) / len(recent_returns)
        vol_20d = math.sqrt(variance) * math.sqrt(252)  # Annualized
        features["vol_20d"] = vol_20d
    else:
        features["vol_20d"] = 0.0

    # Medium-term volatility (60-day)
    if len(returns) >= 60:
        recent_returns = returns[-60:]
        mean = sum(recent_returns) / len(recent_returns)
        variance = sum((r - mean) ** 2 for r in recent_returns) / len(recent_returns)
        vol_60d = math.sqrt(variance) * math.sqrt(252)
        features["vol_60d"] = vol_60d
    else:
        features["vol_60d"] = 0.0

    # Volatility ratio (short / long term)
    if features["vol_60d"] > 0:
        features["vol_ratio"] = features["vol_20d"] / features["vol_60d"]
    else:
        features["vol_ratio"] = 1.0

    # Realized vs implied vol could be added here if options data available

    return features


def calculate_zscore(values: list[float], lookback: int = 20) -> float:
    """Calculate z-score of most recent value.

    Args:
        values: List of values
        lookback: Lookback period for mean/std

    Returns:
        Z-score
    """
    if len(values) < lookback:
        return 0.0

    recent = values[-lookback:]
    mean = sum(recent) / len(recent)
    variance = sum((v - mean) ** 2 for v in recent) / len(recent)
    std = math.sqrt(variance) if variance > 0 else 0

    if std == 0:
        return 0.0

    return (values[-1] - mean) / std


def calculate_technical_features(
    prices: list[float],
    volumes: list[float],
) -> dict[str, float]:
    """Calculate technical analysis features (normalized).

    Args:
        prices: List of daily prices
        volumes: List of daily volumes

    Returns:
        Dict of technical features (z-scored or normalized)
    """
    features = {}

    # Price relative to moving averages (normalized)
    for period in [20, 50, 200]:
        if len(prices) >= period:
            ma = sum(prices[-period:]) / period
            features[f"price_to_ma{period}"] = (prices[-1] / ma - 1) if ma > 0 else 0
        else:
            features[f"price_to_ma{period}"] = 0.0

    # Volume z-score
    if len(volumes) >= 20:
        features["volume_zscore"] = calculate_zscore(volumes, 20)
    else:
        features["volume_zscore"] = 0.0

    # Relative volume (current / 20-day average)
    if len(volumes) >= 20:
        avg_vol = sum(volumes[-20:]) / 20
        features["rvol"] = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
    else:
        features["rvol"] = 1.0

    # Price percentile (where is current price in 52-week range)
    if len(prices) >= 252:
        min_52w = min(prices[-252:])
        max_52w = max(prices[-252:])
        price_range = max_52w - min_52w
        if price_range > 0:
            features["price_percentile_52w"] = (prices[-1] - min_52w) / price_range
        else:
            features["price_percentile_52w"] = 0.5
    else:
        features["price_percentile_52w"] = 0.5

    # Gap feature (overnight gap as % of price)
    # Would need OHLC data for proper implementation

    return features


def calculate_fundamental_features(
    fundamentals: dict[str, Any] | None,
) -> dict[str, float]:
    """Calculate fundamental features (normalized).

    Converts raw fundamental data to ML-ready features.

    Args:
        fundamentals: Dict with keys like pe_ratio, pb_ratio, etc.

    Returns:
        Dict of fundamental features
    """
    features = {}

    if fundamentals is None:
        return {
            "pe_zscore": 0.0,
            "pb_zscore": 0.0,
            "roe": 0.0,
            "profit_margin": 0.0,
            "debt_to_equity": 0.0,
            "earnings_yield": 0.0,
        }

    # Earnings yield (inverse of P/E, handles negative P/E better)
    pe = fundamentals.get("pe_ratio", 0)
    if pe and pe > 0:
        features["earnings_yield"] = 1 / pe
    else:
        features["earnings_yield"] = 0.0

    # Book yield (inverse of P/B)
    pb = fundamentals.get("pb_ratio", 0)
    if pb and pb > 0:
        features["book_yield"] = 1 / pb
    else:
        features["book_yield"] = 0.0

    # Quality metrics (raw values, should be z-scored cross-sectionally)
    features["roe"] = fundamentals.get("roe", 0) or 0
    features["profit_margin"] = fundamentals.get("profit_margin", 0) or 0

    # Leverage (capped to handle outliers)
    debt_equity = fundamentals.get("debt_to_equity", 0) or 0
    features["debt_to_equity"] = min(debt_equity, 5.0)  # Cap at 5x

    # Revenue growth
    features["revenue_growth"] = fundamentals.get("revenue_growth", 0) or 0

    return features


def generate_features_for_symbol(
    storage: PortfolioStorage,
    symbol: str,
    as_of_date: date | None = None,
) -> FeatureSet:
    """Generate all features for a single symbol.

    Args:
        storage: Database storage instance
        symbol: Stock ticker
        as_of_date: Date to calculate features for (default: today)

    Returns:
        FeatureSet with all computed features
    """
    if as_of_date is None:
        as_of_date = date.today()

    features: dict[str, float] = {}

    # Fetch price data
    price_query = """
        SELECT date, close, volume
        FROM day_bars
        WHERE symbol = %s
          AND date <= %s
        ORDER BY date DESC
        LIMIT 300
    """
    result = storage.query(price_query, [symbol, str(as_of_date)])

    if result.is_empty():
        return FeatureSet(
            symbol=symbol,
            date=as_of_date,
            features={},
            metadata={"error": "No price data"},
        )

    # Extract prices and volumes (reverse to get oldest->newest)
    rows = result.to_dicts()
    prices = [row["close"] for row in reversed(rows)]
    volumes = [row["volume"] for row in reversed(rows)]

    # Calculate returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

    # Generate all feature sets
    features.update(calculate_returns(prices))
    features.update(calculate_momentum_features(prices))
    features.update(calculate_volatility_features(returns))
    features.update(calculate_technical_features(prices, volumes))

    # Fetch fundamentals if available
    fund_query = """
        SELECT data
        FROM reference_cache
        WHERE symbol = %s
          AND data_type = 'fundamentals'
        ORDER BY cached_at DESC
        LIMIT 1
    """
    fund_result = storage.query(fund_query, [symbol])
    fundamentals = None
    if not fund_result.is_empty():
        row = fund_result.to_dicts()[0]
        fundamentals = row.get("data") if row else None

    features.update(calculate_fundamental_features(fundamentals))

    logger.debug(
        "features_generated",
        symbol=symbol,
        feature_count=len(features),
        date=str(as_of_date),
    )

    return FeatureSet(
        symbol=symbol,
        date=as_of_date,
        features=features,
        metadata={
            "price_observations": len(prices),
            "return_observations": len(returns),
        },
    )


def generate_feature_matrix(
    storage: PortfolioStorage,
    symbols: list[str],
    as_of_date: date | None = None,
) -> list[FeatureSet]:
    """Generate features for multiple symbols.

    Args:
        storage: Database storage instance
        symbols: List of tickers
        as_of_date: Date to calculate features for

    Returns:
        List of FeatureSet objects
    """
    results = []
    for symbol in symbols:
        feature_set = generate_features_for_symbol(storage, symbol, as_of_date)
        results.append(feature_set)

    logger.info(
        "feature_matrix_generated",
        symbols=len(symbols),
        successful=len([r for r in results if r.features]),
    )

    return results


def get_feature_names() -> list[str]:
    """Return list of all feature names generated by this module.

    Useful for model training to know expected features.
    """
    return [
        # Returns
        "return_1d",
        "return_5d",
        "return_20d",
        "return_60d",
        # Momentum
        "mom_12_1",
        "mom_6m",
        "mom_acceleration",
        # Volatility
        "vol_20d",
        "vol_60d",
        "vol_ratio",
        # Technical
        "price_to_ma20",
        "price_to_ma50",
        "price_to_ma200",
        "volume_zscore",
        "rvol",
        "price_percentile_52w",
        # Fundamental
        "earnings_yield",
        "book_yield",
        "roe",
        "profit_margin",
        "debt_to_equity",
        "revenue_growth",
    ]
