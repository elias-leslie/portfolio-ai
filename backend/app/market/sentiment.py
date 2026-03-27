"""Market sentiment scoring and health calculation.

This module provides functions for calculating market health scores based on
various market indicators (VIX, S&P 500, Treasury yields, Dollar Index).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.constants import SECTOR_ETFS
from app.logging_config import get_logger
from app.market._sentiment_models import ComponentScore, MarketHealthScore, SectorScore
from app.storage import get_storage

# Re-export models so existing importers continue to work
__all__ = ["ComponentScore", "MarketHealthScore", "SectorScore", "calculate_market_health"]

logger = get_logger(__name__)


def calculate_vix_score(vix_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate VIX volatility component score (inverted: low VIX = high score)."""
    if vix_price < 15:
        score, signal, interp = 85, "Bullish", "Low volatility suggests market complacency"
    elif vix_price < 20:
        score, signal, interp = 65, "Bullish", "Normal volatility levels"
    elif vix_price < 25:
        score, signal, interp = 45, "Neutral", "Elevated volatility, some concern"
    elif vix_price < 30:
        score, signal, interp = 30, "Bearish", "High volatility, increased fear"
    else:
        score, signal, interp = 15, "Bearish", "Extreme volatility, market panic"

    return ComponentScore(
        name="Volatility (VIX)",
        score=score,
        value=vix_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _fetch_sp500_percentile(price: float) -> float | None:
    """Query DB for current price's percentile rank within 252-day window."""
    storage = get_storage()
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                WITH recent_prices AS (
                    SELECT close
                    FROM day_bars
                    WHERE symbol = '^GSPC'
                    ORDER BY date DESC
                    LIMIT 252
                )
                SELECT COUNT(*) FILTER (WHERE close <= %s) * 100.0 / COUNT(*) as percentile
                FROM recent_prices
                """,
                (price,),
            )
            row = result.fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except Exception as e:
        logger.debug("sp500_percentile_query_failed", error=str(e))
    return None


def _score_from_percentile(percentile: float) -> tuple[int, str, str]:
    """Map a percentile rank to (score, signal, interpretation)."""
    if percentile >= 80:
        return 75, "Bullish", "Strong market levels"
    if percentile >= 60:
        return 60, "Bullish", "Healthy market levels"
    if percentile >= 40:
        return 50, "Neutral", "Moderate market levels"
    return 40, "Bearish", "Below average levels"


def _score_from_sp500_price(price: float) -> tuple[int, str, str]:
    """Fallback: map absolute S&P 500 price to (score, signal, interpretation)."""
    if price > 6800:
        return 75, "Bullish", "Strong market levels"
    if price > 6400:
        return 60, "Bullish", "Healthy market levels"
    if price > 6000:
        return 50, "Neutral", "Moderate market levels"
    return 40, "Bearish", "Below average levels"


def calculate_sp500_score(sp500_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate S&P 500 level component score using dynamic percentile-based approach.

    Scores based on where current price sits in 252-day rolling window (1 trading year).
    Falls back to price-based thresholds only if historical data unavailable.
    """
    percentile = _fetch_sp500_percentile(sp500_price)
    if percentile is not None:
        score, signal, interp = _score_from_percentile(percentile)
    else:
        score, signal, interp = _score_from_sp500_price(sp500_price)

    return ComponentScore(
        name="S&P 500 Level",
        score=score,
        value=sp500_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def calculate_tnx_score(tnx_yield: float, timestamp: str | None) -> ComponentScore:
    """Calculate 10Y Treasury yield component score (Goldilocks: not too hot, not too cold)."""
    if 3.5 <= tnx_yield <= 4.5:
        score, signal, interp = 60, "Neutral", "Yields in healthy range"
    elif tnx_yield < 3.0:
        score, signal, interp = 45, "Neutral", "Low yields, recession concerns"
    elif tnx_yield < 3.5:
        score, signal, interp = 55, "Neutral", "Moderate yields"
    elif tnx_yield < 5.0:
        score, signal, interp = 45, "Bearish", "Rising yields, tightening concerns"
    else:
        score, signal, interp = 35, "Bearish", "High yields, aggressive tightening"

    return ComponentScore(
        name="10Y Treasury Yield",
        score=score,
        value=tnx_yield,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def calculate_dxy_score(dxy_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate US Dollar Index component score."""
    if dxy_price < 100:
        score, signal, interp = 65, "Bullish", "Weak dollar supports stocks"
    elif dxy_price < 105:
        score, signal, interp = 55, "Neutral", "Dollar at moderate levels"
    else:
        score, signal, interp = 45, "Bearish", "Strong dollar headwind"

    return ComponentScore(
        name="US Dollar (DXY)",
        score=score,
        value=dxy_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _sector_thresholds(changes: list[float]) -> tuple[float, float]:
    """Return (top, bottom) thresholds for Leading/Lagging classification."""
    if len(changes) <= 2:
        return 0.5, -0.5
    sorted_changes = sorted(changes)
    return sorted_changes[int(len(sorted_changes) * 0.67)], sorted_changes[int(len(sorted_changes) * 0.33)]


def _sector_signal(change_pct: float | None, top: float, bottom: float) -> str:
    """Classify a sector change_pct as Leading, Lagging, Neutral, or Unknown."""
    if change_pct is None:
        return "Unknown"
    if change_pct >= top:
        return "Leading"
    if change_pct <= bottom:
        return "Lagging"
    return "Neutral"


def calculate_sector_scores(
    sector_data: dict[str, tuple[float | None, float | None, str | None]],
) -> list[SectorScore]:
    """Calculate sector rotation scores with relative performance signals."""
    changes = [chg for _, (_, chg, _) in sector_data.items() if chg is not None]
    top_threshold, bottom_threshold = _sector_thresholds(changes)

    sectors = [
        SectorScore(
            symbol=symbol,
            name=SECTOR_ETFS.get(symbol, symbol),
            price=price,
            change_pct=change_pct,
            signal=_sector_signal(change_pct, top_threshold, bottom_threshold),
            last_updated=timestamp,
        )
        for symbol, (price, change_pct, timestamp) in sector_data.items()
    ]

    sectors.sort(key=lambda s: s.change_pct if s.change_pct is not None else -999, reverse=True)
    return sectors


def _overall_label(score: int) -> str:
    """Map overall score to human-readable label."""
    if score >= 75:
        return "Very Bullish"
    if score >= 60:
        return "Bullish"
    if score >= 45:
        return "Neutral"
    if score >= 30:
        return "Bearish"
    return "Extreme Fear"


def calculate_market_health(
    vix_price: float | None,
    sp500_price: float | None,
    tnx_yield: float | None,
    dxy_price: float | None,
    sector_data: dict[str, tuple[float | None, float | None, str | None]] | None = None,
    current_timestamp: str | None = None,
) -> MarketHealthScore:
    """Calculate overall market health score from indicators."""
    indicator_funcs = [
        (vix_price, calculate_vix_score),
        (sp500_price, calculate_sp500_score),
        (tnx_yield, calculate_tnx_score),
        (dxy_price, calculate_dxy_score),
    ]
    components = [
        fn(value, current_timestamp)
        for value, fn in indicator_funcs
        if value is not None
    ]

    overall_score = int(sum(c.score for c in components) / len(components)) if components else 50

    return MarketHealthScore(
        overall_score=overall_score,
        overall_label=_overall_label(overall_score),
        components=components,
        sectors=calculate_sector_scores(sector_data) if sector_data else [],
        last_updated=datetime.now(UTC).isoformat(),
    )
