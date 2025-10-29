# Task List: Solution Alignment Fixes

**PRD**: `0012-prd-solution-alignment-fixes.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: MEDIUM (1-2 weeks)
**Last Updated**: 2025-10-28

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. Begin with Task 1.0 (Fix 15 failing tests)
2. Task 2.0 (Python 3.13 migration) - requires Python 3.13 installation
3. Task 3.0 (Pin all dependencies)
4. Task 4.0 (Document Tailscale authentication)
5. Task 5.0 (Final validation and verification)

**EFFORT TO COMPLETE:** MEDIUM (1-2 weeks, ~40-60 hours)

**Context from Current State**:
- Current Python: 3.12.3 (need to migrate to 3.13)
- Current pyproject.toml: `requires-python = ">=3.11"` (needs update to `>=3.13"`)
- Pre-commit tools: ruff 0.14.2, mypy 1.18.2 (need to pin in pyproject.toml)
- 15 failing tests in agent-related test files
- Test coverage: 86% (must maintain)

---

## Relevant Files

### Files to Update (11 files)

**Test Files (Fix failing tests):**
- `backend/tests/test_api_ideas.py` - Fix 8 failing tests (mock configuration issues)
- `backend/tests/test_discovery_agent.py` - Fix 4 failing tests (mock configuration issues)
- `backend/tests/test_portfolio_analyzer.py` - Fix 3 failing tests (mock configuration issues)

**Configuration Files (Python 3.13 migration + dependency pinning):**
- `backend/pyproject.toml` - Update `requires-python = ">=3.13"`, pin all dependencies to exact versions
- `backend/requirements.txt` - Regenerate with `pip freeze` after Python 3.13 migration
- `.pre-commit-config.yaml` - Update to use Python 3.13, sync tool versions with pyproject.toml

**Documentation Files (Python 3.13 + Tailscale auth):**
- `SETUP_NOTES.md` - Change `python3.12-venv` to `python3.13-venv`
- `CLAUDE.md` - Update "Python 3.11+" to "Python 3.13+"
- `docs/core/ARCHITECTURE.md` - Update tech stack to "Python 3.13+"
- `docs/core/API_REFERENCE.md` - Add Tailscale authentication section
- `docs/core/OPERATIONS.md` - Add Tailscale remote access setup
- `docs/core/SOLUTION_ALIGNMENT.md` - Mark authentication issue as resolved
- `docs/core/DEVELOPMENT.md` - Add dependency update process
- `docs/known-issues.md` - Move test failures to "Resolved Issues"

**Validation Scripts:**
- `scripts/validate-versions.sh` - Enhance to check pyproject.toml vs pre-commit config

### Files to Create (1 file)

- `docs/pre-commit-checklist.md` (~80 lines) - Pre-commit checklist for developers

### Notes

- **Python 3.13 Installation Required**: Must install Python 3.13 before starting Task 2.0
  - Ubuntu/Debian: `sudo apt install python3.13 python3.13-venv`
  - macOS: `brew install python@3.13`
- **Backup Recommendation**: Create database backup before starting (precautionary)
- **Testing Strategy**: Run full test suite after each major task to catch regressions early
- Use `pytest backend/tests/ -v --cov=app` to run all tests with coverage
- Use `./scripts/lint.sh` to run full linting suite
- Use `./scripts/validate-versions.sh` to verify tool version sync

---

## Tasks

