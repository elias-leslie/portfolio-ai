-- Migration 041: Add valuation metrics columns to reference_cache
-- Extracts P/E, P/B, P/S, PEG, dividend yield, and payout ratio from JSON payload

ALTER TABLE reference_cache
  ADD COLUMN IF NOT EXISTS pe_ratio_trailing DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pe_ratio_forward DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS ps_ratio DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS pb_ratio DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS peg_ratio DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS dividend_yield DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS payout_ratio DOUBLE PRECISION;

-- Create index for trailing P/E queries
CREATE INDEX IF NOT EXISTS idx_reference_cache_pe_trailing
  ON reference_cache(pe_ratio_trailing)
  WHERE pe_ratio_trailing IS NOT NULL;

-- Create index for P/B queries
CREATE INDEX IF NOT EXISTS idx_reference_cache_pb
  ON reference_cache(pb_ratio)
  WHERE pb_ratio IS NOT NULL;

-- Create index for P/S queries
CREATE INDEX IF NOT EXISTS idx_reference_cache_ps
  ON reference_cache(ps_ratio)
  WHERE ps_ratio IS NOT NULL;

-- Create index for dividend yield queries
CREATE INDEX IF NOT EXISTS idx_reference_cache_dividend_yield
  ON reference_cache(dividend_yield)
  WHERE dividend_yield IS NOT NULL;
