# Workflow Visualization Feature

**Feature ID**: FEAT-WORKFLOW-VIZ
**Created**: 2025-12-09
**Status**: Planning
**Effort**: MEDIUM (Phase 1) + LOW (Phase 2)
**Priority**: HIGH

---

## Overview

Implement n8n-inspired workflow visualization for scheduled tasks, automation pipelines, and multi-agent workflows using React Flow. This provides visual understanding of task dependencies, execution flow, and real-time status.

**Key Principle**: This is a **visualization** feature, NOT a workflow builder. We visualize existing Celery schedules and workflows - we don't create new ones visually.

---

## Existing Infrastructure to Reuse (DRY Compliance)

### Backend - Already Built

| Component | Location | What It Provides | Reuse Strategy |
|-----------|----------|------------------|----------------|
| Beat Schedule API | `api/celery_endpoints.py:89-134` | Schedule list with next/last run times | Direct use - extend response |
| Celery Capabilities Table | `migrations/035_celery_capabilities.sql` | `depends_on_tasks`, `populates_tables`, `category` fields | Direct use - already has dependency data |
| CeleryScanner | `services/capability_celery_scanner.py` | Auto-detects task dependencies via code analysis | Run scanner to populate deps |
| Unified Task List | `services/celery_inspector.py:get_unified_task_list()` | Active/pending/completed/failed tasks | Direct use for status overlay |
| SSE Stream | `api/status_stream.py` | Real-time status updates every 2s | Extend for task-specific events |
| Workflow Orchestrator | `agents/workflow_orchestrator.py` | Multi-agent workflow state | Query for workflow graphs |
| Workflow Health | `utils/health_workflows.py` | 24h/7d workflow metrics | Direct use for workflow tab |
| Maintenance Log | `maintenance_log` table | Task execution history | Query for timeline view |

### Frontend - Already Built

| Component | Location | What It Provides | Reuse Strategy |
|-----------|----------|------------------|----------------|
| PageHeader/PageContainer | `components/shared/` | Consistent page layout | Direct use |
| SectionCard | `components/shared/SectionCard.tsx` | Section containers with headers | Direct use for tabs |
| BeatScheduleCard | `components/status/BeatScheduleCard.tsx` | Schedule display logic | Reference patterns |
| CeleryTaskTable | `components/status/CeleryTaskTable.tsx` | Task status display | Reference for status colors |
| WorkflowHealthCard | `components/status/WorkflowHealthCard.tsx` | Workflow health display | Direct use in workflow tab |
| WorkflowMetricsCard | `components/status/WorkflowMetricsCard.tsx` | 7-day workflow metrics | Direct use in workflow tab |
| useStatusStream | `lib/hooks/useStatusStream.ts` | SSE connection + fallback | Direct use for live updates |
| Status API client | `lib/api/celery.ts` | fetchBeatSchedule, fetchCeleryTasks | Extend for graph endpoint |
| Badge variants | `components/ui/badge.tsx` | success/warning/destructive | Direct use for node status |
| Tooltip | `components/ui/tooltip.tsx` | Hover information | Direct use on nodes |

### Data Already Available

```sql
-- celery_capabilities table already has:
SELECT task_name, category, depends_on_tasks, populates_tables,
       last_run_at, next_run_at, success_rate_pct, avg_duration_ms
FROM celery_capabilities;
```

**Categories already defined**: market_data, news, portfolio, analytics, infrastructure, strategy

---

## Architecture

### Data Flow

```
celery_capabilities table (deps already stored)
         │
         ▼
/api/workflows/graph endpoint (NEW - transforms to React Flow format)
         │
         ▼
useWorkflowGraph() hook (NEW)
         │
         ▼
React Flow canvas + useStatusStream() (live status overlay)
```

### Graph Data Model

