# Portfolio AI - Optimization Phase 2: Prevention & Autonomy

**Created**: 2025-11-03
**Status**: Ready for Implementation
**Estimated Effort**: HIGH (12-16 hours over 2-3 sessions)
**Goal**: Prevent tech debt BEFORE it's created + Maximum autonomy

---

## Context

**Current Issues**:
- ❌ Claude creates tech debt/bloat by making assumptions (not digging deep enough)
- ❌ Superpowers NOT installed (was assumed to exist)
- ❌ 11 pause cycles per PRD (context management issues)
- ❌ Continuous refactoring needed (reactive vs proactive quality)
- ❌ Manual approval gates slow development

**What Exists**:
- ✅ Browser automation skill (user + project level)
- ✅ Explore subagent (built-in)
- ✅ General-purpose subagent (built-in)
- ✅ /check_it command (runs Gemini analysis)
- ❌ No code-review capability
- ❌ No automatic dispatch triggers
- ❌ No prevention mechanisms

**Scope**: 853 markdown files, 68 Python files, 7 core docs, 19 database tables

---

## ⚠️ BACKUP & ROLLBACK PROCEDURES (MANDATORY)

**CRITICAL**: Create backups BEFORE making ANY changes. This allows easy rollback if optimization causes issues.

### Pre-Optimization Snapshot

**Run BEFORE starting any phase**:

```bash
# Create backup directory with timestamp
BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=~/portfolio-ai/backups/optimization-phase2-$BACKUP_DATE
mkdir -p $BACKUP_DIR

# Backup all instruction files
echo "Backing up instructions..."
cp -r ~/portfolio-ai/.claude/commands $BACKUP_DIR/commands-backup
cp ~/portfolio-ai/CLAUDE.md $BACKUP_DIR/CLAUDE.md.backup
cp -r ~/portfolio-ai/docs/core $BACKUP_DIR/docs-core-backup
cp -r ~/portfolio-ai/docs/reference $BACKUP_DIR/docs-reference-backup

# Create git snapshot
cd ~/portfolio-ai
git add -A
git stash push -m "Pre-optimization snapshot $BACKUP_DATE"
STASH_REF=$(git stash list | head -1 | cut -d: -f1)
echo "$STASH_REF" > $BACKUP_DIR/git-stash-ref.txt

# Create current state manifest
echo "=== Pre-Optimization State ===" > $BACKUP_DIR/STATE_MANIFEST.md
echo "Date: $(date)" >> $BACKUP_DIR/STATE_MANIFEST.md
echo "Git commit: $(git rev-parse HEAD)" >> $BACKUP_DIR/STATE_MANIFEST.md
echo "Git branch: $(git branch --show-current)" >> $BACKUP_DIR/STATE_MANIFEST.md
echo "" >> $BACKUP_DIR/STATE_MANIFEST.md
echo "## Files Backed Up" >> $BACKUP_DIR/STATE_MANIFEST.md
ls -lah $BACKUP_DIR >> $BACKUP_DIR/STATE_MANIFEST.md

# List command file sizes
echo "" >> $BACKUP_DIR/STATE_MANIFEST.md
echo "## Command Sizes (Pre-Optimization)" >> $BACKUP_DIR/STATE_MANIFEST.md
wc -l .claude/commands/*.md >> $BACKUP_DIR/STATE_MANIFEST.md

echo "✅ Backup created: $BACKUP_DIR"
echo "Git stash: $STASH_REF"
echo "To rollback: bash ~/portfolio-ai/backups/rollback-optimization.sh $BACKUP_DATE"
```

**Verification**:
- [ ] Backup directory created with timestamp
- [ ] All instruction files backed up
- [ ] Git stash created
- [ ] State manifest generated
- [ ] Backup location documented

---

### Create Rollback Script

**Create once before starting**:

```bash
cat > ~/portfolio-ai/backups/rollback-optimization.sh << 'ROLLBACK_EOF'
#!/bin/bash
# Rollback optimization changes

if [ -z "$1" ]; then
    echo "Usage: bash rollback-optimization.sh <backup-timestamp>"
    echo "Available backups:"
    ls -1 ~/portfolio-ai/backups/ | grep "optimization-phase2"
    exit 1
fi

BACKUP_DIR=~/portfolio-ai/backups/optimization-phase2-$1

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup not found at $BACKUP_DIR"
    exit 1
fi

echo "⚠️  WARNING: This will restore files to pre-optimization state"
echo "Backup location: $BACKUP_DIR"
echo ""
read -p "Continue with rollback? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

cd ~/portfolio-ai

# Restore instruction files
echo "Restoring instruction files..."
rm -rf .claude/commands
cp -r $BACKUP_DIR/commands-backup .claude/commands
cp $BACKUP_DIR/CLAUDE.md.backup CLAUDE.md
rm -rf docs/core
cp -r $BACKUP_DIR/docs-core-backup docs/core
rm -rf docs/reference
cp -r $BACKUP_DIR/docs-reference-backup docs/reference

# Restore git state if stash exists
if [ -f "$BACKUP_DIR/git-stash-ref.txt" ]; then
    STASH_REF=$(cat $BACKUP_DIR/git-stash-ref.txt)
    echo "Restoring git state from $STASH_REF..."
    git stash apply $STASH_REF
fi

# Remove any new files created during optimization
echo "Cleaning up optimization artifacts..."
rm -rf ~/portfolio-ai/.claude/subagents 2>/dev/null
rm -rf ~/portfolio-ai/.claude/skills/code-quality 2>/dev/null

echo ""
echo "✅ Rollback complete!"
echo "Restored from: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "1. Review changes: git status"
echo "2. Test that commands still work: /do_it --help"
echo "3. If satisfied, commit: git add -A && git commit -m 'Rollback optimization'"
ROLLBACK_EOF

chmod +x ~/portfolio-ai/backups/rollback-optimization.sh
echo "✅ Rollback script created: ~/portfolio-ai/backups/rollback-optimization.sh"
```

