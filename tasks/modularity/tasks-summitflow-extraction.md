# Task List: SummitFlow Platform Extraction (P1)

**PRD**: Architecture Modularity Review - Priority 1
**Status**: Ready
**Completion**: 0%
**Effort to Complete**: High (3-4 week sprint if focused)
**Last Updated**: 2025-12-16

---

## MANDATORY: Verify Before Starting

**⚠️ LOCAL AGENT: Before implementing ANY step below, you MUST:**

1. **Verify all architectural claims**:
   ```bash
   # Count actual lines in capabilities system
   find ~/portfolio-ai/backend/app/api/capabilities -name "*.py" -exec wc -l {} + | tail -1
   find ~/portfolio-ai/backend/app/services -name "*capability*" -o -name "*artifact*" -o -name "*criteria*" | xargs wc -l

   # Verify frontend scope
   find ~/portfolio-ai/frontend/app/capabilities -type f | wc -l
   find ~/portfolio-ai/frontend/app/dev-assistant -type f | wc -l

   # Analyze database schema
   psql -d portfolio_ai -c "\dt" | grep -E "(capabilities|features|artifacts|evidence|vision)"
   ```

2. **Review existing code structure**:
   - Read `backend/app/api/capabilities/__init__.py` - understand routing
   - Read `backend/app/services/artifact_manager.py` - evidence storage patterns
   - Read `frontend/app/capabilities/page.tsx` - UI organization
   - Read `.claude/commands/verify_it.md` - verification workflow

3. **Understand database dependencies**:
   ```bash
   # Extract schema for capabilities tables
   psql -d portfolio_ai -c "\d+ capabilities"
   psql -d portfolio_ai -c "\d+ features"
   psql -d portfolio_ai -c "\d+ artifacts"
   psql -d portfolio_ai -c "\d+ acceptance_criteria"
   psql -d portfolio_ai -c "\d+ vision_goals"
   ```

4. **Analyze command integration**:
   - How does `/test_it` trigger evidence capture?
   - How does `/verify_it` interact with features API?
   - What Celery tasks are involved?

5. **Update this plan** based on discoveries:
   - Correct any incorrect assumptions
   - Add missing dependencies
   - Adjust effort estimates

6. **Create beads structure**:
   ```bash
   # Create epic for SummitFlow extraction
   bd create "Epic: Extract SummitFlow platform from Portfolio AI" \
     -t epic -p 1 \
     -l "complexity:large,domains:backend,domains:frontend,domains:database" \
     -d "Extract development tooling into standalone platform. See tasks/tasks-summitflow-extraction.md" \
     --json

   # For EACH major phase below, create a bead linked to epic
   # Example:
   bd create "Phase 1.1: SummitFlow repository setup" \
     -t task -p 1 \
     -l "complexity:small,domains:backend,domains:frontend" \
     -d "Initialize SummitFlow repo structure. See tasks/tasks-summitflow-extraction.md Phase 1.1" \
     --json

   # Link to epic
   bd dep add <phase-bead-id> <epic-bead-id> --type blocked-by
   ```

---

## Summary

**Goal**: Extract development/meta tooling from Portfolio AI into a standalone **SummitFlow** platform that can manage development for multiple target applications.

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- Initial planning and verification

**⚠️ NEXT STEPS:**
1. Verify architectural claims (see MANDATORY section above)
2. Create bead structure (epic + phase beads)
3. Begin Phase 1.1: Repository setup

**⏱️ ESTIMATED REMAINING:** High complexity - 3-4 week sprint

---

## What Gets Extracted

### Backend Components (~15-20k LOC)
```
backend/app/
├── api/capabilities/           → summitflow/backend/app/api/projects/
│   ├── features_router.py      (1431 lines)
│   ├── capabilities_router.py  (682 lines)
│   ├── vision_content_router.py (22106 bytes)
│   ├── vision_goals_router.py  (16567 bytes)
│   └── notes_router.py
├── services/
│   ├── artifact_manager.py     (790 lines) → Evidence storage
│   ├── criteria_verifier.py    (1125 lines) → Verification engine
│   ├── capability_*.py         (scanner, feature scanner)
│   ├── file_scanner.py         (773 lines)
│   └── sitemap_service.py      (1456 lines)
└── tasks/
    └── (evidence capture tasks) → Scheduled review tasks
```

### Frontend Components (~8-10k LOC)
```
frontend/
├── app/
│   ├── capabilities/           → summitflow/frontend/app/projects/[id]/
│   ├── dev-assistant/          → summitflow/frontend/app/terminal/
│   └── (evidence modals)       → summitflow/frontend/components/evidence/
└── components/
    └── (capability components) → summitflow/frontend/components/
```

### Infrastructure
```
.claude/
├── commands/
│   ├── test_it.md             → SummitFlow API endpoint
│   ├── verify_it.md           → SummitFlow API endpoint
│   ├── audit_it.md            → SummitFlow API endpoint
│   └── next_it.md             → SummitFlow work allocator
├── skills/
│   └── browser-automation/    → SummitFlow evidence capture
└── (beads system)             → SummitFlow global tracker

automation/                     → SummitFlow scheduled tasks
solution_state/                 → SummitFlow evidence storage
```

### Database Tables
```sql
-- Extract these tables to SummitFlow
CREATE TABLE projects (              -- NEW: target applications
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  health_endpoint TEXT,
  api_spec_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Migrate existing tables with project_id FK
ALTER TABLE capabilities ADD COLUMN project_id TEXT REFERENCES projects(id);
ALTER TABLE features ADD COLUMN project_id TEXT REFERENCES projects(id);
ALTER TABLE artifacts ADD COLUMN project_id TEXT REFERENCES projects(id);
ALTER TABLE acceptance_criteria -- already scoped via features
ALTER TABLE vision_goals ADD COLUMN project_id TEXT REFERENCES projects(id);

-- Beads remain global (optional project_id)
ALTER TABLE beads ADD COLUMN project_id TEXT REFERENCES projects(id) NULL;
```

---

## Phase 1: SummitFlow Repository Setup & Foundation

### Phase 1.1: Initialize Repository Structure

**Bead**: Create `Phase 1.1: SummitFlow repository setup` with `complexity:small`

- [ ] Create new repository
  ```bash
  mkdir ~/summitflow
  cd ~/summitflow
  git init
  ```

