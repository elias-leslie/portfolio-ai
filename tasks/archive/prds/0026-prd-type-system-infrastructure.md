# PRD: Type System & Infrastructure Improvements

**Source**: CODE_AUDIT.md, DATABASE_AUDIT.md, INSTRUCTION_AUDIT.md (Remaining Items)
**Severity**: MEDIUM Priority
**Effort**: MEDIUM (6-8 hours total)
**Created**: 2025-11-03

---

## Introduction

**Current Issue**: Multiple medium-priority technical debt items affecting type safety, infrastructure reliability, and operational efficiency:
- 20+ `Any` type hints (band-aids masking proper types)
- Celery task results growing unbounded (6.5 MB table)
- Browser automation scripts not validated
- Pre-commit documentation duplicated

**Desired State**:
- Proper type hints throughout codebase
- Celery task retention policy preventing unbounded growth
- Validated browser automation tooling
- Consolidated pre-commit documentation

**Impact**:
- **Type safety**: IDE support, catch bugs early
- **Performance**: Prevent database bloat
- **Reliability**: Verified tooling, no runtime failures
- **Maintainability**: Single source of truth for docs

---

## Goals

1. **Type System**: Replace 20+ `Any` types with proper types (4-6 hours)
2. **Infrastructure**: Configure Celery result retention (30 min)
3. **Tooling**: Validate browser automation scripts (1-2 hours)
4. **Documentation**: Consolidate pre-commit checklists (30 min)

---

## Functional Requirements

### FR-1: Define DatabaseConnection Protocol
**Issue**: 18 instances of `conn: Any` in function signatures

**Solution**:
```python
# backend/app/storage/types.py (new file)
from typing import Protocol, Any

class DatabaseConnection(Protocol):
    """Protocol for database connection objects."""

    def execute(self, query: str, params: list | None = None) -> Any:
        """Execute SQL query."""
        ...

    def fetchdf(self) -> Any:
        """Fetch results as DataFrame."""
        ...

    def pl(self) -> Any:
        """Return Polars interface."""
        ...
```

**Files to update** (18 instances):
- app/watchlist/earnings.py
- app/watchlist/fundamentals.py
- app/watchlist/scoring.py
- app/watchlist/models.py
- app/watchlist/news.py
- app/watchlist/calculator.py (4 functions)
- app/storage/schema.py
- app/storage/connection.py

**Acceptance**:
- ✅ Protocol defined in storage/types.py
- ✅ All 18 `conn: Any` replaced with `conn: DatabaseConnection`
- ✅ mypy --strict passes
- ✅ No runtime errors

---

### FR-2: Replace Storage Type Hints
**Issue**: 2 instances of `storage: Any` in tasks/agent_tasks.py

**Solution**:
```python
from app.storage.connection import PortfolioStorage

# Replace:
def _setup_agent_tools(storage: Any) -> AgentTools:

# With:
def _setup_agent_tools(storage: PortfolioStorage) -> AgentTools:
```

**Acceptance**:
- ✅ Import PortfolioStorage properly
- ✅ 2 instances replaced
- ✅ mypy --strict passes

---

### FR-3: Configure Celery Result Retention
**Issue**: celery_taskmeta table is 6.5 MB and growing unbounded

**Solution**:
```python
# backend/app/celery_app.py
CELERY_RESULT_EXPIRES = 60 * 60 * 24 * 30  # 30 days

# Or in config
result_expires = 60 * 60 * 24 * 30  # 30 days
```

**Additional**: Document cleanup query
```sql
-- Manual cleanup if needed
DELETE FROM celery_taskmeta
WHERE date_done < NOW() - INTERVAL '30 days';
```

**Acceptance**:
- ✅ Celery config updated with result_expires
- ✅ Restart celery workers/beat
- ✅ Verify old results expire after 30 days
- ✅ Document manual cleanup query in OPERATIONS.md

---

### FR-4: Validate Browser Automation Scripts
**Issue**: CLAUDE.md assumes browser-automation skill exists without verification

