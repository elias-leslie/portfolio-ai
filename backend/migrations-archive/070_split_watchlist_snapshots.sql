-- Migration 070: Split watchlist_snapshots into normalized tables
-- Reduces storage waste and enables granular updates
-- PHASE 1: Create new tables (parallel write to both old and new)

-- 1. Core snapshot table (essential fields only)
CREATE TABLE IF NOT EXISTS watchlist_snapshots_core (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id TEXT NOT NULL REFERENCES watchlist_items(id) ON DELETE CASCADE,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Core metrics
    price DOUBLE PRECISION,
    change_pct DOUBLE PRECISION,
    -- Scores
    overall_score DOUBLE PRECISION,
    technical_score DOUBLE PRECISION,
    fundamental_score DOUBLE PRECISION,
    news_score DOUBLE PRECISION,
    ai_score DOUBLE PRECISION,
    ai_confidence DOUBLE PRECISION,
    -- Status
    is_stale BOOLEAN DEFAULT FALSE,
    signal_type TEXT,
    signal_strength INTEGER,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint: one snapshot per item per timestamp
CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_core_item_fetched
    ON watchlist_snapshots_core(item_id, fetched_at);

-- Fast lookup by item, most recent first
CREATE INDEX IF NOT EXISTS idx_snapshots_core_item_desc
    ON watchlist_snapshots_core(item_id, fetched_at DESC);

-- 2. Technical metrics table (OHLCV-derived indicators)
CREATE TABLE IF NOT EXISTS watchlist_technical_metrics (
    snapshot_id UUID PRIMARY KEY REFERENCES watchlist_snapshots_core(id) ON DELETE CASCADE,
    -- Technical indicators as JSONB
    raw_metrics JSONB,
    -- Key risk metrics
    beta DOUBLE PRECISION,
    volatility DOUBLE PRECISION,
    -- Volume analysis
    volume_relative DOUBLE PRECISION,
    -- Timeframe alignment
    timeframe_short_aligned BOOLEAN DEFAULT FALSE,
    timeframe_long_aligned BOOLEAN DEFAULT FALSE,
    -- Percentile ranking
    percentile_rank_30d DOUBLE PRECISION
);

-- 3. Narrative intelligence table (AI-generated content)
CREATE TABLE IF NOT EXISTS watchlist_narrative (
    snapshot_id UUID PRIMARY KEY REFERENCES watchlist_snapshots_core(id) ON DELETE CASCADE,
    -- AI narrative fields
    narrative_headline TEXT,
    narrative_why_bullets JSONB,
    narrative_company_health JSONB,
    narrative_technical JSONB,
    narrative_action_plan TEXT,
    narrative_position_sizing TEXT,
    narrative_special_notes TEXT,
    -- Trade calculations
    entry_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    profit_target DOUBLE PRECISION,
    position_size_shares INTEGER,
    -- Trading style
    recommended_style TEXT,
    style_confidence INTEGER,
    optimal_holding_period TEXT,
    risk_level TEXT,
    company_health TEXT
);

-- 4. News summary table (news-derived data)
CREATE TABLE IF NOT EXISTS watchlist_news_summary (
    snapshot_id UUID PRIMARY KEY REFERENCES watchlist_snapshots_core(id) ON DELETE CASCADE,
    -- News metrics
    news_sentiment_score DOUBLE PRECISION,
    recent_news_headlines JSONB,
    -- Peer comparison
    sector_score DOUBLE PRECISION,
    competitor_score DOUBLE PRECISION,
    -- Earnings
    earnings_date TIMESTAMPTZ,
    earnings_days_away INTEGER
);

-- Create a view that joins all tables for backwards compatibility
CREATE OR REPLACE VIEW watchlist_snapshots_v AS
SELECT
    c.id,
    c.item_id,
    c.fetched_at,
    c.price,
    c.change_pct,
    c.overall_score,
    c.technical_score,
    c.fundamental_score,
    c.news_score,
    c.ai_score,
    c.ai_confidence,
    c.is_stale,
    c.signal_type,
    c.signal_strength,
    -- Technical
    t.raw_metrics,
    t.beta,
    t.volatility,
    t.volume_relative,
    t.timeframe_short_aligned,
    t.timeframe_long_aligned,
    t.percentile_rank_30d,
    -- Narrative
    n.narrative_headline,
    n.narrative_why_bullets,
    n.narrative_company_health,
    n.narrative_technical,
    n.narrative_action_plan,
    n.narrative_position_sizing,
    n.narrative_special_notes,
    n.entry_price,
    n.stop_loss,
    n.profit_target,
    n.position_size_shares,
    n.recommended_style,
    n.style_confidence,
    n.optimal_holding_period,
    n.risk_level,
    n.company_health,
    -- News
    ns.news_sentiment_score,
    ns.recent_news_headlines,
    ns.sector_score,
    ns.competitor_score,
    ns.earnings_date,
    ns.earnings_days_away
FROM watchlist_snapshots_core c
LEFT JOIN watchlist_technical_metrics t ON t.snapshot_id = c.id
LEFT JOIN watchlist_narrative n ON n.snapshot_id = c.id
LEFT JOIN watchlist_news_summary ns ON ns.snapshot_id = c.id;

-- Comment on migration
COMMENT ON TABLE watchlist_snapshots_core IS 'Normalized core snapshot data (phase 1 of split)';
COMMENT ON TABLE watchlist_technical_metrics IS 'Technical indicators linked to snapshots';
COMMENT ON TABLE watchlist_narrative IS 'AI-generated narratives linked to snapshots';
COMMENT ON TABLE watchlist_news_summary IS 'News and earnings data linked to snapshots';
COMMENT ON VIEW watchlist_snapshots_v IS 'Backwards-compatible view joining all snapshot tables';

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 070: Created 4 normalized snapshot tables and compatibility view';
END $$;