- [ ] Backend structure (FastAPI + Python)
  ```bash
  mkdir -p backend/{app/{api,services,models,tasks,storage,utils},tests,migrations}
  cd backend
  python3.13 -m venv .venv
  source .venv/bin/activate
  ```

- [ ] Create `backend/pyproject.toml`:
  ```toml
  [project]
  name = "summitflow"
  version = "0.1.0"
  dependencies = [
    "fastapi==0.115.0",
    "uvicorn==0.32.0",
    "sqlalchemy==2.0.35",
    "psycopg2-binary==2.9.10",
    "pydantic==2.9.2",
    "celery==5.4.0",
    "redis==5.2.0",
    "structlog==24.4.0",
    "anthropic==0.39.0",
  ]
  ```

- [ ] Frontend structure (Next.js 15 + TypeScript)
  ```bash
  cd ~/summitflow
  npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
  cd frontend
  mkdir -p {app/{projects,terminal,chat,beads,capture},components,lib}
  ```

- [ ] Core documentation
  ```bash
  touch README.md ARCHITECTURE.md CLAUDE.md
  ```

- [ ] Initialize git
  ```bash
  git add .
  git commit -m "feat: Initialize SummitFlow repository structure"
  ```

### Phase 1.2: Database Schema Design

**Bead**: Create `Phase 1.2: SummitFlow database schema` with `complexity:medium,domains:database`

- [ ] Create PostgreSQL database
  ```sql
  CREATE DATABASE summitflow;
  CREATE USER summitflow_user WITH PASSWORD 'summitflow_password';
  GRANT ALL PRIVILEGES ON DATABASE summitflow TO summitflow_user;
  ```

- [ ] Design core tables (migration `001_core_schema.sql`):
  ```sql
  -- Target applications being managed
  CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    base_url TEXT NOT NULL,
    health_endpoint TEXT DEFAULT '/health',
    api_spec_url TEXT,
    repo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Global beads (work items)
  CREATE TABLE beads (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL, -- bug, feature, task, epic, chore
    status TEXT DEFAULT 'open', -- open, in_progress, blocked, closed
    priority INTEGER DEFAULT 2, -- 0=critical, 1=high, 2=medium, 3=low, 4=backlog
    labels TEXT[], -- ['complexity:medium', 'domains:backend']
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
  );

  -- Features (strategic capabilities)
  CREATE TABLE features (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'open', -- open, in_progress, complete, verified
    priority INTEGER DEFAULT 2,
    layers TEXT[], -- ['UI', 'API', 'Backend', 'DB']
    implementation_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ
  );

  -- Acceptance criteria for features
  CREATE TABLE acceptance_criteria (
    id TEXT PRIMARY KEY,
    feature_id TEXT NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    criterion_id TEXT NOT NULL, -- e.g., 'ac-001'
    description TEXT NOT NULL,
    verification_type TEXT NOT NULL, -- api, ui, manual, db
    automatable BOOLEAN DEFAULT false,
    endpoint TEXT, -- For API verification
    expected_response JSONB, -- For automated checks
    status TEXT DEFAULT 'pending', -- pending, passing, failing
    last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Evidence/artifacts (screenshots, logs, metrics)
  CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL, -- screenshot, log, metric, video
    artifact_type TEXT, -- feature_verification, bug_reproduction, debug

    -- Multi-association (evidence can attach to multiple entities)
    feature_id TEXT REFERENCES features(id) ON DELETE SET NULL,
    bead_id TEXT REFERENCES beads(id) ON DELETE SET NULL,
    criterion_id TEXT, -- References acceptance_criteria.id

    file_path TEXT,
    url TEXT,
    metadata JSONB, -- {viewport, browser, duration, etc.}
    description TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    captured_by TEXT DEFAULT 'system' -- system, user, scheduled
  );

  -- Vision goals (strategic alignment)
  CREATE TABLE vision_goals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT, -- business, technical, user_experience
    priority INTEGER DEFAULT 2,
    status TEXT DEFAULT 'active', -- active, achieved, deprecated
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Scheduled AI reviews
  CREATE TABLE ai_reviews (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    review_type TEXT NOT NULL, -- daily_gemini, weekly_claude, on_demand
    model TEXT NOT NULL, -- gemini-2.0-flash-exp, claude-opus-4

    -- Input data
    evidence_ids TEXT[], -- Evidence analyzed
    context_tokens INTEGER,

    -- Output
    findings JSONB, -- Structured findings
    recommendations TEXT,
    beads_created TEXT[], -- Auto-created beads

    status TEXT DEFAULT 'pending', -- pending, running, complete, failed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

  -- Indexes
  CREATE INDEX idx_beads_project ON beads(project_id);
  CREATE INDEX idx_beads_status ON beads(status);
  CREATE INDEX idx_features_project ON features(project_id);
  CREATE INDEX idx_evidence_project ON evidence(project_id);
  CREATE INDEX idx_evidence_feature ON evidence(feature_id);
  CREATE INDEX idx_evidence_bead ON evidence(bead_id);
  ```

- [ ] Create migration system (`backend/app/storage/migrations/runner.py`)
- [ ] Apply initial migration
  ```bash
  cd ~/summitflow/backend
  python -m app.storage.migrations.runner apply
  ```

### Phase 1.3: Project Registration API

**Bead**: Create `Phase 1.3: Project registration API` with `complexity:medium,domains:backend`

- [ ] Create `backend/app/api/projects.py`:
  ```python
  from fastapi import APIRouter, HTTPException
  from pydantic import BaseModel

  router = APIRouter(prefix="/api/projects", tags=["projects"])

  class ProjectCreate(BaseModel):
      name: str
      base_url: str
      health_endpoint: str = "/health"
      api_spec_url: str | None = None
      repo_url: str | None = None

  @router.post("/")
  async def register_project(project: ProjectCreate):
      """Register a new target application."""
      # Generate project ID
      # Call target app's /api/dev/meta endpoint to discover structure
      # Store in database
      # Return project config
      pass

  @router.get("/")
  async def list_projects():
      """List all registered projects."""
      pass

  @router.get("/{project_id}/health")
  async def check_project_health(project_id: str):
      """Poll target app's health endpoint."""
      pass

  @router.get("/{project_id}/meta")
  async def get_project_metadata(project_id: str):
      """Fetch target app's structure from /api/dev/meta."""
      pass
  ```

