# Data Architecture & Feature System Fixes

**Created**: 2025-12-09
**Status**: Planned
**Effort**: HIGH
**Priority**: P1

---

## Overview

This task addresses:
1. **Feature registry cleanup** - Simplify columns, keep useful fields
2. **Feature tasks cleanup** - Keep table, purge non-fix tasks, only allow `fix-*` going forward
3. **Command adjustments** - Update 5 commands after `/command_audit`
4. **Database FK gaps** - 8 tables missing symbol FK, symbols metadata empty
5. **Claude progress logging** - New table for session tracking

---

# PART A: Feature Registry Cleanup

## A1: Fields to DROP from feature_capabilities

| Field | Reason to Drop |
|-------|----------------|
| `task_file` | Orphaned - referenced files archived |
| `task_section` | Useless without task_file |
| `health_status` | Derivable from `passes` + criteria status |
| `test_count` | Derivable from `acceptance_criteria` length |
| `diagram` | Move to task markdown files |
| `implementation_notes` | Move to task markdown files |
| `status` | Implementation tracking, not outcomes |
| `effort` | Implementation tracking, not outcomes |
| `source` | Unclear purpose, rarely used |
| `verified_by` | Redundant with `last_verified_at` |

## A2: Fields to KEEP

| Field | Purpose |
|-------|---------|
| `id` | Internal PK |
| `feature_id` | External ID (FEAT-XXX) |
| `name` | Feature name |
| `category` | Grouping |
| `description` | What it does |
| `acceptance_criteria` | JSONB - testable criteria with `criterion`, `verification`, `type`, `passed` |
| `passes` | null/true/false |
| `layers` | What's affected (Frontend, Backend, DB) - useful for completeness detection |
| `layer_results` | Per-layer verification status |
| `priority` | P1-P4 |
| `vision_goals` | Array linking to vision |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |
| `last_verified_at` | When last tested |

**Result: 14 columns instead of 24**

## A3: Migration for Feature Registry

Create: `backend/migrations/102_simplify_feature_capabilities.sql`

```sql
-- Migration 102: Simplify feature_capabilities
-- Drop implementation-tracking columns (keep outcome-focused fields)
-- Date: 2025-12-09

-- Step 1: Drop unused columns
ALTER TABLE feature_capabilities
    DROP COLUMN IF EXISTS task_file,
    DROP COLUMN IF EXISTS task_section,
    DROP COLUMN IF EXISTS health_status,
    DROP COLUMN IF EXISTS test_count,
    DROP COLUMN IF EXISTS diagram,
    DROP COLUMN IF EXISTS implementation_notes,
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS effort,
    DROP COLUMN IF EXISTS source,
    DROP COLUMN IF EXISTS verified_by;

-- Record migration
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (102, 'Simplify feature_capabilities - drop 10 implementation-tracking columns', NOW())
ON CONFLICT (version) DO NOTHING;
```

---

# PART B: Feature Tasks Cleanup

## B1: Current State

| Task Type | Count | Completed | Action |
|-----------|-------|-----------|--------|
| `audit-*` | 395 | 390 | DELETE ALL - vanity metrics |
| `fix-*` | 110 | 31 | KEEP incomplete, DELETE completed |
| `DEBT-*` | ~20 | varies | RENAME to `fix-*`, keep if legit |
| Regular `1.1` | 296 | 8 | DELETE ALL - belong in task files |

## B2: Cleanup Steps

### Step 1: Rename DEBT tasks to fix tasks

```sql
-- Rename DEBT-* tasks to fix-* format
UPDATE feature_tasks
SET task_id = 'fix-' || SUBSTRING(task_id FROM 6),
    description = REPLACE(description, '[DEBT]', '[FIX]')
WHERE task_id LIKE 'DEBT-%';
```

### Step 2: Delete all completed tasks

```sql
-- Delete all completed tasks (they're just history)
DELETE FROM feature_tasks WHERE completed = true;
```

### Step 3: Delete all audit-* tasks

