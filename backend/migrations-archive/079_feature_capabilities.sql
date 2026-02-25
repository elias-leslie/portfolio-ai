-- Migration 079: Feature Capabilities Table
-- Implements Anthropic's long-running agent patterns for feature tracking
-- Features tab in /capabilities - tracks user-facing functionality with corruption protection

-- Create feature_capabilities table
CREATE TABLE IF NOT EXISTS feature_capabilities (
    id SERIAL PRIMARY KEY,
    feature_id VARCHAR(20) UNIQUE NOT NULL,  -- FEAT-001 format
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),                    -- Dashboard, Watchlist, Trading, Portfolio, etc.
    description TEXT,

    -- Verification status (corruption-protected field)
    -- null = not yet reviewed
    -- false = reviewed and failing
    -- true = reviewed and verified working
    passes BOOLEAN DEFAULT NULL,

    -- Link to task file with granular details
    task_file VARCHAR(255),                   -- tasks/tasks-features-dashboard.md
    task_section VARCHAR(20),                 -- 1.0, 2.0, etc. - section within task file

    -- Health tracking (aligned with other capability tables)
    health_status VARCHAR(20) DEFAULT 'active',  -- active, suspect, orphaned, legacy

    -- Audit fields
    last_verified_at TIMESTAMPTZ,
    verified_by VARCHAR(50),                  -- 'manual', 'ai_scan', 'do_it'

    -- Standard timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_feature_id
    ON feature_capabilities(feature_id);

CREATE INDEX IF NOT EXISTS idx_feature_capabilities_category
    ON feature_capabilities(category);

CREATE INDEX IF NOT EXISTS idx_feature_capabilities_health_status
    ON feature_capabilities(health_status);

CREATE INDEX IF NOT EXISTS idx_feature_capabilities_passes
    ON feature_capabilities(passes);

CREATE INDEX IF NOT EXISTS idx_feature_capabilities_task_file
    ON feature_capabilities(task_file);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_feature_capabilities_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_feature_capabilities_updated_at ON feature_capabilities;
CREATE TRIGGER trigger_feature_capabilities_updated_at
    BEFORE UPDATE ON feature_capabilities
    FOR EACH ROW
    EXECUTE FUNCTION update_feature_capabilities_updated_at();

-- Add comment for documentation
COMMENT ON TABLE feature_capabilities IS 'Tracks user-facing features with verification status. Implements Anthropic long-running agent patterns. Agent permissions: task_it adds features, do_it updates passes field only.';

COMMENT ON COLUMN feature_capabilities.passes IS 'Verification status: null=not reviewed, false=failing, true=verified. Only modifiable by /do_it agent.';

COMMENT ON COLUMN feature_capabilities.task_file IS 'Path to markdown file with detailed task checklist. Multiple features can share one task file.';

COMMENT ON COLUMN feature_capabilities.task_section IS 'Section number within task_file (e.g., 1.0, 2.0). Maps to ## headers in markdown.';