```typescript
// Backend response from /api/workflows/graph
interface WorkflowGraphResponse {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  categories: string[];      // For tab filtering
  lastUpdated: string;       // ISO timestamp
}

interface WorkflowNode {
  id: string;                // task_name from celery_capabilities
  type: 'task' | 'workflow' | 'agent';
  data: {
    label: string;           // Human-readable name
    schedule: string;        // "02:00 UTC" or "Every 60s"
    category: string;        // market_data, strategy, etc.
    status: 'idle' | 'running' | 'completed' | 'failed' | 'pending';
    lastRun: string | null;  // ISO timestamp
    nextRun: string | null;  // ISO timestamp
    successRate: number;     // 0-100
    avgDuration: number;     // milliseconds
    populatesTables: string[];
  };
  position: { x: number; y: number };  // Auto-calculated by dagre
}

interface WorkflowEdge {
  id: string;
  source: string;            // Source task_name
  target: string;            // Target task_name
  type: 'dependency' | 'data-flow';
  animated?: boolean;        // True when source is running
}
```

---

## Phase 1: Core Visualization (MEDIUM effort)

### 1.1 Backend: Graph API Endpoint

**File**: `backend/app/api/workflow_graph.py` (NEW)

**Endpoint**: `GET /api/workflows/graph`

**Query Parameters**:
- `category`: Filter by category (optional)
- `include_inactive`: Include tasks with 0% success rate (default: false)

**Implementation**:
```python
@router.get("/graph")
async def get_workflow_graph(
    category: str | None = None,
    include_inactive: bool = False,
) -> WorkflowGraphResponse:
    """
    Transform celery_capabilities into React Flow graph format.

    Steps:
    1. Query celery_capabilities with deps + metrics
    2. Query celery_inspector for current task status
    3. Build nodes with status overlay
    4. Build edges from depends_on_tasks
    5. Return React Flow compatible structure
    """
```

**Reuses**:
- `celery_capabilities` table (already has deps)
- `get_unified_task_list()` for live status
- Existing DB connection patterns

### 1.2 Backend: Ensure Dependencies Populated

**File**: `backend/app/services/capability_celery_scanner.py` (EXISTS)

**Task**: Verify `_detect_task_dependencies()` runs during capability scan and populates `depends_on_tasks` field correctly.

**Check**:
```sql
SELECT task_name, depends_on_tasks
FROM celery_capabilities
WHERE depends_on_tasks IS NOT NULL AND depends_on_tasks != '[]'::jsonb;
```

If empty, trigger: `scan-celery-capabilities` task to populate.

### 1.3 Frontend: Install React Flow

**Command**:
```bash
cd ~/portfolio-ai/frontend && npm install @xyflow/react
```

**Note**: Package renamed from `reactflow` to `@xyflow/react` in v12.

### 1.4 Frontend: Workflow Graph Page

**File**: `frontend/app/workflows/page.tsx` (NEW)

**Structure**:
```tsx
export default function WorkflowsPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Workflow Visualization"
        description="Task dependencies and execution flow"
        actions={<RefreshButton />}
      />

      <Tabs defaultValue="data-pipeline">
        <TabsList>
          <TabsTrigger value="data-pipeline">Data Pipeline</TabsTrigger>
          <TabsTrigger value="strategy">Trading Strategy</TabsTrigger>
          <TabsTrigger value="system">System Health</TabsTrigger>
          <TabsTrigger value="agents">Multi-Agent</TabsTrigger>
        </TabsList>

        <TabsContent value="data-pipeline">
          <WorkflowCanvas category="market_data,news" />
        </TabsContent>
        {/* Other tabs */}
      </Tabs>
    </PageContainer>
  );
}
```

**Reuses**:
- PageContainer, PageHeader from `components/shared/`
- Tabs from shadcn/ui

### 1.5 Frontend: Workflow Canvas Component

**File**: `frontend/components/workflows/WorkflowCanvas.tsx` (NEW)

**Features**:
- React Flow canvas with dagre auto-layout
- Custom node component with status badge
- Edge animations when source task running
- Fit-to-view on load