- [ ] Create Portfolio AI's `/api/dev/meta` endpoint (in portfolio-ai repo):
  ```python
  # backend/app/api/dev.py (NEW FILE in portfolio-ai)
  from fastapi import APIRouter

  router = APIRouter(prefix="/api/dev", tags=["dev"])

  @router.get("/meta")
  async def dev_metadata():
      """Expose application structure for SummitFlow discovery."""
      return {
          "app_name": "Portfolio AI",
          "version": "2.0.0",
          "pages": [
              {"path": "/", "name": "Dashboard"},
              {"path": "/portfolio", "name": "Portfolio"},
              {"path": "/watchlist", "name": "Watchlist"},
              {"path": "/trading", "name": "Trading"},
              {"path": "/backtest", "name": "Backtest"},
              {"path": "/strategies", "name": "Strategies"},
              {"path": "/settings", "name": "Settings"},
          ],
          "api_endpoints": [
              "/api/portfolio",
              "/api/watchlist",
              "/api/market",
              "/api/agents",
              "/api/backtest",
          ],
          "health_check": "/health/dashboard",
          "evidence_hooks": {
              "screenshot_capture": "/api/dev/screenshot-hook",
              "log_export": "/api/dev/logs",
          }
      }
  ```

- [ ] Test project registration flow:
  ```bash
  # Start Portfolio AI (target app)
  cd ~/portfolio-ai
  bash scripts/restart.sh

  # Start SummitFlow
  cd ~/summitflow/backend
  uvicorn app.main:app --port 8001 --reload

  # Register Portfolio AI as first project
  curl -X POST http://localhost:8001/api/projects \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Portfolio AI",
      "base_url": "http://localhost:8000",
      "health_endpoint": "/health/dashboard",
      "api_spec_url": "http://localhost:8000/openapi.json"
    }'
  ```

---

## Phase 2: Extract Backend Components

### Phase 2.1: Copy Capabilities/Features System

**Bead**: Create `Phase 2.1: Extract capabilities/features backend` with `complexity:large,domains:backend`

- [ ] Copy router files:
  ```bash
  cp ~/portfolio-ai/backend/app/api/capabilities/features_router.py \
     ~/summitflow/backend/app/api/features.py

  cp ~/portfolio-ai/backend/app/api/capabilities/capabilities_router.py \
     ~/summitflow/backend/app/api/capabilities.py

  cp ~/portfolio-ai/backend/app/api/capabilities/vision_content_router.py \
     ~/summitflow/backend/app/api/vision_content.py

  cp ~/portfolio-ai/backend/app/api/capabilities/vision_goals_router.py \
     ~/summitflow/backend/app/api/vision_goals.py
  ```

- [ ] Refactor to add `project_id` scoping:
  ```python
  # In features.py - EVERY query must filter by project_id
  @router.get("/{project_id}/features")
  async def list_features(project_id: str, status: str | None = None):
      """List features for a specific project."""
      conn = get_connection_manager()
      query = """
          SELECT * FROM features
          WHERE project_id = %s
      """
      params = [project_id]
      if status:
          query += " AND status = %s"
          params.append(status)
      # Execute query

  @router.post("/{project_id}/features")
  async def create_feature(project_id: str, feature: FeatureCreate):
      """Create feature scoped to project."""
      # Verify project exists
      # Insert with project_id
  ```

- [ ] Update all SQL queries to include `project_id` filtering
- [ ] Update all foreign keys to cascade properly on project deletion
- [ ] Add project existence validation middleware

### Phase 2.2: Extract Service Layer

**Bead**: Create `Phase 2.2: Extract service layer` with `complexity:large,domains:backend`

- [ ] Copy service files:
  ```bash
  cp ~/portfolio-ai/backend/app/services/artifact_manager.py \
     ~/summitflow/backend/app/services/evidence_manager.py

  cp ~/portfolio-ai/backend/app/services/criteria_verifier.py \
     ~/summitflow/backend/app/services/verification_engine.py

  cp ~/portfolio-ai/backend/app/services/capability_feature_scanner.py \
     ~/summitflow/backend/app/services/feature_scanner.py

  cp ~/portfolio-ai/backend/app/services/file_scanner.py \
     ~/summitflow/backend/app/services/codebase_scanner.py
  ```

- [ ] Refactor `evidence_manager.py`:
  - Rename "artifacts" → "evidence"
  - Add `project_id` to all operations
  - Update storage paths: `evidence/{project_id}/{feature_id}/{filename}`
  - Support multi-association (evidence → feature + bead + criterion)

- [ ] Refactor `verification_engine.py`:
  - Accept `project_id` parameter
  - Fetch project metadata (base_url) before verification
  - Make HTTP calls to target app's endpoints
  - Store verification results with project context

- [ ] Refactor `feature_scanner.py`:
  - Scan target app's codebase (via exposed endpoint or git clone)
  - Associate discovered capabilities with project
  - Auto-create features from code analysis

### Phase 2.3: Extract Beads System

**Bead**: Create `Phase 2.3: Extract beads system` with `complexity:medium,domains:backend`

- [ ] Copy beads CLI tool:
  ```bash
  cp -r ~/portfolio-ai/.beads ~/summitflow/.beads
  ```

- [ ] Update beads schema to use PostgreSQL (current: JSONL file):
  ```python
  # ~/summitflow/backend/app/services/beads_service.py
  class BeadsService:
      """PostgreSQL-backed beads system (replaces JSONL)."""

      def create_bead(self, title: str, type: str, priority: int,
                      labels: list[str], project_id: str | None = None) -> str:
          """Create bead in database."""
          # Generate ID
          # Insert into beads table
          # Return bead ID

      def list_beads(self, status: str | None = None,
                     project_id: str | None = None,
                     labels: list[str] | None = None) -> list[dict]:
          """List beads with filtering."""
          # Query database
          # Return results

      def ready_beads(self, project_id: str | None = None) -> list[dict]:
          """Find unblocked work items."""
          # Query beads without blocking dependencies
          # Order by priority

      def update_bead(self, bead_id: str, **updates) -> dict:
          """Update bead fields."""
          # Update database
          # Return updated bead

      def close_bead(self, bead_id: str, reason: str) -> dict:
          """Close a bead."""
          # Set status=closed, closed_at=now
          # Store reason in notes
  ```