```sql
-- Delete audit tasks (vanity metrics, not real work)
DELETE FROM feature_tasks WHERE task_id LIKE 'audit-%';
```

### Step 4: Delete all regular implementation tasks

```sql
-- Delete regular implementation tasks (belong in task markdown files)
DELETE FROM feature_tasks
WHERE task_id NOT LIKE 'fix-%'
  AND task_id NOT LIKE 'audit-%';
```

### Step 5: Verify only fix-* tasks remain

```sql
-- Should only have incomplete fix-* tasks
SELECT task_id, description, completed
FROM feature_tasks
ORDER BY task_id
LIMIT 20;

-- Count remaining
SELECT COUNT(*) FROM feature_tasks;
-- Expected: ~79 (incomplete fix-* tasks)
```

## B3: Going Forward Rules

| Action | Allowed? | Who Creates |
|--------|----------|-------------|
| Create `fix-*` task | YES | `/verify_it`, `/audit_it` when issues found |
| Create `audit-*` task | NO | Audits should report, not create checkboxes |
| Create regular `1.1` task | NO | Use task markdown files instead |
| Complete `fix-*` task | YES | `/do_it` when fix verified |
| Delete `fix-*` task | YES | When issue resolved or false positive |

---

# PART C: Command Adjustments

## C1: Run /command_audit First

Before modifying commands, run `/command_audit` on these 5 commands to ensure they're streamlined:

```bash
/command_audit task_it do_it go qp pause_it
```

This will identify:
- Redundant sections
- Conflicting instructions
- Opportunities for simplification
- Dead code/references

## C2: Commands to Update

### `/task_it`

**Current**: Creates features + subtasks in DB
**New**: Creates task markdown files in `tasks/` folder

Key changes:
- Remove all `feature_tasks` API calls
- Generate markdown file with implementation steps
- Include `Implements: FEAT-XXX` header if linked to feature
- Include `## Files to Modify`, `## Steps`, `## Verification`, `## Rollback`

### `/do_it`

**Current**: Iterates `feature_tasks` subtasks
**New**: Supports two modes

Mode 1 - Feature mode (default):
- Find feature with `passes=false` or `passes=null`
- Check for `fix-*` tasks (work on those)
- If no fix tasks, check for linked task file
- Run `/verify_it` when done

Mode 2 - Task file mode:
- `/do_it tasks/some-task.md`
- Read and execute task file steps
- Track progress with checkboxes in file
- If `Implements: FEAT-XXX`, verify feature when done
- Archive to `tasks/archive/` when complete

### `/go`

**Current**: Wrapper for `/do_it --max`
**Change**: Same behavior, just ensure it passes through to updated `/do_it`

### `/pause_it`

**Current**: Marks subtasks complete in DB
**New**:
- If working on task file: update checkboxes, note pause point
- If working on feature: note current `fix-*` task
- Git status/stash handling unchanged
- Create pause summary

### `/qp` (Quick Pause)

**Current**: Minimal version of `/pause_it`
**New**: Same simplification, just faster

### `/audit_it`

**Current**: Creates `audit-*` tasks as checkboxes
**New**:
- Audit and REPORT findings
- Create `fix-*` task ONLY when real issues found
- NO more `audit-*` task creation
- Output should be a report, not busywork

### `/verify_it`

**Current**: Creates `fix-*` tasks when criteria fail
**Keep**: This behavior is correct - continue creating `fix-*` tasks for real issues

## C3: Update Order

1. Run `/command_audit` on 5 commands
2. Update `/task_it` (most impactful change)
3. Update `/do_it` (depends on task_it behavior)
4. Update `/pause_it` and `/qp` (simple adjustments)
5. Update `/audit_it` (stop creating audit-* tasks)
6. Test full workflow

---

# PART D: Claude Progress Log

## D1: Purpose

Replace Anthropic's `claude-progress.txt` with a queryable DB table.

Benefits over text file:
- Queryable (filter by session, feature, date)
- Structured data
- UI-viewable (add Claude Log tab)
- No git clutter

## D2: Table Schema

Create: `backend/migrations/103_claude_progress_log.sql`

