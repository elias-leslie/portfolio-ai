"""Analyst estimate revisions service (GAP-005).

Fetches analyst recommendation trends from Finnhub (FREE tier) and tracks
revisions over time to detect sentiment momentum signals.

Upgrade signals: Buy ratings increasing = positive analyst momentum
Downgrade signals: Sell ratings increasing = negative analyst momentum

Data source: Finnhub /stock/recommendation (FREE, returns monthly data)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypedDict

import httpx

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class AnalystRevision(TypedDict):
    """Analyst revision record."""

    symbol: str
    metric: str
    period: str
    current_estimate: Decimal | None
    estimate_7d_ago: Decimal | None
    estimate_30d_ago: Decimal | None
    estimate_90d_ago: Decimal | None
    revision_direction: str | None
    revision_magnitude: Decimal | None
    num_analysts: int | None
    fetched_at: datetime


def _get_finnhub_key(storage: PortfolioStorage) -> str | None:
    """Get Finnhub API key from database."""
    try:
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT value FROM source_credentials WHERE source_id = 'finnhub' AND field = 'apikey'"
            )
            row = result.fetchone()
            return str(row[0]) if row else None
    except Exception as e:
        logger.warning("finnhub_key_fetch_failed", error=str(e))
        return None


def fetch_analyst_recommendations(
    symbol: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Fetch analyst recommendations from Finnhub (FREE tier).

    Args:
        symbol: Stock symbol
        api_key: Finnhub API key

    Returns:
        List of recommendation records (monthly data)
    """
    try:
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={api_key}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        logger.warning("finnhub_recommendations_failed", symbol=symbol, error=str(e))
        return []


def calculate_revision_metrics(
    current: float | None,
    prior: float | None,
) -> tuple[str | None, Decimal | None]:
    """Calculate revision direction and magnitude.

    Args:
        current: Current estimate value
        prior: Prior estimate value (7d, 30d, or 90d ago)

    Returns:
        Tuple of (direction, magnitude_pct)
    """
    if current is None or prior is None or prior == 0:
        return (None, None)

    change_pct = ((current - prior) / abs(prior)) * 100

    if abs(change_pct) < 0.5:
        direction = "unchanged"
    elif change_pct > 0:
        direction = "up"
    else:
        direction = "down"

    return (direction, Decimal(str(round(change_pct, 4))))


def parse_recommendation_response(
    symbol: str,
    recommendations: list[dict[str, Any]],
) -> list[AnalystRevision]:
    """Parse Finnhub recommendation response into revision records.

    Finnhub returns monthly recommendation data:
    - buy, sell, hold, strongBuy, strongSell counts
    - period: "YYYY-MM-01" format

    We calculate a "buy score" (0-100) as: (strongBuy*2 + buy) / total * 100
    Revisions track changes in this score over time.

    Args:
        symbol: Stock symbol
        recommendations: Raw Finnhub API response (newest first)

    Returns:
        List of AnalystRevision records
    """
    if not recommendations:
        return []

    revisions: list[AnalystRevision] = []
    now = datetime.now(UTC)

    def calc_buy_score(rec: dict[str, Any]) -> float | None:
        """Calculate buy score (0-100) from recommendation counts."""
        strong_buy = rec.get("strongBuy", 0) or 0
        buy = rec.get("buy", 0) or 0
        hold = rec.get("hold", 0) or 0
        sell = rec.get("sell", 0) or 0
        strong_sell = rec.get("strongSell", 0) or 0
        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return None
        # Weight strongBuy 2x, normalize to 0-100
        weighted = (strong_buy * 2 + buy * 1.5 + hold * 0.5) / (total * 2) * 100
        return round(weighted, 2)

    # Get most recent recommendation (current)
    current = recommendations[0] if recommendations else None
    if not current:
        return []

    # Look for 1 month, 3 month, 6 month ago (indices 1, 3, 6 in monthly data)
    rec_1m = recommendations[1] if len(recommendations) > 1 else None
    rec_3m = recommendations[3] if len(recommendations) > 3 else None
    rec_6m = recommendations[6] if len(recommendations) > 6 else None

    current_score = calc_buy_score(current)
    if current_score is not None:
        prior_score = calc_buy_score(rec_1m) if rec_1m else None
        direction, magnitude = calculate_revision_metrics(current_score, prior_score)

        # Calculate total analysts
        total_analysts = sum(
            current.get(k, 0) or 0 for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]
        )

        revisions.append(
            AnalystRevision(
                symbol=symbol,
                metric="buy_score",  # 0-100 weighted buy score
                period=current.get("period", "unknown"),
                current_estimate=Decimal(str(current_score)),
                estimate_7d_ago=Decimal(str(prior_score)) if prior_score else None,
                estimate_30d_ago=(
                    Decimal(str(calc_buy_score(rec_3m)))
                    if rec_3m and calc_buy_score(rec_3m)
                    else None
                ),
                estimate_90d_ago=(
                    Decimal(str(calc_buy_score(rec_6m)))
                    if rec_6m and calc_buy_score(rec_6m)
                    else None
                ),
                revision_direction=direction,
                revision_magnitude=magnitude,
                num_analysts=total_analysts,
                fetched_at=now,
            )
        )

    return revisions


