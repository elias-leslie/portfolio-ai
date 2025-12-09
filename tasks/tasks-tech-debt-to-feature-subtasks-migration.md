# Tech Debt → Feature Subtasks Migration

**Created**: 2025-12-08
**Status**: Planning
**Effort**: MEDIUM
**Vision Goals**: VG-QUAL, VG-RELY

---

## Overview

Consolidate the separate "Tech Debt / Insights" system into the Features system as subtasks. This eliminates redundancy and creates a single source of truth for all work tracking.

### Why

- **Redundant systems**: Tech Debt and Features both track "things to fix"
- **No ownership**: Tech debt items float without clear feature association
- **Two places to look**: Confusing for users and agents
- **Against DRY**: Tech debt items are just subtasks with `[DEBT]` prefix
- **Completion gate**: Features can't properly track "done" if debt is elsewhere

### Outcome

- Single Features system tracks everything (features, tasks, debt)
- Tech debt becomes `[DEBT]` prefixed subtasks on owning features
- Cross-cutting debt becomes `FEAT-DEBT-XXX` features
- Tech Debt tab removed from UI
- Agents use one workflow for all work

---

## Phase 1: Analysis & Mapping

### 1.1 Audit current tech debt

```bash
# Get all tech debt items
curl -s 'http://localhost:8000/api/capabilities/insights/?limit=200' | jq '{
  total: .total,
  by_status: (group_by(.status) | map({status: .[0].status, count: length})),
  by_severity: (group_by(.severity) | map({severity: .[0].severity, count: length}))
}'
```

### 1.2 Categorize each item

| Category | Criteria | Action |
|----------|----------|--------|
| **Feature-specific** | References specific table/endpoint/task | Subtask on owning feature |
| **Cross-cutting** | Affects multiple features | Create `FEAT-DEBT-XXX` |
| **Already fixed** | Issue no longer exists | Mark dismissed |
| **Duplicate** | Same as existing feature/task | Mark dismissed |

### 1.3 Map tech debt to features

Create mapping based on:
- Table name → Feature with that table in implementation_notes
- Endpoint path → Feature with that endpoint in layers/criteria
- Celery task → Feature with that task in implementation_notes
- Category match → Feature in same category

```bash
# Example: Find feature for tech debt about "financial_health_scores" table
curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | jq '
  [.features[] | select(
    .implementation_notes.tables[]? == "financial_health_scores" or
    (.name | ascii_downcase | contains("financial health"))
  )]'
```

---

## Phase 2: Migration Script

### 2.1 Create migration script

Location: `backend/migrations/103_migrate_tech_debt_to_subtasks.py`

```python
# Pseudocode
for debt_item in get_all_tech_debt():
    if debt_item.status in ['fixed', 'dismissed']:
        continue  # Already handled

    feature = find_owning_feature(debt_item)

    if feature:
        # Create [DEBT] subtask on existing feature
        create_subtask(
            feature_id=feature.feature_id,
            task_id=f"DEBT-{debt_item.id}",
            description=f"[DEBT] {debt_item.finding}",
            notes=f"Severity: {debt_item.severity}\nSuggested fix: {debt_item.suggested_fix}",
            effort=severity_to_effort(debt_item.severity)
        )
    else:
        # Create new FEAT-DEBT feature
        create_feature(
            feature_id=f"FEAT-DEBT-{debt_item.id}",
            name=f"[DEBT] {debt_item.finding[:50]}",
            category="Tech Debt",
            description=debt_item.finding,
            vision_goals=["VG-QUAL"],
            acceptance_criteria=[{
                "id": "ac-001",
                "criterion": "Issue resolved",
                "verification": debt_item.suggested_fix,
                "type": "backend"
            }]
        )

    # Mark original as migrated
    mark_debt_migrated(debt_item.id, feature_id or new_feature_id)
```

### 2.2 Severity to effort mapping

