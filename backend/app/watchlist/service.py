"""Watchlist scoring service for background refresh tasks."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import polars as pl

from ..logging_config import get_logger
from ..portfolio.price_fetcher import PriceDataFetcher
from ..storage import DuckDBStorage
from .models import (
    ScoreWeights,
    TechnicalSnapshot,
    WatchlistScoreInputs,
    WatchlistSnapshot,
)
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)


def _load_watchlist_items(storage: DuckDBStorage, account_id: str | None) -> pl.DataFrame:
    params: list[Any] = []
    sql = """
        SELECT id, account_id, symbol
        FROM watchlist_items
    """
    if account_id:
        sql += " WHERE account_id = ?"
        params.append(account_id)
    return storage.query(sql, params)


def _load_latest_technical(
    storage: DuckDBStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    if not symbols:
        return {}

    placeholders = ",".join(["?"] * len(symbols))
    df = storage.query(
        f"""
        SELECT *
        FROM technical_indicators
        WHERE ticker IN ({placeholders})
        ORDER BY ticker, date DESC
        """,
        symbols,
    )

    if df.is_empty():
        return {}

    grouped = df.group_by("ticker").agg(pl.all().first())
    snapshots: dict[str, TechnicalSnapshot] = {}
    for row in grouped.iter_rows(named=True):
        calculated_at = row.get("calculated_at")
        if isinstance(calculated_at, datetime) and calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=UTC)
        snapshots[row["ticker"]] = TechnicalSnapshot(
            rsi_14=row.get("rsi_14"),
            sma_50=row.get("sma_50"),
            sma_200=row.get("sma_200"),
            macd=row.get("macd"),
            macd_signal=row.get("macd_signal"),
            price=None,
            calculated_at=calculated_at,
        )
    return snapshots


def _load_default_weights(storage: DuckDBStorage) -> ScoreWeights:
    df = storage.query(
        """
        SELECT watchlist_price_weight, watchlist_technical_weight
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    if df.is_empty():
        return ScoreWeights()

    row = df.to_dicts()[0]
    return ScoreWeights(
        price=row.get("watchlist_price_weight", 50.0) or 0.0,
        technical=row.get("watchlist_technical_weight", 50.0) or 0.0,
    )


def _calculate_price_change(
    storage: DuckDBStorage, symbol: str, price: float | None
) -> float | None:
    if price is None or price <= 0:
        return None

    df = storage.query(
        """
        SELECT close
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 2
        """,
        [symbol],
    )
    if df.height < 2:
        return None

    prev_close = df["close"][1]
    if prev_close in (0, None):
        return None

    return float((price - prev_close) / prev_close * 100.0)


def refresh_watchlist_scores(
    storage: DuckDBStorage,
    *,
    account_id: str | None = None,
    price_fetcher: PriceDataFetcher | None = None,
    batch_size: int = 20,
    batch_delay_seconds: float = 2.0,
) -> dict[str, Any]:
    """Refresh watchlist scores for all items or a specific account.

    Args:
        storage: Database storage instance
        account_id: Optional account ID to filter items (None = all accounts)
        price_fetcher: Optional price fetcher instance (creates new if None)
        batch_size: Number of symbols to fetch in each batch (default: 20)
        batch_delay_seconds: Delay between batches to respect rate limits (default: 2.0)

    Returns:
        Dict with processing statistics:
        - processed: Number of items successfully processed
        - symbols: List of symbols processed
        - batches: Number of batches executed

    Note:
        Batching strategy respects API quota limits:
        - YFinance: Unlimited (primary source, handles bulk requests)
        - TwelveData: 8 req/min, 800/day (batch_size=20, delay=2s = 6/min conservative)
        - Polygon: 5 req/min (batch_size=20, delay=2s = well under limit)
        Conservative defaults ensure we stay within free tier quotas even with failover.
    """
    items_df = _load_watchlist_items(storage, account_id)
    if items_df.is_empty():
        logger.info("watchlist_refresh_no_items", account_id=account_id)
        return {"processed": 0, "symbols": [], "batches": 0}

    symbols = sorted(set(items_df["symbol"]))
    fetcher = price_fetcher or PriceDataFetcher(storage)
    technical_map = _load_latest_technical(storage, symbols)
    default_weights = _load_default_weights(storage)

    # Batch symbols to respect API rate limits
    symbol_batches = [symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)]
    total_batches = len(symbol_batches)

    logger.info(
        "watchlist_refresh_batching",
        total_symbols=len(symbols),
        batch_size=batch_size,
        total_batches=total_batches,
        delay_seconds=batch_delay_seconds,
    )

    # Fetch price data in batches with delays
    price_map: dict[str, Any] = {}
    for batch_idx, batch_symbols in enumerate(symbol_batches, start=1):
        logger.debug(
            "watchlist_refresh_batch",
            batch=batch_idx,
            total_batches=total_batches,
            batch_size=len(batch_symbols),
        )

        batch_prices = fetcher.fetch_price_data(batch_symbols)
        price_map.update(batch_prices)

        # Delay between batches (except after last batch)
        if batch_idx < total_batches and batch_delay_seconds > 0:
            time.sleep(batch_delay_seconds)

    processed = 0
    now = datetime.now(UTC)
    processed_symbols: list[str] = []

    for row in items_df.iter_rows(named=True):
        symbol = row["symbol"]
        item_id = row["id"]

        price_data = price_map.get(symbol)
        if not price_data or price_data.price <= 0:
            logger.warning(
                "watchlist_refresh_missing_price",
                symbol=symbol,
                item_id=item_id,
            )
            continue

        change_pct = _calculate_price_change(storage, symbol, price_data.price)
        technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
        technical_snapshot.price = price_data.price

        breakdown = calculate_watchlist_scores(
            WatchlistScoreInputs(
                price=price_data,
                price_change_pct=change_pct,
                technical=technical_snapshot,
                weights=default_weights,
                now=now,
            )
        )

        snapshot = WatchlistSnapshot(
            item_id=item_id,
            fetched_at=now,
            price=price_data.price,
            change_pct=change_pct,
            beta=price_data.beta,
            volatility=price_data.volatility,
            overall_score=breakdown.overall,
            technical_score=breakdown.technical.score,
            raw_metrics=breakdown.to_snapshot_payload(),
        )

        storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())
        processed += 1
        processed_symbols.append(symbol)

    logger.info(
        "watchlist_refresh_completed",
        processed=processed,
        symbols=processed_symbols,
        batches=total_batches,
    )
    return {"processed": processed, "symbols": processed_symbols, "batches": total_batches}


