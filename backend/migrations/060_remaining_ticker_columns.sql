-- Migration 060: Rename remaining ticker columns to symbol
-- Tables: reference_cache, technical_indicators, idea_outcomes
-- Note: sec_cik_cache intentionally keeps 'ticker' (SEC-specific mapping)

-- 1. reference_cache: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'reference_cache' AND column_name = 'ticker') THEN
        ALTER TABLE reference_cache RENAME COLUMN ticker TO symbol;
    END IF;
END $$;

-- 2. technical_indicators: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'technical_indicators' AND column_name = 'ticker') THEN
        ALTER TABLE technical_indicators RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS idx_technical_indicators_ticker;
CREATE INDEX IF NOT EXISTS idx_technical_indicators_symbol ON technical_indicators(symbol);

-- 3. idea_outcomes: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'idea_outcomes' AND column_name = 'ticker') THEN
        ALTER TABLE idea_outcomes RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
