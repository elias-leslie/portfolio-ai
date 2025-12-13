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

### Creating Issues
```bash
bd create "Title" -t feature|bug|task -p 0-4 -d "Description" --json
bd dep add <child> <parent>                  # Link dependencies
bd create "Found bug" --deps discovered-from:<parent-id> --json
```

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

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| `?limit=200` on feature queries | No limit (get all) |
| Assume API field names | Verify with `curl ... \| jq keys` |
| DELETE without dry-run | SELECT/COUNT first |
| `localhost:3000` for screenshots | `192.168.8.233:3000` |
| Manual `systemctl` | Use scripts |
| `git stash` with uncommitted changes | Commit first |
| Hardcode version numbers | Reference STACK.md |
| Skip pre-commit (`--no-verify`) | Fix the issues |

---

## Session Protocol

### Start
```bash
bd ready --json                              # Find work
bd update <id> --status in_progress --json   # Claim it
```

### End
```bash
bd close <id> --reason "Description" --json  # Mark done
bd sync                                       # Force commit/push
```

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
