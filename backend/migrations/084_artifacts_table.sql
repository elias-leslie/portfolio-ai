-- Migration: 084_artifacts_table.sql
-- Description: Create artifacts table for UI verification evidence storage
-- Created: 2025-12-06

-- Artifacts table for storing UI verification evidence (screenshots, console logs, etc.)
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    artifact_id VARCHAR(50) UNIQUE NOT NULL,  -- e.g., "FEAT-001-ac-001-v3"
    feature_id VARCHAR(20) NOT NULL,           -- e.g., "FEAT-001"
    criterion_id VARCHAR(20),                  -- e.g., "ac-001" (nullable for feature-level artifacts)
    artifact_type VARCHAR(20) DEFAULT 'evidence',  -- 'evidence', 'screenshot', etc.

    -- File storage
    file_path VARCHAR(500) NOT NULL,           -- Relative path: "FEAT-001/ac-001/v1/"
    file_size_bytes INTEGER,                   -- Total size of all files in version dir

    -- Versioning
    version INTEGER DEFAULT 1,
    is_current BOOLEAN DEFAULT TRUE,

    -- Timestamps
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,                    -- When evidence becomes stale (default: +24h)

    -- AI Review
    quality_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'passed', 'failed', 'needs_review'
    quality_issues JSONB DEFAULT '[]'::jsonb,      -- List of detected issues
    confidence FLOAT,                              -- 0.0-1.0 confidence score
    ai_reviewed_at TIMESTAMPTZ,
    ai_reviewed_by VARCHAR(50),                    -- Model/agent that reviewed
    ai_evidence TEXT,                              -- AI's reasoning/notes

    -- User Review
    user_reviewed_at TIMESTAMPTZ,
    user_approved BOOLEAN,                         -- True=approved, False=rejected, NULL=pending
    user_notes TEXT,                               -- User feedback/notes

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_artifacts_feature_id ON artifacts(feature_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_criterion_id ON artifacts(criterion_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_feature_criterion ON artifacts(feature_id, criterion_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_expires_at ON artifacts(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_artifacts_quality_status ON artifacts(quality_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_is_current ON artifacts(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_artifacts_user_notes ON artifacts(id) WHERE user_notes IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_artifacts_needs_review ON artifacts(quality_status) WHERE quality_status = 'needs_review';

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_artifacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_artifacts_updated_at ON artifacts;
CREATE TRIGGER trigger_artifacts_updated_at
    BEFORE UPDATE ON artifacts
    FOR EACH ROW
    EXECUTE FUNCTION update_artifacts_updated_at();

-- Record migration
INSERT INTO schema_migrations (version, description, applied_at, checksum)
VALUES (84, 'Create artifacts table for UI verification evidence', NOW(), md5('084_artifacts_table'))
ON CONFLICT (version) DO NOTHING;
