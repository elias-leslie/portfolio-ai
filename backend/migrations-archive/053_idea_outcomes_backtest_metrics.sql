-- Migration 053: Add backtest metrics columns to idea_outcomes
-- These columns store strategy backtest performance for paper trades

ALTER TABLE idea_outcomes
ADD COLUMN IF NOT EXISTS backtest_sharpe DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS backtest_win_rate DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS backtest_max_drawdown DECIMAL(10,4);

-- Add comments for documentation
COMMENT ON COLUMN idea_outcomes.backtest_sharpe IS 'Strategy expected Sharpe ratio from backtest';
COMMENT ON COLUMN idea_outcomes.backtest_win_rate IS 'Strategy expected win rate from backtest (0-100)';
COMMENT ON COLUMN idea_outcomes.backtest_max_drawdown IS 'Strategy expected max drawdown from backtest (0-100)';
