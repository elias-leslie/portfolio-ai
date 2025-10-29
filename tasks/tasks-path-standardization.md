# Task List: Complete Path Standardization

**Created**: 2025-10-28
**Status**: 29% Complete (2/7 files done)
**Effort**: LOW (remaining work is straightforward find/replace)

---

## Summary

Standardize ALL path references in documentation to use absolute paths anchored to `~/portfolio-ai/` to prevent path confusion and the `backend/backend/` nesting issue.

**Core Rule**: Every path reference must start from `~/portfolio-ai/`

---

## ✅ Completed (2/7 files)

1. ✅ **CLAUDE.md** (Committed: 48206b3)
   - 25 path references standardized
   - Quick Start, Command Reference, Pre-commit workflows updated
   - Python version updated to 3.13+

2. ✅ **docs/core/DEVELOPMENT.md** (Committed: e9852db)
   - 21 path references standardized
   - Execution Context, Testing, Linting, Dependency Management updated

---

## ⏭️ Remaining (5/7 files, ~70 references)

### 3. PROJECT_STRUCTURE.md (~35 references)

**Location**: `/home/kasadis/portfolio-ai/PROJECT_STRUCTURE.md`

**Sections to update**:
- Line 12-60: Directory tree structure (update all backend/, frontend/, data/, etc.)
- Line 66-80: Critical Paths section (virtual environment, tests, app code paths)
- Line 85-105: Configuration Files, Database, Application Startup sections
- Line 150-177: "Common Mistakes to Avoid" examples
- Line 180-194: Quick Verification commands

**Pattern replacements**:
```bash
# Find all instances of these patterns and replace:
backend/                    → ~/portfolio-ai/backend/
frontend/                   → ~/portfolio-ai/frontend/
scripts/                    → ~/portfolio-ai/scripts/
config/                     → ~/portfolio-ai/config/
docs/core/                  → ~/portfolio-ai/docs/core/
data/                       → ~/portfolio-ai/data/ (for backups)
backend/data/               → ~/portfolio-ai/backend/data/ (active DB)
tasks/                      → ~/portfolio-ai/tasks/
.ai_dev_tasks/              → ~/portfolio-ai/.ai_dev_tasks/

# Command examples:
cd backend                  → cd ~/portfolio-ai/backend
source backend/.venv/       → source ~/portfolio-ai/backend/.venv/
ls backend/.venv/           → ls ~/portfolio-ai/backend/.venv/
pytest backend/tests/       → pytest ~/portfolio-ai/backend/tests/
./scripts/lint.sh           → ~/portfolio-ai/scripts/lint.sh
```

**Example edits**:
```diff
- Location: `/home/kasadis/portfolio-ai/backend/.venv/`
+ Location: `~/portfolio-ai/backend/.venv/`

- Run from project root: `backend/.venv/bin/pytest backend/tests/ -v`
+ Run from anywhere: `~/portfolio-ai/backend/.venv/bin/pytest ~/portfolio-ai/backend/tests/ -v`

- ❌ Wrong: `cd backend && source backend/.venv/bin/activate`
+ ❌ Wrong: `cd ~/portfolio-ai/backend && source backend/.venv/bin/activate`
```

---

### 4. docs/core/SETUP.md (~15 references)

**Location**: `/home/kasadis/portfolio-ai/docs/core/SETUP.md`

**Sections to update**:
- Backend setup instructions (cd backend → cd ~/portfolio-ai/backend)
- Virtual environment creation paths
- Dependency installation commands
- Database setup paths
- Verification commands

**Key patterns**:
```bash
cd backend                           → cd ~/portfolio-ai/backend
python3 -m venv backend/.venv        → python3 -m venv ~/portfolio-ai/backend/.venv
source backend/.venv/bin/activate    → source ~/portfolio-ai/backend/.venv/bin/activate
pip install -r backend/requirements.txt → pip install -r ~/portfolio-ai/backend/requirements.txt
```

---

### 5. docs/core/OPERATIONS.md (~10 references)

**Location**: `/home/kasadis/portfolio-ai/docs/core/OPERATIONS.md`

**Sections to update**:
- Deployment paths
- Backup/restore commands
- Log file locations
- Database paths
- Monitoring setup

**Key patterns**:
```bash
backend/logs/                        → ~/portfolio-ai/backend/logs/
backend/data/portfolio-ai.db         → ~/portfolio-ai/backend/data/portfolio-ai.db
backup data/                         → backup ~/portfolio-ai/data/
```

---

### 6. docs/core/ARCHITECTURE.md (~5 references)

**Location**: `/home/kasadis/portfolio-ai/docs/core/ARCHITECTURE.md`

**Sections to update**:
- System components (file references)
- Data flow paths
- Module structure references

**Key patterns**:
```bash
app/storage/                         → ~/portfolio-ai/backend/app/storage/
app/agents/                          → ~/portfolio-ai/backend/app/agents/
config/sources/                      → ~/portfolio-ai/config/sources/
```

---

### 7. README.md (~5 references, if exists)