**Implementation**:
```tsx
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react';
import dagre from 'dagre';
import '@xyflow/react/dist/style.css';

interface WorkflowCanvasProps {
  category: string;  // Comma-separated categories to show
}

export function WorkflowCanvas({ category }: WorkflowCanvasProps) {
  const { data, isLoading } = useWorkflowGraph(category);
  const { streamData } = useStatusStream();  // REUSE existing hook

  // Merge live status from SSE into node data
  const nodesWithStatus = useMemo(() =>
    mergeStatusIntoNodes(data?.nodes, streamData?.activeTasks),
    [data, streamData]
  );

  // Auto-layout with dagre
  const { nodes, edges } = useMemo(() =>
    getLayoutedElements(nodesWithStatus, data?.edges),
    [nodesWithStatus, data?.edges]
  );

  return (
    <div className="h-[600px] w-full border rounded-lg">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
```

### 1.6 Frontend: Custom Task Node

**File**: `frontend/components/workflows/TaskNode.tsx` (NEW)

**Design**:
```
┌─────────────────────────────┐
│ ⏰ OHLCV Refresh           │  ← Icon + Label
│ 02:00 UTC                  │  ← Schedule
├─────────────────────────────┤
│ ✓ 98% success  │  ~45s     │  ← Metrics
│ Last: 2h ago   │  Next: 6h │  ← Timing
└─────────────────────────────┘
   │
   ▼ (edge to dependent task)
```

**Status Colors** (reuse from CeleryTaskTable):
- Running: `bg-blue-500 animate-pulse`
- Completed: `bg-green-500`
- Failed: `bg-red-500`
- Pending: `bg-yellow-500`
- Idle: `bg-gray-300`

### 1.7 Frontend: API Hook

**File**: `frontend/lib/hooks/useWorkflowGraph.ts` (NEW)

```typescript
import { useQuery } from '@tanstack/react-query';

export function useWorkflowGraph(category?: string) {
  return useQuery({
    queryKey: ['workflow-graph', category],
    queryFn: () => fetchWorkflowGraph(category),
    staleTime: 30_000,     // 30s - matches other status queries
    gcTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
```

**File**: `frontend/lib/api/workflows.ts` (NEW)

```typescript
export async function fetchWorkflowGraph(category?: string): Promise<WorkflowGraphResponse> {
  const params = new URLSearchParams();
  if (category) params.set('category', category);

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/workflows/graph?${params}`
  );
  return response.json();
}
```

### 1.8 Navigation Link

**File**: `frontend/components/Navigation.tsx` (single file)

Add to `mainLinks` array after Capabilities:
```typescript
{ href: "/workflows", label: "Workflows", icon: GitBranch },
```

Import `GitBranch` from lucide-react.

---

## Phase 2: Enhanced Features (LOW effort)

### 2.1 Click-to-View-Logs on Nodes

**File**: `frontend/components/workflows/TaskNode.tsx` (UPDATE)

**Implementation**:
- Add `onClick` handler to node
- Open slide-over panel with recent logs for that task
- Reuse existing log fetching from `LogsCard.tsx`

```tsx
const handleNodeClick = (taskName: string) => {
  setSelectedTask(taskName);
  setLogsPanelOpen(true);
};
```

**File**: `frontend/components/workflows/TaskLogsPanel.tsx` (NEW)

- Slide-over panel (Sheet from shadcn/ui)
- Filter logs by task name
- Show last 10 executions with duration, status, error if any
- Link to full logs in `/status` page

### 2.2 Mini-Map Enhancement

Already included in Phase 1 via React Flow's `<MiniMap />` component.

**Enhancement**: Color nodes in mini-map by status:
```tsx
<MiniMap
  nodeColor={(node) => {
    switch (node.data.status) {
      case 'running': return '#3b82f6';  // blue
      case 'failed': return '#ef4444';   // red
      case 'completed': return '#22c55e'; // green
      default: return '#d1d5db';          // gray
    }
  }}
