# TASK: Implement Unified `/audit_it` Command

**Status**: In Progress
**Priority**: P2
**Complexity**: Large
**Created**: 2025-12-16
**Updated**: 2025-12-16

---

## Objective

Create a unified `/audit_it` command that **consolidates and replaces** three existing commands:
- `/data_check` - Data architecture analysis
- `/silo_check` - Architecture coherence audit
- `/clean_it` - Dead code cleanup

The new command provides comprehensive codebase health assessment with actionable output, health scoring, and historical tracking.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration | New unified implementation | Cleaner architecture, removes redundancy |
| Bead creation | HIGH+ severity only | Reduces noise, focuses on actionable items |
| History | docs/audits/YYYY-MM-DD.md | Git-tracked, diff-able, simple |

---

## Commands Being Replaced

### /data_check (Absorbed)
- Data source analysis (YFinance, Polygon, etc.)
- Database schema analysis (tables, FKs, indexes)
- Data ingestion patterns (Celery tasks, schedules)
- Redundancy and normalization issues
- **Agents**: 3 parallel (Sources, Schema, Ingestion)

### /silo_check (Absorbed)
- Duplicate code detection
- Service/module boundary analysis
- Pattern consistency analysis
- Naming convention audit (--deep mode)
- Bead creation for findings
- **Agents**: 4-5 parallel

### /clean_it (Absorbed)
- Dead code detection (ruff F401/F841)
- Orphan file detection
- DRY violation detection
- Cleanup with confidence levels (HIGH/MEDIUM/LOW)
- Git checkpoint before mutations
- **Agents**: None (script-based)

---

## New Capabilities

| Tool | Purpose | Status |
|------|---------|--------|
| jscpd | Cross-language code duplication | Needs sudo install |
| radon | Cyclomatic complexity + maintainability index | Installed |
| pip-audit | Python dependency vulnerabilities | Installed |
| npm audit | Frontend dependency vulnerabilities | Available (needs integration) |

---

## Command Structure

### Arguments

```
/audit_it [options]

Options:
  --fix           Auto-apply safe fixes without prompting
  --dry-run       Report only, no changes
  --quick         Fast mode: metrics + lint only (skip deep analysis)
  --deep          Extra thorough: add naming conventions agent
  --focus <area>  Run specific phase: metrics|lint|data|arch|security|cleanup
  --no-beads      Don't create beads, report only
  --json          Machine-readable output
  --ci            CI mode: exit codes, non-interactive
```

### Phases

```
Phase 0: Pre-Flight (Always runs)
├── Git safety checkpoint (uncommitted changes warning)
├── Service health check (backend, celery running)
└── Tool availability check (jscpd, radon, pip-audit)

Phase 1: Metrics Collection (~30 seconds, parallel)
├── jscpd → duplication % (Python + TypeScript)
├── radon cc → cyclomatic complexity scores
├── radon mi → maintainability index
├── quality-report-full.sh → existing 16 checks
└── pip-audit + npm audit → vulnerability counts

Phase 2: Static Analysis (~20 seconds, parallel)
├── ruff check --fix → Python lint issues
├── mypy → Python type errors
├── tsc --noEmit → TypeScript errors
└── eslint → TypeScript lint issues

Phase 3: Deep Analysis (agents, ~3-5 minutes)
├── Agent: Data architecture (redundancy, normalization, schema)
├── Agent: Code architecture (DRY, boundaries, patterns)
├── Agent: Security review (if vulnerabilities found)
└── Agent: Naming conventions (--deep only)

Phase 4: Cleanup (~2-3 minutes, interactive unless --fix)
├── Dead code removal (ruff F401/F841)
├── Orphan file cleanup (with confidence levels)
├── DRY violation flagging (creates beads, doesn't auto-fix)
└── Git checkpoint before any mutations

Phase 5: Reporting
├── Health score calculation (0-100)
├── Prioritized findings summary
├── Bead creation (HIGH+ severity only)
├── History save to docs/audits/YYYY-MM-DD.md
└── Next steps recommendations
```

---

## Health Score Formula

```python
# Total: 100 points
health_score = (
    duplication_score(max=15) +      # 15 points, <2% dup = 15, >10% = 0
    complexity_score(max=15) +        # 15 points, avg CC <5 = 15, >15 = 0
    maintainability_score(max=10) +   # 10 points, MI >70 = 10, <40 = 0
    lint_score(max=10) +              # 10 points, 0 issues = 10, >50 = 0
    type_score(max=10) +              # 10 points, 0 errors = 10
    security_score(max=15) +          # 15 points, 0 vulns = 15
    architecture_score(max=15) +      # 15 points, no silos = 15
    cleanliness_score(max=10)         # 10 points, no dead code = 10
)

# Grades
90-100: Excellent (A)
80-89:  Good (B)
70-79:  Acceptable (C)
60-69:  Needs Attention (D)
<60:    Critical (F)
```

