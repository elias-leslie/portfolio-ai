-- Migration 043: Paper Trading Cash Management & Ownership Tracking
-- Description: Add cash balance tracking, transaction log, and ownership tracking
--              for autonomous paper trading and agent watchlist management
-- Date: 2025-11-14
-- Dependencies: Task 0064 (Paper Trading Engine Phase A)

-- ============================================================================
-- PART 1: Cash Balance Tracking for Portfolio Accounts
-- ============================================================================

-- Add cash balance columns to portfolio_accounts
DO $$
BEGIN
    -- Add cash_balance column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_accounts'
        AND column_name = 'cash_balance'
    ) THEN
        ALTER TABLE portfolio_accounts
        ADD COLUMN cash_balance DOUBLE PRECISION DEFAULT 100000.0 NOT NULL;

        RAISE NOTICE 'Added cash_balance column to portfolio_accounts';
    END IF;

    -- Add initial_cash column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_accounts'
        AND column_name = 'initial_cash'
    ) THEN
        ALTER TABLE portfolio_accounts
        ADD COLUMN initial_cash DOUBLE PRECISION DEFAULT 100000.0 NOT NULL;

        RAISE NOTICE 'Added initial_cash column to portfolio_accounts';
    END IF;
END $$;

-- Add index on account_type for efficient paper trading account queries
CREATE INDEX IF NOT EXISTS idx_portfolio_accounts_type
ON portfolio_accounts(account_type);

-- ============================================================================
-- PART 2: Transaction Log Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS paper_trade_transactions (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    trade_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('ENTRY', 'EXIT')),
    ticker TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    cash_before DOUBLE PRECISION NOT NULL,
    cash_after DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,

    -- Foreign key to idea_outcomes
    CONSTRAINT paper_trade_transactions_trade_id_fkey
        FOREIGN KEY (trade_id) REFERENCES idea_outcomes(idea_id) ON DELETE CASCADE
);

-- Indexes for efficient transaction queries
CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_trade_id
ON paper_trade_transactions(trade_id);

CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_ticker
ON paper_trade_transactions(ticker);

CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_timestamp
ON paper_trade_transactions(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_type
ON paper_trade_transactions(transaction_type);

-- ============================================================================
-- PART 3: Ownership Tracking for Watchlist Items
-- ============================================================================

DO $$
BEGIN
    -- Add added_by column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'watchlist_items'
        AND column_name = 'added_by'
    ) THEN
        ALTER TABLE watchlist_items
        ADD COLUMN added_by TEXT DEFAULT 'user' NOT NULL;

        RAISE NOTICE 'Added added_by column to watchlist_items';
    END IF;

    -- Add added_at column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'watchlist_items'
        AND column_name = 'added_at'
    ) THEN
        ALTER TABLE watchlist_items
        ADD COLUMN added_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;

        RAISE NOTICE 'Added added_at column to watchlist_items';
    END IF;
END $$;

-- Index on added_by for filtering agent-added tickers
CREATE INDEX IF NOT EXISTS idx_watchlist_items_added_by
ON watchlist_items(added_by);

-- ============================================================================
-- PART 4: Position Sizing Extensions for idea_outcomes
-- ============================================================================

DO $$
BEGIN
    -- Add shares column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'idea_outcomes'
        AND column_name = 'shares'
    ) THEN
        ALTER TABLE idea_outcomes
        ADD COLUMN shares INTEGER;

        RAISE NOTICE 'Added shares column to idea_outcomes';
    END IF;

    -- Add entry_amount column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'idea_outcomes'
        AND column_name = 'entry_amount'
    ) THEN
        ALTER TABLE idea_outcomes
        ADD COLUMN entry_amount DOUBLE PRECISION;

        RAISE NOTICE 'Added entry_amount column to idea_outcomes';
    END IF;

    -- Add exit_amount column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'idea_outcomes'
        AND column_name = 'exit_amount'
    ) THEN
        ALTER TABLE idea_outcomes
        ADD COLUMN exit_amount DOUBLE PRECISION;

        RAISE NOTICE 'Added exit_amount column to idea_outcomes';
    END IF;

    -- Add realized_pnl column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'idea_outcomes'
        AND column_name = 'realized_pnl'
    ) THEN
        ALTER TABLE idea_outcomes
        ADD COLUMN realized_pnl DOUBLE PRECISION;

        RAISE NOTICE 'Added realized_pnl column to idea_outcomes';
    END IF;
END $$;

-- ============================================================================
-- PART 5: Initialize Paper Trading Account
-- ============================================================================

-- Create default paper trading account if it doesn't exist
INSERT INTO portfolio_accounts (id, name, account_type, cash_balance, initial_cash)
VALUES ('paper_trading', 'Paper Trading Portfolio', 'paper', 100000.0, 100000.0)
ON CONFLICT (id) DO UPDATE
SET
    cash_balance = EXCLUDED.cash_balance,
    initial_cash = EXCLUDED.initial_cash;

-- ============================================================================
-- PART 6: Update Table Registry
-- ============================================================================

-- Register new table in table_registry
INSERT INTO table_registry (table_name, table_type, description)
VALUES ('paper_trade_transactions', 'trading', 'Audit trail for all paper trade transactions (entry/exit)')
ON CONFLICT (table_name) DO NOTHING;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    accounts_count INTEGER;
    has_cash_balance BOOLEAN;
    has_initial_cash BOOLEAN;
    transactions_table_exists BOOLEAN;
    watchlist_has_ownership BOOLEAN;
    ideas_has_position_sizing BOOLEAN;
BEGIN
    -- Check portfolio_accounts has new columns
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_accounts' AND column_name = 'cash_balance'
    ) INTO has_cash_balance;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'portfolio_accounts' AND column_name = 'initial_cash'
    ) INTO has_initial_cash;

    -- Check transaction table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'paper_trade_transactions'
    ) INTO transactions_table_exists;

    -- Check watchlist has ownership tracking
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'watchlist_items' AND column_name = 'added_by'
    ) INTO watchlist_has_ownership;

    -- Check idea_outcomes has position sizing
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'idea_outcomes' AND column_name = 'shares'
    ) INTO ideas_has_position_sizing;

    -- Count paper trading accounts
    SELECT COUNT(*) INTO accounts_count
    FROM portfolio_accounts
    WHERE account_type = 'paper';

    -- Report results
    RAISE NOTICE '=== Migration 043 Verification ===';
    RAISE NOTICE 'Portfolio accounts - cash_balance: %', has_cash_balance;
    RAISE NOTICE 'Portfolio accounts - initial_cash: %', has_initial_cash;
    RAISE NOTICE 'Transactions table exists: %', transactions_table_exists;
    RAISE NOTICE 'Watchlist ownership tracking: %', watchlist_has_ownership;
    RAISE NOTICE 'Idea outcomes position sizing: %', ideas_has_position_sizing;
    RAISE NOTICE 'Paper trading accounts: %', accounts_count;

    IF has_cash_balance AND has_initial_cash AND transactions_table_exists
       AND watchlist_has_ownership AND ideas_has_position_sizing
       AND accounts_count > 0 THEN
        RAISE NOTICE '✓ Migration 043 completed successfully';
    ELSE
        RAISE WARNING '✗ Migration 043 incomplete - check errors above';
    END IF;
END $$;