**Verification**:
- [ ] Rollback script created
- [ ] Script is executable
- [ ] Script tested with dry-run

---

### Phase-by-Phase Backup Strategy

**Before each phase, create incremental backup**:

```bash
# Phase 1 backup (before autonomy changes)
PHASE="phase1-autonomy"
cp -r ~/portfolio-ai/.claude/commands ~/portfolio-ai/backups/$PHASE-$(date +%Y%m%d-%H%M%S)

# Phase 2 backup (before audit changes)
PHASE="phase2-audit"
cp -r ~/portfolio-ai/docs ~/portfolio-ai/backups/$PHASE-$(date +%Y%m%d-%H%M%S)

# Phase 3 backup (before prevention mechanisms)
PHASE="phase3-prevention"
tar czf ~/portfolio-ai/backups/$PHASE-$(date +%Y%m%d-%H%M%S).tar.gz \
  ~/portfolio-ai/.claude/commands \
  ~/portfolio-ai/.claude/subagents \
  ~/portfolio-ai/.claude/skills

# After each phase completes successfully
git add -A
git commit -m "feat: optimization $PHASE complete (backed up)"
```

---

### Testing After Each Phase

**Mandatory validation before proceeding to next phase**:

```bash
# Test 1: Verify commands load
cd ~/portfolio-ai
ls -la .claude/commands/  # Should see all expected .md files

# Test 2: Verify no syntax errors in commands
for cmd in .claude/commands/*.md; do
    echo "Checking $cmd..."
    head -20 "$cmd" | grep -E "^---$" || echo "⚠️  Warning: No frontmatter in $cmd"
done

# Test 3: Try running a simple command
# (Just verify it loads, don't execute full workflow)
echo "Commands should be accessible via / prefix"

# Test 4: Verify git status is clean or as expected
git status

# Test 5: Check file sizes didn't explode
echo "Command sizes after changes:"
wc -l .claude/commands/*.md | tail -1

# If ANY test fails: ROLLBACK IMMEDIATELY
# bash ~/portfolio-ai/backups/rollback-optimization.sh <backup-timestamp>
```

---

### Rollback Decision Matrix

**When to rollback**:

| Issue | Severity | Action |
|-------|----------|--------|
| Commands fail to load | 🔴 CRITICAL | Rollback immediately |
| Syntax errors in commands | 🔴 CRITICAL | Rollback immediately |
| Claude behavior broken | 🔴 CRITICAL | Rollback immediately |
| Increased pause cycles | ⚠️ HIGH | Complete phase, measure, then decide |
| Unclear instructions | ⚠️ MEDIUM | Fix specific issue, don't rollback all |
| Minor typos/formatting | ✅ LOW | Fix in place |

**Rollback command**:
```bash
# List available backups
ls -1 ~/portfolio-ai/backups/ | grep optimization-phase2

# Rollback to specific backup
bash ~/portfolio-ai/backups/rollback-optimization.sh <timestamp>

# Example:
bash ~/portfolio-ai/backups/rollback-optimization.sh 20251103-120000
```

---

### Emergency Rollback (If Script Fails)

**Manual restoration**:

```bash
# 1. Find latest backup
ls -lt ~/portfolio-ai/backups/ | grep optimization-phase2 | head -1

# 2. Manually restore files
BACKUP=optimization-phase2-<timestamp>
cp -r ~/portfolio-ai/backups/$BACKUP/commands-backup/* ~/.claude/commands/
cp ~/portfolio-ai/backups/$BACKUP/CLAUDE.md.backup ~/portfolio-ai/CLAUDE.md

# 3. Verify restoration
git status
git diff .claude/commands/

# 4. If good, commit
git add -A
git commit -m "Emergency rollback from optimization phase 2"
```

---

## Phase 1: Immediate Autonomy (2-3 hours)

**⚠️ BEFORE STARTING: Run pre-optimization snapshot (see above)**

### 1.1 Add Automatic Dispatch Triggers to /do_it.md

**Location**: `.claude/commands/do_it.md` (after line 13, before "## Database Information")

**Add this section**:

```markdown
## Automatic Subagent Dispatch (NEVER ASK - JUST DO)

**Critical Rule**: When these conditions are met, IMMEDIATELY dispatch subagents WITHOUT asking for permission. This is MANDATORY for autonomy.

### Discovery Tasks (Explore Subagent)
**Trigger**: Task includes "find all", "search for", "locate", or requires checking >5 files

**Action**: IMMEDIATELY dispatch Explore subagent with:
```
Prompt: "Find ALL instances of [pattern] in [directory].
         Return complete list: file:line:code
         Include edge cases and variations"
