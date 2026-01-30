"""Watchlist Discovery Helper Functions.

Utility functions for data retrieval and scoring used by discovery task.
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
# Data Retrieval Functions
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


# =============================================================================
# Scoring Functions
# =============================================================================


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


# =============================================================================
# Watchlist Helper Functions
# =============================================================================


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
