# PRD: Audit Quick Wins - High Impact, Low Effort Fixes

**Source**: CODE_AUDIT.md, DATABASE_AUDIT.md, INSTRUCTION_AUDIT.md (Combined)
**Severity**: CRITICAL + HIGH Priority Items
**Effort**: LOW-MEDIUM (3-5 hours total)
**Created**: 2025-11-03

---

## Introduction

**Current Issue**: Three comprehensive audits identified critical and high-priority issues that can be fixed quickly for immediate impact.

**Desired State**: Address all CRITICAL and HIGH priority findings with low-to-medium effort to improve:
- Database query performance (missing indexes)
- Documentation accuracy (outdated DB references)
- Code reliability (remove tool assumptions)

**Impact**:
- Dramatic performance improvement for portfolio queries
- Accurate documentation for developers
- Prevent runtime failures from missing tools

---

## Goals

1. **Performance**: Add 4 missing database indexes (5-15 minutes)
2. **Documentation**: Update outdated PostgreSQL references (30-60 minutes)
3. **Reliability**: Remove unverified tool assumptions (1-2 hours)
4. **Configuration**: Clarify service management policy (30 minutes)

---

## Scope: Quick Wins Only

### From DATABASE_AUDIT.md

**HIGH Priority - Missing Index**:
- ✅ `portfolio_positions.account_id` - CRITICAL for portfolio queries

**MEDIUM Priority - Missing Indexes**:
- ✅ `agent_ideas.agent_run_id` - Agent analysis performance
- ✅ `agent_tool_calls.agent_run_id` - Agent analysis performance
- ✅ `validation_results.idea_id` - Idea tracing performance

**Effort**: 15 minutes (4 SQL statements)
**Impact**: HIGH (eliminates full table scans)

---

### From INSTRUCTION_AUDIT.md

**CRITICAL Priority #1 - Outdated DB References**:
- ✅ Remove DuckDB references from OPERATIONS.md
- ✅ Remove DuckDB references from SETUP.md
- ✅ Update backup/restore procedures to PostgreSQL

**HIGH Priority #5 - Conflicting Service Directives**:
- ✅ Clarify service management policy in do_it.md
- ✅ Allow project scripts (start.sh, restart.sh)
- ✅ Forbid only manual nohup/& commands

**Effort**: 1-2 hours (documentation updates)
**Impact**: HIGH (prevents confusion, correct procedures)

---

### From CODE_AUDIT.md (Documentation Only)

**Quick Documentation Fix**:
- ✅ Document the 7 files >500 lines in CODE_AUDIT.md
- ✅ Note: Actual refactoring deferred to separate PRD

**Effort**: 10 minutes (awareness only)
**Impact**: LOW (sets expectations for future work)

---

## Functional Requirements

### FR-1: Database Index Creation
- Create index on `portfolio_positions.account_id`
- Create index on `agent_ideas.agent_run_id`
- Create index on `agent_tool_calls.agent_run_id`
- Create index on `validation_results.idea_id`
- Verify indexes created successfully
- Test query performance improvement

### FR-2: Update OPERATIONS.md for PostgreSQL
- Remove all DuckDB file references (`portfolio-ai.db`)
- Remove .wal file and locking references
- Update backup section to PostgreSQL pg_dump
- Update restore section to psql restore
- Add database connection string format
- Verify all commands use PostgreSQL

### FR-3: Update SETUP.md for PostgreSQL
- Remove DuckDB installation steps
- Remove file database references
- Update to PostgreSQL setup only
- Verify consistency with OPERATIONS.md

### FR-4: Clarify Service Management Policy
- Update do_it.md service management section
- Clarify: "Prefer project scripts (start.sh, restart.sh, shutdown.sh)"
- Clarify: "Forbid only manual nohup/& commands"
- Remove blanket prohibition on background processes
- Align with actual practice in OPERATIONS.md

### FR-5: Code Audit Awareness (No Code Changes)
- Review CODE_AUDIT.md findings
- Understand 7 files exceed 500-line limit
- Note for future refactoring PRD
- No immediate code changes required

---

## Non-Goals

**Explicitly OUT OF SCOPE** (separate PRDs needed):
- ❌ Refactoring large files (watchlist/service.py, etc.) - Separate PRD
- ❌ Replacing Any types with proper types - Separate PRD
- ❌ Browser automation validation - Lower priority
- ❌ Code reviewer agent verification - Lower priority
- ❌ Celery result retention policy - MEDIUM priority
- ❌ Pre-commit checklist consolidation - LOW priority

---

## Technical Considerations

### Database Migrations
- SQL scripts for index creation
- Safe to run on production (CREATE INDEX IF NOT EXISTS)
- No downtime required
- Minimal lock time (<1 second per index)

