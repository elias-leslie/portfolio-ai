-- Migration: 098_seed_celery_feature_mappings.sql
-- Purpose: Populate celery_feature_mappings with task-to-feature relationships
-- Dependencies: 097_create_celery_feature_mappings.sql
--
-- Creates 103 mappings linking 59 Celery tasks to 66 features
-- Results: 20 tasks with multiple features, 19 features with multiple tasks
--
-- Example queries:
-- 1. Find all tasks powering a feature:
--    SELECT cc.task_name, cc.schedule, cfm.confidence, cfm.reason
--    FROM feature_capabilities fc
--    JOIN celery_feature_mappings cfm ON fc.id = cfm.feature_id
--    JOIN celery_capabilities cc ON cfm.task_name = cc.task_name
--    WHERE fc.feature_id = 'FEAT-001';
--
-- 2. Find all features powered by a task:
--    SELECT fc.feature_id, fc.name, cfm.confidence, cfm.reason
--    FROM celery_capabilities cc
--    JOIN celery_feature_mappings cfm ON cc.task_name = cfm.task_name
--    JOIN feature_capabilities fc ON cfm.feature_id = fc.id
--    WHERE cc.task_name = 'refresh-watchlist-scores';

-- Clear any existing mappings (idempotent)
TRUNCATE TABLE celery_feature_mappings;

-- Market Data & Intelligence Tasks
INSERT INTO celery_feature_mappings (task_name, feature_id, relationship_type, confidence, reason, linked_by)
VALUES
-- refresh-daily-ohlcv powers market data for dashboard and watchlist
('refresh-daily-ohlcv', 2, 'powers', 'high', 'Provides daily OHLCV data for Fear & Greed calculations', 'migration'),
('refresh-daily-ohlcv', 17, 'powers', 'high', 'Provides daily OHLCV data for market indicators chart', 'migration'),
('refresh-daily-ohlcv', 18, 'powers', 'high', 'Provides daily OHLCV data for sector performance analysis', 'migration'),
('refresh-daily-ohlcv', 19, 'powers', 'high', 'Provides daily OHLCV data for today''s movers summary', 'migration'),

-- refresh-watchlist-ohlcv powers watchlist sparklines and score history
('refresh-watchlist-ohlcv', 32, 'powers', 'high', 'Provides OHLCV data for watchlist sparkline charts', 'migration'),
('refresh-watchlist-ohlcv', 125, 'powers', 'high', 'Provides historical OHLCV data for watchlist score history visualization', 'migration'),

-- maintain-historical-market-data ensures data completeness
('maintain-historical-market-data', 80, 'powers', 'high', 'Maintains data freshness tracked in capabilities dashboard', 'migration'),
('maintain-historical-market-data', 99, 'powers', 'high', 'Directly powers the data freshness status display', 'migration'),

-- Fear & Greed calculation pipeline
('populate-fear-greed-inputs-daily', 2, 'powers', 'high', 'Fetches inputs (VIX, breadth, momentum) for Fear & Greed calculation', 'migration'),
('populate-fear-greed-inputs-daily', 16, 'powers', 'high', 'Fetches inputs for Fear & Greed gauge visualization', 'migration'),
('calculate-fear-greed-daily', 2, 'powers', 'high', 'Calculates Fear & Greed index value displayed on dashboard', 'migration'),
('calculate-fear-greed-daily', 16, 'powers', 'high', 'Calculates Fear & Greed index for gauge visualization', 'migration'),
('update-fear-greed-after-close', 2, 'powers', 'high', 'Updates Fear & Greed calculation after market close', 'migration'),
('update-fear-greed-after-close', 16, 'powers', 'high', 'Updates Fear & Greed gauge after market close', 'migration'),
('calculate-fear-greed-after-close', 2, 'powers', 'high', 'Recalculates Fear & Greed index post-market', 'migration'),
('refresh-fear-greed-midday', 2, 'powers', 'high', 'Updates Fear & Greed index midday for intraday monitoring', 'migration'),
('calculate-fear-greed-midday', 2, 'powers', 'high', 'Calculates midday Fear & Greed snapshot', 'migration'),

