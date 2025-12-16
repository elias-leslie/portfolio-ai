# Architecture Modularity Roadmap

**Created**: 2025-12-16
**Status**: Planning Complete, Ready for Implementation
**Owner**: Local Claude Agent + User

---

## Executive Summary

Portfolio AI has grown to **138,000+ lines of code** with a monolithic architecture that mixes:
- Core business logic (investment intelligence) - ~60%
- Development/meta tooling (capabilities, evidence, verification) - ~30%
- Infrastructure - ~10%

This roadmap defines a **3-phase modularization strategy** to extract standalone services, improve internal architecture, and create marketable products from existing code.

---

## Strategic Vision

### Phase 1: DevVision Platform (P1) ⭐⭐⭐⭐⭐
**Priority**: HIGHEST - Do This First
**Effort**: 3-4 weeks
**Impact**: Massive

Extract all development/meta tooling into **DevVision** - a standalone platform for AI-assisted software development.

**What is DevVision?**
- Multi-project development platform
- Global beads (work tracking across all projects)
- Evidence capture system (screenshots, logs, metrics)
- Feature verification engine
- Web terminal (Claude Code native access)
- Multi-LLM chat (Claude, Gemini, round table)
- Auto mode (autonomous development using Anthropic's long-running agent patterns)
- Scheduled AI reviews (Gemini 1-2M token daily reviews)

**Benefits:**
- Reduces portfolio-ai by ~30% (~40k LOC)
- Immediately reusable on all future projects
- Potential commercial product (no one has this combination)
- Self-improving (use DevVision to build DevVision)
- Portfolio AI becomes first reference implementation

**Task Plan**: `tasks/tasks-devvision-extraction.md`

---

### Phase 2: Internal Refactoring (P3) ⭐⭐⭐
**Priority**: High - After DevVision extraction proves the pattern
**Effort**: 2-3 weeks
**Impact**: High (maintainability, onboarding, velocity)

Refactor Portfolio AI's internal architecture to enforce:
- **Domain-Driven Design** (bounded contexts: portfolio, market, trading, intelligence, watchlist, user)
- **Dependency Inversion** (services depend on interfaces, not implementations)
- **Event-Driven Communication** (no direct cross-context calls)
- **Strict Size Limits** (300-line soft limit, down from current 500)
- **Proper Test Pyramid** (80% unit, 15% integration, 5% E2E - currently inverted)

**Current Problems:**
- Files up to 1456 lines (sitemap_service.py)
- Unclear domain boundaries (`services/` is a dumping ground)
- Direct cross-domain coupling (portfolio → watchlist direct calls)
- Too many integration tests (slow, brittle)

**Benefits:**
- Easier onboarding (clear boundaries)
- Faster development (isolated changes)
- Better testability (pure unit tests)
- Less technical debt accumulation

**Task Plan**: `tasks/tasks-internal-refactoring.md`

---

### Phase 3: StrategyLab Service (P4) ⭐
**Priority**: Low - DEFER until after P1 + P3
**Effort**: 3-4 weeks (high complexity)
**Impact**: Uncertain (no immediate need)

Extract backtesting and strategy systems into **StrategyLab** - a standalone strategy research platform.

**What is StrategyLab?**
- Generic backtesting engine (works with any trading strategy)
- Strategy interface and implementations
- Performance analytics and optimization
- Heavy computation (could run on separate infrastructure)

**Benefits:**
- Reduces portfolio-ai by ~15-20k LOC
- Reusable for multiple trading apps
- Potential strategy research platform product

**Challenges:**
- Deeply integrated with portfolio data model
- No second client waiting
- Not currently a bottleneck
- May be better handled by P3's bounded contexts

**RECOMMENDATION: DEFER**
- Treat as bounded context in P3 instead
- Re-evaluate after P1 + P3 complete
- Extract later if clear need emerges

**Task Plan**: `tasks/tasks-backtest-strategy-extraction.md`

---

## Implementation Order

### Recommended Sequence

```
1. DevVision Extraction (P1)
   ├─ Proves extraction pattern works
   ├─ Immediately usable for ongoing work
   ├─ Reduces cognitive load on portfolio-ai
   └─ Creates foundation for multi-project workflow

2. Internal Refactoring (P3)
   ├─ Portfolio-ai now smaller (easier to refactor)
   ├─ Use DevVision to manage the refactoring work
   ├─ Validates DevVision's effectiveness
   └─ Creates clean architecture for future features

3. StrategyLab Extraction (P4) - DEFERRED
   ├─ Re-evaluate after P1 + P3 complete
   ├─ P3's bounded contexts may eliminate need
   └─ Extract only if clear value emerges
```

### Why This Order?

**P1 First (DevVision):**
- Clearest boundary (dev tooling ≠ investment logic)
- Highest ROI (use immediately on all projects)
- Creates tooling to manage P3 work
- Potential product (commercial value)

**P3 Second (Refactoring):**
- Easier after removing 30% of code
- Use DevVision to track refactoring beads
- Proves DevVision handles complex work
- Prepares for future feature velocity

**P4 Third (StrategyLab):**
- DEFERRED - re-evaluate after P1 + P3
- High complexity, uncertain value
- P3's bounded contexts may solve this better
- Extract only if clear need (second client, bottleneck, product opportunity)

---

## Auto Mode Integration (P1 Enhancement)

As part of DevVision, implement **Auto Mode** based on:
- [Anthropic's Long-Running Agent Patterns](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Python harness + Claude Code SDK
- OAuth integration (already wired up)

**Auto Mode Capabilities:**
1. **Task Decomposition**: Claude breaks down complex tasks into verifiable steps
2. **Execution Loop**: Iterates with checkpoints and state persistence
3. **Tool Execution**: Reads/writes code, runs tests, verifies criteria
4. **Error Recovery**: Retries with adjustments when failures occur
5. **Resume Support**: Can pause/resume from any checkpoint

**UI:**
- Describe task in natural language
- Watch real-time progress (phase, steps, logs)
- Streamed execution logs
- Auto-created beads for discovered issues

**Example Auto Mode Task:**
> "Add a new endpoint to fetch portfolio performance metrics grouped by sector"

Auto mode will:
1. Plan: Define endpoint spec, identify files to modify, list tests needed
2. Execute: Create endpoint, update router, add tests, verify criteria
3. Verify: Run tests, check types, lint code, capture evidence
4. Report: Summary with links to beads for any issues found

---

## Local Agent Instructions

**You are the local Claude agent** with complete access to the development environment.

### Your Responsibilities

1. **Verify All Claims**
   - Don't trust the architectural analysis blindly
   - Run the verification commands in each task plan's "MANDATORY" section
   - Correct any incorrect assumptions
   - Update plans based on discoveries

2. **Create Bead Structure**
   - For EACH task plan, create an epic bead
   - For EACH major phase in the plan, create a task/feature bead
   - Link phase beads to epic with dependencies
   - Use proper labels: `complexity:*`, `domains:*`
   - See `.claude/docs/bead-reference.md` for valid types/labels

3. **Execute Work**
   - Follow the task plans sequentially
   - Mark beads as in_progress before starting
   - Commit frequently with good messages
   - Mark beads as closed when complete
   - Create new beads for discovered issues (`.claude/rules/issue-tracking.md`)

4. **Update Plans**
   - Keep task files current (check boxes, summaries, timestamps)
   - If you discover complexity was underestimated, update effort
   - If you find missing dependencies, add them
   - Document blockers and decisions

5. **Landing the Plane**
   - Commit implementation changes FIRST
   - Then update/close beads
   - Commit bead changes separately
   - `git pull --rebase && git push` (MANDATORY)
   - See `AGENTS.md` for full session end protocol

### Critical Rules

- **NEVER skip verification** - Always run the analysis commands first
- **NEVER guess at architecture** - Read the actual code
- **ALWAYS create beads for discovered issues** - See `.claude/rules/issue-tracking.md`
- **ALWAYS check for existing implementations** - See `.claude/rules/architecture-coherence.md`
- **ALWAYS commit and push** - Never leave work unpushed

### Getting Started

To start P1 (DevVision extraction):

```bash
# 1. Read the task plan
cat ~/portfolio-ai/tasks/tasks-devvision-extraction.md

# 2. Run verification commands (MANDATORY section)
# ... (follow instructions in task plan)

# 3. Create epic bead
bd create "Epic: Extract DevVision platform from Portfolio AI" \
  -t epic -p 1 \
  -l "complexity:large,domains:backend,domains:frontend,domains:database" \
  -d "Extract development tooling into standalone platform. See tasks/tasks-devvision-extraction.md" \
  --json

# 4. Create phase beads and link to epic
# ... (follow task plan)

# 5. Begin Phase 1.1
bd update <phase-1.1-bead-id> --status in_progress
# ... implement Phase 1.1 tasks
```

---

## Success Metrics

### DevVision (P1)
- [ ] Manages Portfolio AI development (all beads, features, evidence)
- [ ] Auto mode completes simple feature end-to-end (>70% success rate)
- [ ] Scheduled AI reviews generate actionable beads
- [ ] Web terminal provides Claude Code access
- [ ] Can onboard second project in <5 minutes
- [ ] Portfolio AI codebase reduced by 30%+

### Internal Refactoring (P3)
- [ ] All bounded contexts defined (no cross-context imports)
- [ ] All files <300 lines
- [ ] Event bus handles cross-context communication
- [ ] Repository pattern implemented
- [ ] Test pyramid achieved (80/15/5)
- [ ] Development velocity increased (measure via bead completion rate)

### StrategyLab (P4) - IF EXTRACTED
- [ ] Runs backtests independently
- [ ] Portfolio AI uses StrategyLab client successfully
- [ ] All strategies migrated and working
- [ ] Performance matches previous implementation
- [ ] Can serve second client application
- [ ] Portfolio AI codebase reduced by 15-20k LOC

---

## Risk Mitigation

### Risk: DevVision extraction breaks Portfolio AI

**Mitigation:**
- Extract incrementally (one phase at a time)
- Keep Portfolio AI working throughout migration
- Extensive testing after each phase
- Can rollback git commits if needed

### Risk: Auto mode is too complex to implement

**Mitigation:**
- Start simple (basic task decomposition)
- Iterate on capabilities (Phase 4.1 → 4.2 → 4.3)
- Learn from Anthropic's patterns article
- Fall back to manual mode if auto mode doesn't work

### Risk: Time estimates are too optimistic

**Mitigation:**
- Plans are detailed enough to reveal hidden complexity
- Local agent will update estimates based on verification
- Can pause between phases if needed
- Each phase delivers value independently (not all-or-nothing)

---

## Next Steps

**For User:**
1. Review this roadmap and the 3 task plans
2. Confirm agreement with priority order (P1 → P3 → P4)
3. Give local agent permission to start P1
4. Decide if you want to pause between phases for review

**For Local Agent:**
1. Read all 3 task plans thoroughly
2. Run verification commands for P1 (DevVision extraction)
3. Create bead structure for P1 (epic + phase beads)
4. Begin Phase 1.1: DevVision repository setup
5. Check in with user after each major phase completion

---

## References

**Task Plans:**
- P1: `tasks/tasks-devvision-extraction.md`
- P3: `tasks/tasks-internal-refactoring.md`
- P4: `tasks/tasks-backtest-strategy-extraction.md` (DEFERRED)
- Future: `tasks/tasks-data-ingestion-extraction-FUTURE.md` (DataFountain concept)

**Project Documentation:**
- `AGENTS.md` - Workflow and session protocol
- `CLAUDE.md` - Quick reference
- `ARCHITECTURE.md` - Current system design
- `.claude/rules/architecture-coherence.md` - Anti-silo rules
- `.claude/rules/issue-tracking.md` - Bead creation protocol
- `.claude/docs/bead-reference.md` - Valid types, labels, commands

**External References:**
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html)

---

**Version:** 1.0.0 | **Updated:** 2025-12-16
