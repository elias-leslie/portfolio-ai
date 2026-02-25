-- Migration: 112_agent_conversation_messages
-- Description: Create table for storing full conversation history for FEAT-223
-- Dependencies: agent_runs table must exist

-- Create the conversation messages table
CREATE TABLE IF NOT EXISTS agent_conversation_messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    agent_run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence_num INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,

    -- Ensure unique ordering within a run
    CONSTRAINT uq_agent_conversation_messages_run_seq UNIQUE (agent_run_id, sequence_num),

    -- Validate role values
    CONSTRAINT chk_agent_conversation_messages_role
    CHECK (role IN ('user', 'assistant', 'system', 'tool_call', 'tool_result'))
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_conversation_messages_run_id
ON agent_conversation_messages(agent_run_id);

CREATE INDEX IF NOT EXISTS idx_agent_conversation_messages_created_at
ON agent_conversation_messages(created_at);

-- Composite index for fetching messages in order
CREATE INDEX IF NOT EXISTS idx_agent_conversation_messages_run_seq
ON agent_conversation_messages(agent_run_id, sequence_num);
