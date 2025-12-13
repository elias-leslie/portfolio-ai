-- Migration: 113_agent_run_fks
-- Description: Add agent_run_id FKs to strategy_reviews and cross_validation_results for FEAT-223 DRY fix
-- Dependencies: agent_runs table with new columns must exist

-- Add agent_run_id to strategy_reviews
-- This allows linking reviews to the agent run that created them, eliminating duplicate token_usage/provider columns
ALTER TABLE strategy_reviews
ADD COLUMN IF NOT EXISTS agent_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_strategy_reviews_agent_run_id ON strategy_reviews(agent_run_id);

-- Add generator_run_id and validator_run_id to cross_validation_results
-- This links each validation to the specific generator and validator runs, eliminating duplicate provider/model columns
ALTER TABLE cross_validation_results
ADD COLUMN IF NOT EXISTS generator_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL;

ALTER TABLE cross_validation_results
ADD COLUMN IF NOT EXISTS validator_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_cross_validation_results_generator_run_id ON cross_validation_results(generator_run_id);
CREATE INDEX IF NOT EXISTS idx_cross_validation_results_validator_run_id ON cross_validation_results(validator_run_id);