```sql
-- Migration 103: Claude progress log for session tracking
-- Replaces claude-progress.txt from Anthropic's agent harness model
-- Date: 2025-12-09

CREATE TABLE claude_progress_log (
    id SERIAL PRIMARY KEY,
    session_id TEXT,                          -- Group entries by session
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,                     -- What was done
    action_type TEXT,                         -- category: implement, verify, fix, explore, etc.
    feature_id TEXT,                          -- Optional: linked FEAT-XXX
    task_file TEXT,                           -- Optional: linked task file path
    files_modified TEXT[],                    -- Files changed
    details JSONB,                            -- Additional context
    git_commit TEXT,                          -- Associated commit hash
    context_percent INTEGER                   -- Context usage at time of log
);

-- Indexes for common queries
CREATE INDEX idx_claude_progress_session ON claude_progress_log(session_id);
CREATE INDEX idx_claude_progress_logged_at ON claude_progress_log(logged_at DESC);
CREATE INDEX idx_claude_progress_feature ON claude_progress_log(feature_id);
CREATE INDEX idx_claude_progress_action_type ON claude_progress_log(action_type);

-- Record migration
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (103, 'Add claude_progress_log table for session tracking', NOW())
ON CONFLICT (version) DO NOTHING;
```

## D3: Usage Pattern

Commands should log progress:

```bash
# API endpoint for logging
POST /api/claude/progress
{
  "session_id": "2025-12-09-session-1",
  "action": "Implemented watchlist sorting",
  "action_type": "implement",
  "feature_id": "FEAT-042",
  "files_modified": ["frontend/components/Watchlist.tsx"],
  "git_commit": "abc123",
  "context_percent": 65
}

# Query recent progress
GET /api/claude/progress?limit=20
GET /api/claude/progress?feature_id=FEAT-042
GET /api/claude/progress?session_id=2025-12-09-session-1
```

## D4: When to Log

- Start of `/do_it` execution
- After each major step completion
- Before `/pause_it` saves state
- After `/verify_it` completes
- After git commits

## D5: UI Component - Log Tab

Add a "Log" tab to the Capabilities page (between Tasks and API tabs).

**Location**: `frontend/components/capabilities/LogTab.tsx`

**Features**:
- Table with expandable rows
- Columns: Time, Action, Type, Feature, Task File, Commit
- Expand row to show: files_modified, details JSONB, context_percent
- Filter by: session_id, feature_id, action_type, date range
- Sort by: logged_at (default DESC)
- Pagination: 25 rows per page

**API Endpoint**: `GET /api/claude/progress`

Query params:
- `limit` (default 25)
- `offset` (for pagination)
- `session_id` (filter)
- `feature_id` (filter)
- `action_type` (filter)
- `since` (ISO date filter)

**Tab Order on Capabilities Page**:
```
Dashboard | Vision | Features | Workflows | QA | Sources | Rules | DB | Tasks | Log | API
```

**Implementation Steps**:
1. Create `LogTab.tsx` component with expandable table
2. Add tab to `CapabilitiesDashboard.tsx` (before API tab)
3. Create `/api/claude/progress` endpoint in backend
4. Add query/filter/pagination logic
5. Style consistent with other capability tabs

---

# PART E: Database FK Fixes

## E1: Critical Data Quality

### 1.1 Symbols Table Metadata Empty
- **Issue**: All 44 symbols have NULL/empty company_name, sector, exchange
- **Impact**: No sector-based analysis, no company name display
- **Fix**: Create Celery task to enrich from yfinance

### 1.2 Orphan Records in news_summary_log
- **Issue**: 9 records reference symbols not in symbols table
- **Impact**: Will block FK constraint addition
- **Fix**: Either insert missing symbols or delete orphans

## E2: Missing Foreign Key Constraints

These 8 tables have `symbol` column but NO FK to `symbols`:

| Table | Risk if Orphans | Cascade Behavior |
|-------|-----------------|------------------|
| backtest_trades | MEDIUM | RESTRICT DELETE |
| idea_outcomes | HIGH | RESTRICT DELETE |
| news_summary_log | LOW | CASCADE DELETE |
| paper_trade_transactions | HIGH | RESTRICT DELETE |
| reference_cache | HIGH | RESTRICT DELETE |
| sec_cik_cache | LOW | RESTRICT DELETE |
| strategy_reviews | LOW | RESTRICT DELETE |
| symbol_risk_metrics | LOW | RESTRICT DELETE |

### E3: Cross-Table FK Missing

- `agent_messages.from_agent_run_id` → `agent_runs.id` (no FK constraint)

---

## E4: Implementation

### Step 1: Pre-Migration Orphan Check

```sql
-- Check for orphans in each table (must be 0 before proceeding)
SELECT 'backtest_trades' as tbl, COUNT(*) as orphans FROM backtest_trades bt
WHERE NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = bt.symbol)
UNION ALL
SELECT 'idea_outcomes', COUNT(*) FROM idea_outcomes io
WHERE io.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = io.symbol)
UNION ALL
SELECT 'news_summary_log', COUNT(*) FROM news_summary_log nsl
WHERE nsl.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = nsl.symbol)
UNION ALL
SELECT 'paper_trade_transactions', COUNT(*) FROM paper_trade_transactions ptt
WHERE ptt.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = ptt.symbol)
UNION ALL
SELECT 'reference_cache', COUNT(*) FROM reference_cache rc
WHERE rc.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = rc.symbol)
UNION ALL
SELECT 'sec_cik_cache', COUNT(*) FROM sec_cik_cache scc
WHERE scc.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = scc.symbol)
UNION ALL
SELECT 'strategy_reviews', COUNT(*) FROM strategy_reviews sr
WHERE sr.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = sr.symbol)
UNION ALL
SELECT 'symbol_risk_metrics', COUNT(*) FROM symbol_risk_metrics srm
WHERE srm.symbol IS NOT NULL AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = srm.symbol);
```

### Step 2: Orphan Cleanup

```sql
-- Option A: Insert missing symbols
INSERT INTO symbols (symbol, is_active, created_at)
SELECT DISTINCT nsl.symbol, true, NOW()
FROM news_summary_log nsl
LEFT JOIN symbols s ON nsl.symbol = s.symbol
WHERE s.symbol IS NULL AND nsl.symbol IS NOT NULL
ON CONFLICT (symbol) DO NOTHING;

-- Option B: Delete orphan records (if truly invalid)
DELETE FROM news_summary_log nsl
WHERE NOT EXISTS (SELECT 1 FROM symbols s WHERE s.symbol = nsl.symbol);
```

### Step 3: Migration 100 - Add Symbol FK Constraints

Create file: `backend/migrations/100_add_missing_symbol_fk_constraints.sql`

```sql
-- Migration 100: Add missing FK constraints for symbol columns
-- Prerequisites: Run orphan cleanup (Step 2) first
-- Date: 2025-12-09

-- 1. backtest_trades → symbols
ALTER TABLE backtest_trades
ADD CONSTRAINT fk_backtest_trades_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 2. idea_outcomes → symbols
ALTER TABLE idea_outcomes
ADD CONSTRAINT fk_idea_outcomes_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 3. news_summary_log → symbols
ALTER TABLE news_summary_log
ADD CONSTRAINT fk_news_summary_log_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE CASCADE
DEFERRABLE INITIALLY DEFERRED;

-- 4. paper_trade_transactions → symbols
ALTER TABLE paper_trade_transactions
ADD CONSTRAINT fk_paper_trade_transactions_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 5. reference_cache → symbols
ALTER TABLE reference_cache
ADD CONSTRAINT fk_reference_cache_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 6. sec_cik_cache → symbols
ALTER TABLE sec_cik_cache
ADD CONSTRAINT fk_sec_cik_cache_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 7. strategy_reviews → symbols
ALTER TABLE strategy_reviews
ADD CONSTRAINT fk_strategy_reviews_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- 8. symbol_risk_metrics → symbols
ALTER TABLE symbol_risk_metrics
ADD CONSTRAINT fk_symbol_risk_metrics_symbol
FOREIGN KEY (symbol) REFERENCES symbols(symbol)
ON UPDATE CASCADE ON DELETE RESTRICT
DEFERRABLE INITIALLY DEFERRED;

-- Create indexes for JOIN performance
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol ON backtest_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_idea_outcomes_symbol ON idea_outcomes(symbol);
CREATE INDEX IF NOT EXISTS idx_news_summary_log_symbol ON news_summary_log(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trade_transactions_symbol ON paper_trade_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_reference_cache_symbol ON reference_cache(symbol);
CREATE INDEX IF NOT EXISTS idx_sec_cik_cache_symbol ON sec_cik_cache(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_reviews_symbol ON strategy_reviews(symbol);
CREATE INDEX IF NOT EXISTS idx_symbol_risk_metrics_symbol ON symbol_risk_metrics(symbol);

-- Record migration
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (100, 'Add missing symbol FK constraints to 8 tables', NOW())
ON CONFLICT (version) DO NOTHING;
```

