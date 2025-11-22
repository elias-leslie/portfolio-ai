-- Migration 012: Strategy Evaluation Metrics
-- Purpose: Track strategy performance metrics over time for drift monitoring
-- Created: 2025-11-22

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

    -- LLM reviewer disagreement rate
    reviews_count INTEGER NOT NULL DEFAULT 0,
    disagreements_count INTEGER NOT NULL DEFAULT 0,
    disagreement_rate_pct DECIMAL(5,2),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Ensure one record per date per type
    UNIQUE(metric_date, metric_type)
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_date ON strategy_metrics(metric_date DESC);

-- Index for drift detection (high stdev)
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_drift ON strategy_metrics(score_stdev DESC);

-- Index for performance tracking
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_winrate ON strategy_metrics(win_rate_pct DESC);

-- Add to table registry
INSERT INTO table_registry (table_name, description)
VALUES (
    'strategy_metrics',
    'Daily/weekly/monthly strategy performance metrics for drift monitoring'
)
ON CONFLICT (table_name) DO NOTHING;
