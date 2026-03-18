"""Repository layer for watchlist database operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl

from ..storage import PortfolioStorage
from ..utils.db_helpers import ensure_symbol_exists


class _WatchlistCoreReadRepository:
    """Core read-oriented watchlist queries."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage

    def get_all_items_with_snapshots(self) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT wi.id, wi.symbol, wi.note, wi.source, wi.created_at, wi.updated_at,
                   ws.overall_score, ws.technical_score, ws.fetched_at, ws.raw_metrics,
                   ws.signal_type, ws.signal_strength, ws.narrative_headline,
                   ws.recommended_style, ws.style_confidence, ws.optimal_holding_period, ws.risk_level,
                   ws.entry_price, ws.stop_loss, ws.profit_target, ws.position_size_shares,
                   ws.narrative_action_plan, ws.narrative_position_sizing,
                   ws.narrative_company_health, ws.narrative_special_notes,
                   ws.company_health, ws.earnings_date, ws.earnings_days_away,
                   ws.news_sentiment_score, ws.recent_news_headlines,
                   ws.timeframe_short_aligned, ws.timeframe_long_aligned, ws.volume_relative
            FROM watchlist_items wi
            LEFT JOIN LATERAL (
                SELECT * FROM watchlist_snapshots_v WHERE item_id = wi.id
                ORDER BY fetched_at DESC LIMIT 1
            ) ws ON TRUE
            WHERE wi.symbol NOT LIKE 'ZZTEST%%'
            ORDER BY wi.created_at DESC
            """
        )

    def get_item_by_id(self, item_id: str) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT wi.id, wi.symbol, wi.note, wi.created_at, wi.updated_at
            FROM watchlist_items wi
            WHERE wi.id = ?
            """,
            [item_id],
        )

    def get_latest_snapshot(self, item_id: str) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT overall_score, technical_score, fetched_at, raw_metrics,
                   signal_type, signal_strength, narrative_headline,
                   recommended_style, style_confidence, optimal_holding_period, risk_level,
                   entry_price, stop_loss, profit_target, position_size_shares,
                   narrative_action_plan, narrative_position_sizing,
                   narrative_company_health, narrative_special_notes,
                   company_health, earnings_date, earnings_days_away,
                   news_sentiment_score, recent_news_headlines
            FROM watchlist_snapshots_v
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )

    def get_score_history(self, item_id: str, limit: int = 30) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT overall_score
            FROM watchlist_snapshots_v
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT ?
            """,
            [item_id, limit],
        )

    def get_latest_daily_report(self) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT id, report_date, symbols_added, symbols_removed, score_changes, generated_at
            FROM watchlist_daily_reports
            ORDER BY report_date DESC
            LIMIT 1
            """
        )

    def get_all_symbols(self) -> pl.DataFrame:
        return self.storage.query("SELECT id, symbol FROM watchlist_items")

    def get_symbol_by_item_id(self, item_id: str) -> pl.DataFrame:
        return self.storage.query("SELECT symbol FROM watchlist_items WHERE id = ?", [item_id])


class _WatchlistReviewReadRepository:
    """Review and historical read queries."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage

    def get_item_with_snapshots(self, item_id: str) -> pl.DataFrame:
        return self.storage.query("SELECT * FROM watchlist_items WHERE id = ?", [item_id])

    def get_latest_snapshot_for_review(self, item_id: str) -> pl.DataFrame:
        return self.storage.query(
            """
            SELECT * FROM watchlist_snapshots_v
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )

    def get_snapshots_with_metrics(self, item_id: str, days: int = 60) -> pl.DataFrame:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return self.storage.query(
            """
            SELECT item_id, fetched_at, price, technical_score, overall_score, raw_metrics
            FROM watchlist_snapshots_v
            WHERE item_id = ?
              AND fetched_at >= ?
            ORDER BY fetched_at DESC
            """,
            [item_id, cutoff],
        )


