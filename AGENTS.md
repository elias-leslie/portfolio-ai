# Portfolio-AI Agent Instructions

Before anything else: run `bd onboard` and follow instructions.

## Task Tracking (Beads)

### Finding Work
```bash
bd ready --json              # Find unblocked work
bd list --status open --json # All open issues
bd stale --days 7 --json     # Forgotten issues
```

### Working on Issues
```bash
bd update <id> --status in_progress --json   # Claim work
bd close <id> --reason "Completed" --json    # Mark done
bd sync                                       # MANDATORY at session end
```

### Creating Issues (ENFORCED by pre-push hook)
```bash
# Labels are REQUIRED - pre-push hook blocks if missing!
bd create "Title" -t feature|bug|task -p 0-4 -d "Description" \
  --set-labels "complexity:small" --set-labels "domains:backend" --json

bd dep add <child> <parent>                  # Link dependencies
bd create "Found bug" --deps discovered-from:<parent-id> \
  --set-labels "complexity:small" --set-labels "domains:backend" --json
```

**See `.claude/rules/bead-quality.md` for full requirements.**

### Complexity Labels (REQUIRED for /next_it efficiency)
| Label | Criteria | Agent Strategy |
|-------|----------|----------------|
| `complexity:small` | <3 files, <50 lines | Orchestrator direct |
| `complexity:medium` | 3-10 files, <200 lines | Light agent assist |
| `complexity:large` | >10 files OR multi-domain | Full specialist agents |

### Domain Labels (REQUIRED)
| Label | When |
|-------|------|
| `domains:backend` | Python/FastAPI changes |
| `domains:frontend` | React/Next.js changes |
| `domains:database` | Schema/migration changes |

### Priority Levels
| Level | Meaning |
|-------|---------|
| 0 | Critical (security, data loss) |
| 1 | High (major features, important bugs) |
| 2 | Medium (enhancements, minor bugs) |
| 3 | Low (polish, optimization) |
| 4 | Backlog (future ideas) |

---

## Feature Verification (Portfolio-AI)

For major features requiring evidence, use the verification system:

### Run Verification
```bash
curl -X POST localhost:8000/api/capabilities/features/FEAT-XXX/verify
```

### Capture Evidence
```bash
curl -X POST localhost:8000/api/artifacts/refresh \
  -H "Content-Type: application/json" \
  -d '{"feature_id": "FEAT-XXX", "criterion_id": "ac-001", "url": "http://192.168.8.233:3000/page"}'
```

### Link Beads Issue to Feature
```bash
bd update <id> --notes "Feature: FEAT-XXX"
```

### Verification Commands (Keep Using)
| Command | Purpose |
|---------|---------|
| `/verify_it FEAT-XXX` | Full-stack verification with evidence |
| `/test_it` | UI regression testing |

---

## Code Quality

### Testing Separation
| Layer | Purpose | Tool |
|-------|---------|------|
| Unit tests | Logic correctness | pytest |
| Type safety | Catch type errors | mypy |
| Lint/format | Code style | ruff, pre-commit |
| E2E verification | Feature works for users | Acceptance criteria |

### Rules
- Never skip pre-commit hooks
- pytest for business logic (edge cases, calculations)
- Acceptance criteria for integration/E2E
- Don't duplicate - if pytest tests it, acceptance criteria shouldn't

### Architecture Coherence
- **Before ANY new code**: Check for existing implementations (see `.claude/rules/architecture-coherence.md`)
- Run `/silo_check` for comprehensive architecture audit
- Consolidate over create - extend existing utilities, don't duplicate

---

## Domain Rules

### Data
- Use `symbol` everywhere, NEVER `ticker`
- Verify before DELETE (SELECT first)
- No hardcoded limits on queries (`?limit=N`)

### UI/Backend
- Backend changes MUST have UI visibility
- Screenshots use `192.168.8.233:3000` (not localhost)

