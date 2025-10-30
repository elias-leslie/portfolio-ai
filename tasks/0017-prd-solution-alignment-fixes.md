# PRD #0017: Solution Alignment Fixes

**Created**: 2025-10-30
**Status**: Ready for Implementation
**Priority**: CRITICAL
**Complexity**: HIGH
**Estimated Effort**: 2-3 days

---

## Introduction/Overview

The `/check_it` analysis (2025-10-30) revealed that the Portfolio AI Platform's overall alignment score has regressed from 77% to 64%, with severe documentation drift and critical configuration mismatches stemming from the PostgreSQL migration. This PRD addresses all identified alignment issues to restore project integrity and bring the alignment score above 80%.

**Problem**: Key documents and dependencies still reference the legacy DuckDB system despite the completed PostgreSQL migration. Additionally, there are contradictions in feature completion status, test reporting inaccuracies, and incomplete cleanup that undermine developer confidence and project maintainability.

**Goal**: Eliminate all critical, high, medium, and low-priority alignment issues identified in `docs/core/SOLUTION_ALIGNMENT.md`, achieving >80% alignment score on re-run of `/check_it`.

---

## Goals

1. **Eliminate Documentation Drift**: Update all documentation to accurately reflect the PostgreSQL architecture and current feature status
2. **Remove DuckDB Artifacts**: Completely remove DuckDB dependencies and references from the codebase
3. **Restore Test Integrity**: Accurately document test failures and create a plan to fix them
4. **Verify Feature Status**: Investigate and document the true status of PRD #0016 (multi-source failover)
5. **Implement Quality Gates**: Add CI enforcement for coding standards
6. **Achieve >80% Alignment**: Re-run `/check_it` and verify improvement

---

## User Stories

1. **As a new developer**, I want documentation that accurately reflects the current architecture so that I can understand and contribute to the project without confusion.

2. **As a maintainer**, I want all dependencies to be correct and necessary so that the project installs cleanly and doesn't carry legacy baggage.

3. **As a developer**, I want accurate test status reporting so that I can trust the test suite and know when I've broken something.

4. **As a project lead**, I want a clear understanding of feature completion status so that I can accurately report progress and plan next steps.

5. **As a contributor**, I want automated quality gates so that I can't accidentally merge code that violates project standards.

---

## Functional Requirements

### Phase 1: Investigation & Audit (Critical)

**FR1.1**: Investigate PRD #0016 actual implementation status
- Review `backend/app/portfolio/price_fetcher.py` to determine if 6-source failover is implemented
- Check for integration with all 6 sources (YFinance, TwelveData, FMP, Polygon, Finnhub, AlphaVantage)
- Document findings in a status report
- Update either `REFACTOR_STATUS.md` or `tasks/tasks-0016-prd-complete-multi-source-failover.md` to reflect reality

**FR1.2**: Audit codebase for DuckDB references
- Search all Python files for `duckdb` imports, references, or connections
- Search all documentation for "DuckDB" or "duckdb" (case-insensitive)
- Search all configuration files for DuckDB dependencies
- Create a comprehensive list of all locations requiring updates

**FR1.3**: Verify test status accuracy
- Run full test suite and capture actual pass/fail counts
- Document which tests are failing and why
- Update `docs/known-issues.md` with accurate test failure information
- Update `tasks/tasks-0015-postgresql-migration.md` to remove "100% passing" claim if inaccurate

### Phase 2: Dependency & Configuration Cleanup (Critical)

**FR2.1**: Remove DuckDB from Python dependencies
- Remove `duckdb==1.4.1` from `backend/pyproject.toml`
- Regenerate `backend/requirements.txt` via `pip freeze`
- Remove `duckdb>=1.4.0` from `.pre-commit-config.yaml` mypy hook dependencies
- Verify no DuckDB code remains in `backend/app/` (based on FR1.2 audit)

**FR2.2**: Update dependency documentation
- Update any documentation that references DuckDB installation or setup
- Verify `backend/requirements.txt` only contains necessary dependencies

**FR2.3**: Run full test suite after dependency removal
- Execute `pytest tests/ -v --cov=app` after dependency changes
- Document any new failures or issues
- Verify removal didn't break anything (should pass same tests as before)

### Phase 3: Documentation Overhaul (High Priority)

