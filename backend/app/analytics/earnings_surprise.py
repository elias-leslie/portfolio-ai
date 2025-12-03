"""Earnings surprise data fetching and scoring (GAP-003).

Fetches earnings surprise data (EPS estimate vs actual) from Finnhub
and provides scoring for signal classification.

Earnings surprises are predictive:
- Stocks that beat EPS estimates consistently tend to outperform
- Stocks that miss estimates consistently tend to underperform
- Large positive surprises often lead to price momentum
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import requests

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Score thresholds
LARGE_BEAT_PCT = 10.0  # >10% beat = very bullish
SMALL_BEAT_PCT = 2.0  # >2% beat = bullish
SMALL_MISS_PCT = -2.0  # <-2% miss = bearish
LARGE_MISS_PCT = -10.0  # <-10% miss = very bearish


@dataclass
class EarningsSurprise:
    """Single earnings surprise record."""

    ticker: str
    earnings_date: date
    fiscal_quarter: str | None
    eps_estimate: Decimal | None
    eps_actual: Decimal | None
    surprise_pct: Decimal | None
    surprise_direction: str  # 'beat', 'miss', 'inline'
    revenue_estimate: Decimal | None = None
    revenue_actual: Decimal | None = None


def fetch_earnings_surprises_from_finnhub(
    ticker: str,
    limit: int = 4,
) -> list[EarningsSurprise]:
    """Fetch earnings surprises from Finnhub API.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of recent earnings to fetch

    Returns:
        List of EarningsSurprise records (most recent first)
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        logger.warning("finnhub_api_key_missing", ticker=ticker)
        return []

    try:
        # Finnhub earnings calendar endpoint returns historical and future earnings
        # We need to filter for past earnings with actuals
        url = "https://finnhub.io/api/v1/stock/earnings"
        params = {"symbol": ticker, "token": api_key}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        surprises = []

        for item in data[:limit]:
            # Skip if no actual data yet
            if item.get("actual") is None:
                continue

            eps_estimate = item.get("estimate")
            eps_actual = item.get("actual")
            surprise_pct = item.get("surprisePercent")

            # Calculate surprise direction
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

            # Parse period (e.g., "2024-09-30" -> "Q3 2024")
            period = item.get("period", "")
            fiscal_quarter = None
            if period:
                try:
                    period_date = datetime.strptime(period, "%Y-%m-%d").date()
                    quarter = (period_date.month - 1) // 3 + 1
                    fiscal_quarter = f"Q{quarter} {period_date.year}"
                except (ValueError, TypeError):
                    pass

            surprises.append(
                EarningsSurprise(
                    ticker=ticker,
                    earnings_date=datetime.strptime(period, "%Y-%m-%d").date()
                    if period
                    else date.today(),
                    fiscal_quarter=fiscal_quarter,
                    eps_estimate=Decimal(str(eps_estimate)) if eps_estimate else None,
                    eps_actual=Decimal(str(eps_actual)) if eps_actual else None,
                    surprise_pct=Decimal(str(surprise_pct)) if surprise_pct else None,
                    surprise_direction=direction,
                )
            )

        logger.debug(
            "finnhub_earnings_fetched",
            ticker=ticker,
            count=len(surprises),
        )
        return surprises

    except requests.RequestException as e:
        logger.warning("finnhub_earnings_fetch_failed", ticker=ticker, error=str(e))
        return []
    except (KeyError, ValueError, TypeError) as e:
        logger.warning("finnhub_earnings_parse_failed", ticker=ticker, error=str(e))
        return []


