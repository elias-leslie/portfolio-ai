-- Migration 100: Add missing FK constraints for symbol columns
-- Note: sec_cik_cache is excluded since it's a cache for broader market symbols
-- Prerequisites: No orphan records in target tables
-- Date: 2025-12-09

-- Clean orphan records first (test DBs may have stale data)
DELETE FROM reference_cache WHERE symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM news_summary_log WHERE symbol IS NOT NULL AND symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM idea_outcomes WHERE symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM backtest_trades WHERE symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM paper_trade_transactions WHERE symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM strategy_reviews WHERE symbol NOT IN (SELECT symbol FROM symbols);
DELETE FROM symbol_risk_metrics WHERE symbol NOT IN (SELECT symbol FROM symbols);

-- 1. backtest_trades -> symbols
ALTER TABLE backtest_trades
ADD CONSTRAINT fk_backtest_trades_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 2. idea_outcomes -> symbols
ALTER TABLE idea_outcomes
ADD CONSTRAINT fk_idea_outcomes_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 3. news_summary_log -> symbols (CASCADE DELETE since news is expendable)
ALTER TABLE news_summary_log
ADD CONSTRAINT fk_news_summary_log_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE CASCADE
DEFERRABLE INITIALLY DEFERRED;

-- 4. paper_trade_transactions -> symbols
ALTER TABLE paper_trade_transactions
ADD CONSTRAINT fk_paper_trade_transactions_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 5. reference_cache -> symbols
ALTER TABLE reference_cache
ADD CONSTRAINT fk_reference_cache_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 6. strategy_reviews -> symbols
ALTER TABLE strategy_reviews
ADD CONSTRAINT fk_strategy_reviews_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 7. symbol_risk_metrics -> symbols
ALTER TABLE symbol_risk_metrics
ADD CONSTRAINT fk_symbol_risk_metrics_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- Create indexes for JOIN performance (only if they don't exist)
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_idea_outcomes_symbol ON idea_outcomes(symbol);
CREATE INDEX IF NOT EXISTS idx_news_summary_log_symbol ON news_summary_log(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_symbol ON paper_trade_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_reference_cache_symbol ON reference_cache(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_symbol ON strategy_reviews(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_risk_metrics_symbol ON symbol_risk_metrics(symbol);
