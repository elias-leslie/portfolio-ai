"""Snapshot upsert helpers for watchlist storage queries."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import ConnectionManager


def do_upsert_watchlist_snapshot(
    connection_mgr: ConnectionManager,
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
    raw_metrics: dict | None = None,
    signal_type: str | None = None,
    signal_strength: int | None = None,
    narrative_headline: str | None = None,
    narrative_why_bullets: dict | None = None,
    narrative_company_health: dict | None = None,
    narrative_technical: dict | None = None,
    narrative_action_plan: str | None = None,
    narrative_position_sizing: str | None = None,
    narrative_special_notes: str | None = None,
    entry_price: float | None = None,
    stop_loss: float | None = None,
    profit_target: float | None = None,
    position_size_shares: int | None = None,
    recommended_style: str | None = None,
    style_confidence: int | None = None,
    optimal_holding_period: str | None = None,
    risk_level: str | None = None,
    company_health: str | None = None,
    earnings_date: datetime | None = None,
    earnings_days_away: int | None = None,
    news_sentiment_score: float | None = None,
    recent_news_headlines: dict | None = None,
    volume_relative: float | None = None,
    timeframe_short_aligned: bool = False,
    timeframe_long_aligned: bool = False,
    percentile_rank_30d: float | None = None,
) -> None:
    """Insert or update a watchlist snapshot record (legacy + normalized tables)."""
    (
        raw_metrics_json,
        narrative_why_bullets_json,
        narrative_company_health_json,
        narrative_technical_json,
        recent_news_headlines_json,
    ) = serialize_snapshot_json_fields(
        raw_metrics, narrative_why_bullets,
        narrative_company_health, narrative_technical, recent_news_headlines,
    )
    sql = build_snapshot_upsert_sql()
    params = prepare_snapshot_parameters(
        item_id, fetched_at, price, change_pct, overall_score, is_stale
    )
    with connection_mgr.connection() as conn:
        conn.execute(sql, params)
        execute_normalized_snapshot_upsert(
            conn,
            item_id=item_id, fetched_at=fetched_at,
            price=price, change_pct=change_pct, overall_score=overall_score,
            technical_score=technical_score, fundamental_score=fundamental_score,
            news_score=news_score, ai_score=ai_score, ai_confidence=ai_confidence,
            is_stale=is_stale, signal_type=signal_type, signal_strength=signal_strength,
            raw_metrics=raw_metrics_json, beta=beta, volatility=volatility,
            volume_relative=volume_relative,
            timeframe_short_aligned=timeframe_short_aligned,
            timeframe_long_aligned=timeframe_long_aligned,
            percentile_rank_30d=percentile_rank_30d,
            narrative_headline=narrative_headline,
            narrative_why_bullets=narrative_why_bullets_json,
            narrative_company_health=narrative_company_health_json,
            narrative_technical=narrative_technical_json,
            narrative_action_plan=narrative_action_plan,
            narrative_position_sizing=narrative_position_sizing,
            narrative_special_notes=narrative_special_notes,
            entry_price=entry_price, stop_loss=stop_loss,
            profit_target=profit_target, position_size_shares=position_size_shares,
            recommended_style=recommended_style, style_confidence=style_confidence,
            optimal_holding_period=optimal_holding_period,
            risk_level=risk_level, company_health=company_health,
            news_sentiment_score=news_sentiment_score,
            recent_news_headlines=recent_news_headlines_json,
            sector_score=sector_score, competitor_score=competitor_score,
            earnings_date=earnings_date, earnings_days_away=earnings_days_away,
        )
        conn.commit()


def serialize_snapshot_json_fields(
    raw_metrics: dict | None,
    narrative_why_bullets: dict | None,
    narrative_company_health: dict | None,
    narrative_technical: dict | None,
    recent_news_headlines: dict | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Serialize dict fields to JSON strings for database storage."""
    return (
        json.dumps(raw_metrics) if raw_metrics is not None else None,
        json.dumps(narrative_why_bullets) if narrative_why_bullets is not None else None,
        json.dumps(narrative_company_health) if narrative_company_health is not None else None,
        json.dumps(narrative_technical) if narrative_technical is not None else None,
        json.dumps(recent_news_headlines) if recent_news_headlines is not None else None,
    )


def build_snapshot_upsert_sql() -> str:
    """Build SQL for legacy watchlist_snapshots upsert (core metrics only)."""
    return """
        INSERT INTO watchlist_snapshots (
            item_id, fetched_at, price, change_pct,
            overall_score, is_stale
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (item_id, fetched_at) DO UPDATE SET
            price = EXCLUDED.price,
            change_pct = EXCLUDED.change_pct,
            overall_score = EXCLUDED.overall_score,
            is_stale = EXCLUDED.is_stale
    """


