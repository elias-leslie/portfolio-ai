-- Migration: 072_backtest_benchmark_fields
-- Purpose: Add benchmark comparison fields to backtest_runs table
-- Section: 0.1 B&H Benchmark Integration (tasks-0096)

-- Add benchmark comparison columns to backtest_runs
ALTER TABLE backtest_runs
ADD COLUMN IF NOT EXISTS buy_hold_return DECIMAL(12,4),
ADD COLUMN IF NOT EXISTS excess_return DECIMAL(12,4),
ADD COLUMN IF NOT EXISTS beats_buy_hold BOOLEAN,
ADD COLUMN IF NOT EXISTS alpha DECIMAL(12,6),
ADD COLUMN IF NOT EXISTS information_ratio DECIMAL(12,4),
ADD COLUMN IF NOT EXISTS beta DECIMAL(8,4),
ADD COLUMN IF NOT EXISTS benchmark_symbol VARCHAR(20) DEFAULT 'SPY';

-- Add comment for documentation
COMMENT ON COLUMN backtest_runs.buy_hold_return IS 'Buy-and-hold return (%) for benchmark over same period';
COMMENT ON COLUMN backtest_runs.excess_return IS 'Strategy return minus buy-hold return (%)';
COMMENT ON COLUMN backtest_runs.beats_buy_hold IS 'Whether strategy outperformed buy-and-hold';
COMMENT ON COLUMN backtest_runs.alpha IS 'Jensen alpha (CAPM risk-adjusted excess return)';
COMMENT ON COLUMN backtest_runs.information_ratio IS 'Excess return per unit tracking error';
COMMENT ON COLUMN backtest_runs.beta IS 'Strategy beta vs benchmark';
COMMENT ON COLUMN backtest_runs.benchmark_symbol IS 'Benchmark symbol used (default SPY)';

-- Create index for filtering by benchmark performance
CREATE INDEX IF NOT EXISTS idx_backtest_runs_beats_buy_hold ON backtest_runs(beats_buy_hold);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_excess_return ON backtest_runs(excess_return);