---

## Implementation Checklist

### Phase 1: Tool Installation
- [x] Install radon in backend venv
- [x] Install pip-audit in backend venv
- [x] Add to pyproject.toml [dev] deps
- [ ] Install jscpd globally (needs sudo)

### Phase 2: Wrapper Scripts
- [ ] Create check-duplication.sh (jscpd wrapper)
- [ ] Create check-complexity.sh (radon wrapper)
- [ ] Create check-vulnerabilities.sh (pip-audit + npm audit)

### Phase 3: Command File
- [ ] Create .claude/commands/audit_it.md
- [ ] Implement all 6 phases
- [ ] Add argument parsing
- [ ] Add health score calculation
- [ ] Add history save logic

### Phase 4: Cleanup
- [ ] Delete .claude/commands/data_check.md
- [ ] Delete .claude/commands/silo_check.md
- [ ] Delete .claude/commands/clean_it.md
- [ ] Update CLAUDE.md command table
- [ ] Update AGENTS.md references
- [ ] Update architecture-coherence.md references
- [ ] Update review_files.md references
- [ ] Update docs/core/COMMAND_REFERENCE.md

### Phase 5: Testing
- [ ] Test: audit_it (full run)
- [ ] Test: audit_it --dry-run
- [ ] Test: audit_it --quick
- [ ] Test: audit_it --fix
- [ ] Test: audit_it --focus metrics

---

## Files Summary

### To Create
| File | Purpose | Lines |
|------|---------|-------|
| `.claude/commands/audit_it.md` | Main unified command | ~500 |
| `.claude/skills/code-quality/scripts/check-duplication.sh` | jscpd wrapper | ~50 |
| `.claude/skills/code-quality/scripts/check-complexity.sh` | radon wrapper | ~60 |
| `.claude/skills/code-quality/scripts/check-vulnerabilities.sh` | pip-audit + npm audit | ~80 |
| `docs/audits/.gitkeep` | History directory | 0 |

### To Delete
- `.claude/commands/data_check.md`
- `.claude/commands/silo_check.md`
- `.claude/commands/clean_it.md`

### To Update
- `CLAUDE.md` - Command table
- `AGENTS.md` - /silo_check reference
- `.claude/rules/architecture-coherence.md` - /silo_check reference
- `.claude/commands/review_files.md` - /clean_it reference
- `docs/core/COMMAND_REFERENCE.md` - /data_check docs
- `backend/pyproject.toml` - Already done

---

## Bead Deduplication Strategy

To avoid duplicate beads on repeated runs:

1. **Before creating bead**, check existing open beads:
   ```bash
   bd list --status open --json | jq -r '.[] | "\(.id) \(.title)"'
   ```

2. **Match by location hash**: Generate deterministic ID from finding location
   ```
   hash = sha256(f"{issue_type}:{file_path}:{line_start}")[:8]
   title = f"Audit: {description} [{hash}]"
   ```

3. **Update if exists**: If bead with same hash exists, update notes instead of creating new

4. **Age out stale beads**: Flag beads not found in latest audit as "may be resolved"

---

## History File Format

`docs/audits/YYYY-MM-DD.md`:

```markdown
# Codebase Audit - YYYY-MM-DD HH:MM

## Health Score: 78/100 (C - Acceptable)

### Metrics Summary
| Metric | Value | Score |
|--------|-------|-------|
| Duplication | 3.2% | 12/15 |
| Avg Complexity | 7.3 | 11/15 |
| Maintainability | 68.5 | 7/10 |
| Lint Issues | 12 | 8/10 |
| Type Errors | 0 | 10/10 |
| Vulnerabilities | 2 (1 high) | 10/15 |
| Architecture | 3 issues | 10/15 |
| Dead Code | 5 files | 8/10 |

### Critical/High Findings
1. **[CRITICAL]** SQL injection risk in `backend/app/api/search.py:145`
2. **[HIGH]** Duplicate function `format_date` in 3 locations
3. **[HIGH]** High vulnerability in `requests` package

### Beads Created
- portfolio-ai-XXX: Audit: SQL injection risk [a1b2c3d4]
- portfolio-ai-YYY: Audit: Duplicate format_date [e5f6g7h8]

### Comparison to Previous
- Health score: 78 (was 75, +3)
- Duplication: 3.2% (was 4.1%, -0.9%)
- Vulnerabilities: 2 (was 3, -1)
```

---

## Notes

- Remaining commands after consolidation: `/next_it`, `/verify_it`, `/test_it`, `/back_it`, `/update_it`, `/review_files`
- `/audit_it` becomes the recommended first step for codebase health checks
- Historical archives in tasks/archive/ remain as-is (historical record)

---

**Version**: 2.0.0
**Author**: Claude
**Last Updated**: 2025-12-16