**Location**: `/home/kasadis/portfolio-ai/README.md`

**Check if this file exists first**. If it does, update:
- Getting started instructions
- Quick start paths
- Project structure references

---

## Execution Steps

### For each remaining file:

1. **Read the file** to identify all path references
2. **Apply replacements** using the patterns above
3. **Verify changes** - ensure commands make sense
4. **Test a command** (optional) - pick one to verify it works
5. **Commit individually** with descriptive message

### Commit message template:

```bash
git add [filename]
git commit -m "docs: standardize all paths in [filename] to anchor from ~/portfolio-ai/

Updated ALL path references to use absolute paths anchored to project root:
- [Section 1]: [Brief description of changes]
- [Section 2]: [Brief description of changes]
- [Section 3]: [Brief description of changes]

All commands now unambiguous and impossible to run in wrong directory.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Pattern Reference Guide

### Common Replacements

| Context | Before | After |
|---------|--------|-------|
| **Change directory** | `cd backend` | `cd ~/portfolio-ai/backend` |
| **Activate venv** | `source backend/.venv/bin/activate` | `source ~/portfolio-ai/backend/.venv/bin/activate` |
| **Run tests** | `pytest tests/` (from backend) | `cd ~/portfolio-ai/backend && pytest tests/` |
| **Run scripts** | `./scripts/lint.sh` | `~/portfolio-ai/scripts/lint.sh` |
| **File references** | `backend/app/main.py` | `~/portfolio-ai/backend/app/main.py` |
| **Git operations** | `git add .` | `cd ~/portfolio-ai && git add .` |
| **Database path** | `data/portfolio-ai.db` | `~/portfolio-ai/backend/data/portfolio-ai.db` |
| **Logs path** | `logs/` | `~/portfolio-ai/backend/logs/` |
| **Config path** | `config/sources/` | `~/portfolio-ai/config/sources/` |

### Multi-step Commands

When showing multi-step workflows, ALWAYS anchor each step:

```bash
# ❌ WRONG - ambiguous
cd backend
source .venv/bin/activate
pytest tests/

# ✅ CORRECT - unambiguous
cd ~/portfolio-ai/backend
source ~/portfolio-ai/backend/.venv/bin/activate
pytest tests/  # Now clearly in ~/portfolio-ai/backend/tests/
```

### Directory Trees

When showing directory structure, add absolute path at top:

```
~/portfolio-ai/              ← PROJECT ROOT
├── backend/                 ← Backend application root
│   ├── app/                 ← Python application code
│   ├── tests/               ← Test files
│   └── .venv/               ← Virtual environment
├── frontend/                ← Next.js dashboard
└── scripts/                 ← Build & validation scripts
```

---

## Verification

After completing all files:

1. **Search for remaining ambiguous paths**:
   ```bash
   cd ~/portfolio-ai
   grep -r "cd backend" docs/ CLAUDE.md PROJECT_STRUCTURE.md README.md 2>/dev/null | grep -v "~/portfolio-ai"
   grep -r "backend/" docs/ CLAUDE.md PROJECT_STRUCTURE.md README.md 2>/dev/null | grep -v "~/portfolio-ai" | head -20
   ```

2. **Test sample commands**:
   ```bash
   # These should work from any directory
   cd ~/portfolio-ai/backend
   source ~/portfolio-ai/backend/.venv/bin/activate
   python --version  # Should show 3.13.x
   ```

3. **Create final commit** documenting completion:
   ```bash
   git commit --allow-empty -m "docs: complete path standardization across all documentation

   All 7 documentation files now use absolute paths anchored to ~/portfolio-ai/:
   - CLAUDE.md (✅ completed)
   - docs/core/DEVELOPMENT.md (✅ completed)
   - PROJECT_STRUCTURE.md (✅ completed)
   - docs/core/SETUP.md (✅ completed)
   - docs/core/OPERATIONS.md (✅ completed)
   - docs/core/ARCHITECTURE.md (✅ completed)
   - README.md (✅ completed)

   Total: ~140 path references standardized
   Benefit: Impossible to create backend/backend/ or run commands in wrong directory

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

---

## Why This Matters

**Problem solved**:
- ❌ `cd backend` from wrong location → created `backend/backend/`
- ❌ Relative paths → confusion about execution context
- ❌ Tools run from root → duplicate caches in wrong locations

**After standardization**:
- ✅ `cd ~/portfolio-ai/backend` → always correct location
- ✅ Absolute paths → no ambiguity
- ✅ Single source of truth → one way to reference files

---

## Notes

- **Priority**: Complete PROJECT_STRUCTURE.md first (most references, most important)
- **Time estimate**: 30-45 minutes for all 5 remaining files
- **Complexity**: LOW - mostly find/replace with verification
- **Risk**: VERY LOW - documentation only, no code changes

---

**Related Work**:
- Completed: Task 2.0 (Python 3.13 Migration)
- Completed: Task 3.0 (Pin All Dependencies) - 95%
- Completed: Project Structure Cleanup (8 files removed)
- In Progress: Path Standardization (29% complete)
