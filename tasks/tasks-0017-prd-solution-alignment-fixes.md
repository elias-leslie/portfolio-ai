# Task List: Solution Alignment Fixes

**PRD**: `0017-prd-solution-alignment-fixes.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: High
**Last Updated**: 2025-10-30

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity (21-28 hours estimated)

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0 (Investigation & Audit)
2. Complete Phase 1 before moving to Phase 2
3. Update this summary as work progresses

**EFFORT TO COMPLETE:** High (21-28 hours, ~2.5-3.5 days)

---

## Pre-Verified Facts (from codebase analysis)

**✅ VERIFIED FINDINGS:**
- PRD #0016 **IS IMPLEMENTED**: All 6 sources integrated in `backend/app/portfolio/price_fetcher.py:60-98`
- DuckDB dependency **EXISTS** in `backend/pyproject.toml:14` (`duckdb==1.4.1`)
- DuckDB dependency **EXISTS** in `.pre-commit-config.yaml:42` (`duckdb>=1.4.0`)
- DuckDB imports **EXIST** in 2 files: `storage/metadata.py`, `storage/facade.py` (for compatibility wrapper)
- Python version **INCONSISTENT**: `README.md:23` says "3.11+", `.pre-commit-config.yaml:6` says "3.13"
- fetchScoreHistory **HAS 404 FALLBACK**: `frontend/lib/api/watchlist.ts` with "may not exist yet" comment
- Documentation refs: **7 DuckDB mentions** in root docs, **28 mentions** in core docs
- Templates: **DO NOT EXIST** (.ai_dev_tasks/templates/ directory not found)
- Existing scripts: **17 shell scripts** in `scripts/` directory

---

## Relevant Files

### Files to Create (3 new files)

- `scripts/check-mypy-coverage.sh` (~30 lines) - Script to enforce mypy coverage threshold (98%+)
- `scripts/check-file-sizes.sh` (~50 lines) - Script to enforce file size limits (500 soft, 800 hard)
- `docs/alignment-investigation-report.md` (~100 lines) - Comprehensive findings from Phase 1 investigation

### Files to Update (20+ files - verified to exist)

**Configuration Files:**
- `backend/pyproject.toml:14` - Remove `duckdb==1.4.1` from dependencies list
- `backend/requirements.txt` - Regenerate after removing duckdb (will auto-remove duckdb entry)
- `.pre-commit-config.yaml:42` - Remove `duckdb>=1.4.0` from mypy additional_dependencies

**Root Documentation:**
- `README.md:23` - Change "Python 3.11+" to "Python 3.13+"
- `README.md` - Replace all DuckDB references with PostgreSQL 16 (tech stack, architecture)
- `CLAUDE.md` - Update "Project Structure" section, remove "DuckDB storage layer" references
- `PROJECT_STRUCTURE.md` - Update `backend/data/` description for PostgreSQL (no .db files)

**Core Documentation:**
- `docs/core/ARCHITECTURE.md` - Update diagram, data flow, schema examples, tech stack for PostgreSQL
- `docs/core/SETUP.md` - Replace DuckDB setup with PostgreSQL 16 installation
- `docs/core/OPERATIONS.md` - Remove DuckDB troubleshooting, add PostgreSQL operations
- `docs/core/REFACTOR_STATUS.md` - Update PRD #0016 status to reflect implementation
- `docs/core/DEVELOPMENT.md` - Add "Update documentation" to Definition of Done checklist

**Task/Status Files:**
- `docs/known-issues.md` - Update with accurate test failure counts (will be verified in Phase 1)
- `tasks/tasks-0015-postgresql-migration.md` - Remove/correct "100% passing" claim if inaccurate
- `tasks/tasks-0016-prd-complete-multi-source-failover.md:4-5` - Change Status to "COMPLETE", Completion to "100%"

**Storage Layer (DuckDB compatibility wrapper - document only, don't remove):**
- `backend/app/storage/metadata.py` - Keep duckdb import (compatibility wrapper), document as PostgreSQL-only
- `backend/app/storage/facade.py` - Keep duckdb type hints (compatibility wrapper), document as PostgreSQL-only
- `backend/app/storage/connection.py` - PostgreSQLDuckDBWrapper is intentional, verify documentation

**Frontend:**
- `frontend/lib/api/watchlist.ts` - Remove temporary 404 handling in fetchScoreHistory function (lines 100-120)

**New PRD (to be created):**
- `tasks/0018-prd-fix-agent-test-failures.md` - Document plan to fix 15 failing agent tests

### Notes

- Run `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v --cov=app` to verify test status
- Run `cd ~/portfolio-ai/backend && mypy app/ --strict` to verify type safety
- Run `~/portfolio-ai/scripts/lint.sh` for linting and formatting
- Use `/check_it` to verify final alignment score >80%
- DuckDB imports in storage/ are INTENTIONAL (PostgreSQLDuckDBWrapper for backward compat), document but don't remove

---

## Tasks

- [ ] **1.0 Investigation & Audit Phase** (Critical - 2-3 hours, reduced from 4-6)
  - [ ] 1.1 Verify PRD #0016 implementation status (15 min - already confirmed)
    - [ ] 1.1.1 Read `backend/app/portfolio/price_fetcher.py:60-98` to verify multi-source initialization
    - [ ] 1.1.2 Confirm all 6 sources present: YFinance (61), TwelveData (66), FMP (73), Polygon (80), Finnhub (87), AlphaVantage (94)
    - [ ] 1.1.3 Verify conditional API key detection with _has_api_key() method
    - [ ] 1.1.4 Verify priority-based failover via MultiSourceFetcher initialization
    - [ ] 1.1.5 Document finding: "PRD #0016 IS IMPLEMENTED - all 6 sources in priority order, conditional API key detection confirmed"
  - [ ] 1.2 Audit DuckDB references comprehensively (45 min)
    - [ ] 1.2.1 Verify `backend/pyproject.toml:14` contains `duckdb==1.4.1`
    - [ ] 1.2.2 Verify `.pre-commit-config.yaml:42` contains `duckdb>=1.4.0` in mypy deps
    - [ ] 1.2.3 Run `grep -rn "import duckdb\|from duckdb" backend/app --include="*.py"` and list files (expect: metadata.py, facade.py)
    - [ ] 1.2.4 Read `backend/app/storage/connection.py:1-35` to verify PostgreSQLDuckDBWrapper is documented
    - [ ] 1.2.5 Run `grep -c "DuckDB\|duckdb" README.md CLAUDE.md PROJECT_STRUCTURE.md` (expect: ~7 total)
    - [ ] 1.2.6 Run `grep -c "DuckDB\|duckdb" docs/core/*.md` (expect: ~28 total)
    - [ ] 1.2.7 Create comprehensive list with file paths and line numbers
  - [ ] 1.3 Verify actual test status (45 min)
    - [ ] 1.3.1 Run `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v 2>&1 | tee /tmp/test-results.txt`
    - [ ] 1.3.2 Parse output to count: total tests, passed, failed, skipped
    - [ ] 1.3.3 Extract specific failing test names (e.g., test_api_ideas.py::test_generate_ideas_discovery)
    - [ ] 1.3.4 Compare to `docs/known-issues.md` claim of "15 agent-related test failures"
    - [ ] 1.3.5 Compare to `tasks/tasks-0015-postgresql-migration.md` claim of "All 296 tests passing"
  - [ ] 1.4 Create investigation findings report (30 min)
    - [ ] 1.4.1 Create `docs/alignment-investigation-report.md` with template structure
    - [ ] 1.4.2 Document PRD #0016 status: "COMPLETE - verified in price_fetcher.py:60-98"
    - [ ] 1.4.3 List all DuckDB references by file and line number from task 1.2.7
    - [ ] 1.4.4 Document test status: actual pass/fail counts vs documented claims
    - [ ] 1.4.5 Create prioritized action items for Phase 2-7

- [ ] **2.0 Dependency & Configuration Cleanup** (Critical - 2-3 hours)
  - [ ] 2.1 Remove DuckDB from Python dependencies (30 min)
    - [ ] 2.1.1 Open `backend/pyproject.toml` in editor
    - [ ] 2.1.2 Locate line 14: `"duckdb==1.4.1",`
    - [ ] 2.1.3 Delete the entire line (including comma)
    - [ ] 2.1.4 Save `backend/pyproject.toml`
    - [ ] 2.1.5 Run `cd ~/portfolio-ai/backend && source .venv/bin/activate && pip install -e .`
    - [ ] 2.1.6 Run `cd ~/portfolio-ai/backend && pip freeze > requirements.txt` to regenerate
    - [ ] 2.1.7 Verify duckdb is removed from requirements.txt
  - [ ] 2.2 Remove DuckDB from pre-commit config (15 min)
    - [ ] 2.2.1 Open `.pre-commit-config.yaml` in editor
    - [ ] 2.2.2 Locate line 42 in mypy hook additional_dependencies: `- duckdb>=1.4.0`
    - [ ] 2.2.3 Delete the entire line
    - [ ] 2.2.4 Save `.pre-commit-config.yaml`
    - [ ] 2.2.5 Run `pre-commit clean && pre-commit install --install-hooks` to refresh hooks
  - [ ] 2.3 Document compatibility wrapper (30 min)
    - [ ] 2.3.1 Read `backend/app/storage/connection.py:1-80` to understand PostgreSQLDuckDBWrapper
    - [ ] 2.3.2 Verify docstring states this is for PostgreSQL with DuckDB-compatible interface
    - [ ] 2.3.3 Add comment in `storage/metadata.py` above duckdb import: "# Type hint only - actual connection is PostgreSQL via wrapper"
    - [ ] 2.3.4 Add comment in `storage/facade.py` above duckdb import: "# Type hint only - actual connection is PostgreSQL via wrapper"
    - [ ] 2.3.5 Save both files with clarifying comments
  - [ ] 2.4 Run full test suite after cleanup (1 hour)
    - [ ] 2.4.1 Run `cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/ -v --cov=app 2>&1 | tee /tmp/test-results-post-cleanup.txt`
    - [ ] 2.4.2 Compare test counts to baseline from task 1.3.2
    - [ ] 2.4.3 Verify no NEW failures introduced (some pre-existing failures are OK)
    - [ ] 2.4.4 Check coverage percentage hasn't dropped below 86%
    - [ ] 2.4.5 Document in investigation report: "Dependency removal successful, X tests passing (unchanged from baseline)"

- [ ] **3.0 Documentation Overhaul** (High Priority - 6-8 hours)
  - [ ] 3.1 Update README.md (30 min)
    - [ ] 3.1.1 Open `README.md` in editor
    - [ ] 3.1.2 Change line 23: "Python 3.11+" to "Python 3.13+"
    - [ ] 3.1.3 Find tech stack/database section (search for "DuckDB" or "Database")
    - [ ] 3.1.4 Replace all "DuckDB" with "PostgreSQL 16"
    - [ ] 3.1.5 Update setup/installation if it mentions DuckDB
    - [ ] 3.1.6 Save and verify markdown renders correctly
  - [ ] 3.2 Update CLAUDE.md (45 min)
    - [ ] 3.2.1 Open `CLAUDE.md` in editor
    - [ ] 3.2.2 Search for "DuckDB storage layer" in Project Structure section
    - [ ] 3.2.3 Replace with "PostgreSQL storage layer"
    - [ ] 3.2.4 Update Key Architectural Decisions: "PostgreSQL 16 primary storage" (currently says DuckDB)
    - [ ] 3.2.5 Update Tech Stack section to list PostgreSQL 16, SQLAlchemy, psycopg2
    - [ ] 3.2.6 Verify all command examples use `~/portfolio-ai/` prefix
    - [ ] 3.2.7 Save changes
  - [ ] 3.3 Update PROJECT_STRUCTURE.md (30 min)
    - [ ] 3.3.1 Open `PROJECT_STRUCTURE.md` in editor
    - [ ] 3.3.2 Find `backend/data/` directory description
    - [ ] 3.3.3 Remove reference to "DuckDB database files" or ".db files"
    - [ ] 3.3.4 Update to: "PostgreSQL data files and backups only (database managed by PostgreSQL service)"
    - [ ] 3.3.5 Update `backend/app/storage/` description to "PostgreSQL storage layer"
    - [ ] 3.3.6 Save changes
  - [ ] 3.4 Update ARCHITECTURE.md - Diagram (1 hour)
    - [ ] 3.4.1 Open `docs/core/ARCHITECTURE.md` in editor
    - [ ] 3.4.2 Find ASCII architecture diagram (search for "DuckDB File" or box drawing characters)
    - [ ] 3.4.3 Replace "DuckDB File" box with "PostgreSQL 16" box
    - [ ] 3.4.4 Update box label "Storage Layer (DuckDB)" to "Storage Layer (PostgreSQL)"
    - [ ] 3.4.5 Add connection pooling details (pool_size=20, max_overflow=10) in diagram or caption
    - [ ] 3.4.6 Update database label from "(portfolio-ai.db)" to "(portfolio_ai db)"
    - [ ] 3.4.7 Save and verify diagram alignment
  - [ ] 3.5 Update ARCHITECTURE.md - Data Flow (1 hour)
    - [ ] 3.5.1 Find "Portfolio Analytics Flow" section in ARCHITECTURE.md
    - [ ] 3.5.2 Replace "DuckDB" references with "PostgreSQL" in flow steps
    - [ ] 3.5.3 Find "AI Idea Generation Flow" section
    - [ ] 3.5.4 Replace "DuckDB" references with "PostgreSQL" in flow steps
    - [ ] 3.5.5 Add note about connection pooling preventing lock issues
    - [ ] 3.5.6 Save changes
  - [ ] 3.6 Update ARCHITECTURE.md - Schema & Tech Stack (1 hour)
    - [ ] 3.6.1 Find "Database Schema" section in ARCHITECTURE.md
    - [ ] 3.6.2 Update schema examples to show PostgreSQL types: TIMESTAMPTZ (not TIMESTAMP), JSONB, SERIAL, DOUBLE PRECISION
    - [ ] 3.6.3 Find "Why PostgreSQL?" or "Why DuckDB?" section
    - [ ] 3.6.4 Update to explain PostgreSQL choice: MVCC (zero lock errors), connection pooling, 4x throughput, production-grade
    - [ ] 3.6.5 Update "Tech Stack" section: PostgreSQL 16, SQLAlchemy, psycopg2-binary
    - [ ] 3.6.6 Update data sources list to all 6: YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage
    - [ ] 3.6.7 Save changes
  - [ ] 3.7 Update SETUP.md (1 hour)
    - [ ] 3.7.1 Open `docs/core/SETUP.md` in editor
    - [ ] 3.7.2 Find DuckDB installation instructions (search for "duckdb", "pip install duckdb")
    - [ ] 3.7.3 Replace with PostgreSQL 16 installation: `sudo apt install postgresql-16` or equivalent
    - [ ] 3.7.4 Add PostgreSQL user creation: `sudo -u postgres createuser -s portfolio_ai_user`
    - [ ] 3.7.5 Add database creation: `sudo -u postgres createdb portfolio_ai`
    - [ ] 3.7.6 Add trust authentication setup if not present
    - [ ] 3.7.7 Verify all paths use `~/portfolio-ai/` prefix
    - [ ] 3.7.8 Save changes
  - [ ] 3.8 Update OPERATIONS.md (1.5 hours)
    - [ ] 3.8.1 Open `docs/core/OPERATIONS.md` in editor
    - [ ] 3.8.2 Find and remove "Database Locked" troubleshooting section (DuckDB-specific)
    - [ ] 3.8.3 Find and remove DuckDB backup strategies (`.db` file copy/backup)
    - [ ] 3.8.4 Add PostgreSQL backup section: `pg_dump portfolio_ai > backup.sql`
    - [ ] 3.8.5 Add PostgreSQL restore section: `psql portfolio_ai < backup.sql`
    - [ ] 3.8.6 Add PostgreSQL troubleshooting: connection pooling exhaustion, lock monitoring
    - [ ] 3.8.7 Update monitoring section: `SELECT * FROM pg_stat_activity;` for connections
    - [ ] 3.8.8 Save changes
  - [ ] 3.9 Update REFACTOR_STATUS.md - PRD #0016 (30 min)
    - [ ] 3.9.1 Open `docs/core/REFACTOR_STATUS.md` in editor
    - [ ] 3.9.2 Find PRD #0016 section (search for "PRD #0016" or "Multi-Source Failover")
    - [ ] 3.9.3 Verify status shows "✅ COMPLETE (100%)" - update if needed
    - [ ] 3.9.4 Update description: "All 6 sources integrated into PriceDataFetcher with priority-based failover"
    - [ ] 3.9.5 List completed features: YFinance → TwelveData → FMP → Polygon → Finnhub → AlphaVantage priority, conditional API key detection, source performance tracking
    - [ ] 3.9.6 Ensure "Recent Updates" section reflects completion
    - [ ] 3.9.7 Save changes

- [ ] **4.0 Test Integrity & Feature Status Verification** (High Priority - 2 hours)
  - [ ] 4.1 Update known-issues.md with accurate test status (30 min)
    - [ ] 4.1.1 Open `docs/known-issues.md` in editor
    - [ ] 4.1.2 Find "Pre-Existing Test Failures" or agent test section
    - [ ] 4.1.3 Update with actual test counts from task 1.3.2 (e.g., "X of 296 tests failing")
    - [ ] 4.1.4 List specific failing tests from task 1.3.3 (test file names and test names)
    - [ ] 4.1.5 Update severity assessment based on actual impact
    - [ ] 4.1.6 Update "Last Updated" timestamp to current date
    - [ ] 4.1.7 Save changes
  - [ ] 4.2 Update PostgreSQL migration task file (15 min)
    - [ ] 4.2.1 Open `tasks/tasks-0015-postgresql-migration.md` in editor
    - [ ] 4.2.2 Search for "All 296 tests passing" or "100% test" claims
    - [ ] 4.2.3 Replace with accurate status: "X tests passing, Y tests failing (see known-issues.md)"
    - [ ] 4.2.4 Add note: "Note: X pre-existing agent test failures documented in known-issues.md"
    - [ ] 4.2.5 Save with accurate test reporting
  - [ ] 4.3 Update PRD #0016 task file status (15 min)
    - [ ] 4.3.1 Open `tasks/tasks-0016-prd-complete-multi-source-failover.md` in editor
    - [ ] 4.3.2 Change line 4: Status from "Ready for Implementation" to "COMPLETE ✅"
    - [ ] 4.3.3 Change line 5: Completion from "0% (Not started)" to "100%"
    - [ ] 4.3.4 Update "Last Updated" to current date
    - [ ] 4.3.5 Add completion note: "Verified complete on 2025-10-30 - all 6 sources integrated in price_fetcher.py"
    - [ ] 4.3.6 Save changes
  - [ ] 4.4 Create PRD for fixing failing tests (30 min)
    - [ ] 4.4.1 Create new file `tasks/0018-prd-fix-agent-test-failures.md`
    - [ ] 4.4.2 Add PRD header: title, created date, status, priority (MEDIUM), complexity (MEDIUM)
    - [ ] 4.4.3 Document problem: "X agent-related tests failing due to mock configuration issues"
    - [ ] 4.4.4 List affected files from investigation: test_api_ideas.py, test_discovery_agent.py, test_portfolio_analyzer.py
    - [ ] 4.4.5 Define goal: "Fix all failing agent tests to restore test suite integrity"
    - [ ] 4.4.6 Add functional requirements: investigate mock failures, fix configurations, verify all pass
    - [ ] 4.4.7 Save as separate PRD for future work
  - [ ] 4.5 Verify no contradictory test claims (15 min)
    - [ ] 4.5.1 Run `grep -rn "100% test\|all tests passing\|296 tests" docs/ tasks/ --include="*.md"`
    - [ ] 4.5.2 Review each match for accuracy against actual test status from task 1.3.2
    - [ ] 4.5.3 Update any contradictory claims found
    - [ ] 4.5.4 Document verification in `docs/alignment-investigation-report.md`
    - [ ] 4.5.5 Note any files that still need updates

- [ ] **5.0 CI Quality Gates Implementation** (Medium Priority - 3-4 hours)
  - [ ] 5.1 Create mypy coverage check script (1.5 hours)
    - [ ] 5.1.1 Create `scripts/check-mypy-coverage.sh` file
    - [ ] 5.1.2 Add shebang: `#!/usr/bin/env bash`
    - [ ] 5.1.3 Add header comment: purpose, usage, threshold (98%)
    - [ ] 5.1.4 Add code to run: `cd ~/portfolio-ai/backend && mypy app/ --strict`
    - [ ] 5.1.5 Add code to parse output and count errors
    - [ ] 5.1.6 Add threshold check: exit 1 if errors exceed 2% of files
    - [ ] 5.1.7 Make executable: `chmod +x scripts/check-mypy-coverage.sh`
    - [ ] 5.1.8 Test locally: `bash ~/portfolio-ai/scripts/check-mypy-coverage.sh`
    - [ ] 5.1.9 Verify exit codes (0 = pass, 1 = fail)
  - [ ] 5.2 Create file size check script (1.5 hours)
    - [ ] 5.2.1 Create `scripts/check-file-sizes.sh` file
    - [ ] 5.2.2 Add shebang: `#!/usr/bin/env bash`
    - [ ] 5.2.3 Add header comment: purpose, limits (500 soft, 800 hard), exceptions
    - [ ] 5.2.4 Add code to find all *.py files: `find backend/app -name "*.py"`
    - [ ] 5.2.5 Add code to count lines with `wc -l`
    - [ ] 5.2.6 Add soft limit check (500): warning output only
    - [ ] 5.2.7 Add hard limit check (800): exit 1 if exceeded
    - [ ] 5.2.8 Add exceptions list: `*schema*.py`, `test_*.py`, `*cli*.py`
    - [ ] 5.2.9 Make executable: `chmod +x scripts/check-file-sizes.sh`
    - [ ] 5.2.10 Test locally: `bash ~/portfolio-ai/scripts/check-file-sizes.sh`
    - [ ] 5.2.11 Verify warnings and exit codes
  - [ ] 5.3 Document CI scripts in DEVELOPMENT.md (30 min)
    - [ ] 5.3.1 Open `docs/core/DEVELOPMENT.md` in editor
    - [ ] 5.3.2 Find appropriate section (e.g., "Testing Workflow" or "Pre-Commit Checklist")
    - [ ] 5.3.3 Add new section: "## CI Quality Gates"
    - [ ] 5.3.4 Document mypy coverage script: usage, threshold (98%), how to run
    - [ ] 5.3.5 Document file size script: usage, limits (500/800), exceptions, how to run
    - [ ] 5.3.6 Add both scripts to pre-commit checklist (manual run before commit)
    - [ ] 5.3.7 Save changes

- [ ] **6.0 Code Quality & Process Improvements** (Low Priority - 1-2 hours)
  - [ ] 6.1 Harden watchlist history endpoint (30 min)
    - [ ] 6.1.1 Open `frontend/lib/api/watchlist.ts` in editor
    - [ ] 6.1.2 Locate fetchScoreHistory function (around line 100)
    - [ ] 6.1.3 Find the 404 fallback logic: `if (!response.ok) { return { item_id, symbol: "", history: [] } }`
    - [ ] 6.1.4 Remove the entire 404 fallback block
    - [ ] 6.1.5 Replace with standard error handling: `if (!response.ok) throw new Error(...)`
    - [ ] 6.1.6 Save file
    - [ ] 6.1.7 Test in browser: verify history loads for valid items
  - [ ] 6.2 Add documentation to Definition of Done (30 min)
    - [ ] 6.2.1 Open `docs/core/DEVELOPMENT.md` in editor
    - [ ] 6.2.2 Find "Definition of Done" or "Production Readiness" section
    - [ ] 6.2.3 Add checkbox item: "[ ] Documentation updated (ARCHITECTURE.md, API_REFERENCE.md, REFACTOR_STATUS.md as needed)"
    - [ ] 6.2.4 Add note: "Run `/doc_it` after major features to sync all documentation"
    - [ ] 6.2.5 Save changes
  - [ ] 6.3 Check if PRD template exists and update (15 min)
    - [ ] 6.3.1 Check if `.ai_dev_tasks/templates/prd-template.md` exists: `test -f ~/portfolio-ai/.ai_dev_tasks/templates/prd-template.md && echo "exists" || echo "not found"`
    - [ ] 6.3.2 If file exists: Open in editor and add "Documentation Updates" section to template
    - [ ] 6.3.3 If file exists: Add reminder to update docs as part of implementation
    - [ ] 6.3.4 If file exists: Save template
    - [ ] 6.3.5 If file doesn't exist: Skip this task
  - [ ] 6.4 Check if task template exists and update (15 min)
    - [ ] 6.4.1 Check if `.ai_dev_tasks/templates/task-template.md` exists: `test -f ~/portfolio-ai/.ai_dev_tasks/templates/task-template.md && echo "exists" || echo "not found"`
    - [ ] 6.4.2 If file exists: Open in editor and add documentation update task to verification checklist
    - [ ] 6.4.3 If file exists: Add reminder about `/doc_it` command
    - [ ] 6.4.4 If file exists: Save template
    - [ ] 6.4.5 If file doesn't exist: Skip this task

- [ ] **7.0 Verification & Completion** (Critical - 1 hour, must be last)
  - [ ] 7.1 Re-run solution alignment check (20 min)
    - [ ] 7.1.1 Verify all tasks 1.0-6.0 are complete
    - [ ] 7.1.2 Run `/check_it` command in chat
    - [ ] 7.1.3 Wait for Gemini analysis to complete (~30-90 seconds)
    - [ ] 7.1.4 Read new `docs/core/SOLUTION_ALIGNMENT.md` report
    - [ ] 7.1.5 Verify overall alignment score is >80% (up from 64%)
    - [ ] 7.1.6 Note any remaining issues or regressions
  - [ ] 7.2 Create trend comparison (15 min)
    - [ ] 7.2.1 Open previous alignment report (dated 2025-10-30, score 64%)
    - [ ] 7.2.2 Open new alignment report from task 7.1.4
    - [ ] 7.2.3 Create comparison table: Category | Previous | Current | Change | Trend
    - [ ] 7.2.4 Calculate improvements: Documentation (20% → ?%), Configuration (40% → ?%), Tests (50% → ?%), Architecture (70% → ?%)
    - [ ] 7.2.5 Document major improvements and any remaining issues
  - [ ] 7.3 Update REFACTOR_STATUS.md with completion (15 min)
    - [ ] 7.3.1 Open `docs/core/REFACTOR_STATUS.md` in editor
    - [ ] 7.3.2 Find "Recent Updates" section
    - [ ] 7.3.3 Add entry: "### PRD #0017: Solution Alignment Fixes - ✅ COMPLETE (2025-10-30)"
    - [ ] 7.3.4 List achievements: Removed DuckDB deps, updated all docs, verified PRD #0016, achieved >80% alignment
    - [ ] 7.3.5 Update "Overall Status" with new alignment score from task 7.1.5
    - [ ] 7.3.6 Save changes
  - [ ] 7.4 Document lessons learned (10 min)
    - [ ] 7.4.1 Add "Lessons Learned" section to `docs/alignment-investigation-report.md`
    - [ ] 7.4.2 Document: "Documentation drift is inevitable after major migrations - plan for cleanup"
    - [ ] 7.4.3 Document: "Dependency cleanup must be coordinated across all config files (pyproject.toml, requirements.txt, pre-commit)"
    - [ ] 7.4.4 Document: "Regular `/check_it` runs (monthly/quarterly) catch drift early"
    - [ ] 7.4.5 Recommend: "Always verify feature status in code before trusting task file status"
    - [ ] 7.4.6 Save lessons learned

---

## Verification & Production Readiness

**MANDATORY before marking task "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All 8 phases completed sequentially
  - [ ] All DuckDB dependencies removed from pyproject.toml and pre-commit config
  - [ ] All documentation updated to reflect PostgreSQL 16 architecture
  - [ ] Test status accurately documented (no contradictory claims)
  - [ ] PRD #0016 status corrected to "COMPLETE" in task file
  - [ ] PRD #0018 created for fixing agent test failures

- [ ] **Alignment Score Achievement** (PRIMARY SUCCESS METRIC)
  - [ ] `/check_it` re-run shows >80% overall alignment (up from 64%)
  - [ ] Documentation Currency >80% (up from 20%)
  - [ ] Configuration Alignment >85% (up from 40%)
  - [ ] Test Coverage & Quality >70% (up from 50%)
  - [ ] Architecture Consistency >85% (up from 70%)

- [ ] **Test Suite Stability**
  - [ ] Full test suite runs without NEW failures
  - [ ] Dependency removal didn't break any tests
  - [ ] Test pass/fail count accurately documented in known-issues.md
  - [ ] Plan created for fixing failing tests (PRD #0018)

- [ ] **Configuration Correctness**
  - [ ] `backend/pyproject.toml` has NO duckdb dependency
  - [ ] `backend/requirements.txt` has NO duckdb entry (verified after regeneration)
  - [ ] `.pre-commit-config.yaml` has NO duckdb in mypy additional_dependencies
  - [ ] All pre-commit hooks pass: `pre-commit run --all-files`

- [ ] **Documentation Consistency**
  - [ ] ZERO contradictions between documentation files
  - [ ] All paths use `~/portfolio-ai/` prefix throughout
  - [ ] Python version consistent (3.13+) across README, CLAUDE, pre-commit
  - [ ] All 6 data sources documented in ARCHITECTURE.md
  - [ ] PostgreSQL architecture fully documented (diagram, data flow, schema, operations)
  - [ ] DuckDB compatibility wrapper documented (not removed, just clarified)

- [ ] **CI Quality Gates**
  - [ ] `scripts/check-mypy-coverage.sh` created, executable, and tested
  - [ ] `scripts/check-file-sizes.sh` created, executable, and tested
  - [ ] Both scripts documented in DEVELOPMENT.md
  - [ ] Scripts added to pre-commit checklist (manual run)

- [ ] **Process Improvements**
  - [ ] "Update documentation" added to Definition of Done in DEVELOPMENT.md
  - [ ] Templates updated with documentation reminders (if they exist)
  - [ ] Lessons learned documented in investigation report

- [ ] **Final Verification**
  - [ ] REFACTOR_STATUS.md updated with PRD #0017 completion
  - [ ] Trend comparison shows improvement in ALL critical categories
  - [ ] No new issues introduced during fixes
  - [ ] Investigation report complete and comprehensive
  - [ ] Project in significantly better state (alignment >80%, was 64%)

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
