-- Migration 008: Add Narrative Intelligence columns to watchlist_snapshots and user_preferences
-- Created: 2025-11-01
-- Description: Adds signal classification, narrative text, trade calculations, and fundamental data columns

-- Add signal classification columns
ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS signal_type TEXT CHECK(signal_type IN ('BUY', 'HOLD', 'AVOID'));

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS signal_strength INTEGER CHECK(signal_strength BETWEEN 0 AND 10);

-- Add narrative text columns
ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_headline TEXT;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_why_bullets JSONB;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_company_health JSONB;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_technical JSONB;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_action_plan TEXT;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_position_sizing TEXT;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS narrative_special_notes TEXT;

-- Add trade calculation columns
ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS stop_loss DOUBLE PRECISION;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS profit_target DOUBLE PRECISION;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS position_size_shares INTEGER;

-- Add trading style columns
ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS recommended_style TEXT CHECK(recommended_style IN ('Index', 'Trend', 'Value', 'Swing', 'Event'));

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS style_confidence INTEGER CHECK(style_confidence BETWEEN 0 AND 10);

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS optimal_holding_period TEXT;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS risk_level TEXT CHECK(risk_level IN ('Low', 'Medium-Low', 'Medium', 'High'));

-- Add fundamental & news data columns
ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS company_health TEXT CHECK(company_health IN ('EXCELLENT', 'GOOD', 'WEAK'));

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS earnings_date DATE;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS earnings_days_away INTEGER;

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS news_sentiment_score DOUBLE PRECISION CHECK(news_sentiment_score BETWEEN -1.0 AND 1.0);

ALTER TABLE watchlist_snapshots
ADD COLUMN IF NOT EXISTS recent_news_headlines JSONB;

-- Add user preference columns for narrative features
ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_risk_budget INTEGER DEFAULT 500;

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_price_clamp INTEGER DEFAULT 20;

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_show_news BOOLEAN DEFAULT true;

ALTER TABLE user_preferences
ADD COLUMN IF NOT EXISTS watchlist_show_fundamentals BOOLEAN DEFAULT true;

-- Create performance indexes for new columns
CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_signal
  ON watchlist_snapshots(item_id, signal_type, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_earnings
  ON watchlist_snapshots(item_id, earnings_date)
  WHERE earnings_date IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_style
  ON watchlist_snapshots(item_id, recommended_style, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_watchlist_snapshots_company_health
  ON watchlist_snapshots(item_id, company_health, fetched_at DESC)
  WHERE company_health IS NOT NULL;

-- Record migration in schema_migrations table
INSERT INTO schema_migrations (version, description, applied_at, checksum)
VALUES (8, 'Add narrative intelligence columns', NOW(), 'manual')
ON CONFLICT (version) DO NOTHING;