**Solution**:
1. Create validation script
```bash
# scripts/validate-browser-automation.sh
#!/bin/bash
SKILL_DIR=~/.claude/skills/browser-automation

echo "Validating browser automation skill..."

# Check directory exists
if [ ! -d "$SKILL_DIR" ]; then
  echo "❌ Skill directory not found: $SKILL_DIR"
  exit 1
fi

# Check scripts exist and are executable
SCRIPTS=(
  "scripts/screenshot.js"
  "scripts/snapshot.js"
  "scripts/console.js"
  "scripts/network.js"
  "scripts/interact.js"
  "scripts/execute.js"
  "scripts/manage.js"
  "scripts/emulate.js"
  "scripts/performance.js"
  "scripts/expand-and-screenshot.js"
)

for script in "${SCRIPTS[@]}"; do
  SCRIPT_PATH="$SKILL_DIR/$script"
  if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Missing: $script"
    exit 1
  fi
  if [ ! -x "$SCRIPT_PATH" ]; then
    echo "⚠️  Not executable: $script"
    chmod +x "$SCRIPT_PATH"
  fi
  echo "✅ $script"
done

echo "✅ All browser automation scripts validated"
```

2. Add to SETUP.md
```markdown
### Verify Browser Automation
```bash
bash ~/portfolio-ai/scripts/validate-browser-automation.sh
```
```

3. Add existence check to do_it.md
```markdown
Before using browser automation:
- Run: bash ~/portfolio-ai/scripts/validate-browser-automation.sh
- If fails: Install from project .claude/skills/browser-automation/
```

**Acceptance**:
- ✅ Validation script created
- ✅ All 10 scripts exist and are executable
- ✅ Documentation updated in SETUP.md
- ✅ do_it.md references validation

---

### FR-5: Consolidate Pre-Commit Documentation
**Issue**: Pre-commit workflow duplicated in CLAUDE.md and DEVELOPMENT.md

**Solution**:
1. Make DEVELOPMENT.md canonical source (keep detailed version)
2. Replace CLAUDE.md section with link:
```markdown
## Pre-Commit Workflow

**See**: [DEVELOPMENT.md - Pre-Commit Checklist](docs/core/DEVELOPMENT.md#pre-commit-checklist)

Quick reference:
- `~/portfolio-ai/scripts/lint.sh` - Run all checks
- `cd ~/portfolio-ai/backend && pytest tests/` - Run tests
- Pre-commit hooks run automatically on commit
```

**Acceptance**:
- ✅ DEVELOPMENT.md has complete pre-commit documentation
- ✅ CLAUDE.md links to DEVELOPMENT.md
- ✅ No duplication
- ✅ Both docs remain useful

---

## Non-Goals

