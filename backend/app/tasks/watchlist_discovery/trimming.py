"""Watchlist Trimming Module.

Removes underperforming symbols from watchlist after minimum hold period.
Scheduled via Hatchet cron: Daily 08:30 UTC
"""

from __future__ import annotations

from typing import Any

from ...logging_config import get_logger
from ...rules.loader import get_rules
from ...storage import PortfolioStorage

logger = get_logger(__name__)


# =============================================================================
# Trimming Functions
# =============================================================================


def get_trim_candidates(
    storage: PortfolioStorage,
    min_days_watched: int = 7,
    min_score_threshold: float = 4.0,
    exclude_portfolio: bool = True,
) -> list[dict[str, Any]]:
    """Find watchlist items eligible for trimming."""
    exclude_clause = ""
    if exclude_portfolio:
        exclude_clause = """
            AND wi.symbol NOT IN (
                SELECT DISTINCT symbol FROM portfolio_positions WHERE shares > 0
            )
        """

    sql = f"""
        WITH watchlist_scores AS (
            SELECT
                wi.id,
                wi.symbol,
                wi.created_at,
                EXTRACT(DAY FROM NOW() - wi.created_at) as days_watched,
                COALESCE(AVG(wsc.overall_score), 0) as avg_score
            FROM watchlist_items wi
            LEFT JOIN watchlist_snapshots_core wsc ON wsc.item_id = wi.id
                AND wsc.fetched_at >= NOW() - INTERVAL '60 days'
            WHERE wi.created_at <= NOW() - make_interval(days => $1)
            {exclude_clause}
            GROUP BY wi.id, wi.symbol, wi.created_at
        )
        SELECT id, symbol, days_watched, avg_score
        FROM watchlist_scores
        WHERE avg_score < $2
        ORDER BY avg_score ASC
    """

    df = storage.query(sql, [min_days_watched, min_score_threshold])
    return [
        {
            "id": str(row["id"]),
            "symbol": str(row["symbol"]),
            "days_watched": int(row["days_watched"]) if row["days_watched"] else 0,
            "avg_score": float(row["avg_score"]) if row["avg_score"] else 0.0,
        }
        for row in df.iter_rows(named=True)
    ]


def remove_symbol_from_watchlist(
    storage: PortfolioStorage,
    item_id: str,
    symbol: str,
    reason: str,
) -> bool:
    """Remove symbol from watchlist."""
    try:
        with storage.connection() as conn:
            cursor = conn.raw_connection.cursor()
            # Delete snapshots first (FK constraint)
            cursor.execute("DELETE FROM watchlist_snapshots_core WHERE item_id = %s", (item_id,))
            # Delete item
            cursor.execute("DELETE FROM watchlist_items WHERE id = %s RETURNING id", (item_id,))
            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.info(
                    "watchlist_trim_removed",
                    symbol=symbol,
                    item_id=item_id,
                    reason=reason,
                )
                return True
            return False
    except Exception as e:
        logger.error("watchlist_trim_failed", symbol=symbol, error=str(e))
        return False


# =============================================================================
# =============================================================================


def trim_underperforming_watchlist_task() -> dict[str, Any]:
    """Remove underperforming symbols from watchlist.

    Scheduled: Daily 08:30 UTC
    Limits: Max 3 removals per day
    """
    rules = get_rules()
    wm = rules.watchlist_management

    if not wm.auto_trim_enabled:
        logger.info("watchlist_trim_skipped", reason="auto_trim_disabled")
        return {"status": "skipped", "reason": "auto_trim_disabled"}

    storage = PortfolioStorage()
    try:
        # Find trim candidates
        candidates = get_trim_candidates(
            storage,
            min_days_watched=wm.min_days_watched,
            min_score_threshold=wm.min_score_threshold,
            exclude_portfolio=wm.exclude_portfolio_holdings,
        )

        # Limit removals per day
        to_remove = candidates[: wm.max_daily_removals]

        # Remove from watchlist
        removed: list[dict[str, Any]] = []
        for candidate in to_remove:
            reason = f"avg_score={candidate['avg_score']:.1f} < {wm.min_score_threshold}"
            success = remove_symbol_from_watchlist(
                storage,
                candidate["id"],
                candidate["symbol"],
                reason,
            )
            if success:
                removed.append(
                    {
                        "symbol": candidate["symbol"],
                        "avg_score": candidate["avg_score"],
                        "days_watched": candidate["days_watched"],
                    }
                )

        logger.info(
            "watchlist_trim_complete",
            candidates_found=len(candidates),
            removed=len(removed),
        )

        return {
            "status": "success",
            "candidates_found": len(candidates),
            "removed": removed,
        }

    except Exception as e:
        logger.error("watchlist_trim_failed", error=str(e))
        return {"status": "error", "error": str(e)}