| Severity | Effort | Priority |
|----------|--------|----------|
| critical | high | 1 |
| high | medium | 2 |
| medium | low | 3 |
| low | low | 4 |

### 2.3 Run migration

```bash
cd ~/portfolio-ai/backend
.venv/bin/python migrations/103_migrate_tech_debt_to_subtasks.py
```

### 2.4 Verify migration

- [ ] All pending tech debt items converted to subtasks or features
- [ ] Each subtask has `[DEBT]` prefix
- [ ] Each subtask linked to correct feature
- [ ] Cross-cutting items became `FEAT-DEBT-XXX` features
- [ ] Original tech debt items marked as migrated

---

## Phase 3: Update Phase 1.8 in audit_it

### 3.1 Change tech debt handling

**Before**: Create new features from tech debt
**After**:
1. Scanner finds issues → creates `capability_insights` (unchanged)
2. Phase 1.8 triages into subtasks on existing features
3. Cross-cutting issues → `FEAT-DEBT-XXX` features
4. Mark original insight as `fixed` with reference

### 3.2 Update audit_it.md Phase 1.8

Replace current Phase 1.8 with intelligent linking:

```markdown
## Phase 1.8: Tech Debt Triage (Link to Features)

For each pending tech debt item:
1. Match to existing feature by table/endpoint/task/category
2. If match: Create `[DEBT]` subtask on that feature
3. If no match: Create `FEAT-DEBT-XXX` feature
4. Mark original as `fixed` with reference
```

---

## Phase 4: UI Updates

### 4.1 Remove Tech Debt tab

File: `frontend/app/capabilities/page.tsx`

- Remove "insights" from TabValue type
- Remove Tech Debt TabsTrigger
- Remove Tech Debt TabsContent
- Update grid-cols from 9 to 8
- Remove InsightCard import
- Remove insights query

### 4.2 Update Features tab

- Add filter for `[DEBT]` tasks
- Show debt badge on features with open debt subtasks
- Add "Tech Debt" category filter

### 4.3 Update Dashboard

- Remove tech debt card OR change to show debt subtask count
- Update stats to pull from features

---

## Phase 5: Backend Cleanup

### 5.1 Remove Gap Detection System (already migrated)

**Files to DELETE:**
```
backend/app/services/gap_detection/
├── analyzer.py
├── capability_checker.py
├── gap_detector.py
├── __init__.py
├── requirements.py
└── types.py
```

**Tasks to REMOVE from `gap_analysis_tasks.py`:**
- `analyze_trading_gaps` - gaps migrated to features
- `track_gap_trends` - no longer needed
- `alert_critical_gaps` - no longer needed

Then delete: `backend/app/tasks/gap_analysis_tasks.py`

**Remove from Celery beat schedule** (`celery_schedules.py`):
```python
# Remove these entries:
"analyze_trading_gaps": {...}
"track_gap_trends": {...}
"alert_critical_gaps": {...}
```

### 5.2 Replace AI Analyzer with Deterministic Scanner

**DELETE:** `backend/app/services/ai_analyzer.py` (LLM-based, non-deterministic)

**CREATE:** `backend/scripts/tech_debt_scanner.py` (factual queries, no hallucination)

#### 5.2.1 Scanner Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Factual** | SQL queries, curl checks - no LLM |
| **Deterministic** | Same input = same output |
| **No false positives** | Exception list for known cases |
| **Auditable** | Each finding includes verify_cmd |

#### 5.2.2 Deterministic Checks