-- Technical indicators
('update-technical-indicators-daily', 30, 'powers', 'high', 'Updates technical indicators shown in watchlist score breakdown', 'migration'),
('update-technical-indicators-daily', 130, 'powers', 'high', 'Updates RVOL analytics displayed in watchlist', 'migration'),
('update-technical-indicators-daily', 131, 'powers', 'high', 'Updates peer comparison technical metrics', 'migration'),
('update-technical-indicators-daily', 132, 'powers', 'high', 'Updates sector rotation technical analysis', 'migration'),

-- Watchlist & Scoring
('refresh-watchlist-scores', 26, 'powers', 'high', 'Recalculates all watchlist scores when symbols are added/modified', 'migration'),
('refresh-watchlist-scores', 27, 'powers', 'high', 'Updates scores searchable via watchlist search', 'migration'),
('refresh-watchlist-scores', 28, 'powers', 'high', 'Powers score data shown in expandable watchlist rows', 'migration'),
('refresh-watchlist-scores', 29, 'powers', 'high', 'Generates symbol narrative intelligence displayed in watchlist', 'migration'),
('refresh-watchlist-scores', 30, 'powers', 'high', 'Powers the score breakdown display with pillar metrics', 'migration'),
('refresh-watchlist-scores', 31, 'powers', 'high', 'Updates scores when inline notes are edited', 'migration'),
('refresh-watchlist-scores', 33, 'powers', 'high', 'Triggered by refresh all symbols action', 'migration'),
('refresh-watchlist-scores', 125, 'powers', 'high', 'Generates historical score data for score history visualization', 'migration'),
('refresh-watchlist-scores', 126, 'powers', 'high', 'Provides progress tracking for watchlist refresh UI', 'migration'),

-- Watchlist automation
('discover-watchlist-candidates-daily', 136, 'powers', 'high', 'Auto-discovers watchlist candidates using scoring logic', 'migration'),
('trim-underperforming-watchlist-daily', 137, 'powers', 'high', 'Auto-trims underperforming symbols from watchlist', 'migration'),
('generate-watchlist-daily-report', 34, 'powers', 'high', 'Generates the daily watchlist report visible in UI', 'migration'),

-- Portfolio Analysis
('run-portfolio-analyzer-daily', 43, 'powers', 'high', 'Calculates portfolio statistics (Sharpe, volatility, etc.)', 'migration'),
('run-portfolio-analyzer-daily', 44, 'powers', 'high', 'Generates asset allocation data for pie charts', 'migration'),
('run-portfolio-analyzer-daily', 45, 'powers', 'high', 'Calculates diversification score shown in portfolio', 'migration'),
('run-portfolio-analyzer-daily', 46, 'powers', 'high', 'Generates risk profile breakdown (beta, VaR, etc.)', 'migration'),
('run-portfolio-analyzer-daily', 47, 'powers', 'high', 'Identifies top performers displayed in portfolio section', 'migration'),
('run-portfolio-analyzer-daily', 51, 'powers', 'high', 'Generates investment ideas/catalysts shown in portfolio', 'migration'),
('run-portfolio-analyzer-daily', 128, 'powers', 'high', 'Powers comprehensive portfolio analytics dashboard', 'migration'),
('update-portfolio-covariance-daily', 46, 'powers', 'high', 'Updates covariance matrix used in risk profile calculations', 'migration'),
('update-portfolio-covariance-daily', 128, 'powers', 'high', 'Updates covariance data for portfolio analytics', 'migration'),
('save-portfolio-snapshots-daily', 43, 'powers', 'high', 'Saves daily snapshots for portfolio statistics trending', 'migration'),