def prepare_snapshot_parameters(
    item_id: str,
    fetched_at: datetime,
    price: float | None,
    change_pct: float | None,
    overall_score: float | None,
    is_stale: bool,
) -> list[object]:
    """Build parameter list for legacy snapshot upsert."""
    return [item_id, fetched_at, price, change_pct, overall_score, is_stale]


def upsert_core_snapshot(
    conn: object,
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
) -> int | None:
    """Insert/update watchlist_snapshots_core; return snapshot_id or None."""
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
    result = conn.execute(  # type: ignore[union-attr]
        core_sql,
        [
            item_id, fetched_at, price, change_pct,
            overall_score, technical_score, fundamental_score, news_score,
            ai_score, ai_confidence, is_stale, signal_type, signal_strength,
        ],
    )
    row = result.fetchone()
    if not row:
        return None
    return int(row[0])


def upsert_technical_metrics(
    conn: object,
    snapshot_id: int,
    *,
    raw_metrics: str | None,
    beta: float | None,
    volatility: float | None,
    volume_relative: float | None,
    timeframe_short_aligned: bool,
    timeframe_long_aligned: bool,
    percentile_rank_30d: float | None,
) -> None:
    """Insert/update watchlist_technical_metrics for a snapshot."""
    sql = """
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
    conn.execute(  # type: ignore[union-attr]
        sql,
        [snapshot_id, raw_metrics, beta, volatility,
         volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d],
    )


def upsert_narrative(
    conn: object,
    snapshot_id: int,
    *,
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
) -> None:
    """Insert/update watchlist_narrative for a snapshot."""
    sql = """
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
    conn.execute(  # type: ignore[union-attr]
        sql,
        [snapshot_id, narrative_headline, narrative_why_bullets,
         narrative_company_health, narrative_technical, narrative_action_plan,
         narrative_position_sizing, narrative_special_notes, entry_price,
         stop_loss, profit_target, position_size_shares, recommended_style,
         style_confidence, optimal_holding_period, risk_level, company_health],
    )


def upsert_news_summary(
    conn: object,
    snapshot_id: int,
    *,
    news_sentiment_score: float | None,
    recent_news_headlines: str | None,
    sector_score: float | None,
    competitor_score: float | None,
    earnings_date: datetime | None,
    earnings_days_away: int | None,
) -> None:
    """Insert/update watchlist_news_summary for a snapshot."""
    sql = """
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
    conn.execute(  # type: ignore[union-attr]
        sql,
        [snapshot_id, news_sentiment_score, recent_news_headlines,
         sector_score, competitor_score, earnings_date, earnings_days_away],
    )


def execute_normalized_snapshot_upsert(
    conn: object,
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
    raw_metrics: str | None,
    beta: float | None,
    volatility: float | None,
    volume_relative: float | None,
    timeframe_short_aligned: bool,
    timeframe_long_aligned: bool,
    percentile_rank_30d: float | None,
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
    news_sentiment_score: float | None,
    recent_news_headlines: str | None,
    sector_score: float | None,
    competitor_score: float | None,
    earnings_date: datetime | None,
    earnings_days_away: int | None,
) -> None:
    """Write to all 4 normalized snapshot tables (dual-write with legacy)."""
    snapshot_id = upsert_core_snapshot(
        conn,
        item_id=item_id, fetched_at=fetched_at,
        price=price, change_pct=change_pct, overall_score=overall_score,
        technical_score=technical_score, fundamental_score=fundamental_score,
        news_score=news_score, ai_score=ai_score, ai_confidence=ai_confidence,
        is_stale=is_stale, signal_type=signal_type, signal_strength=signal_strength,
    )
    if snapshot_id is None:
        return

    upsert_technical_metrics(
        conn, snapshot_id,
        raw_metrics=raw_metrics, beta=beta, volatility=volatility,
        volume_relative=volume_relative,
        timeframe_short_aligned=timeframe_short_aligned,
        timeframe_long_aligned=timeframe_long_aligned,
        percentile_rank_30d=percentile_rank_30d,
    )
    upsert_narrative(
        conn, snapshot_id,
        narrative_headline=narrative_headline,
        narrative_why_bullets=narrative_why_bullets,
        narrative_company_health=narrative_company_health,
        narrative_technical=narrative_technical,
        narrative_action_plan=narrative_action_plan,
        narrative_position_sizing=narrative_position_sizing,
        narrative_special_notes=narrative_special_notes,
        entry_price=entry_price, stop_loss=stop_loss,
        profit_target=profit_target, position_size_shares=position_size_shares,
        recommended_style=recommended_style, style_confidence=style_confidence,
        optimal_holding_period=optimal_holding_period,
        risk_level=risk_level, company_health=company_health,
    )
    upsert_news_summary(
        conn, snapshot_id,
        news_sentiment_score=news_sentiment_score,
        recent_news_headlines=recent_news_headlines,
        sector_score=sector_score, competitor_score=competitor_score,
        earnings_date=earnings_date, earnings_days_away=earnings_days_away,
    )
