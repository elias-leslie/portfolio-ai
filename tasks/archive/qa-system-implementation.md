# QA System Implementation

**Created**: 2025-12-09
**Purpose**: Add QA tab, /clean_it command, anti-bloat rules, trend tracking
**Priority**: High - prevents tech debt accumulation

---

## Overview

Three interconnected pieces:
1. **QA Tab** on Capabilities page (between Workflows and Sources)
2. **`/clean_it` command** for deletion-focused cleanup
3. **Anti-bloat rules** added to existing commands

---

## Part 1: QA Tab Implementation

### 1.1 Database Schema

```sql
-- Migration: XXX_qa_issues.sql
CREATE TABLE qa_issues (
    id SERIAL PRIMARY KEY,
    issue_id VARCHAR(20) UNIQUE NOT NULL,  -- QA-001, QA-002, etc.
    category VARCHAR(50) NOT NULL,          -- dead_code, dry_violation, security, orphan_file, schema_drift, stale_data
    severity VARCHAR(20) NOT NULL,          -- critical, high, medium, low
    file_path TEXT,
    line_start INTEGER,
    line_end INTEGER,
    description TEXT NOT NULL,
    detection_source VARCHAR(50),           -- ruff, custom_scanner, manual, data_check
    first_detected_at TIMESTAMP DEFAULT NOW(),
    last_detected_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100),               -- auto, manual, claude
    resolution_notes TEXT,
    false_positive BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_qa_issues_category ON qa_issues(category);
CREATE INDEX idx_qa_issues_severity ON qa_issues(severity);
CREATE INDEX idx_qa_issues_resolved ON qa_issues(resolved_at);

-- Trend tracking
CREATE TABLE qa_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE UNIQUE NOT NULL,
    total_issues INTEGER NOT NULL,
    critical_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    by_category JSONB,                      -- {"dead_code": 5, "dry_violation": 12, ...}
    issues_added INTEGER DEFAULT 0,         -- New issues since last snapshot
    issues_resolved INTEGER DEFAULT 0,      -- Resolved since last snapshot
    lines_of_code INTEGER,                  -- Total LOC for trend
    file_count INTEGER,                     -- Total files for trend
    table_count INTEGER,                    -- Total DB tables for trend
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_qa_snapshots_date ON qa_snapshots(snapshot_date);
```

### 1.2 QA Categories

| Category | Detection Method | Severity Default |
|----------|------------------|------------------|
| `dead_code` | ruff F401 (unused imports), F841 (unused vars) | medium |
| `orphan_file` | Files not imported anywhere | high |
| `dry_violation` | Duplicate code blocks >10 lines (jscpd or custom) | medium |
| `security` | check-security.sh findings | critical |
| `schema_drift` | Tables not in migrations, orphaned columns | high |
| `stale_data` | Tables not updated in >7 days (configurable) | medium |
| `bloat` | Files >500 lines, functions >50 lines | low |
| `test_gap` | Features with test_count=0 | high |

### 1.3 Backend API Endpoints

```python
# backend/app/api/qa.py

router = APIRouter(prefix="/api/qa", tags=["qa"])

# List/filter issues
GET  /api/qa/issues?category=X&severity=Y&resolved=false&limit=50

# Get single issue
GET  /api/qa/issues/{issue_id}

# Mark resolved
PATCH /api/qa/issues/{issue_id}/resolve
Body: {"resolved_by": "manual", "resolution_notes": "Deleted file"}

# Mark false positive
PATCH /api/qa/issues/{issue_id}/false-positive
Body: {"false_positive": true, "notes": "Intentionally unused"}

# Trigger scan
POST /api/qa/scan?categories=dead_code,dry_violation

# Get summary stats
GET  /api/qa/summary
Response: {
  "total": 45,
  "by_severity": {"critical": 2, "high": 10, "medium": 28, "low": 5},
  "by_category": {"dead_code": 15, "dry_violation": 12, ...},
  "trend": "improving",  -- or "degrading", "stable"
  "resolved_this_week": 8,
  "added_this_week": 3
}

# Get trend data (for charts)
GET  /api/qa/trends?days=30
Response: {
  "snapshots": [
    {"date": "2025-12-01", "total": 50, "critical": 3, ...},
    {"date": "2025-12-02", "total": 48, "critical": 2, ...},
    ...
  ]
}
```

### 1.4 Scanner Service