### Services
- Celery tasks for data fetching (no manual scripts)
- Use systemd scripts exclusively:
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh  # After code changes
  bash ~/portfolio-ai/scripts/status.sh   # Check health
  ```

### Logs
```bash
journalctl --user -u portfolio-backend -f
journalctl --user -u portfolio-celery -f
```

---

## MANDATORY: Track Discovered Issues

**When you encounter ANY pre-existing bug, error, or issue during your work, you MUST:**

1. **Review ALL open Beads** (do NOT filter by keywords - you might miss matches):
   ```bash
   bd list --status open --json | jq -r '.[] | "\(.id) \(.title)"'
   ```
2. **If no bead exists, CREATE + LINK IMMEDIATELY**:
   ```bash
   # Create the bug with complexity and domain labels
   bd create --title "Fix: <clear description>" \
     --description "Error: <exact error message>

   Location: <file:line>

   Found during: <parent-bead-id> <task name>" \
     --priority 2 --type bug \
     --set-labels "complexity:small" --set-labels "domains:backend" \
     --json

   # MANDATORY: Link with discovered-from dependency
   bd dep add <new-id> <parent-bead-id> --type discovered-from
   ```
3. **If bead exists, UPDATE with new info**: `bd update <id> --notes "Additional context..."`

**This is MANDATORY. Do NOT:**
- Mention bugs in summaries without creating beads
- Say "pre-existing issue, not related to this task" and move on
- Leave issues undocumented for future discovery
- Filter beads by keywords (scan the FULL list)

**Every discovered issue = immediate bead creation + dependency link. No exceptions.**

---

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| `?limit=200` on feature queries | No limit (get all) |
| Assume API field names | Verify with `curl ... \| jq keys` |
| DELETE without dry-run | SELECT/COUNT first |
| `localhost:3000` for screenshots | `192.168.8.233:3000` |
| Manual `systemctl` | Use scripts |
| `git stash` with uncommitted changes | Commit first |
| Start work with dirty working tree | Commit previous changes FIRST |
| Hardcode version numbers | Reference STACK.md |
| Skip pre-commit (`--no-verify`) | Fix the issues |
| Note bugs without creating beads | Create bead IMMEDIATELY |

---

## Session Protocol

### Start - MANDATORY

**Before starting ANY new work, verify clean working tree:**

#### 1. Check for Uncommitted Changes (MANDATORY)
```bash
git status --short
```
- If output shows files: **STOP** - you have uncommitted changes from a previous session
- **You MUST commit these BEFORE proceeding:**
  ```bash
  git diff --stat                    # Review what changed
  git add -A && git commit -m "WIP: Previous session changes"
  git push
  ```

#### 2. Find and Claim Work
```bash
bd ready --json                              # Find work
bd update <id> --status in_progress --json   # Claim it
```

**Critical:** Uncommitted changes break multi-agent coordination. Never start new work on a dirty tree.

### End ("Landing the Plane") - MANDATORY

**All steps must complete before session ends. The plane hasn't landed until `git push` succeeds.**

#### 1. Run Quality Gates (if code changed)
```bash
cd backend && .venv/bin/ruff check app/ --fix
cd backend && .venv/bin/mypy app/ --no-error-summary
cd backend && .venv/bin/pytest tests/ -x --tb=short -q
```
- If builds/tests broken, file P0 issue before continuing

#### 2. Commit Your Implementation Changes FIRST
```bash
git add <your-changed-files>
git commit -m "feat/fix/chore: <title>

<WHY this change was needed - 1-2 sentences>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```
**IMPORTANT:** Commit message must be 100+ chars with reasoning (pre-commit hook enforces this).

#### 3. Update Beads State (AFTER implementation commit)
```bash
# Close completed issues
bd close <id> --reason "Completed: <summary>"

# Update in-progress work
bd update <id> --notes "Progress: <what was done>"

# Create beads for discovered bugs (see MANDATORY section above)
```

#### 4. Commit Beads Changes Separately
`bd close` and `bd update` modify `.beads/issues.jsonl`. Commit this BEFORE pulling:
```bash
git add .beads/issues.jsonl
git commit -m "chore: Update beads state after <task-id>

Closes/updates beads for: <brief description of what was completed>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

#### 5. Push to Remote (NON-NEGOTIABLE)
```bash
git pull --rebase && git push
git status  # MUST show "up to date with origin/main"
```
- If pull/push fails, resolve and retry until successful
- Never say "ready to push when you are"—YOU must push
- Unpushed work breaks multi-agent coordination

**NOTE:** Skip `bd sync` - it has worktree bugs. The manual commit pattern above is more reliable.

#### 6. Verify Clean State
```bash
git status  # Should show: "nothing to commit, working tree clean"
```

#### 7. Choose Next Work
- Run `bd ready --json` to identify next task
- Provide context for next session if needed

**Critical Rules:**
- Commit implementation BEFORE closing beads (order matters!)
- Commit beads changes BEFORE `git pull --rebase` (avoids unstaged changes error)
- Never stop before pushing—that leaves work stranded locally
- Lost issues = lost work = unacceptable

---

## Documentation

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](docs/core/ARCHITECTURE.md) | System design |
| [DEVELOPMENT.md](docs/core/DEVELOPMENT.md) | Workflows |
| [API_REFERENCE.md](docs/core/API_REFERENCE.md) | Endpoints |
| [STACK.md](docs/core/STACK.md) | Version numbers |

---

## Quick Reference

| Task | Command |
|------|---------|
| Find work | `bd ready --json` |
| Verify feature | `/verify_it FEAT-XXX` |
| Restart services | `bash ~/portfolio-ai/scripts/restart.sh` |
| Check health | `bash ~/portfolio-ai/scripts/status.sh` |
| Run tests | `cd backend && pytest tests/ -v` |
| Check types | `cd backend && mypy app/` |
