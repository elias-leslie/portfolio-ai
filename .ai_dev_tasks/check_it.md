---
description: Analyze entire codebase for solution alignment using Gemini's large context window
---

# Rule: Solution Alignment Analysis

## Goal

To provide a periodic "second opinion" on codebase health by analyzing the entire project (documentation, code, configuration, tests) and identifying alignment issues across multiple dimensions. This prevents technical drift and ensures the implementation stays true to documented goals and standards.

## When to Use

Invoke this workflow by using `/check_it` in these scenarios:

1. **After major milestone completion** - Verify the implementation aligns with original goals
2. **Before starting new features** - Ensure foundation is solid and aligned
3. **Periodic health checks** - Run monthly/quarterly to catch drift early
4. **After team transitions** - Verify new contributors maintain alignment
5. **Pre-release validation** - Ensure production readiness and consistency

## Process

### Phase 1: Discovery

1. **Detect Project Structure**:
   - Find root documentation (README.md, CLAUDE.md, docs/, wiki/, etc.)
   - Identify core documentation directory (docs/core/, documentation/, etc.)
   - Locate configuration files (pyproject.toml, package.json, tsconfig.json, Cargo.toml, go.mod, etc.)
   - Find code directories (app/, src/, lib/, pkg/, backend/, frontend/, etc.)
   - Detect test directories (tests/, test/, __tests__/, spec/, etc.)
   - Identify planning/task directories (tasks/, .ai_dev_tasks/, docs/planning/, etc.)

2. **Determine Tech Stack**:
   - Detect languages (Python, JavaScript/TypeScript, Go, Rust, Java, etc.)
   - Identify frameworks (FastAPI, Django, React, Next.js, Vue, Express, etc.)
   - Find build tools (pip, npm, cargo, go modules, maven, gradle, etc.)
   - Note testing frameworks (pytest, jest, vitest, go test, etc.)

3. **Find Standards Documentation**:
   - Coding standards (DEVELOPMENT.md, CONTRIBUTING.md, style guides)
   - Architecture patterns (ARCHITECTURE.md, ADRs, design docs)
   - Operational procedures (OPERATIONS.md, deployment docs, runbooks)
   - API contracts (API_REFERENCE.md, OpenAPI specs, proto files)

### Phase 2: Analysis with Gemini

**Use the Gemini MCP tool** (`mcp__gemini-cli__ask-gemini`) to leverage Gemini's massive context window.

**Construction of Analysis Prompt**:

```
Analyze the following codebase for solution alignment across multiple dimensions.

PROJECT DOCUMENTATION:
@README.md
@CLAUDE.md (if exists)
@docs/ (entire directory)

CONFIGURATION:
@pyproject.toml OR @package.json OR @Cargo.toml (detect based on tech stack)
@tsconfig.json (if TypeScript)
@.pre-commit-config.yaml OR @.eslintrc (if exists)
@.github/ (if exists)

CODE STRUCTURE (sample representative files from each major module):
@backend/app/main.py OR @src/index.ts OR @main.go (entry point)
@backend/app/storage/ OR @src/database/ (data layer, if exists)
@frontend/app/layout.tsx OR @src/App.tsx (frontend root, if exists)
[Add 3-5 representative files from major modules]

TESTS (sample):
@tests/ OR @test/ OR @__tests__/ (sample 2-3 test files)

PLANNING (if exists):
@tasks/ OR @.ai_dev_tasks/

Evaluate alignment across these dimensions:

1. ARCHITECTURE CONSISTENCY (0-100%):
   - Do components follow stated architectural patterns?
   - Are layers/boundaries respected (e.g., storage abstraction, API boundaries)?
   - Is there consistent error handling?
   - Are dependencies managed as documented?

2. DOCUMENTATION CURRENCY (0-100%):
   - Are docs up-to-date with code reality?
   - Do README/setup instructions work?
   - Are API docs synchronized with actual endpoints?
   - Are architecture diagrams/descriptions accurate?

3. CODING STANDARDS ADHERENCE (0-100%):
   - Are linting rules from config enforced in code?
   - Do files respect size limits (if documented)?
   - Are naming conventions consistent?
   - Is code formatted according to standards?

4. TEST COVERAGE & QUALITY (0-100%):
   - Does test coverage meet stated targets?
   - Are critical paths tested?
   - Are test files properly organized?
   - Do tests follow naming conventions?

5. CONFIGURATION ALIGNMENT (0-100%):
   - Do multiple config files contradict each other?
   - Are environment variables documented?
   - Are dependencies up-to-date and consistent?
   - Do build tools have correct settings?

6. SECURITY BEST PRACTICES (0-100%):
   - Are secrets properly managed (not hardcoded)?
   - Are security patterns documented and followed (e.g., SQL parameterization)?
   - Are dependencies free of known vulnerabilities?
   - Are authentication/authorization patterns consistent?

7. [PROJECT-SPECIFIC CATEGORIES]:
   - Detect and evaluate additional categories based on project type
   - Examples: Database migration consistency, API versioning, component reusability

For EACH dimension, provide in structured markdown:

### [Category Name] (XX%)
**Status**: ✅ Well-aligned | ⚠️ Needs attention | 🔴 Critical

**Aligned**:
- [Bulleted list of what IS aligned and working well]

**Misalignments**:
- [Specific issues with file:line references where possible]
- [Quantify gaps: "15 files exceed size limit", "12 functions missing type hints"]

**Recommendations**:
1. [Specific, actionable fix with estimated effort]
2. [Another recommendation]

OVERALL SUMMARY:
- Overall Alignment Score: XX% (weighted average)
- Critical Issues Count: N
- High Priority Issues Count: N
- Categories Analyzed: N

PRIORITIZED ACTION ITEMS (top 10-15):
1. [CRITICAL] Specific issue with file reference
2. [HIGH] Another issue
[etc.]
```

