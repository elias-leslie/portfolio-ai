# TASK: Design Comprehensive `/audit_it` Command

**Status**: Ready for exploration
**Priority**: P2
**Complexity**: Large
**Created**: 2025-12-16

---

## Objective

Design and implement a unified `/audit_it` command that combines and orchestrates:
- Existing commands: `/data_check`, `/silo_check`, `/clean_it`
- Existing quality scripts: `quality-report-full.sh` (16 scripts)
- Existing agents: `code-reviewer`, `security-auditor`, `dependency-manager`, `refactoring-specialist`
- **NEW tools to add**: `jscpd` (duplication), `radon` (complexity), `pip-audit`, enhanced metrics

Goal: Single command that provides a complete codebase health assessment with actionable output.

---

## Phase 1: Deep Exploration (MANDATORY)

Launch **5 parallel exploration agents** in "very thorough" mode to understand the full landscape:

### Agent 1: Existing Commands Analysis
```
Explore and document:
- .claude/commands/data_check.md - What it does, how it works, outputs
- .claude/commands/silo_check.md - What it does, how it works, outputs
- .claude/commands/clean_it.md - What it does, how it works, outputs
- .claude/commands/review_files.md - Potential overlap/integration
- .claude/commands/verify_it.md - Potential overlap/integration

Questions to answer:
1. What's the overlap between these commands?
2. What's unique to each?
3. How do they create/use beads?
4. What agents do they spawn internally?
5. What's the typical runtime for each?
6. What are the dependencies between them?
```

### Agent 2: Existing Agents Analysis
```
Explore and document:
- .claude/agents/code-reviewer.md - Capabilities, when to use
- .claude/agents/security-auditor.md - Capabilities, when to use
- .claude/agents/dependency-manager.md - Capabilities, when to use
- .claude/agents/refactoring-specialist.md - Capabilities, when to use
- .claude/agents/pre-implementation-check.md - Potential integration

Questions to answer:
1. Which agents are already used by existing commands?
2. Which agents are underutilized but valuable?
3. What's the agent invocation pattern (Task tool + subagent_type)?
4. How do agents report findings?
5. Can agents be run in parallel?
```

### Agent 3: Code Quality Scripts Analysis
```
Explore and document:
- .claude/skills/code-quality/SKILL.md - Full capabilities
- All 16 scripts in .claude/skills/code-quality/scripts/
- quality-report.sh vs quality-report-full.sh differences
- Exit codes and CI/CD integration patterns

Questions to answer:
1. What's the total coverage of these scripts?
2. What gaps exist (duplication detection? complexity metrics?)
3. How long does quality-report-full.sh take?
4. What's the output format of each script?
5. How are thresholds configured?
```

### Agent 4: External Tools Research
```
Research and document integration requirements for:

1. jscpd (JavaScript Copy/Paste Detector)
   - Installation: npm install -g jscpd
   - Usage: jscpd backend/ frontend/ --min-lines 10 --reporters json
   - Output format, thresholds, configuration
   - Can detect duplication across Python AND TypeScript

2. radon (Python complexity metrics)
   - Installation: pip install radon
   - Usage: radon cc backend/app -j (cyclomatic complexity)
   - Usage: radon mi backend/app -j (maintainability index)
   - Output format, scoring, thresholds

3. pip-audit (Python dependency vulnerabilities)
   - Installation: pip install pip-audit
   - Usage: pip-audit --format json
   - Integration with existing check-security.sh

4. npm audit (already available)
   - Usage: npm audit --json
   - Integration with frontend checks

5. Consider: vulture (dead code), bandit (security), prospector (meta-linter)
```

### Agent 5: Bead/Task Integration Patterns
```
Explore and document:
- How existing commands create beads (bd create patterns)
- Bead priority mapping (CRITICAL → P1, HIGH → P2, etc.)
- Label conventions (complexity, domains, etc.)
- How /next_it picks up created beads
- QA issue creation patterns (from /clean_it)

Questions to answer:
1. What's the ideal bead creation threshold? (Don't create for every finding)
2. Should audit findings auto-create beads or just report?
3. How to avoid duplicate beads on repeated runs?
4. How to track audit history/trends over time?
```

