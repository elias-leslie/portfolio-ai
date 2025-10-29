# PRD #0012: Solution Alignment Fixes

**Status**: Draft
**Created**: 2025-10-28
**Priority**: Critical
**Effort**: Medium (1-2 weeks)
**Dependencies**: None

---

## Introduction/Overview

The `/check_it` comprehensive solution alignment analysis identified critical and high-priority issues that are blocking optimal system health. This PRD addresses infrastructure fixes to restore test suite integrity, standardize the development environment, and ensure reproducible builds.

**Problem Statement**: The project has 15 failing tests, Python version conflicts between documentation and configuration, and loose dependency specifications that can cause "works on my machine" issues.

**Goal**: Achieve 100% passing test suite, standardized Python 3.13 environment, and fully pinned dependencies for stable, reproducible development.

---

## Goals

1. **Restore Test Suite Integrity**: Fix all 15 failing agent-related tests to achieve 100% passing test suite
2. **Standardize Python Environment**: Migrate to Python 3.13 (latest stable) across all tooling and documentation
3. **Pin All Dependencies**: Lock all dependencies to exact versions for reproducible builds
4. **Document Tailscale Authentication**: Clarify that Tailscale provides secure remote access (no additional API auth needed)
5. **Maintain 86% Test Coverage**: Ensure fixes don't reduce existing test coverage

---

## User Stories

### As a Developer
- I want all tests to pass so I can trust the test suite when making changes
- I want consistent Python versions across all environments so I don't encounter version-related bugs
- I want pinned dependencies so my environment matches exactly with CI/production
- I want clear documentation on security model so I understand how Tailscale protects the API

### As an AI Agent
- I want a reliable test suite so I can validate my code changes automatically
- I want consistent tooling so I don't encounter pre-commit hook failures due to version mismatches
- I want clear guidelines so I know which Python version to use when creating new code

---

## Functional Requirements

### 1. Test Suite Fixes (15 Failing Tests)

**FR-1.1**: Fix all 15 failing tests in agent-related test files
- `backend/tests/test_api_ideas.py` (8 failures)
- `backend/tests/test_discovery_agent.py` (4 failures)
- `backend/tests/test_portfolio_analyzer.py` (3 failures)

**FR-1.2**: For each failing test, determine the cleanest approach:
- Option A: Fix mock configurations if tests are well-structured
- Option B: Use real agent objects if mocks are overly complex
- Option C: Refactor minimal agent code to improve testability

**FR-1.3**: Ensure all fixed tests are meaningful and testing actual functionality (not just passing)

**FR-1.4**: Run full test suite with `pytest backend/tests/ -v --cov=app` and verify:
- All tests pass (no failures, no skipped)
- Test coverage remains ≥86%
- No new warnings introduced

**FR-1.5**: Update `docs/known-issues.md` to move "Pre-Existing Test Failures" to "Resolved Issues"

### 2. Python 3.13 Migration

**FR-2.1**: Update Python version to 3.13 in all configuration files:
- `backend/pyproject.toml`: `requires-python = ">=3.13"`
- `.pre-commit-config.yaml`: Update hooks to use `python: python3.13`
- `SETUP_NOTES.md`: Change from `python3.12-venv` to `python3.13-venv`
- `CLAUDE.md`: Update "Python 3.11+" to "Python 3.13+"
- `docs/core/ARCHITECTURE.md`: Update tech stack section to "Python 3.13+"

**FR-2.2**: Test Python 3.13 compatibility:
- Create fresh Python 3.13 venv
- Install all dependencies from `requirements.txt`
- Run full test suite
- Run all linters (ruff, mypy)
- Start backend and verify all endpoints work

**FR-2.3**: Update Quick Start documentation with Python 3.13 installation:
```bash
# Ubuntu/Debian
sudo apt install python3.13 python3.13-venv

# macOS (Homebrew)
brew install python@3.13
```

**FR-2.4**: Document any breaking changes or migration steps in commit message

### 3. Dependency Pinning

**FR-3.1**: Pin ALL dependencies in `backend/pyproject.toml` to exact versions:
- Replace `>=` with `==` for all dependencies
- Use currently installed versions from `pip freeze` as baseline
- Include all transitive dependencies if not already specified

**FR-3.2**: Update `backend/requirements.txt` with pinned versions:
```bash
pip freeze > backend/requirements.txt
```

**FR-3.3**: Sync `.pre-commit-config.yaml` versions with `pyproject.toml`:
- Ensure ruff, mypy versions match exactly
- Document in `.pre-commit-config.yaml` header: "Versions synced with pyproject.toml"

**FR-3.4**: Update `scripts/validate-versions.sh` to check for version consistency:
- Parse versions from `pyproject.toml`
- Parse versions from `.pre-commit-config.yaml`
- Exit with error if any mismatch found
- Provide clear error messages showing which tools are out of sync

**FR-3.5**: Run `./scripts/validate-versions.sh` and verify it passes