-- Strategy & Trading
('evaluate-strategy-performance', 63, 'powers', 'high', 'Evaluates strategy performance shown in strategy summary cards', 'migration'),
('evaluate-strategy-performance', 65, 'powers', 'high', 'Populates strategy performance data in strategy table', 'migration'),
('evaluate-strategy-performance', 66, 'powers', 'high', 'Generates performance metrics for strategy detail modal', 'migration'),
('evaluate-strategy-performance', 138, 'powers', 'high', 'Tracks strategy performance variance over time', 'migration'),
('generate-daily-strategy-signals', 74, 'powers', 'high', 'Generates trade recommendation cards displayed in recommendations tab', 'migration'),
('generate-daily-strategy-signals', 75, 'powers', 'high', 'Generates signal summary cards with strength metrics', 'migration'),
('generate-daily-strategy-signals', 79, 'powers', 'high', 'Generates signal reasons displayed in UI', 'migration'),
('generate-daily-strategy-signals', 139, 'powers', 'high', 'Core task for strategy signal generation', 'migration'),
('auto-paper-trade-from-signals', 53, 'powers', 'high', 'Automatically executes paper trades from generated signals', 'migration'),
('auto-paper-trade-from-signals', 54, 'powers', 'high', 'Updates performance metrics displayed in paper trading dashboard', 'migration'),
('auto-paper-trade-from-signals', 55, 'powers', 'high', 'Respects pipeline controls (enabled/disabled automation)', 'migration'),
('auto-paper-trade-from-signals', 56, 'powers', 'high', 'Creates open positions visible in open positions tab', 'migration'),
('auto-paper-trade-from-signals', 57, 'powers', 'high', 'Closes positions visible in closed trades tab', 'migration'),
('update-paper-trades-daily', 53, 'powers', 'high', 'Updates paper portfolio summary with latest P&L', 'migration'),
('update-paper-trades-daily', 54, 'powers', 'high', 'Recalculates performance metrics for paper trading', 'migration'),
('generate-weekly-strategies', 62, 'powers', 'high', 'Generates new strategies displayed in strategy generation UI', 'migration'),
('auto-promote-strategies', 63, 'powers', 'high', 'Auto-promotes high-performing strategies reflected in strategy cards', 'migration'),
('weekly-strategy-evolution', 7, 'powers', 'high', 'Evolves strategies as part of strategy evolution loop', 'migration'),
('daily-strategy-refresh', 62, 'powers', 'high', 'Refreshes strategy evaluations daily', 'migration'),
('weekly-optimization-review', 138, 'powers', 'high', 'Reviews and optimizes strategy performance weekly', 'migration'),

-- News & Sentiment
('refresh-news-sentiment', 22, 'powers', 'high', 'Fetches and processes news articles for unified news feed', 'migration'),
('refresh-news-sentiment', 23, 'powers', 'high', 'Calculates sentiment breakdown displayed in news tab', 'migration'),
('cleanup-old-news-weekly', 22, 'powers', 'medium', 'Cleans up old news articles to keep feed performant', 'migration'),
('profile-news-sources', 134, 'powers', 'high', 'Generates news health telemetry for monitoring news quality', 'migration'),
('retrain-article-quality-model', 135, 'powers', 'high', 'Retrains ML model for article quality scoring', 'migration'),

-- Infrastructure & Monitoring
('scan-system-capabilities', 80, 'powers', 'high', 'Scans system and updates capabilities dashboard', 'migration'),
('scan-system-capabilities', 89, 'powers', 'high', 'Triggered by scan system button in capabilities UI', 'migration'),
('scan-feature-capabilities', 88, 'powers', 'high', 'Scans and updates features tab in capabilities dashboard', 'migration'),
('maintain-data-freshness', 80, 'powers', 'high', 'Maintains data freshness tracking for capabilities dashboard', 'migration'),
('maintain-data-freshness', 99, 'powers', 'high', 'Directly updates data freshness status display', 'migration'),
('verify-acceptance-criteria', 165, 'powers', 'high', 'Auto-verifies acceptance criteria for all features', 'migration'),
('refresh-expired-artifacts', 165, 'powers', 'medium', 'Refreshes expired artifacts used in acceptance criteria verification', 'migration'),

-- Fundamentals & Valuation
('ingest-fundamental-data-weekly', 140, 'powers', 'high', 'Ingests fundamental data displayed in valuation metrics', 'migration'),
('parse-valuation-metrics', 140, 'powers', 'high', 'Parses and formats valuation metrics for display', 'migration'),
('update-earnings-surprises-weekly', 176, 'powers', 'high', 'Updates earnings surprises data for scoring and display', 'migration'),
('refresh-analyst-revisions-daily', 177, 'powers', 'high', 'Refreshes analyst estimate revisions used in scoring', 'migration'),
('refresh-financial-health-scores-weekly', 163, 'powers', 'high', 'Refreshes financial health scores displayed in watchlist', 'migration'),

