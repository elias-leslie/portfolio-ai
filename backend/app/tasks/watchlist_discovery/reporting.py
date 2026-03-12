"""Watchlist Reporting Module.

Generates daily watchlist reports with additions, removals, and score changes.
Scheduled via Hatchet cron: Daily 09:00 UTC
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from ...logging_config import get_logger
from ...storage import PortfolioStorage

logger = get_logger(__name__)
_SQL_ADDED = """
    SELECT symbol, created_at, source
    FROM watchlist_items
    WHERE created_at >= $1
    ORDER BY created_at DESC
"""
_SQL_REMOVED = """
    SELECT metadata->>'symbol' as symbol, deleted_at
    FROM deletion_audit
    WHERE table_name = 'watchlist_items' AND deleted_at >= $1
    ORDER BY deleted_at DESC
"""
_SQL_SCORE_CHANGES = """
    WITH prev AS (
        SELECT DISTINCT ON (item_id) item_id, overall_score as old_score
        FROM watchlist_snapshots_core
        WHERE fetched_at >= $1 - INTERVAL '1 day' AND fetched_at < $1
        ORDER BY item_id, fetched_at DESC
    ),
    curr AS (
        SELECT DISTINCT ON (item_id) item_id, overall_score as new_score
        FROM watchlist_snapshots_core
        WHERE fetched_at >= $1
        ORDER BY item_id, fetched_at DESC
    )
    SELECT DISTINCT ON (wi.symbol)
        wi.symbol, p.old_score, c.new_score,
        ABS(c.new_score - p.old_score) as change_abs,
        ((c.new_score - p.old_score) / NULLIF(p.old_score, 0)) * 100 as change_pct
    FROM watchlist_items wi
    LEFT JOIN prev p ON p.item_id = wi.id
    LEFT JOIN curr c ON c.item_id = wi.id
    WHERE p.old_score IS NOT NULL AND c.new_score IS NOT NULL
      AND ABS(c.new_score - p.old_score) >= 10
    ORDER BY wi.symbol, change_abs DESC
"""
# %s placeholders are required here because this query is executed via
# storage.connection() / raw_connection.cursor().execute(), which uses DB-API
# paramstyle. The other queries above use $1 (PostgreSQL positional) because
# they are executed via storage.query().
_SQL_UPSERT = """
    INSERT INTO watchlist_daily_reports
        (id, report_date, symbols_added, symbols_removed, score_changes, generated_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (report_date) DO UPDATE SET
        symbols_added = EXCLUDED.symbols_added,
        symbols_removed = EXCLUDED.symbols_removed,
        score_changes = EXCLUDED.score_changes,
        generated_at = EXCLUDED.generated_at
    RETURNING id
"""

def _fetch_added_symbols(storage: PortfolioStorage, since: datetime) -> list[dict[str, Any]]:
    return [
        {
            "symbol": row["symbol"],
            "added_at": row["created_at"].isoformat() if row["created_at"] else None,
            "source": row["source"],
        }
        for row in storage.query(_SQL_ADDED, [since]).iter_rows(named=True)
    ]


def _fetch_removed_symbols(storage: PortfolioStorage, since: datetime) -> list[dict[str, Any]]:
    # deletion_audit stores symbol in metadata JSONB, not as a separate column
    return [
        {
            "symbol": row["symbol"] or "UNKNOWN",
            "removed_at": row["deleted_at"].isoformat() if row["deleted_at"] else None,
        }
        for row in storage.query(_SQL_REMOVED, [since]).iter_rows(named=True)
    ]


def _fetch_score_changes(storage: PortfolioStorage, since: datetime) -> list[dict[str, Any]]:
    return [
        {
            "symbol": row["symbol"],
            "old_score": float(row["old_score"]) if row["old_score"] else 0.0,
            "new_score": float(row["new_score"]) if row["new_score"] else 0.0,
            "change_pct": float(row["change_pct"]) if row["change_pct"] else 0.0,
        }
        for row in storage.query(_SQL_SCORE_CHANGES, [since]).iter_rows(named=True)
    ]


def _persist_report(
    storage: PortfolioStorage,
    report_date: date,
    symbols_added: list[dict[str, Any]],
    symbols_removed: list[dict[str, Any]],
    score_changes: list[dict[str, Any]],
    now: datetime,
) -> None:
    with storage.connection() as conn:
        with conn.raw_connection.cursor() as cur:
            cur.execute(
                _SQL_UPSERT,
                (
                    str(uuid4()),
                    report_date,
                    json.dumps(symbols_added),
                    json.dumps(symbols_removed),
                    json.dumps(score_changes),
                    now,
                ),
            )
        conn.commit()


def generate_daily_watchlist_report_task() -> dict[str, Any]:
    """Generate daily watchlist report with additions, removals, and score changes.

    Scheduled: Daily 09:00 UTC (after discovery and trim tasks)
    Generates summary of last 24 hours of watchlist activity.
    """
    storage = PortfolioStorage()
    try:
        now = datetime.now(UTC)
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)

        symbols_added = _fetch_added_symbols(storage, since)
        symbols_removed = _fetch_removed_symbols(storage, since)
        score_changes = _fetch_score_changes(storage, since)
        report_date = now.date()
        _persist_report(storage, report_date, symbols_added, symbols_removed, score_changes, now)

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
        logger.error("watchlist_daily_report_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}