```python
# backend/scripts/tech_debt_scanner.py

CHECKS = [
    {
        "id": "empty_table",
        "name": "Empty Tables",
        "query": "SELECT COUNT(*) FROM {table}",
        "condition": lambda count: count == 0,
        "severity": "high",
        "message": "Table {table} has 0 rows",
    },
    {
        "id": "stale_data",
        "name": "Stale Data",
        "query": "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/86400 FROM {table}",
        "condition": lambda days: days > threshold_days,
        "severity": "medium",
        "message": "Table {table} not updated in {days} days",
    },
    {
        "id": "failing_feature",
        "name": "Failing Features",
        "query": "SELECT feature_id, name FROM feature_capabilities WHERE passes = false",
        "condition": lambda rows: len(rows) > 0,
        "severity": "high",
        "message": "Feature {feature_id} is marked as failing",
    },
    {
        "id": "no_tests",
        "name": "Features Without Tests",
        "query": "SELECT feature_id, name FROM feature_capabilities WHERE test_count = 0 AND passes IS NOT NULL",
        "condition": lambda rows: len(rows) > 0,
        "severity": "medium",
        "message": "Feature {feature_id} has no tests",
    },
    {
        "id": "orphan_tasks",
        "name": "Incomplete Tasks on Passing Features",
        "query": """
            SELECT f.feature_id, t.task_id
            FROM feature_capabilities f
            JOIN feature_tasks t ON f.id = t.feature_id
            WHERE f.passes = true AND t.completed = false
        """,
        "condition": lambda rows: len(rows) > 0,
        "severity": "low",
        "message": "Feature {feature_id} passes but has incomplete task {task_id}",
    },
]
```

#### 5.2.3 Exception Mechanism (No False Positives)

**Config file:** `backend/app/config/tech_debt_exceptions.yaml`

```yaml
# Tables that are expected to be empty or rarely updated
exceptions:
  empty_table:
    - table: secure_credentials
      reason: "Only updated when new API keys added"
    - table: backtest_runs
      reason: "Empty until user runs backtest"

  stale_data:
    - table: secure_credentials
      max_days: 365  # Override default threshold
      reason: "API keys rarely change"
    - table: vision_goals
      max_days: 30
      reason: "Vision goals are stable"
    - table: trading_rules
      max_days: 30
      reason: "Rules don't change often"

  # Endpoints expected to return non-200
  endpoint_check:
    - path: /api/admin/*
      reason: "Admin endpoints require auth"
```

**Database table for UI-managed exceptions:**

```sql
CREATE TABLE tech_debt_exceptions (
    id SERIAL PRIMARY KEY,
    check_type VARCHAR(50) NOT NULL,  -- empty_table, stale_data, etc.
    entity VARCHAR(255) NOT NULL,      -- table name, endpoint, etc.
    reason TEXT NOT NULL,
    threshold_override JSONB,          -- {"max_days": 365}
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP               -- Optional: temporary exceptions
);
```

**UI: Add to Capabilities page**
- New "Exceptions" section or modal
- List current exceptions with reasons
- Add/remove exceptions
- Shows which checks are skipped and why

#### 5.2.4 Scanner Output

```bash
# Run scanner
python backend/scripts/tech_debt_scanner.py --output json

# Output
{
  "scan_timestamp": "2025-12-08T12:00:00Z",
  "checks_run": 5,
  "exceptions_applied": 3,
  "findings": [
    {
      "check_id": "empty_table",
      "entity": "financial_health_scores",
      "severity": "high",
      "message": "Table financial_health_scores has 0 rows",
      "verify_cmd": "SELECT COUNT(*) FROM financial_health_scores",
      "suggested_fix": "Run ingest task or check data source"
    }
  ],
  "skipped": [
    {
      "check_id": "stale_data",
      "entity": "secure_credentials",
      "reason": "Exception: Only updated when new API keys added"
    }
  ]
}
```

#### 5.2.5 Integration Points

**Celery scheduled task (daily):**
```python
@celery_app.task(name="scan_tech_debt")
def scan_tech_debt():
    result = subprocess.run(
        ["python", "scripts/tech_debt_scanner.py", "--output", "json", "--create-tasks"],
        capture_output=True
    )
    findings = json.loads(result.stdout)
    # Creates [DEBT] subtasks on matching features
    return {"findings": len(findings["findings"]), "skipped": len(findings["skipped"])}
```