- [ ] 1.0 Fix Failing Test Suite (15 Tests) [EFFORT: HIGH]
  - [ ] 1.1 Analyze failing tests and determine fix strategy
    - [ ] 1.1.1 Run `pytest backend/tests/test_api_ideas.py -v` to see 8 failures
    - [ ] 1.1.2 Run `pytest backend/tests/test_discovery_agent.py -v` to see 4 failures
    - [ ] 1.1.3 Run `pytest backend/tests/test_portfolio_analyzer.py -v` to see 3 failures
    - [ ] 1.1.4 Document error messages and root causes (likely mock.return_value or mock.spec issues)
    - [ ] 1.1.5 Decide strategy per test: fix mocks (Option A), use real objects (Option B), or refactor code (Option C)
  - [ ] 1.2 Fix test_api_ideas.py (8 failures)
    - [ ] 1.2.1 Read current test file to understand test structure
    - [ ] 1.2.2 For each failing test, apply chosen fix strategy:
      - [ ] Option A: Add `spec=ActualClass` or `spec_set=ActualClass` to Mock() calls
      - [ ] Option B: Replace mocks with lightweight real agent instances (if mocks too complex)
      - [ ] Option C: Refactor agent code minimally to improve testability
    - [ ] 1.2.3 Run `pytest backend/tests/test_api_ideas.py -v` after each fix
    - [ ] 1.2.4 Verify all 8 tests now pass
  - [ ] 1.3 Fix test_discovery_agent.py (4 failures)
    - [ ] 1.3.1 Read current test file to understand test structure
    - [ ] 1.3.2 Apply same fix strategy as 1.2.2 to each failing test
    - [ ] 1.3.3 Run `pytest backend/tests/test_discovery_agent.py -v` after each fix
    - [ ] 1.3.4 Verify all 4 tests now pass
  - [ ] 1.4 Fix test_portfolio_analyzer.py (3 failures)
    - [ ] 1.4.1 Read current test file to understand test structure
    - [ ] 1.4.2 Apply same fix strategy as 1.2.2 to each failing test
    - [ ] 1.4.3 Run `pytest backend/tests/test_portfolio_analyzer.py -v` after each fix
    - [ ] 1.4.4 Verify all 3 tests now pass
  - [ ] 1.5 Verify full test suite and coverage
    - [ ] 1.5.1 Run `pytest backend/tests/ -v --cov=app --cov-report=term-missing`
    - [ ] 1.5.2 Verify: All tests pass (0 failures, 0 skipped)
    - [ ] 1.5.3 Verify: Coverage ≥86% (should be maintained or improved)
    - [ ] 1.5.4 Verify: No new warnings introduced
    - [ ] 1.5.5 Run `./scripts/lint.sh` to ensure no regressions
  - [ ] 1.6 Update known-issues.md
    - [ ] 1.6.1 Move "Pre-Existing Test Failures" from "Active Issues" to "Resolved Issues"
    - [ ] 1.6.2 Add resolution details: date resolved, approach used, commit hash
    - [ ] 1.6.3 Commit changes with message: "fix: resolve 15 failing agent tests with mock configuration fixes"

