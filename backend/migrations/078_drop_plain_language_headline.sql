-- Migration 078: Drop plain_language_headline column from news_cache
-- This column was used for LLM-transformed headlines but:
-- 1. The feature caused task timeouts (150+ LLM calls per refresh)
-- 2. The frontend was already hardcoded to ignore it
-- 3. No agents or automation used it
-- Removed as part of tech debt cleanup.

-- Drop the column (safe since nothing uses it)
ALTER TABLE news_cache DROP COLUMN IF EXISTS plain_language_headline;

-- Migration tracking handled by MigrationManager