- [ ] Create beads API endpoints:
  ```python
  # ~/summitflow/backend/app/api/beads.py
  from fastapi import APIRouter

  router = APIRouter(prefix="/api/beads", tags=["beads"])

  @router.post("/")
  async def create_bead(bead: BeadCreate):
      """Create a new bead."""
      pass

  @router.get("/")
  async def list_beads(
      status: str | None = None,
      project_id: str | None = None,
      labels: str | None = None
  ):
      """List beads with filtering."""
      pass

  @router.get("/ready")
  async def ready_beads(project_id: str | None = None):
      """Find unblocked work."""
      pass

  @router.patch("/{bead_id}")
  async def update_bead(bead_id: str, updates: BeadUpdate):
      """Update bead."""
      pass

  @router.post("/{bead_id}/close")
  async def close_bead(bead_id: str, reason: str):
      """Close bead."""
      pass
  ```

- [ ] Migrate existing beads from JSONL to PostgreSQL:
  ```python
  # Migration script
  import json
  from pathlib import Path

  # Read .beads/issues.jsonl
  beads_file = Path("~/portfolio-ai/.beads/issues.jsonl")

  with beads_file.open() as f:
      for line in f:
          bead = json.loads(line)
          # Insert into SummitFlow database
          # Set project_id = 'portfolio-ai'
  ```

- [ ] Update `bd` CLI to use API instead of JSONL:
  ```bash
  # ~/summitflow/cli/bd
  #!/usr/bin/env python3
  """Beads CLI - talks to SummitFlow API."""

  import requests
  import sys

  SUMMITFLOW_URL = os.getenv("SUMMITFLOW_URL", "http://localhost:8001")

  def create_bead(args):
      response = requests.post(f"{SUMMITFLOW_URL}/api/beads", json={
          "title": args.title,
          "type": args.type,
          "priority": args.priority,
          "labels": args.labels.split(","),
          "project_id": args.project_id,
      })
      print(response.json())

  # ... other commands
  ```

---

## Phase 3: Extract Frontend Components

### Phase 3.1: Multi-Project Dashboard

**Bead**: Create `Phase 3.1: SummitFlow frontend dashboard` with `complexity:large,domains:frontend`

- [ ] Create project list page (`frontend/app/page.tsx`):
  ```tsx
  // SummitFlow home page - list all registered projects
  import { useQuery } from '@tanstack/react-query';

  export default function ProjectsPage() {
    const { data: projects } = useQuery({
      queryKey: ['projects'],
      queryFn: async () => {
        const res = await fetch('http://localhost:8001/api/projects');
        return res.json();
      }
    });

    return (
      <div>
        <h1>SummitFlow - Projects</h1>
        {projects?.map(project => (
          <ProjectCard
            key={project.id}
            name={project.name}
            health={project.health_status}
            features={project.feature_count}
            beads={project.open_beads_count}
          />
        ))}
      </div>
    );
  }
  ```

- [ ] Create project detail page (`frontend/app/projects/[id]/page.tsx`):
  ```tsx
  // Project overview - features, beads, evidence, health
  export default function ProjectDetailPage({ params }: { params: { id: string } }) {
    // Tabs: Features | Beads | Evidence | Vision | Health
  }
  ```

- [ ] Copy capabilities UI from portfolio-ai:
  ```bash
  cp -r ~/portfolio-ai/frontend/app/capabilities/* \
        ~/summitflow/frontend/app/projects/[id]/
  ```

- [ ] Refactor all API calls to include `project_id`:
  ```tsx
  // Before (portfolio-ai)
  const { data: features } = useQuery({
    queryKey: ['features'],
    queryFn: () => fetch('/api/features').then(r => r.json())
  });

  // After (summitflow)
  const { data: features } = useQuery({
    queryKey: ['features', projectId],
    queryFn: () => fetch(`/api/${projectId}/features`).then(r => r.json())
  });
  ```

### Phase 3.2: Web Terminal Integration

**Bead**: Create `Phase 3.2: Claude Code web terminal` with `complexity:medium,domains:frontend`

- [ ] Research Claude Code OAuth integration:
  ```bash
  # Review existing implementation
  grep -r "claude.*oauth" ~/portfolio-ai/frontend/

  # Find SDK usage
  grep -r "anthropic.*sdk" ~/portfolio-ai/backend/
  ```

- [ ] Create terminal page (`frontend/app/terminal/page.tsx`):
  ```tsx
  'use client';

  import { useState } from 'react';
  import { ClaudeTerminal } from '@/components/terminal/ClaudeTerminal';

  export default function TerminalPage() {
    const [sessionId, setSessionId] = useState<string | null>(null);

    return (
      <div className="h-screen flex flex-col">
        <header>
          <h1>SummitFlow Terminal</h1>
          <button onClick={() => initializeSession()}>
            Connect to Claude Code
          </button>
        </header>

        <ClaudeTerminal sessionId={sessionId} />
      </div>
    );
  }
  ```

- [ ] Implement Claude Code connection:
  ```tsx
  // components/terminal/ClaudeTerminal.tsx
  export function ClaudeTerminal({ sessionId }: { sessionId: string | null }) {
    // OAuth flow to authenticate with Claude
    // Establish WebSocket connection
    // Render terminal UI
    // Send commands, receive responses
  }
  ```

- [ ] Add context injection from beads/features:
  ```tsx
  // When user clicks "Debug this bead" button in beads UI
  function debugBead(beadId: string) {
    const bead = await fetch(`/api/beads/${beadId}`).then(r => r.json());

    // Inject context into terminal
    terminal.send({
      type: 'context',
      data: {
        task: bead.title,
        description: bead.description,
        evidence: bead.evidence_ids,
        project: bead.project_id,
      }
    });

    // Navigate to terminal
    router.push('/terminal');
  }
  ```

### Phase 3.3: Chat Interface (Agent SDK)

**Bead**: Create `Phase 3.3: Multi-LLM chat interface` with `complexity:medium,domains:frontend`

- [ ] Create chat page (`frontend/app/chat/page.tsx`):
  ```tsx
  // Multi-LLM chat: Claude, Gemini, Round Table
  export default function ChatPage() {
    const [mode, setMode] = useState<'claude' | 'gemini' | 'roundtable'>('claude');

    return (
      <div>
        <ModelSelector value={mode} onChange={setMode} />
        <ChatInterface mode={mode} />
      </div>
    );
  }
  ```