def save_analyst_revisions(
    storage: PortfolioStorage,
    revisions: list[AnalystRevision],
) -> int:
    """Save analyst revision records to database.

    Uses UPSERT to update existing records.

    Args:
        storage: Database storage instance
        revisions: List of revision records

    Returns:
        Number of records saved
    """
    if not revisions:
        return 0

    saved = 0
    for rev in revisions:
        try:
            # Ensure symbol exists in symbols table (FK constraint)
            storage.execute(
                """
                INSERT INTO symbols (symbol, security_type, created_at)
                VALUES (?, 'equity', NOW())
                ON CONFLICT (symbol) DO NOTHING
                """,
                [rev["symbol"]],
            )
            storage.execute(
                """
                INSERT INTO analyst_revisions
                    (symbol, metric, period, current_estimate, estimate_7d_ago,
                     estimate_30d_ago, estimate_90d_ago, revision_direction,
                     revision_magnitude, num_analysts, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (symbol, metric, period) DO UPDATE SET
                    current_estimate = EXCLUDED.current_estimate,
                    estimate_7d_ago = EXCLUDED.estimate_7d_ago,
                    estimate_30d_ago = EXCLUDED.estimate_30d_ago,
                    estimate_90d_ago = EXCLUDED.estimate_90d_ago,
                    revision_direction = EXCLUDED.revision_direction,
                    revision_magnitude = EXCLUDED.revision_magnitude,
                    num_analysts = EXCLUDED.num_analysts,
                    fetched_at = EXCLUDED.fetched_at
                """,
                [
                    rev["symbol"],
                    rev["metric"],
                    rev["period"],
                    float(rev["current_estimate"]) if rev["current_estimate"] else None,
                    float(rev["estimate_7d_ago"]) if rev["estimate_7d_ago"] else None,
                    float(rev["estimate_30d_ago"]) if rev["estimate_30d_ago"] else None,
                    float(rev["estimate_90d_ago"]) if rev["estimate_90d_ago"] else None,
                    rev["revision_direction"],
                    float(rev["revision_magnitude"]) if rev["revision_magnitude"] else None,
                    rev["num_analysts"],
                    rev["fetched_at"],
                ],
            )
            saved += 1
        except Exception as e:
            logger.warning(
                "analyst_revision_save_failed",
                symbol=rev["symbol"],
                metric=rev["metric"],
                error=str(e),
            )

    return saved


def refresh_analyst_revisions_for_symbols(
    storage: PortfolioStorage,
    symbols: list[str],
) -> dict[str, int]:
    """Refresh analyst revisions for multiple symbols using Finnhub (FREE tier).

    Args:
        storage: Database storage instance
        symbols: List of stock symbols

    Returns:
        Dict with success/failure counts
    """
    results = {"success": 0, "failed": 0, "records_saved": 0}

    # Get Finnhub API key from database
    api_key = _get_finnhub_key(storage)
    if not api_key:
        logger.error("finnhub_api_key_not_found")
        return {"success": 0, "failed": len(symbols), "records_saved": 0}

    for symbol in symbols:
        try:
            recommendations = fetch_analyst_recommendations(symbol, api_key)
            if recommendations:
                revisions = parse_recommendation_response(symbol, recommendations)
                saved = save_analyst_revisions(storage, revisions)
                results["records_saved"] += saved
                results["success"] += 1
                logger.info(
                    "analyst_revisions_updated",
                    symbol=symbol,
                    records=saved,
                )
            else:
                logger.info("analyst_revisions_no_data", symbol=symbol)
                results["success"] += 1  # No data is still success
        except Exception as e:
            logger.warning(
                "analyst_revisions_failed",
                symbol=symbol,
                error=str(e),
            )
            results["failed"] += 1

    return results
