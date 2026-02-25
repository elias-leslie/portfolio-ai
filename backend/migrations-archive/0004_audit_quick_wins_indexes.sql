-- Migration: 0004 Audit Quick Wins Indexes
-- Purpose: Add missing indexes for improved query performance
-- Date: 2025-11-03
-- Related: tasks/tasks-0024-prd-audit-quick-wins.md

-- ============================================================================
-- CREATE INDEXES
-- ============================================================================

-- Portfolio positions: Critical for portfolio queries (eliminates full table scan)
CREATE INDEX IF NOT EXISTS idx_portfolio_positions_account_id
ON portfolio_positions(account_id);

-- Agent ideas: High priority for agent analysis performance
CREATE INDEX IF NOT EXISTS idx_agent_ideas_agent_run_id
ON agent_ideas(agent_run_id);

-- Agent tool calls: High priority for agent analysis performance
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_agent_run_id
ON agent_tool_calls(agent_run_id);

-- Validation results: Medium priority for idea tracing performance
CREATE INDEX IF NOT EXISTS idx_validation_results_idea_id
ON validation_results(idea_id);

-- ============================================================================
-- ROLLBACK (for reference)
-- ============================================================================

-- DROP INDEX IF EXISTS idx_portfolio_positions_account_id;
-- DROP INDEX IF EXISTS idx_agent_ideas_agent_run_id;
-- DROP INDEX IF EXISTS idx_agent_tool_calls_agent_run_id;
-- DROP INDEX IF EXISTS idx_validation_results_idea_id;