- [ ] 2.0 Migrate to Python 3.13 [EFFORT: MEDIUM]
  - [ ] 2.1 Install Python 3.13
    - [ ] 2.1.1 Check if Python 3.13 already installed: `python3.13 --version`
    - [ ] 2.1.2 If not installed:
      - [ ] Ubuntu/Debian: `sudo apt update && sudo apt install python3.13 python3.13-venv python3.13-dev`
      - [ ] macOS: `brew install python@3.13`
    - [ ] 2.1.3 Verify installation: `python3.13 --version` (should show 3.13.x)
  - [ ] 2.2 Create fresh Python 3.13 virtual environment
    - [ ] 2.2.1 Backup current venv: `mv backend/.venv backend/.venv.python312.backup`
    - [ ] 2.2.2 Create new venv: `cd backend && python3.13 -m venv .venv`
    - [ ] 2.2.3 Activate new venv: `source backend/.venv/bin/activate`
    - [ ] 2.2.4 Verify Python version in venv: `python --version` (should show 3.13.x)
  - [ ] 2.3 Install dependencies in Python 3.13 venv
    - [ ] 2.3.1 Upgrade pip: `pip install --upgrade pip setuptools wheel`
    - [ ] 2.3.2 Install dependencies: `pip install -r backend/requirements.txt`
    - [ ] 2.3.3 Install package in editable mode: `pip install -e backend/`
    - [ ] 2.3.4 Verify no installation errors or warnings
  - [ ] 2.4 Test Python 3.13 compatibility
    - [ ] 2.4.1 Run full test suite: `pytest backend/tests/ -v --cov=app`
    - [ ] 2.4.2 Verify all tests pass (0 failures)
    - [ ] 2.4.3 Run linters: `ruff check backend/app/ backend/tests/`
    - [ ] 2.4.4 Run type checker: `mypy backend/app/ --strict`
    - [ ] 2.4.5 Start backend: `uvicorn app.main:app --reload` (in backend dir)
    - [ ] 2.4.6 Test health endpoint: `curl http://localhost:8000/health`
    - [ ] 2.4.7 Test portfolio endpoint: `curl http://localhost:8000/api/portfolio`
    - [ ] 2.4.8 Stop backend (Ctrl+C)
    - [ ] 2.4.9 Document any issues or breaking changes
  - [ ] 2.5 Update configuration files for Python 3.13
    - [ ] 2.5.1 Update `backend/pyproject.toml`: Change `requires-python = ">=3.11"` to `requires-python = ">=3.13"`
    - [ ] 2.5.2 Update `.pre-commit-config.yaml`: Add `language_version: python3.13` to relevant hooks
    - [ ] 2.5.3 Verify pre-commit works: `pre-commit run --all-files`
  - [ ] 2.6 Update documentation for Python 3.13
    - [ ] 2.6.1 Update `SETUP_NOTES.md`: Change `python3.12-venv` to `python3.13-venv`
    - [ ] 2.6.2 Update `CLAUDE.md`: Change "Python 3.11+" to "Python 3.13+"
    - [ ] 2.6.3 Update `docs/core/ARCHITECTURE.md`: Update tech stack section to "Python 3.13+"
    - [ ] 2.6.4 Update `CLAUDE.md` Quick Start: Add Python 3.13 installation commands
    - [ ] 2.6.5 Update `docs/core/SETUP.md`: Add Python 3.13 prerequisites
  - [ ] 2.7 Commit Python 3.13 migration
    - [ ] 2.7.1 Stage all changes: `git add backend/pyproject.toml .pre-commit-config.yaml SETUP_NOTES.md CLAUDE.md docs/core/ARCHITECTURE.md docs/core/SETUP.md`
    - [ ] 2.7.2 Commit: "feat: migrate to Python 3.13 for latest features and performance"
    - [ ] 2.7.3 Verify pre-commit hooks pass
    - [ ] 2.7.4 Document breaking changes in commit message if any

