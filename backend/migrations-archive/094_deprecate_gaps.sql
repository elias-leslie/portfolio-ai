-- Migration: 094_deprecate_gaps.sql
-- Purpose: Deprecate the gap abstraction layer
--
-- Gaps were useful for initial requirements gathering but are now redundant.
-- FEAT-166 to FEAT-214 features already exist and track the same information.
-- This migration:
--   1. Deletes duplicate features (keep FEAT-166 to FEAT-214 versions with more data)
--   2. Drops gap-related views
--   3. Drops the feature_gap_mappings junction table
--   4. Drops the trading_gaps table
--
-- Date: 2025-12-09
-- Status: APPLIED

-- Step 1: Delete duplicate features (FEAT-* versions with less data)
-- Keep FEAT-168 "Earnings Surprises" (5 tasks, 3 criteria)
-- Delete FEAT-159 "Earnings Surprises" (1 task, 2 criteria)
DELETE FROM feature_tasks WHERE feature_id IN (
    SELECT id FROM feature_capabilities WHERE feature_id = 'FEAT-159'
);
DELETE FROM feature_capabilities WHERE feature_id = 'FEAT-159';

-- Keep FEAT-169 "Cash Flow Metrics" (5 tasks, 4 criteria, passes=true)
-- Delete FEAT-156 "Cash Flow Metrics" (2 tasks, 2 criteria, passes=false)
DELETE FROM feature_tasks WHERE feature_id IN (
    SELECT id FROM feature_capabilities WHERE feature_id = 'FEAT-156'
);
DELETE FROM feature_capabilities WHERE feature_id = 'FEAT-156';

-- Step 2: Drop views that depend on gap tables
DROP VIEW IF EXISTS feature_gap_summary CASCADE;
DROP VIEW IF EXISTS gap_resolution_summary CASCADE;

-- Step 3: Drop feature_gap_mappings junction table
DROP TABLE IF EXISTS feature_gap_mappings CASCADE;

-- Step 4: Drop trading_gaps table
DROP TABLE IF EXISTS trading_gaps CASCADE;

-- Verification queries (run manually to confirm):
-- SELECT COUNT(*) FROM feature_capabilities WHERE feature_id LIKE 'FEAT-GAP-%';
-- Expected: 49 (all gap features preserved)
--
-- SELECT * FROM feature_capabilities WHERE name IN ('Earnings Surprises', 'Cash Flow Metrics');
-- Expected: 2 rows (only FEAT-168 and FEAT-169)
