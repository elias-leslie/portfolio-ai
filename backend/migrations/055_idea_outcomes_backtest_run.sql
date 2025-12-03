-- Migration 055: Link idea_outcomes (paper trades) to backtest_runs
-- Enables tracking which backtest validated the paper trade

-- 1. Add backtest_run_id column to idea_outcomes
ALTER TABLE idea_outcomes
ADD COLUMN IF NOT EXISTS backtest_run_id UUID;

-- 2. Add foreign key constraint (SET NULL on delete to preserve trade history)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_idea_outcomes_backtest_run'
    ) THEN
        ALTER TABLE idea_outcomes
        ADD CONSTRAINT fk_idea_outcomes_backtest_run
            FOREIGN KEY (backtest_run_id)
            REFERENCES backtest_runs(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- 3. Add index for efficient queries
CREATE INDEX IF NOT EXISTS idx_idea_outcomes_backtest_run_id
ON idea_outcomes(backtest_run_id);

-- 4. Add compound index for backtest validation queries
CREATE INDEX IF NOT EXISTS idx_idea_outcomes_strategy_backtest
ON idea_outcomes(strategy_id, backtest_run_id);

-- 5. Add live_metrics_updated_at column to strategy_definitions
ALTER TABLE strategy_definitions
ADD COLUMN IF NOT EXISTS live_metrics_updated_at TIMESTAMP WITH TIME ZONE;
