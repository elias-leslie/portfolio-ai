# Portfolio AI - Comprehensive Cleanup Report

**Date**: 2025-11-06
**Analyzer**: Claude Code (File Search Specialist)
**Scope**: Entire /home/kasadis/portfolio-ai solution (29,986 project files)
**Repository Size**: 4.3GB (101,052 total files including dependencies)

---

## Executive Summary

**Total Files Identified for Removal**: 166+ files
**Total Size Recoverable**: ~862 MB (20% of repo size)
**Risk Level**: LOW to MEDIUM (all removals are safe, but some are historical)
**Primary Targets**: Legacy venv backup (717MB), screenshots (21MB), logs (106MB), archived docs/tasks

**Quick Wins** (High value, zero risk):
1. Remove `.venv.python312.backup/` → Saves 717MB
2. Remove old log files → Saves 95MB
3. Remove backend screenshots → Saves 1.1MB
4. Remove pip artifacts → Saves 5.4KB
5. Remove duplicate archived screenshots → Saves 8.1MB

---

## Category Breakdown

### 1. **CRITICAL: Legacy Virtual Environment Backup** (717MB)

**Location**: `/home/kasadis/portfolio-ai/backend/.venv.python312.backup/`

**Details**:
- Full Python 3.12 virtual environment backup
- Size: 717MB
- Already ignored in `.gitignore` (line 80)
- Active venv is `.venv/` (Python 3.13)

**Reason for Removal**:
- Obsolete backup from Python 3.12 → 3.13 migration
- No references in documentation
- All dependencies in current `.venv/`
- Can be recreated from `requirements.txt` if needed

**Impact**: ZERO - Backup serves no purpose with working venv

**Recommendation**: **DELETE IMMEDIATELY**
```bash
rm -rf /home/kasadis/portfolio-ai/backend/.venv.python312.backup/
```

**Size Saved**: 717MB (83% of cleanup total)

---

### 2. **Application Log Files** (106MB)

**Location**: `/home/kasadis/portfolio-ai/backend/logs/`

**Files**:
```
11M  portfolio-ai.log (current - KEEP)
1.4M portfolio-ai.log.2025-10-27
4.1M portfolio-ai.log.2025-10-28
731K portfolio-ai.log.2025-10-29
6.8M portfolio-ai.log.2025-10-30
1.5M portfolio-ai.log.2025-10-31
12M  portfolio-ai.log.2025-11-01
24M  portfolio-ai.log.2025-11-02
24M  portfolio-ai.log.2025-11-03
17M  portfolio-ai.log.2025-11-04
5.3M portfolio-ai.log.2025-11-05
```

**Reason for Removal**:
- Rotated logs older than 7 days have limited value
- No log aggregation system configured
- Active debugging uses current log only
- Can compress/archive if historical value exists

**Impact**: LOW - Historical logs rarely needed after issue resolution

**Recommendation**: **REMOVE LOGS OLDER THAN 7 DAYS**
```bash
find /home/kasadis/portfolio-ai/backend/logs/ -name "*.log.2025-*" -mtime +7 -delete
```

**Size Saved**: ~95MB (keep only 11MB current + last 2 days)

---

### 3. **Archived Screenshots** (8.1MB)

**Location**: `/home/kasadis/portfolio-ai/docs/screenshots/archive/`

**Structure**:
```
8.1MB docs/screenshots/archive/phase2-audit-20251103-132213/screenshots/
  - 45 duplicate screenshots from Nov 2-3
  - Watchlist subdirectory with README (372 lines)
  - All screenshots superseded by current versions
```

**Current Active Screenshots**:
```
docs/screenshots/ (root) - 44 files (11.9MB)
docs/screenshots/watchlist/ - 11 files + README (2.9MB)
docs/screenshots/news/ - 10 files (various dates)
```

**Reason for Removal**:
- Archive created 2025-11-03 during phase 2 audit
- All screenshots have current equivalents in root
- Duplicate README.md (identical to current watchlist/README.md)
- Archive purpose was snapshot before changes (changes now complete)

**Impact**: ZERO - Current screenshots cover all features