class WatchlistService:
    """Service layer for watchlist operations."""

    def __init__(self, storage: DuckDBStorage):
        """Initialize watchlist service."""
        self.storage = storage
        self.price_fetcher = PriceDataFetcher(storage)

    def get_items_with_scores(self, account_id: str) -> list[dict[str, Any]]:
        """
        Get all watchlist items for an account with their latest scores.

        Args:
            account_id: Account ID

        Returns:
            List of watchlist items with scores and alert flags
        """
        items_df = self.storage.query(
            """
            SELECT wi.id, wi.account_id, wi.symbol, wi.note,
                   wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.account_id = ?
            ORDER BY wi.created_at DESC
            """,
            [account_id],
        )

        if items_df.is_empty():
            return []

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            # Convert datetime objects to ISO strings if needed
            created_at = row["created_at"]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            updated_at = row["updated_at"]
            if hasattr(updated_at, "isoformat"):
                updated_at = updated_at.isoformat()

            item_data = {
                "id": row["id"],
                "account_id": row["account_id"],
                "symbol": row["symbol"],
                "note": row.get("note"),
                "created_at": created_at,
                "updated_at": updated_at,
                "score": None,
                "score_alert": False,
            }

            # Get latest snapshot
            snapshot_df = self.storage.query(
                """
                SELECT overall_score, technical_score, fetched_at, raw_metrics
                FROM watchlist_snapshots
                WHERE item_id = ?
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                [row["id"]],
            )

            if not snapshot_df.is_empty():
                snap_row = snapshot_df.to_dicts()[0]
                raw_metrics = snap_row.get("raw_metrics", {})

                # Parse raw_metrics if it's a string (JSON)
                if isinstance(raw_metrics, str):
                    try:
                        raw_metrics = json.loads(raw_metrics)
                    except (json.JSONDecodeError, TypeError):
                        raw_metrics = {}

                # Check if >10 point change in last 7 days
                alert = self._check_score_alert(row["id"], snap_row["overall_score"])

                item_data["score"] = {
                    "price": raw_metrics.get("price", {}),
                    "technical": raw_metrics.get("technical", {}),
                    "overall": snap_row["overall_score"],
                }
                item_data["score_alert"] = alert

            results.append(item_data)

        return results

    def _check_score_alert(self, item_id: str, current_score: float) -> bool:
        """Check if score changed >10 points in last 7 days."""
        history_df = self.storage.query(
            """
            SELECT overall_score
            FROM watchlist_snapshots
            WHERE item_id = ?
              AND fetched_at >= current_timestamp - INTERVAL '7 days'
            ORDER BY fetched_at ASC
            LIMIT 1
            """,
            [item_id],
        )

        if history_df.is_empty():
            return False

        week_ago_score = float(history_df["overall_score"][0])
        return abs(current_score - week_ago_score) > 10.0

    def refresh_scores(self, item_id: str, symbol: str) -> None:
        """
        Refresh scores for a single watchlist item.

        Args:
            item_id: Watchlist item ID
            symbol: Stock symbol
        """
        price_data = self.price_fetcher.fetch_price_data([symbol]).get(symbol)
        if not price_data or price_data.price <= 0:
            raise ValueError(f"Unable to fetch price data for {symbol}")

        technical_map = _load_latest_technical(self.storage, [symbol])
        technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
        technical_snapshot.price = price_data.price

        change_pct = _calculate_price_change(self.storage, symbol, price_data.price)
        default_weights = _load_default_weights(self.storage)
        now = datetime.now(UTC)

        breakdown = calculate_watchlist_scores(
            WatchlistScoreInputs(
                price=price_data,
                price_change_pct=change_pct,
                technical=technical_snapshot,
                weights=default_weights,
                now=now,
            )
        )

        snapshot = WatchlistSnapshot(
            item_id=item_id,
            fetched_at=now,
            price=price_data.price,
            change_pct=change_pct,
            beta=price_data.beta,
            volatility=price_data.volatility,
            overall_score=breakdown.overall,
            technical_score=breakdown.technical.score,
            raw_metrics=breakdown.to_snapshot_payload(),
        )

        self.storage.query_mgr.upsert_watchlist_snapshot(**snapshot.to_upsert_params())

        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)