- [ ] Implement round table mode:
  ```tsx
  // Send same prompt to multiple models, compare responses
  async function roundTableQuery(prompt: string) {
    const responses = await Promise.all([
      queryClaude(prompt),
      queryGemini(prompt),
      queryGPT4(prompt),
    ]);

    return {
      claude: responses[0],
      gemini: responses[1],
      gpt4: responses[2],
      consensus: analyzeConsensus(responses),
    };
  }
  ```

---

## Phase 4: Auto Mode Implementation (Anthropic Patterns)

### Phase 4.1: Long-Running Agent Harness

**Bead**: Create `Phase 4.1: Auto mode agent harness` with `complexity:large,domains:backend`

**Reference**: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

- [ ] Study Anthropic's patterns:
  - Read the full article
  - Understand: Task planning, execution loops, state management, error recovery
  - Review portfolio-ai's existing feature verification patterns

- [ ] Design auto mode architecture:
  ```python
  # backend/app/agents/auto_mode.py

  class AutoModeAgent:
      """Long-running agent for autonomous development tasks.

      Based on Anthropic's effective harness patterns:
      1. Task decomposition (break down complex tasks)
      2. Execution loop (iterate with checkpoints)
      3. State persistence (resume after interruption)
      4. Tool execution (call APIs, run commands, verify)
      5. Error recovery (retry with adjustments)
      """

      def __init__(self, project_id: str, oauth_token: str):
          self.project_id = project_id
          self.claude_client = ClaudeClient(oauth_token=oauth_token)
          self.state = AgentState()

      async def execute_task(self, task_description: str):
          """Execute a development task autonomously."""

          # Phase 1: Planning
          plan = await self.decompose_task(task_description)
          self.state.save_checkpoint('planning', plan)

          # Phase 2: Execution loop
          for step in plan.steps:
              try:
                  result = await self.execute_step(step)
                  self.state.mark_complete(step.id)

                  # Verify step completed correctly
                  verification = await self.verify_step(step, result)
                  if not verification.passed:
                      # Retry with adjustment
                      await self.retry_step(step, verification.issues)

              except Exception as e:
                  # Error recovery
                  await self.handle_error(step, e)

          # Phase 3: Final verification
          final_check = await self.verify_task_complete(task_description)
          return final_check

      async def decompose_task(self, task: str) -> TaskPlan:
          """Use Claude to break down task into steps."""
          response = await self.claude_client.messages.create(
              model="claude-opus-4",
              max_tokens=4096,
              system="""You are a development planning agent.
              Break down the user's task into concrete, verifiable steps.
              Output JSON: {steps: [{id, description, verification_criteria}]}""",
              messages=[{"role": "user", "content": task}]
          )
          return TaskPlan.parse(response.content[0].text)

      async def execute_step(self, step: TaskStep) -> StepResult:
          """Execute a single step using Claude Code."""
          # This is where we call Claude Code SDK with OAuth
          response = await self.claude_client.messages.create(
              model="claude-opus-4",
              max_tokens=8192,
              tools=self.get_available_tools(),
              system="""You are an autonomous coding agent.
              Execute the given step. Use tools to read/write code,
              run tests, and verify your work.""",
              messages=[{
                  "role": "user",
                  "content": f"Execute this step: {step.description}"
              }]
          )

          # Process tool calls
          for block in response.content:
              if block.type == "tool_use":
                  await self.execute_tool(block.name, block.input)

          return StepResult(success=True, output=response)
  ```

- [ ] Implement state persistence:
  ```python
  class AgentState:
      """Persist agent state for resumability."""

      def __init__(self, run_id: str):
          self.run_id = run_id
          self.db = get_connection_manager()

      def save_checkpoint(self, phase: str, data: dict):
          """Save checkpoint to resume from."""
          self.db.execute("""
              INSERT INTO agent_checkpoints
              (run_id, phase, state_data, created_at)
              VALUES (%s, %s, %s, NOW())
          """, [self.run_id, phase, json.dumps(data)])

      def load_latest_checkpoint(self) -> dict | None:
          """Resume from last checkpoint."""
          result = self.db.execute("""
              SELECT phase, state_data FROM agent_checkpoints
              WHERE run_id = %s
              ORDER BY created_at DESC LIMIT 1
          """, [self.run_id])
          return result[0] if result else None

      def mark_complete(self, step_id: str):
          """Mark step as completed."""
          self.db.execute("""
              UPDATE agent_steps SET status = 'complete'
              WHERE run_id = %s AND step_id = %s
          """, [self.run_id, step_id])
  ```

- [ ] Define tools for auto mode:
  ```python
  def get_available_tools(self) -> list[dict]:
      """Tools available to auto mode agent."""
      return [
          {
              "name": "read_file",
              "description": "Read a file from target project",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "path": {"type": "string"},
                      "project_id": {"type": "string"}
                  }
              }
          },
          {
              "name": "write_file",
              "description": "Write to a file in target project",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "path": {"type": "string"},
                      "content": {"type": "string"},
                      "project_id": {"type": "string"}
                  }
              }
          },
          {
              "name": "run_command",
              "description": "Execute shell command in target project",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "command": {"type": "string"},
                      "project_id": {"type": "string"}
                  }
              }
          },
          {
              "name": "create_bead",
              "description": "Create a new work item",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "title": {"type": "string"},
                      "type": {"type": "string"},
                      "description": {"type": "string"}
                  }
              }
          },
          {
              "name": "verify_criterion",
              "description": "Check if acceptance criterion passes",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "feature_id": {"type": "string"},
                      "criterion_id": {"type": "string"}
                  }
              }
          },
          {
              "name": "capture_evidence",
              "description": "Take screenshot or capture logs",
              "input_schema": {
                  "type": "object",
                  "properties": {
                      "type": {"type": "string"},
                      "url": {"type": "string"},
                      "description": {"type": "string"}
                  }
              }
          }
      ]
  ```

### Phase 4.2: OAuth Integration with Claude Code

**Bead**: Create `Phase 4.2: Claude Code OAuth setup` with `complexity:medium,domains:backend`

- [ ] Review existing OAuth implementation:
  ```bash
  grep -r "oauth" ~/portfolio-ai/ | grep -i claude
  ```