**Recommendation**: **DELETE ARCHIVE SCREENSHOTS**
```bash
rm -rf /home/kasadis/portfolio-ai/docs/screenshots/archive/
```

**Size Saved**: 8.1MB

---

### 4. **Backend Development Screenshots** (1.1MB)

**Location**: `/home/kasadis/portfolio-ai/backend/`

**Files**:
```
188K staleness-investigation.png
195K task-0.0-fix-verified.png
197K task-1.5-timestamp-fix-verified.png
201K task-2.0-manual-refresh-test.png
188K watchlist-auto-refresh-working.png
128K watchlist-current-state.png
```

**Reason for Removal**:
- Temporary debugging screenshots from Oct 31 - Nov 2
- Belong in `docs/screenshots/` not backend code directory
- All issues resolved (tasks complete)
- No references in current documentation

**Impact**: ZERO - Debugging artifacts, issues fixed

**Recommendation**: **DELETE ALL**
```bash
rm /home/kasadis/portfolio-ai/backend/*.png
```

**Size Saved**: 1.1MB

---

### 5. **Completed Handoff Files in tasks/** (136KB, 13 files)

**Location**: `/home/kasadis/portfolio-ai/tasks/`

**Files to Archive**:
```
PAUSE-HANDOFF-20251102-0052.md (Nov 2-3)
PAUSE-HANDOFF-20251102-0408.md (Nov 2-3)
PAUSE-HANDOFF-20251102-1354.md (Nov 2-3)
PAUSE-HANDOFF-20251103-0300.md (Nov 3)
PAUSE-HANDOFF-2025-11-03-17-30.md (Nov 3)
PAUSE-HANDOFF-2025-11-03-2235.md (Nov 3)
PAUSE-HANDOFF-2025-11-04-0905.md (Nov 4)
PAUSE-HANDOFF-2025-11-04-1552.md (Nov 4)
PAUSE-HANDOFF-20251104-2339.md (Nov 4) - ACTIVE (referenced in WORK_TRACKER.md)
PAUSE-HANDOFF-20251106-1820.md (Nov 6)
PAUSE-HANDOFF-20251106-1835.md (Nov 6)
HANDOFF-20251106-CIK-CACHE.md (Nov 6)
HANDOFF-20251106-SEC-EDGAR-PHASE1.md (Nov 6)
```

**Reason for Archival**:
- Handoffs from completed sessions (Nov 2-6)
- Work continuation completed successfully
- Historical value: shows development progression
- Only keep most recent 2 handoffs in root

**Impact**: LOW - Historical reference only

**Recommendation**: **MOVE TO ARCHIVE** (keep recent)
```bash
# Keep only latest 3 handoffs in root, archive rest
mkdir -p /home/kasadis/portfolio-ai/tasks/archive/handoffs/2025-11/
mv /home/kasadis/portfolio-ai/tasks/PAUSE-HANDOFF-202511{02,03,04}*.md \
   /home/kasadis/portfolio-ai/tasks/archive/handoffs/2025-11/
```

**Size Saved**: 0 (moved, not deleted) - Organizational cleanup

---

### 6. **Archived Documentation** (244KB, 23 files)

**Location**: `/home/kasadis/portfolio-ai/docs/archive/`

**Structure**:
```
legacy-20251027-v1/ (1 file)
  - REMOTE_ACCESS_SETUP.md (7.6K)

legacy-20251028-v2/ (7 files, 37KB)
  - CHANGES_FROM_MARKET_SIM.md (6.2K)
  - GETTING_STARTED.md (4.7K)
  - HANDOFF_NOTES.md (5.1K)
  - PROJECT_STATUS.md (5.3K)
  - SETUP_NOTES.md (581 bytes)
  - TRANSITION_NOTES.md (5.9K)

legacy-20251030-v4/ (2 files, 15K)
  - postgresql-migration-summary.md (8.1K)
  - SERVICES.md (6.5K)

legacy-20251101-v5/ (4 files, 24K)
  - README.md (887 bytes)
  - session-2025-10-30-watchlist-refresh.md (5.9K)
  - TESTING_METHODOLOGY.md (7.0K)
  - watchlist_narrative_data_audit.md (9.5K)

legacy-20251102-v6/ (4 files, 27K)
  - README.md (1.2K)
  - UI_VALIDATION_PLAN.md (6.7K)
  - VALIDATION_WORKFLOW.md (7.7K)
  - watchlist-history-improvements.md (12K)

legacy-20251104-v1/ (5 files, 41K)
  - POSTGRESQL_PROFILE_ANALYSIS.md (8.8K)
  - RESOURCE_ALLOCATION_ANALYSIS.md (7.8K)
  - RESUME_NEXT_SESSION.md (7.0K)
  - solution_review.md (9.8K)
  - TESTING_FIX_SUMMARY.md (5.1K)
  - watchlist_review.md (11K)
```

