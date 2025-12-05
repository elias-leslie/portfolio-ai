-- Migration: Rules Validation Reports Table
-- Description: Stores automated rules validation results and optimization recommendations
-- Created: 2025-12-04 (Tier 3 Task 3.0)

-- Create table for validation reports
CREATE TABLE IF NOT EXISTS rules_validation_reports (
    id SERIAL PRIMARY KEY,

    -- Report metadata
    rules_version VARCHAR(50) NOT NULL,
    validation_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    overall_status VARCHAR(20) NOT NULL CHECK (overall_status IN ('valid', 'warnings', 'critical')),

    -- Summary counts
    critical_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    info_count INTEGER NOT NULL DEFAULT 0,

    -- Validation results (JSON array of ValidationError objects)
    validation_errors JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Optimization recommendations (JSON array of Recommendation objects)
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Summary text
    summary TEXT NOT NULL,

    -- Performance data used for optimization (if available)
    performance_data JSONB,

    CONSTRAINT validation_time_idx UNIQUE (validation_time)
);

-- Index for querying recent reports
CREATE INDEX idx_validation_reports_time ON rules_validation_reports(validation_time DESC);

-- Index for querying by status
CREATE INDEX idx_validation_reports_status ON rules_validation_reports(overall_status);

-- Index for querying critical reports
CREATE INDEX idx_validation_reports_critical ON rules_validation_reports(validation_time DESC)
    WHERE overall_status = 'critical';

-- Comments for documentation
COMMENT ON TABLE rules_validation_reports IS 'Automated trading rules validation results and optimization recommendations';
COMMENT ON COLUMN rules_validation_reports.rules_version IS 'Version from rules.yaml at time of validation';
COMMENT ON COLUMN rules_validation_reports.overall_status IS 'valid = no errors, warnings = non-critical issues, critical = blocking errors';
COMMENT ON COLUMN rules_validation_reports.validation_errors IS 'JSON array: [{severity, category, field_path, message, current_value, expected_range}]';
COMMENT ON COLUMN rules_validation_reports.recommendations IS 'JSON array: [{priority, category, field_path, recommendation, rationale, suggested_value}]';
COMMENT ON COLUMN rules_validation_reports.performance_data IS 'Recent trading performance metrics used for optimization analysis';
