-- Migration 010: Establish dedicated news_cache table for sentiment-scored articles
-- Created: 2025-02-14
-- Description: Creates news_cache storage, indexes, metadata registration, and cleans legacy reference_cache entries.

CREATE TABLE IF NOT EXISTS news_cache (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    headline TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    news_source_name TEXT,
    author TEXT,
    image_url TEXT,
    published_at TIMESTAMPTZ,
    sentiment_score DOUBLE PRECISION,
    sentiment_label TEXT,
    sentiment_confidence DOUBLE PRECISION,
    sentiment_model TEXT,
    raw_payload JSONB,
    content_hash TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure unique constraint to prevent duplicate articles per ticker
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_cache_ticker_hash
    ON news_cache (ticker, content_hash);

-- Support recency queries
CREATE INDEX IF NOT EXISTS idx_news_cache_ticker_published
    ON news_cache (ticker, published_at DESC);

-- Register table metadata
INSERT INTO table_registry (table_name, table_type, description)
VALUES ('news_cache', 'timeseries', 'Cached news articles with sentiment scoring')
ON CONFLICT (table_name) DO UPDATE
SET table_type = EXCLUDED.table_type,
    description = EXCLUDED.description;

-- Clean up legacy reference_cache entries that stored news payloads
DELETE FROM reference_cache WHERE source = 'news';

-- Summary log for evaluation/backtesting
CREATE TABLE IF NOT EXISTS news_summary_log (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    sentiment_score DOUBLE PRECISION,
    sentiment_delta DOUBLE PRECISION,
    positive_count INTEGER,
    neutral_count INTEGER,
    negative_count INTEGER,
    article_count INTEGER,
    model_breakdown JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_summary_log_ticker_time
    ON news_summary_log (ticker, window_end DESC);

INSERT INTO table_registry (table_name, table_type, description)
VALUES (
    'news_summary_log',
    'timeseries',
    'Aggregated news sentiment snapshots for evaluation'
)
ON CONFLICT (table_name) DO UPDATE
SET table_type = EXCLUDED.table_type,
    description = EXCLUDED.description;