def save_earnings_surprises(
    storage: PortfolioStorage,
    surprises: list[EarningsSurprise],
) -> int:
    """Save earnings surprises to database.

    Uses UPSERT to avoid duplicates.

    Args:
        storage: Database storage instance
        surprises: List of earnings surprises to save

    Returns:
        Number of records saved/updated
    """
    if not surprises:
        return 0

    count = 0
    with storage.connection() as conn:
        for surprise in surprises:
            try:
                conn.execute(
                    """
                    INSERT INTO earnings_surprises (
                        symbol, earnings_date, fiscal_quarter,
                        eps_estimate, eps_actual, surprise_pct, surprise_direction,
                        revenue_estimate, revenue_actual, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    ON CONFLICT (symbol, earnings_date) DO UPDATE SET
                        fiscal_quarter = EXCLUDED.fiscal_quarter,
                        eps_estimate = EXCLUDED.eps_estimate,
                        eps_actual = EXCLUDED.eps_actual,
                        surprise_pct = EXCLUDED.surprise_pct,
                        surprise_direction = EXCLUDED.surprise_direction,
                        revenue_estimate = EXCLUDED.revenue_estimate,
                        revenue_actual = EXCLUDED.revenue_actual,
                        updated_at = NOW()
                    """,
                    [
                        surprise.ticker,
                        surprise.earnings_date.isoformat(),
                        surprise.fiscal_quarter,
                        float(surprise.eps_estimate) if surprise.eps_estimate else None,
                        float(surprise.eps_actual) if surprise.eps_actual else None,
                        float(surprise.surprise_pct) if surprise.surprise_pct else None,
                        surprise.surprise_direction,
                        float(surprise.revenue_estimate) if surprise.revenue_estimate else None,
                        float(surprise.revenue_actual) if surprise.revenue_actual else None,
                    ],
                )
                count += 1
            except Exception as e:
                logger.warning(
                    "earnings_surprise_save_failed",
                    ticker=surprise.ticker,
                    error=str(e),
                )
        conn.commit()
    return count


def get_recent_earnings_surprises(
    storage: PortfolioStorage,
    ticker: str,
    quarters: int = 4,
) -> list[dict[str, str | float | None]]:
    """Get recent earnings surprises for a ticker from database.

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol
        quarters: Number of recent quarters to fetch

    Returns:
        List of dicts with surprise data
    """
    result = storage.query(
        """
        SELECT symbol, earnings_date, fiscal_quarter,
               eps_estimate, eps_actual, surprise_pct, surprise_direction
        FROM earnings_surprises
        WHERE symbol = $1
        ORDER BY earnings_date DESC
        LIMIT $2
        """,
        [ticker, quarters],
    )

    if result.is_empty():
        return []

    return result.to_dicts()


def calculate_earnings_surprise_score(
    storage: PortfolioStorage,
    ticker: str,
    quarters: int = 4,
) -> tuple[int, list[str]]:
    """Calculate 0-4 point earnings surprise score for signal classification.

    Scoring based on recent earnings history:
    - Consistent beats (3-4 quarters): +3-4 points
    - Recent beat: +2 points
    - Inline results: +1 point
    - Recent miss: 0 points
    - Consistent misses: -1 point (AVOID signal contribution)

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol
        quarters: Number of quarters to analyze

    Returns:
        (score, reasons) tuple
    """
    surprises = get_recent_earnings_surprises(storage, ticker, quarters)

    if not surprises:
        return 0, []  # No data = no score

    score = 0
    reasons: list[str] = []

    # Count beats, misses, and inline
    beats = sum(1 for s in surprises if s.get("surprise_direction") == "beat")
    misses = sum(1 for s in surprises if s.get("surprise_direction") == "miss")
    total = len(surprises)

    # Most recent quarter gets extra weight
    most_recent = surprises[0] if surprises else None
    most_recent_direction = most_recent.get("surprise_direction") if most_recent else None
    most_recent_pct = most_recent.get("surprise_pct") if most_recent else None

    # Score based on beat/miss ratio and recency
    if beats >= 3 and misses == 0:
        # Consistent beater (3-4 beats, no misses)
        score += 4
        reasons.append(f"Earnings: {beats}/{total} quarters beat estimates")
    elif beats >= 2 and misses <= 1:
        # Good track record
        score += 3
        reasons.append(f"Earnings: {beats}/{total} quarters beat")
    elif most_recent_direction == "beat":
        # Recent beat
        score += 2
        if most_recent_pct and float(most_recent_pct) > LARGE_BEAT_PCT:
            reasons.append(f"Recent earnings +{float(most_recent_pct):.1f}% surprise")
        else:
            reasons.append("Recent earnings beat")
    elif most_recent_direction == "inline":
        # Met expectations
        score += 1
        reasons.append("Earnings met expectations")
    elif misses >= 3:
        # Consistent misser - negative signal
        score -= 1
        reasons.append(f"Earnings: {misses}/{total} quarters missed estimates")
    # Recent miss = 0 points, no reason

    return score, reasons


def fetch_and_store_earnings_surprises(
    storage: PortfolioStorage,
    ticker: str,
) -> int:
    """Convenience function to fetch and store earnings surprises.

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol

    Returns:
        Number of records saved
    """
    surprises = fetch_earnings_surprises_from_finnhub(ticker)
    if surprises:
        return save_earnings_surprises(storage, surprises)
    return 0