### Step 4: Migration 101 - Agent Messages FK

Create file: `backend/migrations/101_agent_messages_fk.sql`

```sql
-- Migration 101: Add FK constraint for agent_messages
-- Date: 2025-12-09

ALTER TABLE agent_messages
ADD CONSTRAINT fk_agent_messages_from_run
FOREIGN KEY (from_agent_run_id) REFERENCES agent_runs(id)
ON DELETE SET NULL
DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS idx_agent_messages_from_run ON agent_messages(from_agent_run_id);

INSERT INTO schema_migrations (version, description, applied_at)
VALUES (101, 'Add agent_messages FK to agent_runs', NOW())
ON CONFLICT (version) DO NOTHING;
```

### Step 5: Create Symbols Enrichment Task

Location: `backend/app/tasks/enrich_symbols.py`

```python
"""Enrich symbols table with metadata from yfinance."""
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.tasks.utils import task_logger, task_lock

logger = get_logger(__name__)

@celery_app.task(bind=True, name="tasks.enrich_symbols_metadata")
def enrich_symbols_metadata(self):
    """Fetch and update company_name, sector, exchange for all symbols."""
    with task_logger(self, "enrich_symbols"):
        with task_lock("enrich_symbols", ttl=600) as acquired:
            if not acquired:
                return {"status": "skipped", "reason": "locked"}

            import yfinance as yf
            from app.storage import get_storage

            storage = get_storage()
            result = storage.query("SELECT symbol FROM symbols WHERE company_name IS NULL OR company_name = ''")
            symbols = result.to_dicts()

            updated = 0
            for row in symbols:
                try:
                    ticker = yf.Ticker(row["symbol"])
                    info = ticker.info

                    storage.execute("""
                        UPDATE symbols
                        SET company_name = %s, sector = %s, exchange = %s, updated_at = NOW()
                        WHERE symbol = %s
                    """, (
                        info.get("longName") or info.get("shortName"),
                        info.get("sector"),
                        info.get("exchange"),
                        row["symbol"]
                    ))
                    updated += 1
                except Exception as e:
                    logger.warning("enrich_symbol_failed", symbol=row["symbol"], error=str(e))

            return {"status": "success", "updated": updated}
```

---

## E5: Verification

```sql
-- 1. Verify FK count increased
SELECT COUNT(*) as fk_count
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public';
-- Expected: 59 (was 50, added 9)

-- 2. Verify specific FKs exist
SELECT tc.table_name, kcu.column_name, ccu.table_name AS references_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name IN ('backtest_trades', 'idea_outcomes', 'news_summary_log',
    'paper_trade_transactions', 'reference_cache', 'sec_cik_cache',
    'strategy_reviews', 'symbol_risk_metrics', 'agent_messages')
ORDER BY tc.table_name;
-- Expected: 9 rows

-- 3. Test referential integrity (should fail)
INSERT INTO backtest_trades (run_id, symbol, entry_date, entry_price, shares)
VALUES ('00000000-0000-0000-0000-000000000000', 'INVALID_SYMBOL_XYZ', '2025-01-01', 100.0, 10);
-- Expected: FK violation error

-- 4. Verify symbols enrichment
SELECT COUNT(*) as enriched FROM symbols WHERE company_name IS NOT NULL AND company_name != '';
-- Expected: > 0 after enrichment task runs
```