**/audit_it calls same script:**
```bash
# In audit_it Phase 1.6.4 (new):
python backend/scripts/tech_debt_scanner.py --output json --dry-run
# Review findings, then:
python backend/scripts/tech_debt_scanner.py --create-tasks
```

**/do_it verifies before executing:**
```bash
# For [DEBT] task, run the verify_cmd first
eval "$verify_cmd"  # e.g., SELECT COUNT(*) FROM financial_health_scores
# If issue gone, auto-close task
```

### 5.3 Keep These Scanners (power Dashboard tabs)

| File | Powers | Keep? |
|------|--------|-------|
| `capability_db_scanner.py` | Database tab (83 tables) | **YES** |
| `capability_celery_scanner.py` | Tasks tab (64 tasks) | **YES** |
| `capability_api_scanner.py` | Endpoints tab (37 endpoints) | **YES** |
| `capability_feature_scanner.py` | Features tab (214 features) | **YES** |
| `capability_tasks.py` → `scan_system_capabilities` | Runs above scanners | **YES** |
| `capability_tasks.py` → `scan_feature_capabilities` | Validates features | **YES** |

### 5.4 Remove Tech Debt API

**File to DELETE:**
- `backend/app/api/capabilities/insights_router.py`

**Update `backend/app/api/capabilities/__init__.py`:**
Remove `insights_router` import and registration.

### 5.5 Remove Tech Debt UI

**Update `frontend/app/capabilities/page.tsx`:**
- Remove "insights" from TabValue type
- Remove Tech Debt TabsTrigger
- Remove Tech Debt TabsContent
- Remove insights query
- Update grid-cols from 9 to 8

**Files to DELETE:**
- `frontend/components/capabilities/InsightCard.tsx`

### 5.6 Remove audit_it Phase 1.8

**Update `.claude/commands/audit_it.md`:**
- Delete entire Phase 1.8 (Tech Debt Review)
- No longer needed - tech debt is now subtasks on features

### 5.7 Update /do_it to verify scanner-generated tasks

**Update `.claude/commands/do_it.md`:**

Add verification step for `[DEBT]` tasks with `source: "scanner"`:

```markdown
## Scanner-Generated Task Verification

Before executing any `[DEBT]` task with `source: "scanner"`:

### Step 1: Verify issue still exists

| Issue Type | Verification |
|------------|--------------|
| Empty table | `SELECT COUNT(*) FROM {table}` > 0? |
| Stale data | `SELECT MAX(updated_at) FROM {table}` recent? |
| Missing Celery task | Task exists in registry? |
| Broken endpoint | `curl` returns 200? |

### Step 2: Take action based on verification

| Result | Action |
|--------|--------|
| Issue confirmed | Proceed with fix |
| Issue no longer exists | Mark task complete: "Issue resolved (verified {date})" |
| Cannot verify | Ask user for guidance |

### Step 3: Example flow

```bash
# Task: [DEBT] financial_health_scores table is empty
# Verification:
curl -s "http://localhost:8000/api/..." | jq '.count'

# If count > 0:
#   → Mark complete: "Table now has {count} rows"
# If count == 0:
#   → Proceed with fix
```
```

**Why this matters:**
- Scanner may detect issues that get fixed before /do_it runs
- Prevents wasted effort on false positives
- Self-healing: outdated tasks auto-close

### 5.8 Database Tables

**Tables to DROP (after verification):**
```sql
-- Only after confirming migration complete
DROP TABLE IF EXISTS capability_insights;
DROP TABLE IF EXISTS gap_analysis_history;
DROP TABLE IF EXISTS trading_gaps;
DROP TABLE IF EXISTS feature_gap_mappings;
```

**Tables to KEEP:**
- `db_capabilities` - powers Database tab
- `celery_capabilities` - powers Tasks tab
- `api_capabilities` - powers Endpoints tab
- `feature_capabilities` - single source of truth
- `feature_tasks` - subtasks including [DEBT] items

### 5.9 Config Files