```

**Examples**:
- "Fix datetime.now() in preferences.py" → SEARCH ENTIRE codebase first
- "Update API endpoint" → SEARCH for all references first
- "Remove deprecated function" → FIND all usages first

**Why**: Prevents partial fixes that create tech debt

### Test Generation (General Subagent)
**Trigger**: Implemented >50 lines of new code OR new function/class added

**Action**: IMMEDIATELY dispatch general-purpose subagent with:
```
Prompt: "Generate comprehensive tests for [function/class] in [file].
         Read the implementation first.
         Cover: happy path, edge cases, error conditions, boundary values.
         Follow project test patterns in tests/conftest.py.
         Return complete test file content."
```

**Run in PARALLEL**: Don't wait for tests, continue implementation

**Why**: Comprehensive tests, not rushed afterthoughts

### Code Review (Built-in)
**Trigger**: Parent task complete, about to commit

**Action**:
1. Run `ruff check` and `mypy` on changed files
2. Read changed files with fresh eyes
3. Check against coding standards (500-line soft limit, type hints, no `Any`)
4. Verify no SQL injection (f-strings with user input)
5. Check for duplication (DRY principle)

**Fix critical issues immediately**, commit only after clean

**Why**: Catch quality issues before they're committed

### Context Management
**Trigger**: Context usage >100k tokens (~50% of 200k limit)

**Action**: IMMEDIATELY dispatch ALL remaining independent tasks to subagents:
- Test generation → general subagent
- Documentation review → general subagent
- Pattern searches → Explore subagent
- Continue ONLY core implementation in main agent

**Why**: Prevents context exhaustion and pauses

### UI Testing (Browser Automation Skill)
**Trigger**: ANY UI changes detected (frontend files modified)

**Action**: IMMEDIATELY use browser automation skill:
```bash
# NO approval needed - just run
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/[page] /tmp/ui-before.png

# After changes:
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/[page] /tmp/ui-after.png

# Check console errors:
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/console.js \
  http://192.168.8.233:3000/[page] 5000
```

**Why**: 0-context verification, catch UI regressions immediately
```

**Verification**:
- [ ] Added automatic dispatch section (85 lines)
- [ ] Triggers are MANDATORY (never ask permission)
- [ ] All 5 categories covered

---

### 1.2 Remove Approval Gates from /do_it.md

**Current behavior**: Pause after each sub-task for approval
**New behavior**: Work through all sub-tasks, pause only for parent task review

**Location**: `.claude/commands/do_it.md` lines 190-220 (Completion Protocol)

**Changes**:
- Remove: "Ask: 'Ready for 1.2? (yes/y)'"
- Add: "Continue automatically through all sub-tasks [1.1, 1.2, 1.3...]"
- Keep: Pause for parent task review after verification

**Verification**:
- [ ] Removed approval gates on sub-tasks
- [ ] Keep verification gate on parent tasks
- [ ] Updated completion protocol section

---

### 1.3 Delete Unused /next_it Command

**Action**: Remove unused 70-line command

```bash
cd ~/portfolio-ai
git rm .claude/commands/next_it.md
git commit -m "refactor: remove unused /next_it command (saves 1.2k tokens)"
```

**Verification**:
- [ ] Deleted .claude/commands/next_it.md
- [ ] No references remain in other docs
- [ ] Committed

---

## Phase 2: Comprehensive Solution Audit (4-6 hours)

**⚠️ BEFORE STARTING: Create Phase 2 incremental backup**:
```bash
PHASE="phase2-audit"
cp -r ~/portfolio-ai/docs ~/portfolio-ai/backups/$PHASE-$(date +%Y%m%d-%H%M%S)
echo "✅ Phase 2 backup created"
```

**Purpose**: Find ALL tech debt, bloat, assumptions, legacy code across ENTIRE solution before it causes more problems.

### 2.1 Instruction Audit (Deep Review)

**Scan all instruction files for**:
- Redundancy (same content in multiple places)
- Assumptions (documented without verification)
- Outdated references (legacy database when using PostgreSQL)
- Missing automation opportunities
- Conflicting directives

