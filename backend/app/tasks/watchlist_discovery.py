"""Watchlist Discovery and Trimming Tasks.

Automated watchlist management:
1. Discovery: Find high-potential symbols from top gainers, volume spikes, news mentions
2. Trimming: Remove underperforming symbols after minimum hold period

Scheduled via Celery Beat:
- discover_watchlist_candidates: Daily 08:00 UTC
- trim_underperforming_watchlist: Daily 08:30 UTC
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from celery import shared_task

from ..logging_config import get_logger
from ..rules.loader import get_rules
from ..storage import PortfolioStorage

logger = get_logger(__name__)


# =============================================================================
# Discovery Functions
# =============================================================================


def get_top_gainers(
    storage: PortfolioStorage,
    threshold_pct: float = 5.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find symbols with daily price gain above threshold."""
    sql = """
        WITH latest_bars AS (
            SELECT DISTINCT ON (symbol)
                symbol, date, close,
                LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close
            FROM day_bars
            WHERE date >= CURRENT_DATE - INTERVAL '5 days'
            ORDER BY symbol, date DESC
        )
        SELECT
            symbol,
            close,
            prev_close,
            ((close - prev_close) / NULLIF(prev_close, 0)) * 100 as change_pct
        FROM latest_bars
        WHERE prev_close IS NOT NULL
          AND ((close - prev_close) / NULLIF(prev_close, 0)) * 100 >= $1
        ORDER BY change_pct DESC
        LIMIT $2
    """
    df = storage.query(sql, [threshold_pct, limit])
    return [
        {
            "symbol": row["symbol"],
            "close": float(row["close"]) if row["close"] else 0.0,
            "prev_close": float(row["prev_close"]) if row["prev_close"] else 0.0,
            "change_pct": float(row["change_pct"]) if row["change_pct"] else 0.0,
        }
        for row in df.iter_rows(named=True)
    ]


