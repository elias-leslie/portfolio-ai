-- Migration 025: Add source_metrics table for news quality profiling
-- Purpose: Store calculated quality metrics per news vendor/source
--
-- Part of: News Source Quality Profiling System (Phase 1)
-- Created: 2025-11-11
-- Related: tasks-0049-news-source-quality-profiling.md

-- Create source_metrics table
CREATE TABLE IF NOT EXISTS source_metrics (
    id SERIAL PRIMARY KEY,
    vendor VARCHAR(100) NOT NULL,
    duplicate_rate DOUBLE PRECISION NOT NULL CHECK (duplicate_rate >= 0.0 AND duplicate_rate <= 1.0),
    diversity_score DOUBLE PRECISION NOT NULL CHECK (diversity_score >= 0.0 AND diversity_score <= 1.0),
    confidence_avg DOUBLE PRECISION NOT NULL CHECK (confidence_avg >= 0.0 AND confidence_avg <= 1.0),
    freshness_score DOUBLE PRECISION NOT NULL CHECK (freshness_score >= 0.0 AND freshness_score <= 1.0),
    user_useful_rate DOUBLE PRECISION CHECK (user_useful_rate >= 0.0 AND user_useful_rate <= 1.0),
    quality_score DOUBLE PRECISION NOT NULL CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    article_count INTEGER NOT NULL DEFAULT 0 CHECK (article_count >= 0),
    sample_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_vendor_calculated_at UNIQUE (vendor, calculated_at)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_source_metrics_vendor ON source_metrics(vendor);
CREATE INDEX IF NOT EXISTS idx_source_metrics_calculated_at ON source_metrics(calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_metrics_quality_score ON source_metrics(quality_score DESC);

-- Add comments for documentation
COMMENT ON TABLE source_metrics IS 'Quality metrics for news vendors calculated by profiling task';
COMMENT ON COLUMN source_metrics.vendor IS 'Vendor/source identifier (e.g., polygon, finnhub, sec_edgar)';
COMMENT ON COLUMN source_metrics.duplicate_rate IS 'Proportion of duplicate articles (0=none, 1=all)';
COMMENT ON COLUMN source_metrics.diversity_score IS 'Headline uniqueness score (1=all unique, 0=all same)';
COMMENT ON COLUMN source_metrics.confidence_avg IS 'Average sentiment confidence from FinBERT/VADER';
COMMENT ON COLUMN source_metrics.freshness_score IS 'Recency score (1=24h old, 0=7d old)';
COMMENT ON COLUMN source_metrics.user_useful_rate IS 'User feedback score (NULL if no feedback yet)';
COMMENT ON COLUMN source_metrics.quality_score IS 'Weighted composite quality score';
COMMENT ON COLUMN source_metrics.article_count IS 'Number of articles in sample period';
COMMENT ON COLUMN source_metrics.sample_period_start IS 'Start of analysis window';
COMMENT ON COLUMN source_metrics.calculated_at IS 'When metrics were calculated';