**Files to audit**:
- [ ] .claude/commands/*.md (7 files)
- [ ] CLAUDE.md
- [ ] docs/core/*.md (7 files)
- [ ] docs/reference/*.md (3 files)

**Output**: `docs/core/INSTRUCTION_AUDIT.md` with findings + fixes

**Checks**:
```bash
# Find duplicate sections across commands
for file in .claude/commands/*.md; do
  echo "=== $(basename $file) ==="
  grep -h "^## " "$file"
done | sort | uniq -d

# Find assumptions in docs
grep -r "should\|probably\|assume\|typically" docs/core/ .claude/commands/

# Find outdated tech references
grep -ri "legacy-db\|sqlite" docs/ CLAUDE.md

# Check for conflicting instructions
grep -r "NEVER\|ALWAYS\|MUST" docs/core/ .claude/commands/ | \
  grep -v "Binary file" | wc -l
```

---

### 2.2 Code Bloat & Tech Debt Audit

**Scan all Python files for**:
- Files >500 lines (soft limit violations)
- Duplicate logic (DRY violations)
- `Any` type hints (band-aids)
- `TODO`, `FIXME`, `HACK` comments
- Commented-out code (legacy)
- Functions >50 lines
- Cyclomatic complexity >10

**Files to audit**: 68 Python files in backend/app/

**Commands**:
```bash
cd ~/portfolio-ai/backend

# Files exceeding limits
find app -name "*.py" -exec wc -l {} \; | sort -rn | head -20

# Find Any types (band-aids)
grep -rn "Any" app/ --include="*.py"

# Find TODOs/FIXMEs
grep -rn "TODO\|FIXME\|HACK\|XXX" app/ --include="*.py"

# Find commented code
grep -rn "^[[:space:]]*#.*def \|^[[:space:]]*#.*class " app/ --include="*.py"

# Find long functions (>50 lines)
# (Use ast-grep or manual review)

# Use Gemini for comprehensive analysis
mcp__gemini-cli__ask-gemini \
  prompt="@backend/app/**/*.py Find: files >500 lines, Any types, TODOs, duplicate logic, long functions (>50 lines)"
```

**Output**: `docs/core/CODE_AUDIT.md` with:
- All violations listed (file:line)
- Severity (critical/high/medium/low)
- Recommended fixes
- Effort estimates

---

### 2.3 Database Schema Integrity Audit

**Scan for**:
- Tables without indexes on foreign keys
- Missing constraints (NOT NULL, CHECK)
- SQLAlchemy models not matching actual schema
- Unused tables/columns
- Missing migrations for recent changes
- Query performance issues (missing indexes)

**Commands**:
```bash
# Get actual schema
psql portfolio_ai -c "\d+" > /tmp/actual-schema.txt

# List all tables
psql portfolio_ai -c "\dt"

# Check indexes
psql portfolio_ai -c "
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;"

# Find missing indexes on FKs
psql portfolio_ai -c "
SELECT
    tc.table_name,
    kcu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = tc.table_name
    AND indexdef LIKE '%' || kcu.column_name || '%'
);"

# Check table sizes
psql portfolio_ai -c "
SELECT
    schemaname AS schema,
    tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Use Gemini for model comparison**:
```bash
mcp__gemini-cli__ask-gemini \
  prompt="@backend/app/storage/schema.py Compare SQLAlchemy models with actual schema in /tmp/actual-schema.txt. Find mismatches."
```

**Output**: `docs/core/DATABASE_AUDIT.md`

---

### 2.4 Test Coverage & Quality Audit

**Scan for**:
- Modules <80% coverage (target threshold)
- Tests that don't actually test anything (empty asserts)
- Skipped tests without explanation
- Slow tests (>1 second)
- Tests with hard-coded values (not fixtures)
- Missing edge case coverage

**Commands**:
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate

# Get detailed coverage report
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# Find modules below 80% coverage
pytest tests/ --cov=app --cov-report=term | grep -E "^app/" | awk '$4 < 80'

# Find slow tests
pytest tests/ --durations=20

# Find skipped tests
pytest tests/ -v | grep SKIP

# Find empty asserts
grep -rn "assert True\|pass$" tests/ --include="*test*.py"
```

**Output**: `docs/core/TEST_AUDIT.md`

---

### 2.5 Documentation Currency Audit

**Scan for**:
- Features implemented but not documented
- API endpoints missing from API_REFERENCE.md
- Outdated examples (old code patterns)
- Broken internal links
- Stale timestamps (>30 days old)

**Commands**:
```bash
# Check all API endpoints
grep -r "@router" backend/app/api/ | wc -l  # Actual endpoints
grep -c "### " docs/core/API_REFERENCE.md    # Documented endpoints

# Find stale docs (>30 days)
find docs/core -name "*.md" -mtime +30

# Find broken links
grep -rh "\[.*\](.*\.md)" docs/ .claude/commands/ | \
  sed 's/.*(\(.*\.md\)).*/\1/' | \
  while read link; do
    [ ! -f "$link" ] && echo "Broken: $link"
  done

# Find references to old tech
grep -ri "legacy-db\|sqlite\|localhost:8000" docs/
```

**Use Gemini for comprehensive check**:
```bash
mcp__gemini-cli__ask-gemini \
  prompt="@docs/core/*.md @backend/app/api/*.py Find: undocumented endpoints, outdated examples, stale content"
```

**Output**: `docs/core/DOCUMENTATION_AUDIT.md`

---

### 2.6 Configuration & Dependencies Audit

**Scan for**:
- Unused dependencies (in pyproject.toml but never imported)
- Version drift (tool versions not matching)
- Hardcoded values (should be config)
- Environment variables not documented
- Dead configuration options

**Commands**:
```bash
# Find unused dependencies
cd ~/portfolio-ai/backend
for pkg in $(grep "^[a-z]" pyproject.toml | cut -d= -f1 | tr -d '"' | tr -d ' '); do
  grep -r "import $pkg\|from $pkg" app/ tests/ >/dev/null || echo "Unused: $pkg"
done

# Check version sync
~/portfolio-ai/scripts/validate-versions.sh

# Find hardcoded values
grep -rn "localhost\|127.0.0.1\|8000\|3000\|5432" backend/app/ --include="*.py" | \
  grep -v "# config" | wc -l