**Reason for Keeping Archive**:
- Contains migration history (DuckDB → PostgreSQL)
- Documents architectural decisions
- Valuable for understanding system evolution
- Small size (244KB total)

**Reason for Potential Removal**:
- All content superseded by current docs/core/
- No active references in CLAUDE.md or ARCHITECTURE.md
- Historical value decreasing over time

**Impact**: LOW - Historical reference, no active usage

**Recommendation**: **KEEP FOR NOW** (revisit in 3 months)
- Archive shows project evolution
- May be useful for future refactors
- Size is negligible (244KB)

**Alternative**: Compress archive
```bash
tar -czf /home/kasadis/portfolio-ai/docs/archive-legacy-docs-2025-10-11.tar.gz \
        /home/kasadis/portfolio-ai/docs/archive/legacy-*/
rm -rf /home/kasadis/portfolio-ai/docs/archive/legacy-*/
```
**Size Saved**: ~200KB (compressed to ~50KB)

---

### 7. **Backups Directory** (748KB, 53 files)

**Location**: `/home/kasadis/portfolio-ai/backups/`

**Structure**:
```
optimization-phase2-20251103-131641/ (748KB)
  - commands-backup/ (7 .md files)
  - docs-core-backup/ (8 .md files)
  - docs-reference-backup/ (3 .md files)
  - STATE_MANIFEST.md

phase2-audit-20251103-132213/ (duplicate of docs/archive)
```

**Reason for Removal**:
- Created Nov 3 during optimization phase 2
- All files duplicated in active locations
- Optimization complete (TASK-0024, TASK-0025 done)
- 3+ days old, changes committed to git

**Impact**: ZERO - Git history preserves all changes

**Recommendation**: **DELETE BACKUPS**
```bash
rm -rf /home/kasadis/portfolio-ai/backups/
```

**Size Saved**: 748KB

---

### 8. **References Directory** (9.9MB, 51 .md files)

**Location**: `/home/kasadis/portfolio-ai/references/`

**Contents**:
```
AI-Trader-main/ (3.2MB)
  - Complete AI trading system reference
  - 26 markdown files
  - Python code, configs, docs

superpowers-main/ (6.5MB)
  - Claude Code enhancement patterns
  - 36 markdown files
  - Skills, commands, best practices

dexter-main/ (200KB)
  - Trading bot reference

Individual files:
  - ai_arena.md (47KB)
  - chat_log.md (19KB)
  - console_errors.md (12KB)
  - stock_trading.md (6KB)
```

**Status**: Already in `.gitignore` (lines 62-64)

**Reason for Keeping**:
- Active reference material for development
- Superpowers patterns used in slash commands
- AI-Trader concepts influence design
- Already excluded from git

**Reason for Potential Removal**:
- Reference repos available online
- Local copies not actively updated
- 9.9MB recoverable space

**Impact**: MEDIUM - Removes local reference docs

**Recommendation**: **KEEP** (already gitignored, useful reference)

**Alternative**: If needed, can delete and rely on online docs:
```bash
# Only if space critical
rm -rf /home/kasadis/portfolio-ai/references/
```
**Size Saved**: 9.9MB (if removed)

---

### 9. **Pip Artifact Files** (5.4KB, 2 files)

**Location**: `/home/kasadis/portfolio-ai/backend/`

**Files**:
```
=1.3.0 (5.4KB)
=2.2.0 (0 bytes)
```

**Reason for Removal**:
- Pip install artifacts from version constraint errors
- Created when running: `pip install package>=version`
- Already in `.gitignore` (line 10: `=*`)
- No functional purpose

