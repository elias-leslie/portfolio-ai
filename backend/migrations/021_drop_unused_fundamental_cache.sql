-- Migration 021: Drop unused fundamental_cache table
-- Created: 2025-11-08
-- Description: Remove fundamental_cache table created in migration 020
--              System uses reference_cache with source='fundamentals' instead
--              This table was created by mistake and is not used by any code

-- Drop the unused table
DROP TABLE IF EXISTS fundamental_cache;

-- Note: Fundamental data is correctly stored in reference_cache with source='fundamentals'
-- No data migration needed as fundamental_cache was never populated