---

## Phase 2: Gap Analysis

After exploration, identify:

### What's Missing Today
- [ ] Code duplication detection (jscpd needed)
- [ ] Cyclomatic complexity metrics (radon needed)
- [ ] Maintainability index tracking (radon needed)
- [ ] Dependency vulnerability scanning (pip-audit, npm audit)
- [ ] Unified health score calculation
- [ ] Historical trend tracking
- [ ] Single-command orchestration

### What's Redundant/Overlapping
- [ ] Multiple commands doing similar DB analysis?
- [ ] Overlapping security checks?
- [ ] Duplicate DRY violation detection?

### Integration Opportunities
- [ ] Can quality scripts output feed into agents?
- [ ] Can agent findings feed into bead creation?
- [ ] Can cleanup run automatically after analysis?

---

## Phase 3: Architecture Design

Design the `/audit_it` command structure:

### Proposed Phases

```
Phase 0: Pre-Flight
├── Git safety checkpoint
├── Service health check
└── Tool availability check (jscpd, radon, etc.)

Phase 1: Metrics Collection (Parallel - Fast)
├── jscpd → duplication %
├── radon cc → complexity scores
├── radon mi → maintainability index
├── quality-report-full.sh → existing checks
└── pip-audit + npm audit → vulnerabilities

Phase 2: Static Analysis (Parallel - Fast)
├── ruff check --fix → Python lint
├── eslint --fix → TypeScript lint
├── mypy → type errors
└── tsc --noEmit → TypeScript errors

Phase 3: Deep Analysis (Agents - Slower)
├── Agent: Data architecture (from /data_check)
├── Agent: Architecture coherence (from /silo_check)
├── Agent: Security review (security-auditor)
└── Agent: Dependency analysis (dependency-manager)

Phase 4: Cleanup (Interactive)
├── Dead code removal (from /clean_it)
├── Orphan file cleanup
└── Auto-fixable issues

Phase 5: Reporting
├── Health score calculation
├── Prioritized findings
├── Bead creation (HIGH+ only)
└── Next steps recommendations
```

### Arguments to Support

```
--fix           Auto-apply safe fixes without prompting
--dry-run       Report only, no changes
--quick         Skip deep agent analysis (phases 1-2 only)
--deep          Extra thorough (add naming convention agent)
--focus <area>  Run specific phase: metrics|lint|data|arch|security|cleanup
--no-beads      Don't create beads, report only
--json          Machine-readable output
--ci            CI mode (exit codes, no interactive)
```

### Health Score Calculation

```python
# Proposed scoring (100 points total)
health_score = (
    duplication_score(max=15) +      # 0-15 based on duplication %
    complexity_score(max=15) +        # 0-15 based on avg CC
    maintainability_score(max=10) +   # 0-10 based on MI
    lint_score(max=10) +              # 0-10 based on lint issues
    type_score(max=10) +              # 0-10 based on type coverage
    security_score(max=15) +          # 0-15 based on vulnerabilities
    architecture_score(max=15) +      # 0-15 based on silo/DRY findings
    cleanliness_score(max=10)         # 0-10 based on dead code
)

# Grades
90-100: Excellent
80-89:  Good
70-79:  Acceptable
60-69:  Needs Attention
<60:    Critical
```

---

## Phase 4: Implementation Plan

### Step 1: Install New Tools
```bash
# Python tools
pip install radon pip-audit

# Node tools
npm install -g jscpd

# Verify installation
radon --version
jscpd --version
pip-audit --version
```

### Step 2: Create Integration Scripts
```bash
# New scripts to add to .claude/skills/code-quality/scripts/
check-duplication.sh    # Wrapper for jscpd
check-complexity.sh     # Wrapper for radon cc
check-maintainability.sh # Wrapper for radon mi
check-vulnerabilities.sh # Wrapper for pip-audit + npm audit
```

