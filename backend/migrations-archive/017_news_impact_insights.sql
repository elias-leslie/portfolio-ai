-- Migration 017: Add impact_summary and actionable_insight fields to news_cache
-- Plain language translations for everyday investors
-- Created: 2025-11-06

-- Add impact summary field
-- Explains "what this means" for traders (plain language)
ALTER TABLE news_cache
  ADD COLUMN IF NOT EXISTS impact_summary TEXT;

-- Add actionable insight field
-- Answers "what should I do?" with context-aware recommendations
ALTER TABLE news_cache
  ADD COLUMN IF NOT EXISTS actionable_insight TEXT;

COMMENT ON COLUMN news_cache.impact_summary IS
  'Plain language explanation of what the news means (e.g., "Strong results may drive stock higher short-term")';

COMMENT ON COLUMN news_cache.actionable_insight IS
  'Context-aware recommendation for what to do (e.g., "Good news - consider adding to position if you own it")';