**FR-3.6**: Document dependency update process in `docs/core/DEVELOPMENT.md`:
```markdown
## Updating Dependencies

1. Update version in `backend/pyproject.toml`
2. Run `pip install -e .` to install new version
3. Update corresponding version in `.pre-commit-config.yaml`
4. Run `./scripts/validate-versions.sh` to verify sync
5. Run full test suite to verify compatibility
6. Commit both files together
```

### 4. Tailscale Authentication Documentation

**FR-4.1**: Update `docs/core/API_REFERENCE.md` authentication section:
```markdown
## Authentication

Portfolio AI uses **Tailscale** for secure remote access. No additional API authentication is implemented as Tailscale provides:
- End-to-end encrypted connections
- User authentication via identity provider (Google, GitHub, etc.)
- Access control via Tailscale ACLs
- Audit logging of all connections

**For local access** (localhost:8000): No authentication required
**For remote access** (Tailscale): Authenticated via Tailscale identity

**Security Model**:
- Backend assumes all requests are from authenticated Tailscale users
- No API keys or tokens required
- Single-user deployment model
- Multi-user support requires separate authentication system (future PRD)
```

**FR-4.2**: Update `docs/core/OPERATIONS.md` to include Tailscale setup:
```markdown
## Remote Access via Tailscale

### Setup
1. Install Tailscale on server: `curl -fsSL https://tailscale.com/install.sh | sh`
2. Authenticate: `sudo tailscale up`
3. Enable Tailscale Serve: `tailscale serve https / http://localhost:8000`
4. Access from any Tailscale device: `https://<hostname>.<tailnet>.ts.net`

### Security
- All connections encrypted end-to-end
- Only Tailscale users in your tailnet can access
- Use ACLs to restrict access to specific users/groups
- Audit logs available in Tailscale admin console
```

**FR-4.3**: Update `docs/core/SOLUTION_ALIGNMENT.md` security section:
- Change "No Authentication/Authorization" from Critical to Resolved
- Note: "Tailscale provides authentication for remote access"
- Document: "Multi-user API auth is intentionally deferred (single-user deployment)"

### 5. Validation & Verification

**FR-5.1**: Create pre-commit checklist document `docs/pre-commit-checklist.md`:
```markdown
# Pre-Commit Checklist

Run this checklist before committing ANY changes:

## Automated Checks (run automatically on commit)
- [ ] `ruff format` - Code formatting
- [ ] `ruff check` - Linting
- [ ] `mypy` - Type checking
- [ ] File size checks
- [ ] Trailing whitespace
- [ ] YAML syntax

## Manual Checks (run these yourself)
- [ ] `pytest backend/tests/ -v --cov=app` - All tests pass, ≥86% coverage
- [ ] `./scripts/validate-versions.sh` - Tool versions synced
- [ ] `./scripts/lint.sh` - Full linting suite passes
- [ ] Review changes with `git diff --staged`
- [ ] Verify no debug code or print statements
- [ ] Check commit message follows conventional commits format

## Python Version Check
- [ ] Verify venv uses Python 3.13: `python --version`
- [ ] If version mismatch, recreate venv with Python 3.13

**Never use `--no-verify` to bypass pre-commit hooks!**
```

**FR-5.2**: Run complete validation suite before marking PRD complete:
```bash
# 1. Recreate venv with Python 3.13
cd backend
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -e .

# 3. Run linters
ruff format app/ tests/
ruff check app/ tests/
mypy app/ tests/

# 4. Run tests
pytest tests/ -v --cov=app --cov-report=term-missing

# 5. Validate versions
cd ..
./scripts/validate-versions.sh

# 6. Start backend (smoke test)
cd backend
uvicorn app.main:app --reload &
sleep 5
curl http://localhost:8000/health
kill %1
```

**FR-5.3**: Update `CLAUDE.md` "Current Status" to reflect fixes:
```markdown
**Completed**:
- ✅ MVP v1.0.0 (Oct 2025)
- ✅ PRD #0010 Infrastructure Improvements (100%)
- ✅ PRD #0011 Multi-Source Data & Trading Intelligence (85%)
- ✅ PRD #0012 Solution Alignment Fixes (100%)
  - All tests passing (118+ tests, 86% coverage)
  - Python 3.13 standardization complete
  - All dependencies pinned for reproducibility
  - Tailscale authentication documented
