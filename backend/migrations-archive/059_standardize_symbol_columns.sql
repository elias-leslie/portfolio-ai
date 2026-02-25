-- Migration 059: Standardize ticker/symbol column naming
-- Renames all "ticker" columns to "symbol" for consistency.
-- This migration is idempotent - safe to run multiple times.

-- 1. day_bars: ticker → symbol (simple rename, no constraints)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'day_bars' AND column_name = 'ticker') THEN
        ALTER TABLE day_bars RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS idx_day_bars_ticker;
DROP INDEX IF EXISTS idx_day_bars_ticker_date;
CREATE INDEX IF NOT EXISTS idx_day_bars_symbol ON day_bars(symbol);
CREATE INDEX IF NOT EXISTS idx_day_bars_symbol_date ON day_bars(symbol, date);

-- 2. price_cache: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'price_cache' AND column_name = 'ticker') THEN
        ALTER TABLE price_cache RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS idx_price_cache_ticker;
CREATE INDEX IF NOT EXISTS idx_price_cache_symbol ON price_cache(symbol);

-- 3. news_cache: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'news_cache' AND column_name = 'ticker') THEN
        ALTER TABLE news_cache RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS news_cache_ticker_hash;
DROP INDEX IF EXISTS idx_news_cache_ticker;
CREATE INDEX IF NOT EXISTS idx_news_cache_symbol ON news_cache(symbol);
CREATE INDEX IF NOT EXISTS news_cache_symbol_hash ON news_cache(symbol, content_hash);

-- 4. paper_trade_transactions: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'paper_trade_transactions' AND column_name = 'ticker') THEN
        ALTER TABLE paper_trade_transactions RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS idx_paper_trade_transactions_ticker;
CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_symbol ON paper_trade_transactions(symbol);

-- 5. earnings_surprises: ticker → symbol (has unique constraint)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'earnings_surprises' AND column_name = 'ticker') THEN
        ALTER TABLE earnings_surprises DROP CONSTRAINT IF EXISTS earnings_surprises_ticker_earnings_date_key;
        ALTER TABLE earnings_surprises RENAME COLUMN ticker TO symbol;
        ALTER TABLE earnings_surprises ADD CONSTRAINT earnings_surprises_symbol_earnings_date_key UNIQUE(symbol, earnings_date);
    END IF;
END $$;

-- 6. news_summary_log: ticker → symbol
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'news_summary_log' AND column_name = 'ticker') THEN
        ALTER TABLE news_summary_log RENAME COLUMN ticker TO symbol;
    END IF;
END $$;
DROP INDEX IF EXISTS idx_news_summary_log_ticker;
CREATE INDEX IF NOT EXISTS idx_news_summary_log_symbol ON news_summary_log(symbol);

-- 7. watchlist_gap_coverage: ticker → symbol (has primary key constraint)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'watchlist_gap_coverage' AND column_name = 'ticker') THEN
        ALTER TABLE watchlist_gap_coverage DROP CONSTRAINT IF EXISTS watchlist_gap_coverage_pkey;
        ALTER TABLE watchlist_gap_coverage RENAME COLUMN ticker TO symbol;
        ALTER TABLE watchlist_gap_coverage ADD PRIMARY KEY (symbol, analysis_type);
    END IF;
END $$;

-- 8. portfolio_covariance: ticker1/ticker2 → symbol1/symbol2
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'portfolio_covariance' AND column_name = 'ticker1') THEN
        ALTER TABLE portfolio_covariance DROP CONSTRAINT IF EXISTS portfolio_covariance_pkey;
        ALTER TABLE portfolio_covariance RENAME COLUMN ticker1 TO symbol1;
        ALTER TABLE portfolio_covariance RENAME COLUMN ticker2 TO symbol2;
        ALTER TABLE portfolio_covariance ADD PRIMARY KEY (symbol1, symbol2);
    END IF;
END $$;
