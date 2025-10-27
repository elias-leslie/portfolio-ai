---
description: Find the next thing to work on and initiate planning
---

# Rule: Finding the Next Thing to Work On

## Goal

To guide an AI assistant in discovering and presenting **15 prioritized opportunities** across 3 categories:
1. **Top 5 Known Issues** - Existing work that needs to be done (bugs, debt, incomplete work)
2. **Top 5 Quick Win Ideas** - New features/improvements (high value, low effort, free/open source)
3. **Top 5 Strategic Ideas** - Harder implementations with extreme value (free/open source)

Then enable user selection to automatically initiate `/plan_it` for the chosen item.

## Discovery Process

### Phase 1: Known Issues Analysis

**Scan Existing Plans & Tasks**:
- PRDs without corresponding task lists, incomplete task lists (unchecked boxes)
- Status/progress documents for "next", "planned", "TODO", "FIXME" sections
- Recently completed work to identify natural next steps

**Code Quality Scan**:
- Files exceeding project line limits, missing test coverage
- DRY violations (similar code patterns across files)
- Inline TODO/FIXME/HACK comments, missing type hints/docs

**Documentation Review**:
- Stale documentation (git log timestamps > 7 days old)
- README/main docs vs. actual codebase state
- Documented features not yet implemented, missing API docs

**Git History & Security**:
- Last 5-10 commits for context, commit patterns (fix → tests, refactor → docs)
- Security issues (SQL injection, hardcoded secrets), performance bottlenecks

### Phase 2: Quick Win Brainstorming

Generate 5 ideas that are:
- **High value** for users or developers
- **Low effort** (straightforward implementation)
- **Free/open source** (no paid APIs or commercial tools)
- **Actionable** (clear implementation path)

**Categories**: Automation (CI/CD, scripts), Developer Experience (debugging, setup), Integrations (free/OSS services), Utilities (export/import, validation), Monitoring (logging, health checks), Documentation (API docs, guides), Testing (fixtures, coverage), Configuration (env management)

**Techniques**: Analyze features for gaps, study similar OSS projects, automate manual processes, improve debugging/troubleshooting, add tooling for repetitive tasks

### Phase 3: Strategic Brainstorming

Generate 5 ideas that are:
- **Extreme value** (game-changing for the project)
- **High complexity** (significant implementation effort)
- **Free/open source** (self-hosted or community solutions)
- **Aligned with project goals** (check project docs for stated goals)

**Categories**: Major Features (expansions, modules), Architecture (scalability, microservices, caching), Ecosystem (plugins, APIs), Integrations (databases, multi-platform), Performance (distributed, optimization), Analytics (monitoring, metrics), Developer Platform (SDKs, code generation)

**Techniques**: Study mature OSS projects, consider architectural patterns (event sourcing, CQRS), think 10x capabilities, identify ecosystem gaps, platform expansion (CLI → web, desktop → mobile)

## Prioritization Framework

### Known Issues Prioritization
1. **Critical (P0)**: Blockers, broken functionality, security vulnerabilities
2. **High (P1)**: Architecture improvements, major tech debt, test coverage gaps
3. **Medium (P2)**: Refactoring, DRY violations, documentation updates
4. **Low (P3)**: Polish, minor improvements, nice-to-haves

Consider:
- **Impact**: Affects many components vs. isolated change
- **Dependencies**: Blocks other work or enables future work?
- **Risk**: Safe refactoring vs. risky architectural change

### Quick Win Prioritization
- **Value/Effort Ratio**: Maximum bang for buck
- **Unblocking**: Does it enable other work?
- **Pain Points**: Does it solve a frequent frustration?
- **Adoption**: Will it be immediately useful?

### Strategic Prioritization
- **Long-term Value**: Sustained benefit over time
- **Competitive Advantage**: Unique or differentiating capability
- **Ecosystem Fit**: Aligns with community trends
- **Feasibility**: Realistic with current team/resources

## Output Format

Present opportunities in three sections:

```markdown
## Known Issues (Top 5)

1. [Category] Title
   Description (1-2 sentences explaining the issue)
   Effort: Small/Medium/Large | Impact: Critical/High/Medium/Low

2. [Category] Title
   ...

## Quick Win Ideas (Top 5)

6. [NEW] Title
   Description (1-2 sentences explaining the value)
   Effort: Small | Value: High | Free/OSS: Yes

7. [NEW] Title
   ...

## Strategic Ideas (Top 5)

11. [STRATEGIC] Title
    Description (1-2 sentences explaining the vision)
    Effort: Large | Value: Extreme | Free/OSS: Yes

12. [STRATEGIC] Title
    ...
```

**Summary Line**: Include stats like "3 critical, 4 high, 3 medium issues | 5 quick wins | 5 strategic ideas"

**Prompt**: "Select a number (1-15) to start planning, or 'cancel' to exit:"

## Selection Handler

1. **Wait for User Input**: Accept numbers 1-15 or 'cancel'

2. **On Valid Selection**:
   - Echo the selection with full title and description
   - Ask for confirmation: "Proceed with planning this item? (yes/y to continue)"
   - If confirmed:
     - **For Known Issues**: Gather context from existing docs, related files, error logs
     - **For Quick Wins**: Expand with implementation approach, similar projects, tools needed
     - **For Strategic Ideas**: Break down into phases, identify prerequisites, research needed
   - Construct detailed prompt for `/plan_it` including:
     - Full description with background
     - Relevant files and context
     - Project standards and constraints
     - Free/open source requirement (for ideas)
   - Automatically invoke `/plan_it` with the constructed prompt

3. **On Cancel**: Exit gracefully with message "Cancelled. Run /next_it again anytime."

## AI Instructions

**Adaptability**:
- Discover project structure dynamically (don't assume specific paths)
- Look for project standards in common locations (CLAUDE.md, README.md, CONTRIBUTING.md, docs/)
- Adapt categories to project type (web app vs. CLI vs. library)

**Thoroughness**:
- Check ALL discovery sources, don't shortcut
- Be specific in descriptions (not vague)
- Include actionable next steps

**Balance**:
- Mix maintenance (fixing debt) with innovation (new features)
- Balance quick wins that unblock strategic work
- Consider both developer experience and end-user value

**Creativity**:
- Think outside the box for ideas
- Look at the problem domain, not just the code
- Consider what's missing from similar projects
- Be ambitious but realistic

**Cost Consciousness**:
- ALL ideas must be free/open source
- No paid APIs (free tiers OK if generous)
- No commercial licenses
- Prefer self-hosted over SaaS
- Community-driven solutions

**Quality**:
- Ensure all 15 items are distinct (no duplicates)
- Make ideas actionable (not vague aspirations)
- Ground strategic ideas in reality (not pipe dreams)
- Consider implementation feasibility

---

## Usage

Simply invoke the command (no arguments needed):
```
/next_it
```

The AI will:
1. Analyze the project across all discovery dimensions
2. Brainstorm quick win and strategic ideas
3. Present 15 prioritized opportunities (5 + 5 + 5)
4. Wait for your selection (1-15)
5. Automatically initiate `/plan_it` for the selected item

## Example Output

```
📋 Next Work Opportunities

## Known Issues (Top 5)
1. [P1] Extract storage interface for testing
   Effort: Medium | Impact: High
2. [P3] Add unit tests for filters module
   Effort: Large | Impact: High
...

## Quick Win Ideas (Top 5)
6. [NEW] Add pre-commit hooks for code quality
   Effort: Small | Value: High | Free/OSS: Yes
7. [NEW] Create development environment setup script
   Effort: Small | Value: High | Free/OSS: Yes
...

## Strategic Ideas (Top 5)
11. [STRATEGIC] Implement plugin/extension system
    Effort: Large | Value: Extreme | Free/OSS: Yes
12. [STRATEGIC] Add distributed task processing
    Effort: Large | Value: Extreme | Free/OSS: Yes
...

Summary: 2 critical, 2 high, 1 medium | 5 quick wins | 5 strategic ideas
Select a number (1-15) to start planning, or 'cancel' to exit:
```
