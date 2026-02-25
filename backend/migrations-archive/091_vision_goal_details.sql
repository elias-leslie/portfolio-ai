-- Migration 091: Create vision_goal_details table for detailed goal content
-- Stores objectives, feature bullets, and success criteria for each vision goal
-- Enables full VISION.md goal content to be displayed and queried

-- Create vision_goal_details table
CREATE TABLE IF NOT EXISTS vision_goal_details (
    id SERIAL PRIMARY KEY,
    goal_code TEXT NOT NULL REFERENCES vision_goals(code) ON DELETE CASCADE,
    detail_type TEXT NOT NULL,     -- 'objective', 'feature', 'success_criterion'
    content TEXT NOT NULL,
    order_num INT DEFAULT 0,
    metadata JSONB,                -- Additional structured data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (goal_code, detail_type, order_num)
);

-- Add comments for documentation
COMMENT ON TABLE vision_goal_details IS 'Detailed content for vision goals: objectives, feature bullets, success criteria from VISION.md';
COMMENT ON COLUMN vision_goal_details.goal_code IS 'FK to vision_goals.code (VG-INTEL, VG-AUTO, etc.)';
COMMENT ON COLUMN vision_goal_details.detail_type IS 'Type: objective (1 per goal), feature (multiple), success_criterion (multiple)';
COMMENT ON COLUMN vision_goal_details.content IS 'The actual content text';
COMMENT ON COLUMN vision_goal_details.order_num IS 'Display order within goal/type';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_vision_goal_details_code ON vision_goal_details(goal_code);
CREATE INDEX IF NOT EXISTS idx_vision_goal_details_type ON vision_goal_details(detail_type);
CREATE INDEX IF NOT EXISTS idx_vision_goal_details_code_type ON vision_goal_details(goal_code, detail_type);

-- ============================================================================
-- SEED DATA FROM VISION.md - Goal Details
-- ============================================================================