# Find env vars in code
grep -rn "os.environ\|os.getenv" backend/app/ --include="*.py"

# Cross-reference with OPERATIONS.md
# (manual check)
```

**Output**: `docs/core/CONFIG_AUDIT.md`

---

## Phase 3: Prevention Mechanisms (4-6 hours)

**⚠️ BEFORE STARTING: Create Phase 3 incremental backup**:
```bash
PHASE="phase3-prevention"
tar czf ~/portfolio-ai/backups/$PHASE-$(date +%Y%m%d-%H%M%S).tar.gz \
  ~/portfolio-ai/.claude/commands \
  ~/portfolio-ai/docs/core \
  ~/portfolio-ai/docs/reference
echo "✅ Phase 3 backup created"
```

**Purpose**: Stop tech debt BEFORE it's created (proactive vs reactive)

### 3.1 Create Pre-Implementation Checklist Subagent

**Purpose**: Forces me to verify assumptions BEFORE coding

**Create**: `~/portfolio-ai/.claude/subagents/pre-check.md`

```markdown
---
name: pre-implementation-check
description: Verify assumptions before implementation to prevent tech debt
allowed-tools: Read, Grep, Glob, Bash
---

# Pre-Implementation Checklist Subagent

**Purpose**: VERIFY assumptions before implementation, prevent tech debt

## When to Invoke

BEFORE implementing ANY feature/fix that:
- Modifies >50 lines
- Touches >3 files
- Changes database schema
- Modifies API contracts
- Affects UI behavior

## Checklist

### 1. Understand Current State
- [ ] Read ALL related files (not just the one mentioned)
- [ ] Understand current architecture/pattern
- [ ] Find similar implementations (grep for patterns)
- [ ] Check recent changes (git log for context)

### 2. Verify Assumptions
- [ ] Does the problem exist where I think it does?
- [ ] Is the proposed solution aligned with existing patterns?
- [ ] Are there edge cases I haven't considered?
- [ ] Will this change break existing functionality?

### 3. Check for Existing Solutions
- [ ] Does a helper function already exist?
- [ ] Is there a pattern I should follow?
- [ ] Can I reuse code instead of duplicating?
- [ ] Is there a library/utility that solves this?

### 4. Impact Analysis
- [ ] What files will this change affect? (grep for usages)
- [ ] Are there tests that will break?
- [ ] Does documentation need updating?
- [ ] Are there database migrations needed?

### 5. Quality Gates
- [ ] Will this exceed file size limits?
- [ ] Am I adding `Any` types (band-aid)?
- [ ] Am I using TODO/FIXME (deferring work)?
- [ ] Am I copying code (DRY violation)?

## Output Format

Return structured report:

```markdown
## Pre-Implementation Check: [Feature Name]

### Current State
- Files affected: [list]
- Existing pattern: [description]
- Similar implementations: [file:line references]

### Assumptions Verified
✅ [Assumption 1]: Verified by [evidence]
❌ [Assumption 2]: INVALID - [correction]
⚠️ [Assumption 3]: UNCERTAIN - needs clarification

### Recommended Approach
[Implementation strategy based on verification]

### Risks & Mitigations
- Risk: [description] | Mitigation: [solution]

### Files to Modify
- [ ] file1.py - [reason]
- [ ] file2.py - [reason]
- [ ] tests/test_file.py - [reason]

### Quality Checklist
- [ ] Within file size limits
- [ ] No `Any` types introduced
- [ ] No duplicate code
- [ ] Follows existing patterns
```

## Examples

### Example 1: "Fix datetime.now() in preferences.py"

**Pre-Check Actions**:
1. Search ENTIRE codebase for datetime.now() (not just preferences.py)
2. Find ALL instances across ALL files
3. Check if pattern already exists for UTC datetime
4. Verify test coverage for datetime handling

**Output**:
```markdown
## Pre-Implementation Check: Fix datetime.now() for UTC

### Current State
- 17 instances found across 5 files (not just preferences.py!)
- Existing pattern in storage/connection.py uses datetime.now(timezone.utc)
- No centralized time utility (should create one)

### Assumptions Verified
❌ ASSUMPTION: "Only preferences.py affected" - INVALID
   Found 17 instances: preferences.py (3), agents/base.py (7), etc.

✅ ASSUMPTION: "Should use UTC" - VERIFIED
   Project uses UTC throughout (storage/connection.py:45)

### Recommended Approach
1. Create utility: app/utils/time_utils.py with utc_now()
2. Replace ALL 17 instances with utility call
3. Add tests for utility
4. Update docs if datetime handling is mentioned

### Files to Modify
- [ ] app/utils/time_utils.py - create new utility
- [ ] app/api/preferences.py - 3 instances
- [ ] app/agents/base.py - 7 instances
- [ ] app/analytics/paper_trading.py - 2 instances
- [ ] app/api/health.py - 5 instances
- [ ] tests/test_time_utils.py - test new utility
```

**Result**: Comprehensive fix, not partial band-aid
```

**Verification**:
- [ ] Created ~/portfolio-ai/.claude/subagents/pre-check.md
- [ ] Checklist covers all assumption categories
- [ ] Examples show comprehensive approach

---

### 3.2 Update /do_it to MANDATE Pre-Check

**Location**: `.claude/commands/do_it.md` (after automatic dispatch section)

**Add**:

```markdown
## Pre-Implementation Check (MANDATORY)

