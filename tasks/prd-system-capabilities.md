# PRD: System Capabilities Registry (Three-Phase Intelligence)

**Created**: 2025-11-13
**Status**: Planning
**Priority**: P0 - Critical Infrastructure
**Estimated Effort**: 20-24 hours (with parallel agents: 10-12 hours)

---

## Executive Summary

Build an intelligent, self-updating registry of system capabilities that:
1. **Auto-discovers** data sources (DB tables, Celery tasks, API endpoints)
2. **AI analyzes** completeness, freshness, and gaps
3. **Human reviews** and adds strategic context

**Purpose**: Prevent AI agents from breaking features due to incomplete context by providing a queryable knowledge base of system capabilities, data quality, and dependencies.

---

## Problem Statement

**Current Issues**:
- 🚨 AI agents break features when context resets (forget what data exists, how it's connected)
- 🚨 Data quality issues go undetected (Fear & Greed 3 days stale, 4/5 fields NULL)
- 🚨 No visibility into what data we have vs. need (missing earnings, analyst ratings)
- 🚨 Manual documentation becomes stale and inconsistent

**Impact on Trading**:
- Cannot make informed decisions with incomplete/stale data
- AI advisor gives bad recommendations based on missing context
- Time wasted debugging issues that should be auto-detected

---

## Solution Overview

### Three-Phase Approach

**Phase 1: Automated Data Gathering (Scripts)**
- Scan database tables (row counts, columns, field completeness, date ranges)
- Scan Celery scheduled tasks (schedules, last run, success rates)
- Scan API endpoints (paths, response times, error rates)
- Store raw facts in normalized tables

**Phase 2: AI Analysis & Insights (Automated Agent)**
- AI reviews Phase 1 data + logs + existing task files
- Identifies: data quality issues, stale data, missing capabilities, broken dependencies
- Generates insights with severity, impact, suggested fixes
- Stores findings in `capability_insights` table

**Phase 3: Human Review & Strategic Notes**
- User reviews AI insights, confirms/dismisses findings
- Adds strategic context: priorities, tradeoffs, domain knowledge
- Documents "why" decisions (defer to Phase 4, not trading options yet)
- AI references these notes during future refactoring

---

## Detailed Requirements

### 1. Database Schema

#### 1.1 Core Capability Tables (Phase 1 Auto-Discovery)

**Table: `db_capabilities`**
```sql
CREATE TABLE db_capabilities (
  id SERIAL PRIMARY KEY,
  table_name TEXT UNIQUE NOT NULL,
  category TEXT,  -- market_data, news, portfolio, analytics, infrastructure
  row_count INTEGER,
  total_columns INTEGER,
  columns JSONB,  -- Array of all column names
  columns_with_data JSONB,  -- Columns with non-NULL values (any row)
  columns_mostly_null JSONB,  -- Columns >80% NULL
  completeness_pct INTEGER,  -- (columns_with_data / total_columns) * 100
  date_range_start DATE,  -- MIN(created_at/updated_at/as_of_date)
  date_range_end DATE,    -- MAX(created_at/updated_at/as_of_date)
  expected_freshness TEXT,  -- From config: "daily", "hourly", "real-time", "on-demand"
  days_since_update INTEGER,  -- (TODAY - date_range_end)
  freshness_status TEXT,  -- "current", "acceptable", "stale", "critical"
  last_scanned_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_db_capabilities_category ON db_capabilities(category);
CREATE INDEX idx_db_capabilities_freshness ON db_capabilities(freshness_status);
```

**Table: `celery_capabilities`**
```sql
CREATE TABLE celery_capabilities (
  id SERIAL PRIMARY KEY,
  task_name TEXT UNIQUE NOT NULL,
  category TEXT,  -- market_data, news, portfolio, analytics, infrastructure
  task_path TEXT,  -- File path: app/tasks/market_data_tasks.py
  function_name TEXT,  -- Python function name
  schedule_description TEXT,  -- Human-readable: "Every 60 seconds"
  schedule_crontab TEXT,  -- Cron format: "*/60 * * * *"
  schedule_interval_seconds INTEGER,  -- Numeric interval for sorting
  last_run_at TIMESTAMP,
  next_run_at TIMESTAMP,
  success_count_7d INTEGER DEFAULT 0,
  failure_count_7d INTEGER DEFAULT 0,
  success_rate_pct INTEGER,  -- (success / (success + failure)) * 100
  avg_duration_ms INTEGER,
  max_duration_ms INTEGER,
  populates_tables JSONB,  -- Array of table names this task writes to
  depends_on_tasks JSONB,  -- Array of task names this depends on
  last_scanned_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_celery_capabilities_category ON celery_capabilities(category);
CREATE INDEX idx_celery_capabilities_success_rate ON celery_capabilities(success_rate_pct);
```

**Table: `api_capabilities`**
```sql
CREATE TABLE api_capabilities (
  id SERIAL PRIMARY KEY,
  endpoint_path TEXT NOT NULL,
  http_method TEXT NOT NULL,  -- GET, POST, PUT, DELETE
  category TEXT,
  route_file TEXT,  -- File path: app/routes/watchlist.py
  function_name TEXT,  -- Python function name
  depends_on_tables JSONB,  -- Tables this endpoint reads from
  avg_response_time_ms INTEGER,
  p95_response_time_ms INTEGER,
  p99_response_time_ms INTEGER,
  error_rate_pct DECIMAL(5,2),
  last_7d_request_count INTEGER,
  last_scanned_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(endpoint_path, http_method)
);

CREATE INDEX idx_api_capabilities_category ON api_capabilities(category);
```

#### 1.2 AI Insights Table (Phase 2 Analysis)

**Table: `capability_insights`**
```sql
CREATE TABLE capability_insights (
  id SERIAL PRIMARY KEY,
  capability_type TEXT NOT NULL,  -- 'db', 'celery', 'api', 'missing'
  capability_id INTEGER,  -- FK to respective table, NULL if capability doesn't exist
  table_name TEXT,  -- For quick reference (denormalized)
  insight_type TEXT NOT NULL,  -- data_quality, freshness, missing_data, missing_capability, broken_dependency, performance
  severity TEXT NOT NULL,  -- critical, high, medium, low
  finding TEXT NOT NULL,  -- What's wrong (concise, 1-2 sentences)
  expected_behavior TEXT,  -- What should happen
  actual_behavior TEXT,  -- What's actually happening
  impact TEXT,  -- Why this matters for trading/business
  suggested_fix TEXT,  -- Specific action with file/line references
  references JSONB,  -- {files: [...], tables: [...], tasks: [...], urls: [...]}
  ai_model TEXT,  -- Which AI generated this: "claude-sonnet-4.5", "gemini-2.0"
  ai_confidence DECIMAL(3,2),  -- 0.00-1.00
  status TEXT DEFAULT 'pending',  -- pending, confirmed, dismissed, in_progress, fixed
  status_reason TEXT,  -- Why confirmed/dismissed (from human review)
  generated_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP,
  reviewed_by TEXT,
  fixed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_insights_capability ON capability_insights(capability_type, capability_id);
CREATE INDEX idx_insights_status ON capability_insights(status);
CREATE INDEX idx_insights_severity ON capability_insights(severity);
```

#### 1.3 Human Notes Table (Phase 3 Strategic Context)

**Table: `capability_notes`**
```sql
CREATE TABLE capability_notes (
  id SERIAL PRIMARY KEY,
  capability_type TEXT NOT NULL,  -- 'db', 'celery', 'api', 'general'
  capability_id INTEGER,  -- FK to respective table
  insight_id INTEGER,  -- Reference to specific AI insight (optional)
  note_type TEXT NOT NULL,  -- purpose, gap_justification, priority, strategic_context, verification, known_issue
  note TEXT NOT NULL,
  created_by TEXT NOT NULL,  -- 'human' or AI agent identifier
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (insight_id) REFERENCES capability_insights(id) ON DELETE SET NULL
);

CREATE INDEX idx_notes_capability ON capability_notes(capability_type, capability_id);
CREATE INDEX idx_notes_insight ON capability_notes(insight_id);
```

---

### 2. Configuration System

**File: `backend/app/config/capabilities_config.yaml`**

```yaml
scan_config:
  # Global settings
  enabled: true
  scan_schedule: "daily at 03:00 UTC"  # After data refresh tasks

  # What to scan
  targets:
    database:
      enabled: true
      track_field_completeness: true
      track_freshness: true
      null_threshold_pct: 80  # Column is "mostly null" if >80% NULL

      # Expected freshness per table
      expected_freshness:
        fear_greed_daily: "daily"
        fear_greed_inputs: "daily"
        news_cache: "hourly"
        news_summary_log: "hourly"
        watchlist_snapshots: "60s"
        watchlist_items: "on-demand"
        portfolio_positions: "on-demand"
        market_data: "daily"
        day_bars: "daily"
        technical_indicators: "daily"
        reference_cache: "weekly"

    celery:
      enabled: true
      track_success_rate: true
      track_duration: true
      lookback_days: 7
      min_success_rate_pct: 95  # Warn if below
      max_duration_warn_ms: 30000  # 30 seconds

    api:
      enabled: true  # Set to false for Phase 1 if not ready
      track_response_times: true
      track_error_rates: true
      lookback_days: 7
      max_p95_warn_ms: 1000
      max_error_rate_warn_pct: 5.0

  # AI Analysis settings
  ai_analysis:
    enabled: true  # Set to false to skip Phase 2
    model: "claude-sonnet-4.5"  # or "gemini-2.0-flash"
    confidence_threshold: 0.70  # Only store insights with confidence >= 0.70
    include_logs: true
    log_lookback_hours: 24
    include_task_files: true
    task_files_path: "tasks/"

categorization:
  # How to categorize tables/tasks by name pattern
  market_data:
    patterns: ["market_data", "ticker", "ohlcv", "day_bars", "minute_bars", "price_cache"]
  news:
    patterns: ["news", "article", "sentiment"]
  portfolio:
    patterns: ["portfolio", "holding", "watchlist", "position"]
  analytics:
    patterns: ["fear_greed", "technical_indicator", "ml_", "agent_"]
  infrastructure:
    patterns: ["user", "auth", "schema_migration", "celery_", "maintenance"]
```

---

### 3. Scanning Scripts

#### 3.1 Main Scanner (Config-Driven)

**File: `backend/scripts/scan_capabilities.py`**

Functions:
- `load_config()` - Load YAML config
- `scan_database_capabilities(config)` - Scan DB tables, populate `db_capabilities`
- `scan_celery_capabilities(config)` - Scan Celery tasks, populate `celery_capabilities`
- `scan_api_capabilities(config)` - Scan API endpoints, populate `api_capabilities`
- `calculate_freshness_status(table_name, days_since_update, expected)` - Categorize freshness
- `save_capabilities(results)` - Insert/update capability tables
- `main()` - Orchestrate all scans

**Behavior**:
- Run independently (CLI) or as Celery task
- Idempotent: Can run multiple times safely
- Upsert logic: Update existing rows, insert new
- Change detection: Log what's NEW/CHANGED/REMOVED since last scan

---

#### 3.2 Database Scanner Details

**What to detect**:
- Table name
- Row count (`SELECT COUNT(*) FROM table`)
- Column names (`INFORMATION_SCHEMA.COLUMNS`)
- Columns with data (check if any row has non-NULL value)
- Columns mostly NULL (>80% NULL via sampling or `COUNT(column) / COUNT(*)`)
- Date range (MIN/MAX of `created_at`, `updated_at`, `as_of_date`, `date` columns)
- Category (match table name against config patterns)

**Example SQL**:
```sql
-- Get columns with NULL percentage
SELECT
  column_name,
  COUNT(*) as total_rows,
  COUNT(column_name) as non_null_rows,
  (COUNT(*) - COUNT(column_name)) * 100.0 / COUNT(*) as null_pct
FROM table_name
GROUP BY column_name;
```

---

#### 3.3 Celery Scanner Details

**What to detect**:
- Task name (from `celery_app.conf.beat_schedule`)
- Schedule (crontab or interval)
- Task path (import path from `task` key)
- Last run (query `celery_taskmeta` table if using DB backend)
- Success/failure counts (parse `celery_taskmeta.status` for last 7 days)
- Duration (parse `celery_taskmeta.runtime` or task result metadata)
- Populates tables (parse task code for `INSERT`/`UPDATE` statements - basic regex scan)

**Note**: Celery task metadata only available if using DB backend. May need to parse log files otherwise.

---

#### 3.4 API Scanner Details

**What to detect**:
- Endpoint paths (scan `app/routes/*.py` files for `@router.get/post/put/delete`)
- HTTP method
- Route file + function name
- Dependencies (basic: scan function body for `SELECT ... FROM table` patterns)
- Performance metrics (if we add request logging middleware - Phase 2 enhancement)

**Initial approach**: Static file scanning (regex)
**Future enhancement**: Add FastAPI middleware to track actual request metrics

---

### 4. AI Analysis Agent

#### 4.1 Celery Task

**File: `backend/app/tasks/capability_analysis_tasks.py`**

```python
@celery_app.task(name="analyze_capabilities", bind=True)
def analyze_capabilities(self):
    """Run AI analysis on capability data to generate insights.

    Runs: Daily at 03:15 UTC (15 min after capability scan)

    Steps:
      1. Load all capability data (db, celery, api)
      2. Load recent error logs (last 24h)
      3. Load task files (tasks/*.md)
      4. Build context prompt for AI
      5. Call Claude/Gemini API
      6. Parse AI response
      7. Store insights in capability_insights table
      8. Log summary stats
    """
    from app.services.ai_analyzer import CapabilityAnalyzer

    analyzer = CapabilityAnalyzer()
    insights = analyzer.analyze()

    # Store insights
    storage = get_storage()
    with storage.connection() as conn:
        for insight in insights:
            conn.execute("""
                INSERT INTO capability_insights
                (capability_type, capability_id, insight_type, severity,
                 finding, expected_behavior, impact, suggested_fix,
                 references, ai_model, ai_confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (capability_type, capability_id, insight_type)
                DO UPDATE SET
                  finding = EXCLUDED.finding,
                  severity = EXCLUDED.severity,
                  updated_at = NOW()
            """, (...))

    logger.info("ai_analysis_complete", insights_generated=len(insights))
```

#### 4.2 AI Analyzer Service

**File: `backend/app/services/ai_analyzer.py`**

**Class: `CapabilityAnalyzer`**

Methods:
- `analyze()` - Main entry point
- `load_capabilities()` - Fetch all capability data from DB
- `load_error_logs(hours=24)` - Get recent errors
- `load_task_files()` - Read tasks/*.md files
- `build_prompt()` - Construct AI prompt with context
- `call_ai_api(prompt)` - Call Claude or Gemini
- `parse_ai_response(response)` - Extract structured insights from AI output
- `validate_insights(insights)` - Check confidence threshold, required fields

**AI Prompt Template**:
```
You are a senior data engineer and market data analyst reviewing a trading platform's infrastructure.

CONTEXT:
You have access to the complete system capabilities registry including:

DATABASE TABLES ({num_tables} total):
{db_capabilities_json}

CELERY SCHEDULED TASKS ({num_tasks} total):
{celery_capabilities_json}

API ENDPOINTS ({num_endpoints} total):
{api_capabilities_json}

RECENT ERROR LOGS (last 24 hours):
{error_logs}

EXISTING TASK FILES (known issues):
{task_files_content}

TASK:
Analyze the system and identify:

1. DATA QUALITY ISSUES
   - Tables with incomplete data (many NULL columns)
   - Fields that should be populated but aren't
   - Data type mismatches or invalid values

2. FRESHNESS ISSUES
   - Stale data (expected daily, but 3+ days old)
   - Tasks not running on schedule
   - Date ranges that haven't updated recently

3. MISSING CAPABILITIES
   - Data sources that should exist but don't (e.g., earnings calendar, analyst ratings)
   - Why they're needed for trading decisions
   - Impact on AI advisor accuracy

4. BROKEN DEPENDENCIES
   - Tasks that write to tables but haven't run
   - Tables referenced by APIs but empty
   - Circular dependencies or missing prerequisites

5. PERFORMANCE ISSUES
   - Tasks taking too long (>30s)
   - API endpoints with high error rates
   - Tables growing too large (>1M rows without partitioning)

OUTPUT FORMAT (JSON):
Return an array of insight objects:

[
  {
    "capability_type": "db" | "celery" | "api" | "missing",
    "capability_id": <id from respective table, null if missing>,
    "table_name": "<table name for reference>",
    "insight_type": "data_quality" | "freshness" | "missing_data" | "missing_capability" | "broken_dependency" | "performance",
    "severity": "critical" | "high" | "medium" | "low",
    "finding": "<concise description, 1-2 sentences>",
    "expected_behavior": "<what should happen>",
    "actual_behavior": "<what's actually happening>",
    "impact": "<why this matters for trading/business>",
    "suggested_fix": "<specific action with file paths and line numbers if applicable>",
    "references": {
      "files": ["backend/app/tasks/indicator_tasks.py:221"],
      "tables": ["fear_greed_components", "day_bars"],
      "tasks": ["calculate_fear_greed"],
      "urls": []
    },
    "ai_confidence": 0.95
  },
  ...
]

GUIDELINES:
- Be specific: Reference actual table names, column names, file paths
- Prioritize severity: critical = blocking trading decisions, high = limits functionality, medium = nice to have, low = minor
- Provide actionable fixes: Not "fix the data" but "Check why VIX data not flowing from day_bars to fear_greed_inputs"
- Include confidence: 1.0 = certain (verified from logs/code), 0.8 = high confidence, 0.5 = educated guess
- Focus on trading impact: How does this affect investment decisions?

Begin analysis:
```

**AI Response Parsing**:
- Expect JSON array of insights
- Validate schema (required fields present)
- Filter by confidence threshold (>= 0.70)
- Deduplicate similar insights
- Store in `capability_insights` table

---

### 5. API Endpoints

**File: `backend/app/routes/capabilities.py`**

#### 5.1 Capability Queries

```python
GET /api/capabilities
Query params:
  - type: db | celery | api | all (default: all)
  - category: market_data | news | portfolio | analytics | infrastructure
  - status: current | stale | critical (for DB freshness)
  - limit, offset (pagination)

Response:
{
  "total": 48,
  "capabilities": [
    {
      "type": "db",
      "id": 12,
      "table_name": "fear_greed_components",
      "category": "analytics",
      "row_count": 5,
      "completeness_pct": 43,
      "columns_null": ["vix_close", "spy_close", "rsi_14", "breadth_pct"],
      "date_range": "2025-11-07 to 2025-11-11",
      "freshness_status": "stale",
      "days_since_update": 3
    },
    ...
  ]
}
```

```python
GET /api/capabilities/{type}/{id}
Response:
{
  "capability": { ... },
  "insights": [ ... ],  # Related AI insights
  "notes": [ ... ],     # Human notes
  "dependencies": {
    "populated_by": ["calculate_fear_greed task"],
    "used_by": ["Dashboard Fear & Greed widget"]
  }
}
```

```python
GET /api/capabilities/dependencies
Query params:
  - table: <table_name>
  - task: <task_name>

Response:
{
  "depends_on": [
    {"type": "db", "name": "day_bars"},
    {"type": "celery", "name": "refresh_daily_ohlcv"}
  ],
  "used_by": [
    {"type": "api", "name": "GET /api/market/intelligence"},
    {"type": "ui", "name": "Dashboard Fear & Greed Widget"}
  ]
}
```

#### 5.2 AI Insights Queries

```python
GET /api/capabilities/insights
Query params:
  - status: pending | confirmed | dismissed | fixed
  - severity: critical | high | medium | low
  - type: data_quality | freshness | missing_data | missing_capability
  - limit, offset

Response:
{
  "total": 17,
  "insights": [
    {
      "id": 42,
      "capability_type": "db",
      "table_name": "fear_greed_components",
      "insight_type": "data_quality",
      "severity": "critical",
      "finding": "Only 1 of 5 required fields populated (20% complete)",
      "impact": "Fear & Greed Index unreliable - only using Put/Call ratio",
      "suggested_fix": "Check why VIX/SPY data not flowing from day_bars → fear_greed_inputs",
      "status": "pending",
      "ai_confidence": 0.95
    },
    ...
  ]
}
```

```python
POST /api/capabilities/insights/{id}/review
Body:
{
  "status": "confirmed" | "dismissed" | "in_progress",
  "status_reason": "CONFIRMED - VIX symbol is '^VIX' not 'VIX'. Priority: P0",
  "reviewed_by": "user_id"
}

Response: { "success": true }
```

#### 5.3 Notes Management

```python
POST /api/capabilities/notes
Body:
{
  "capability_type": "db",
  "capability_id": 12,
  "insight_id": 42,  // optional
  "note_type": "strategic_context",
  "note": "Fix before Phase 2 - blocks all analytics"
}

Response: { "id": 123, "created_at": "..." }
```

```python
GET /api/capabilities/notes
Query params:
  - capability_type, capability_id
  - insight_id

Response: { "notes": [ ... ] }
```

---

### 6. User Interface

#### 6.1 Main Capabilities Page

**Route**: `/capabilities`

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ System Capabilities                Last Scan: 5 min ago     │
│ [🔄 Refresh] [📊 View: All ▾] [🔍 Search]         48 items │
└─────────────────────────────────────────────────────────────┘

Tabs:
[ Overview ] [ Database ] [ Tasks ] [ APIs ] [ AI Insights ] [ Gaps ]

DATABASE (30 items) - Showing stale/incomplete only
┌─────────────────────────────────────────────────────────────┐
│ 🔴 fear_greed_components                                    │
│ Analytics · 5 rows, Nov 7-11 (3 days old)                  │
│ ⚠️  43% complete · 4/5 fields NULL                         │
│ 2 AI insights (1 critical, 1 high)                         │
│ [View Details] [Add Note]                                  │
├─────────────────────────────────────────────────────────────┤
│ ⚠️  reference_cache                                         │
│ Market Data · 126 rows, Nov 2-13                           │
│ ⚠️  67% complete · Valuation fields NULL                   │
│ 1 AI insight (high)                                        │
│ [View Details] [Add Note]                                  │
└─────────────────────────────────────────────────────────────┘

CELERY TASKS (11 items) - Showing issues only
┌─────────────────────────────────────────────────────────────┐
│ ⚠️  calculate_fear_greed                                    │
│ Analytics · Daily at 04:00 UTC                             │
│ Last run: 3 days ago (Nov 10)                              │
│ Success rate: 100% (3/3 runs, 7d window)                   │
│ 1 AI insight (critical - not running on schedule)         │
│ [View Details] [Trigger Manually]                         │
└─────────────────────────────────────────────────────────────┘
```

#### 6.2 Detail View (Modal or Side Panel)

```
┌─────────────────────────────────────────────────────────────┐
│ fear_greed_components (Database Table)                 [✕] │
├─────────────────────────────────────────────────────────────┤
│ Category: Analytics                                         │
│ Row Count: 5                                                │
│ Date Range: Nov 7-11, 2025 (3 days old) 🔴 STALE          │
│ Completeness: 43% (3/7 fields populated)                   │
│                                                             │
│ Columns:                                                    │
│   ✅ id, as_of_date, put_call_ratio                        │
│   ❌ vix_close, spy_close, rsi_14, breadth_pct            │
│                                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ AI INSIGHTS (2)                                             │
│                                                             │
│ 🔴 CRITICAL - Data Quality                                 │
│ Finding: Only 1/5 required fields populated (20% complete) │
│ Impact: Fear & Greed unreliable, trading signals wrong     │
│ Fix: Check VIX/SPY flow (indicator_tasks.py:221)          │
│ Confidence: 95%                                            │
│                                                             │
│ Status: Pending Review                                     │
│ [✓ Confirm] [✗ Dismiss] [💬 Add Note]                     │
│                                                             │
│ 🔴 CRITICAL - Freshness                                    │
│ Finding: Data 3 days stale (expected: daily updates)       │
│ Impact: Dashboard shows outdated sentiment                 │
│ Fix: Celery task calculate_fear_greed not running         │
│ Confidence: 100%                                           │
│                                                             │
│ Status: Pending Review                                     │
│ [✓ Confirm] [✗ Dismiss] [💬 Add Note]                     │
│                                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ HUMAN NOTES (1)                                             │
│                                                             │
│ 📝 Strategic Context (You, 2025-11-13)                     │
│ CONFIRMED - VIX symbol is '^VIX' not 'VIX'. Also need to   │
│ implement breadth calculation using sector ETFs. Priority:  │
│ P0 - fix before Phase 2 (blocks all analytics).            │
│                                                             │
│ [Edit] [Delete]                                             │
│                                                             │
│ [+ Add Note]                                                │
│                                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ DEPENDENCIES                                                │
│                                                             │
│ Populated by:                                               │
│   • calculate_fear_greed task (celery)                     │
│                                                             │
│ Used by:                                                    │
│   • Dashboard Fear & Greed widget (UI)                     │
│   • GET /api/market/intelligence (API)                     │
│                                                             │
│                                        [Close]              │
└─────────────────────────────────────────────────────────────┘
```

#### 6.3 AI Insights Tab

```
AI INSIGHTS
[View: Pending ▾] [Severity: All ▾] [Type: All ▾]

🔴 CRITICAL (5)
┌─────────────────────────────────────────────────────────────┐
│ Fear & Greed Components - Data Quality                     │
│ Only 1/5 fields populated → Unreliable index               │
│ [✓ Confirm & Add to Sprint] [✗ Dismiss]                   │
├─────────────────────────────────────────────────────────────┤
│ Fear & Greed Components - Freshness                        │
│ 3 days stale → Trading on outdated sentiment               │
│ [✓ Confirm & Add to Sprint] [✗ Dismiss]                   │
└─────────────────────────────────────────────────────────────┘

⚠️  HIGH (12)
┌─────────────────────────────────────────────────────────────┐
│ Missing Capability: Earnings Calendar                       │
│ No earnings dates → Can't avoid volatility windows          │
│ [✓ Agree - Add to Phase 2] [✗ Not Needed]                 │
├─────────────────────────────────────────────────────────────┤
│ Missing Capability: Analyst Ratings                         │
│ No price targets → Missing institutional sentiment          │
│ [✓ Agree - Add to Phase 2] [✗ Not Needed]                 │
└─────────────────────────────────────────────────────────────┘

📊 MEDIUM (8) ...
```

#### 6.4 Gaps Tab (Missing Capabilities)

```
MISSING CAPABILITIES (AI-Identified Gaps)

🔵 MARKET DATA (3 missing)
┌─────────────────────────────────────────────────────────────┐
│ Earnings Calendar                                           │
│ Why needed: Predict volatility windows, avoid earnings plays│
│ Impact: Risk entering positions 1 day before earnings       │
│ Priority: HIGH                                              │
│ [+ Add to Roadmap] [Dismiss - Not Trading This]           │
├─────────────────────────────────────────────────────────────┤
│ Analyst Ratings & Price Targets                            │
│ Why needed: Gauge institutional sentiment, find catalysts   │
│ Impact: Missing sell-side consensus for stock selection     │
│ Priority: HIGH                                              │
│ [+ Add to Roadmap] [Dismiss]                               │
└─────────────────────────────────────────────────────────────┘

📈 PORTFOLIO (2 missing)
┌─────────────────────────────────────────────────────────────┐
│ Transaction History / Ledger                                │
│ Why needed: Track P&L, tax lots, performance attribution    │
│ Impact: Cannot measure strategy success, tax reporting hard │
│ Priority: MEDIUM                                            │
│ [+ Add to Roadmap] [Dismiss]                               │
└─────────────────────────────────────────────────────────────┘
```

---

### 7. Integration Points

#### 7.1 Celery Beat Schedule

**File: `backend/app/celery_app.py`**

Add to `beat_schedule`:
```python
# System Capabilities Scanning
'scan-system-capabilities': {
    'task': 'scan_system_capabilities',
    'schedule': crontab(hour=3, minute=0),  # Daily at 03:00 UTC
},

# AI Analysis of Capabilities
'analyze-capabilities': {
    'task': 'analyze_capabilities',
    'schedule': crontab(hour=3, minute=15),  # 15 min after scan
},
```

#### 7.2 AI Agent Integration

**When AI agent (Claude Code) starts refactoring**:

1. Query capabilities API: `GET /api/capabilities?type=db&table=fear_greed_components`
2. Check AI insights: `GET /api/capabilities/insights?table=fear_greed_components`
3. Read human notes: `GET /api/capabilities/notes?capability_type=db&table=fear_greed_components`
4. Proceed with full context of what's broken, why, and strategic priorities

**Example in CLAUDE.md**:
```markdown
### Before Refactoring Checklist

1. Query System Capabilities API for affected tables/tasks
2. Review AI insights for known issues
3. Read human notes for strategic context
4. Check dependencies (what breaks if I change this?)
5. Verify expected behavior vs. actual behavior
6. Only then proceed with changes
```

---

### 8. Testing Strategy

#### 8.1 Unit Tests

**File: `backend/tests/unit/test_capability_scanner.py`**

Test cases:
- Scan database tables (mock DB queries)
- Detect NULL columns correctly
- Calculate completeness percentage
- Categorize tables by name patterns
- Calculate freshness status (current/stale/critical)
- Scan Celery tasks from beat_schedule
- Parse schedule into human-readable format
- Handle missing columns gracefully

#### 8.2 Integration Tests

**File: `backend/tests/integration/test_capabilities_api.py`**

Test cases:
- Full scan populates all capability tables
- API returns correct data
- Filtering by category works
- Pagination works
- Notes CRUD operations
- Insights review workflow (confirm/dismiss)
- Change detection (new tables, removed tables)

#### 8.3 AI Analysis Tests

**File: `backend/tests/unit/test_ai_analyzer.py`**

Test cases:
- Build prompt with all context
- Parse AI JSON response
- Validate insight schema
- Filter by confidence threshold
- Deduplicate similar insights
- Handle AI API errors gracefully

---

### 9. Success Criteria

#### Phase 1: Auto-Discovery (MVP)
- ✅ Scan script discovers all DB tables, Celery tasks, API endpoints
- ✅ Data stored in normalized tables (db_capabilities, celery_capabilities, api_capabilities)
- ✅ UI displays capabilities grouped by category
- ✅ API endpoints for querying capabilities
- ✅ Manual scan trigger works
- ✅ Scheduled daily scan runs successfully

#### Phase 2: AI Analysis
- ✅ AI agent runs daily after capability scan
- ✅ Generates insights with severity, impact, suggested fixes
- ✅ Insights stored in capability_insights table
- ✅ UI shows AI insights grouped by severity
- ✅ Can confirm/dismiss insights
- ✅ Detects actual bugs (e.g., Fear & Greed 4/5 fields NULL)

#### Phase 3: Human Review
- ✅ Can add notes to capabilities and insights
- ✅ Notes stored in capability_notes table
- ✅ UI displays notes alongside AI insights
- ✅ AI agents query notes before refactoring
- ✅ Strategic context preserved across sessions

---

### 10. Implementation Plan

#### Task Breakdown (via /task_it)

**Phase 1: Foundation (Tasks 0-6)**
- Task 0: Database schema + migrations
- Task 1: Config system (YAML)
- Task 2: Database scanner
- Task 3: Celery scanner
- Task 4: API scanner (optional for v1)
- Task 5: Main scan script + Celery task
- Task 6: Basic API endpoints

**Phase 2: AI Analysis (Tasks 7-10)**
- Task 7: AI analyzer service (prompt building)
- Task 8: AI API integration (Claude/Gemini)
- Task 9: Insight parsing + storage
- Task 10: AI analysis Celery task

**Phase 3: UI (Tasks 11-14)**
- Task 11: Capabilities list page (overview)
- Task 12: Detail view (modal/panel)
- Task 13: AI insights tab
- Task 14: Notes management UI

**Phase 4: Integration & Testing (Tasks 15-17)**
- Task 15: Add to Celery beat schedule
- Task 16: Write tests (unit + integration)
- Task 17: Documentation + AI agent integration guide

---

### 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI API costs high | Medium | Medium | Cache AI results for 24h, only re-analyze on changes |
| AI generates noise (false positives) | High | Medium | Confidence threshold (0.70), human review required |
| Scanning slows down system | Low | Low | Run at 03:00 UTC (low traffic), limit to read-only queries |
| Config becomes complex | Medium | Low | Start simple (20 tables), expand as needed |
| Users ignore AI insights | Medium | High | Surface critical insights on dashboard homepage |

---

### 12. Future Enhancements (Out of Scope for v1)

- Real-time monitoring (detect issues within 5 min of occurrence)
- Automated fixing (AI generates PRs for simple fixes)
- Dependency graph visualization (D3.js network graph)
- Historical tracking (trend analysis: "data quality improving/degrading?")
- Alerting (Slack/email when critical insight detected)
- Multi-tenancy (different configs per environment: dev/staging/prod)

---

## Estimated Effort

**Total**: 20-24 hours (sequential)
**With Parallel Agents**: 10-12 hours

**Breakdown**:
- Phase 1 (Foundation): 8-10 hours (3 agents in parallel: 4-5 hours)
- Phase 2 (AI Analysis): 4-6 hours (1 agent: 4-6 hours)
- Phase 3 (UI): 6-8 hours (2 agents in parallel: 3-4 hours)
- Integration & Testing: 2-4 hours (1 agent: 2-4 hours)

**Dependencies**: None (clean slate, no blocking tasks)

---

## Acceptance Criteria

### For Product Owner Review

**Scenario 1**: Fear & Greed data is stale
- ✅ AI detects "fear_greed_components is 3 days old, expected: daily"
- ✅ Insight shows severity: CRITICAL
- ✅ Suggested fix: "Check calculate_fear_greed task schedule"
- ✅ User confirms insight, adds note: "P0 - fix before Phase 2"

**Scenario 2**: Adding new data source
- ✅ Add `earnings_calendar` table
- ✅ Next scan detects new table automatically
- ✅ AI suggests: "Populate with yfinance earnings_dates"
- ✅ User adds note: "Phase 2 priority, use yfinance free tier"

**Scenario 3**: AI agent refactoring
- ✅ Claude Code queries capabilities API before changes
- ✅ Sees "fear_greed_components has 4/5 fields NULL"
- ✅ Reads human note: "VIX symbol is '^VIX' not 'VIX'"
- ✅ Fixes symbol, verifies all 5 fields populate
- ✅ Updates note: "FIXED - all components now working"

---

**Ready for /task_it execution.**