**File to DELETE:**
- `backend/app/config/trading_requirements.yaml` - migrated to features

---

## Phase 6: Cleanup

### 6.1 Verify no orphan debt

```bash
curl -s 'http://localhost:8000/api/capabilities/insights/?status=pending' | jq '.total'
# Should be 0 after migration
```

### 6.2 Update documentation

- CLAUDE.md - Remove tech debt references
- COMMAND_REFERENCE.md - Update audit_it description
- ARCHITECTURE.md - Update capability tracking section

---

## Migration Checklist

### Pre-Migration
- [ ] Backup database
- [ ] Document current tech debt count and status breakdown
- [ ] Create rollback plan

### Migration
- [ ] Run analysis to map debt → features
- [ ] Create migration script
- [ ] Run migration
- [ ] Verify all items migrated or dismissed

### Post-Migration
- [ ] Update audit_it Phase 1.8
- [ ] Remove Tech Debt tab from UI
- [ ] Add deprecation notice to insights API
- [ ] Update documentation
- [ ] Test /audit_it --max --enrich works with new flow

---

## Success Criteria

- [ ] Zero pending tech debt items in old system (all migrated or dismissed)
- [ ] All actionable debt visible as `[DEBT]` subtasks in Features tab
- [ ] Tech Debt tab removed from /capabilities
- [ ] Phase 1.8 removed from audit_it (no longer needed)
- [ ] Gap detection system fully removed (files, tasks, schedules)
- [ ] AI analyzer removed (no more auto-generated insights)
- [ ] Deprecated tables dropped (capability_insights, trading_gaps, etc.)
- [ ] Capability scanners still running (db/celery/api/feature tabs work)

---

## Files to Create/Modify/Delete

### New Files
- `backend/migrations/103_migrate_tech_debt_to_subtasks.py`
- `backend/scripts/tech_debt_scanner.py` - Deterministic scanner (replaces LLM-based)
- `backend/app/config/tech_debt_exceptions.yaml` - Exception config
- `backend/migrations/104_tech_debt_exceptions.sql` - Exception table

### Modified Files
- `frontend/app/capabilities/page.tsx` - Remove Tech Debt tab, add Exceptions UI
- `backend/app/api/capabilities/__init__.py` - Remove insights_router
- `backend/app/tasks/capability_tasks.py` - Replace analyze_capabilities with scan_tech_debt
- `backend/app/celery_schedules.py` - Remove gap tasks, update analyze task
- `.claude/commands/audit_it.md` - Remove Phase 1.8, add Phase 1.6.4 (scanner call)
- `.claude/commands/do_it.md` - Add scanner task verification step

### Files to DELETE
```
# Gap Detection (migrated to features)
backend/app/services/gap_detection/  (entire directory)
backend/app/tasks/gap_analysis_tasks.py
backend/app/config/trading_requirements.yaml

# LLM-based analyzer (replaced by deterministic scanner)
backend/app/services/ai_analyzer.py

# Tech Debt UI/API (subtasks replace insights table)
backend/app/api/capabilities/insights_router.py
frontend/components/capabilities/InsightCard.tsx
```

### Keep (no changes)
- `backend/app/services/capability_db_scanner.py` - Powers Database tab
- `backend/app/services/capability_celery_scanner.py` - Powers Tasks tab
- `backend/app/services/capability_api_scanner.py` - Powers Endpoints tab
- `backend/app/services/capability_feature_scanner.py` - Powers Features tab

---

## Notes

- Similar pattern to trading-reqs-to-features migration
- Scanner keeps finding issues - this is valuable
- The change is in how issues get TRACKED (features) not FOUND (scanner)
- Cross-cutting debt becomes its own feature, not lost
- `[DEBT]` prefix makes debt tasks visually distinct

---

## Rollback Plan

If migration fails:
1. Restore database from backup
2. Revert UI changes (git checkout)
3. Remove deprecation notices
4. Tech debt system continues as before