---

## E6: Rollback Plan

```sql
-- Rollback Migration 101
ALTER TABLE agent_messages DROP CONSTRAINT IF EXISTS fk_agent_messages_from_run;
DROP INDEX IF EXISTS idx_agent_messages_from_run;
DELETE FROM schema_migrations WHERE version = 101;

-- Rollback Migration 100 (all 8 constraints)
ALTER TABLE backtest_trades DROP CONSTRAINT IF EXISTS fk_backtest_trades_symbol;
ALTER TABLE idea_outcomes DROP CONSTRAINT IF EXISTS fk_idea_outcomes_symbol;
ALTER TABLE news_summary_log DROP CONSTRAINT IF EXISTS fk_news_summary_log_symbol;
ALTER TABLE paper_trade_transactions DROP CONSTRAINT IF EXISTS fk_paper_trade_transactions_symbol;
ALTER TABLE reference_cache DROP CONSTRAINT IF EXISTS fk_reference_cache_symbol;
ALTER TABLE sec_cik_cache DROP CONSTRAINT IF EXISTS fk_sec_cik_cache_symbol;
ALTER TABLE strategy_reviews DROP CONSTRAINT IF EXISTS fk_strategy_reviews_symbol;
ALTER TABLE symbol_risk_metrics DROP CONSTRAINT IF EXISTS fk_symbol_risk_metrics_symbol;

DROP INDEX IF EXISTS idx_backtest_trades_symbol;
DROP INDEX IF EXISTS idx_idea_outcomes_symbol;
DROP INDEX IF EXISTS idx_news_summary_log_symbol;
DROP INDEX IF EXISTS idx_paper_trade_transactions_symbol;
DROP INDEX IF EXISTS idx_reference_cache_symbol;
DROP INDEX IF EXISTS idx_sec_cik_cache_symbol;
DROP INDEX IF EXISTS idx_strategy_reviews_symbol;
DROP INDEX IF EXISTS idx_symbol_risk_metrics_symbol;

DELETE FROM schema_migrations WHERE version = 100;
```

---

# PART F: Claude Session Protocol

## F1: Problem Statement

Per Anthropic's recommendations, Claude needs a consistent session startup protocol to:
1. Get bearings quickly (not waste tokens figuring out state)
2. Catch bugs before starting new work
3. Track progress for future sessions
4. Avoid premature victory declarations

## F2: Session Startup Protocol

Every Claude session should start with these steps (update CLAUDE.md):

```markdown
## Session Startup Protocol

When starting a new session or after context reset:

1. **Get bearings**
   ```bash
   pwd
   git status
   git log --oneline -10
   ```

2. **Read progress log** (replaces claude-progress.txt)
   ```bash
   curl -s http://localhost:8000/api/claude/progress?limit=10 | jq
   ```

3. **Check for incomplete fix tasks**
   ```bash
   curl -s http://localhost:8000/api/capabilities/features/ | jq '[.features[] | select(.tasks | any(.task_id | startswith("fix-") and .completed == false))] | length'
   ```

4. **Run health check** (catch bugs before new work)
   ```bash
   bash ~/portfolio-ai/scripts/status.sh
   curl -s http://localhost:8000/api/health | jq
   ```

5. **Basic UI verification** (optional, if UI work planned)
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js http://192.168.8.233:3000/ /tmp/startup-check.png
   ```

6. **Choose work**
   - If fix-* tasks exist → work on those first
   - If task file specified → execute that
   - Otherwise → find feature with passes=null or passes=false
```

## F3: Session End Protocol

Before ending a session or when context is high:

```markdown
## Session End Protocol

1. **Commit current work**
   ```bash
   git add -A && git commit -m "checkpoint: <description>"
   ```