**Impact**: ZERO - Garbage files

**Recommendation**: **DELETE IMMEDIATELY**
```bash
rm /home/kasadis/portfolio-ai/backend/=*
```

**Size Saved**: 5.4KB

---

### 10. **Debug Log Files** (varies)

**Files**:
```
/home/kasadis/portfolio-ai/.git/gc.log
/home/kasadis/portfolio-ai/backend/pytestdebug.log
```

**Reason for Removal**:
- Git garbage collection log (transient)
- Pytest debug log (debugging complete)
- Not tracked in git
- Auto-regenerated as needed

**Impact**: ZERO - Transient debug files

**Recommendation**: **DELETE**
```bash
rm /home/kasadis/portfolio-ai/.git/gc.log
rm /home/kasadis/portfolio-ai/backend/pytestdebug.log
```

**Size Saved**: <100KB

---

### 11. **Analysis/Summary Files in tasks/** (varies)

**Location**: `/home/kasadis/portfolio-ai/tasks/`

**Files**:
```
SLASH-COMMANDS-ANALYSIS.md
SLASH-COMMANDS-UPDATE-SUMMARY.md
OPTIMIZATION-PHASE-2.md
SESSION-SUMMARY-20251106-NEWS-INTELLIGENCE.md
SEC-EDGAR-SCHEMA-FIX-NEEDED.md
PROGRESS-HANDOFF-20251102.md
```

**Reason for Archival**:
- Completed analysis documents
- Slash commands updated (current in .claude/commands/)
- Optimization phase 2 complete
- Session summaries for historical reference

**Impact**: LOW - Historical documents

**Recommendation**: **MOVE TO ARCHIVE**
```bash
mv /home/kasadis/portfolio-ai/tasks/*ANALYSIS*.md \
   /home/kasadis/portfolio-ai/tasks/*SUMMARY*.md \
   /home/kasadis/portfolio-ai/tasks/OPTIMIZATION-PHASE-2.md \
   /home/kasadis/portfolio-ai/tasks/archive/
```

**Size Saved**: ~50KB (organizational)

---

### 12. **Audit Reports in docs/core/** (60KB, 7 files)

**Location**: `/home/kasadis/portfolio-ai/docs/core/`

**Files**:
```
CODE_AUDIT.md (13KB) - 2025-11-03
CONFIG_AUDIT.md (1.5KB) - 2025-11-03
DATABASE_AUDIT.md (11KB) - 2025-11-03
DOCUMENTATION_AUDIT.md (648 bytes) - 2025-11-03
INSTRUCTION_AUDIT.md (7.2KB) - 2025-11-03
TEST_AUDIT.md (1.3KB) - 2025-11-03
PLAN_TASK_OPTIMIZATION_ANALYSIS.md (14KB) - 2025-11-03
HEALTH_CHECK_REPORT.md (13KB) - 2025-11-04
```

**Reason for Keeping**:
- Snapshot of codebase health (Nov 3-4)
- Identifies ongoing tech debt
- Referenced in TASK-0033 (Code Quality Improvements - PAUSED)
- Used as baseline for improvements

**Reason for Archival**:
- Point-in-time snapshots (3 days old)
- Issues tracked in WORK_TRACKER.md
- Will become stale as code evolves

**Impact**: LOW - Reference documents

**Recommendation**: **KEEP FOR NOW** (archive after TASK-0033 complete)
- Active reference for ongoing work
- Move to archive once all issues addressed
- Small size (60KB)

**Future Action**: After TASK-0033 completion:
```bash
mkdir -p /home/kasadis/portfolio-ai/docs/archive/audits-2025-11-03/
mv /home/kasadis/portfolio-ai/docs/core/*AUDIT*.md \
   /home/kasadis/portfolio-ai/docs/core/HEALTH_CHECK_REPORT.md \
   /home/kasadis/portfolio-ai/docs/archive/audits-2025-11-03/
```

---

### 13. **Process Documentation (Workflow Guides)** (14KB, 1 file)

**Location**: `/home/kasadis/portfolio-ai/docs/core/`

**File**:
```
OPTIMIZATION_WORKFLOW.md (14KB) - How to use optimization mechanisms
```