**Before implementing ANY task that**:
- Modifies >50 lines
- Touches >3 files
- Changes database/API/UI

**You MUST dispatch pre-implementation-check subagent**:

```bash
Task(
  subagent_type="general-purpose",
  prompt="Use pre-implementation checklist from ~/portfolio-ai/.claude/subagents/pre-check.md
          Task: [description]
          Verify ALL assumptions, find ALL affected files, check for existing patterns.
          Return structured pre-check report."
)
```

**DO NOT PROCEED with implementation until**:
- All assumptions verified
- All affected files identified
- Existing patterns understood
- Quality gates passed

**If pre-check reveals issues**:
- Update task plan based on findings
- Ask user if scope change is acceptable
- Proceed only after confirmation

**This is NON-NEGOTIABLE**: Prevents tech debt at source
```

**Verification**:
- [ ] Added mandatory pre-check section
- [ ] Clear triggers for when to use
- [ ] Blocks implementation until verified

---

### 3.3 Create Code Quality Skill (0-Context)

**Purpose**: Instant quality checks with 0 context cost

**Create**: `~/portfolio-ai/.claude/skills/code-quality/`

```bash
mkdir -p ~/portfolio-ai/.claude/skills/code-quality/scripts

# Create SKILL.md
cat > ~/portfolio-ai/.claude/skills/code-quality/SKILL.md << 'EOF'
---
name: code-quality
description: Instant code quality checks with 0 context cost (file size, complexity, duplication, type hints)
allowed-tools: Bash, Read
---

# Code Quality Skill

**Purpose**: Fast, 0-context quality checks before committing

## Available Scripts

### 1. check-file-sizes.sh
Find files exceeding size limits

### 2. find-duplicates.sh <directory>
Find duplicate code blocks (DRY violations)

### 3. check-type-hints.sh <file>
Verify all functions have type hints

### 4. find-any-types.sh <directory>
Find `Any` type hints (band-aids)

### 5. check-complexity.sh <file>
Calculate cyclomatic complexity

### 6. find-todos.sh <directory>
Find TODO/FIXME/HACK comments

### 7. find-commented-code.sh <directory>
Find commented-out code (legacy)

### 8. quality-report.sh <directory>
Run all checks, generate report
EOF

# Create scripts (implementations)
cat > ~/portfolio-ai/.claude/skills/code-quality/scripts/check-file-sizes.sh << 'EOF'
#!/bin/bash
# Find Python files exceeding size limits
find "${1:-.}" -name "*.py" -type f -exec wc -l {} \; | \
  awk '$1 > 500 {print $2 " (" $1 " lines) - EXCEEDS 500-line soft limit"}' | \
  sort -t'(' -k2 -rn
EOF

cat > ~/portfolio-ai/.claude/skills/code-quality/scripts/find-any-types.sh << 'EOF'
#!/bin/bash
# Find Any type hints (band-aids)
grep -rn "from typing import.*Any\|: Any\|-> Any" "${1:-.}" --include="*.py" | \
  grep -v "TYPE_CHECKING"
EOF

cat > ~/portfolio-ai/.claude/skills/code-quality/scripts/find-todos.sh << 'EOF'
#!/bin/bash
# Find TODO/FIXME/HACK comments
grep -rn "TODO\|FIXME\|HACK\|XXX" "${1:-.}" --include="*.py" | \
  sed 's/:/ - /' | \
  sort
EOF

cat > ~/portfolio-ai/.claude/skills/code-quality/scripts/quality-report.sh << 'EOF'
#!/bin/bash
# Run all quality checks
DIR="${1:-.}"
echo "=== Code Quality Report ==="
echo
echo "## Files Exceeding Size Limits"
bash "$(dirname "$0")/check-file-sizes.sh" "$DIR"
echo
echo "## Any Types Found (Band-Aids)"
bash "$(dirname "$0")/find-any-types.sh" "$DIR" | wc -l
echo
echo "## TODOs/FIXMEs Found"
bash "$(dirname "$0")/find-todos.sh" "$DIR" | wc -l
echo
echo "=== Summary ==="
EOF

