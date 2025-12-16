# DevVision Extraction - Verification & Planning Session

## Context

We reviewed the modularity planning docs in `tasks/modularity/` and identified gaps. This session needs to verify the plans against reality and create actionable beads.

## Pre-Work Done

1. **Beads Architecture Correction**: Original plan incorrectly proposed migrating beads to PostgreSQL. CORRECTED: Beads stays in each project's `.beads/` directory (JSONL + SQLite). DevVision provides a web UI layer that calls `bd` CLI. See [steveyegge/beads](https://github.com/steveyegge/beads) for design philosophy.

2. **Scope Decision**: MVP = extraction only (Phases 1-3). Auto Mode and AI Reviews deferred to v1.1.

3. **Evidence Migration**: Migrate last 30 days only (~20MB).

4. **Commands**: Stay in each project, call DevVision API.

---

## CRITICAL: Component Categorization (Verified via Discovery)

The Capabilities/System Registry page (`/capabilities`) contains **BOTH** dev tooling AND portfolio-ai domain logic. You MUST split carefully.

### Capabilities Page Tabs Analysis

| Tab | Component | Category | Reason |
|-----|-----------|----------|--------|
| **Vision** | VisionGoalsTab.tsx (22K) | **DEV TOOLING → MOVE** | Strategic goals, vision content tracking |
| **Features** | FeaturesTab.tsx (67K) | **DEV TOOLING → MOVE** | Feature tracking, acceptance criteria, evidence |
| **Files** | FilesTab.tsx (39K) | **DEV TOOLING → MOVE** | Codebase file analysis (make project-agnostic) |
| **Sitemap** | SitemapTab.tsx (10K) | **DEV TOOLING → MOVE** | Endpoint discovery (make project-agnostic) |
| **Sources** | ApiSourcesOverview.tsx (16K) | **DOMAIN → STAYS** | Market data sources (YFinance, Polygon, etc.) |
| **Rules** | RulesViewer.tsx | **DOMAIN → STAYS** | Trading rules from rules.yaml |
| **Database** | CapabilitiesTable.tsx filtered | **DOMAIN → STAYS** | Portfolio-AI DB schema introspection |
| **Celery/Tasks** | CapabilitiesTable.tsx filtered | **DOMAIN → STAYS** | Portfolio-AI Celery tasks |
| **Workflows** | CapabilitiesTable.tsx filtered | **DOMAIN → STAYS** | Portfolio-AI system capabilities |

### Backend Services Analysis

| Service | LOC | Category | Reason |
|---------|-----|----------|--------|
| `artifact_manager.py` | 790 | **DEV TOOLING → MOVE** | Evidence/artifact storage |
| `criteria_verifier.py` | 1125 | **DEV TOOLING → MOVE** | Feature verification engine |
| `file_scanner.py` | 773 | **DEV TOOLING → MOVE** | Codebase analysis |
| `sitemap_service.py` | 1456 | **DEV TOOLING → MOVE** | URL/endpoint discovery |
| `capability_feature_scanner.py` | 455 | **DEV TOOLING → MOVE** | Feature scanning |
| `capability_db_scanner.py` | 550 | **DOMAIN → STAYS** | Introspects portfolio-ai DB |
| `capability_celery_scanner.py` | 743 | **DOMAIN → STAYS** | Introspects portfolio-ai Celery |
| `capability_api_scanner.py` | 482 | **DOMAIN → STAYS** | Introspects portfolio-ai API |
| `thesis_service.py` | 860 | **DOMAIN → STAYS** | Trading theses |
| `news_*.py` | various | **DOMAIN → STAYS** | News processing |
| `market_events_service.py` | varies | **DOMAIN → STAYS** | Market events |

### Backend API Routers Analysis

| Router | LOC | Category | Reason |
|--------|-----|----------|--------|
| `features_router.py` | 1431 | **DEV TOOLING → MOVE** | Feature CRUD, evidence |
| `vision_goals_router.py` | 475 | **DEV TOOLING → MOVE** | Vision goals |
| `vision_content_router.py` | 621 | **DEV TOOLING → MOVE** | Vision content |
| `notes_router.py` | 158 | **DEV TOOLING → MOVE** | Dev notes |
| `capabilities_router.py` | 682 | **SPLIT NEEDED** | Generic shell stays, domain queries stay |
| `sources.py` | ~200 | **DOMAIN → STAYS** | Market data sources API |
| `sitemap.py` | ~350 | **DEV TOOLING → MOVE** | Sitemap API |
| `files.py` | ~230 | **DEV TOOLING → MOVE** | Files API |

### Frontend Components to MOVE