/>
```

### 2.3 Execution History Timeline

**File**: `frontend/components/workflows/ExecutionTimeline.tsx` (NEW)

**Data Source**: Query `maintenance_log` table for task execution history.

**Backend Enhancement**: Add endpoint or extend existing:
```
GET /api/workflows/history?task_name={name}&limit=10
```

Can reuse: `get_maintenance_history()` from `maintenance_tracker.py`

**UI**: Horizontal timeline showing last 10 runs:
```
─●───●───●───●───●───●───●───●───●───●─
 ✓   ✓   ✓   ✗   ✓   ✓   ✓   ✓   ✓   ✓
2h  4h  6h  8h  10h 12h 14h 16h 18h 20h ago
```

Click on dot to see details (duration, result, error).

### 2.4 Multi-Agent Workflow Tab

**File**: `frontend/components/workflows/AgentWorkflowView.tsx` (NEW)

**Data Source**: Query `agent_workflows` table via existing health endpoints.

**Shows**:
- Active workflows (from WorkflowOrchestrator)
- Agent nodes with communication edges
- Consensus resolution status
- Recent workflow executions

**Reuses**:
- WorkflowHealthCard (embed or reference)
- WorkflowMetricsCard (embed or reference)
- Workflow health data from `/health/detailed`

---

## File Structure

```
backend/app/
├── api/
│   └── workflow_graph.py          # NEW - Graph endpoint
├── services/
│   └── capability_celery_scanner.py  # EXISTS - verify deps populated

