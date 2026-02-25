-- Migration 069: Add FK constraints to fundamental data tables
-- References symbols table (created in migration 058)
-- Uses DEFERRABLE INITIALLY DEFERRED for bulk insert compatibility

-- First, ensure all symbols exist in symbols table
-- Insert any missing symbols from fundamental tables
INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol, 'equity', NOW()
FROM cash_flow_metrics
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol, 'equity', NOW()
FROM insider_transactions
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol, 'equity', NOW()
FROM institutional_holdings
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol, 'equity', NOW()
FROM institutional_ownership_summary
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbols (symbol, security_type, created_at)
SELECT DISTINCT symbol, 'equity', NOW()
FROM short_interest
WHERE symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Add FK constraints
ALTER TABLE cash_flow_metrics
    ADD CONSTRAINT fk_cash_flow_metrics_symbol
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
    ON UPDATE CASCADE ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE insider_transactions
    ADD CONSTRAINT fk_insider_transactions_symbol
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
    ON UPDATE CASCADE ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE institutional_holdings
    ADD CONSTRAINT fk_institutional_holdings_symbol
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
    ON UPDATE CASCADE ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE institutional_ownership_summary
    ADD CONSTRAINT fk_institutional_ownership_summary_symbol
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
    ON UPDATE CASCADE ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE short_interest
    ADD CONSTRAINT fk_short_interest_symbol
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
    ON UPDATE CASCADE ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

-- Log the migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 069: Added FK constraints to 5 fundamental data tables';
END $$;