```python
# backend/app/services/qa_scanner.py

class QAScanner:
    """Unified QA issue detection."""

    def scan_all(self) -> list[QAIssue]:
        issues = []
        issues += self.scan_dead_code()
        issues += self.scan_orphan_files()
        issues += self.scan_dry_violations()
        issues += self.scan_security()
        issues += self.scan_schema_drift()
        issues += self.scan_stale_data()
        issues += self.scan_bloat()
        issues += self.scan_test_gaps()
        return issues

    def scan_dead_code(self) -> list[QAIssue]:
        """Run ruff with F401, F841 rules."""
        result = subprocess.run(
            ["ruff", "check", "backend/app", "--select", "F401,F841", "--output-format", "json"],
            capture_output=True
        )
        # Parse and convert to QAIssue objects
        ...

    def scan_orphan_files(self) -> list[QAIssue]:
        """Find .py files not imported anywhere."""
        all_files = glob("backend/app/**/*.py")
        imported = set()
        for f in all_files:
            # Parse imports, build set of imported modules
            ...
        orphans = all_files - imported - KNOWN_ENTRY_POINTS
        ...

    def scan_dry_violations(self) -> list[QAIssue]:
        """Find duplicate code blocks."""
        # Option 1: Use jscpd
        # Option 2: Custom AST-based detection
        ...

    def scan_stale_data(self) -> list[QAIssue]:
        """Check db_capabilities for stale tables."""
        stale = db.execute("""
            SELECT table_name, days_since_update
            FROM db_capabilities
            WHERE freshness_status IN ('stale', 'critical')
        """)
        ...

    def scan_test_gaps(self) -> list[QAIssue]:
        """Find features with test_count=0."""
        features = db.execute("""
            SELECT feature_id, name FROM feature_capabilities
            WHERE test_count = 0 AND passes = true
        """)
        # Features marked passing but have no tests = risk
        ...

    def upsert_issues(self, issues: list[QAIssue]):
        """Insert new issues, update last_detected_at for existing."""
        ...

    def auto_resolve_missing(self, detected_issue_ids: list[str]):
        """Mark issues as resolved if no longer detected."""
        ...

    def take_snapshot(self):
        """Daily snapshot for trend tracking."""
        ...
```

### 1.5 Celery Task

```python
# backend/app/tasks/qa_tasks.py

@celery_app.task(bind=True, name="tasks.daily_qa_scan")
def daily_qa_scan(self):
    """Run daily at 04:00 UTC, after capability scans."""
    scanner = QAScanner()
    issues = scanner.scan_all()
    scanner.upsert_issues(issues)
    scanner.take_snapshot()
    return {"issues_found": len(issues)}
```

### 1.6 Frontend Component

```tsx
// frontend/components/qa/QATab.tsx

export function QATab() {
  const { data: summary } = useQuery(['qa-summary'], fetchQASummary);
  const { data: issues } = useQuery(['qa-issues'], fetchQAIssues);
  const { data: trends } = useQuery(['qa-trends'], fetchQATrends);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard title="Total Issues" value={summary.total} trend={summary.trend} />
        <SummaryCard title="Critical" value={summary.by_severity.critical} variant="critical" />
        <SummaryCard title="Resolved This Week" value={summary.resolved_this_week} variant="success" />
        <SummaryCard title="Added This Week" value={summary.added_this_week} variant={summary.added_this_week > summary.resolved_this_week ? "warning" : "neutral"} />
      </div>

      {/* Trend Chart */}
      <TrendChart data={trends.snapshots} />

      {/* Issue Filters */}
      <div className="flex gap-2">
        <CategoryFilter />
        <SeverityFilter />
        <ResolvedFilter />
        <Button onClick={triggerScan}>Scan Now</Button>
      </div>

      {/* Issues Table */}
      <QAIssuesTable issues={issues} onResolve={handleResolve} onFalsePositive={handleFalsePositive} />
    </div>
  );
}
```

### 1.7 Navigation Update

```tsx
// frontend/components/Navigation.tsx - add QA tab

// In capabilities page tabs:
<TabsTrigger value="qa">QA</TabsTrigger>

// Tab content:
<TabsContent value="qa">
  <QATab />
</TabsContent>
```

---

## Part 2: /clean_it Command

### 2.1 Command File