frontend/
├── app/
│   └── workflows/
│       └── page.tsx               # NEW - Main page
├── components/
│   └── workflows/                 # NEW directory
│       ├── WorkflowCanvas.tsx     # React Flow canvas
│       ├── TaskNode.tsx           # Custom node component
│       ├── TaskLogsPanel.tsx      # Phase 2 - logs slide-over
│       ├── ExecutionTimeline.tsx  # Phase 2 - history timeline
│       └── AgentWorkflowView.tsx  # Phase 2 - multi-agent tab
├── lib/
│   ├── api/
│   │   └── workflows.ts           # NEW - API client
│   └── hooks/
│       └── useWorkflowGraph.ts    # NEW - React Query hook
```

---

## Implementation Order

### Phase 1 (Core - Do First)

1. **Verify dependency data** - Check celery_capabilities has deps populated
2. **Backend graph endpoint** - `/api/workflows/graph`
3. **Install React Flow** - `npm install @xyflow/react dagre @types/dagre`
4. **Frontend page + canvas** - Basic visualization working
5. **Custom task node** - Status badges, metrics display
6. **Live status overlay** - Wire up useStatusStream
7. **Navigation link** - Add to main nav
8. **Test all 4 tabs** - Verify each category filters correctly

### Phase 2 (Enhanced - Do Second)

9. **Click-to-logs** - TaskLogsPanel component
10. **Mini-map colors** - Status-based coloring
11. **Execution timeline** - History display component
12. **Multi-agent view** - AgentWorkflowView with workflow state

---

## Testing Checklist

### Phase 1
- [ ] `/api/workflows/graph` returns valid node/edge structure
- [ ] React Flow renders without errors
- [ ] `"use client"` directive present (no SSR errors)
- [ ] Dagre layout produces readable graph (no overlapping nodes)
- [ ] Status badges update via polling (30s interval - SSE doesn't include tasks)
- [ ] Manual refresh button works for immediate status update
- [ ] Edge animations trigger when source task runs
- [ ] Tab filtering shows correct tasks per category
- [ ] Mini-map reflects full graph with status colors
- [ ] Fit-to-view works on load and button click
- [ ] Navigation link appears and works
- [ ] Mobile responsive (graph scrollable on small screens)

### Phase 2
- [ ] Node click opens logs panel (Sheet component)
- [ ] Logs panel shows correct task's history
- [ ] `/api/workflows/history` endpoint works
- [ ] Timeline shows last 10 executions from both tables
- [ ] Timeline click shows execution details (duration, status, error)
- [ ] Multi-agent tab shows workflow state
- [ ] Agent communication edges render correctly
- [ ] WorkflowHealthCard and WorkflowMetricsCard embedded correctly

---

## Dependencies

### NPM Packages (Frontend)
```json
{
  "@xyflow/react": "^12.0.0",
  "dagre": "^0.8.5",
  "@types/dagre": "^0.7.52"
}
```

### Existing (No Install Needed)
- @tanstack/react-query (already installed)
- shadcn/ui components (already installed)
- Tailwind CSS (already configured)

---

## API Contract

### GET /api/workflows/graph

**Request**:
```
GET /api/workflows/graph?category=market_data,news&include_inactive=false
```

**Response**:
```json
{
  "nodes": [
    {
      "id": "refresh-daily-ohlcv",
      "type": "task",
      "data": {
        "label": "Daily OHLCV Refresh",
        "schedule": "02:00 UTC",
        "category": "market_data",
        "status": "completed",
        "lastRun": "2025-12-09T02:00:15Z",
        "nextRun": "2025-12-10T02:00:00Z",
        "successRate": 98,
        "avgDuration": 45000,
        "populatesTables": ["day_bars"]
      },
      "position": { "x": 0, "y": 0 }
    }
  ],
  "edges": [
    {
      "id": "e-ohlcv-indicators",
      "source": "refresh-daily-ohlcv",
      "target": "update-technical-indicators-daily",
      "type": "dependency",
      "animated": false
    }
  ],
  "categories": ["market_data", "news", "strategy", "infrastructure"],
  "lastUpdated": "2025-12-09T14:30:00Z"
}
```

---

## Notes

### Why Not Full n8n-Style Builder?
1. Our workflows are Python code, not visual config
2. Building would require massive refactor to data-driven schedules
3. Visualization provides 90% of value at 10% of cost
4. Can always add builder later if needed

### Performance Considerations
- Graph endpoint should cache for 30s (schedules rarely change)
- SSE overlay updates separately (2s interval)
- Dagre layout calculated client-side (fast for <100 nodes)
- We have ~51 scheduled tasks - well within React Flow limits

### Future Enhancements (Out of Scope)
- Visual workflow builder (edit schedules)
- Export to Mermaid/GraphViz
- Alert configuration per task
- Custom node grouping

---

## Agent-Verified Findings (2025-12-09)

### Environment Compatibility ✅

| Component | Version | Status |
|-----------|---------|--------|
| React | 19.2.0 | ✅ Exceeds React 18+ requirement |
| Next.js | 16.0.0 | ✅ App Router fully supported |
| TypeScript | ^5 | ✅ Strict mode enabled |
| Tailwind CSS | ^4 | ✅ PostCSS v4 configured |

**No conflicting libraries**: react-grid-layout is for dashboards, not graphs.

### Navigation Update (CORRECTED)

**File**: `frontend/components/Navigation.tsx` (NOT `components/navigation/`)

**Add to `mainLinks` array** (lines 23-64):
```typescript
{ href: "/workflows", label: "Workflows", icon: GitBranch },
```

**Import icon** (add to existing lucide-react imports):
```typescript
import { GitBranch } from "lucide-react";
```

### SSE Stream Limitations (IMPORTANT)

**SSE stream does NOT include active task info** due to performance (~4s inspection delay).

**Data available in SSE (`useStatusStream`)**:
- Service status (backend, celery, beat, frontend)
- Database/Redis health checks
- Workflow health summary (24h aggregates only)
- Data source health

**Data NOT in SSE (requires manual fetch)**:
- Active/running tasks (use `fetchCeleryTasks()`)
- Pending tasks
- Individual workflow details

**Implementation Impact**:
- Live status overlay needs polling fallback (~30s) for task status
- Or create new SSE endpoint `/api/workflows/stream` for task-specific updates

### Dependency Detection Limitations

**CeleryScanner (`_detect_task_dependencies()`) detects**:
- `.delay()` calls ✅
- `.apply_async()` calls ✅
- `send_task('task_name')` ✅

**Does NOT detect**:
- Variable aliases (`from x import task as t; t.delay()`)
- Dynamic task names (`send_task(f"refresh_{symbol}")`)
- Celery chain/group/chord operations
- `apply_async(link=callback_task)` patterns

**Mitigation**: Dependencies are ~80% accurate. Critical dependencies may need manual annotation.

### Task History Storage

**Two separate systems**:

| System | Table | Retention | Use Case |
|--------|-------|-----------|----------|
| Maintenance tasks | `maintenance_log` | Indefinite | cleanup, vacuum, validation |
| All Celery tasks | `celery_taskmeta` | 30 days | everything else |

**New endpoint needed for timeline** (Phase 2):
```
GET /api/workflows/history?task_name={name}&limit=10
```

Should query both tables and aggregate results.

### Client Component Pattern

**Must use `"use client"` directive** for React Flow:
```typescript
// frontend/app/workflows/page.tsx
"use client";