2. **Log progress to DB**
   ```bash
   curl -X POST http://localhost:8000/api/claude/progress \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "<current-session>",
       "action": "<what was accomplished>",
       "action_type": "checkpoint",
       "feature_id": "<if applicable>",
       "files_modified": ["<files changed>"],
       "context_percent": <current context %>
     }'
   ```

3. **Run /pause_it or /qp** for full handoff document
```

## F4: Commands to Update for Logging

These commands should automatically log to `claude_progress_log`:

| Command | When to Log | action_type |
|---------|-------------|-------------|
| `/do_it` | Start of execution | `start` |
| `/do_it` | Each major step | `progress` |
| `/do_it` | Completion | `complete` |
| `/verify_it` | After verification | `verify` |
| `/audit_it` | After audit | `audit` |
| `/pause_it` | Before pause | `pause` |
| `/qp` | Before quick pause | `pause` |
| `/task_it` | After task file created | `plan` |

## F5: API Endpoint for Logging

Create: `backend/app/api/claude_progress.py`

```python
"""Claude progress logging API."""
from datetime import datetime
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/claude", tags=["claude"])

class ProgressEntry(BaseModel):
    session_id: str | None = None
    action: str
    action_type: str | None = None
    feature_id: str | None = None
    task_file: str | None = None
    files_modified: list[str] | None = None
    details: dict | None = None
    git_commit: str | None = None
    context_percent: int | None = None

