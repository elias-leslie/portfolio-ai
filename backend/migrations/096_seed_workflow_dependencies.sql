-- Migration 096: Seed known workflow dependencies
-- Phase 1.5 of Workflow Visualization - based on system exploration and timing analysis
-- NOTE: Task names updated to match actual beat_schedule keys (2025-12-09)

-- Technical indicators depend on OHLCV data
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-daily-ohlcv', 'refresh-watchlist-ohlcv'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: indicators need day_bars data'
)
WHERE task_name = 'update-technical-indicators-daily';

-- Fear & Greed inputs depend on technical indicators
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('update-technical-indicators-daily'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: fear-greed inputs need technical_indicators'
)
WHERE task_name = 'populate-fear-greed-inputs-daily';

-- Fear & Greed calculation depends on inputs
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('populate-fear-greed-inputs-daily'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: fear-greed calculation needs inputs'
)
WHERE task_name = 'calculate-fear-greed-daily';

-- Discovery agent depends on data being ready
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('calculate-fear-greed-daily', 'scan-system-capabilities'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: runs after all data refresh complete'
)
WHERE task_name = 'run-discovery-agent';

-- Portfolio analyzer depends on data being ready
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('calculate-fear-greed-daily', 'scan-system-capabilities'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: runs after all data refresh complete'
)
WHERE task_name = 'run-portfolio-analyzer';

-- Strategy signals depend on market data
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-daily-ohlcv'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: signals need current day_bars'
)
WHERE task_name = 'generate-daily-strategy-signals';

-- Paper trades depend on signals
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('generate-daily-strategy-signals'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: paper trades need strategy_signals'
)
WHERE task_name = 'auto-paper-trade-from-signals';

-- Valuation parsing depends on yfinance fetch
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-yfinance-reference-data'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: parse needs reference_cache'
)
WHERE task_name = 'parse-valuation-metrics';

-- Alpha Vantage backup depends on parsing (to know what's missing)
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('parse-valuation-metrics'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: fills gaps identified by parse'
)
WHERE task_name = 'refresh-alphavantage-reference-backup';

-- Watchlist scores depend on scoring data being ready
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('update-technical-indicators-daily', 'parse-valuation-metrics'),
    'remove', '[]'::jsonb,
    'reason', 'Timing: needs technical + valuation data'
)
WHERE task_name = 'refresh-watchlist-scores';
