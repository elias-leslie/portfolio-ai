-- Migration 108: Add seed tracking columns to strategy_definitions
-- Links strategies back to their originating AI-generated seed for evolution tracking

-- Add seed-related columns to strategy_definitions
ALTER TABLE strategy_definitions
ADD COLUMN IF NOT EXISTS seed_id UUID,
ADD COLUMN IF NOT EXISTS seed_thesis TEXT,
ADD COLUMN IF NOT EXISTS seed_confidence NUMERIC(3, 1);

-- Add comment explaining seed columns
COMMENT ON COLUMN strategy_definitions.seed_id IS 'UUID reference to the seed that triggered this strategy (if AI-generated)';
COMMENT ON COLUMN strategy_definitions.seed_thesis IS 'Original AI thesis preserved for evolution tracking';
COMMENT ON COLUMN strategy_definitions.seed_confidence IS 'Original confidence score (1-10) from seed generation';

-- Index for finding strategies by seed origin
CREATE INDEX IF NOT EXISTS idx_strategy_seed_id ON strategy_definitions(seed_id) WHERE seed_id IS NOT NULL;

-- Create strategy_seeds table to store seeds before they become strategies
CREATE TABLE IF NOT EXISTS strategy_seeds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(10) NOT NULL,
    thesis TEXT NOT NULL,
    confidence NUMERIC(3, 1) NOT NULL CHECK (confidence >= 1 AND confidence <= 10),
    agent_run_id UUID,

    -- Seed source context
    source_type VARCHAR(50) NOT NULL DEFAULT 'discovery',  -- discovery, market_scan, user_request
    source_data JSONB,  -- News/economic data that informed this seed

    -- Lifecycle tracking
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, processing, converted, rejected
    strategy_id UUID REFERENCES strategy_definitions(id),  -- Linked strategy once converted

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'converted', 'rejected'))
);

-- Indexes for strategy_seeds
CREATE INDEX IF NOT EXISTS idx_seed_symbol ON strategy_seeds(symbol);
CREATE INDEX IF NOT EXISTS idx_seed_status ON strategy_seeds(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_seed_confidence ON strategy_seeds(confidence DESC) WHERE status = 'pending';

-- Foreign key from strategy_definitions to strategy_seeds
ALTER TABLE strategy_definitions
ADD CONSTRAINT fk_strategy_seed
FOREIGN KEY (seed_id) REFERENCES strategy_seeds(id) ON DELETE SET NULL;
