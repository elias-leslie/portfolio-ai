-- Migration 101: Add FK constraint for agent_messages
-- Date: 2025-12-09

ALTER TABLE agent_messages
ADD CONSTRAINT fk_agent_messages_from_run
FOREIGN KEY (from_agent_run_id) REFERENCES agent_runs(id)
ON DELETE SET NULL
DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS idx_agent_messages_from_run ON agent_messages(from_agent_run_id);