```markdown
# .claude/commands/clean_it.md

---
description: Remove bloat - dead code, orphan files, stale data, unused features
---

# /clean_it - Deletion-Focused Cleanup

**Philosophy**: If in doubt, delete it. Code that doesn't exist can't have bugs.

---

## What This Command Does

1. **Scans** for deletable items (dead code, orphan files, stale data)
2. **Lists** candidates with confidence level
3. **Deletes** safe items automatically
4. **Asks** for confirmation on uncertain items
5. **Reports** what was removed

---

## Flags

| Flag | Effect |
|------|--------|
| (none) | Interactive - asks before deleting uncertain items |
| `--dry-run` | Show what would be deleted, don't delete |
| `--force` | Delete all without asking (use carefully) |
| `--category X` | Only clean specific category |

---

## Categories

| Category | Detection | Auto-Delete? |
|----------|-----------|--------------|
| `dead_imports` | ruff F401 | YES |
| `unused_vars` | ruff F841 | YES |
| `orphan_files` | Not imported anywhere | ASK |
| `empty_files` | 0 lines or only imports | YES |
| `stale_qa_issues` | Resolved >30 days ago | YES |
| `feat_debt` | FEAT-DEBT-* entries | ASK |
| `completed_fix_tasks` | [FIX] tasks marked complete | YES |
| `old_migrations_backup` | .bak files in migrations | YES |
| `temp_files` | /tmp/portfolio-ai-* | YES |

---

## Execution Steps

### Step 1: Scan

```bash
# Dead imports
ruff check backend/app --select F401 --output-format json > /tmp/dead_imports.json

# Unused variables
ruff check backend/app --select F841 --output-format json > /tmp/unused_vars.json

# Orphan files (custom scan)
# ... find .py files not imported anywhere

# FEAT-DEBT entries
curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | \
  jq '[.features[] | select(.feature_id | startswith("FEAT-DEBT"))]'

# Completed [FIX] tasks
curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | \
  jq '[.features[].tasks[]? | select(.completed == true and (.description | contains("[FIX]")))]'
```

### Step 2: Categorize by Confidence

| Confidence | Criteria | Action |
|------------|----------|--------|
| HIGH | Detected by linter, empty file, temp file | Auto-delete |
| MEDIUM | Orphan file but recently modified | Ask user |
| LOW | FEAT-DEBT with incomplete tasks | Ask user |

### Step 3: Execute Deletions

```python
# Auto-delete high confidence
for item in high_confidence:
    if item.type == "dead_import":
        run(f"ruff check {item.file} --select F401 --fix")
    elif item.type == "empty_file":
        os.remove(item.path)
    elif item.type == "temp_file":
        os.remove(item.path)

# Ask for medium/low confidence
for item in needs_confirmation:
    response = ask_user(f"Delete {item.path}? ({item.reason})")
    if response == "yes":
        delete(item)
```

### Step 4: Update QA Issues

```bash
# Mark resolved in qa_issues table
curl -X PATCH "http://localhost:8000/api/qa/issues/{id}/resolve" \
  -d '{"resolved_by": "clean_it", "resolution_notes": "Deleted by /clean_it"}'
```

### Step 5: Report

```
/clean_it Summary:

Deleted (auto):
  - 23 unused imports (ruff --fix)
  - 5 unused variables (ruff --fix)
  - 2 empty files
  - 12 completed [FIX] tasks

Deleted (confirmed):
  - 3 orphan files
  - 1 FEAT-DEBT entry

Skipped (user declined):
  - backend/app/legacy/old_scorer.py (orphan but user kept)

Lines removed: ~450
Files removed: 5
QA issues resolved: 28

Next: Run tests to verify nothing broke
```

---

## Safety Rules

1. **NEVER delete** files in .git/
2. **NEVER delete** migration files (even old ones)
3. **NEVER delete** config files without asking
4. **NEVER delete** test files without asking
5. **ALWAYS run** `git status` before and after
6. **ALWAYS offer** to revert (`git checkout -- .`)

---

## Integration

- Run after `/do_it` completes a feature
- Run weekly as maintenance
- Results feed into QA tab trends

---

## Example Session

```
> /clean_it

Scanning for deletable items...

Found 45 items:

HIGH CONFIDENCE (will auto-delete):
  [1] 23 unused imports across 15 files
  [2] 5 unused variables across 3 files
  [3] 2 empty __init__.py files
  [4] 12 completed [FIX] tasks

