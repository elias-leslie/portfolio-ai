-- Migration 056: Strategy Reviews with Dual-LLM Support
-- Purpose: Create strategy_reviews table with dual-provider review columns
-- Created: 2025-12-03

-- Create strategy_reviews table if not exists (migrating from app/storage/migrations)
CREATE TABLE IF NOT EXISTS strategy_reviews (
    id TEXT PRIMARY KEY,
    watchlist_item_id TEXT NOT NULL,
    snapshot_id TEXT,  -- Optional reference to specific snapshot reviewed
    symbol TEXT NOT NULL,
    review_text TEXT NOT NULL,
    provider TEXT NOT NULL,  -- 'gemini' or 'claude'
    is_valid BOOLEAN NOT NULL,  -- Passed guardrails validation
    disagreement BOOLEAN NOT NULL,  -- LLM flagged concerns not in rules rationale
    token_usage JSONB,  -- {prompt_tokens, completion_tokens, total_tokens}
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- New columns for dual-review support
    review_pair_id TEXT,  -- Links dual reviews (both Gemini and Claude reviewing same signal)
    disagreement_severity TEXT CHECK (disagreement_severity IN ('none', 'minor', 'major')),
    provider_disagreement BOOLEAN DEFAULT FALSE,  -- Tracks when providers disagree with each other
    agreement_score REAL  -- Consensus confidence (0.0 to 1.0)
);

-- Index for querying reviews by item
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_item ON strategy_reviews(watchlist_item_id);

-- Index for finding disagreements (LLM vs rules)
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_disagreement ON strategy_reviews(disagreement) WHERE disagreement = true;

-- Index for provider usage tracking
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_provider ON strategy_reviews(provider);

-- Index for finding review pairs
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_pair ON strategy_reviews(review_pair_id) WHERE review_pair_id IS NOT NULL;

-- Index for finding provider disagreements
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_provider_disagreement ON strategy_reviews(provider_disagreement) WHERE provider_disagreement = true;

-- Index for disagreement severity queries
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_severity ON strategy_reviews(disagreement_severity) WHERE disagreement_severity IN ('minor', 'major');

-- Add to table registry if exists
INSERT INTO table_registry (table_name, description)
VALUES (
    'strategy_reviews',
    'LLM strategy review insights with dual-provider consensus tracking'
)
ON CONFLICT (table_name) DO UPDATE SET description = EXCLUDED.description;