-- Options & Advanced Metrics
('fetch-options-activity-daily', 152, 'powers', 'high', 'Fetches options flow metrics for scoring and display', 'migration'),
('fetch-putcall-ratio-market-open', 188, 'powers', 'high', 'Fetches put/call ratio at market open for sentiment analysis', 'migration'),
('fetch-putcall-ratio-market-close', 188, 'powers', 'high', 'Fetches put/call ratio at market close for EOD analysis', 'migration'),

-- Macro & Economic
('ingest-macro-indicators-daily', 153, 'powers', 'high', 'Ingests FRED macro indicators for macro scoring pillar', 'migration'),
('refresh-market-ohlcv-midday', 2, 'powers', 'medium', 'Refreshes market OHLCV midday for intraday monitoring', 'migration'),

-- Reference Data
('refresh-yfinance-reference', 80, 'powers', 'medium', 'Refreshes yfinance reference data for symbol metadata', 'migration'),
('refresh-alphavantage-reference-backup', 80, 'powers', 'medium', 'Refreshes AlphaVantage reference data as backup', 'migration'),
('refresh-sec-cik-cache-weekly', 80, 'powers', 'medium', 'Refreshes SEC CIK mapping cache for filing lookups', 'migration'),

-- Database Maintenance
('vacuum-database-weekly', 80, 'powers', 'medium', 'Vacuums database to maintain performance', 'migration'),
('get-database-size-daily', 80, 'powers', 'medium', 'Tracks database size for monitoring', 'migration'),
('cleanup-old-logs-daily', 102, 'powers', 'medium', 'Cleans up old logs to maintain logs viewer performance', 'migration'),
('cleanup-old-agent-runs-weekly', 114, 'powers', 'medium', 'Cleans up old agent runs shown in recent runs table', 'migration'),
('cleanup-temp-files-daily', 80, 'powers', 'low', 'Cleans up temporary files to free disk space', 'migration'),
('cleanup-orphaned-data-weekly', 80, 'powers', 'low', 'Cleans up orphaned data to maintain data integrity', 'migration'),
('check-disk-space-periodic', 93, 'powers', 'medium', 'Monitors disk space for resource monitoring display', 'migration'),

-- AI Agents
('run-discovery-agent-daily', 73, 'powers', 'high', 'Runs discovery agent to generate trade recommendations', 'migration'),
('run-discovery-agent-daily', 74, 'powers', 'high', 'Generates signal summary cards via discovery agent', 'migration'),
('run-discovery-agent-daily', 110, 'powers', 'high', 'Tracks discovery agent execution in agent execution metrics', 'migration'),

-- Rules Validation
('daily-rules-validation', 3, 'powers', 'high', 'Validates trading rules against threshold alignment', 'migration'),
('daily-rules-validation', 8, 'powers', 'high', 'Powers AI rules validation agent feature', 'migration'),

-- Risk Management
('refresh-risk-metrics-daily', 46, 'powers', 'high', 'Refreshes risk metrics displayed in risk profile breakdown', 'migration'),
('refresh-risk-metrics-daily', 128, 'powers', 'high', 'Updates risk metrics for portfolio analytics dashboard', 'migration'),

-- Cleanup & Optimization
('cleanup-old-artifact-versions', 165, 'powers', 'medium', 'Cleans up old artifact versions used in acceptance criteria', 'migration')

ON CONFLICT (task_name, feature_id) DO NOTHING;

-- Create index for efficient feature -> tasks lookups
CREATE INDEX IF NOT EXISTS idx_celery_feature_mappings_feature_id
ON celery_feature_mappings(feature_id);

-- Create index for efficient task -> features lookups
CREATE INDEX IF NOT EXISTS idx_celery_feature_mappings_task_name
ON celery_feature_mappings(task_name);

-- Verify mappings
DO $$
DECLARE
    mapping_count INTEGER;
    task_count INTEGER;
    feature_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO mapping_count FROM celery_feature_mappings;
    SELECT COUNT(DISTINCT task_name) INTO task_count FROM celery_feature_mappings;
    SELECT COUNT(DISTINCT feature_id) INTO feature_count FROM celery_feature_mappings;

    RAISE NOTICE 'Celery-Feature Mappings Migration Complete:';
    RAISE NOTICE '  - Total mappings: %', mapping_count;
    RAISE NOTICE '  - Unique tasks: %', task_count;
    RAISE NOTICE '  - Unique features: %', feature_count;
END $$;
