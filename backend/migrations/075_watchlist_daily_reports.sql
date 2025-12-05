-- Migration 075: Watchlist Daily Reports
-- Creates table for daily watchlist change summaries

CREATE TABLE IF NOT EXISTS watchlist_daily_reports (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    report_date DATE NOT NULL UNIQUE,
    symbols_added JSONB NOT NULL DEFAULT '[]'::jsonb,
    symbols_removed JSONB NOT NULL DEFAULT '[]'::jsonb,
    score_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick lookup by date
CREATE INDEX IF NOT EXISTS idx_watchlist_daily_reports_report_date ON watchlist_daily_reports(report_date DESC);

-- Index for quick lookup of latest report
CREATE INDEX IF NOT EXISTS idx_watchlist_daily_reports_generated_at ON watchlist_daily_reports(generated_at DESC);