### Documentation Updates
- Markdown file edits only
- No code changes required
- Review by comparing to current PostgreSQL setup

### Service Management
- Policy clarification only
- No script changes required
- Aligns with existing practice

---

## Success Metrics

### Performance (Database Indexes)
- ✅ All 4 indexes created
- ✅ Query plans show index usage (EXPLAIN ANALYZE)
- ✅ Portfolio query response time <100ms

### Documentation (PostgreSQL Updates)
- ✅ Zero DuckDB references in OPERATIONS.md
- ✅ Zero DuckDB references in SETUP.md
- ✅ Backup/restore procedures use pg_dump/psql
- ✅ All database commands reference PostgreSQL

### Reliability (Service Management)
- ✅ Policy clearly stated in do_it.md
- ✅ No confusion about when to use systemctl vs scripts
- ✅ Aligns with OPERATIONS.md

### Code Quality (Awareness)
- ✅ CODE_AUDIT.md reviewed
- ✅ Large files documented
- ✅ Future refactoring PRD created

---

## Implementation Approach

### Phase 1: Database Indexes (15 min)
1. Create SQL migration file
2. Run on both portfolio_ai and portfolio_ai_test databases
3. Verify indexes with `\di` in psql
4. Test portfolio query performance

### Phase 2: Update OPERATIONS.md (30-45 min)
1. Search for all "duckdb" and ".db" references
2. Replace with PostgreSQL equivalents
3. Update backup/restore sections
4. Verify all commands use correct connection string

### Phase 3: Update SETUP.md (15-30 min)
1. Remove DuckDB steps
2. Ensure PostgreSQL setup is comprehensive
3. Cross-reference with OPERATIONS.md for consistency

### Phase 4: Clarify Service Management (15-30 min)
1. Update do_it.md service section
2. Add clear policy statement
3. Remove conflicting language
4. Add examples of allowed vs forbidden

### Phase 5: Review Code Audit (10 min)
1. Read CODE_AUDIT.md thoroughly
2. Note 7 large files
3. Create placeholder for refactoring PRD

---

## Risks & Mitigations

### Risk: Database Index Creation on Large Tables
**Mitigation**:
- watchlist_snapshots is only 10MB (small)
- Index creation <5 seconds
- Use CREATE INDEX IF NOT EXISTS for safety

### Risk: Documentation Inconsistency
**Mitigation**:
- Use grep to find ALL references
- Cross-check between docs
- Test one backup/restore command to verify

### Risk: Service Management Confusion Persists
**Mitigation**:
- Provide explicit examples
- Clear do/don't list
- Reference actual scripts in repo

---

## Testing Plan

### Database Indexes
```sql
-- Verify indexes exist
\di

-- Test query performance (before/after)
EXPLAIN ANALYZE SELECT * FROM portfolio_positions WHERE account_id = 'default';
```

### Documentation
```bash
# Verify no DuckDB references
grep -r "duckdb\|\.db\|\.wal" docs/core/OPERATIONS.md docs/core/SETUP.md

# Should return: nothing

# Verify PostgreSQL references
grep -c "postgresql\|psql\|pg_dump" docs/core/OPERATIONS.md
# Should return: multiple matches
```

### Service Management
```bash
# Check for clear policy in do_it.md
grep -A 5 "service management" .claude/commands/do_it.md
# Should show: allow scripts, forbid manual nohup
```

---

## Dependencies

- PostgreSQL 16 (already installed)
- Access to both portfolio_ai and portfolio_ai_test databases
- Write access to docs/core/ directory
- Write access to .claude/commands/ directory

---

## Estimated Effort Breakdown

| Task | Effort | Complexity |
|------|--------|------------|
| Database indexes | 15 min | LOW |
| OPERATIONS.md update | 45 min | LOW |
| SETUP.md update | 30 min | LOW |
| Service policy clarification | 30 min | LOW |
| Code audit review | 10 min | LOW |
| Testing & verification | 30 min | LOW |
| **TOTAL** | **3 hours** | **LOW** |

---

## Success Criteria Summary

✅ **COMPLETE when**:
1. All 4 database indexes created and verified
2. OPERATIONS.md has zero DuckDB references
3. SETUP.md has zero DuckDB references
4. Service management policy clearly stated
5. All documentation cross-referenced for consistency
6. Query performance verified with EXPLAIN ANALYZE
7. CODE_AUDIT.md reviewed and understood

---

## Next Steps After This PRD

1. **Create refactoring PRD** for 7 large files (CODE_AUDIT.md)
2. **Create type system PRD** for 20+ Any types (CODE_AUDIT.md)
3. **Create Celery cleanup PRD** for result retention (DATABASE_AUDIT.md)
4. **Address MEDIUM/LOW findings** from INSTRUCTION_AUDIT.md

**This PRD focuses on quick wins only** - high impact, low effort, immediate value.