**FR3.1**: Update root documentation
- `README.md`: Replace all DuckDB references with PostgreSQL 16
- `CLAUDE.md`: Update "Project Structure" section to remove "DuckDB storage layer" reference
- `PROJECT_STRUCTURE.md`: Update `backend/data/` description to reflect PostgreSQL usage (no database files)

**FR3.2**: Update core documentation
- `docs/core/ARCHITECTURE.md`:
  - Update architecture diagram (replace DuckDB with PostgreSQL)
  - Update data flow descriptions
  - Update schema examples to show PostgreSQL types
  - Update "Why PostgreSQL?" section with migration rationale
- `docs/core/SETUP.md`: Update setup instructions for PostgreSQL instead of DuckDB
- `docs/core/OPERATIONS.md`: Remove DuckDB troubleshooting, add PostgreSQL operations
- `docs/core/REFACTOR_STATUS.md`: Verify all status claims match reality (based on FR1.1 findings)

**FR3.3**: Update Python version consistency
- Standardize on Python 3.13+ across all documentation
- Update `README.md` if it specifies Python 3.11+

**FR3.4**: Verify external data sources documentation
- Ensure `ARCHITECTURE.md` lists all 6 operational sources (not just yfinance, FRED, News)
- Update data source priority order if needed

### Phase 4: Test Integrity & Documentation (High Priority)

**FR4.1**: Document test failures accurately
- Update `docs/known-issues.md` with current, accurate test failure information
- Remove any claims of "100% test pass rate" from task files or documentation
- Create issue tracker entry or separate PRD for fixing the 15 agent-related test failures

**FR4.2**: Verify test reporting accuracy
- Ensure no contradictory claims exist between different documentation files
- Add a note in task completion documentation about how to verify test status

### Phase 5: Feature Status Verification (Medium Priority)

**FR5.1**: Implement or document 6-source failover status
- If FR1.1 shows it's NOT implemented: Update `REFACTOR_STATUS.md` to mark PRD #0016 as incomplete
- If FR1.1 shows it IS implemented: Update `tasks/tasks-0016-prd-complete-multi-source-failover.md` to mark as complete
- Ensure consistency between all documentation sources

**FR5.2**: Update ARCHITECTURE.md with actual implementation
- Document the actual multi-source failover architecture (if implemented)
- Include all 6 sources in the architecture diagram/description

### Phase 6: CI Enforcement & Quality Gates (Medium Priority)

**FR6.1**: Add CI checks for mypy coverage
- Create a script or CI step that checks mypy coverage threshold (98%+)
- Document how to run this check locally

**FR6.2**: Add CI checks for file size limits
- Create a script or CI step that fails if any file exceeds 800 lines (hard limit)
- Warn if any file exceeds 500 lines (soft limit)
- Document exceptions (schema files, test files, CLI files)

### Phase 7: Code Quality Improvements (Low Priority)

**FR7.1**: Harden watchlist history endpoint
- Remove temporary 404-handling logic from `frontend/lib/api/watchlist.ts:fetchScoreHistory`
- Ensure `/api/watchlist/{itemId}/history` endpoint is always available for valid items
- Add appropriate error handling for invalid item IDs

**FR7.2**: Establish documentation maintenance process
- Add documentation update requirement to "Definition of Done" checklist in `DEVELOPMENT.md`
- Create a reminder in PRD/task templates to update documentation

### Phase 8: Verification & Completion (Critical)

**FR8.1**: Re-run solution alignment check
- Execute `/check_it` command after all fixes are complete
- Verify alignment score is >80%
- Document improvement in the new SOLUTION_ALIGNMENT.md report

**FR8.2**: Create trend comparison
- Compare new scores to previous report (2025-10-30)
- Document improvements in each category
- Identify any remaining issues

**FR8.3**: Update REFACTOR_STATUS.md
- Mark this PRD as complete
- Update overall project status
- Document lessons learned about maintaining alignment

---

## Non-Goals (Out of Scope)

1. **Fixing the 15 failing agent tests** - This will be addressed in a separate PRD (per user preference)
2. **Implementing new features** - This PRD focuses solely on alignment fixes, not new capabilities
3. **Performance optimization** - No performance improvements are in scope
4. **Refactoring large files** - File size limit enforcement is in scope, but refactoring existing large files is not
5. **Implementing authentication** - Security improvements mentioned in the report are out of scope for this PRD
6. **Adding new data sources** - Only documenting existing sources is in scope

