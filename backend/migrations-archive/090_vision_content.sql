-- Migration 090: Create vision_content table for VISION.md narrative content
-- Stores mission statement, vision narrative, core principles, success metrics, and roadmap phases
-- Enables slash commands and UI to access full VISION.md content via API

-- Create vision_content table
CREATE TABLE IF NOT EXISTS vision_content (
    id SERIAL PRIMARY KEY,
    content_type TEXT NOT NULL,    -- 'mission', 'vision', 'principle', 'success_metric', 'roadmap_phase'
    content_key TEXT NOT NULL,     -- 'core', 'principle-1', 'phase-1', 'system', etc.
    title TEXT,                    -- Display title
    content TEXT NOT NULL,         -- Full content text
    order_num INT DEFAULT 0,       -- Display order within type
    metadata JSONB,                -- Additional structured data (bullet points, status, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (content_type, content_key)
);

-- Add comments for documentation
COMMENT ON TABLE vision_content IS 'Stores narrative content from VISION.md: mission, vision, principles, success metrics, roadmap.';
COMMENT ON COLUMN vision_content.content_type IS 'Type of content: mission, vision, principle, success_metric, roadmap_phase';
COMMENT ON COLUMN vision_content.content_key IS 'Unique key within type: core, principle-1, phase-1, system, etc.';
COMMENT ON COLUMN vision_content.metadata IS 'Additional structured data like bullet points, status, completion percentage';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_vision_content_type ON vision_content(content_type);
CREATE INDEX IF NOT EXISTS idx_vision_content_order ON vision_content(content_type, order_num);

-- ============================================================================
-- SEED DATA FROM VISION.md
-- ============================================================================

-- Mission Statement
INSERT INTO vision_content (content_type, content_key, title, content, order_num) VALUES
('mission', 'core', 'Mission Statement',
'Build a self-operating investment intelligence system that autonomously monitors markets, generates trade ideas, validates strategies through backtesting and paper trading, and presents plain-language insights—while keeping humans in the loop for final decisions.',
0)
ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    updated_at = NOW();

-- Vision Narrative
INSERT INTO vision_content (content_type, content_key, title, content, order_num, metadata) VALUES
('vision', 'what', 'What We''re Building',
'Portfolio AI is an AI-led investment intelligence platform that democratizes sophisticated market analysis by transforming complex financial data into clear, actionable insights accessible to all investors—regardless of technical expertise.

We combine the analytical power of AI agents (Claude/Gemini) with deterministic trading strategies, multi-source data redundancy, and rigorous backtesting to create a system that:

1. Thinks autonomously - Continuously monitors markets, evaluates opportunities, and generates ideas without manual intervention
2. Speaks plainly - Eliminates financial jargon and presents insights in clear, everyday language
3. Validates rigorously - Tests every strategy against historical data and tracks paper trading performance before risking real capital
4. Operates reliably - Uses multiple data sources, automated monitoring, and production-grade infrastructure to ensure 24/7 availability',
1,
'{"key_points": ["Thinks autonomously", "Speaks plainly", "Validates rigorously", "Operates reliably"]}'::jsonb),

('vision', 'why', 'Why It Matters',
'Traditional Problem:
• Expensive - Professional analysts cost thousands per year
• Complex - Financial jargon creates barriers for non-experts
• Time-consuming - Manual research takes hours daily
• Risky - Acting on untested ideas can lead to losses

Our Solution:
• Autonomous - AI agents work 24/7, no human intervention needed
• Accessible - Zero jargon, plain-language explanations anyone can understand
• Validated - Every strategy backtested and paper-traded before recommendation
• Transparent - Full visibility into AI reasoning, data sources, and performance metrics',
2,
'{"problems": ["Expensive", "Complex", "Time-consuming", "Risky"], "solutions": ["Autonomous", "Accessible", "Validated", "Transparent"]}'::jsonb)

ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    order_num = EXCLUDED.order_num,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Core Principles
INSERT INTO vision_content (content_type, content_key, title, content, order_num, metadata) VALUES
('principle', 'principle-1', 'Humans Decide, AI Advises',
'AI agents analyze markets and propose strategies, but never execute trades autonomously. Humans retain final authority on all investment decisions. AI provides reasoning and confidence scores to inform decisions, not make them.',
1,
'{"icon": "user-check", "key_points": ["Never execute trades autonomously", "Humans retain final authority", "AI provides reasoning and confidence scores"]}'::jsonb),

('principle', 'principle-2', 'Transparency Over Black Boxes',
'Every recommendation includes full rationale and supporting data. Data sources are tracked and displayed (YFinance, Polygon, etc.). AI reasoning is logged and reviewable. Performance metrics are tracked and visible.',
2,
'{"icon": "eye", "key_points": ["Full rationale included", "Data sources tracked", "AI reasoning logged", "Performance metrics visible"]}'::jsonb),

('principle', 'principle-3', 'Validate Before Execute',
'All strategies must pass backtesting before paper trading. Paper trades must show positive results before recommendation. LLM reviewers (Claude/Gemini) provide independent analysis. Disagreements between reviewers are flagged and logged.',
3,
'{"icon": "check-circle", "key_points": ["Backtesting required", "Paper trades first", "Independent LLM review", "Disagreements flagged"]}'::jsonb),

('principle', 'principle-4', 'Accessibility Without Compromise',
'Plain-language narratives with zero financial jargon. Complex analytics presented visually (charts, gauges, sparklines). Mobile-responsive design for on-the-go access. Dark/light themes and accessibility support (ARIA labels, keyboard navigation).',
4,
'{"icon": "accessibility", "key_points": ["Zero jargon", "Visual analytics", "Mobile responsive", "Accessibility support"]}'::jsonb),

('principle', 'principle-5', 'Reliability Through Redundancy',
'Multi-source data failover (6 operational sources). Automated freshness monitoring with scheduled data refreshes. PostgreSQL with connection pooling for production-grade performance. Comprehensive error handling and graceful degradation.',
5,
'{"icon": "shield", "key_points": ["Multi-source failover", "Automated freshness monitoring", "PostgreSQL with pooling", "Graceful degradation"]}'::jsonb),

('principle', 'principle-6', 'Developer Velocity & Code Quality',
'Comprehensive test coverage (85%+ target). Mypy --strict type safety compliance. Modular architecture (<500 lines per file). Automated maintenance and scheduled cleanup.',
6,
'{"icon": "code", "key_points": ["85%+ test coverage", "Mypy --strict", "Modular architecture", "Automated maintenance"]}'::jsonb)

ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    order_num = EXCLUDED.order_num,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Success Metrics
INSERT INTO vision_content (content_type, content_key, title, content, order_num, metadata) VALUES
('success_metric', 'system', 'System Performance',
'Core system reliability and performance targets.',
1,
'{"metrics": [{"name": "Uptime", "target": "99.9%", "description": "System availability"}, {"name": "Data Freshness", "target": "<24 hours", "description": "All monitored tables"}, {"name": "API Response Time", "target": "<500ms", "description": "Portfolio endpoints"}, {"name": "Test Pass Rate", "target": "100%", "description": "All 508+ tests passing"}]}'::jsonb),

('success_metric', 'ai_agent', 'AI Agent Performance',
'Autonomous operation and trading performance targets.',
2,
'{"metrics": [{"name": "Idea Generation", "target": "Daily at 03:30 UTC", "description": "Autonomous runs"}, {"name": "Backtest Success", "target": "80%+", "description": "Strategies show positive returns"}, {"name": "Paper Trade Win Rate", "target": "60%+", "description": "Simulated trades profitable"}, {"name": "LLM Agreement", "target": "<20%", "description": "Disagreement rate between reviewers"}]}'::jsonb),

('success_metric', 'ux', 'User Experience',
'Interface performance and accessibility targets.',
3,
'{"metrics": [{"name": "Page Load", "target": "<2 seconds", "description": "All pages"}, {"name": "Mobile Responsive", "target": "100%", "description": "Functionality on phones/tablets"}, {"name": "Accessibility", "target": "WCAG AA", "description": "Compliance level"}, {"name": "Error Rate", "target": "<1%", "description": "API failures"}]}'::jsonb),

('success_metric', 'quality', 'Code Quality',
'Development standards and code health targets.',
4,
'{"metrics": [{"name": "Test Coverage", "target": "85%+", "description": "Code coverage"}, {"name": "Type Safety", "target": "100%", "description": "Mypy --strict compliance"}, {"name": "File Size", "target": "0 files >800 lines", "description": "Hard limit"}, {"name": "Complexity", "target": "0 functions >100 lines", "description": "Critical threshold"}]}'::jsonb)

ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    order_num = EXCLUDED.order_num,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Roadmap Phases
INSERT INTO vision_content (content_type, content_key, title, content, order_num, metadata) VALUES
('roadmap_phase', 'phase-1', 'Phase 1: Foundation & Core Trading',
'MVP features including portfolio, watchlist, agents, PostgreSQL, and multi-source data infrastructure.',
1,
'{"status": "complete", "icon": "check-circle", "features": ["Portfolio tracking", "Watchlist management", "Trading agents", "PostgreSQL database", "Multi-source data"]}'::jsonb),

('roadmap_phase', 'phase-2', 'Phase 2: Narrative Intelligence',
'Signal classification, trading styles, and plain-language insights for all positions.',
2,
'{"status": "complete", "icon": "check-circle", "features": ["Signal classification", "Trading style detection", "Plain-language insights", "Confidence scoring"]}'::jsonb),

('roadmap_phase', 'phase-3', 'Phase 3: Autonomous Trading MVP',
'Backtesting, paper trading, and multi-agent collaboration for strategy validation.',
3,
'{"status": "complete", "icon": "check-circle", "features": ["Backtesting engine", "Paper trading", "Multi-agent collaboration", "Strategy validation"]}'::jsonb),

('roadmap_phase', 'phase-4', 'Phase 4: Production Readiness',
'Validation systems, deployment automation, and git workflow integration.',
4,
'{"status": "in_progress", "icon": "loader", "features": ["Feature validation", "Deployment automation", "Git automation", "Production monitoring"]}'::jsonb),

('roadmap_phase', 'phase-5', 'Phase 5: Intelligence Layer Phase 2',
'Sentiment scoring, fundamental data integration, and advanced AI summaries.',
5,
'{"status": "planned", "icon": "calendar", "features": ["Sentiment scoring", "Fundamental data", "AI summaries", "Advanced analytics"]}'::jsonb)

ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    order_num = EXCLUDED.order_num,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Principles in Practice (examples)
INSERT INTO vision_content (content_type, content_key, title, content, order_num, metadata) VALUES
('example', 'news-sentiment', 'Example: News Sentiment Analysis',
'How we transform raw news into actionable intelligence.

❌ Old Approach: Display raw news headlines, expect users to interpret sentiment themselves

✅ Our Approach:
1. Fetch news from multiple sources (Google News RSS)
2. Run VADER sentiment analysis (-1.0 to +1.0)
3. Classify as Positive/Neutral/Negative with plain-language labels
4. Generate AI insight: "Recent positive earnings beat drove 8% gain - watch for pullback"
5. Show data source and timestamp for transparency
6. Update automatically on schedule (6-hour cache TTL)',
1,
'{"principles_applied": ["Transparency Over Black Boxes", "Accessibility Without Compromise", "Reliability Through Redundancy"]}'::jsonb),

('example', 'backtesting', 'Example: Backtesting a Strategy',
'How we validate strategies before recommending them.

❌ Old Approach: Implement strategy in production, learn from losses

✅ Our Approach:
1. Define deterministic strategy (BUY signal: price > EMA-20, RSI 30-70, MACD > 0)
2. Backtest against 252 days of historical data
3. Calculate performance: Sharpe ratio, max drawdown, win rate, total return
4. Generate equity curve visualization
5. Only proceed to paper trading if backtest shows positive results
6. Track paper trade performance before any recommendation',
2,
'{"principles_applied": ["Validate Before Execute", "Humans Decide, AI Advises", "Transparency Over Black Boxes"]}'::jsonb)

ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    order_num = EXCLUDED.order_num,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Closing Statement
INSERT INTO vision_content (content_type, content_key, title, content, order_num) VALUES
('closing', 'north-star', 'Our North Star',
'Portfolio AI represents a fundamental shift in how individual investors approach markets: from manual research and guesswork to automated intelligence and validated strategies. By combining the analytical power of AI with rigorous backtesting, transparent reasoning, and plain-language communication, we aim to level the playing field between retail investors and professionals.

Every investor deserves sophisticated analysis, delivered clearly, validated rigorously, and available 24/7.',
0)
ON CONFLICT (content_type, content_key) DO UPDATE SET
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    updated_at = NOW();