import { ReactFlow } from '@xyflow/react';
// ...
```

### Custom Theme Colors Available

React Flow nodes can use existing CSS variables:
```css
--color-primary, --color-accent
--color-gain (green), --color-loss (red)
--viz-0 through --viz-5 (visualization palette)
```

---

## Detailed Implementation Steps

### Step 1: Verify Dependencies Data
```bash
# SSH into server and check if deps are populated
psql -d portfolio -c "SELECT task_name, depends_on_tasks FROM celery_capabilities WHERE depends_on_tasks IS NOT NULL AND depends_on_tasks != '[]'::jsonb LIMIT 5;"
```

If empty, trigger scanner:
```bash
curl -X POST http://localhost:8000/api/capabilities/scan
```

### Step 2: Create Backend Endpoint

**File**: `backend/app/api/workflow_graph.py`

```python
"""Workflow graph API for visualization."""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import get_connection_manager
from app.services.celery_inspector import get_unified_task_list

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class NodeData(BaseModel):
    label: str
    schedule: str
    category: str
    status: str  # idle, running, completed, failed, pending
    lastRun: str | None
    nextRun: str | None
    successRate: int
    avgDuration: int  # milliseconds
    populatesTables: list[str]


class WorkflowNode(BaseModel):
    id: str
    type: str  # task, workflow, agent
    data: NodeData
    position: dict  # {x: 0, y: 0} - calculated client-side


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # dependency, data-flow
    animated: bool = False


class WorkflowGraphResponse(BaseModel):
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    categories: list[str]
    lastUpdated: str


@router.get("/graph", response_model=WorkflowGraphResponse)
async def get_workflow_graph(
    category: str | None = Query(None, description="Comma-separated categories"),
    include_inactive: bool = Query(False, description="Include 0% success rate tasks"),
):
    """Transform celery_capabilities into React Flow graph format."""
    # Implementation here - query celery_capabilities + get active task status
    pass
```

**Register in main.py**:
```python
from app.api.workflow_graph import router as workflow_graph_router
app.include_router(workflow_graph_router)
```

### Step 3: Install Frontend Dependencies

```bash
cd ~/portfolio-ai/frontend
npm install @xyflow/react dagre @types/dagre
```

### Step 4: Create Page and Components

See file structure above. Key files:
1. `frontend/app/workflows/page.tsx` - Main page with tabs
2. `frontend/components/workflows/WorkflowCanvas.tsx` - React Flow canvas
3. `frontend/components/workflows/TaskNode.tsx` - Custom node
4. `frontend/lib/api/workflows.ts` - API client
5. `frontend/lib/hooks/useWorkflowGraph.ts` - React Query hook

### Step 5: Add Navigation Link

**File**: `frontend/components/Navigation.tsx`

```diff
+ import { GitBranch } from "lucide-react";

const mainLinks = [
  // ... existing links
  { href: "/capabilities", label: "Capabilities", icon: Database },
+ { href: "/workflows", label: "Workflows", icon: GitBranch },
];
```

### Step 6: Test and Verify

```bash
# Backend test
curl http://localhost:8000/api/workflows/graph | jq '.nodes | length'

# Frontend test (use network IP)
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
  http://192.168.8.233:3000/workflows /tmp/workflows.png
```