- [ ] Set up OAuth credentials:
  ```bash
  # Add to .env
  ANTHROPIC_CLIENT_ID=<from Anthropic Console>
  ANTHROPIC_CLIENT_SECRET=<from Anthropic Console>
  ANTHROPIC_REDIRECT_URI=http://localhost:8001/auth/callback
  ```

- [ ] Implement OAuth flow:
  ```python
  # backend/app/api/auth.py
  from fastapi import APIRouter, HTTPException
  import httpx

  router = APIRouter(prefix="/auth", tags=["auth"])

  @router.get("/login")
  async def oauth_login():
      """Redirect to Anthropic OAuth."""
      auth_url = (
          "https://auth.anthropic.com/oauth/authorize"
          f"?client_id={ANTHROPIC_CLIENT_ID}"
          f"&redirect_uri={ANTHROPIC_REDIRECT_URI}"
          "&response_type=code"
          "&scope=claude_code"
      )
      return {"auth_url": auth_url}

  @router.get("/callback")
  async def oauth_callback(code: str):
      """Handle OAuth callback."""
      async with httpx.AsyncClient() as client:
          response = await client.post(
              "https://auth.anthropic.com/oauth/token",
              data={
                  "grant_type": "authorization_code",
                  "code": code,
                  "client_id": ANTHROPIC_CLIENT_ID,
                  "client_secret": ANTHROPIC_CLIENT_SECRET,
                  "redirect_uri": ANTHROPIC_REDIRECT_URI,
              }
          )

      tokens = response.json()
      # Store access_token, refresh_token in session/database
      return {"access_token": tokens["access_token"]}
  ```

- [ ] Use OAuth token with Claude Code SDK:
  ```python
  from anthropic import Anthropic

  def get_claude_client(oauth_token: str) -> Anthropic:
      """Create Claude client with OAuth token."""
      return Anthropic(
          auth_token=oauth_token,  # Use OAuth token instead of API key
      )
  ```

### Phase 4.3: Auto Mode UI

**Bead**: Create `Phase 4.3: Auto mode UI` with `complexity:medium,domains:frontend`