**Execute the Gemini Analysis**:
- Use `mcp__gemini-cli__ask-gemini` with the constructed prompt
- Use `@` syntax for efficient file/directory inclusion
- Model parameter: Use `gemini-2.5-pro` (default) for comprehensive analysis
- Do NOT use sandbox mode (read-only analysis)

### Phase 3: Generate Report

1. **Create Output File**:
   - Default location: `docs/core/SOLUTION_ALIGNMENT.md`
   - If `docs/core/` doesn't exist, try: `docs/`, `documentation/`, or project root
   - If directory exists, create file there; otherwise, create in project root

2. **Report Structure**:

```markdown
# Solution Alignment Analysis

**Generated**: [ISO timestamp]
**Tool**: `/check_it` (Gemini MCP)
**Model**: gemini-2.5-pro
**Project**: [Detected project name]
**Tech Stack**: [Detected stack]

---

## Executive Summary

- **Overall Alignment**: XX% ([Status emoji])
- **Critical Issues**: N
- **High Priority Issues**: N
- **Medium Priority Issues**: N
- **Categories Analyzed**: N
- **Previous Score**: XX% (±N%) [if previous report exists]

**Status Guide**:
- 90-100%: ✅ Excellent alignment
- 75-89%: ⚠️ Good, minor improvements needed
- 50-74%: ⚠️ Moderate issues, attention required
- 0-49%: 🔴 Critical issues, immediate action needed

---

## Category Breakdown

[Insert each category analysis from Gemini, maintaining structure]

### 1. Architecture Consistency (XX%)
**Status**: [emoji]

**Aligned**:
- [Findings]

**Misalignments**:
- [Issues with file:line references]

**Recommendations**:
1. [Action item]
2. [Action item]

[Repeat for all categories]

---

## Prioritized Action Items

Priority ranking based on impact and effort:

### Critical (Address Immediately)
1. [Issue with file reference]
2. [Issue with file reference]

### High Priority (Address This Sprint)
1. [Issue]
2. [Issue]

### Medium Priority (Address Soon)
1. [Issue]
2. [Issue]

### Low Priority (Backlog)
1. [Issue]
2. [Issue]

---

## Trend Analysis

[Only if previous SOLUTION_ALIGNMENT.md exists]

| Category | Previous | Current | Change | Trend |
|----------|----------|---------|--------|-------|
| Architecture | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Documentation | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Standards | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Tests | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Configuration | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Security | XX% | XX% | ±N% | ✅/⚠️/🔴 |
| Overall | XX% | XX% | ±N% | ✅/⚠️/🔴 |

**Key Observations**:
- [What improved]
- [What regressed]
- [What stayed the same]

---

## Next Steps

1. **Review this report** - Discuss critical and high-priority issues with team
2. **Create PRD** - Use `/plan_it` to plan fixes for priority issues
3. **Generate tasks** - Use `/task_it` to break down the PRD
4. **Execute fixes** - Use `/do_it` to implement improvements
5. **Re-run check** - Use `/check_it` again after fixes to verify improvement

---

## Methodology

**Analysis Date**: [ISO timestamp]
**Tool**: Gemini MCP (`mcp__gemini-cli__ask-gemini`)
**Model**: gemini-2.5-pro
**Context Loaded**:
- Documentation: [list of @ includes]
- Configuration: [list of @ includes]
- Code Samples: [list of @ includes]
- Tests: [list of @ includes]

**Scoring Method**:
- Each category scored 0-100% based on alignment with documented standards
- Overall score is weighted average (critical categories weighted higher)
- Trend analysis compares to previous report (if exists)

---

**Report Version**: 1.0
**Generated by**: /check_it command
```

### Phase 4: Display Summary

After generating the report, display a concise summary to the user:

```
✅ Solution Alignment Analysis Complete

📊 Overall Score: XX% ([status emoji])

📋 Issues Found:
   🔴 Critical: N
   ⚠️ High: N
   ⚠️ Medium: N

📄 Report saved to: docs/core/SOLUTION_ALIGNMENT.md

🔝 Top 3 Priorities:
1. [Critical issue summary]
2. [High priority issue summary]
3. [High priority issue summary]

💡 Next Steps:
• Review full report: docs/core/SOLUTION_ALIGNMENT.md
• Create fix PRD: /plan_it Fix alignment issues from check_it report
• Generate tasks: /task_it [PRD filename]
• Execute fixes: /do_it [task list filename]
• Re-check: /check_it (after fixes)
```

