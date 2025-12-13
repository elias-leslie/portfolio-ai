-- Migration: 111_agent_session_tracking
-- Description: Add session tracking columns to agent_runs for FEAT-223
-- Dependencies: agent_runs table must exist, agent_workflows table must exist

-- Add run_type to categorize the type of agent execution
-- Values: 'automated' (scheduled/triggered), 'user_chat' (user interaction), 'cross_validation'
ALTER TABLE agent_runs
ADD COLUMN IF NOT EXISTS run_type TEXT DEFAULT 'automated';

-- Add parent_run_id for linking related runs (e.g., validator to generator, follow-up to original)
ALTER TABLE agent_runs
ADD COLUMN IF NOT EXISTS parent_run_id TEXT REFERENCES agent_runs(id) ON DELETE SET NULL;

-- Add workflow_id to link runs to multi-agent workflows
ALTER TABLE agent_runs
ADD COLUMN IF NOT EXISTS workflow_id TEXT REFERENCES agent_workflows(id) ON DELETE SET NULL;

-- Add user_id for future multi-user support
ALTER TABLE agent_runs
ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_runs_run_type ON agent_runs(run_type);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent_run_id ON agent_runs(parent_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_workflow_id ON agent_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id ON agent_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at);

-- Validate run_type values with a CHECK constraint
ALTER TABLE agent_runs
ADD CONSTRAINT chk_agent_runs_run_type
CHECK (run_type IN ('automated', 'user_chat', 'cross_validation'));