def get_volume_spikes(
    storage: PortfolioStorage,
    spike_ratio: float = 2.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find symbols with volume spike above average."""
    sql = """
        WITH volume_stats AS (
            SELECT
                symbol,
                MAX(CASE WHEN date = (SELECT MAX(date) FROM day_bars) THEN volume END) as latest_volume,
                AVG(volume) FILTER (WHERE date < (SELECT MAX(date) FROM day_bars)) as avg_volume
            FROM day_bars
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY symbol
            HAVING AVG(volume) FILTER (WHERE date < (SELECT MAX(date) FROM day_bars)) > 0
        )
        SELECT
            symbol,
            latest_volume,
            avg_volume,
            (latest_volume / avg_volume) as volume_ratio
        FROM volume_stats
        WHERE latest_volume IS NOT NULL
          AND (latest_volume / avg_volume) >= $1
        ORDER BY volume_ratio DESC
        LIMIT $2
    """
    df = storage.query(sql, [spike_ratio, limit])
    return [
        {
            "symbol": row["symbol"],
            "volume": int(row["latest_volume"]) if row["latest_volume"] else 0,
            "avg_volume": float(row["avg_volume"]) if row["avg_volume"] else 0.0,
            "volume_ratio": float(row["volume_ratio"]) if row["volume_ratio"] else 0.0,
        }
        for row in df.iter_rows(named=True)
    ]


def get_news_mentions(
    storage: PortfolioStorage,
    min_mentions: int = 3,
    hours: int = 24,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find symbols with high news mention count."""
    sql = """
        SELECT
            symbol,
            COUNT(*) as article_count,
            AVG(sentiment_score) as avg_sentiment
        FROM news_cache
        WHERE published_at >= NOW() - make_interval(hours => $1)
          AND symbol IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= $2
        ORDER BY article_count DESC
        LIMIT $3
    """
    df = storage.query(sql, [hours, min_mentions, limit])
    return [
        {
            "symbol": row["symbol"],
            "article_count": int(row["article_count"]) if row["article_count"] else 0,
            "avg_sentiment": float(row["avg_sentiment"]) if row["avg_sentiment"] else 0.0,
        }
        for row in df.iter_rows(named=True)
    ]


def calculate_discovery_score(
    symbol: str,
    gainers_data: list[dict[str, Any]],
    volume_data: list[dict[str, Any]],
    news_data: list[dict[str, Any]],
) -> float:
    """Calculate combined discovery score for a symbol (0-12 scale)."""
    score = 0.0

    # Gainers score (0-4)
    gainer = next((g for g in gainers_data if g["symbol"] == symbol), None)
    if gainer:
        change_pct = gainer["change_pct"]
        if change_pct >= 20:
            score += 4.0
        elif change_pct >= 15:
            score += 3.0
        elif change_pct >= 10:
            score += 2.0
        elif change_pct >= 5:
            score += 1.0

    # Volume score (0-4)
    volume = next((v for v in volume_data if v["symbol"] == symbol), None)
    if volume:
        ratio = volume["volume_ratio"]
        if ratio >= 5:
            score += 4.0
        elif ratio >= 4:
            score += 3.0
        elif ratio >= 3:
            score += 2.0
        elif ratio >= 2:
            score += 1.0

    # News score (0-4)
    news = next((n for n in news_data if n["symbol"] == symbol), None)
    if news:
        count = news["article_count"]
        if count >= 10:
            score += 4.0
        elif count >= 7:
            score += 3.0
        elif count >= 5:
            score += 2.0
        elif count >= 3:
            score += 1.0

    return score


def get_existing_watchlist_symbols(storage: PortfolioStorage) -> set[str]:
    """Get set of symbols already in watchlist."""
    df = storage.query("SELECT symbol FROM watchlist_items", [])
    return {str(row["symbol"]) for row in df.iter_rows(named=True)}


def get_watchlist_size(storage: PortfolioStorage) -> int:
    """Get current watchlist item count."""
    df = storage.query("SELECT COUNT(*) as cnt FROM watchlist_items", [])
    for row in df.iter_rows(named=True):
        return int(row["cnt"]) if row["cnt"] else 0
    return 0


def add_symbol_to_watchlist(
    storage: PortfolioStorage,
    symbol: str,
    discovery_score: float,
    source: str = "discovery",
) -> str | None:
    """Add symbol to watchlist with discovery metadata."""
    item_id = str(uuid4())
    now = datetime.now(UTC)
    metadata = {
        "discovery_score": discovery_score,
        "discovery_date": now.isoformat(),
        "auto_added": True,
    }

    try:
        with storage.connection() as conn:
            cursor = conn.raw_connection.cursor()
            # Ensure symbol exists in symbols table (FK constraint)
            cursor.execute(
                """
                INSERT INTO symbols (symbol, security_type, created_at)
                VALUES (%s, 'equity', %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                (symbol.upper(), now),
            )
            cursor.execute(
                """
                INSERT INTO watchlist_items (id, symbol, source, added_by, metadata, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
                RETURNING id
                """,
                (
                    item_id,
                    symbol.upper(),
                    source,
                    "system_discovery",
                    json.dumps(metadata),
                    now,
                    now,
                ),
            )
            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.info(
                    "watchlist_discovery_added",
                    symbol=symbol,
                    discovery_score=discovery_score,
                    item_id=item_id,
                )
                return item_id
            return None
    except Exception as e:
        logger.error("watchlist_discovery_add_failed", symbol=symbol, error=str(e))
        return None


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
# Celery Tasks
# =============================================================================


@shared_task(name="discover_watchlist_candidates", bind=True)  # type: ignore[misc]
def discover_watchlist_candidates_task(
    self: Any,
) -> dict[str, Any]:
    """Discover and add high-potential symbols to watchlist.

    Scheduled: Daily 08:00 UTC
    Limits: Max 5 additions per day, respects max watchlist size
    """
    rules = get_rules()
    wm = rules.watchlist_management

    storage = PortfolioStorage()
    try:
        # Check current size
        current_size = get_watchlist_size(storage)
        if current_size >= wm.max_watchlist_size:
            logger.info(
                "watchlist_discovery_skipped",
                reason="watchlist_full",
                current_size=current_size,
                max_size=wm.max_watchlist_size,
            )
            return {
                "status": "skipped",
                "reason": "watchlist_full",
                "current_size": current_size,
            }

        # Get discovery data
        gainers = get_top_gainers(storage, wm.gainers_threshold_pct)
        volume_spikes = get_volume_spikes(storage, wm.volume_spike_ratio)
        news_mentions = get_news_mentions(storage, wm.news_mention_threshold)

        # Get existing symbols
        existing = get_existing_watchlist_symbols(storage)

        # Find all unique candidates
        all_symbols: set[str] = set()
        for g in gainers:
            all_symbols.add(g["symbol"])
        for v in volume_spikes:
            all_symbols.add(v["symbol"])
        for n in news_mentions:
            all_symbols.add(n["symbol"])

        # Filter out existing
        candidates = all_symbols - existing

        # Score candidates
        scored_candidates: list[dict[str, Any]] = []
        for symbol in candidates:
            score = calculate_discovery_score(symbol, gainers, volume_spikes, news_mentions)
            if score >= wm.discovery_score_threshold:
                scored_candidates.append({"symbol": symbol, "score": score})

        # Sort by score and limit
        scored_candidates.sort(key=lambda x: float(x["score"]), reverse=True)
        to_add = scored_candidates[: wm.max_daily_additions]

        # Respect watchlist size limit
        slots_available = wm.max_watchlist_size - current_size
        to_add = to_add[:slots_available]

        # Add to watchlist
        added: list[dict[str, Any]] = []
        for candidate in to_add:
            item_id = add_symbol_to_watchlist(
                storage,
                candidate["symbol"],
                float(candidate["score"]),
            )
            if item_id:
                added.append({"symbol": candidate["symbol"], "score": candidate["score"]})

        logger.info(
            "watchlist_discovery_complete",
            candidates_found=len(candidates),
            qualified=len(scored_candidates),
            added=len(added),
        )

        return {
            "status": "success",
            "candidates_found": len(candidates),
            "qualified": len(scored_candidates),
            "added": added,
            "top_gainers": len(gainers),
            "volume_spikes": len(volume_spikes),
            "news_mentions": len(news_mentions),
        }

    except Exception as e:
        logger.error("watchlist_discovery_failed", error=str(e))
        return {"status": "error", "error": str(e)}


@shared_task(name="trim_underperforming_watchlist", bind=True)  # type: ignore[misc]
def trim_underperforming_watchlist_task(
    self: Any,
) -> dict[str, Any]:
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


@shared_task(name="generate_daily_watchlist_report", bind=True)  # type: ignore[misc]
def generate_daily_watchlist_report_task(
    self: Any,
) -> dict[str, Any]:
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
        removed_df = storage.query(
            """
            SELECT table_name, record_data, deleted_at
            FROM deletion_audit
            WHERE table_name = 'watchlist_items'
              AND deleted_at >= $1
            ORDER BY deleted_at DESC
            """,
            [yesterday],
        )
        symbols_removed = []
        for row in removed_df.iter_rows(named=True):
            record_data = (
                json.loads(row["record_data"])
                if isinstance(row["record_data"], str)
                else row["record_data"]
            )
            symbols_removed.append(
                {
                    "symbol": record_data.get("symbol", "UNKNOWN"),
                    "removed_at": row["deleted_at"].isoformat() if row["deleted_at"] else None,
                }
            )

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
