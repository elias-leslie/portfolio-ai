-- Migration 037: Capability Insights Table (AI Analysis)
-- Purpose: Store AI-generated insights about data quality, gaps, and issues
-- Part of: System Capabilities Registry (Task 0059, Phase 2)
-- Created: 2025-11-13
-- Related: tasks/tasks-0059-system-capabilities-registry.md

CREATE TABLE IF NOT EXISTS capability_insights (
    id SERIAL PRIMARY KEY,
    capability_type TEXT NOT NULL,  -- 'db', 'celery', 'api', 'missing'
    capability_id INTEGER,  -- FK to respective table, NULL if capability doesn't exist
    table_name TEXT,  -- For quick reference (denormalized)
    insight_type TEXT NOT NULL,  -- data_quality, freshness, missing_data, missing_capability, broken_dependency, performance
    severity TEXT NOT NULL,  -- critical, high, medium, low
    finding TEXT NOT NULL,  -- What's wrong (concise, 1-2 sentences)
    expected_behavior TEXT,  -- What should happen
    actual_behavior TEXT,  -- What's actually happening
    impact TEXT,  -- Why this matters for trading/business
    suggested_fix TEXT,  -- Specific action with file/line references
    reference_data JSONB,  -- {files: [...], tables: [...], tasks: [...], urls: [...]}
    ai_model TEXT,  -- Which AI generated this: "claude-sonnet-4.5", "gemini-2.0"
    ai_confidence DECIMAL(3,2),  -- 0.00-1.00
    status TEXT DEFAULT 'pending',  -- pending, confirmed, dismissed, in_progress, fixed
    status_reason TEXT,  -- Why confirmed/dismissed (from human review)
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by TEXT,
    fixed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_insights_capability ON capability_insights(capability_type, capability_id);
CREATE INDEX IF NOT EXISTS idx_insights_status ON capability_insights(status);
CREATE INDEX IF NOT EXISTS idx_insights_severity ON capability_insights(severity);
CREATE INDEX IF NOT EXISTS idx_insights_type ON capability_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_generated_at ON capability_insights(generated_at DESC);

-- Comments for documentation
COMMENT ON TABLE capability_insights IS 'AI-generated insights about system capabilities, data quality, and gaps';
COMMENT ON COLUMN capability_insights.capability_type IS 'Type of capability: db, celery, api, missing (if capability does not exist)';
COMMENT ON COLUMN capability_insights.capability_id IS 'Foreign key to respective capability table (db_capabilities, celery_capabilities, api_capabilities)';
COMMENT ON COLUMN capability_insights.table_name IS 'Denormalized table/task/endpoint name for quick reference';
COMMENT ON COLUMN capability_insights.insight_type IS 'Type of insight: data_quality, freshness, missing_data, missing_capability, broken_dependency, performance';
COMMENT ON COLUMN capability_insights.severity IS 'Severity level: critical, high, medium, low';
COMMENT ON COLUMN capability_insights.finding IS 'Brief description of the issue (1-2 sentences)';
COMMENT ON COLUMN capability_insights.expected_behavior IS 'What should be happening';
COMMENT ON COLUMN capability_insights.actual_behavior IS 'What is actually happening';
COMMENT ON COLUMN capability_insights.impact IS 'Business/trading impact of this issue';
COMMENT ON COLUMN capability_insights.suggested_fix IS 'Specific fix recommendation with file paths and line numbers';
COMMENT ON COLUMN capability_insights.reference_data IS 'JSON object with arrays: files, tables, tasks, urls (for context)';
COMMENT ON COLUMN capability_insights.ai_model IS 'AI model that generated this insight (e.g., claude-sonnet-4.5)';
COMMENT ON COLUMN capability_insights.ai_confidence IS 'Confidence score from AI (0.00-1.00)';
COMMENT ON COLUMN capability_insights.status IS 'Review status: pending, confirmed, dismissed, in_progress, fixed';
COMMENT ON COLUMN capability_insights.status_reason IS 'Human explanation for confirmation/dismissal';
COMMENT ON COLUMN capability_insights.generated_at IS 'When AI generated this insight';
COMMENT ON COLUMN capability_insights.reviewed_at IS 'When human reviewed this insight';
COMMENT ON COLUMN capability_insights.reviewed_by IS 'Who reviewed this insight';
COMMENT ON COLUMN capability_insights.fixed_at IS 'When the issue was marked as fixed';