@router.post("/progress")
async def log_progress(entry: ProgressEntry):
    """Log a progress entry."""
    from app.storage import get_storage
    storage = get_storage()

    storage.execute("""
        INSERT INTO claude_progress_log
        (session_id, action, action_type, feature_id, task_file,
         files_modified, details, git_commit, context_percent)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        entry.session_id, entry.action, entry.action_type,
        entry.feature_id, entry.task_file, entry.files_modified,
        entry.details, entry.git_commit, entry.context_percent
    ))

    return {"status": "logged"}

@router.get("/progress")
async def get_progress(
    limit: int = Query(25, le=100),
    offset: int = Query(0),
    session_id: str | None = None,
    feature_id: str | None = None,
    action_type: str | None = None,
    since: str | None = None
):
    """Get progress entries with filtering."""
    from app.storage import get_storage
    storage = get_storage()

    conditions = []
    params = []

    if session_id:
        conditions.append("session_id = %s")
        params.append(session_id)
    if feature_id:
        conditions.append("feature_id = %s")
        params.append(feature_id)
    if action_type:
        conditions.append("action_type = %s")
        params.append(action_type)
    if since:
        conditions.append("logged_at >= %s")
        params.append(since)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = storage.query(f"""
        SELECT * FROM claude_progress_log
        {where}
        ORDER BY logged_at DESC
        LIMIT %s OFFSET %s
    """, (*params, limit, offset))

    return {"entries": result.to_dicts(), "limit": limit, "offset": offset}

@router.get("/progress/latest")
async def get_latest_session():
    """Get the most recent session's progress."""
    from app.storage import get_storage
    storage = get_storage()

    result = storage.query("""
        SELECT * FROM claude_progress_log
        WHERE session_id = (
            SELECT session_id FROM claude_progress_log
            ORDER BY logged_at DESC LIMIT 1
        )
        ORDER BY logged_at DESC
    """)

    return {"entries": result.to_dicts()}
```

## F6: Update CLAUDE.md

Add to CLAUDE.md after implementation:

```markdown
## 🚀 Session Startup (Do This First)

When starting fresh or after context reset:

1. Read recent progress: `curl -s http://localhost:8000/api/claude/progress?limit=10 | jq`
2. Check git state: `git log --oneline -5`
3. Check service health: `bash ~/portfolio-ai/scripts/status.sh`
4. If fix-* tasks exist, work on those first
5. Otherwise, find feature with `passes=null` or `passes=false`

**Never start new features if existing bugs or fix tasks are pending.**
```

## F7: Failure Mode Prevention

| Failure Mode | Prevention |
|--------------|------------|
| Declare victory too early | Only mark `passes=true` after `/verify_it` confirms all criteria pass |
| Leave bugs undocumented | Always log progress before pause, run health check at session start |
| Mark features done prematurely | Fix-* tasks must be resolved before feature can pass |
| Waste time figuring out state | Read progress log + git log at session start |

---

# EXECUTION ORDER

## Summary: 6 Parts

| Part | Description | Risk |
|------|-------------|------|
| **A** | Feature registry cleanup (drop 10 columns) | LOW |
| **B** | Feature tasks cleanup (purge, keep fix-* only) | LOW |
| **C** | Command adjustments (after /command_audit) | MEDIUM |
| **D** | Claude progress log table + UI | LOW |
| **E** | Database FK fixes | LOW |
| **F** | Claude session protocol (startup/end, logging) | LOW |

## Recommended Sequence

### Phase 1: Preparation
- [ ] Create git checkpoint
- [ ] Run `/command_audit` on task_it, do_it, go, qp, pause_it

### Phase 2: Feature Tasks Cleanup (Part B)
- [ ] Rename DEBT-* to fix-*
- [ ] Delete completed tasks
- [ ] Delete audit-* tasks
- [ ] Delete regular implementation tasks
- [ ] Verify only incomplete fix-* remain (~79 tasks)

### Phase 3: Feature Registry Cleanup (Part A)
- [ ] Create migration 102
- [ ] Apply migration 102
- [ ] Verify UI still works

### Phase 4: Claude Progress Log (Part D)
- [ ] Create migration 103
- [ ] Apply migration 103
- [ ] Create API endpoint `GET /api/claude/progress`
- [ ] Create `LogTab.tsx` component (expandable rows, filters, pagination)
- [ ] Add Log tab to CapabilitiesDashboard.tsx (before API tab)

### Phase 5: Database FKs (Part E)
- [ ] Run orphan check
- [ ] Clean orphans
- [ ] Create and apply migration 100
- [ ] Create and apply migration 101
- [ ] Create symbols enrichment task
- [ ] Run enrichment task

### Phase 6: Command Adjustments (Part C)
- [ ] Update `/task_it` (create task files)
- [ ] Update `/do_it` (dual mode: features + task files)
- [ ] Update `/pause_it` and `/qp`
- [ ] Update `/audit_it` (no more audit-* creation)
- [ ] Test full workflow

### Phase 7: Claude Session Protocol (Part F)
- [ ] Add logging calls to commands (do_it, verify_it, audit_it, pause_it, qp, task_it)
- [ ] Update CLAUDE.md with session startup/end protocol
- [ ] Test session startup flow

### Phase 8: Cleanup
- [ ] Archive this task file
- [ ] Update CLAUDE.md if needed

---

## Acceptance Criteria

### Part A - Feature Registry
- [ ] feature_capabilities has 14 columns (was 24)
- [ ] Features UI still works

### Part B - Feature Tasks
- [ ] Only `fix-*` tasks remain in table
- [ ] ~79 incomplete fix tasks
- [ ] 0 audit-* tasks
- [ ] 0 regular implementation tasks

### Part C - Commands
- [ ] `/command_audit` completed on 5 commands
- [ ] `/task_it` creates markdown files (not DB subtasks)
- [ ] `/do_it` supports task file mode
- [ ] `/audit_it` creates fix-* only (no audit-*)

### Part D - Claude Progress Log
- [ ] Table created (migration 103)
- [ ] API endpoint `GET /api/claude/progress` working
- [ ] `LogTab.tsx` component created with expandable rows
- [ ] Log tab added to Capabilities page (before API tab)
- [ ] Filters and pagination working
- [ ] Commands log progress

### Part E - Database FKs
- [ ] FK count increased from 50 to 59
- [ ] No orphan records
- [ ] Symbols have metadata

### Part F - Claude Session Protocol
- [ ] Commands log progress to `claude_progress_log` table
- [ ] CLAUDE.md updated with session startup protocol
- [ ] Session end protocol documented
- [ ] Failure modes addressed

---

**End of Task**
