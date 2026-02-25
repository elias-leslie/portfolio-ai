-- Migration 061: Add FK constraints to symbols table
-- This enforces referential integrity for symbol columns across the schema.
-- Prerequisites: Migration 058 (symbols table), 059-060 (ticker→symbol renames)

-- Note: This migration adds DEFERRABLE INITIALLY DEFERRED constraints
-- so inserts can happen in any order within a transaction.

-- Core tables with symbol column
ALTER TABLE day_bars
ADD CONSTRAINT fk_day_bars_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE watchlist_items
ADD CONSTRAINT fk_watchlist_items_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE portfolio_positions
ADD CONSTRAINT fk_portfolio_positions_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE news_cache
ADD CONSTRAINT fk_news_cache_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE price_cache
ADD CONSTRAINT fk_price_cache_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE technical_indicators
ADD CONSTRAINT fk_technical_indicators_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE strategy_definitions
ADD CONSTRAINT fk_strategy_definitions_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE strategy_signals
ADD CONSTRAINT fk_strategy_signals_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE backtest_runs
ADD CONSTRAINT fk_backtest_runs_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- fundamental_cache was dropped in migration 021, reference_cache is the replacement
-- Note: reference_cache stores JSON payload, no direct symbol column to constrain

ALTER TABLE earnings_surprises
ADD CONSTRAINT fk_earnings_surprises_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- Create index for symbols table lookups
CREATE INDEX IF NOT EXISTS idx_symbols_is_active ON symbols(is_active) WHERE is_active = true;

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 061: Added FK constraints to 11 tables referencing symbols';
END $$;
