-- Migration: Enhanced feature fields for task file replacement
-- Purpose: Add status, effort, source, and diagram to fully replace markdown task files

-- Feature status enum (work state, separate from verification passes)
-- pending: Not started
-- in_progress: Actively being worked on
-- review_needed: Implementation done, needs review
-- deferred: Intentionally postponed
-- blocked: Waiting on dependencies
-- complete: Done (use with passes=true for verified)
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';

-- Effort estimation (for sprint planning)
-- low: <2 hours, straightforward
-- medium: 2-8 hours, multiple components
-- high: 1-3 days, complex dependencies
-- very_high: 3+ days, architectural changes
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS effort TEXT;

-- Source/origin tracking
-- user_request: Direct user ask
-- bug_report: From bug/issue
-- audit: From /audit_it scan
-- tech_debt: Code quality finding
-- gap_analysis: From trading gap analysis
-- enhancement: Planned improvement
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS source TEXT;

-- Architecture/flow diagram (Mermaid or ASCII)
-- Recommended for features touching 3+ components
-- Helps understand data flow and dependencies
ALTER TABLE feature_capabilities
ADD COLUMN IF NOT EXISTS diagram TEXT;

-- Add comments
COMMENT ON COLUMN feature_capabilities.status IS
'Work status: pending, in_progress, review_needed, deferred, blocked, complete';

COMMENT ON COLUMN feature_capabilities.effort IS
'Effort estimate: low (<2h), medium (2-8h), high (1-3d), very_high (3d+)';

COMMENT ON COLUMN feature_capabilities.source IS
'Origin: user_request, bug_report, audit, tech_debt, gap_analysis, enhancement';

COMMENT ON COLUMN feature_capabilities.diagram IS
'Mermaid or ASCII diagram showing architecture/flow. Recommended for multi-component features.';

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_status
ON feature_capabilities(status);

-- Index for filtering by effort
CREATE INDEX IF NOT EXISTS idx_feature_capabilities_effort
ON feature_capabilities(effort);
