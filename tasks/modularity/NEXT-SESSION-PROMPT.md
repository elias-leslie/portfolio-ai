# DevVision Extraction - Verification & Planning Session

## Context

We reviewed the modularity planning docs in `tasks/modularity/` and identified gaps. This session needs to verify the plans against reality and create actionable beads.

## Pre-Work Done

1. **Beads Architecture Correction**: Original plan incorrectly proposed migrating beads to PostgreSQL. CORRECTED: Beads stays in each project's `.beads/` directory (JSONL + SQLite). DevVision provides a web UI layer that calls `bd` CLI. See [steveyegge/beads](https://github.com/steveyegge/beads) for design philosophy.

2. **Scope Decision**: MVP = extraction only (Phases 1-3). Auto Mode and AI Reviews deferred to v1.1.

3. **Evidence Migration**: Migrate last 30 days only (~20MB).

4. **Commands**: Stay in each project, call DevVision API.

## Your Tasks

### 1. Commit Pending Changes First
```bash
git add tasks/modularity/ docs/ tasks/
git commit -m "docs: Move modularity planning to tasks/modularity/"
git push
```

### 2. Explore & Verify Extraction Targets

Run these to verify the plan matches reality:

```bash
# What exists in capabilities API?
find ~/portfolio-ai/backend/app/api/capabilities -name "*.py" -exec wc -l {} +

# What services are extraction candidates?
wc -l ~/portfolio-ai/backend/app/services/{artifact_manager,criteria_verifier,file_scanner,sitemap_service}.py 2>/dev/null

# Frontend capabilities pages?
find ~/portfolio-ai/frontend/app/capabilities -name "*.tsx" | head -20
find ~/portfolio-ai/frontend/app/dev-assistant -name "*.tsx" | head -20

# Skills to potentially move?
ls -la ~/portfolio-ai/.claude/skills/

# Current beads structure?
ls -la ~/portfolio-ai/.beads/
wc -l ~/portfolio-ai/.beads/issues.jsonl

# Evidence volume?
du -sh ~/portfolio-ai/data/artifacts/
find ~/portfolio-ai/data/artifacts -mtime -30 -type f | wc -l
```

### 3. Verify What STAYS in Portfolio-AI

Confirm domain logic isn't accidentally listed for extraction:
```bash
# These should NOT move
ls ~/portfolio-ai/backend/app/watchlist/
ls ~/portfolio-ai/backend/app/portfolio/
ls ~/portfolio-ai/backend/app/sources/
ls ~/portfolio-ai/backend/app/analytics/
```

### 4. Update Task File with Findings

Edit `tasks/modularity/tasks-devvision-extraction.md`:

**Critical Corrections:**
- [ ] Section on Beads: Change from PostgreSQL migration to "UI layer over bd CLI"
- [ ] Update LOC estimates based on actual file counts
- [ ] Add/remove components based on exploration findings
- [ ] Verify Phase dependencies are accurate

### 5. Create Beads for DevVision Work

```bash
# Epic
bd create "Epic: DevVision Platform Extraction" \
  -t epic -p 1 \
  -l "complexity:large,domains:backend,domains:frontend,domains:database" \
  -d "Extract dev tooling into standalone platform. MVP = Phases 1-3 (extraction). Auto Mode/AI Reviews = v1.1. See tasks/modularity/tasks-devvision-extraction.md"

# Phase 1 - Foundation
bd create "DevVision Phase 1: Foundation setup" \
  -t task -p 1 \
  -l "complexity:medium,domains:backend,domains:frontend,domains:database" \
  -d "Create ~/devvision repo, FastAPI+Next.js scaffold, PostgreSQL schema (projects, features, evidence, acceptance_criteria - NO beads table)"

# Phase 2 - Backend Extraction
bd create "DevVision Phase 2: Backend extraction" \
  -t task -p 1 \
  -l "complexity:large,domains:backend" \
  -d "Copy capabilities API routers, services (artifact_manager, criteria_verifier, file_scanner). Create beads API that wraps bd CLI. Add project registration."

# Phase 3 - Frontend Extraction
bd create "DevVision Phase 3: Frontend extraction" \
  -t task -p 1 \
  -l "complexity:large,domains:frontend" \
  -d "Copy capabilities UI, build Beads UI (CRUD via bd CLI), copy dev-assistant components, multi-project dashboard."

# Link dependencies
bd dep add <phase2-id> <phase1-id> --type blocks
bd dep add <phase3-id> <phase2-id> --type blocks
```

### 6. Pause Existing P1 Beads

The existing P1 beads (Alert Infrastructure 722, Maintenance uep/8ba) conflict with DevVision work. Either:
- Close them as "deferred"
- Or work them first before starting DevVision

Decision needed from user.

## Key Architecture Decisions (Already Made)

| Decision | Choice |
|----------|--------|
| Beads storage | JSONL in each project (no PostgreSQL) |
| DevVision Beads UI | Calls `bd` CLI via subprocess |
| MVP scope | Phases 1-3 only |
| Auto Mode | Deferred to v1.1 |
| Evidence migration | Last 30 days only |
| Commands | Stay in project, call DevVision API |
| Rules | All stay in project |

## Files to Reference

- `tasks/modularity/tasks-devvision-extraction.md` - Main implementation plan (needs corrections)
- `tasks/modularity/architecture-roadmap.md` - Executive summary
- `tasks/modularity/modularity.md` - Original discussion transcript
- `~/.claude/plans/lucky-beaming-zephyr.md` - Discussion log from previous session

## Success Criteria

By end of this session:
- [ ] Pending git changes committed
- [ ] Exploration commands run, findings documented
- [ ] `tasks-devvision-extraction.md` updated with corrections
- [ ] Epic + Phase 1-3 beads created with dependencies
- [ ] Ready to begin Phase 1 implementation
