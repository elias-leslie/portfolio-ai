-- Migration 057: Strategy Metrics with Provider Disagreement Tracking
-- Purpose: Track strategy performance metrics with multi-LLM consensus data
-- Created: 2025-12-03

-- Create strategy_metrics table if not exists (migrated from app/storage/migrations)
CREATE TABLE IF NOT EXISTS strategy_metrics (
    id TEXT PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_type TEXT NOT NULL,  -- 'daily', 'weekly', 'monthly'

    -- Signal accuracy metrics
    total_signals INTEGER NOT NULL DEFAULT 0,
    buy_signals INTEGER NOT NULL DEFAULT 0,
    hold_signals INTEGER NOT NULL DEFAULT 0,
    avoid_signals INTEGER NOT NULL DEFAULT 0,

    -- Win rate tracking (for signals that became trades)
    signals_traded INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    win_rate_pct DECIMAL(5,2),

    -- Return metrics
    avg_return_pct DECIMAL(8,4),
    best_return_pct DECIMAL(8,4),
    worst_return_pct DECIMAL(8,4),
    cumulative_return_pct DECIMAL(10,4),

    -- Score distribution (for drift detection)
    avg_overall_score DECIMAL(5,2),
    avg_technical_score DECIMAL(5,2),
    avg_fundamental_score DECIMAL(5,2),
    score_stdev DECIMAL(5,2),  -- Standard deviation indicates drift

    -- LLM reviewer disagreement rate (rules vs LLM)
    reviews_count INTEGER NOT NULL DEFAULT 0,
    disagreements_count INTEGER NOT NULL DEFAULT 0,
    disagreement_rate_pct DECIMAL(5,2),

    -- Multi-LLM provider disagreement tracking (Gemini vs Claude)
    provider_disagreements_count INTEGER DEFAULT 0,
    provider_disagreement_rate_pct DECIMAL(5,2),
    avg_agreement_score DECIMAL(5,4),
    major_disagreements_count INTEGER DEFAULT 0,
    minor_disagreements_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Ensure one record per date per type
    UNIQUE(metric_date, metric_type)
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_date ON strategy_metrics(metric_date DESC);

-- Index for drift detection (high stdev)
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_drift ON strategy_metrics(score_stdev DESC);

-- Index for performance tracking
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_winrate ON strategy_metrics(win_rate_pct DESC);

-- Index for provider disagreement monitoring
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_provider_disagreement
    ON strategy_metrics(provider_disagreement_rate_pct DESC)
    WHERE provider_disagreement_rate_pct > 20;

-- Add to table registry
INSERT INTO table_registry (table_name, description)
VALUES (
    'strategy_metrics',
    'Daily/weekly/monthly strategy performance metrics with multi-LLM consensus tracking'
)
ON CONFLICT (table_name) DO UPDATE SET description = EXCLUDED.description;