class _WatchlistNewsRepository:
    """News cache queries for watchlist symbols."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage

    def get_recent_news(
        self,
        symbol: str,
        hours: int = 24,
        limit: int = 20,
    ) -> list[tuple[Any, ...]]:
        start_time = datetime.now(UTC) - timedelta(hours=hours)
        with self.storage.connection() as conn:
            rows: list[tuple[Any, ...]] = conn.execute(
                """
                SELECT
                    symbol, headline, url, summary, news_source_name, author, image_url,
                    published_at, sentiment_score, sentiment_label, sentiment_confidence,
                    sentiment_model, raw_payload, content_hash, fetched_at, filing_type,
                    is_material_event, story_id, is_primary_article, coverage_count,
                    impact_summary, actionable_insight
                FROM news_cache
                WHERE symbol = %s
                  AND published_at >= %s
                  AND (is_primary_article = true OR is_primary_article IS NULL)
                ORDER BY published_at DESC, is_material_event DESC
                LIMIT %s
                """,
                [symbol, start_time, limit],
            ).fetchall()
        return rows

    def get_recent_news_batch(
        self,
        symbols: list[str],
        hours: int = 24,
        limit_per_symbol: int = 20,
    ) -> dict[str, list[tuple[Any, ...]]]:
        if not symbols:
            return {}

        start_time = datetime.now(UTC) - timedelta(hours=hours)
        placeholders = ", ".join(["%s"] * len(symbols))
        with self.storage.connection() as conn:
            rows: list[tuple[Any, ...]] = conn.execute(
                f"""
                SELECT
                    symbol, headline, url, summary, news_source_name, author, image_url,
                    published_at, sentiment_score, sentiment_label, sentiment_confidence,
                    sentiment_model, raw_payload, content_hash, fetched_at, filing_type,
                    is_material_event, story_id, is_primary_article, coverage_count,
                    impact_summary, actionable_insight
                FROM news_cache
                WHERE symbol IN ({placeholders})
                  AND published_at >= %s
                  AND (is_primary_article = true OR is_primary_article IS NULL)
                ORDER BY symbol, published_at DESC, is_material_event DESC
                """,
                [*symbols, start_time],
            ).fetchall()

        result: dict[str, list[tuple[Any, ...]]] = {}
        for row in rows:
            sym = str(row[0])
            if sym not in result:
                result[sym] = []
            if len(result[sym]) < limit_per_symbol:
                result[sym].append(row)
        return result


class _WatchlistWriteRepository:
    """Write-oriented watchlist persistence operations."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage

    def upsert_snapshot(self, snapshot_params: dict[str, Any]) -> None:
        self.storage.query_mgr.upsert_watchlist_snapshot(**snapshot_params)

    def check_item_exists(self, symbol: str) -> bool:
        df = self.storage.query("SELECT id FROM watchlist_items WHERE symbol = ?", [symbol])
        return not df.is_empty()

    def create_item(self, item_id: str, symbol: str, note: str | None, now: str) -> None:
        with self.storage.connection() as conn:
            ensure_symbol_exists(conn, symbol)
            conn.execute(
                """
                INSERT INTO watchlist_items (id, symbol, note, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [item_id, symbol, note, now, now],
            )
            conn.commit()

    def update_item_note(self, item_id: str, note: str | None, now: str) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE watchlist_items
                SET note = ?, updated_at = ?
                WHERE id = ?
                """,
                [note, now, item_id],
            )
            conn.commit()

    def delete_item(self, item_id: str) -> None:
        with self.storage.connection() as conn:
            conn.execute("DELETE FROM watchlist_snapshots WHERE item_id = ?", [item_id])
            conn.execute("DELETE FROM watchlist_items WHERE id = ?", [item_id])
            conn.commit()

    def store_strategy_review(
        self,
        review_id: str,
        item_id: str,
        snapshot_id: str | None,
        symbol: str,
        review_text: str,
        provider: str,
        is_valid: bool,
        disagreement: bool | None,
        token_usage_json: str,
        created_at: str,
        pair_id: str | None = None,
        severity: str | None = None,
        agreement: float | None = None,
        provider_disagreement: bool | None = None,
    ) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_reviews (
                    id, watchlist_item_id, snapshot_id, symbol, review_text,
                    provider, is_valid, disagreement, token_usage, created_at,
                    review_pair_id, disagreement_severity, provider_disagreement, agreement_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    review_id,
                    item_id,
                    snapshot_id,
                    symbol,
                    review_text,
                    provider,
                    is_valid,
                    disagreement,
                    token_usage_json,
                    created_at,
                    pair_id,
                    severity,
                    agreement,
                    provider_disagreement,
                ],
            )
            conn.commit()


class WatchlistRepository(
    _WatchlistCoreReadRepository,
    _WatchlistReviewReadRepository,
    _WatchlistNewsRepository,
    _WatchlistWriteRepository,
):
    """Composite repository preserving the existing public API."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage


__all__ = ["WatchlistRepository"]
