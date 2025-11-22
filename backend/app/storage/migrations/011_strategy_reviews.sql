-- Migration 011: Strategy Review Logs
-- Purpose: Store LLM strategy review insights for watchlist signals
-- Created: 2025-11-22

CREATE TABLE IF NOT EXISTS strategy_reviews (
    id TEXT PRIMARY KEY,
    watchlist_item_id TEXT NOT NULL REFERENCES watchlist_items(id) ON DELETE CASCADE,
    snapshot_id TEXT,  -- Optional reference to specific snapshot reviewed
    symbol TEXT NOT NULL,
    review_text TEXT NOT NULL,
    provider TEXT NOT NULL,  -- 'gemini' or 'claude'
    is_valid BOOLEAN NOT NULL,  -- Passed guardrails validation
    disagreement BOOLEAN NOT NULL,  -- LLM flagged concerns not in rules rationale
    token_usage JSONB,  -- {prompt_tokens, completion_tokens, total_tokens}
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for querying reviews by item
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_item ON strategy_reviews(watchlist_item_id);

-- Index for finding disagreements
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_disagreement ON strategy_reviews(disagreement) WHERE disagreement = true;

-- Index for provider usage tracking
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_provider ON strategy_reviews(provider);

-- Add to table registry
INSERT INTO table_registry (table_name, description)
VALUES (
    'strategy_reviews',
    'LLM strategy review insights and disagreements'
)
ON CONFLICT (table_name) DO NOTHING;