MEDIUM CONFIDENCE (need confirmation):
  [5] backend/app/services/old_scorer.py - orphan file (not imported)
  [6] backend/app/utils/deprecated_helpers.py - orphan file
  [7] FEAT-DEBT-001 - fundamental ingestion success rate

Delete high confidence items? [Y/n] y
✓ Fixed 23 unused imports
✓ Fixed 5 unused variables
✓ Deleted 2 empty files
✓ Removed 12 completed [FIX] tasks

Delete backend/app/services/old_scorer.py? [y/N] y
✓ Deleted

Delete backend/app/utils/deprecated_helpers.py? [y/N] n
⏭ Skipped

Delete FEAT-DEBT-001? [y/N] y
✓ Deleted feature entry

Summary: 43 items cleaned, ~380 lines removed
Run `pytest` to verify nothing broke.
```
```

---

## Part 3: Anti-Bloat Rules for Existing Commands

### 3.1 Add to /audit_it

```markdown
## Anti-Bloat Rules (ADD TO audit_it.md)

### Phase 1.8: Bloat Detection (NEW - add after Phase 1.7)

**Check for bloat indicators:**

```bash
# Count FEAT-DEBT entries (should be 0)
DEBT_COUNT=$(curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | \
  jq '[.features[] | select(.feature_id | startswith("FEAT-DEBT"))] | length')

# Count [FIX] tasks that are completed but not deleted
FIX_COMPLETED=$(curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | \
  jq '[.features[].tasks[]? | select(.completed == true and (.description | contains("[FIX]")))] | length')

# Count features with >10 subtasks (over-specified)
OVER_SPECIFIED=$(curl -s 'http://localhost:8000/api/capabilities/features/?limit=500' | \
  jq '[.features[] | select((.tasks | length) > 10)] | length')
```

**Bloat thresholds:**
| Metric | Acceptable | Warning | Critical |
|--------|------------|---------|----------|
| FEAT-DEBT entries | 0 | 1-3 | >3 |
| Completed [FIX] tasks | 0 | 1-5 | >5 |
| Over-specified features | 0 | 1-3 | >3 |

**If bloat detected:**
- Do NOT create more tasks
- Recommend running `/clean_it` first
- Report in summary

### FORBIDDEN (ADD to existing section)

6. **NEVER create FEAT-DEBT-* entries** - Tech debt is not a feature
7. **NEVER leave completed [FIX] tasks** - Delete them after fixing
8. **NEVER auto-generate >5 tasks per feature** - If you need more, feature is too big
```

### 3.2 Add to /do_it

```markdown
## Anti-Bloat Rules (ADD TO do_it.md)

### Phase 6: Cleanup (NEW - add after feature completion)

**MANDATORY after every feature completion:**

```bash
# 1. Fix dead imports in files you touched
ruff check backend/app --select F401 --fix

# 2. Fix unused variables in files you touched
ruff check backend/app --select F841 --fix

# 3. Delete any [FIX] tasks you completed
curl -X DELETE "http://localhost:8000/api/capabilities/features/{id}/tasks/{fix_task_id}"

# 4. Check: Did you add files? List them.
git status --short | grep "^A"

# 5. Check: Are all added files necessary?
# If not, delete them now
```

**Before moving to next feature:**
- [ ] No new unused imports
- [ ] No new unused variables
- [ ] Completed [FIX] tasks deleted
- [ ] All new files are necessary

### FORBIDDEN (ADD to existing section)

- **NEVER leave [FIX] tasks after fixing** - Delete the task
- **NEVER create FEAT-DEBT entries** - Fix debt or note on existing feature
- **NEVER add files "for later"** - Only add what's needed now
```

### 3.3 Add to /task_it

```markdown
## Anti-Bloat Rules (ADD TO task_it.md)

### Before Creating Feature

**Check if this should be a feature:**

| Request Type | Create Feature? | Instead |
|--------------|-----------------|---------|
| Bug fix in existing feature | NO | Add subtask to existing feature |
| Tech debt cleanup | NO | Run /clean_it |
| "Add tests for X" | NO | Add subtask to feature X |
| Small enhancement | MAYBE | Consider subtask on parent feature |
| New capability | YES | Create feature |

### Limits

- **Max 5 subtasks** per feature (if you need more, split the feature)
- **Max 4 acceptance criteria** per feature (if you need more, split the feature)
- **No [FIX] prefix** in feature names - that's for subtasks only

### FORBIDDEN

- **NEVER create FEAT-DEBT-* entries** - Delete and fix, or add note to affected feature
- **NEVER create features for cleanup work** - Use /clean_it
- **NEVER over-specify** - 2-3 good criteria > 6 vague criteria
```