chmod +x ~/portfolio-ai/.claude/skills/code-quality/scripts/*.sh
```

**Verification**:
- [ ] Created skill directory structure
- [ ] Created SKILL.md with documentation
- [ ] Created 7 quality check scripts
- [ ] All scripts executable
- [ ] Tested on backend/app/

---

### 3.4 Create TestGen Specialized Subagent

**Purpose**: Comprehensive test generation (not rushed)

**Create**: `~/portfolio-ai/.claude/subagents/testgen.md`

```markdown
---
name: test-generator
description: Generate comprehensive test suites with edge cases (specialized, not rushed)
allowed-tools: Read, Grep, Glob
---

# Test Generation Specialist Subagent

**Purpose**: Generate COMPREHENSIVE tests (not rushed afterthoughts)

## When to Invoke

After implementing:
- Any new function (>10 lines)
- Any new class
- Any API endpoint
- Any database model
- Any utility

## Test Generation Protocol

### 1. Read Implementation
- Read the actual code being tested
- Understand inputs, outputs, side effects
- Identify edge cases and error conditions

### 2. Read Project Test Patterns
- Check tests/conftest.py for fixtures
- Find similar tests in same module
- Follow project conventions

### 3. Generate Comprehensive Tests

**Coverage Requirements**:
- ✅ Happy path (normal usage)
- ✅ Edge cases (boundary values, empty inputs)
- ✅ Error conditions (invalid inputs, exceptions)
- ✅ Side effects (database changes, API calls)
- ✅ Null/None handling
- ✅ Type validation (if applicable)

**Test Structure**:
```python
# tests/test_module.py
import pytest
from app.module import function_to_test

def test_function_happy_path():
    """Test normal operation with valid inputs"""
    result = function_to_test(valid_input)
    assert result == expected_output

def test_function_edge_case_empty_input():
    """Test behavior with empty input"""
    result = function_to_test("")
    assert result is None  # or appropriate behavior

def test_function_error_invalid_input():
    """Test error handling for invalid input"""
    with pytest.raises(ValueError, match="expected error message"):
        function_to_test(invalid_input)

def test_function_side_effect(db_session):
    """Test database/external side effects"""
    function_to_test(input_with_side_effect)
    # Verify side effect occurred
    assert db_session.query(Model).count() == 1
```

### 4. Return Complete Test File

**Output**: Full test file content, ready to write
```

**Verification**:
- [ ] Created ~/portfolio-ai/.claude/subagents/testgen.md
- [ ] Protocol includes reading existing code + patterns
- [ ] Generates comprehensive coverage (happy path + edge cases + errors)

---

### 3.5 Update /do_it to Use TestGen Automatically

**Location**: `.claude/commands/do_it.md` (update Test Generation section)

**Change from**:
```
Dispatch general-purpose subagent for test generation
```

**Change to**:
```
Dispatch test-generator specialized subagent:

Task(
  subagent_type="general-purpose",
  prompt="Use test generation protocol from ~/portfolio-ai/.claude/subagents/testgen.md
          Generate tests for [file/function/class].
          Follow protocol: read implementation, read test patterns, generate comprehensive tests.
          Return complete test file content."
)
```

**Verification**:
- [ ] Updated /do_it test generation section
- [ ] References testgen.md subagent
- [ ] Specifies comprehensive coverage

---

## Phase 4: Validation & Monitoring (1-2 hours)

### 4.1 Create Audit Summary Report

**After completing Phase 2 audits**, create summary:

**File**: `docs/core/AUDIT_SUMMARY.md`

```markdown
# Portfolio AI - Comprehensive Audit Summary

**Date**: YYYY-MM-DD
**Scope**: 853 .md files, 68 .py files, 19 database tables, 7 core docs

---

## Executive Summary

[2-3 paragraphs summarizing findings]

---

## Findings by Category

### 1. Instruction Bloat
- Total instruction tokens: XX,XXXk
- Redundancy found: XX instances
- Outdated references: XX instances
- **Action items**: XX fixes needed

### 2. Code Quality
- Files >500 lines: XX files
- `Any` types found: XX instances
- TODOs/FIXMEs: XX instances
- Duplicate code: XX blocks
- **Action items**: XX refactorings needed

### 3. Database Integrity
- Missing indexes: XX
- Schema mismatches: XX
- Unused tables: XX
- **Action items**: XX migrations needed

### 4. Test Coverage
- Modules <80%: XX modules
- Skipped tests: XX tests
- Slow tests (>1s): XX tests
- **Action items**: XX tests needed

### 5. Documentation Currency
- Undocumented features: XX
- Broken links: XX
- Stale content (>30 days): XX files
- **Action items**: XX doc updates needed

### 6. Configuration Issues
- Unused dependencies: XX packages
- Hardcoded values: XX instances
- Missing env vars: XX variables
- **Action items**: XX config fixes needed

---

## Prioritized Action Plan

### 🔴 CRITICAL (Do First)
1. [Item] - File:line - Effort: XX hours

### ⚠️ HIGH (This Week)
1. [Item] - File:line - Effort: XX hours

### 📋 MEDIUM (This Month)
1. [Item] - File:line - Effort: XX hours

### 💡 LOW (Backlog)
1. [Item] - File:line - Effort: XX hours

---

## Prevention Measures Status

- [x] Pre-implementation checklist - Created
- [x] Code quality skill - Created
- [x] TestGen subagent - Created
- [x] Automatic dispatch triggers - Added to /do_it
- [ ] All audit findings addressed

---

## Next Steps

1. Address critical findings
2. Implement high-priority fixes
3. Monitor for 2-3 PRDs to validate prevention measures
4. Re-run audits in 30 days to measure improvement
```

**Verification**:
- [ ] Created AUDIT_SUMMARY.md with all findings
- [ ] Prioritized action items
- [ ] Effort estimates included

---

### 4.2 Add Token Budget Monitoring to /doc_it

**Location**: `.claude/commands/doc_it.md` (after line 50, before "## Usage")

**Add**:

```markdown
## Token Budget Review

After documentation updates, check instruction efficiency:

```bash
# Check slash command sizes
wc -l .claude/commands/*.md | tail -1

# Alert thresholds:
# ⚠️ Individual command >200 lines
# 🔴 Total commands >900 lines

# Find redundancy
for file in .claude/commands/*.md; do
  echo "=== $(basename $file) ==="
  grep -h "^## " "$file"
done | sort | uniq -d

# Verify reference docs in use
grep -r "docs/reference" .claude/commands/ CLAUDE.md

# Report status
echo "## Token Budget Status"
echo "Slash commands: $(wc -l .claude/commands/*.md | tail -1) lines"
echo "Reference docs: $(wc -l docs/reference/*.md | tail -1) lines"
echo "Target: <800 lines for commands"
```

**If exceeded**: Extract to reference docs, update commands to reference
```

**Verification**:
- [ ] Added token budget section to /doc_it
- [ ] Automated checks for bloat
- [ ] Clear thresholds defined

---

## Success Metrics

**Measure these after implementing Phase 1-3**:

### Autonomy Metrics
- **Pause cycles per PRD**: Currently 11 → Target 5-6 (45% reduction)
- **Manual approvals per session**: Currently ~20 → Target ~5 (75% reduction)
- **Subagent dispatches per session**: Currently ~2 → Target ~8 (4x increase)

### Quality Metrics
- **Tech debt introduced per PRD**: Currently high → Target low (measure by TODO/FIXME additions)
- **Assumptions validated before implementation**: Currently 0% → Target 100%
- **Tests generated automatically**: Currently 50% → Target 95%
- **Files exceeding size limits**: Currently 6 → Target 0 (refactor all)

### Efficiency Metrics
- **Time to complete similar PRD**: Measure before/after (target 30% faster)
- **Context usage at pause**: Currently 140k → Target 100k (28% improvement)
- **Token waste from redundancy**: Currently ~9k → Target ~2k (77% reduction)

### Prevention Metrics
- **Pre-checks run before implementation**: Target 100% compliance
- **Quality skill invocations per session**: Target 3-5 times
- **Tech debt created (new TODOs)**: Target 0 per session

---

## Implementation Order

**Session 1** (2-3 hours):
- [ ] Phase 1.1 - Add automatic dispatch triggers
- [ ] Phase 1.2 - Remove approval gates
- [ ] Phase 1.3 - Delete /next_it
- [ ] Commit: "refactor: add autonomy mechanisms (automatic dispatch + remove gates)"

**Session 2** (4-6 hours):
- [ ] Phase 2.1 - Instruction audit
- [ ] Phase 2.2 - Code audit
- [ ] Phase 2.3 - Database audit
- [ ] Phase 2.4 - Test audit
- [ ] Phase 2.5 - Documentation audit
- [ ] Phase 2.6 - Config audit
- [ ] Phase 4.1 - Create audit summary
- [ ] Commit: "docs: comprehensive solution audit (findings + recommendations)"

**Session 3** (4-6 hours):
- [ ] Phase 3.1 - Create pre-check subagent
- [ ] Phase 3.2 - Update /do_it to mandate pre-check
- [ ] Phase 3.3 - Create code quality skill
- [ ] Phase 3.4 - Create TestGen subagent
- [ ] Phase 3.5 - Update /do_it to use TestGen
- [ ] Phase 4.2 - Add token monitoring to /doc_it
- [ ] Commit: "feat: add prevention mechanisms (pre-check + quality skill + testgen)"

**Session 4** (variable):
- [ ] Address critical audit findings
- [ ] Address high-priority audit findings
- [ ] Monitor next 2-3 PRDs for improvement
- [ ] Measure success metrics

---

## Notes

**Critical Principle**: Prevention > Reaction

- Pre-implementation checks prevent tech debt BEFORE it's created
- Automatic quality checks catch issues immediately
- Comprehensive tests ensure robustness
- Regular audits identify patterns to prevent

**The Goal**: You rarely need to intervene because quality is baked into the process

---

## Backup & Safety Summary

**Before you start ANY phase**:
1. ✅ Run pre-optimization snapshot (creates timestamped backup)
2. ✅ Create rollback script (one-time setup)
3. ✅ Create phase-specific backup before each phase
4. ✅ Test after each phase (5 validation checks)
5. ✅ Commit after successful phase completion

**If something goes wrong**:
```bash
# Quick rollback
bash ~/portfolio-ai/backups/rollback-optimization.sh <timestamp>

# List backups
ls -1 ~/portfolio-ai/backups/ | grep optimization-phase2

# Manual restore (emergency)
cp -r ~/portfolio-ai/backups/optimization-phase2-<timestamp>/commands-backup/* ~/.claude/commands/
```

**Rollback criteria**:
- 🔴 Commands fail to load → Rollback immediately
- 🔴 Syntax errors → Rollback immediately
- 🔴 Claude broken → Rollback immediately
- ⚠️ Performance worse → Measure, then decide
- ✅ Minor issues → Fix in place

**Backups are stored in**: `~/portfolio-ai/backups/`
- Full snapshots: `optimization-phase2-<timestamp>/`
- Phase backups: `phase1-autonomy-<timestamp>/`, etc.
- Git stashes: Referenced in `git-stash-ref.txt`

**Safety guaranteed**: Every change is reversible. No risk of permanent damage.

---

**Updated**: 2025-11-03
**Status**: Ready for next session