- [ ] 3.0 Pin All Dependencies [EFFORT: MEDIUM]
  - [ ] 3.1 Pin dependencies in pyproject.toml
    - [ ] 3.1.1 Run `pip freeze > backend/requirements-freeze.txt` to capture exact versions
    - [ ] 3.1.2 Open `backend/pyproject.toml` and locate `[project.dependencies]` section
    - [ ] 3.1.3 For each dependency with `>=`, replace with `==` using versions from requirements-freeze.txt
    - [ ] 3.1.4 Add any missing transitive dependencies from requirements-freeze.txt
    - [ ] 3.1.5 Special attention to: fastapi, uvicorn, duckdb, pydantic, anthropic, yfinance, pandas, celery, redis
    - [ ] 3.1.6 Save pyproject.toml
  - [ ] 3.2 Regenerate requirements.txt with pinned versions
    - [ ] 3.2.1 Uninstall all packages: `pip freeze | xargs pip uninstall -y` (in venv)
    - [ ] 3.2.2 Reinstall from updated pyproject.toml: `pip install -e backend/`
    - [ ] 3.2.3 Generate new requirements.txt: `pip freeze > backend/requirements.txt`
    - [ ] 3.2.4 Verify requirements.txt has exact versions (all `==`, no `>=`)
    - [ ] 3.2.5 Test installation from requirements.txt: `pip install -r backend/requirements.txt`
  - [ ] 3.3 Sync pre-commit config with pyproject.toml versions
    - [ ] 3.3.1 Extract ruff version from pyproject.toml (e.g., `ruff==0.14.2`)
    - [ ] 3.3.2 Extract mypy version from pyproject.toml (e.g., `mypy==1.18.2`)
    - [ ] 3.3.3 Update `.pre-commit-config.yaml`:
      - [ ] Update `astral-sh/ruff-pre-commit` repo rev to match ruff version (e.g., `v0.14.2`)
      - [ ] Update `pre-commit/mirrors-mypy` repo rev to match mypy version (e.g., `v1.18.2`)
    - [ ] 3.3.4 Add comment at top of `.pre-commit-config.yaml`: `# Versions synced with backend/pyproject.toml - ruff 0.14.2, mypy 1.18.2`
    - [ ] 3.3.5 Run `pre-commit clean` to clear cache
    - [ ] 3.3.6 Run `pre-commit install --install-hooks` to reinstall hooks with new versions
    - [ ] 3.3.7 Test: `pre-commit run --all-files` (should pass)
  - [ ] 3.4 Enhance validate-versions.sh script
    - [ ] 3.4.1 Open `scripts/validate-versions.sh`
    - [ ] 3.4.2 Add function to parse ruff version from `backend/pyproject.toml`
    - [ ] 3.4.3 Add function to parse mypy version from `backend/pyproject.toml`
    - [ ] 3.4.4 Add function to parse ruff rev from `.pre-commit-config.yaml`
    - [ ] 3.4.5 Add function to parse mypy rev from `.pre-commit-config.yaml`
    - [ ] 3.4.6 Add version comparison logic (exit 1 if mismatch)
    - [ ] 3.4.7 Add clear error messages showing expected vs actual versions
    - [ ] 3.4.8 Test script: `./scripts/validate-versions.sh` (should pass)
  - [ ] 3.5 Document dependency update process
    - [ ] 3.5.1 Open `docs/core/DEVELOPMENT.md`
    - [ ] 3.5.2 Add new section "## Updating Dependencies"
    - [ ] 3.5.3 Add steps:
      1. Update version in `backend/pyproject.toml` (change `==` version)
      2. Run `pip install -e backend/` to install new version
      3. Run `pip freeze > backend/requirements.txt` to update requirements.txt
      4. Update corresponding version in `.pre-commit-config.yaml` (rev field)
      5. Run `pre-commit clean && pre-commit install --install-hooks`
      6. Run `./scripts/validate-versions.sh` to verify sync
      7. Run full test suite to verify compatibility: `pytest backend/tests/ -v --cov=app`
      8. Commit both files together with descriptive message
    - [ ] 3.5.4 Add warning: "Never update pyproject.toml without updating .pre-commit-config.yaml"
  - [ ] 3.6 Verify dependency pinning complete
    - [ ] 3.6.1 Run `./scripts/validate-versions.sh` (must pass with 0 warnings)
    - [ ] 3.6.2 Check `backend/pyproject.toml`: Verify all dependencies use `==`
    - [ ] 3.6.3 Check `backend/requirements.txt`: Verify all dependencies use `==`
    - [ ] 3.6.4 Run full test suite: `pytest backend/tests/ -v --cov=app` (all pass)
    - [ ] 3.6.5 Run pre-commit: `pre-commit run --all-files` (all pass)
  - [ ] 3.7 Commit dependency pinning
    - [ ] 3.7.1 Stage changes: `git add backend/pyproject.toml backend/requirements.txt .pre-commit-config.yaml scripts/validate-versions.sh docs/core/DEVELOPMENT.md`
    - [ ] 3.7.2 Commit: "feat: pin all dependencies to exact versions for reproducible builds"
    - [ ] 3.7.3 Verify pre-commit hooks pass