-- VG-INTEL: Investment Intelligence
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-INTEL', 'objective', 'Transform raw market data into actionable insights', 0, NULL),
('VG-INTEL', 'feature', 'Signal Fusion: Combine news sentiment, fundamentals, and technical indicators into unified BUY/HOLD/AVOID recommendations', 1, '{"highlight": "Signal Fusion"}'::jsonb),
('VG-INTEL', 'feature', 'Confidence Scoring: Provide 0-10 strength scores with supporting evidence', 2, '{"highlight": "Confidence Scoring"}'::jsonb),
('VG-INTEL', 'feature', 'Style Classification: Recommend optimal trading approach (Index/Trend/Value/Swing/Event) with holding periods', 3, '{"highlight": "Style Classification"}'::jsonb),
('VG-INTEL', 'feature', 'Position Sizing: Calculate entry/stop/target prices with risk-adjusted position sizes', 4, '{"highlight": "Position Sizing"}'::jsonb),
('VG-INTEL', 'feature', 'Plain Language: Generate narratives that explain "why" in everyday terms (no jargon)', 5, '{"highlight": "Plain Language"}'::jsonb),
('VG-INTEL', 'success_criterion', 'All recommendations include confidence score, rationale, and supporting data', 1, NULL),
('VG-INTEL', 'success_criterion', 'Users understand insights without needing financial expertise', 2, NULL),
('VG-INTEL', 'success_criterion', 'AI explanations pass plain-language readability tests', 3, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-AUTO: Autonomous AI-Driven Analysis
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-AUTO', 'objective', 'Use AI agents as analysts, not execution authorities', 0, NULL),
('VG-AUTO', 'feature', 'Market Discovery: Discovery Agent scans news/economic data for broad opportunities', 1, '{"highlight": "Market Discovery"}'::jsonb),
('VG-AUTO', 'feature', 'Portfolio Analysis: Portfolio Analyzer generates personalized ideas based on holdings', 2, '{"highlight": "Portfolio Analysis"}'::jsonb),
('VG-AUTO', 'feature', 'Strategy Review: LLM reviewers (Claude/Gemini) independently analyze proposed strategies', 3, '{"highlight": "Strategy Review"}'::jsonb),
('VG-AUTO', 'feature', 'Disagreement Detection: Flag when multiple LLMs disagree on recommendations', 4, '{"highlight": "Disagreement Detection"}'::jsonb),
('VG-AUTO', 'feature', 'Autonomous Execution: Paper trades execute automatically based on validated strategies', 5, '{"highlight": "Autonomous Execution"}'::jsonb),
('VG-AUTO', 'success_criterion', 'Agents generate ideas autonomously on schedule (daily at 03:30 UTC)', 1, NULL),
('VG-AUTO', 'success_criterion', 'LLM reviewers provide independent analysis with reasoning', 2, NULL),
('VG-AUTO', 'success_criterion', 'Disagreements are logged and surfaced to users', 3, NULL),
('VG-AUTO', 'success_criterion', 'Zero manual intervention required for routine operations', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-PORT: Portfolio & Watchlist Management
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-PORT', 'objective', 'Unified monitoring of owned and watched positions', 0, NULL),
('VG-PORT', 'feature', 'Real-Time Analytics: Beta, volatility, concentration, sector exposure, Sharpe ratio, diversification', 1, '{"highlight": "Real-Time Analytics"}'::jsonb),
('VG-PORT', 'feature', 'Watchlist Scoring: Real-time scoring with 7-day history and alert detection', 2, '{"highlight": "Watchlist Scoring"}'::jsonb),
('VG-PORT', 'feature', 'Narrative Intelligence: Plain-language insights for every watchlist ticker', 3, '{"highlight": "Narrative Intelligence"}'::jsonb),
('VG-PORT', 'feature', 'Auto-Sync: Portfolio holdings automatically added to watchlist', 4, '{"highlight": "Auto-Sync"}'::jsonb),
('VG-PORT', 'feature', 'Source Tracking: Display which data source provided each quote', 5, '{"highlight": "Source Tracking"}'::jsonb),
('VG-PORT', 'success_criterion', 'All portfolio positions show current analytics within 15 minutes', 1, NULL),
('VG-PORT', 'success_criterion', 'Watchlist scores update on user-configurable schedule (default: 1 minute)', 2, NULL),
('VG-PORT', 'success_criterion', 'Users can see data provenance (source indicators)', 3, NULL),
('VG-PORT', 'success_criterion', 'Portfolio and watchlist data synchronized automatically', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-VALID: Strategy Validation & Testing
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-VALID', 'objective', 'Never recommend untested strategies', 0, NULL),
('VG-VALID', 'feature', 'Backtesting: Replay strategies against historical data with performance metrics', 1, '{"highlight": "Backtesting"}'::jsonb),
('VG-VALID', 'feature', 'Paper Trading: Execute trades in simulation with cash management', 2, '{"highlight": "Paper Trading"}'::jsonb),
('VG-VALID', 'feature', 'Performance Tracking: Sharpe ratio, max drawdown, win rate, total return', 3, '{"highlight": "Performance Tracking"}'::jsonb),
('VG-VALID', 'feature', 'Equity Curves: Visual comparison of strategy performance over time', 4, '{"highlight": "Equity Curves"}'::jsonb),
('VG-VALID', 'feature', 'Transaction Audit: Complete history of all simulated trades', 5, '{"highlight": "Transaction Audit"}'::jsonb),
('VG-VALID', 'success_criterion', 'Every strategy backtested before paper trading', 1, NULL),
('VG-VALID', 'success_criterion', 'Paper trades tracked with full transaction history', 2, NULL),
('VG-VALID', 'success_criterion', 'Performance metrics updated daily', 3, NULL),
('VG-VALID', 'success_criterion', 'Equity curves available for visual comparison', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-RELY: Reliability & Data Quality
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-RELY', 'objective', 'Production-grade reliability with zero single points of failure', 0, NULL),
('VG-RELY', 'feature', 'Multi-Source Failover: 6 operational data sources with priority-based failover', 1, '{"highlight": "Multi-Source Failover"}'::jsonb),
('VG-RELY', 'feature', 'Freshness Monitoring: Automated checks with scheduled data refreshes', 2, '{"highlight": "Freshness Monitoring"}'::jsonb),
('VG-RELY', 'feature', 'PostgreSQL: Production database with connection pooling (4x throughput)', 3, '{"highlight": "PostgreSQL"}'::jsonb),
('VG-RELY', 'feature', 'Health Dashboard: Real-time system health with 9+ monitored subsystems', 4, '{"highlight": "Health Dashboard"}'::jsonb),
('VG-RELY', 'feature', 'Scheduled Maintenance: Automated cleanup of stale data (logs, news, temp files)', 5, '{"highlight": "Scheduled Maintenance"}'::jsonb),
('VG-RELY', 'success_criterion', 'Zero downtime from single data source failures', 1, NULL),
('VG-RELY', 'success_criterion', 'Data freshness <24 hours for all tables', 2, NULL),
('VG-RELY', 'success_criterion', 'Health dashboard shows all systems green', 3, NULL),
('VG-RELY', 'success_criterion', 'Automated maintenance runs without intervention', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-UX: User Experience
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-UX', 'objective', 'Professional, responsive, delightful interface', 0, NULL),
('VG-UX', 'feature', 'Real-Time Updates: Auto-refresh with progress tracking and toast notifications', 1, '{"highlight": "Real-Time Updates"}'::jsonb),
('VG-UX', 'feature', 'Visual Analytics: Equity curves, sparklines, Fear & Greed gauge, sector allocation', 2, '{"highlight": "Visual Analytics"}'::jsonb),
('VG-UX', 'feature', 'Mobile Responsive: Full functionality on phones/tablets', 3, '{"highlight": "Mobile Responsive"}'::jsonb),
('VG-UX', 'feature', 'Theming: Dark/light modes with CSS variables', 4, '{"highlight": "Theming"}'::jsonb),
('VG-UX', 'feature', 'Accessibility: ARIA labels, keyboard navigation, screen reader support', 5, '{"highlight": "Accessibility"}'::jsonb),
('VG-UX', 'success_criterion', 'All pages mobile-responsive (tested on iPhone 12 Pro)', 1, NULL),
('VG-UX', 'success_criterion', 'WCAG AA accessibility compliance', 2, NULL),
('VG-UX', 'success_criterion', 'Page load times <2 seconds', 3, NULL),
('VG-UX', 'success_criterion', 'Real-time updates without page refresh', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;

-- VG-QUAL: Developer Velocity & Code Quality
INSERT INTO vision_goal_details (goal_code, detail_type, content, order_num, metadata) VALUES
('VG-QUAL', 'objective', 'Maintainable, testable, high-quality codebase', 0, NULL),
('VG-QUAL', 'feature', 'Test Coverage: 85%+ with 508 passing tests', 1, '{"highlight": "Test Coverage"}'::jsonb),
('VG-QUAL', 'feature', 'Type Safety: Mypy --strict compliance across all modules', 2, '{"highlight": "Type Safety"}'::jsonb),
('VG-QUAL', 'feature', 'Modular Architecture: Single-responsibility modules <500 lines', 3, '{"highlight": "Modular Architecture"}'::jsonb),
('VG-QUAL', 'feature', 'Automated Linting: Ruff + mypy in pre-commit hooks', 4, '{"highlight": "Automated Linting"}'::jsonb),
('VG-QUAL', 'feature', 'Documentation: Comprehensive docs for all major systems', 5, '{"highlight": "Documentation"}'::jsonb),
('VG-QUAL', 'success_criterion', 'All tests passing (100% pass rate)', 1, NULL),
('VG-QUAL', 'success_criterion', 'Zero mypy --strict errors', 2, NULL),
('VG-QUAL', 'success_criterion', 'All files <800 lines (hard limit)', 3, NULL),
('VG-QUAL', 'success_criterion', 'Pre-commit hooks enforce quality standards', 4, NULL)
ON CONFLICT (goal_code, detail_type, order_num) DO UPDATE SET
    content = EXCLUDED.content,
    metadata = EXCLUDED.metadata;
