-- Migration: Cross-validation results table
-- Created: 2025-12-12
-- Feature: FEAT-219 Multi-Agent Cross-Validation

CREATE TABLE IF NOT EXISTS cross_validation_results (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Generator (Gemini)
    generator_provider TEXT NOT NULL DEFAULT 'gemini',
    generator_model TEXT,
    generator_output TEXT NOT NULL,
    generator_confidence DOUBLE PRECISION,

    -- Validator (Claude)
    validator_provider TEXT NOT NULL DEFAULT 'claude',
    validator_model TEXT,
    validator_review TEXT,
    validator_approved BOOLEAN DEFAULT FALSE,
    validator_confidence DOUBLE PRECISION,

    -- Disagreement tracking
    has_disagreement BOOLEAN DEFAULT FALSE,
    disagreement_reasons JSONB DEFAULT '[]',
    disagreement_details TEXT,

    -- Resolution
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,  -- 'human' or 'auto'
    final_output TEXT,

    -- Context
    context_type TEXT NOT NULL DEFAULT 'insight',
    context_symbol TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_xval_status ON cross_validation_results(status);
CREATE INDEX IF NOT EXISTS idx_xval_created_at ON cross_validation_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_xval_symbol ON cross_validation_results(context_symbol) WHERE context_symbol IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_xval_disagreement ON cross_validation_results(has_disagreement) WHERE has_disagreement = TRUE;

-- Comments
COMMENT ON TABLE cross_validation_results IS 'Stores results of multi-agent cross-validation (Gemini generates, Claude validates)';
COMMENT ON COLUMN cross_validation_results.status IS 'pending, approved, rejected, auto_applied, modified';
COMMENT ON COLUMN cross_validation_results.disagreement_reasons IS 'Array of: factual, logical, risk_assessment, confidence, other';