- [ ] 4.0 Document Tailscale Authentication [EFFORT: LOW]
  - [ ] 4.1 Update API_REFERENCE.md authentication section
    - [ ] 4.1.1 Open `docs/core/API_REFERENCE.md`
    - [ ] 4.1.2 Locate "## Authentication" section (should be near top)
    - [ ] 4.1.3 Replace current content with Tailscale authentication model:
      - [ ] Explain Tailscale provides authentication (no API keys needed)
      - [ ] List Tailscale features: E2E encryption, identity provider auth, ACLs, audit logs
      - [ ] Document: Local access (localhost:8000) = no auth, Remote access = Tailscale auth
      - [ ] Document security model: Backend assumes authenticated users, single-user deployment
      - [ ] Note: Multi-user support requires separate auth system (future PRD)
    - [ ] 4.1.4 Save file
  - [ ] 4.2 Update OPERATIONS.md with Tailscale setup
    - [ ] 4.2.1 Open `docs/core/OPERATIONS.md`
    - [ ] 4.2.2 Add new section "## Remote Access via Tailscale" (after deployment section)
    - [ ] 4.2.3 Add subsection "### Setup" with installation steps:
      1. Install Tailscale: `curl -fsSL https://tailscale.com/install.sh | sh`
      2. Authenticate: `sudo tailscale up`
      3. Enable Tailscale Serve: `tailscale serve https / http://localhost:8000`
      4. Access from any device: `https://<hostname>.<tailnet>.ts.net`
    - [ ] 4.2.4 Add subsection "### Security" with security features:
      - [ ] End-to-end encryption
      - [ ] Tailscale user authentication
      - [ ] ACL configuration for access control
      - [ ] Audit logs in Tailscale admin console
    - [ ] 4.2.5 Save file
  - [ ] 4.3 Update SOLUTION_ALIGNMENT.md security section
    - [ ] 4.3.1 Open `docs/core/SOLUTION_ALIGNMENT.md`
    - [ ] 4.3.2 Locate "### 6. Security Best Practices" section
    - [ ] 4.3.3 Update "Misalignments" subsection:
      - [ ] Change "No Authentication/Authorization" from Critical to Resolved
      - [ ] Add note: "Tailscale provides authentication for remote access"
      - [ ] Add note: "Multi-user API auth is intentionally deferred (single-user deployment model)"
    - [ ] 4.3.4 Update "Critical Issues Count" in Executive Summary (reduce by 1)
    - [ ] 4.3.5 Save file
  - [ ] 4.4 Commit Tailscale documentation
    - [ ] 4.4.1 Stage changes: `git add docs/core/API_REFERENCE.md docs/core/OPERATIONS.md docs/core/SOLUTION_ALIGNMENT.md`
    - [ ] 4.4.2 Commit: "docs: document Tailscale authentication model and setup"
    - [ ] 4.4.3 Verify pre-commit hooks pass

- [ ] 5.0 Final Validation & Verification [EFFORT: MEDIUM]
  - [ ] 5.1 Create pre-commit checklist document
    - [ ] 5.1.1 Create file `docs/pre-commit-checklist.md`
    - [ ] 5.1.2 Add title: "# Pre-Commit Checklist"
    - [ ] 5.1.3 Add section "## Automated Checks (run automatically on commit)":
      - [ ] ruff format - Code formatting
      - [ ] ruff check - Linting
      - [ ] mypy - Type checking
      - [ ] File size checks
      - [ ] Trailing whitespace
      - [ ] YAML syntax
    - [ ] 5.1.4 Add section "## Manual Checks (run these yourself)":
      - [ ] `pytest backend/tests/ -v --cov=app` - All tests pass, ≥86% coverage
      - [ ] `./scripts/validate-versions.sh` - Tool versions synced
      - [ ] `./scripts/lint.sh` - Full linting suite passes
      - [ ] Review changes with `git diff --staged`
      - [ ] Verify no debug code or print statements
      - [ ] Check commit message follows conventional commits format
    - [ ] 5.1.5 Add section "## Python Version Check":
      - [ ] Verify venv uses Python 3.13: `python --version`
      - [ ] If version mismatch, recreate venv with Python 3.13
    - [ ] 5.1.6 Add warning: "**Never use `--no-verify` to bypass pre-commit hooks!**"
    - [ ] 5.1.7 Save file
  - [ ] 5.2 Update DEVELOPMENT.md to reference pre-commit checklist
    - [ ] 5.2.1 Open `docs/core/DEVELOPMENT.md`
    - [ ] 5.2.2 Locate "Pre-commit Workflow" or similar section
    - [ ] 5.2.3 Add reference: "See [Pre-Commit Checklist](../pre-commit-checklist.md) for complete checklist"
    - [ ] 5.2.4 Save file
  - [ ] 5.3 Run comprehensive validation suite
    - [ ] 5.3.1 Activate venv: `source backend/.venv/bin/activate`
    - [ ] 5.3.2 Verify Python version: `python --version | grep "3.13"`
    - [ ] 5.3.3 Run linters: `ruff format backend/app/ backend/tests/`
    - [ ] 5.3.4 Run linters: `ruff check backend/app/ backend/tests/`
    - [ ] 5.3.5 Run type checker: `mypy backend/app/ backend/tests/`
    - [ ] 5.3.6 Run full test suite: `pytest backend/tests/ -v --cov=app --cov-report=term-missing`
    - [ ] 5.3.7 Verify: All tests pass (0 failures, 0 skipped)
    - [ ] 5.3.8 Verify: Coverage ≥86%
    - [ ] 5.3.9 Run version validation: `./scripts/validate-versions.sh`
    - [ ] 5.3.10 Run full lint script: `./scripts/lint.sh`
    - [ ] 5.3.11 Start backend: `cd backend && uvicorn app.main:app --reload`
    - [ ] 5.3.12 Test health endpoint: `curl http://localhost:8000/health` (should return healthy)
    - [ ] 5.3.13 Test portfolio endpoint: `curl http://localhost:8000/api/portfolio` (should return data or empty array)
    - [ ] 5.3.14 Stop backend (Ctrl+C)
    - [ ] 5.3.15 Document validation results
  - [ ] 5.4 Update project status documentation
    - [ ] 5.4.1 Open `CLAUDE.md`
    - [ ] 5.4.2 Update "Current Status" section to add:
      ```markdown
      - ✅ PRD #0012 Solution Alignment Fixes (100% complete)
        - All tests passing (118+ tests, 86%+ coverage)
        - Python 3.13 standardization complete
        - All dependencies pinned for reproducibility
        - Tailscale authentication documented
      ```
    - [ ] 5.4.3 Open `docs/core/REFACTOR_STATUS.md`
    - [ ] 5.4.4 Update "Recent Updates" section to add PRD #0012 completion
    - [ ] 5.4.5 Move tech debt items to "Resolved" if fixed by this PRD
    - [ ] 5.4.6 Save both files
  - [ ] 5.5 Final commit and validation
    - [ ] 5.5.1 Stage all remaining changes: `git add docs/pre-commit-checklist.md docs/core/DEVELOPMENT.md CLAUDE.md docs/core/REFACTOR_STATUS.md`
    - [ ] 5.5.2 Commit: "docs: add pre-commit checklist and update project status for PRD #0012 completion"
    - [ ] 5.5.3 Verify pre-commit hooks pass
    - [ ] 5.5.4 Run final validation: `./scripts/validate-versions.sh && pytest backend/tests/ -v --cov=app`
    - [ ] 5.5.5 Mark this task list as COMPLETE (update status at top of file)