**Reason for Keeping**:
- Active workflow documentation
- Describes current subagent dispatch patterns
- Referenced in development process

**Reason for Potential Archival**:
- Workflows now integrated into slash commands
- Information duplicated in .claude/commands/
- Specific to Phase 2 optimization approach

**Impact**: MEDIUM - Active process doc

**Recommendation**: **KEEP** (useful reference)
- Still describes current workflows
- Can be merged into DEVELOPMENT.md later

---

### 14. **Frontend Documentation** (varies)

**Location**: `/home/kasadis/portfolio-ai/frontend/`

**Files**:
```
README.md - Standard Next.js boilerplate (REPLACE)
README.tokens.md - Design tokens documentation (KEEP)
```

**Reason for Replacement**:
- README.md is default Next.js scaffold
- Doesn't describe Portfolio AI frontend
- No project-specific information

**Impact**: LOW - Generic boilerplate

**Recommendation**: **REPLACE WITH PROJECT-SPECIFIC README**
```bash
# Create proper frontend README with:
# - Architecture overview
# - Component structure
# - API integration patterns
# - Development workflow
# - Token system (link to README.tokens.md)
```

**Size Saved**: 0 (replace, not delete)

---

### 15. **Root Documentation Files** (varies)

**Location**: `/home/kasadis/portfolio-ai/`

**Files**:
```
README.md (6.7KB) - Main project README (KEEP)
CLAUDE.md (13KB) - AI agent instructions (KEEP)
GEMINI.md (2.5KB) - Gemini Code Assistant context (KEEP)
PROJECT_STRUCTURE.md (7.1KB) - Directory layout (KEEP)
test-ui-manual.sh (1.9KB) - Manual UI test script (EVALUATE)
```

**test-ui-manual.sh Analysis**:
- Created Nov 1 for manual browser testing
- Uses browser-automation skill scripts
- Tests watchlist and settings pages
- Hardcoded to specific IP (192.168.8.233)

**Reason for Keeping**:
- Useful for manual testing between development sessions
- Demonstrates browser automation usage
- Small size (1.9KB)

**Reason for Removal**:
- Manual testing can use skill directly
- IP may change (not portable)
- Functionality in .claude/skills/browser-automation/

**Impact**: LOW - Convenience script

**Recommendation**: **KEEP** (useful reference, small size)

---

### 16. **Automation Directory** (12KB)

**Location**: `/home/kasadis/portfolio-ai/automation/devtools/`

**File**:
```
news-smoke.json (1.7KB) - News system smoke test data
```

**Reason for Keeping**:
- Test fixture for news system
- Created Nov 5 (recent)
- Small size, potentially active

**Impact**: UNKNOWN - May be used in tests

**Recommendation**: **KEEP** (check if used in test suite)

---

### 17. **Duplicate Core Documentation** (NONE FOUND)

