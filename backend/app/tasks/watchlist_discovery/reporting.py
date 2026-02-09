"""Watchlist Reporting Module.

Generates daily watchlist reports with additions, removals, and score changes.
Scheduled via Hatchet cron: Daily 09:00 UTC
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from ...logging_config import get_logger
from ...storage import PortfolioStorage

logger = get_logger(__name__)


# =============================================================================
# =============================================================================


def generate_daily_watchlist_report_task() -> dict[str, Any]:
    """Generate daily watchlist report with additions, removals, and score changes.

    Scheduled: Daily 09:00 UTC (after discovery and trim tasks)
    Generates summary of last 24 hours of watchlist activity.
    """
    storage = PortfolioStorage()
    try:
        now = datetime.now(UTC)
        yesterday = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Find symbols added in last 24 hours
        added_df = storage.query(
            """
            SELECT symbol, created_at, source, metadata
            FROM watchlist_items
            WHERE created_at >= $1
            ORDER BY created_at DESC
            """,
            [yesterday],
        )
        symbols_added = [
            {
                "symbol": row["symbol"],
                "added_at": row["created_at"].isoformat() if row["created_at"] else None,
                "source": row["source"],
            }
            for row in added_df.iter_rows(named=True)
        ]

        # Find symbols removed in last 24 hours (from deletion_audit)
        # Note: deletion_audit stores symbol in metadata JSONB, not as separate column
        removed_df = storage.query(
            """
            SELECT metadata->>'symbol' as symbol, deleted_at
            FROM deletion_audit
            WHERE table_name = 'watchlist_items'
              AND deleted_at >= $1
            ORDER BY deleted_at DESC
            """,
            [yesterday],
        )
        symbols_removed = [
            {
                "symbol": row["symbol"] or "UNKNOWN",
                "removed_at": row["deleted_at"].isoformat() if row["deleted_at"] else None,
            }
            for row in removed_df.iter_rows(named=True)
        ]

        # Find significant score changes (>10 points) in last 24 hours
        score_changes_df = storage.query(
            """
            WITH yesterday_scores AS (
                SELECT
                    item_id,
                    overall_score as old_score
                FROM watchlist_snapshots_core
                WHERE fetched_at >= $1 - INTERVAL '1 day'
                  AND fetched_at < $1
                ORDER BY fetched_at DESC
            ),
            today_scores AS (
                SELECT
                    item_id,
                    overall_score as new_score
                FROM watchlist_snapshots_core
                WHERE fetched_at >= $1
                ORDER BY fetched_at DESC
            )
            SELECT DISTINCT ON (wi.symbol)
                wi.symbol,
                ys.old_score,
                ts.new_score,
                ABS(ts.new_score - ys.old_score) as change_abs,
                ((ts.new_score - ys.old_score) / NULLIF(ys.old_score, 0)) * 100 as change_pct
            FROM watchlist_items wi
            LEFT JOIN yesterday_scores ys ON ys.item_id = wi.id
            LEFT JOIN today_scores ts ON ts.item_id = wi.id
            WHERE ys.old_score IS NOT NULL
              AND ts.new_score IS NOT NULL
              AND ABS(ts.new_score - ys.old_score) >= 10
            ORDER BY wi.symbol, change_abs DESC
            """,
            [yesterday],
        )
        score_changes = [
            {
                "symbol": row["symbol"],
                "old_score": float(row["old_score"]) if row["old_score"] else 0.0,
                "new_score": float(row["new_score"]) if row["new_score"] else 0.0,
                "change_pct": float(row["change_pct"]) if row["change_pct"] else 0.0,
            }
            for row in score_changes_df.iter_rows(named=True)
        ]

        # Insert or update report for today
        report_id = str(uuid4())
        report_date = now.date()
        with storage.connection() as conn:
            cursor = conn.raw_connection.cursor()
            cursor.execute(
                """
                INSERT INTO watchlist_daily_reports (
                    id, report_date, symbols_added, symbols_removed, score_changes, generated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_date)
                DO UPDATE SET
                    symbols_added = EXCLUDED.symbols_added,
                    symbols_removed = EXCLUDED.symbols_removed,
                    score_changes = EXCLUDED.score_changes,
                    generated_at = EXCLUDED.generated_at
                RETURNING id
                """,
                (
                    report_id,
                    report_date,
                    json.dumps(symbols_added),
                    json.dumps(symbols_removed),
                    json.dumps(score_changes),
                    now,
                ),
            )
            conn.commit()

        logger.info(
            "watchlist_daily_report_generated",
            report_date=str(report_date),
            added_count=len(symbols_added),
            removed_count=len(symbols_removed),
            score_changes_count=len(score_changes),
        )

        return {
            "status": "success",
            "report_date": str(report_date),
            "added_count": len(symbols_added),
            "removed_count": len(symbols_removed),
            "score_changes_count": len(score_changes),
        }

    except Exception as e:
        logger.error("watchlist_daily_report_failed", error=str(e))
        return {"status": "error", "error": str(e)}