### Step 3: Create Command File
```
.claude/commands/audit_it.md
├── Argument parsing
├── Phase orchestration
├── Agent spawning
├── Result aggregation
├── Health score calculation
├── Bead creation logic
└── Report generation
```

### Step 4: Update Existing Commands
- `/data_check` - Add flag to run as sub-phase of /audit_it
- `/silo_check` - Add flag to run as sub-phase of /audit_it
- `/clean_it` - Add flag to run as sub-phase of /audit_it

### Step 5: Documentation
- Update CLAUDE.md with /audit_it reference
- Create docs/commands/audit_it.md with full documentation
- Add to command table in CLAUDE.md

---

## Phase 5: Testing & Validation

### Test Scenarios
1. `audit_it` - Full run, verify all phases execute
2. `audit_it --dry-run` - Verify no changes made
3. `audit_it --quick` - Verify only fast phases run
4. `audit_it --fix` - Verify auto-fixes applied correctly
5. `audit_it --focus metrics` - Verify single phase works
6. `audit_it --ci` - Verify CI-appropriate output and exit codes

### Acceptance Criteria
- [ ] All 6 phases complete without error
- [ ] Health score calculated and displayed
- [ ] Beads created only for HIGH+ severity
- [ ] No duplicate beads on repeated runs
- [ ] Runtime < 10 minutes for full audit
- [ ] Runtime < 2 minutes for --quick mode
- [ ] Clear, actionable output

---

## Questions to Resolve During Exploration

1. **Bead Deduplication**: How to prevent creating duplicate beads if audit is run repeatedly?
   - Option A: Check existing beads before creating
   - Option B: Use deterministic bead IDs based on finding hash
   - Option C: Mark beads with audit date, close old ones

2. **Agent Parallelization**: Can data_check and silo_check agents run simultaneously?
   - Need to verify no resource conflicts
   - May need to stagger if both hit same files

3. **Threshold Configuration**: Where should thresholds live?
   - Option A: Hardcoded in command file
   - Option B: .claude/config/audit-thresholds.yaml
   - Option C: Environment variables

4. **Historical Tracking**: Should audit results be persisted?
   - Option A: Save to docs/audits/YYYY-MM-DD.md
   - Option B: Save to database table
   - Option C: Just display, don't persist

5. **Cleanup Automation**: Should cleanup be automatic or interactive?
   - Recommendation: Interactive by default, --fix for auto

---

## Deliverables

1. **New Scripts** (in .claude/skills/code-quality/scripts/):
   - [ ] check-duplication.sh
   - [ ] check-complexity.sh
   - [ ] check-maintainability.sh
   - [ ] check-vulnerabilities.sh

2. **New Command**:
   - [ ] .claude/commands/audit_it.md

3. **Documentation**:
   - [ ] Updated CLAUDE.md
   - [ ] docs/commands/audit_it.md (detailed guide)

4. **Dependencies**:
   - [ ] radon added to backend/pyproject.toml [dev]
   - [ ] jscpd documented in package.json or README

---

## Execution Instructions

When working on this task:

1. **Start with Phase 1 exploration** - Launch all 5 agents in parallel
2. **Wait for all agents to complete** before proceeding
3. **Synthesize findings** into gap analysis
4. **Present design to user** for approval before implementation
5. **Implement incrementally** - scripts first, then command, then docs
6. **Test each phase** before moving to next
7. **Create bead for any blockers** discovered during implementation

---

## Notes

- This is a LARGE task, expect 4-6 hours of work
- Can be split into sub-tasks if needed
- User preference: Single comprehensive command over multiple smaller ones
- Existing commands should remain functional (backward compatibility)
- New command should be the "recommended" approach going forward

---

**Version**: 1.0.0
**Author**: Claude
**Last Updated**: 2025-12-16
