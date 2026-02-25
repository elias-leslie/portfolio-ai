-- Migration 046: Extend agent_runs table with CLI provider telemetry
-- Captures provider/model/status for CLI-based agent execution
--
-- New fields:
--   provider: CLI provider used (gemini, claude, anthropic_api)
--   model: Specific model name/version
--   cli_command: Full CLI command executed (for debugging)
--   exit_code: Process exit code (0 = success, non-zero = error)
--   duration_ms: Execution duration in milliseconds
--   token_usage: Token counts from provider (JSONB: {input, output, total})
--   session_id: CLI session ID for resume/continue support

-- Step 1: Add new columns to agent_runs table
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS cli_command TEXT;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS exit_code INTEGER;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS duration_ms INTEGER;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS token_usage JSONB;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS session_id TEXT;

-- Step 2: Add comments for documentation
COMMENT ON COLUMN agent_runs.provider IS 'CLI provider: gemini, claude, or anthropic_api';
COMMENT ON COLUMN agent_runs.model IS 'Specific model name (e.g., gemini-2.5-pro, claude-sonnet-4-5-20250929)';
COMMENT ON COLUMN agent_runs.cli_command IS 'Full CLI command executed (sanitized, for debugging)';
COMMENT ON COLUMN agent_runs.exit_code IS 'Process exit code: 0 = success, non-zero = error';
COMMENT ON COLUMN agent_runs.duration_ms IS 'Execution duration in milliseconds';
COMMENT ON COLUMN agent_runs.token_usage IS 'Token counts: {input_tokens, output_tokens, total_tokens}';
COMMENT ON COLUMN agent_runs.session_id IS 'CLI session ID for resume/continue support';

-- Step 3: Create index on provider for filtering
CREATE INDEX IF NOT EXISTS idx_agent_runs_provider ON agent_runs(provider);

-- Step 4: Create index on model for analytics
CREATE INDEX IF NOT EXISTS idx_agent_runs_model ON agent_runs(model);

-- Step 5: Update table registry for monitoring
INSERT INTO table_registry (table_name, table_type, description)
VALUES (
    'agent_runs',
    'analytics',
    'Agent execution runs with provider/model telemetry'
)
ON CONFLICT (table_name) DO UPDATE SET
    description = EXCLUDED.description;
