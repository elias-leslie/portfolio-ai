-- Migration 074: Backfill historical data from watchlist_snapshots to normalized tables
-- This completes migration 070 by migrating historical data that wasn't transferred
-- during the initial table split.

-- 1. Backfill watchlist_snapshots_core with historical data
INSERT INTO watchlist_snapshots_core (
    item_id, fetched_at, price, change_pct,
    overall_score, technical_score, fundamental_score, news_score,
    ai_score, ai_confidence, is_stale, signal_type, signal_strength
)
SELECT
    item_id, fetched_at, price, change_pct,
    overall_score, technical_score, fundamental_score, news_score,
    ai_score, ai_confidence, is_stale, signal_type, signal_strength
FROM watchlist_snapshots ws
WHERE NOT EXISTS (
    SELECT 1 FROM watchlist_snapshots_core wsc
    WHERE wsc.item_id = ws.item_id AND wsc.fetched_at = ws.fetched_at
);

-- 2. Backfill watchlist_technical_metrics for all core records that don't have metrics
INSERT INTO watchlist_technical_metrics (
    snapshot_id, raw_metrics, beta, volatility,
    volume_relative, timeframe_short_aligned, timeframe_long_aligned, percentile_rank_30d
)
SELECT
    wsc.id,
    ws.raw_metrics,
    ws.beta,
    ws.volatility,
    ws.volume_relative,
    ws.timeframe_short_aligned,
    ws.timeframe_long_aligned,
    ws.percentile_rank_30d
FROM watchlist_snapshots_core wsc
JOIN watchlist_snapshots ws ON ws.item_id = wsc.item_id AND ws.fetched_at = wsc.fetched_at
WHERE NOT EXISTS (
    SELECT 1 FROM watchlist_technical_metrics wtm WHERE wtm.snapshot_id = wsc.id
);

-- 3. Backfill watchlist_narrative for all core records that don't have narratives
INSERT INTO watchlist_narrative (
    snapshot_id,
    narrative_headline, narrative_why_bullets, narrative_company_health, narrative_technical,
    narrative_action_plan, narrative_position_sizing, narrative_special_notes,
    entry_price, stop_loss, profit_target, position_size_shares,
    recommended_style, style_confidence, optimal_holding_period, risk_level, company_health
)
SELECT
    wsc.id,
    ws.narrative_headline,
    ws.narrative_why_bullets,
    ws.narrative_company_health,
    ws.narrative_technical,
    ws.narrative_action_plan,
    ws.narrative_position_sizing,
    ws.narrative_special_notes,
    ws.entry_price,
    ws.stop_loss,
    ws.profit_target,
    ws.position_size_shares,
    ws.recommended_style,
    ws.style_confidence,
    ws.optimal_holding_period,
    ws.risk_level,
    ws.company_health
FROM watchlist_snapshots_core wsc
JOIN watchlist_snapshots ws ON ws.item_id = wsc.item_id AND ws.fetched_at = wsc.fetched_at
WHERE NOT EXISTS (
    SELECT 1 FROM watchlist_narrative wn WHERE wn.snapshot_id = wsc.id
);

-- 4. Backfill watchlist_news_summary for all core records that don't have news data
INSERT INTO watchlist_news_summary (
    snapshot_id,
    news_sentiment_score, recent_news_headlines,
    sector_score, competitor_score,
    earnings_date, earnings_days_away
)
SELECT
    wsc.id,
    ws.news_sentiment_score,
    ws.recent_news_headlines,
    ws.sector_score,
    ws.competitor_score,
    ws.earnings_date,
    ws.earnings_days_away
FROM watchlist_snapshots_core wsc
JOIN watchlist_snapshots ws ON ws.item_id = wsc.item_id AND ws.fetched_at = wsc.fetched_at
WHERE NOT EXISTS (
    SELECT 1 FROM watchlist_news_summary wns WHERE wns.snapshot_id = wsc.id
);

-- Log the migration results
DO $$
DECLARE
    core_count INT;
    tech_count INT;
    narr_count INT;
    news_count INT;
BEGIN
    SELECT COUNT(*) INTO core_count FROM watchlist_snapshots_core;
    SELECT COUNT(*) INTO tech_count FROM watchlist_technical_metrics;
    SELECT COUNT(*) INTO narr_count FROM watchlist_narrative;
    SELECT COUNT(*) INTO news_count FROM watchlist_news_summary;

    RAISE NOTICE 'Migration 074 complete: Core=%, Tech=%, Narrative=%, News=%',
        core_count, tech_count, narr_count, news_count;
END $$;
