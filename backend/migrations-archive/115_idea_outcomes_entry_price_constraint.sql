-- Migration 115: Add CHECK constraint for positive entry_price on idea_outcomes
--
-- Purpose: Prevent trades with zero or negative entry_price from being inserted.
-- This constraint prevents ZeroDivisionError in calculate_trade_return().
--
-- The backtest_trades table already has this protection:
--   CONSTRAINT backtest_trades_prices_check CHECK (entry_price > 0 AND ...)
-- This brings idea_outcomes to parity.

-- First ensure no bad data exists (should already be fixed)
UPDATE idea_outcomes
SET status = 'error',
    exit_reason = COALESCE(exit_reason, 'invalid_entry_price')
WHERE entry_price <= 0 AND status = 'open';

-- Add the CHECK constraint
ALTER TABLE idea_outcomes
ADD CONSTRAINT idea_outcomes_entry_price_positive
CHECK (entry_price > 0 OR status = 'error');
-- Note: We allow entry_price <= 0 for error status to preserve historical bad data