---

## Verification & Production Readiness

**MANDATORY before marking PRD #0012 "COMPLETE ✅":**

- [ ] **Functional Completeness**
  - [ ] All 15 failing tests now pass
  - [ ] Python 3.13 installed and used in venv
  - [ ] All dependencies pinned to exact versions
  - [ ] Tailscale authentication documented in 3 locations
  - [ ] Pre-commit checklist created

- [ ] **Test Coverage** (target: 86%+)
  - [ ] All tests passing: `pytest backend/tests/ -v` returns 0 failures
  - [ ] Coverage maintained: `pytest backend/tests/ --cov=app --cov-report=term-missing` shows ≥86%
  - [ ] No skipped tests (unless explicitly documented as optional)

- [ ] **Type Safety & Code Quality**
  - [ ] Type checking passes: `mypy backend/app/ backend/tests/ --strict` returns 0 errors
  - [ ] Linting passes: `ruff check backend/app/ backend/tests/` returns 0 errors
  - [ ] Formatting applied: `ruff format backend/app/ backend/tests/` makes no changes
  - [ ] Version sync passes: `./scripts/validate-versions.sh` returns 0 warnings

- [ ] **Documentation**
  - [ ] Python 3.13 documented in 5 files (pyproject.toml, pre-commit, SETUP_NOTES, CLAUDE, ARCHITECTURE)
  - [ ] Tailscale auth documented in 3 files (API_REFERENCE, OPERATIONS, SOLUTION_ALIGNMENT)
  - [ ] Dependency update process documented in DEVELOPMENT.md
  - [ ] Pre-commit checklist created and referenced

- [ ] **Operational Readiness**
  - [ ] Backend starts successfully with Python 3.13: `uvicorn app.main:app --reload`
  - [ ] Health endpoint returns 200: `curl http://localhost:8000/health`
  - [ ] Pre-commit hooks pass on all files: `pre-commit run --all-files`
  - [ ] known-issues.md shows test failures resolved

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