**Analysis**:
- No duplicate content found between:
  - docs/core/*.md
  - docs/reference/*.md
  - Root *.md files
- All docs serve distinct purposes
- No obsolete documentation detected

**Result**: ✅ CLEAN - No duplicate docs to remove

---

### 18. **Completed PRD/Task Files** (varies)

**Location**: `/home/kasadis/portfolio-ai/tasks/`

**Active Files** (keep in root):
```
WORK_TRACKER.md - Central tracker (KEEP)
news-phase1-sec-edgar-integration.md - COMPLETE (archive)
news-phase2-plain-language-ui.md - ACTIVE (keep)
news-phase3-cleanup-and-polish.md - PLANNED (keep)
tasks-0026-prd-type-system-infrastructure.md - COMPLETE (archive)
tasks-0027-mypy-cleanup-duckdb-rename.md - COMPLETE (archive)
tasks-0028-status-dashboard-mvp.md - COMPLETE (archive)
tasks-0029-status-dashboard-phase2-sse.md - COMPLETE (archive)
tasks-0030-status-dashboard-phase3-celery.md - COMPLETE (archive)
tasks-0031-status-dashboard-phases4-6.md - COMPLETE (archive)
tasks-0032-baseline-whitelist-system.md - COMPLETE (archive)
tasks-0033-code-quality-improvements.md - PAUSED (keep)
0026-prd-type-system-infrastructure.md - PRD (archive)
0028-prd-status-page-mvp.md - PRD (archive)
0029-prd-status-page-advanced.md - PRD (archive)
prd-fear_and_greed.md - PLANNED (keep)
prd-watchlist-fixes.md - UNKNOWN (evaluate)
tasks-prd-watchlist-fixes.md - UNKNOWN (evaluate)
```

**Recommendation**: **MOVE COMPLETED TO ARCHIVE**
```bash
# Move completed tasks to archive
mv /home/kasadis/portfolio-ai/tasks/news-phase1-sec-edgar-integration.md \
   /home/kasadis/portfolio-ai/tasks/tasks-002{6,7,8,9}-*.md \
   /home/kasadis/portfolio-ai/tasks/tasks-003{0,1,2}-*.md \
   /home/kasadis/portfolio-ai/tasks/002{6,8,9}-prd-*.md \
   /home/kasadis/portfolio-ai/tasks/archive/task-lists/
```

**Size Saved**: ~150KB (organizational cleanup)

---

### 19. **OS-Specific Junk Files** (varies)

**Files**:
```
/home/kasadis/portfolio-ai/references/AI-Trader-main/AI-Trader-main/data/.DS_Store
/home/kasadis/portfolio-ai/references/AI-Trader-main/AI-Trader-main/docs/assets/.DS_Store
```

**Reason for Removal**:
- macOS Finder metadata files
- No functional purpose on Linux
- Already in .gitignore (line 48)

**Impact**: ZERO - Metadata files

**Recommendation**: **DELETE**
```bash
find /home/kasadis/portfolio-ai/references -name ".DS_Store" -delete
```

**Size Saved**: <10KB

---

## Removal Priority Matrix

### HIGH PRIORITY (Execute Immediately)

| Item | Size | Risk | Effort | Action |
|------|------|------|--------|--------|
| .venv.python312.backup/ | 717MB | ZERO | 5 sec | `rm -rf` |
| backend/*.png | 1.1MB | ZERO | 5 sec | `rm` |
| backend/=* | 5.4KB | ZERO | 5 sec | `rm` |
| Old logs (>7 days) | 95MB | LOW | 10 sec | `find -delete` |
| .git/gc.log | <1KB | ZERO | 5 sec | `rm` |
| backend/pytestdebug.log | <100KB | ZERO | 5 sec | `rm` |
| .DS_Store files | <10KB | ZERO | 5 sec | `find -delete` |

**Total High Priority**: ~813MB, <1 minute effort

### MEDIUM PRIORITY (Execute This Week)

| Item | Size | Risk | Effort | Action |
|------|------|------|--------|--------|
| docs/screenshots/archive/ | 8.1MB | ZERO | 5 sec | `rm -rf` |
| backups/ | 748KB | ZERO | 5 sec | `rm -rf` |
| Completed handoffs | 136KB | LOW | 2 min | Move to archive |
| Completed task files | 150KB | LOW | 2 min | Move to archive |
| Analysis/summary files | 50KB | LOW | 1 min | Move to archive |

**Total Medium Priority**: ~9MB, ~10 minutes effort

### LOW PRIORITY (Optional)

| Item | Size | Risk | Effort | Action |
|------|------|------|--------|--------|
| references/ | 9.9MB | MEDIUM | 5 sec | Delete (if space critical) |
| docs/archive/legacy-*/ | 244KB | MEDIUM | 5 sec | Compress or keep |
| Audit reports | 60KB | LOW | 1 min | Archive after TASK-0033 |

**Total Low Priority**: ~10MB

---

## Execution Plan

### Phase 1: Quick Wins (5 minutes, 813MB)