---

## Design Considerations

### Documentation Structure
- All path references must use `~/portfolio-ai/` prefix (per path standardization rule)
- Documentation should be clear enough for junior developers
- Use consistent terminology throughout (PostgreSQL 16, not "Postgres" or "pg")

### Verification Approach
- Each phase should be verifiable before moving to the next
- Test suite must be run after dependency changes
- `/check_it` is the ultimate success metric

---

## Technical Considerations

### Dependency Removal Safety
- DuckDB is listed in `additional_dependencies` for mypy, so removal must be coordinated
- After removal, the codebase should still support the DuckDB-compatibility wrapper in `storage/connection.py` (for backward compatibility)
- The wrapper should be documented as a compatibility layer only

### PostgreSQL Migration Completeness
- The migration is reported as 100% complete in PRD #0015
- This PRD assumes the migration is technically complete
- Focus is on documentation and cleanup, not re-migrating

### Test Suite Stability
- Current test status is unclear (contradictory reports)
- Baseline test pass rate must be established before dependency changes
- Any new failures after dependency removal must be investigated

---

## Success Metrics

### Primary Success Metric
- **Alignment Score**: `/check_it` re-run shows >80% overall alignment (up from 64%)

### Category-Specific Targets
- **Documentation Currency**: >80% (up from 20%)
- **Configuration Alignment**: >85% (up from 40%)
- **Test Coverage & Quality**: >70% (up from 50%)
- **Architecture Consistency**: >85% (up from 70%)

### Process Metrics
- Zero contradictions between documentation files
- Zero legacy DuckDB references in code or docs
- Test status accurately documented
- All CI quality gates passing

---

## Open Questions

1. ~~What is the true status of PRD #0016 implementation?~~ → Will be determined in FR1.1
2. ~~Are there any DuckDB code references remaining in the codebase?~~ → Will be determined in FR1.2
3. ~~What is the actual test pass rate?~~ → Will be determined in FR1.3
4. Should we create a separate PRD for the 15 failing agent tests? → Yes, per user preference (FR4.1)
5. Are there any DuckDB-specific features we need to preserve in the compatibility wrapper?
6. Should we maintain the DuckDB-compatibility wrapper long-term or deprecate it?

---

## Implementation Notes

### Recommended Order of Execution
1. **Phase 1** (Investigation) - Must complete first to inform all other phases
2. **Phase 2** (Dependency Cleanup) - Do this early to avoid confusion
3. **Phase 3** (Documentation) - Can be done in parallel with Phase 4-7 once Phase 1 is complete
4. **Phase 4** (Test Integrity) - Quick wins, do early
5. **Phase 5** (Feature Status) - Depends on Phase 1 findings
6. **Phase 6** (CI Enforcement) - Can be done anytime, but good to have before Phase 8
7. **Phase 7** (Code Quality) - Low priority, can be last
8. **Phase 8** (Verification) - Must be last to verify all fixes

### Estimated Effort Breakdown
- Phase 1 (Investigation): 4-6 hours
- Phase 2 (Dependency Cleanup): 2-3 hours
- Phase 3 (Documentation): 6-8 hours (largest effort)
- Phase 4 (Test Integrity): 2 hours
- Phase 5 (Feature Status): 2 hours
- Phase 6 (CI Enforcement): 3-4 hours
- Phase 7 (Code Quality): 1-2 hours
- Phase 8 (Verification): 1 hour

**Total**: 21-28 hours (~2.5-3.5 days of focused work)

---

## Related Documents

- [SOLUTION_ALIGNMENT.md](../docs/core/SOLUTION_ALIGNMENT.md) - Source of all issues
- [PRD #0015: PostgreSQL Migration](tasks-0015-postgresql-migration.md) - Context for migration
- [PRD #0016: Multi-Source Failover](tasks-0016-prd-complete-multi-source-failover.md) - Status to be verified
- [DEVELOPMENT.md](../docs/core/DEVELOPMENT.md) - Coding standards reference
- [ARCHITECTURE.md](../docs/core/ARCHITECTURE.md) - Architecture to be updated

---

**Version**: 1.0
**Created by**: `/plan_it` command
**Next Step**: Use `/task_it tasks/0017-prd-solution-alignment-fixes.md` to generate detailed task list
