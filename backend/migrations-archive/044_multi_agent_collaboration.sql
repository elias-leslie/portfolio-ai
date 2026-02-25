-- Migration 044: Multi-Agent Collaboration Infrastructure
-- Description: Add agent_messages and agent_workflows tables for inter-agent
--              communication and workflow orchestration
-- Date: 2025-11-15
-- Dependencies: Task 0060 Task 3.7 (Multi-Agent Infrastructure)

-- ============================================================================
-- PART 1: Agent Messages Table (Inter-Agent Communication)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    from_agent_run_id TEXT,
    to_agent_type TEXT NOT NULL,
    message_type TEXT NOT NULL CHECK (message_type IN ('question', 'answer', 'data', 'consensus')),
    content JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'read', 'replied')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,

    -- Metadata
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    timeout_seconds INTEGER DEFAULT 300,

    CONSTRAINT agent_messages_read_at_check
        CHECK (status != 'read' OR read_at IS NOT NULL),
    CONSTRAINT agent_messages_replied_at_check
        CHECK (status != 'replied' OR replied_at IS NOT NULL)
);

-- Indexes for efficient message queries
CREATE INDEX IF NOT EXISTS idx_agent_messages_to_agent_type
ON agent_messages(to_agent_type, status);

CREATE INDEX IF NOT EXISTS idx_agent_messages_from_run_id
ON agent_messages(from_agent_run_id);

CREATE INDEX IF NOT EXISTS idx_agent_messages_status
ON agent_messages(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_messages_type
ON agent_messages(message_type);

COMMENT ON TABLE agent_messages IS 'Inter-agent communication: questions, answers, data sharing, consensus';
COMMENT ON COLUMN agent_messages.from_agent_run_id IS 'Source agent run (NULL for system messages)';
COMMENT ON COLUMN agent_messages.to_agent_type IS 'Target agent type (e.g., gemini, claude, strategy_analyzer)';
COMMENT ON COLUMN agent_messages.message_type IS 'Type of message: question, answer, data, consensus';
COMMENT ON COLUMN agent_messages.content IS 'Message payload (structure varies by message_type)';
COMMENT ON COLUMN agent_messages.status IS 'Message state: pending → read → replied';
COMMENT ON COLUMN agent_messages.priority IS '1 (urgent) to 10 (low priority), default 5';

-- ============================================================================
-- PART 2: Agent Workflows Table (Orchestration State)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_workflows (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    workflow_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'blocked', 'complete', 'failed')),
    current_step TEXT,
    agents_involved TEXT[] NOT NULL DEFAULT '{}',
    shared_context JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Configuration
    max_duration_seconds INTEGER DEFAULT 3600,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Metadata
    triggered_by TEXT,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),

    CONSTRAINT agent_workflows_started_at_check
        CHECK (status NOT IN ('running', 'blocked', 'complete', 'failed') OR started_at IS NOT NULL),
    CONSTRAINT agent_workflows_completed_at_check
        CHECK (status NOT IN ('complete', 'failed') OR completed_at IS NOT NULL),
    CONSTRAINT agent_workflows_result_check
        CHECK (status != 'complete' OR result IS NOT NULL),
    CONSTRAINT agent_workflows_error_check
        CHECK (status != 'failed' OR error IS NOT NULL)
);

-- Indexes for efficient workflow queries
CREATE INDEX IF NOT EXISTS idx_agent_workflows_type_status
ON agent_workflows(workflow_type, status);

CREATE INDEX IF NOT EXISTS idx_agent_workflows_status
ON agent_workflows(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_workflows_created_at
ON agent_workflows(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_workflows_triggered_by
ON agent_workflows(triggered_by);

-- GIN index for agents_involved array queries
CREATE INDEX IF NOT EXISTS idx_agent_workflows_agents_involved
ON agent_workflows USING GIN(agents_involved);

COMMENT ON TABLE agent_workflows IS 'Multi-agent workflow orchestration state tracking';
COMMENT ON COLUMN agent_workflows.workflow_type IS 'Workflow identifier (e.g., daily_gap_analysis, paper_trade_validation)';
COMMENT ON COLUMN agent_workflows.status IS 'Workflow state: pending → running → blocked/complete/failed';
COMMENT ON COLUMN agent_workflows.current_step IS 'Current execution step description';
COMMENT ON COLUMN agent_workflows.agents_involved IS 'Array of agent types participating';
COMMENT ON COLUMN agent_workflows.shared_context IS 'Shared data accessible to all agents in workflow';
COMMENT ON COLUMN agent_workflows.result IS 'Final workflow output (only set when complete)';
COMMENT ON COLUMN agent_workflows.max_duration_seconds IS 'Maximum workflow runtime (prevents infinite loops)';
COMMENT ON COLUMN agent_workflows.retry_count IS 'Number of retry attempts for failed workflows';

-- ============================================================================
-- PART 3: Update Table Registry
-- ============================================================================

INSERT INTO table_registry (table_name, table_type, description)
VALUES
    ('agent_messages', 'agents', 'Inter-agent communication messages'),
    ('agent_workflows', 'agents', 'Multi-agent workflow orchestration state')
ON CONFLICT (table_name) DO NOTHING;

-- ============================================================================
-- PART 4: Sample Workflow Types (for reference)
-- ============================================================================

-- Common workflow types:
-- - 'daily_gap_analysis': Gemini → Claude → Consensus → Report
-- - 'paper_trade_validation': Strategy agent → Risk agent → Consensus → Execution
-- - 'research_corroboration': Agent A researches → Agent B verifies → Consensus
-- - 'strategy_backtest': Backtest → Analysis → Paper trade decision

COMMENT ON TABLE agent_workflows IS 'Multi-agent workflow orchestration state tracking

Common workflow types:
- daily_gap_analysis: Gemini → Claude → Consensus → Report
- paper_trade_validation: Strategy agent → Risk agent → Consensus → Execution
- research_corroboration: Agent A researches → Agent B verifies → Consensus
- strategy_backtest: Backtest → Analysis → Paper trade decision';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    messages_table_exists BOOLEAN;
    workflows_table_exists BOOLEAN;
    messages_indexes_count INTEGER;
    workflows_indexes_count INTEGER;
BEGIN
    -- Check tables exist
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'agent_messages'
    ) INTO messages_table_exists;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'agent_workflows'
    ) INTO workflows_table_exists;

    -- Count indexes
    SELECT COUNT(*) INTO messages_indexes_count
    FROM pg_indexes
    WHERE tablename = 'agent_messages';

    SELECT COUNT(*) INTO workflows_indexes_count
    FROM pg_indexes
    WHERE tablename = 'agent_workflows';

    -- Report results
    RAISE NOTICE '=== Migration 044 Verification ===';
    RAISE NOTICE 'agent_messages table exists: %', messages_table_exists;
    RAISE NOTICE 'agent_workflows table exists: %', workflows_table_exists;
    RAISE NOTICE 'agent_messages indexes: %', messages_indexes_count;
    RAISE NOTICE 'agent_workflows indexes: %', workflows_indexes_count;

    IF messages_table_exists AND workflows_table_exists
       AND messages_indexes_count >= 4 AND workflows_indexes_count >= 5 THEN
        RAISE NOTICE '✓ Migration 044 completed successfully';
    ELSE
        RAISE WARNING '✗ Migration 044 incomplete - check errors above';
    END IF;
END $$;
