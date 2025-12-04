"""PostgreSQL query operations for portfolio data retrieval.

This module provides preset query methods and raw SQL execution capabilities.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

import polars as pl

from ..logging_config import get_logger
from .types import ParameterValue

if TYPE_CHECKING:
    from .connection import ConnectionManager

logger = get_logger(__name__)


class QueryManager:
    """Manages query operations for PostgreSQL storage.

    Provides preset query methods for common use cases and raw SQL execution.
    """

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize query manager.

        Args:
            connection_mgr: ConnectionManager instance for database access.
        """
        self.connection_mgr = connection_mgr

    def query(self, sql: str, params: list[ParameterValue] | None = None) -> pl.DataFrame:
        """Execute a SQL query and return results as a Polars DataFrame.

        Args:
            sql: SQL query string
            params: Optional list of parameter values for parameterized queries

        Returns:
            Polars DataFrame with query results
        """
        with self.connection_mgr.connection() as conn:
            if params:
                result = conn.execute(sql, params).fetchdf()
            else:
                result = conn.execute(sql).fetchdf()
            # fetchdf() already returns polars DataFrame
            return result  # type: ignore[no-any-return]

    def get_watchlist_items_by_account(self, account_id: str) -> pl.DataFrame:
        """Return all watchlist items ordered by symbol.

        Note: account_id parameter is deprecated but kept for backward compatibility.
        Watchlist items are now global (not tied to accounts).
        """
        sql = """
            SELECT
                id,
                symbol,
                metadata,
                note,
                created_at,
                updated_at
            FROM watchlist_items
            ORDER BY symbol
        """
        return self.query(sql)

    def get_watchlist_snapshot_history(
        self,
        item_id: str,
        *,
        limit: int = 100,
        start_at: datetime | None = None,
    ) -> pl.DataFrame:
        """Return historical snapshots for a watchlist item."""
        sql = """
            SELECT
                item_id,
                fetched_at,
                price,
                change_pct,
                beta,
                volatility,
                news_score,
                technical_score,
                fundamental_score,
                ai_score,
                ai_confidence,
                sector_score,
                competitor_score,
                overall_score,
                raw_metrics
            FROM watchlist_snapshots
            WHERE item_id = ?
        """
        params: list[ParameterValue] = [item_id]

        if start_at is not None:
            sql += " AND fetched_at >= ?"
            params.append(start_at)

        sql += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)

        return self.query(sql, params)

    def _serialize_snapshot_json_fields(
        self,
        raw_metrics: dict[str, Any] | None,
        narrative_why_bullets: dict[str, Any] | None,
        narrative_company_health: dict[str, Any] | None,
        narrative_technical: dict[str, Any] | None,
        recent_news_headlines: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        """Serialize dict fields to JSON strings for database storage.

        Args:
            raw_metrics: Raw metrics dictionary
            narrative_why_bullets: Narrative why bullets dictionary
            narrative_company_health: Narrative company health dictionary
            narrative_technical: Narrative technical dictionary
            recent_news_headlines: Recent news headlines dictionary

        Returns:
            Tuple of (raw_metrics_json, why_bullets_json, company_health_json,
                     technical_json, headlines_json)
        """
        return (
            json.dumps(raw_metrics) if raw_metrics is not None else None,
            json.dumps(narrative_why_bullets) if narrative_why_bullets is not None else None,
            json.dumps(narrative_company_health) if narrative_company_health is not None else None,
            json.dumps(narrative_technical) if narrative_technical is not None else None,
            json.dumps(recent_news_headlines) if recent_news_headlines is not None else None,
        )

    def _build_snapshot_upsert_sql(self) -> str:
        """Build the SQL query for watchlist snapshot upsert.

        Returns:
            SQL query string with INSERT...ON CONFLICT UPDATE
        """
        return """
            INSERT INTO watchlist_snapshots (
                item_id, fetched_at, price, change_pct, beta, volatility,
                news_score, technical_score, fundamental_score, ai_score, ai_confidence,
                sector_score, competitor_score, overall_score, is_stale, raw_metrics,
                signal_type, signal_strength, narrative_headline, narrative_why_bullets,
                narrative_company_health, narrative_technical, narrative_action_plan,
                narrative_position_sizing, narrative_special_notes,
                entry_price, stop_loss, profit_target, position_size_shares,
                recommended_style, style_confidence, optimal_holding_period, risk_level,
                company_health, earnings_date, earnings_days_away,
                news_sentiment_score, recent_news_headlines,
                volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d
            ) VALUES (
                ?, ?, ?, ?, ?, ?,  ?, ?, ?, ?, ?,  ?, ?, ?, ?, ?,
                ?, ?, ?, ?,  ?, ?, ?, ?, ?,  ?, ?, ?, ?,
                ?, ?, ?, ?,  ?, ?, ?,  ?, ?,  ?, ?, ?, ?
            )
            ON CONFLICT (item_id, fetched_at) DO UPDATE SET
                price = EXCLUDED.price,
                change_pct = EXCLUDED.change_pct,
                beta = EXCLUDED.beta,
                volatility = EXCLUDED.volatility,
                news_score = EXCLUDED.news_score,
                technical_score = EXCLUDED.technical_score,
                fundamental_score = EXCLUDED.fundamental_score,
                ai_score = EXCLUDED.ai_score,
                ai_confidence = EXCLUDED.ai_confidence,
                sector_score = EXCLUDED.sector_score,
                competitor_score = EXCLUDED.competitor_score,
                overall_score = EXCLUDED.overall_score,
                is_stale = EXCLUDED.is_stale,
                raw_metrics = EXCLUDED.raw_metrics,
                signal_type = EXCLUDED.signal_type,
                signal_strength = EXCLUDED.signal_strength,
                narrative_headline = EXCLUDED.narrative_headline,
                narrative_why_bullets = EXCLUDED.narrative_why_bullets,
                narrative_company_health = EXCLUDED.narrative_company_health,
                narrative_technical = EXCLUDED.narrative_technical,
                narrative_action_plan = EXCLUDED.narrative_action_plan,
                narrative_position_sizing = EXCLUDED.narrative_position_sizing,
                narrative_special_notes = EXCLUDED.narrative_special_notes,
                entry_price = EXCLUDED.entry_price,
                stop_loss = EXCLUDED.stop_loss,
                profit_target = EXCLUDED.profit_target,
                position_size_shares = EXCLUDED.position_size_shares,
                recommended_style = EXCLUDED.recommended_style,
                style_confidence = EXCLUDED.style_confidence,
                optimal_holding_period = EXCLUDED.optimal_holding_period,
                risk_level = EXCLUDED.risk_level,
                company_health = EXCLUDED.company_health,
                earnings_date = EXCLUDED.earnings_date,
                earnings_days_away = EXCLUDED.earnings_days_away,
                news_sentiment_score = EXCLUDED.news_sentiment_score,
                recent_news_headlines = EXCLUDED.recent_news_headlines,
                volume_relative = EXCLUDED.volume_relative,
                timeframe_short_aligned = EXCLUDED.timeframe_short_aligned,
                timeframe_long_aligned = EXCLUDED.timeframe_long_aligned,
                percentile_rank_30d = EXCLUDED.percentile_rank_30d
        """

    def _prepare_snapshot_parameters(
        self,
        item_id: str,
        fetched_at: datetime,
        price: float | None,
        change_pct: float | None,
        beta: float | None,
        volatility: float | None,
        news_score: float | None,
        technical_score: float | None,
        fundamental_score: float | None,
        ai_score: float | None,
        ai_confidence: float | None,
        sector_score: float | None,
        competitor_score: float | None,
        overall_score: float | None,
        is_stale: bool,
        raw_metrics_json: str | None,
        signal_type: str | None,
        signal_strength: int | None,
        narrative_headline: str | None,
        narrative_why_bullets_json: str | None,
        narrative_company_health_json: str | None,
        narrative_technical_json: str | None,
        narrative_action_plan: str | None,
        narrative_position_sizing: str | None,
        narrative_special_notes: str | None,
        entry_price: float | None,
        stop_loss: float | None,
        profit_target: float | None,
        position_size_shares: int | None,
        recommended_style: str | None,
        style_confidence: int | None,
        optimal_holding_period: str | None,
        risk_level: str | None,
        company_health: str | None,
        earnings_date: datetime | None,
        earnings_days_away: int | None,
        news_sentiment_score: float | None,
        recent_news_headlines_json: str | None,
        volume_relative: float | None,
        timeframe_short_aligned: bool,
        timeframe_long_aligned: bool,
        percentile_rank_30d: float | None,
    ) -> list[ParameterValue]:
        """Prepare parameter list for snapshot upsert query.

        Args:
            All parameters that will be bound to the SQL query

        Returns:
            List of parameters in the correct order for the SQL query
        """
        return [
            item_id,
            fetched_at,
            price,
            change_pct,
            beta,
            volatility,
            news_score,
            technical_score,
            fundamental_score,
            ai_score,
            ai_confidence,
            sector_score,
            competitor_score,
            overall_score,
            is_stale,
            raw_metrics_json,
            signal_type,
            signal_strength,
            narrative_headline,
            narrative_why_bullets_json,
            narrative_company_health_json,
            narrative_technical_json,
            narrative_action_plan,
            narrative_position_sizing,
            narrative_special_notes,
            entry_price,
            stop_loss,
            profit_target,
            position_size_shares,
            recommended_style,
            style_confidence,
            optimal_holding_period,
            risk_level,
            company_health,
            earnings_date,
            earnings_days_away,
            news_sentiment_score,
            recent_news_headlines_json,
            volume_relative,
            timeframe_short_aligned,
            timeframe_long_aligned,
            percentile_rank_30d,
        ]

    def upsert_watchlist_snapshot(
        self,
        item_id: str,
        fetched_at: datetime,
        *,
        price: float | None = None,
        change_pct: float | None = None,
        beta: float | None = None,
        volatility: float | None = None,
        news_score: float | None = None,
        technical_score: float | None = None,
        fundamental_score: float | None = None,
        ai_score: float | None = None,
        ai_confidence: float | None = None,
        sector_score: float | None = None,
        competitor_score: float | None = None,
        overall_score: float | None = None,
        is_stale: bool = False,
        raw_metrics: dict[str, Any] | None = None,
        # Narrative intelligence fields
        signal_type: str | None = None,
        signal_strength: int | None = None,
        narrative_headline: str | None = None,
        narrative_why_bullets: dict[str, Any] | None = None,
        narrative_company_health: dict[str, Any] | None = None,
        narrative_technical: dict[str, Any] | None = None,
        narrative_action_plan: str | None = None,
        narrative_position_sizing: str | None = None,
        narrative_special_notes: str | None = None,
        # Trade calculation fields
        entry_price: float | None = None,
        stop_loss: float | None = None,
        profit_target: float | None = None,
        position_size_shares: int | None = None,
        # Trading style fields
        recommended_style: str | None = None,
        style_confidence: int | None = None,
        optimal_holding_period: str | None = None,
        risk_level: str | None = None,
        # Fundamental & news data fields
        company_health: str | None = None,
        earnings_date: datetime | None = None,
        earnings_days_away: int | None = None,
        news_sentiment_score: float | None = None,
        recent_news_headlines: dict[str, Any] | None = None,
        # Volume & timeframe analysis fields (PRD #0022)
        volume_relative: float | None = None,
        timeframe_short_aligned: bool = False,
        timeframe_long_aligned: bool = False,
        percentile_rank_30d: float | None = None,
    ) -> None:
        """Insert or update a watchlist snapshot record."""
        # Serialize dict fields to JSON
        (
            raw_metrics_json,
            narrative_why_bullets_json,
            narrative_company_health_json,
            narrative_technical_json,
            recent_news_headlines_json,
        ) = self._serialize_snapshot_json_fields(
            raw_metrics,
            narrative_why_bullets,
            narrative_company_health,
            narrative_technical,
            recent_news_headlines,
        )

        # Build SQL query
        sql = self._build_snapshot_upsert_sql()

        # Prepare parameters
        params = self._prepare_snapshot_parameters(
            item_id,
            fetched_at,
            price,
            change_pct,
            beta,
            volatility,
            news_score,
            technical_score,
            fundamental_score,
            ai_score,
            ai_confidence,
            sector_score,
            competitor_score,
            overall_score,
            is_stale,
            raw_metrics_json,
            signal_type,
            signal_strength,
            narrative_headline,
            narrative_why_bullets_json,
            narrative_company_health_json,
            narrative_technical_json,
            narrative_action_plan,
            narrative_position_sizing,
            narrative_special_notes,
            entry_price,
            stop_loss,
            profit_target,
            position_size_shares,
            recommended_style,
            style_confidence,
            optimal_holding_period,
            risk_level,
            company_health,
            earnings_date,
            earnings_days_away,
            news_sentiment_score,
            recent_news_headlines_json,
            volume_relative,
            timeframe_short_aligned,
            timeframe_long_aligned,
            percentile_rank_30d,
        )

        # Execute upsert to legacy table
        with self.connection_mgr.connection() as conn:
            conn.execute(sql, params)

            # Also write to normalized tables (Phase 1: dual-write)
            self._upsert_normalized_snapshot(
                conn,
                item_id=item_id,
                fetched_at=fetched_at,
                price=price,
                change_pct=change_pct,
                overall_score=overall_score,
                technical_score=technical_score,
                fundamental_score=fundamental_score,
                news_score=news_score,
                ai_score=ai_score,
                ai_confidence=ai_confidence,
                is_stale=is_stale,
                signal_type=signal_type,
                signal_strength=signal_strength,
                # Technical
                raw_metrics=raw_metrics_json,
                beta=beta,
                volatility=volatility,
                volume_relative=volume_relative,
                timeframe_short_aligned=timeframe_short_aligned,
                timeframe_long_aligned=timeframe_long_aligned,
                percentile_rank_30d=percentile_rank_30d,
                # Narrative
                narrative_headline=narrative_headline,
                narrative_why_bullets=narrative_why_bullets_json,
                narrative_company_health=narrative_company_health_json,
                narrative_technical=narrative_technical_json,
                narrative_action_plan=narrative_action_plan,
                narrative_position_sizing=narrative_position_sizing,
                narrative_special_notes=narrative_special_notes,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target,
                position_size_shares=position_size_shares,
                recommended_style=recommended_style,
                style_confidence=style_confidence,
                optimal_holding_period=optimal_holding_period,
                risk_level=risk_level,
                company_health=company_health,
                # News
                news_sentiment_score=news_sentiment_score,
                recent_news_headlines=recent_news_headlines_json,
                sector_score=sector_score,
                competitor_score=competitor_score,
                earnings_date=earnings_date,
                earnings_days_away=earnings_days_away,
            )

            conn.commit()  # Commit both old and new tables

    def _upsert_normalized_snapshot(
        self,
        conn: Any,
        *,
        item_id: str,
        fetched_at: datetime,
        price: float | None,
        change_pct: float | None,
        overall_score: float | None,
        technical_score: float | None,
        fundamental_score: float | None,
        news_score: float | None,
        ai_score: float | None,
        ai_confidence: float | None,
        is_stale: bool,
        signal_type: str | None,
        signal_strength: int | None,
        # Technical
        raw_metrics: str | None,
        beta: float | None,
        volatility: float | None,
        volume_relative: float | None,
        timeframe_short_aligned: bool,
        timeframe_long_aligned: bool,
        percentile_rank_30d: float | None,
        # Narrative
        narrative_headline: str | None,
        narrative_why_bullets: str | None,
        narrative_company_health: str | None,
        narrative_technical: str | None,
        narrative_action_plan: str | None,
        narrative_position_sizing: str | None,
        narrative_special_notes: str | None,
        entry_price: float | None,
        stop_loss: float | None,
        profit_target: float | None,
        position_size_shares: int | None,
        recommended_style: str | None,
        style_confidence: int | None,
        optimal_holding_period: str | None,
        risk_level: str | None,
        company_health: str | None,
        # News
        news_sentiment_score: float | None,
        recent_news_headlines: str | None,
        sector_score: float | None,
        competitor_score: float | None,
        earnings_date: datetime | None,
        earnings_days_away: int | None,
    ) -> None:
        """Write to normalized snapshot tables (Phase 1: dual-write with legacy).

        This method inserts/updates data in the 4 normalized tables:
        - watchlist_snapshots_core: Core metrics
        - watchlist_technical_metrics: Technical indicators
        - watchlist_narrative: AI narratives and trade calculations
        - watchlist_news_summary: News data

        Called within an existing transaction from upsert_watchlist_snapshot.
        """
        # 1. Insert into core table, get snapshot_id
        core_sql = """
            INSERT INTO watchlist_snapshots_core (
                item_id, fetched_at, price, change_pct,
                overall_score, technical_score, fundamental_score, news_score,
                ai_score, ai_confidence, is_stale, signal_type, signal_strength
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (item_id, fetched_at) DO UPDATE SET
                price = EXCLUDED.price,
                change_pct = EXCLUDED.change_pct,
                overall_score = EXCLUDED.overall_score,
                technical_score = EXCLUDED.technical_score,
                fundamental_score = EXCLUDED.fundamental_score,
                news_score = EXCLUDED.news_score,
                ai_score = EXCLUDED.ai_score,
                ai_confidence = EXCLUDED.ai_confidence,
                is_stale = EXCLUDED.is_stale,
                signal_type = EXCLUDED.signal_type,
                signal_strength = EXCLUDED.signal_strength
            RETURNING id
        """
        result = conn.execute(
            core_sql,
            [
                item_id,
                fetched_at,
                price,
                change_pct,
                overall_score,
                technical_score,
                fundamental_score,
                news_score,
                ai_score,
                ai_confidence,
                is_stale,
                signal_type,
                signal_strength,
            ],
        )
        row = result.fetchone()
        if not row:
            return  # No ID returned, skip dependent tables
        snapshot_id = row[0]

        # 2. Insert/update technical metrics
        tech_sql = """
            INSERT INTO watchlist_technical_metrics (
                snapshot_id, raw_metrics, beta, volatility,
                volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d
            ) VALUES (?, ?::jsonb, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_id) DO UPDATE SET
                raw_metrics = EXCLUDED.raw_metrics,
                beta = EXCLUDED.beta,
                volatility = EXCLUDED.volatility,
                volume_relative = EXCLUDED.volume_relative,
                timeframe_short_aligned = EXCLUDED.timeframe_short_aligned,
                timeframe_long_aligned = EXCLUDED.timeframe_long_aligned,
                percentile_rank_30d = EXCLUDED.percentile_rank_30d
        """
        conn.execute(
            tech_sql,
            [
                snapshot_id,
                raw_metrics,
                beta,
                volatility,
                volume_relative,
                timeframe_short_aligned,
                timeframe_long_aligned,
                percentile_rank_30d,
            ],
        )

        # 3. Insert/update narrative
        narrative_sql = """
            INSERT INTO watchlist_narrative (
                snapshot_id, narrative_headline, narrative_why_bullets, narrative_company_health,
                narrative_technical, narrative_action_plan, narrative_position_sizing, narrative_special_notes,
                entry_price, stop_loss, profit_target, position_size_shares,
                recommended_style, style_confidence, optimal_holding_period, risk_level, company_health
            ) VALUES (?, ?, ?::jsonb, ?::jsonb, ?::jsonb, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_id) DO UPDATE SET
                narrative_headline = EXCLUDED.narrative_headline,
                narrative_why_bullets = EXCLUDED.narrative_why_bullets,
                narrative_company_health = EXCLUDED.narrative_company_health,
                narrative_technical = EXCLUDED.narrative_technical,
                narrative_action_plan = EXCLUDED.narrative_action_plan,
                narrative_position_sizing = EXCLUDED.narrative_position_sizing,
                narrative_special_notes = EXCLUDED.narrative_special_notes,
                entry_price = EXCLUDED.entry_price,
                stop_loss = EXCLUDED.stop_loss,
                profit_target = EXCLUDED.profit_target,
                position_size_shares = EXCLUDED.position_size_shares,
                recommended_style = EXCLUDED.recommended_style,
                style_confidence = EXCLUDED.style_confidence,
                optimal_holding_period = EXCLUDED.optimal_holding_period,
                risk_level = EXCLUDED.risk_level,
                company_health = EXCLUDED.company_health
        """
        conn.execute(
            narrative_sql,
            [
                snapshot_id,
                narrative_headline,
                narrative_why_bullets,
                narrative_company_health,
                narrative_technical,
                narrative_action_plan,
                narrative_position_sizing,
                narrative_special_notes,
                entry_price,
                stop_loss,
                profit_target,
                position_size_shares,
                recommended_style,
                style_confidence,
                optimal_holding_period,
                risk_level,
                company_health,
            ],
        )

        # 4. Insert/update news summary
        news_sql = """
            INSERT INTO watchlist_news_summary (
                snapshot_id, news_sentiment_score, recent_news_headlines,
                sector_score, competitor_score, earnings_date, earnings_days_away
            ) VALUES (?, ?, ?::jsonb, ?, ?, ?, ?)
            ON CONFLICT (snapshot_id) DO UPDATE SET
                news_sentiment_score = EXCLUDED.news_sentiment_score,
                recent_news_headlines = EXCLUDED.recent_news_headlines,
                sector_score = EXCLUDED.sector_score,
                competitor_score = EXCLUDED.competitor_score,
                earnings_date = EXCLUDED.earnings_date,
                earnings_days_away = EXCLUDED.earnings_days_away
        """
        conn.execute(
            news_sql,
            [
                snapshot_id,
                news_sentiment_score,
                recent_news_headlines,
                sector_score,
                competitor_score,
                earnings_date,
                earnings_days_away,
            ],
        )