```

---

## Non-Goals (Out of Scope)

1. **API Authentication Implementation**: Tailscale handles authentication; no additional API auth needed
2. **Agent Cost Tracking**: Deferred to PRD #0013 (migrating to headless Claude)
3. **Multi-User Support**: Single-user deployment model is sufficient
4. **Performance Optimization**: Focus is on correctness and stability, not performance
5. **New Features**: This PRD only fixes existing issues, no new functionality
6. **Database Changes**: No schema changes or migrations required
7. **Frontend Changes**: All changes are backend/infrastructure only

---

## Technical Considerations

### Python 3.13 Compatibility
- **New Features**: Type parameter syntax, improved error messages, dead battery removal
- **Breaking Changes**: Minimal for typical code (check release notes)
- **Performance**: ~10% faster than 3.12 for many workloads
- **Type Checking**: Better support for generics and type parameters

### Dependency Pinning Trade-offs
- **Pros**: Reproducible builds, no surprise breakages, easier debugging
- **Cons**: Requires manual updates for security patches, can become outdated
- **Mitigation**: Use Dependabot or similar to track updates, update quarterly

### Test Fixing Strategies
- **Mocking Issues**: Likely caused by `unittest.mock.Mock()` not matching actual interfaces
- **Preferred Fix**: Use `spec=ActualClass` or `spec_set=ActualClass` in mock creation
- **Alternative**: Replace mocks with lightweight real objects (dependency injection)
- **Last Resort**: Refactor agent code to be more testable

### Pre-commit Hook Performance
- Pinning versions ensures hooks run at consistent speed
- Hooks run in virtual environment (not system Python)
- Can add `--fast` flag to ruff for faster checks if needed

---

## Success Metrics

1. **Test Suite Health**:
   - ✅ 0 failing tests (currently 15)
   - ✅ 0 skipped tests
   - ✅ ≥86% test coverage maintained
   - ✅ Test execution time <30 seconds

2. **Version Consistency**:
   - ✅ All docs reference Python 3.13
   - ✅ All config files use Python 3.13
   - ✅ `./scripts/validate-versions.sh` passes with 0 warnings

3. **Dependency Stability**:
   - ✅ 100% of dependencies pinned to exact versions
   - ✅ `pip install -r requirements.txt` produces identical environment
   - ✅ No version conflicts in dependency resolution

4. **Documentation Completeness**:
   - ✅ Tailscale authentication model documented in 3 places
   - ✅ Pre-commit checklist created
   - ✅ Dependency update process documented

5. **Pre-commit Success Rate**:
   - ✅ Pre-commit hooks pass on first try (no version mismatch errors)
   - ✅ No developer needs to use `--no-verify`

---

## Open Questions

1. ~~Should we implement API authentication?~~ **RESOLVED**: No, Tailscale provides authentication
2. ~~Which Python version to standardize on?~~ **RESOLVED**: Python 3.13 (latest stable)
3. ~~How aggressively to pin dependencies?~~ **RESOLVED**: Pin everything for maximum stability
4. **Q1**: Are there any known incompatibilities between Python 3.13 and our current dependencies?
   - **Action**: Test in Python 3.13 venv before implementing
5. **Q2**: Should we create a `pyproject.toml` entry for Python 3.13 in `tool.mypy` or `tool.ruff`?
   - **Action**: Check if tools respect `requires-python` or need explicit target version

---

## Implementation Notes

### Test Fixing Priority Order
1. Fix `test_api_ideas.py` first (8 failures, highest count)
2. Fix `test_discovery_agent.py` next (4 failures)
3. Fix `test_portfolio_analyzer.py` last (3 failures)

### Python 3.13 Migration Risks
- **Low Risk**: Most code is type-safe and doesn't use deprecated features
- **Medium Risk**: Some dependencies may not have Python 3.13 wheels yet
- **Mitigation**: Test in separate venv before committing, fallback to 3.12 if needed

### Dependency Pinning Best Practices
- Pin to versions currently in use (from `pip freeze`)
- Document pinned versions in commit message
- Set reminder to review/update dependencies quarterly
- Use `pip-audit` to check for known vulnerabilities

---

## Acceptance Criteria

**This PRD is complete when:**

1. ✅ All 118+ tests pass with 0 failures, 0 skipped
2. ✅ Test coverage remains ≥86%
3. ✅ Python 3.13 is used in all docs and config files
4. ✅ All dependencies in `backend/pyproject.toml` use `==` version pinning
5. ✅ `./scripts/validate-versions.sh` passes with no warnings
6. ✅ Backend starts successfully with Python 3.13
7. ✅ All API endpoints return expected responses (smoke test)
8. ✅ Pre-commit hooks pass on first run (no version conflicts)
9. ✅ Tailscale authentication is documented in `API_REFERENCE.md` and `OPERATIONS.md`
10. ✅ `docs/known-issues.md` shows "Pre-Existing Test Failures" as resolved
11. ✅ `docs/pre-commit-checklist.md` created and referenced in `DEVELOPMENT.md`
12. ✅ Git commit created with conventional commits format

**Verification Command**:
```bash
# This single command must succeed
source backend/.venv/bin/activate && \
python --version | grep "3.13" && \
./scripts/validate-versions.sh && \
pytest backend/tests/ -v --cov=app && \
./scripts/lint.sh
```

---

## Related PRDs

- **PRD #0010**: Quick Wins & Infrastructure Improvements (completed)
- **PRD #0011**: Multi-Source Data & Trading Intelligence (85% complete)
- **PRD #0013**: Headless AI Migration (to be created)

---

## References

- Solution Alignment Report: `docs/core/SOLUTION_ALIGNMENT.md`
- Python 3.13 Release Notes: https://docs.python.org/3/whatsnew/3.13.html
- Tailscale Documentation: https://tailscale.com/kb/
- Pre-commit Documentation: https://pre-commit.com/