```bash
#!/bin/bash
# Phase 1: Immediate removals (zero risk)

cd /home/kasadis/portfolio-ai

# 1. Remove legacy venv backup (717MB)
echo "Removing legacy venv backup..."
rm -rf backend/.venv.python312.backup/

# 2. Remove backend screenshots (1.1MB)
echo "Removing backend debug screenshots..."
rm backend/*.png

# 3. Remove pip artifacts (5.4KB)
echo "Removing pip artifacts..."
rm backend/=*

# 4. Remove old logs >7 days (95MB)
echo "Removing old log files..."
find backend/logs/ -name "*.log.2025-*" -mtime +7 -delete

# 5. Remove debug logs
echo "Removing debug logs..."
rm .git/gc.log backend/pytestdebug.log 2>/dev/null

# 6. Remove OS junk files
echo "Removing .DS_Store files..."
find references/ -name ".DS_Store" -delete

echo "✅ Phase 1 complete! Saved ~813MB"
du -sh .
```

### Phase 2: Organizational Cleanup (10 minutes, 9MB)

```bash
#!/bin/bash
# Phase 2: Archive and organize

cd /home/kasadis/portfolio-ai

# 1. Remove archived screenshots (8.1MB)
echo "Removing archived screenshots..."
rm -rf docs/screenshots/archive/

# 2. Remove backups directory (748KB)
echo "Removing backups directory..."
rm -rf backups/

# 3. Archive completed handoffs
echo "Archiving completed handoffs..."
mkdir -p tasks/archive/handoffs/2025-11/
mv tasks/PAUSE-HANDOFF-2025110{2,3,4}*.md tasks/archive/handoffs/2025-11/ 2>/dev/null
mv tasks/HANDOFF-20251106-CIK-CACHE.md tasks/archive/handoffs/2025-11/ 2>/dev/null

# 4. Archive completed task files
echo "Archiving completed task files..."
mv tasks/news-phase1-sec-edgar-integration.md tasks/archive/task-lists/ 2>/dev/null
mv tasks/tasks-002{6,7,8,9}-*.md tasks/archive/task-lists/ 2>/dev/null
mv tasks/tasks-003{0,1,2}-*.md tasks/archive/task-lists/ 2>/dev/null
mv tasks/002{6,8,9}-prd-*.md tasks/archive/prds/ 2>/dev/null

# 5. Archive analysis files
echo "Archiving analysis files..."
mv tasks/*ANALYSIS*.md tasks/*SUMMARY*.md tasks/OPTIMIZATION-PHASE-2.md tasks/archive/ 2>/dev/null

echo "✅ Phase 2 complete! Saved ~9MB"
```

### Phase 3: Optional (if space critical)

```bash
#!/bin/bash
# Phase 3: Optional removals (evaluate need first)

cd /home/kasadis/portfolio-ai

# 1. Compress legacy docs (optional)
echo "Compressing legacy documentation..."
tar -czf docs/archive-legacy-docs-2025-10-11.tar.gz docs/archive/legacy-*/
rm -rf docs/archive/legacy-*/

# 2. Remove references (only if space critical)
# echo "Removing reference directories..."
# rm -rf references/

echo "✅ Phase 3 complete!"
```

---

## Summary Statistics

### Before Cleanup
- Total files: 101,052 (29,986 project files)
- Repository size: 4.3GB
- Project size (no deps): ~1.0GB

### After Phase 1 (High Priority)
- Files removed: ~150
- Size saved: 813MB
- New repository size: ~3.5GB
- Time required: 5 minutes

### After Phase 2 (Medium Priority)
- Files removed: ~200
- Size saved: 822MB
- New repository size: ~3.48GB
- Time required: 15 minutes total

### After Phase 3 (Low Priority)
- Files removed: ~220
- Size saved: ~832MB
- New repository size: ~3.47GB
- Time required: 20 minutes total

---

## Validation Checklist

After cleanup, verify:

```bash
# 1. Services still start
cd ~/portfolio-ai
bash scripts/start.sh
bash scripts/status.sh

# 2. Tests still pass
cd ~/portfolio-ai/backend
source .venv/bin/activate
pytest tests/ -v

# 3. Linting still works
~/portfolio-ai/scripts/lint.sh

# 4. Frontend builds
cd ~/portfolio-ai/frontend
npm run build

# 5. Git status clean
cd ~/portfolio-ai
git status

# 6. Key docs exist
ls -lh docs/core/*.md
ls -lh tasks/WORK_TRACKER.md
ls -lh README.md CLAUDE.md
```

---

## Risk Assessment

**Overall Risk**: LOW

