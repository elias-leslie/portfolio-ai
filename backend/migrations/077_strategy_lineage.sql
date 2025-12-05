-- Migration 076: Strategy lineage tracking for evolution system
-- Tracks parent-child relationships between strategy versions when evolved via LLM

CREATE TABLE IF NOT EXISTS strategy_lineage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship
    child_strategy_id UUID NOT NULL REFERENCES strategy_definitions(id) ON DELETE CASCADE,
    parent_strategy_id UUID REFERENCES strategy_definitions(id) ON DELETE SET NULL,

    -- Evolution metadata
    changes_description TEXT NOT NULL,  -- LLM-generated explanation of what changed
    evolution_reason TEXT NOT NULL,     -- Why evolution was triggered (e.g., "underperforming", "market_regime_shift")

    -- Performance comparison
    metrics_before JSONB,  -- Parent strategy metrics: {sharpe, win_rate, drawdown}
    metrics_after JSONB,   -- Child strategy metrics after optimization

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(child_strategy_id)  -- Each child has exactly one lineage record
);

-- Indexes for strategy_lineage
CREATE INDEX IF NOT EXISTS idx_lineage_child ON strategy_lineage(child_strategy_id);
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON strategy_lineage(parent_strategy_id);
CREATE INDEX IF NOT EXISTS idx_lineage_created ON strategy_lineage(created_at DESC);

-- Migration tracking
INSERT INTO schema_migrations (version, description, applied_at, checksum)
VALUES (76, 'Create strategy_lineage table for evolution tracking', NOW(), 'manual')
ON CONFLICT (version) DO NOTHING;
