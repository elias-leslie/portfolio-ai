-- Migration 047: Strategy definitions and performance tracking
-- Creates tables for dynamic strategy storage and live performance monitoring

-- Strategy definitions table (stores generated strategies with research context)
CREATE TABLE IF NOT EXISTS strategy_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,  -- e.g., "AAPL_Momentum_2024Q4"
    symbol VARCHAR(10) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,  -- momentum, value, event, reversal, defensive

    -- Strategy configuration (JSONB for flexibility)
    parameters JSONB NOT NULL,  -- Full StrategyParameters JSON

    -- Research context (what informed this strategy)
    research_summary JSONB NOT NULL,  -- ResearchInsights snapshot
    generation_reasoning TEXT,  -- Agent's explanation

    -- Performance metrics (from optimization)
    backtest_metrics JSONB NOT NULL,  -- Walk-forward results
    expected_sharpe NUMERIC(10, 4),
    expected_win_rate NUMERIC(5, 4),
    expected_max_drawdown NUMERIC(5, 4),

    -- Metadata
    created_by VARCHAR(255),  -- "workflow:{uuid}" or "manual"
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 1,  -- Increment on parameter changes

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'testing',  -- testing, active, archived
    activation_date TIMESTAMP WITH TIME ZONE,
    archive_date TIMESTAMP WITH TIME ZONE,
    archive_reason TEXT,

    -- Performance tracking (updated daily)
    live_trades_count INT DEFAULT 0,
    live_win_rate NUMERIC(5, 4),
    live_sharpe_ratio NUMERIC(10, 4),
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    UNIQUE(symbol, name, version)
);

-- Indexes for strategy_definitions
CREATE INDEX IF NOT EXISTS idx_strategy_status ON strategy_definitions(status, symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_type ON strategy_definitions(strategy_type, status);
CREATE INDEX IF NOT EXISTS idx_strategy_created ON strategy_definitions(created_at DESC);

-- Strategy performance tracking table (daily metrics)
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_definitions(id) ON DELETE CASCADE,
    date DATE NOT NULL,

    -- Daily metrics
    trades_today INT DEFAULT 0,
    wins_today INT DEFAULT 0,
    losses_today INT DEFAULT 0,
    pnl_today NUMERIC(15, 2) DEFAULT 0,

    -- Rolling metrics (30-day)
    trades_30d INT DEFAULT 0,
    win_rate_30d NUMERIC(5, 4),
    sharpe_ratio_30d NUMERIC(10, 4),
    max_drawdown_30d NUMERIC(5, 4),

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, underperforming
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(strategy_id, date)
);

-- Indexes for strategy_performance
CREATE INDEX IF NOT EXISTS idx_performance_date ON strategy_performance(date DESC);
CREATE INDEX IF NOT EXISTS idx_performance_status ON strategy_performance(status, date DESC);
CREATE INDEX IF NOT EXISTS idx_performance_strategy ON strategy_performance(strategy_id, date DESC);

-- Migration tracking handled by MigrationManager
