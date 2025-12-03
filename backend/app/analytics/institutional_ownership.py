"""Institutional ownership scoring for GAP-008.

Provides scoring based on institutional and insider ownership levels
from yfinance data (heldPercentInstitutions, heldPercentInsiders).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from ..storage.facade import PortfolioStorage

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


@dataclass
class OwnershipMetrics:
    """Ownership metrics for a ticker."""

    ticker: str
    institutional_pct: float | None  # 0-1 range (e.g., 0.64 = 64%)
    insider_pct: float | None  # 0-1 range (e.g., 0.02 = 2%)
    ownership_score: int  # 0-5 points


def get_ownership_from_cache(ticker: str, storage: PortfolioStorage) -> OwnershipMetrics | None:
    """Get ownership metrics from reference_cache.

    Args:
        ticker: Stock ticker symbol
        storage: Database storage instance

    Returns:
        OwnershipMetrics if found, None otherwise
    """
    query = """
        SELECT payload
        FROM reference_cache
        WHERE symbol = $1
        ORDER BY as_of_date DESC
        LIMIT 1
    """

    result = storage.query(query, [ticker])
    if result.is_empty():
        return None

    try:
        payload_str = result.row(0)[0]
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        inst_pct = payload.get("heldPercentInstitutions")
        insider_pct = payload.get("heldPercentInsiders")

        # Calculate score
        score = calculate_ownership_score(inst_pct, insider_pct)

        return OwnershipMetrics(
            ticker=ticker,
            institutional_pct=inst_pct,
            insider_pct=insider_pct,
            ownership_score=score,
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(
            "ownership_parse_error",
            ticker=ticker,
            error=str(e),
        )
        return None


def calculate_ownership_score(institutional_pct: float | None, insider_pct: float | None) -> int:
    """Calculate ownership quality score (0-5 points).

    Scoring logic:
    - High institutional (>50%): +2 (smart money validation)
    - Medium institutional (30-50%): +1
    - High insider (>10%): +2 (skin in the game)
    - Medium insider (5-10%): +1
    - Very low institutional (<10%): -1 (may indicate issues)

    Args:
        institutional_pct: Percentage held by institutions (0-1 range)
        insider_pct: Percentage held by insiders (0-1 range)

    Returns:
        Score from 0-5
    """
    score = 0

    # Institutional ownership scoring
    if institutional_pct is not None:
        if institutional_pct >= 0.50:
            score += 2  # Strong institutional support
        elif institutional_pct >= 0.30:
            score += 1  # Moderate institutional interest
        elif institutional_pct < 0.10:
            score -= 1  # Very low - may indicate concerns

    # Insider ownership scoring
    if insider_pct is not None:
        if insider_pct >= 0.10:
            score += 2  # Strong insider alignment
        elif insider_pct >= 0.05:
            score += 1  # Moderate insider stake

    # Clamp to 0-5 range
    return max(0, min(5, score))


def get_ownership_metrics_batch(
    tickers: list[str], storage: PortfolioStorage
) -> dict[str, OwnershipMetrics]:
    """Get ownership metrics for multiple tickers.

    Args:
        tickers: List of ticker symbols
        storage: Database storage instance

    Returns:
        Dictionary mapping ticker to OwnershipMetrics
    """
    if not tickers:
        return {}

    # Query all tickers at once with DISTINCT ON for latest
    query = """
        SELECT DISTINCT ON (ticker) ticker, payload
        FROM reference_cache
        WHERE symbol = ANY($1)
        ORDER BY symbol, as_of_date DESC
    """

    ticker_list: list[str | int | float | bool | None] = list(tickers)
    result = storage.query(query, [ticker_list])
    metrics: dict[str, OwnershipMetrics] = {}

    for row in result.iter_rows():
        ticker = row[0]
        try:
            payload = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            inst_pct = payload.get("heldPercentInstitutions")
            insider_pct = payload.get("heldPercentInsiders")
            score = calculate_ownership_score(inst_pct, insider_pct)

            metrics[str(ticker)] = OwnershipMetrics(
                ticker=str(ticker),
                institutional_pct=inst_pct,
                insider_pct=insider_pct,
                ownership_score=score,
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("ownership_batch_parse_error", ticker=ticker, error=str(e))
            continue

    return metrics
