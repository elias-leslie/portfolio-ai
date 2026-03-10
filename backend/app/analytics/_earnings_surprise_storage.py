"""Earnings surprise database persistence (internal helper)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger

from .earnings_surprise_types import EarningsSurprise

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

_UPSERT_SYMBOL_SQL = """
    INSERT INTO symbols (symbol, security_type, created_at)
    VALUES ($1, 'equity', NOW())
    ON CONFLICT (symbol) DO NOTHING
"""

_UPSERT_EARNINGS_SQL = """
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
"""


def _save_one(conn: Any, surprise: EarningsSurprise) -> None:
    """Persist a single EarningsSurprise row via upsert."""
    conn.execute(_UPSERT_SYMBOL_SQL, [surprise.symbol])
    conn.execute(
        _UPSERT_EARNINGS_SQL,
        [
            surprise.symbol,
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


def save_earnings_surprises(
    storage: PortfolioStorage,
    surprises: list[EarningsSurprise],
) -> int:
    """Save earnings surprises to database using UPSERT to avoid duplicates.

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
                _save_one(conn, surprise)
                count += 1
            except Exception as e:
                logger.warning(
                    "earnings_surprise_save_failed",
                    symbol=surprise.symbol,
                    error=str(e),
                )
        conn.commit()
    return count


def get_recent_earnings_surprises(
    storage: PortfolioStorage,
    symbol: str,
    quarters: int = 4,
) -> list[dict[str, str | float | None]]:
    """Get recent earnings surprises for a symbol from database.

    Args:
        storage: Database storage instance
        symbol: Stock symbol
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
        [symbol, quarters],
    )

    if result.is_empty():
        return []

    return result.to_dicts()
