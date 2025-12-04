-- Migration 066: Add Piotroski F-Score and Altman Z-Score columns
-- GAP-008: Piotroski F-Score (9-point fundamental quality score)
-- GAP-009: Altman Z-Score (bankruptcy prediction model)

-- Add columns to reference_cache for financial health scores
ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS f_score INTEGER;
ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS f_score_components JSONB;
ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS z_score DECIMAL(10,2);
ALTER TABLE reference_cache ADD COLUMN IF NOT EXISTS z_score_zone VARCHAR(20);

-- Add comments
COMMENT ON COLUMN reference_cache.f_score IS 'Piotroski F-Score (0-9, higher=better quality)';
COMMENT ON COLUMN reference_cache.f_score_components IS 'Individual F-Score component scores (JSON)';
COMMENT ON COLUMN reference_cache.z_score IS 'Altman Z-Score (>2.99=safe, 1.81-2.99=grey, <1.81=distress)';
COMMENT ON COLUMN reference_cache.z_score_zone IS 'Z-Score interpretation: safe, grey, or distress';

-- Create index for querying by scores
CREATE INDEX IF NOT EXISTS idx_reference_cache_f_score ON reference_cache(f_score) WHERE f_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reference_cache_z_score_zone ON reference_cache(z_score_zone) WHERE z_score_zone IS NOT NULL;