---

## Part 4: Trend Tracking

### 4.1 Metrics to Track (Daily Snapshot)

| Metric | Source | Why |
|--------|--------|-----|
| Total QA issues | qa_issues table | Overall health |
| Issues by severity | qa_issues table | Priority distribution |
| Issues by category | qa_issues table | Problem areas |
| Issues added (24h) | qa_issues.first_detected_at | Are we creating debt? |
| Issues resolved (24h) | qa_issues.resolved_at | Are we cleaning? |
| Lines of code | `find | wc -l` | Code growth |
| File count | `find | wc -l` | File sprawl |
| Table count | db_capabilities | Schema growth |
| Feature count | feature_capabilities | Feature sprawl |
| Passing features | feature_capabilities | Health |

### 4.2 Trend Indicators

| Indicator | Calculation | Display |
|-----------|-------------|---------|
| Improving | resolved_7d > added_7d | Green arrow up |
| Stable | resolved_7d ≈ added_7d (±10%) | Yellow dash |
| Degrading | added_7d > resolved_7d | Red arrow down |

### 4.3 Frontend Chart

```tsx
// TrendChart.tsx
<ResponsiveContainer width="100%" height={300}>
  <LineChart data={snapshots}>
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Legend />
    <Line type="monotone" dataKey="total" stroke="#8884d8" name="Total Issues" />
    <Line type="monotone" dataKey="critical" stroke="#ff0000" name="Critical" />
    <Line type="monotone" dataKey="resolved_cumulative" stroke="#00ff00" name="Resolved (cumulative)" />
  </LineChart>
</ResponsiveContainer>
```

---

## Implementation Order

### Phase 1: Database & Backend (Day 1)
1. [ ] Create migration for qa_issues and qa_snapshots tables
2. [ ] Create QAScanner service
3. [ ] Create /api/qa endpoints
4. [ ] Create daily_qa_scan Celery task

### Phase 2: Frontend (Day 2)
1. [ ] Create QATab component
2. [ ] Create QAIssuesTable component
3. [ ] Create TrendChart component
4. [ ] Add QA tab to Capabilities page navigation

### Phase 3: /clean_it Command (Day 3)
1. [ ] Create .claude/commands/clean_it.md
2. [ ] Test with --dry-run
3. [ ] Verify safety rules work

### Phase 4: Anti-Bloat Rules (Day 4)
1. [ ] Update audit_it.md with Phase 1.8 and forbidden rules
2. [ ] Update do_it.md with Phase 6 and forbidden rules
3. [ ] Update task_it.md with limits and forbidden rules

### Phase 5: Integration & Testing (Day 5)
1. [ ] Run /audit_it, verify bloat detection works
2. [ ] Run /clean_it --dry-run, verify detection works
3. [ ] Verify QA tab shows data
4. [ ] Verify trend chart populates after 2+ daily scans

---

## Success Criteria

- [ ] QA tab visible at /capabilities between Workflows and Sources
- [ ] QA issues detected and displayed
- [ ] Trend chart shows 7+ days of data
- [ ] /clean_it removes dead code safely
- [ ] /audit_it warns about bloat
- [ ] /do_it has mandatory cleanup phase
- [ ] No new FEAT-DEBT entries created
- [ ] Completed [FIX] tasks are deleted, not accumulated

---

## Files to Create/Modify

### New Files
- `backend/migrations/versions/XXX_qa_tables.sql`
- `backend/app/services/qa_scanner.py`
- `backend/app/api/qa.py`
- `backend/app/tasks/qa_tasks.py`
- `frontend/components/qa/QATab.tsx`
- `frontend/components/qa/QAIssuesTable.tsx`
- `frontend/components/qa/TrendChart.tsx`
- `.claude/commands/clean_it.md`

### Modified Files
- `backend/app/api/__init__.py` (add qa router)
- `backend/app/celery_config.py` (add daily_qa_scan schedule)
- `frontend/app/capabilities/page.tsx` (add QA tab)
- `.claude/commands/audit_it.md` (add anti-bloat rules)
- `.claude/commands/do_it.md` (add cleanup phase)
- `.claude/commands/task_it.md` (add limits)