**Explicitly OUT OF SCOPE**:
- ❌ Code refactoring (PRD #0025)
- ❌ Database index creation (PRD #0024 - already done)
- ❌ Creating SQLAlchemy declarative models (LOW priority)
- ❌ Replacing ALL Any types (only the documented 20+ instances)

---

## Technical Considerations

### Type System
- Protocol added in Python 3.8, we use 3.13 ✅
- Protocol is structural (duck typing), safe to add
- mypy understands Protocol well

### Celery Configuration
- Need to restart workers after config change
- Existing results retained (not deleted retroactively)
- 30 days is industry standard

### Browser Automation
- Scripts are in project `.claude/skills/browser-automation/`
- Need to verify both user and project level skills
- May need to copy from project to user level

---

## Success Metrics

### Type System Compliance
- ✅ Zero `conn: Any` instances (18 replaced)
- ✅ Zero `storage: Any` instances (2 replaced)
- ✅ mypy --strict passes
- ✅ IDE autocomplete works for database connections

### Infrastructure Health
- ✅ Celery result_expires configured
- ✅ celery_taskmeta stops growing unbounded
- ✅ Old results auto-expire after 30 days

### Tooling Reliability
- ✅ All 10 browser automation scripts validated
- ✅ Validation script passes
- ✅ Documentation references validation

### Documentation Quality
- ✅ Pre-commit docs consolidated
- ✅ DEVELOPMENT.md is canonical source
- ✅ CLAUDE.md links properly
- ✅ No conflicts or duplication

---

## Implementation Approach

### Phase 1: Type System (4-6 hours)

**Step 1**: Create DatabaseConnection Protocol (30 min)
```bash
# Create new file
touch backend/app/storage/types.py

# Define Protocol
# Add to __init__.py exports
```

**Step 2**: Replace conn: Any (3-4 hours)
```bash
# Find all instances
grep -rn "conn: Any" backend/app/

# Replace systematically, file by file
# Run mypy after each file
# Fix any type errors revealed
```

**Step 3**: Replace storage: Any (30 min)
```bash
# Only 2 instances in agent_tasks.py
# Should be straightforward
```

**Step 4**: Verify (30 min)
```bash
mypy backend/app/ --strict
pytest backend/tests/ -v
```

---

### Phase 2: Celery Retention (30 min)

**Step 1**: Update celery_app.py (10 min)
```python
# Add result_expires setting
result_expires = 60 * 60 * 24 * 30
```

**Step 2**: Restart Celery (5 min)
```bash
bash ~/portfolio-ai/scripts/restart.sh
```

**Step 3**: Document in OPERATIONS.md (15 min)
```markdown
### Celery Task Result Retention
- Auto-expires after 30 days
- Manual cleanup query: [SQL]
```

---

### Phase 3: Browser Automation Validation (1-2 hours)

**Step 1**: Create validation script (30 min)

**Step 2**: Run validation (10 min)
```bash
bash ~/portfolio-ai/scripts/validate-browser-automation.sh
```

**Step 3**: Fix any missing/non-executable scripts (30 min)

**Step 4**: Update documentation (30 min)
- SETUP.md: Add validation step
- do_it.md: Reference validation before use

---

### Phase 4: Consolidate Pre-Commit Docs (30 min)

**Step 1**: Verify DEVELOPMENT.md is complete (10 min)

**Step 2**: Update CLAUDE.md (10 min)
- Replace section with link
- Keep quick reference

**Step 3**: Cross-check consistency (10 min)

---

## Risks & Mitigations

### Risk: mypy reveals new type errors
**Mitigation**:
- Fix incrementally, file by file
- Use `# type: ignore` sparingly as last resort
- Most issues should be straightforward (we're adding types, not changing logic)

### Risk: Celery config breaks tasks
**Mitigation**:
- Test with simple task after restart
- result_expires only affects result storage, not execution
- Can revert easily if issues

### Risk: Browser scripts missing
**Mitigation**:
- They exist in project `.claude/skills/`
- Validation script will identify gaps
- Can copy from project to user level if needed

---

## Testing Plan

### Type System
```bash
# After each file updated
mypy backend/app/[file].py --strict

# After all files
mypy backend/app/ --strict
pytest backend/tests/ -v

# Verify no runtime errors
# Should see improved IDE autocomplete
```

### Celery Retention
```bash
# Check config loaded
python -c "from app.celery_app import celery_app; print(celery_app.conf.result_expires)"
# Should output: 2592000 (30 days in seconds)

# After 30+ days (manual verification)
SELECT COUNT(*) FROM celery_taskmeta WHERE date_done < NOW() - INTERVAL '30 days';
# Should be 0 (auto-expired)
```

### Browser Automation
```bash
# Run validation
bash ~/portfolio-ai/scripts/validate-browser-automation.sh
# Should output: ✅ All browser automation scripts validated

# Test one script
node ~/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000 /tmp/test.png
# Should create screenshot
```

### Documentation
```bash
# Verify no duplication
diff <(grep -A 10 "Pre-Commit" CLAUDE.md) \
     <(grep -A 10 "Pre-Commit" docs/core/DEVELOPMENT.md)
# Should show: CLAUDE.md links to DEVELOPMENT.md

# Verify link works
grep "DEVELOPMENT.md#pre-commit" CLAUDE.md
# Should find link
```

---

## Dependencies

- Python 3.13 (for Protocol support)
- mypy installed
- Celery workers/beat running
- Browser automation skill installed (project level)
- Access to CLAUDE.md, DEVELOPMENT.md

---

## Estimated Effort Breakdown

| Task | Effort | Complexity |
|------|--------|------------|
| Define DatabaseConnection Protocol | 30 min | LOW |
| Replace 18 conn: Any instances | 3-4 hours | MEDIUM |
| Replace 2 storage: Any instances | 30 min | LOW |
| Configure Celery retention | 30 min | LOW |
| Create browser validation script | 30 min | LOW |
| Validate browser scripts | 30 min | LOW |
| Update documentation | 1 hour | LOW |
| Testing & verification | 1 hour | LOW |
| **TOTAL** | **6-8 hours** | **MEDIUM** |

**Recommended**: 2 work sessions
- Session 1: Type system (4-6 hours)
- Session 2: Infrastructure + docs (2 hours)

---

## Success Criteria Summary

✅ **COMPLETE when**:
1. DatabaseConnection Protocol defined
2. All 20 `Any` types replaced with proper types
3. mypy --strict passes
4. Celery result_expires configured (30 days)
5. Browser automation validation script created
6. All 10 browser scripts validated
7. Pre-commit docs consolidated (DEVELOPMENT.md canonical)
8. All tests pass
9. Documentation updated

---

## Follow-up Tasks

After this PRD:
- Monitor celery_taskmeta table size (should stop growing)
- Consider adding more Protocols for other duck-typed objects
- Run periodic browser automation validation

**This PRD completes the MEDIUM priority items** from all three audits.
