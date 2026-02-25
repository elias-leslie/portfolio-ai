-- Migration: Backtesting Framework - Phase A MVP Tables
-- Description: Create tables for storing backtest runs, trades, and equity curves
-- Created: 2025-11-14
-- Dependencies: None (standalone feature)

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Table: backtest_runs
-- Purpose: Store backtest execution metadata and final performance metrics
-- ============================================================================

CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_name VARCHAR(100) NOT NULL,  -- e.g., "signal_classifier"
    symbol VARCHAR(20) NOT NULL,          -- Single symbol for Phase A MVP
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    final_equity DECIMAL(15,2),           -- Null until backtest completes
    total_return_pct DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    max_drawdown_pct DECIMAL(10,4),
    win_rate DECIMAL(10,4),
    num_trades INTEGER,
    profit_factor DECIMAL(10,4),          -- Sum(wins) / Sum(losses)
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT backtest_runs_status_check CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT backtest_runs_dates_check CHECK (end_date >= start_date),
    CONSTRAINT backtest_runs_capital_check CHECK (initial_capital > 0)
);

-- Indexes for query performance
CREATE INDEX idx_backtest_runs_status ON backtest_runs(status);
CREATE INDEX idx_backtest_runs_created_at ON backtest_runs(created_at DESC);
CREATE INDEX idx_backtest_runs_symbol ON backtest_runs(symbol);
CREATE INDEX idx_backtest_runs_strategy ON backtest_runs(strategy_name);

-- ============================================================================
-- Table: backtest_trades
-- Purpose: Store individual trade entry/exit details
-- Pattern: Reuses idea_outcomes schema patterns (excursions, exit_reason)
-- ============================================================================

CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    entry_date DATE NOT NULL,
    entry_price DECIMAL(15,4) NOT NULL,
    exit_date DATE,                       -- Null if position still open at end
    exit_price DECIMAL(15,4),
    shares INTEGER NOT NULL,
    pnl DECIMAL(15,2),                    -- Profit/loss in dollars
    pnl_pct DECIMAL(10,4),                -- Profit/loss percentage
    exit_reason VARCHAR(20),              -- target/stop/signal/time/eod
    max_favorable_pct DECIMAL(10,4) DEFAULT 0.0,
    max_adverse_pct DECIMAL(10,4) DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT backtest_trades_exit_reason_check CHECK (exit_reason IN ('target', 'stop', 'signal', 'time', 'eod') OR exit_reason IS NULL),
    CONSTRAINT backtest_trades_shares_check CHECK (shares > 0),
    CONSTRAINT backtest_trades_prices_check CHECK (entry_price > 0 AND (exit_price > 0 OR exit_price IS NULL))
);

-- Indexes for query performance
CREATE INDEX idx_backtest_trades_run_id ON backtest_trades(run_id);
CREATE INDEX idx_backtest_trades_entry_date ON backtest_trades(entry_date);
CREATE INDEX idx_backtest_trades_symbol ON backtest_trades(symbol);

-- ============================================================================
-- Table: backtest_equity
-- Purpose: Daily equity curve snapshots for drawdown calculation and charts
-- ============================================================================

CREATE TABLE IF NOT EXISTS backtest_equity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    equity DECIMAL(15,2) NOT NULL,        -- Total portfolio value (cash + positions)
    cash DECIMAL(15,2) NOT NULL,
    position_value DECIMAL(15,2) NOT NULL,
    drawdown_pct DECIMAL(10,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT backtest_equity_run_date_unique UNIQUE (run_id, date),
    CONSTRAINT backtest_equity_values_check CHECK (equity >= 0 AND cash >= 0 AND position_value >= 0)
);

-- Indexes for query performance
CREATE INDEX idx_backtest_equity_run_id ON backtest_equity(run_id);
CREATE INDEX idx_backtest_equity_date ON backtest_equity(date);

-- ============================================================================
-- Comments (documentation for capabilities scanner)
-- ============================================================================

COMMENT ON TABLE backtest_runs IS 'Backtest execution metadata and final performance metrics. Single-symbol backtests for Phase A MVP.';
COMMENT ON TABLE backtest_trades IS 'Individual trade entry/exit details within backtest runs. Tracks excursions and exit reasons.';
COMMENT ON TABLE backtest_equity IS 'Daily equity curve snapshots for drawdown calculation and visualization.';

COMMENT ON COLUMN backtest_runs.strategy_name IS 'Strategy used (e.g., signal_classifier). Extensible for custom strategies in Phase B.';
COMMENT ON COLUMN backtest_runs.profit_factor IS 'Sum of winning trades divided by sum of losing trades. >1.0 indicates profitable strategy.';
COMMENT ON COLUMN backtest_trades.exit_reason IS 'Why trade was closed: target (profit target), stop (stop loss), signal (exit signal), time (max holding period), eod (end of backtest).';
COMMENT ON COLUMN backtest_trades.max_favorable_pct IS 'Best return percentage achieved during trade (for MAE/MFE analysis).';
COMMENT ON COLUMN backtest_trades.max_adverse_pct IS 'Worst return percentage during trade (for drawdown analysis).';
COMMENT ON COLUMN backtest_equity.drawdown_pct IS 'Current drawdown from peak equity. Calculated as (peak - current) / peak * 100.';

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verification queries (run manually to check)
-- SELECT COUNT(*) FROM backtest_runs;
-- SELECT COUNT(*) FROM backtest_trades;
-- SELECT COUNT(*) FROM backtest_equity;
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'backtest%';