- [ ] Create auto mode page (`frontend/app/auto/page.tsx`):
  ```tsx
  'use client';

  export default function AutoModePage() {
    const [running, setRunning] = useState(false);
    const [progress, setProgress] = useState<AutoModeProgress | null>(null);

    async function startAutoMode(task: string) {
      setRunning(true);

      // Start auto mode run
      const response = await fetch('/api/auto/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, project_id: 'portfolio-ai' })
      });

      const { run_id } = await response.json();

      // Poll for progress
      const interval = setInterval(async () => {
        const progress = await fetch(`/api/auto/runs/${run_id}`).then(r => r.json());
        setProgress(progress);

        if (progress.status === 'complete' || progress.status === 'failed') {
          clearInterval(interval);
          setRunning(false);
        }
      }, 2000);
    }

    return (
      <div>
        <h1>Auto Mode</h1>
        <p>Autonomous development powered by Claude Code</p>

        {!running ? (
          <div>
            <textarea
              placeholder="Describe what you want to build..."
              onChange={(e) => setTask(e.target.value)}
            />
            <button onClick={() => startAutoMode(task)}>
              Start Auto Mode
            </button>
          </div>
        ) : (
          <div>
            <h2>Running...</h2>
            <ProgressDisplay progress={progress} />
            <LiveLog runId={progress.run_id} />
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] Display real-time progress:
  ```tsx
  function ProgressDisplay({ progress }: { progress: AutoModeProgress }) {
    return (
      <div>
        <h3>Phase: {progress.current_phase}</h3>
        <progress value={progress.completed_steps} max={progress.total_steps} />
        <p>{progress.completed_steps} / {progress.total_steps} steps</p>

        <div>
          <h4>Current Step:</h4>
          <p>{progress.current_step?.description}</p>
        </div>

        <div>
          <h4>Completed:</h4>
          <ul>
            {progress.completed.map(step => (
              <li key={step.id}>✓ {step.description}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
  ```

- [ ] Stream agent logs:
  ```tsx
  function LiveLog({ runId }: { runId: string }) {
    const [logs, setLogs] = useState<string[]>([]);

    useEffect(() => {
      const eventSource = new EventSource(`/api/auto/runs/${runId}/logs`);

      eventSource.onmessage = (event) => {
        const log = JSON.parse(event.data);
        setLogs(prev => [...prev, log.message]);
      };

      return () => eventSource.close();
    }, [runId]);

    return (
      <pre className="bg-black text-green-400 p-4 overflow-auto max-h-96">
        {logs.join('\n')}
      </pre>
    );
  }
  ```

---

## Phase 5: Scheduled AI Review System

### Phase 5.1: Evidence Capture Scheduler

**Bead**: Create `Phase 5.1: Scheduled evidence capture` with `complexity:medium,domains:backend`

- [ ] Create Celery tasks for evidence capture:
  ```python
  # backend/app/tasks/evidence_tasks.py
  from celery import shared_task

  @shared_task(name="capture_project_evidence")
  def capture_project_evidence(project_id: str):
      """Capture evidence for all features in a project."""

      # Get project config
      project = get_project(project_id)

      # Get all features with acceptance criteria
      features = get_features(project_id)

      for feature in features:
          for criterion in feature.acceptance_criteria:
              if criterion.verification_type == 'ui':
                  # Capture screenshot
                  screenshot = capture_screenshot(
                      url=f"{project.base_url}{criterion.page_url}",
                      viewport={'width': 1920, 'height': 1080}
                  )

                  # Store as evidence
                  store_evidence(
                      project_id=project_id,
                      feature_id=feature.id,
                      criterion_id=criterion.id,
                      evidence_type='screenshot',
                      file_path=screenshot.path
                  )

              elif criterion.verification_type == 'api':
                  # Test API endpoint
                  response = test_api_endpoint(
                      url=f"{project.base_url}{criterion.endpoint}",
                      expected=criterion.expected_response
                  )

                  # Store result as evidence
                  store_evidence(
                      project_id=project_id,
                      feature_id=feature.id,
                      criterion_id=criterion.id,
                      evidence_type='api_test',
                      metadata=response.to_dict()
                  )
  ```

- [ ] Configure Celery Beat schedule:
  ```python
  # backend/app/celery_schedules.py
  from celery.schedules import crontab

  beat_schedule = {
      # Capture evidence daily at 2 AM
      'capture-evidence-daily': {
          'task': 'capture_project_evidence',
          'schedule': crontab(hour=2, minute=0),
          'args': ['portfolio-ai'],  # Run for all projects
      },

      # Quick health checks every 15 minutes
      'health-check-projects': {
          'task': 'check_project_health',
          'schedule': crontab(minute='*/15'),
      },
  }
  ```

### Phase 5.2: AI Review Engine (Gemini Long-Context)

**Bead**: Create `Phase 5.2: Gemini scheduled review` with `complexity:large,domains:backend`

- [ ] Install Gemini SDK:
  ```bash
  pip install google-generativeai==0.8.0
  ```

- [ ] Create AI review service:
  ```python
  # backend/app/services/ai_review_service.py
  import google.generativeai as genai
  from datetime import datetime, timedelta

  class AIReviewService:
      """Schedule AI reviews of evidence with long-context models."""

      def __init__(self):
          genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
          self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

      async def daily_review(self, project_id: str):
          """Daily review with Gemini (1-2M token context)."""

          # Gather evidence from last 24 hours
          evidence = self.get_recent_evidence(
              project_id=project_id,
              since=datetime.now() - timedelta(days=1)
          )

          # Get project context
          features = self.get_all_features(project_id)
          beads = self.get_open_beads(project_id)

          # Build massive context (up to 1M tokens)
          context = self.build_review_context(
              evidence=evidence,
              features=features,
              beads=beads,
              project_id=project_id
          )

          # Send to Gemini
          prompt = f"""You are reviewing a software project's development progress.

          PROJECT: {project_id}

          EVIDENCE CAPTURED (last 24 hours):
          {context['evidence_summary']}

          FEATURES (current state):
          {context['features_json']}

          OPEN BEADS (work items):
          {context['beads_json']}

          TASK:
          1. Analyze all evidence - identify issues, regressions, improvements
          2. Review feature completion status - are criteria met?
          3. Suggest new beads for discovered issues
          4. Prioritize existing beads based on impact
          5. Recommend architectural improvements

          Output JSON:
          {{
            "findings": [...],
            "regressions": [...],
            "suggested_beads": [{{title, type, priority, description}}],
            "bead_reprioritization": [{{bead_id, new_priority, reason}}],
            "recommendations": [...]
          }}
          """

          response = self.model.generate_content(prompt)
          review = json.loads(response.text)

          # Store review results
          await self.store_review(project_id, review)

          # Auto-create beads for critical findings
          for bead in review['suggested_beads']:
              if bead['priority'] <= 1:  # P0 or P1
                  await self.create_bead_from_ai(project_id, bead)

          return review

      def build_review_context(self, evidence, features, beads, project_id):
          """Build comprehensive context for AI review."""

          # Include screenshot descriptions (OCR + vision)
          screenshots = []
          for ev in evidence:
              if ev.evidence_type == 'screenshot':
                  vision_analysis = self.analyze_screenshot(ev.file_path)
                  screenshots.append({
                      'url': ev.url,
                      'description': vision_analysis,
                      'captured_at': ev.captured_at,
                  })

          # Serialize features with acceptance criteria
          features_json = json.dumps([{
              'id': f.id,
              'name': f.name,
              'status': f.status,
              'criteria': [{
                  'id': c.id,
                  'description': c.description,
                  'status': c.status,
                  'last_verified': c.last_verified_at,
              } for c in f.acceptance_criteria]
          } for f in features], indent=2)

          # Serialize beads
          beads_json = json.dumps([{
              'id': b.id,
              'title': b.title,
              'priority': b.priority,
              'labels': b.labels,
              'created_at': b.created_at.isoformat(),
          } for b in beads], indent=2)

          return {
              'evidence_summary': screenshots,
              'features_json': features_json,
              'beads_json': beads_json,
          }
  ```

- [ ] Create Celery task:
  ```python
  @shared_task(name="ai_review_daily")
  def ai_review_daily(project_id: str):
      """Daily AI review with Gemini."""
      service = AIReviewService()
      return service.daily_review(project_id)
  ```

- [ ] Add to schedule:
  ```python
  beat_schedule['ai-review-gemini-daily'] = {
      'task': 'ai_review_daily',
      'schedule': crontab(hour=3, minute=0),  # After evidence capture
      'args': ['portfolio-ai'],
  }
  ```

### Phase 5.3: Weekly Claude Deep Review

**Bead**: Create `Phase 5.3: Weekly Claude review` with `complexity:medium,domains:backend`

- [ ] Create weekly review task:
  ```python
  @shared_task(name="ai_review_weekly_claude")
  def ai_review_weekly_claude(project_id: str):
      """Weekly deep review with Claude Opus."""

      # Gather evidence from last 7 days
      evidence = get_recent_evidence(
          project_id=project_id,
          since=datetime.now() - timedelta(days=7)
      )

      # Use Claude Opus for deeper analysis
      client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

      response = client.messages.create(
          model="claude-opus-4",
          max_tokens=8192,
          system="""You are a senior software architect reviewing a project.
          Focus on:
          - Architectural coherence
          - Code quality trends
          - Technical debt accumulation
          - Security concerns
          - Performance bottlenecks
          """,
          messages=[{
              "role": "user",
              "content": f"""Review this project's weekly progress:

              EVIDENCE: {json.dumps(evidence)}

              Provide architectural recommendations."""
          }]
      )

      # Store review
      store_review(project_id, response.content[0].text, model='claude-opus-4')
  ```

- [ ] Schedule weekly:
  ```python
  beat_schedule['ai-review-claude-weekly'] = {
      'task': 'ai_review_weekly_claude',
      'schedule': crontab(day_of_week=1, hour=4, minute=0),  # Monday 4 AM
      'args': ['portfolio-ai'],
  }
  ```

---

## Phase 6: Migrate Portfolio AI to Use SummitFlow

### Phase 6.1: Remove Extracted Code from Portfolio AI

**Bead**: Create `Phase 6.1: Clean up portfolio-ai` with `complexity:medium,domains:backend,domains:frontend`

- [ ] Delete extracted backend code:
  ```bash
  cd ~/portfolio-ai

  # Remove capabilities API
  rm -rf backend/app/api/capabilities/

  # Remove services
  rm backend/app/services/artifact_manager.py
  rm backend/app/services/criteria_verifier.py
  rm backend/app/services/capability_*.py
  rm backend/app/services/file_scanner.py
  rm backend/app/services/sitemap_service.py
  ```

- [ ] Delete extracted frontend code:
  ```bash
  rm -rf frontend/app/capabilities/
  rm -rf frontend/app/dev-assistant/
  ```

- [ ] Keep agent-hub (domain-specific):
  ```bash
  # Keep frontend/app/agent-hub/ - this is investment-specific AI agents
  ```

- [ ] Update imports and remove references

### Phase 6.2: Implement SummitFlow Client in Portfolio AI

**Bead**: Create `Phase 6.2: SummitFlow client library` with `complexity:small,domains:backend`

- [ ] Create client library:
  ```python
  # ~/portfolio-ai/backend/app/clients/summitflow.py
  import httpx

  class SummitFlowClient:
      """Client for interacting with SummitFlow platform."""

      def __init__(self, base_url: str = "http://localhost:8001"):
          self.base_url = base_url
          self.project_id = "portfolio-ai"

      async def capture_evidence(
          self,
          feature_id: str,
          criterion_id: str,
          url: str,
          evidence_type: str = "screenshot"
      ):
          """Trigger evidence capture in SummitFlow."""
          async with httpx.AsyncClient() as client:
              response = await client.post(
                  f"{self.base_url}/api/evidence/capture",
                  json={
                      "project_id": self.project_id,
                      "feature_id": feature_id,
                      "criterion_id": criterion_id,
                      "url": url,
                      "evidence_type": evidence_type,
                  }
              )
              return response.json()

      async def create_bead(
          self,
          title: str,
          type: str,
          priority: int,
          description: str,
          labels: list[str]
      ):
          """Create bead in SummitFlow."""
          async with httpx.AsyncClient() as client:
              response = await client.post(
                  f"{self.base_url}/api/beads",
                  json={
                      "project_id": self.project_id,
                      "title": title,
                      "type": type,
                      "priority": priority,
                      "description": description,
                      "labels": labels,
                  }
              )
              return response.json()
  ```

- [ ] Use in Portfolio AI code:
  ```python
  # Example: Auto-create bead when error occurs
  from app.clients.summitflow import SummitFlowClient

  summitflow = SummitFlowClient()

  async def handle_data_fetch_error(symbol: str, error: str):
      await summitflow.create_bead(
          title=f"Fix: Data fetch failed for {symbol}",
          type="bug",
          priority=2,
          description=f"Error: {error}\n\nLocation: app/sources/yfinance.py",
          labels=["complexity:small", "domains:backend"]
      )
  ```

### Phase 6.3: Update Commands to Call SummitFlow

**Bead**: Create `Phase 6.3: Commands → SummitFlow API` with `complexity:small,domains:backend`

- [ ] Update `.claude/commands/test_it.md`:
  ```markdown
  # /test_it - UI Regression Testing

  Triggers SummitFlow's evidence capture system.

  ## Implementation

  ```bash
  curl -X POST http://localhost:8001/api/evidence/batch-capture \
    -H "Content-Type: application/json" \
    -d '{
      "project_id": "portfolio-ai",
      "capture_type": "full",
      "pages": ["all"]
    }'
  ```
  ```

- [ ] Update `.claude/commands/verify_it.md`:
  ```markdown
  # /verify_it - Feature Verification

  Triggers SummitFlow's verification engine.

  ```bash
  FEATURE_ID=$1
  curl -X POST http://localhost:8001/api/verify/features/$FEATURE_ID \
    -H "Content-Type: application/json" \
    -d '{"project_id": "portfolio-ai"}'
  ```
  ```

- [ ] Update `.claude/commands/audit_it.md`:
  ```markdown
  # /audit_it - Codebase Health Audit

  Triggers SummitFlow's audit system.

  ```bash
  curl -X POST http://localhost:8001/api/audit/run \
    -H "Content-Type: application/json" \
    -d '{
      "project_id": "portfolio-ai",
      "mode": "--quick"
    }'
  ```
  ```

---

## Phase 7: Testing & Documentation

### Phase 7.1: Integration Testing

**Bead**: Create `Phase 7.1: SummitFlow integration tests` with `complexity:medium,domains:backend`

- [ ] Test project registration flow
- [ ] Test evidence capture from Portfolio AI
- [ ] Test bead creation from Portfolio AI errors
- [ ] Test verification engine
- [ ] Test auto mode end-to-end

### Phase 7.2: Documentation

**Bead**: Create `Phase 7.2: SummitFlow documentation` with `complexity:small`

- [ ] Write `~/summitflow/README.md`
- [ ] Write `~/summitflow/ARCHITECTURE.md`
- [ ] Write `~/summitflow/GETTING_STARTED.md`
- [ ] Update `~/portfolio-ai/CLAUDE.md` to reference SummitFlow
- [ ] Document API endpoints
- [ ] Write migration guide for future projects

---

## Production Readiness Verification

- [ ] All functionality implemented and tested
- [ ] Tests passing (pytest tests/)
- [ ] Type checks passing (mypy app/ --strict)
- [ ] Linting passing (ruff check app/ tests/)
- [ ] Code coverage ≥80% for new code
- [ ] Documentation complete
- [ ] Portfolio AI successfully migrated to use SummitFlow
- [ ] Auto mode tested with real tasks
- [ ] Scheduled reviews running successfully
- [ ] All beads closed or transferred
- [ ] Git history clean (proper commits)

---

## Dependencies & Blockers

**External Dependencies:**
- Anthropic OAuth credentials (client_id, client_secret)
- Google AI API key (for Gemini)
- PostgreSQL database access

**Potential Blockers:**
- OAuth flow complexity
- Claude Code SDK API changes
- Evidence capture performance with large projects

---

## Success Criteria

**SummitFlow is production-ready when:**
1. ✅ Manages Portfolio AI development (all beads, features, evidence)
2. ✅ Auto mode can complete a simple feature end-to-end
3. ✅ Scheduled reviews create useful beads
4. ✅ Web terminal provides Claude Code access
5. ✅ Multi-project support works (can add second project)
6. ✅ Portfolio AI codebase reduced by 30%+

**Marketability indicators:**
- Can onboard a new project in <5 minutes
- Auto mode success rate >70% on well-defined tasks
- AI review generates actionable beads (not noise)

---

**Version:** 1.0.0 | **Updated:** 2025-12-16