```
frontend/components/capabilities/
├── FeaturesTab.tsx (67K) → MOVE
├── VisionGoalsTab.tsx (22K) → MOVE
├── FilesTab.tsx (39K) → MOVE
├── SitemapTab.tsx (10K) → MOVE
├── SitemapTreeView.tsx (10K) → MOVE
├── SitemapTableView.tsx (7K) → MOVE
├── EvidenceViewerModal.tsx (28K) → MOVE
├── ApiSourcesOverview.tsx (16K) → STAYS (domain-specific)
├── CapabilitiesTable.tsx (52K) → STAYS (domain-specific)
├── StatusBadge.tsx (7K) → COPY (shared utility)
├── WatchlistCoverage.tsx (12K) → STAYS (domain-specific)
```

### Frontend Components to STAY

```
frontend/components/rules/
└── RulesViewer.tsx → STAYS (trading rules)

frontend/components/capabilities/
├── ApiSourcesOverview.tsx → STAYS (market data sources)
├── CapabilitiesTable.tsx → STAYS (db/celery/api introspection)
├── WatchlistCoverage.tsx → STAYS (watchlist coverage)
```

### Standalone Services to MOVE

```
services/dev-companion/           → MOVE (entire service)
├── dev_companion/
│   ├── server.py                 → DevVision backend service
│   ├── gemini_process.py         → AI chat backend
│   └── ...
├── pyproject.toml
└── tests/

frontend/app/dev-assistant/       → MOVE
└── page.tsx (7K)                 → DevVision frontend page

frontend/components/dev-assistant/
└── ChatPanel.tsx (15K)           → MOVE
```

### Database Tables Analysis

| Table | Category | Reason |
|-------|----------|--------|
| `feature_capabilities` | **DEV TOOLING → MOVE** | Feature tracking |
| `feature_tasks` | **DEV TOOLING → MOVE** | Feature tasks (deprecated?) |
| `feature_dependencies` | **DEV TOOLING → MOVE** | Feature deps |
| `feature_vision_goal_mappings` | **DEV TOOLING → MOVE** | Feature-vision links |
| `feature_gap_mappings` | **DEV TOOLING → MOVE** | Feature-gap links |
| `vision_goals` | **DEV TOOLING → MOVE** | Vision goals |
| `vision_content` | **DEV TOOLING → MOVE** | Vision content docs |
| `vision_goal_details` | **DEV TOOLING → MOVE** | Vision goal details |
| `artifacts` | **DEV TOOLING → MOVE** | Evidence artifacts |
| `sitemap_entries` | **DEV TOOLING → MOVE** | URL/endpoint discovery |
| `sitemap_health_history` | **DEV TOOLING → MOVE** | Sitemap health logs |
| `db_capabilities` | **DOMAIN → STAYS** | Portfolio-AI schema introspection |
| `api_capabilities` | **DOMAIN → STAYS** | Portfolio-AI API introspection |
| `celery_capabilities` | **DOMAIN → STAYS** | Portfolio-AI task introspection |
| All trading/portfolio tables | **DOMAIN → STAYS** | Domain data |

### Frontend Pages Analysis

| Page | Category | Reason |
|------|----------|--------|
| `/capabilities` | **SPLIT** | Some tabs move, some stay |
| `/dev-assistant` | **DEV TOOLING → MOVE** | AI chat for dev sessions |
| `/agent-hub` | **DOMAIN → STAYS** | Investment-specific agents |
| All other pages | **DOMAIN → STAYS** | Trading UI |

### Skills Analysis

| Skill | Category | Reason |
|-------|----------|--------|
| `browser-automation/` | **DEV TOOLING → MOVE** | Evidence capture, screenshots |
| `code-quality/` | **DEV TOOLING → MOVE** | Quality metrics |
| `python-patterns/` | **DOMAIN → STAYS** | Portfolio-AI specific patterns |
| `react-patterns/` | **DOMAIN → STAYS** | Portfolio-AI specific patterns |
| `postgresql-patterns/` | **DOMAIN → STAYS** | Portfolio-AI specific patterns |

---

## What Happens to Capabilities Page After Extraction

**Portfolio-AI keeps a slimmed `/capabilities` page with:**
- Sources tab (market data providers)
- Rules tab (trading rules)
- Database tab (schema introspection)
- Tasks tab (Celery tasks)
- Workflows tab (system capabilities)

**DevVision gets a new `/projects/{id}/dev` page with:**
- Vision tab
- Features tab
- Files tab
- Sitemap tab
- Beads UI (NEW)

---

## Your Tasks

### 1. Commit Pending Changes First
```bash
# Already committed in previous session - verify clean
git status
```

### 2. Verify Categorization Above

Run these to confirm the analysis:

```bash
# Capabilities API structure
find ~/portfolio-ai/backend/app/api/capabilities -name "*.py" -exec wc -l {} +

# Services that MOVE
wc -l ~/portfolio-ai/backend/app/services/{artifact_manager,criteria_verifier,file_scanner,sitemap_service,capability_feature_scanner}.py

# Services that STAY
wc -l ~/portfolio-ai/backend/app/services/{capability_db_scanner,capability_celery_scanner,capability_api_scanner,thesis_service}.py

# Frontend components
ls -la ~/portfolio-ai/frontend/components/capabilities/
ls -la ~/portfolio-ai/frontend/components/rules/

# Skills
ls -la ~/portfolio-ai/.claude/skills/

# Sources API (should STAY - domain specific)
head -30 ~/portfolio-ai/backend/app/api/sources.py
```

### 3. Update Task File with Categorization

Edit `tasks/modularity/tasks-devvision-extraction.md`:

**Critical Updates:**
- [ ] Add "Component Categorization" section with tables above
- [ ] Section on Beads: Change from PostgreSQL migration to "UI layer over bd CLI"
- [ ] Clarify that Sources tab, Rules tab, Database/Celery/Workflows tabs STAY in portfolio-ai
- [ ] Update extraction list to only include dev tooling components
- [ ] Add note about capabilities_router.py needing to be split (some generic, some domain)

### 4. Create Beads for DevVision Work

```bash
# Epic
bd create "Epic: DevVision Platform Extraction" \
  -t epic -p 1 \
  -l "complexity:large,domains:backend,domains:frontend,domains:database" \
  -d "Extract dev tooling into standalone platform. MVP = Phases 1-3 (extraction). Auto Mode/AI Reviews = v1.1. See tasks/modularity/tasks-devvision-extraction.md

MOVES: Features, Vision, Files, Sitemap, Evidence, Beads UI
STAYS: Sources, Rules, DB/Celery/Workflows introspection"

# Phase 1 - Foundation
bd create "DevVision Phase 1: Foundation setup" \
  -t task -p 1 \
  -l "complexity:medium,domains:backend,domains:frontend,domains:database" \
  -d "Create ~/devvision repo, FastAPI+Next.js scaffold, PostgreSQL schema (projects, features, evidence, acceptance_criteria - NO beads table)"

# Phase 2 - Backend Extraction
bd create "DevVision Phase 2: Backend extraction" \
  -t task -p 1 \
  -l "complexity:large,domains:backend" \
  -d "Extract: features_router, vision_*_router, notes_router, sitemap, files APIs. Extract: artifact_manager, criteria_verifier, file_scanner, sitemap_service, capability_feature_scanner. Create beads API (bd CLI wrapper). Add project registration."

# Phase 3 - Frontend Extraction
bd create "DevVision Phase 3: Frontend extraction" \
  -t task -p 1 \
  -l "complexity:large,domains:frontend" \
  -d "Extract: FeaturesTab, VisionGoalsTab, FilesTab, SitemapTab, EvidenceViewerModal. Build Beads UI (CRUD via bd CLI). Create multi-project dashboard. Update capabilities page.tsx to remove extracted tabs."

# Link dependencies
bd dep add <phase2-id> <phase1-id> --type blocks
bd dep add <phase3-id> <phase2-id> --type blocks
```

### 5. Handle Existing P1 Beads

The existing P1 beads (Alert Infrastructure 722, Maintenance uep/8ba) conflict with DevVision work. Options:
- **Option A**: Defer them, start DevVision now
- **Option B**: Complete them first (1-2 weeks), then DevVision
- **Option C**: Work DevVision Phase 1 in parallel (repo setup doesn't conflict)

Decision needed from user.

---

## Key Architecture Decisions (Already Made)

| Decision | Choice |
|----------|--------|
| Beads storage | JSONL in each project (no PostgreSQL) |
| DevVision Beads UI | Calls `bd` CLI via subprocess |
| MVP scope | Phases 1-3 only |
| Auto Mode | Deferred to v1.1 |
| Evidence migration | Last 30 days only |
| Commands | Stay in project, call DevVision API |
| Rules (.claude/rules/) | All stay in project |
| Sources tab | STAYS in portfolio-ai (domain-specific) |
| Rules tab | STAYS in portfolio-ai (trading rules) |
| DB/Celery/Workflows tabs | STAY in portfolio-ai (app introspection) |

---

## Files to Reference

- `tasks/modularity/tasks-devvision-extraction.md` - Main implementation plan (needs corrections)
- `tasks/modularity/architecture-roadmap.md` - Executive summary
- `tasks/modularity/modularity.md` - Original discussion transcript
- `~/.claude/plans/lucky-beaming-zephyr.md` - Discussion log from previous session

---

## Success Criteria

By end of this session:
- [ ] Categorization verified via exploration commands
- [ ] `tasks-devvision-extraction.md` updated with component categorization
- [ ] Beads architecture section corrected (UI over bd CLI, not PostgreSQL)
- [ ] Epic + Phase 1-3 beads created with accurate descriptions
- [ ] Decision made on existing P1 beads
- [ ] Ready to begin Phase 1 implementation
