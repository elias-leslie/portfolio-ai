-- Migration: Add tech debt insight types
-- Purpose: Expand insight_type to support tech debt categorization
-- The insight_type is a TEXT column without constraints, so we just update documentation

-- Update the comment to document all valid insight types
COMMENT ON COLUMN capability_insights.insight_type IS
'Type of insight. Original types: data_quality, freshness, missing_data, missing_capability,
broken_dependency, performance. Tech debt types: dead_code, orphaned_infra, complexity,
dry_violation, test_coverage, dependency_issue, security_concern';

-- Note: No schema changes needed. The dashboard will group by insight_type for categorization.
-- Tech debt types are:
-- - dead_code: Unused code, unreferenced functions, orphaned files
-- - orphaned_infra: Uncalled Celery tasks, unused DB tables, dead API endpoints
-- - complexity: High cyclomatic complexity, deep nesting, long functions
-- - dry_violation: Duplicate code, copy-paste patterns
-- - test_coverage: Missing tests, low coverage areas
-- - dependency_issue: Outdated dependencies, security vulnerabilities
-- - security_concern: Potential security issues, hardcoded secrets, SQL injection risks
