"""Earnings surprise data fetching from Finnhub (internal helper)."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal

import requests

from app.logging_config import get_logger

from .earnings_surprise_types import SMALL_BEAT_PCT, SMALL_MISS_PCT, EarningsSurprise

logger = get_logger(__name__)


def _parse_fiscal_quarter(period: str) -> str | None:
    """Parse period string (e.g. '2024-09-30') into fiscal quarter (e.g. 'Q3 2024')."""
    if not period:
        return None
    try:
        period_date = datetime.strptime(period, "%Y-%m-%d").date()
        quarter = (period_date.month - 1) // 3 + 1
        return f"Q{quarter} {period_date.year}"
    except (ValueError, TypeError):
        return None


def _determine_direction(surprise_pct: float | None, eps_estimate: float | None, eps_actual: float | None) -> tuple[float | None, str]:
    """Compute (surprise_pct, direction) from raw API fields."""
    if surprise_pct is None and eps_estimate and eps_actual and abs(eps_estimate) > 0.001:
        surprise_pct = (eps_actual - eps_estimate) / abs(eps_estimate) * 100

    if surprise_pct is not None:
        if surprise_pct > SMALL_BEAT_PCT:
            direction = "beat"
        elif surprise_pct < SMALL_MISS_PCT:
            direction = "miss"
        else:
            direction = "inline"
    else:
        direction = "inline"

    return surprise_pct, direction


def _parse_item(symbol: str, item: dict) -> EarningsSurprise | None:  # type: ignore[type-arg]
    """Parse a single Finnhub earnings item into an EarningsSurprise. Returns None if no actual."""
    if item.get("actual") is None:
        return None

    eps_estimate = item.get("estimate")
    eps_actual = item.get("actual")
    raw_surprise_pct = item.get("surprisePercent")
    period = item.get("period", "")

    surprise_pct, direction = _determine_direction(raw_surprise_pct, eps_estimate, eps_actual)

    earnings_date = datetime.strptime(period, "%Y-%m-%d").date() if period else date.today()

    return EarningsSurprise(
        symbol=symbol,
        earnings_date=earnings_date,
        fiscal_quarter=_parse_fiscal_quarter(period),
        eps_estimate=Decimal(str(eps_estimate)) if eps_estimate else None,
        eps_actual=Decimal(str(eps_actual)) if eps_actual else None,
        surprise_pct=Decimal(str(surprise_pct)) if surprise_pct else None,
        surprise_direction=direction,
    )


def fetch_earnings_surprises_from_finnhub(
    symbol: str,
    limit: int = 4,
) -> list[EarningsSurprise]:
    """Fetch earnings surprises from Finnhub API.

    Args:
        symbol: Stock symbol
        limit: Maximum number of recent earnings to fetch

    Returns:
        List of EarningsSurprise records (most recent first)
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        logger.warning("finnhub_api_key_missing", symbol=symbol)
        return []

    try:
        url = "https://finnhub.io/api/v1/stock/earnings"
        params = {"symbol": symbol, "token": api_key}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        surprises = [
            parsed
            for item in response.json()[:limit]
            if (parsed := _parse_item(symbol, item)) is not None
        ]

        logger.debug("finnhub_earnings_fetched", symbol=symbol, count=len(surprises))
        return surprises

    except requests.RequestException as e:
        logger.warning("finnhub_earnings_fetch_failed", symbol=symbol, error=str(e))
        return []
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("finnhub_earnings_parse_failed", symbol=symbol, error=str(e))
        return []