## Quality Standards

### Analysis Should Be:
- **Comprehensive**: Cover all major aspects of the codebase
- **Specific**: Include file:line references for issues
- **Actionable**: Recommendations should be concrete and implementable
- **Quantified**: Use percentages and counts, not vague terms
- **Comparative**: Track trends over time (if previous report exists)

### Avoid:
- ❌ Vague issues: "Some files have problems" → "12 files exceed 500-line limit: app/main.py:1-723, ..."
- ❌ Non-actionable: "Improve tests" → "Add integration tests for API endpoints in test_api_*.py (13 endpoints missing coverage)"
- ❌ Speculation: "Might have issues" → State facts or mark as "Not evaluated"
- ❌ Judgment: "Bad code" → "Violates standard X (defined in DEVELOPMENT.md:45)"

## Target Audience

Assume the primary readers are:
1. **Engineering leads** - Need high-level scores and trends
2. **AI coding assistants** - Need specific file:line refs for `/plan_it` and `/task_it`
3. **Developers** - Need actionable recommendations

## Anti-Patterns to Avoid

- ❌ Running analysis without discovering project structure first
- ❌ Hardcoding file paths (must be generic and auto-discover)
- ❌ Analyzing every single file (use representative samples for large projects)
- ❌ Ignoring existing standards documentation
- ❌ Creating alignment categories that don't match the project type
- ❌ Failing to provide file:line references for issues
- ❌ Not tracking trends over time

## Success Criteria

After completion, verify:
- ✅ Gemini MCP tool was used for analysis (not manual code inspection)
- ✅ All major project areas were included in analysis (docs, code, config, tests)
- ✅ Each category has a percentage score
- ✅ Misalignments include specific file:line references
- ✅ Recommendations are actionable and prioritized
- ✅ Report saved to appropriate location
- ✅ Summary displayed to user with next steps
- ✅ If previous report exists, trend analysis included

---

## Usage

Simply invoke the command (no arguments needed):
```
/check_it
```

The AI will:
1. Auto-discover your project structure
2. Construct comprehensive analysis prompt
3. Execute Gemini MCP analysis with large context
4. Generate SOLUTION_ALIGNMENT.md report
5. Display summary with top priorities
6. Suggest next steps for fixing issues

## Example Output

```
🔍 Discovering project structure...
   ✓ Found docs in: docs/core/
   ✓ Detected tech stack: Python 3.11 + FastAPI + Next.js 14
   ✓ Found config: pyproject.toml, package.json, tsconfig.json
   ✓ Found tests: 25 test files in backend/tests/

📊 Analyzing with Gemini (this may take 30-60 seconds)...
   ✓ Context loaded: 15 docs, 8 configs, 12 code samples
   ✓ Analysis complete

📝 Generating report...
   ✓ Report saved to: docs/core/SOLUTION_ALIGNMENT.md

✅ Solution Alignment Analysis Complete

📊 Overall Score: 82% (⚠️ Good, minor improvements needed)

📋 Issues Found:
   🔴 Critical: 2
   ⚠️ High: 5
   ⚠️ Medium: 8

🔝 Top 3 Priorities:
1. [CRITICAL] 3 files have SQL injection risk (app/analytics.py:45, app/reports.py:112, app/queries.py:88)
2. [HIGH] Documentation 2 months out of date (docs/core/API_REFERENCE.md last updated 2025-08-15)
3. [HIGH] 15 functions missing type hints in app/agents/

💡 Next Steps:
• Review full report: docs/core/SOLUTION_ALIGNMENT.md
• Create fix PRD: /plan_it Fix critical alignment issues from check_it report
• Generate tasks: /task_it [PRD filename]
• Execute fixes: /do_it [task list filename]
• Re-check: /check_it (after fixes to track improvement)
```

---

## Integration with Command Suite

**Workflow Position**:

```
/next_it → /plan_it → /task_it → /do_it → /doc_it
                                              ↓
                                         /check_it (periodic validation)
                                              ↓
                            (If issues found) /plan_it → ... (remediation cycle)
```

**Use Cases**:
1. **After `/doc_it`**: Verify documentation updates improved alignment
2. **Before `/next_it`**: Ensure foundation is solid before new features
3. **Independent periodic check**: Monthly/quarterly health validation
4. **Pre-release gate**: Ensure production-ready alignment

---

## Notes

- **Gemini Context Window**: This command leverages Gemini's 2M+ token context window, allowing analysis of entire codebases
- **Cost Consideration**: Gemini API usage incurs costs; use judiciously (e.g., not on every commit)
- **Complementary to `/doc_it`**: `/doc_it` updates docs; `/check_it` validates entire solution alignment
- **Not a replacement for tests**: This checks architectural/documentation alignment, not functional correctness