### Zero Risk Items (813MB)
- ✅ .venv.python312.backup/ - Obsolete backup
- ✅ backend/*.png - Debug screenshots
- ✅ backend/=* - Pip artifacts
- ✅ Old logs - Rotated application logs
- ✅ Debug logs - Transient files

### Low Risk Items (9MB)
- ⚠️ docs/screenshots/archive/ - Duplicate screenshots (verify current coverage first)
- ⚠️ backups/ - Duplicated in git history
- ⚠️ Completed handoffs - Historical context (keep 2 recent)
- ⚠️ Completed task files - Moved to archive (not deleted)

### Medium Risk Items (10MB)
- ⚠️⚠️ references/ - Useful reference docs (only remove if space critical)
- ⚠️⚠️ docs/archive/legacy-*/ - Project history (compress instead of delete)
- ⚠️⚠️ Audit reports - Active reference for TASK-0033 (wait until complete)

---

## Maintenance Recommendations

### Immediate
1. Execute Phase 1 cleanup script (813MB savings, zero risk)
2. Update .gitignore to prevent log bloat:
   ```
   # Add to .gitignore
   backend/logs/*.log.2025-*
   backend/pytestdebug.log
   .git/gc.log
   ```

### Weekly
1. Rotate logs: `find backend/logs/ -name "*.log.2025-*" -mtime +7 -delete`
2. Archive completed handoffs: Move PAUSE-HANDOFF-* files >7 days old
3. Clean pytest cache: `rm -rf .pytest_cache/ backend/.pytest_cache/`

### Monthly
1. Archive completed task files to `tasks/archive/`
2. Review `docs/screenshots/` for outdated screenshots
3. Compress old archives: `tar -czf docs/archive-YYYY-MM.tar.gz docs/archive/legacy-*/`
4. Check references/ for updates

### After Major Milestones
1. Archive audit reports after issues resolved
2. Clean up handoff files after successful continuation
3. Update documentation to reflect completed features
4. Remove deprecated code/docs

---

## Notes

**Documentation Philosophy**:
- Keep all core documentation (ARCHITECTURE.md, DEVELOPMENT.md, etc.)
- Archive historical snapshots (audits, legacy docs)
- Remove duplicates and outdated references
- Preserve project evolution history in compressed archives

**Screenshot Management**:
- Keep current screenshots for active features
- Archive old screenshots after feature updates
- Document screenshots with README.md in subdirectories
- Remove debug/temporary screenshots from backend/

**Task Management**:
- Keep WORK_TRACKER.md as single source of truth
- Archive completed task lists to tasks/archive/
- Keep 2-3 recent handoffs in root for quick reference
- Move older handoffs to tasks/archive/handoffs/YYYY-MM/

**Log Management**:
- Rotate logs older than 7 days
- Keep current log for debugging
- Consider log aggregation system for production
- Add log rotation to .gitignore

---

**Generated**: 2025-11-06
**Next Review**: 2025-12-06 (monthly maintenance)
**Estimated Total Cleanup**: 822MB (Phase 1 + 2)
**Estimated Effort**: 15 minutes

---

## Appendix: File Categories Summary

| Category | Count | Size | Risk | Action |
|----------|-------|------|------|--------|
| Legacy venv backup | 1 dir | 717MB | ZERO | Delete |
| Log files | 10 | 95MB | LOW | Delete old |
| Screenshots (archive) | 58 | 8.1MB | ZERO | Delete |
| Screenshots (backend) | 6 | 1.1MB | ZERO | Delete |
| Backups | 53 | 748KB | ZERO | Delete |
| Handoffs | 13 | 136KB | LOW | Archive |
| Task files | 15 | 150KB | LOW | Archive |
| Audit reports | 7 | 60KB | LOW | Keep |
| Legacy docs | 23 | 244KB | MEDIUM | Keep/compress |
| References | 51+ | 9.9MB | MEDIUM | Keep |
| Pip artifacts | 2 | 5.4KB | ZERO | Delete |
| Debug logs | 2 | <100KB | ZERO | Delete |
| OS junk | 2 | <10KB | ZERO | Delete |
| **TOTAL** | **166+** | **~832MB** | **LOW** | **Multi-phase** |

---

**End of Report**
