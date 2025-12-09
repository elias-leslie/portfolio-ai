# Workflow Visualization Feature

**Feature ID**: FEAT-WORKFLOW-VIZ
**Created**: 2025-12-09
**Status**: Phase 1.5 Complete + UI Fixes, Phase 2 Pending
**Effort**: MEDIUM (Phase 1) + MEDIUM (Phase 1.5) + LOW (Phase 2)
**Priority**: HIGH
**Phase 1 Commit**: 3558b40
**Phase 1.5 Commit**: 244d432
**UI Fixes Commit**: 529c5ba

---

## Current State (as of 529c5ba)

### What's Working
- **Unified "All Tasks" view** - Default tab shows all 57 tasks with 9 dependency edges
- **Dark mode support** - Task nodes properly styled for dark theme
- **Dependency inference** - Edges inferred from table writes→reads relationships
- **Manual overrides** - PATCH endpoint for adding/removing dependencies
- **Category filters** - Optional tabs for Data Pipeline, Strategy, System views

### Known Issues to Address in Next Session
1. **Zoom level** - With 57 nodes, fitView zooms out significantly making nodes small
2. **More edges needed** - Only 9 edges currently; need more seed dependencies
3. **Edge visibility** - Edges hard to see when nodes are spread out
4. **No click-to-details** - Phase 2 feature (logs panel on node click)

---

## Overview

Implement n8n-inspired workflow visualization for scheduled tasks, automation pipelines, and multi-agent workflows using React Flow. This provides visual understanding of task dependencies, execution flow, and real-time status.

**Key Principle**: This is a **visualization** feature, NOT a workflow builder. We visualize existing Celery schedules and workflows - we don't create new ones visually.

**Critical Insight (discovered during Phase 1)**: The original approach assumed `depends_on_tasks` would be auto-populated via code analysis. This failed because:
1. Beat schedule uses short task names (e.g., `refresh_watchlist_scores`) not full module paths
2. Scanner's regex can't find source files without full paths
3. Most dependencies are **implicit** (timing + data flow), not explicit code calls

**Solution**: Infer dependencies from table relationships (writes → reads) + timing order, with manual overrides for edge cases.

---

## Existing Infrastructure to Reuse (DRY Compliance)

### Backend - Already Built

| Component | Location | What It Provides | Reuse Strategy |
|-----------|----------|------------------|----------------|
| Beat Schedule API | `api/celery_endpoints.py:144-223` | Schedule list (note: last_run/next_run are NULL) | Use celery_capabilities table for timing data instead |
| Celery Capabilities Table | `migrations/035_celery_capabilities.sql` | `depends_on_tasks`, `populates_tables`, `category` fields | Direct use - already has dependency data |
| CeleryScanner | `services/capability_celery_scanner.py` | Auto-detects task dependencies via code analysis | Run scanner to populate deps |
| Unified Task List | `services/celery_inspector.py:get_unified_task_list()` | Active/pending/completed/failed tasks | Direct use for status overlay |
| SSE Stream | `api/status_stream.py` | Real-time status updates every 2s (excludes task status for performance) | Use polling via fetchCeleryTasks() for task status |
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

**Categories currently defined**: market_data, news, portfolio, analytics, infrastructure

**Note**: "strategy" category needs to be added to `backend/app/config/capabilities_config.yaml`. There are ~7 strategy-related scheduled tasks (out of 62 total) that would benefit from this category:
- evaluate-strategy-performance
- auto-promote-strategies
- weekly-strategy-generation
- weekly-strategy-evolution
- daily-strategy-refresh
- generate-daily-strategy-signals
- auto-paper-trade-from-signals

Add patterns: `["strategy", "backtest", "trade_signal"]`

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

## Phase 1.5: Intelligent Dependency Detection (MEDIUM effort)

**Goal**: Make workflow visualization show accurate dependencies by inferring them from table relationships and timing, with automatic auditing and manual overrides.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Dependency Resolution Flow                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  CeleryScanner                                                       │
│  ├── _detect_populates_tables() ──► populates_tables (existing)     │
│  └── _detect_reads_from_tables() ──► reads_from_tables (NEW)        │
│                                                                      │
│  Graph Endpoint                                                      │
│  ├── Infer edges: If Task B reads table X AND Task A writes X       │
│  │                AND Task A runs before Task B → Edge A→B          │
│  ├── Apply overrides: dependency_overrides.add/remove               │
│  └── Return final edges                                              │
│                                                                      │
│  /audit_it (enhanced)                                                │
│  ├── Detect timing violations (reader before writer)                │
│  ├── Detect orphaned tasks (no reads, no writes, no deps)          │
│  ├── Suggest missing dependencies                                    │
│  └── Auto-apply dependency_overrides                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.5.1 Database Migration: Add New Columns

**File**: `backend/migrations/XXX_celery_reads_and_overrides.sql` (NEW)

```sql
-- Add reads_from_tables column (auto-detected by scanner)
ALTER TABLE celery_capabilities
ADD COLUMN IF NOT EXISTS reads_from_tables JSONB DEFAULT '[]'::jsonb;

-- Add dependency_overrides column (manual corrections)
-- Structure: {"add": ["task_a"], "remove": ["task_b"], "reason": "..."}
ALTER TABLE celery_capabilities
ADD COLUMN IF NOT EXISTS dependency_overrides JSONB DEFAULT '{}'::jsonb;

-- Add index for dependency queries
CREATE INDEX IF NOT EXISTS idx_celery_capabilities_reads
ON celery_capabilities USING GIN (reads_from_tables);

COMMENT ON COLUMN celery_capabilities.reads_from_tables IS
'Tables this task reads from (auto-detected via SQL SELECT/JOIN patterns)';

COMMENT ON COLUMN celery_capabilities.dependency_overrides IS
'Manual dependency corrections: {add: [], remove: [], reason: ""}';
```

### 1.5.2 Enhance CeleryScanner: Detect Table Reads

**File**: `backend/app/services/capability_celery_scanner.py` (UPDATE)

**Add method** `_detect_reads_from_tables(task_path: str) -> list[str]`:

```python
def _detect_reads_from_tables(self, task_path: str) -> list[str]:
    """Detect tables this task reads from via SQL patterns.

    Searches for patterns like:
    - SELECT ... FROM table_name
    - JOIN table_name
    - FROM table_name (in subqueries)

    Returns:
        Sorted list of table names read by this task
    """
    try:
        # Convert import path to file path (same as _detect_populates_tables)
        path_parts = task_path.split(".")
        if len(path_parts) < 2:
            return []

        module_parts = path_parts[:-1]
        file_path = Path(__file__).parent.parent / "/".join(module_parts[1:])
        file_path = file_path.with_suffix(".py")

        if not file_path.exists():
            return []

        content = file_path.read_text()
        tables = set()

        # Pattern 1: SELECT ... FROM table
        # Handles: FROM table, FROM schema.table
        from_pattern = r"FROM\s+([a-z_][a-z0-9_]*)"

        # Pattern 2: JOIN table (LEFT, RIGHT, INNER, OUTER, etc.)
        join_pattern = r"JOIN\s+([a-z_][a-z0-9_]*)"

        # Pattern 3: Table in parentheses (subqueries, EXISTS)
        # e.g., EXISTS (SELECT 1 FROM table WHERE...)

        for match in re.finditer(from_pattern, content, re.IGNORECASE):
            table = match.group(1).lower()
            # Filter out SQL keywords that might match
            if table not in ["select", "where", "and", "or", "not", "null",
                            "true", "false", "dual", "information_schema"]:
                tables.add(table)

        for match in re.finditer(join_pattern, content, re.IGNORECASE):
            table = match.group(1).lower()
            if table not in ["select", "where", "and", "or", "lateral"]:
                tables.add(table)

        # Remove tables that this task writes to (self-references)
        writes = set(self._detect_populates_tables(task_path))
        reads_only = tables - writes

        return sorted(reads_only)

    except Exception as e:
        logger.debug("failed_to_detect_reads_from_tables", task=task_path, error=str(e))
        return []
```

**Update `_scan_single_task()`** to include `reads_from_tables`:

```python
# Around line 137, after depends_on_tasks detection:
reads_from_tables = self._detect_reads_from_tables(task_path)

# Add to return dict around line 165:
return {
    ...
    "reads_from_tables": reads_from_tables,
    ...
}
```

**Update `save_capabilities()`** UPSERT to include new column.

### 1.5.3 Update Graph Endpoint: Infer Dependencies

**File**: `backend/app/api/workflow_graph.py` (UPDATE)

**Add dependency inference function**:

```python
def _infer_dependencies(
    tasks: list[dict],
) -> list[tuple[str, str, str]]:
    """Infer task dependencies from table relationships and timing.

    Rules:
    1. If Task B reads_from table X AND Task A populates table X
       AND Task A scheduled before Task B → A depends on B (A→B edge)
    2. Apply dependency_overrides (add/remove)

    Returns:
        List of (source_task, target_task, reason) tuples
    """
    edges = []

    # Build lookup maps
    writers = {}  # table -> [(task_name, schedule_time)]
    for task in tasks:
        for table in task.get("populates_tables", []):
            if table not in writers:
                writers[table] = []
            writers[table].append((
                task["task_name"],
                _parse_schedule_time(task.get("schedule_crontab"),
                                    task.get("schedule_interval_seconds"))
            ))

    # Find dependencies based on reads
    for task in tasks:
        task_name = task["task_name"]
        task_time = _parse_schedule_time(
            task.get("schedule_crontab"),
            task.get("schedule_interval_seconds")
        )

        for table in task.get("reads_from_tables", []):
            if table in writers:
                for writer_name, writer_time in writers[table]:
                    # Skip self-references
                    if writer_name == task_name:
                        continue
                    # Check timing (writer should run before reader)
                    if writer_time is not None and task_time is not None:
                        if writer_time < task_time:
                            edges.append((
                                writer_name,
                                task_name,
                                f"writes→reads: {table}"
                            ))

        # Apply manual overrides
        overrides = task.get("dependency_overrides", {})
        for dep in overrides.get("add", []):
            edges.append((dep, task_name, f"manual: {overrides.get('reason', 'override')}"))
        # Remove edges will be filtered later

    # Deduplicate
    seen = set()
    unique_edges = []
    for source, target, reason in edges:
        key = (source, target)
        if key not in seen:
            seen.add(key)
            unique_edges.append((source, target, reason))

    return unique_edges


def _parse_schedule_time(crontab: str | None, interval_seconds: int | None) -> int | None:
    """Convert schedule to minutes-from-midnight for comparison.

    Returns None for interval-based schedules (can't determine order).
    """
    if crontab:
        parts = crontab.split()
        if len(parts) >= 2:
            try:
                minute = int(parts[0]) if parts[0] != "*" else 0
                hour = int(parts[1]) if parts[1] != "*" else 0
                return hour * 60 + minute
            except ValueError:
                pass
    return None
```

**Update `get_workflow_graph()` to use inferred dependencies**:

```python
# After querying tasks, before building edges:
inferred_deps = _infer_dependencies(tasks_data)

# Build edges from inferred dependencies
for source, target, reason in inferred_deps:
    # Check if edge should be removed by override
    target_task = next((t for t in tasks_data if t["task_name"] == target), None)
    if target_task:
        removes = target_task.get("dependency_overrides", {}).get("remove", [])
        if source in removes:
            continue  # Skip this edge

    edge = WorkflowEdge(
        id=f"e-{source}-{target}",
        source=source,
        target=target,
        type="data-flow",
        animated=source in active_tasks,
    )
    edges.append(edge)
```

### 1.5.4 Enhance /audit_it: Dependency Auditing

**File**: `.claude/commands/audit_it.md` (UPDATE)

**Add new audit phase** (insert after Phase 1.7, before Phase 2):

```markdown
### Phase 1.8: Dependency Audit (NEW)

**Purpose**: Verify task dependencies are accurate and auto-correct issues.

**Trigger capability scan first**:
```bash
curl -X POST http://localhost:8000/api/capabilities/scan
```

**Checks to perform**:

1. **Timing Violations**: Reader runs before writer
   ```sql
   -- Find tasks that read from tables written by tasks that run LATER
   SELECT
       r.task_name as reader,
       w.task_name as writer,
       t.table_name,
       r.schedule_crontab as reader_schedule,
       w.schedule_crontab as writer_schedule
   FROM celery_capabilities r
   CROSS JOIN LATERAL jsonb_array_elements_text(r.reads_from_tables) as t(table_name)
   JOIN celery_capabilities w ON w.populates_tables ? t.table_name
   WHERE r.task_name != w.task_name
   -- Compare schedules (simplified - real impl needs time parsing)
   ```

2. **Orphaned Tasks**: No reads, no writes, no dependencies
   ```sql
   SELECT task_name
   FROM celery_capabilities
   WHERE (populates_tables = '[]' OR populates_tables IS NULL)
     AND (reads_from_tables = '[]' OR reads_from_tables IS NULL)
     AND (depends_on_tasks = '[]' OR depends_on_tasks IS NULL);
   ```

3. **Missing Dependencies**: Task reads from table but no writer exists
   ```sql
   SELECT r.task_name, t.table_name as reads_from
   FROM celery_capabilities r
   CROSS JOIN LATERAL jsonb_array_elements_text(r.reads_from_tables) as t(table_name)
   WHERE NOT EXISTS (
       SELECT 1 FROM celery_capabilities w
       WHERE w.populates_tables ? t.table_name
   );
   ```

**Auto-correction actions**:

For timing violations:
```bash
# Add override to move dependency
curl -X PATCH "http://localhost:8000/api/capabilities/celery/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "dependency_overrides": {
      "remove": ["incorrectly_inferred_task"],
      "reason": "Timing violation: reader runs at 02:00, writer at 04:00"
    }
  }'
```

For missing known dependencies (from system knowledge):
```bash
# Add manual dependency
curl -X PATCH "http://localhost:8000/api/capabilities/celery/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "dependency_overrides": {
      "add": ["known_dependency_task"],
      "reason": "Manual: reads Redis cache populated by this task"
    }
  }'
```

**Known dependencies to seed** (from system exploration):
| Reader Task | Writer Task | Relationship |
|-------------|-------------|--------------|
| backfill_technical_indicators | refresh_daily_ohlcv | reads day_bars |
| backfill_technical_indicators | refresh_watchlist_ohlcv | reads day_bars |
| populate_fear_greed_inputs | backfill_technical_indicators | reads technical_indicators |
| calculate_fear_greed | populate_fear_greed_inputs | reads fear_greed_inputs |
| run_discovery_agent | calculate_fear_greed | runs after data ready |
| run_portfolio_analyzer | calculate_fear_greed | runs after data ready |
| generate_daily_strategy_signals | refresh_daily_ohlcv | reads day_bars |
| auto_paper_trade_from_signals | generate_daily_strategy_signals | reads strategy_signals |
| parse_valuation_metrics | refresh_yfinance_reference_data | reads reference_cache |
| refresh_alphavantage_reference_backup | parse_valuation_metrics | runs after parse |

**Output**: Report of issues found, corrections applied, remaining manual review items.
```

### 1.5.5 Add API Endpoint for Dependency Overrides

**File**: `backend/app/api/workflow_graph.py` (UPDATE)

**Add PATCH endpoint**:

```python
@router.patch("/tasks/{task_name}/dependencies")
async def update_task_dependencies(
    task_name: str,
    overrides: DependencyOverrideRequest,
) -> dict:
    """Update dependency overrides for a task.

    Used by /audit_it to auto-correct dependency issues.
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # Merge with existing overrides
        result = conn.execute(
            """
            UPDATE celery_capabilities
            SET dependency_overrides = dependency_overrides || %s::jsonb,
                updated_at = NOW()
            WHERE task_name = %s
            RETURNING id
            """,
            [json.dumps(overrides.model_dump()), task_name]
        )

        if result.rowcount == 0:
            raise HTTPException(404, f"Task {task_name} not found")

    return {"status": "updated", "task_name": task_name}


class DependencyOverrideRequest(BaseModel):
    add: list[str] = []
    remove: list[str] = []
    reason: str
```

### 1.5.6 Seed Initial Dependencies

**File**: `backend/migrations/XXX_seed_workflow_dependencies.sql` (NEW)

Based on the comprehensive system exploration, seed known dependencies:

```sql
-- Seed known dependencies that can't be auto-detected
-- These are based on timing order and data flow analysis

-- Technical indicators depend on OHLCV data
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-daily-ohlcv', 'refresh-watchlist-ohlcv'),
    'reason', 'Timing: runs at 02:30, needs day_bars from 02:00/02:15'
)
WHERE task_name = 'backfill-technical-indicators';

-- Fear & Greed inputs depend on technical indicators
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('backfill-technical-indicators'),
    'reason', 'Timing: runs at 02:45, needs technical_indicators from 02:30'
)
WHERE task_name = 'populate-fear-greed-inputs';

-- Fear & Greed calculation depends on inputs
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('populate-fear-greed-inputs'),
    'reason', 'Timing: runs at 03:00, needs fear_greed_inputs from 02:45'
)
WHERE task_name = 'calculate-fear-greed';

-- Agents depend on all data being ready
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('calculate-fear-greed', 'scan-system-capabilities'),
    'reason', 'Timing: runs at 03:30, after all data refresh complete'
)
WHERE task_name IN ('run-discovery-agent', 'run-portfolio-analyzer');

-- Strategy signals depend on market data
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-daily-ohlcv'),
    'reason', 'Timing: runs at 21:30, needs current day_bars'
)
WHERE task_name = 'generate-daily-strategy-signals';

-- Paper trades depend on signals
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('generate-daily-strategy-signals'),
    'reason', 'Timing: runs at 21:45, needs strategy_signals from 21:30'
)
WHERE task_name = 'auto-paper-trade-from-signals';

-- Valuation parsing depends on yfinance fetch
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('refresh-yfinance-reference-data'),
    'reason', 'Timing: runs at 04:30, needs reference_cache from 04:00'
)
WHERE task_name = 'parse-valuation-metrics';

-- Alpha Vantage backup depends on parsing (to know what's missing)
UPDATE celery_capabilities
SET dependency_overrides = jsonb_build_object(
    'add', jsonb_build_array('parse-valuation-metrics'),
    'reason', 'Timing: runs at 04:45, fills gaps identified by 04:30 parse'
)
WHERE task_name = 'refresh-alphavantage-reference-backup';
```

### 1.5.7 Testing Checklist

- [x] Migration applies cleanly
- [x] `reads_from_tables` populated after scan
- [x] Dependencies inferred correctly in graph endpoint
- [x] Overrides apply (add/remove work)
- [x] Visualization shows proper edges
- [ ] `/audit_it` detects timing violations (deferred to Phase 1.8)
- [ ] `/audit_it` auto-applies corrections (deferred to Phase 1.8)
- [x] Seeded dependencies appear in visualization

### 1.5.8 Feature Registry & Vision Goals

**After Phase 1.5 implementation is complete**, register the feature and link to vision goals.

#### Create Feature Entry

```bash
curl -s -X POST 'http://localhost:8000/api/capabilities/features/' \
  -H "Content-Type: application/json" \
  -d '{
    "feature_id": "FEAT-WORKFLOW-VIZ",
    "name": "Workflow Visualization",
    "description": "n8n-inspired visualization of scheduled tasks, automation pipelines, and multi-agent workflows using React Flow with intelligent dependency detection",
    "category": "Architecture - Observability",
    "status": "in_progress",
    "effort": "medium",
    "priority": "high",
    "layers": ["Frontend", "Backend", "API", "DB"]
  }'
```

#### Link Vision Goals

This feature supports multiple vision goals:

| Vision Goal | Code | Why It Applies |
|-------------|------|----------------|
| Autonomous Operation | VG-AUTO | Visualizes autonomous agent workflows and task orchestration |
| Transparency Over Black Boxes | VG-TRANS | Makes task dependencies and execution flow visible and reviewable |
| Reliability Through Redundancy | VG-RELY | Shows data pipeline health, identifies broken dependencies |
| Developer Velocity | VG-DEV | Helps developers understand and debug task scheduling |

```bash
curl -s -X PATCH 'http://localhost:8000/api/capabilities/features/FEAT-WORKFLOW-VIZ/vision-goals' \
  -H "Content-Type: application/json" \
  -d '{"vision_goals": ["VG-AUTO", "VG-TRANS", "VG-RELY", "VG-DEV"]}'
```

#### Add Acceptance Criteria

```bash
# Phase 1 criteria (completed)
curl -s -X PATCH 'http://localhost:8000/api/capabilities/features/FEAT-WORKFLOW-VIZ/acceptance-criteria' \
  -H "Content-Type: application/json" \
  -d '{
    "acceptance_criteria": [
      {"id": "ac-001", "criterion": "Workflow page loads at /workflows", "type": "ui", "passed": true},
      {"id": "ac-002", "criterion": "React Flow canvas renders task nodes", "type": "ui", "passed": true},
      {"id": "ac-003", "criterion": "4 tabs filter by category (Data Pipeline, Strategy, System, Multi-Agent)", "type": "ui", "passed": true},
      {"id": "ac-004", "criterion": "/api/workflows/graph returns nodes with status, metrics, schedule", "type": "api", "passed": true},
      {"id": "ac-005", "criterion": "MiniMap and Controls render", "type": "ui", "passed": true},
      {"id": "ac-006", "criterion": "Navigation link appears in sidebar", "type": "ui", "passed": true}
    ]
  }'

# Phase 1.5 criteria (pending)
curl -s -X PATCH 'http://localhost:8000/api/capabilities/features/FEAT-WORKFLOW-VIZ/acceptance-criteria' \
  -H "Content-Type: application/json" \
  -d '{
    "acceptance_criteria": [
      {"id": "ac-007", "criterion": "reads_from_tables column populated by scanner", "type": "backend", "passed": null},
      {"id": "ac-008", "criterion": "Dependencies inferred from table writes→reads", "type": "api", "passed": null},
      {"id": "ac-009", "criterion": "dependency_overrides add/remove works via API", "type": "api", "passed": null},
      {"id": "ac-010", "criterion": "Visualization shows edges between dependent tasks", "type": "ui", "passed": null},
      {"id": "ac-011", "criterion": "/audit_it detects and auto-corrects timing violations", "type": "backend", "passed": null},
      {"id": "ac-012", "criterion": "Seeded dependencies appear correctly in graph", "type": "ui", "passed": null}
    ]
  }'
```

#### Add Subtasks

```bash
# Phase 1.5 subtasks
for task in \
  '{"task_id": "1.5.1", "description": "Create migration for reads_from_tables and dependency_overrides columns", "effort": "low"}' \
  '{"task_id": "1.5.2", "description": "Add _detect_reads_from_tables() to CeleryScanner", "effort": "medium"}' \
  '{"task_id": "1.5.3", "description": "Update graph endpoint with dependency inference logic", "effort": "medium"}' \
  '{"task_id": "1.5.4", "description": "Add Phase 1.8 (Dependency Audit) to /audit_it command", "effort": "medium"}' \
  '{"task_id": "1.5.5", "description": "Add PATCH endpoint for dependency overrides", "effort": "low"}' \
  '{"task_id": "1.5.6", "description": "Create seed migration for known dependencies", "effort": "low"}' \
  '{"task_id": "1.5.7", "description": "Test and verify visualization shows accurate workflow", "effort": "medium"}'
do
  curl -s -X POST 'http://localhost:8000/api/capabilities/features/FEAT-WORKFLOW-VIZ/tasks' \
    -H "Content-Type: application/json" \
    -d "$task"
done
```

#### Verify Registration

```bash
# Check feature was created with all data
curl -s 'http://localhost:8000/api/capabilities/features/FEAT-WORKFLOW-VIZ' | jq '{
  feature_id,
  name,
  status,
  layers: .layers | length,
  vision_goals: .vision_goals | length,
  criteria: .acceptance_criteria | length,
  tasks: .tasks | length,
  passes
}'
```

**Expected output:**
```json
{
  "feature_id": "FEAT-WORKFLOW-VIZ",
  "name": "Workflow Visualization",
  "status": "in_progress",
  "layers": 4,
  "vision_goals": 4,
  "criteria": 12,
  "tasks": 7,
  "passes": null
}
```

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

## Agent Orchestration Strategy

This feature requires careful orchestration between Opus (main), Task agents, and Explore agents. Each task is assigned to the optimal executor based on complexity, criticality, and required knowledge.

### Agent Assignment Legend

| Agent | Use For | Token Budget |
|-------|---------|--------------|
| **Opus (Main)** | Critical decisions, complex integrations, code review, final verification | Unlimited |
| **Task (Sonnet)** | Standard implementation, boilerplate, straightforward coding | Normal |
| **Task (Haiku)** | Simple edits, config changes, file creation from templates | Minimal |
| **Explore (Very Thorough)** | Deep codebase analysis, pattern discovery, dependency mapping | High |
| **Explore (Quick)** | File location, simple lookups | Low |

---

## Execution Plan with Agent Assignments

### Pre-Flight (Opus Main)

Before starting, Opus should:
1. Read this entire task file
2. Verify services are running (`bash ~/portfolio-ai/scripts/status.sh`)
3. Create checkpoint commit (`git add -A && git commit -m "checkpoint: before workflow-viz"`)

---

### Phase 1A: Backend Foundation

#### Task 1.1: Add Strategy Category
**Agent**: Task (Haiku)
**Criticality**: Low
**Prompt**:
```
Edit backend/app/config/capabilities_config.yaml to add a "strategy" category after "infrastructure" (around line 108).

Add:
  strategy:
    patterns:
      - "strategy"
      - "backtest"
      - "trade_signal"

Then verify the change with: cat backend/app/config/capabilities_config.yaml | grep -A5 "strategy:"
```

#### Task 1.2: Verify/Trigger Capabilities Scan
**Agent**: Opus (Main)
**Criticality**: High (data dependency)
**Why Opus**: Needs to interpret results and decide if manual intervention needed
**Actions**:
1. `curl -X POST http://localhost:8000/api/capabilities/scan`
2. Wait 30s for scan to complete
3. Verify: `curl http://localhost:8000/api/capabilities?type=celery | jq '.items | length'`
4. Check deps populated: `curl http://localhost:8000/api/capabilities?type=celery | jq '[.items[] | select(.depends_on_tasks != null and .depends_on_tasks != [])] | length'`

#### Task 1.3: Create Backend Graph Endpoint
**Agent**: Task (Sonnet)
**Criticality**: High
**Prompt**:
```
Create the workflow graph API endpoint. This is the core backend for visualization.

**File to create**: backend/app/api/workflow_graph.py

**Requirements**:
1. Router with prefix="/api/workflows", tags=["workflows"]
2. GET /graph endpoint that:
   - Queries celery_capabilities table for all tasks
   - Filters by category if provided (comma-separated)
   - Filters out 0% success rate unless include_inactive=true
   - Builds nodes with: id, type="task", data (label, schedule, category, status, lastRun, nextRun, successRate, avgDuration, populatesTables), position={x:0, y:0}
   - Builds edges from depends_on_tasks field
   - Overlays live status from get_unified_task_list()
   - Returns WorkflowGraphResponse

**Imports needed**:
- from app.storage.connection import ConnectionManager
- from app.services.celery_inspector import get_unified_task_list
- from datetime import datetime

**Reference files**:
- backend/app/api/capabilities/capabilities_router.py (query patterns)
- backend/app/services/celery_inspector.py:336-412 (get_unified_task_list)

**Response models** (define with Pydantic):
- NodeData: label, schedule, category, status, lastRun, nextRun, successRate, avgDuration, populatesTables
- WorkflowNode: id, type, data, position
- WorkflowEdge: id, source, target, type, animated
- WorkflowGraphResponse: nodes, edges, categories, lastUpdated

Make sure to handle:
- JSON parsing of depends_on_tasks (it's JSONB)
- NULL values for optional fields
- Status mapping: active tasks → "running", completed → "completed", failed → "failed", else → "idle"
```

#### Task 1.4: Register Router in main.py
**Agent**: Task (Haiku)
**Criticality**: Low
**Prompt**:
```
Register the workflow_graph router in backend/app/main.py:

1. Add import around line 47 (with other api imports):
   from app.api import workflow_graph

2. Add router registration around line 180 (after other routers):
   app.include_router(workflow_graph.router)

Verify with: grep -n "workflow_graph" backend/app/main.py
```

#### Task 1.5: Verify Backend Endpoint
**Agent**: Opus (Main)
**Criticality**: High (gate for frontend work)
**Why Opus**: Needs to interpret response, verify structure, debug if needed
**Actions**:
1. Restart backend: `bash ~/portfolio-ai/scripts/restart.sh`
2. Test endpoint: `curl http://localhost:8000/api/workflows/graph | jq`
3. Verify structure: nodes array, edges array, categories array
4. If errors, debug and fix before proceeding

---

### Phase 1B: Frontend Foundation

#### Task 1.6: Install NPM Dependencies
**Agent**: Task (Haiku)
**Criticality**: Low
**Prompt**:
```
Install React Flow and dagre for workflow visualization:

cd ~/portfolio-ai/frontend && npm install @xyflow/react dagre @types/dagre

Verify installation:
cat package.json | grep -E "xyflow|dagre"
```

#### Task 1.7: Create API Client
**Agent**: Task (Sonnet)
**Criticality**: Medium
**Prompt**:
```
Create the workflows API client following existing patterns.

**File to create**: frontend/lib/api/workflows.ts

**Reference**: frontend/lib/api/celery.ts for patterns

**Types to define**:
```typescript
export interface NodeData {
  label: string;
  schedule: string;
  category: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'pending';
  lastRun: string | null;
  nextRun: string | null;
  successRate: number;
  avgDuration: number;
  populatesTables: string[];
}

export interface WorkflowNode {
  id: string;
  type: 'task' | 'workflow' | 'agent';
  data: NodeData;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type: 'dependency' | 'data-flow';
  animated?: boolean;
}

export interface WorkflowGraphResponse {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  categories: string[];
  lastUpdated: string;
}
```

**Function to export**:
```typescript
export async function fetchWorkflowGraph(
  category?: string,
  includeInactive?: boolean
): Promise<WorkflowGraphResponse>
```

Use the `get()` helper from './client' for the request.
```

#### Task 1.8: Create React Query Hook
**Agent**: Task (Sonnet)
**Criticality**: Medium
**Prompt**:
```
Create the React Query hook for workflow graph data.

**File to create**: frontend/lib/hooks/useWorkflowGraph.ts

**Reference**: frontend/lib/hooks/useCeleryTasks.ts for patterns

**Implementation**:
```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchWorkflowGraph, WorkflowGraphResponse } from '../api/workflows';

export function useWorkflowGraph(category?: string, includeInactive = false) {
  return useQuery<WorkflowGraphResponse>({
    queryKey: ['workflow-graph', category, includeInactive],
    queryFn: () => fetchWorkflowGraph(category, includeInactive),
    staleTime: 30_000,  // 30s - matches polling interval
    gcTime: 60_000,
    retry: 1,
  });
}
```
```

#### Task 1.9: Create Custom Task Node Component
**Agent**: Task (Sonnet)
**Criticality**: High (visual quality)
**Prompt**:
```
Create the custom React Flow node component for tasks.

**File to create**: frontend/components/workflows/TaskNode.tsx

**Requirements**:
1. "use client" directive at top
2. Import Handle from @xyflow/react for connection points
3. Display: task label, schedule badge, status indicator, success rate, duration
4. Use existing Badge component from components/ui/badge
5. Use existing Tooltip for hover details

**Status colors** (from CeleryTaskTable patterns):
- running: bg-blue-500 animate-pulse
- completed/success: bg-green-500
- failed: bg-red-500
- pending: bg-yellow-500
- idle: bg-gray-400

**Structure**:
```tsx
"use client";

import { Handle, Position, NodeProps } from '@xyflow/react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { NodeData } from '@/lib/api/workflows';

export function TaskNode({ data }: NodeProps<{ data: NodeData }>) {
  // Render node with:
  // - Top handle for incoming edges
  // - Label (task name, truncated if long)
  // - Schedule badge (outline variant)
  // - Status dot with color
  // - Success rate (if > 0)
  // - Bottom handle for outgoing edges
}
```

Keep it compact but informative. ~150px wide max.
```

#### Task 1.10: Create Workflow Canvas Component
**Agent**: Opus (Main) - supervise, Task (Sonnet) - implement
**Criticality**: Critical (core visualization)
**Why Opus Supervises**: Complex React Flow integration, layout algorithm, state management

**Pre-work (Explore - Very Thorough)**:
```
Search the codebase for any existing React Flow usage or graph visualization patterns. Also find:
1. How other components handle loading/error states
2. Existing dagre usage patterns (if any)
3. How to properly integrate with the existing CSS variable system for colors
```

**Implementation (Task Sonnet)**:
```
Create the main workflow canvas with React Flow and dagre auto-layout.

**File to create**: frontend/components/workflows/WorkflowCanvas.tsx

**Requirements**:
1. "use client" directive
2. Accept category prop for filtering
3. Use useWorkflowGraph hook for data
4. Use dagre for automatic node positioning
5. Include ReactFlow, Background, Controls, MiniMap
6. Register TaskNode as custom node type
7. Handle loading and error states
8. Implement fitView on load
9. Animate edges when source node is "running"

**Key imports**:
```tsx
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState } from '@xyflow/react';
import dagre from 'dagre';
import '@xyflow/react/dist/style.css';
```

**Dagre layout function**:
```tsx
function getLayoutedElements(nodes, edges) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 100 });

  nodes.forEach(node => g.setNode(node.id, { width: 180, height: 80 }));
  edges.forEach(edge => g.setEdge(edge.source, edge.target));

  dagre.layout(g);

  return {
    nodes: nodes.map(node => {
      const pos = g.node(node.id);
      return { ...node, position: { x: pos.x - 90, y: pos.y - 40 } };
    }),
    edges
  };
}
```

**Edge animation**: Set `animated: true` on edges where source node status is "running".

**Error/loading states**: Use existing patterns from other components.
```

**Post-implementation (Opus Main)**: Review the component, verify dagre integration works.

#### Task 1.11: Create Main Page
**Agent**: Task (Sonnet)
**Criticality**: High
**Prompt**:
```
Create the workflows page with tabs for different categories.

**File to create**: frontend/app/workflows/page.tsx

**Requirements**:
1. "use client" directive
2. Use PageContainer, PageHeader from components/shared
3. Use Tabs, TabsList, TabsTrigger, TabsContent from components/ui/tabs
4. Include refresh button in header actions
5. 4 tabs:
   - Data Pipeline (category: "market_data,news")
   - Trading Strategy (category: "strategy")
   - System Health (category: "infrastructure,analytics")
   - Multi-Agent (special handling - see below)

**Structure**:
```tsx
"use client";

import { PageContainer } from '@/components/shared/PageContainer';
import { PageHeader } from '@/components/shared/PageHeader';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { WorkflowCanvas } from '@/components/workflows/WorkflowCanvas';
import { useQueryClient } from '@tanstack/react-query';

export default function WorkflowsPage() {
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['workflow-graph'] });
  };

  return (
    <PageContainer>
      <PageHeader
        title="Workflow Visualization"
        description="Task dependencies and execution flow"
        actions={
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        }
      />

      <Tabs defaultValue="data-pipeline" className="mt-6">
        <TabsList>
          <TabsTrigger value="data-pipeline">Data Pipeline</TabsTrigger>
          <TabsTrigger value="strategy">Trading Strategy</TabsTrigger>
          <TabsTrigger value="system">System Health</TabsTrigger>
          <TabsTrigger value="agents">Multi-Agent</TabsTrigger>
        </TabsList>

        <TabsContent value="data-pipeline" className="mt-4">
          <WorkflowCanvas category="market_data,news" />
        </TabsContent>

        <TabsContent value="strategy" className="mt-4">
          <WorkflowCanvas category="strategy" />
        </TabsContent>

        <TabsContent value="system" className="mt-4">
          <WorkflowCanvas category="infrastructure,analytics" />
        </TabsContent>

        <TabsContent value="agents" className="mt-4">
          {/* Phase 2: Multi-agent workflow view */}
          <div className="text-center py-12 text-muted-foreground">
            Multi-agent workflow visualization coming in Phase 2
          </div>
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
```
```

#### Task 1.12: Add Navigation Link
**Agent**: Task (Haiku)
**Criticality**: Low
**Prompt**:
```
Add workflow link to navigation.

**File**: frontend/components/Navigation.tsx

1. Add import: import { GitBranch } from "lucide-react";

2. Add to mainLinks array (after Capabilities, before the closing bracket):
   { href: "/workflows", label: "Workflows", icon: GitBranch },

Verify: grep -n "Workflows" frontend/components/Navigation.tsx
```

---

### Phase 1C: Integration & Testing

#### Task 1.13: Restart Services and Initial Test
**Agent**: Opus (Main)
**Criticality**: Critical (verification gate)
**Why Opus**: Needs to interpret results, debug issues, make decisions
**Actions**:
1. `bash ~/portfolio-ai/scripts/restart.sh`
2. Wait for services to stabilize (30s)
3. Test backend: `curl http://localhost:8000/api/workflows/graph | jq '.nodes | length'`
4. Screenshot frontend:
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/screenshot.js \
     http://192.168.8.233:3000/workflows /tmp/workflows-initial.png
   ```
5. Check console for errors:
   ```bash
   node ~/portfolio-ai/.claude/skills/browser-automation/scripts/console.js \
     http://192.168.8.233:3000/workflows 5000
   ```

#### Task 1.14: Debug and Fix Issues
**Agent**: Opus (Main)
**Criticality**: Critical
**Why Opus**: Requires judgment, debugging skills, understanding of full stack
**Actions**: Based on errors from 1.13, fix issues. Common problems:
- Import errors → fix paths
- Type errors → adjust interfaces
- Layout issues → adjust dagre parameters
- Missing data → check API response

#### Task 1.15: Test All Tabs
**Agent**: Task (Sonnet)
**Criticality**: High
**Prompt**:
```
Test each tab and capture screenshots. Use browser automation scripts.

For each tab (data-pipeline, strategy, system, agents):
1. Navigate and click the tab
2. Wait for render
3. Capture screenshot
4. Check for console errors

Use the tab-click-screenshot script:
node ~/portfolio-ai/.claude/skills/browser-automation/scripts/tab-click-screenshot.js \
  http://192.168.8.233:3000/workflows "Data Pipeline" /tmp/workflows-data-pipeline.png

Repeat for each tab. Report any errors or empty states.
```

#### Task 1.16: Create Checkpoint Commit
**Agent**: Opus (Main)
**Criticality**: Required
**Actions**:
```bash
git add -A && git commit -m "feat: add workflow visualization page (Phase 1)

- Add /api/workflows/graph endpoint
- Add strategy category to capabilities config
- Create React Flow canvas with dagre layout
- Add custom TaskNode component with status badges
- Add 4-tab page (Data Pipeline, Strategy, System, Multi-Agent)
- Add navigation link

🤖 Generated with Claude Code"
```

---

### Phase 2: Enhanced Features

#### Task 2.1: Execution History Endpoint
**Agent**: Task (Sonnet)
**Criticality**: Medium
**Prompt**:
```
Add history endpoint to workflow_graph.py for task execution timeline.

**Add to**: backend/app/api/workflow_graph.py

**Endpoint**: GET /api/workflows/history

**Query params**: task_name (required), limit (default 10)

**Logic**:
1. Query celery_taskmeta for matching task (by task path pattern)
2. Query maintenance_log if task_name matches maintenance patterns
3. Merge and sort by date
4. Return list of: { id, status, started_at, completed_at, duration_ms, error }

**Reference**: Check how celery_inspector queries celery_taskmeta
```

#### Task 2.2: Task Logs Panel
**Agent**: Task (Sonnet)
**Criticality**: Medium
**Prompt**:
```
Create slide-over panel for task details and execution history.

**File to create**: frontend/components/workflows/TaskLogsPanel.tsx

**Requirements**:
1. Use Sheet component from shadcn/ui (or create if not exists)
2. Accept taskId and onClose props
3. Fetch history from /api/workflows/history?task_name={taskId}
4. Display:
   - Task name header
   - Current status badge
   - Success rate and avg duration
   - Execution timeline (last 10 runs)
   - Click timeline item to expand details

**Reference**: Check how other detail panels are built in the codebase
```

#### Task 2.3: Wire Node Click to Panel
**Agent**: Task (Haiku)
**Criticality**: Low
**Prompt**:
```
Update WorkflowCanvas to open TaskLogsPanel on node click.

1. Add state for selected task: const [selectedTask, setSelectedTask] = useState<string | null>(null);
2. Add onNodeClick handler to ReactFlow
3. Render TaskLogsPanel when selectedTask is set
4. Pass onClose to clear selectedTask

Update frontend/components/workflows/WorkflowCanvas.tsx accordingly.
```

#### Task 2.4: Multi-Agent Workflow View
**Agent**: Explore (Very Thorough) → Task (Sonnet)
**Criticality**: Medium

**Pre-work (Explore)**:
```
Thoroughly explore the multi-agent workflow infrastructure:
1. Check agent_workflows table schema (migration 044)
2. Find how WorkflowOrchestrator stores state
3. Check if any workflows have been executed (query the table)
4. Find WorkflowHealthCard and WorkflowMetricsCard usage patterns
5. Understand the workflow_type enum values
```

**Implementation (Task Sonnet)**:
```
Create the Multi-Agent tab content based on exploration findings.

**File to create**: frontend/components/workflows/AgentWorkflowView.tsx

**Requirements**:
1. Embed existing WorkflowHealthCard and WorkflowMetricsCard
2. If agent_workflows has data, show workflow state diagram
3. If empty, show helpful message about enabling multi-agent features
4. Use same React Flow setup but with different node types for agents

This component replaces the placeholder in the Multi-Agent tab.
```

#### Task 2.5: Final Testing and Polish
**Agent**: Opus (Main)
**Criticality**: High
**Why Opus**: Final quality gate, needs judgment
**Actions**:
1. Full page screenshot
2. Test all interactions (clicks, tabs, refresh)
3. Verify mobile responsiveness
4. Check for console errors
5. Run lint check
6. Create final commit

---

## Parallel Execution Opportunities

These task groups can run in parallel:

**Group A** (Backend):
- Task 1.1 (strategy category)
- Task 1.3 (graph endpoint) - after 1.1
- Task 1.4 (register router) - after 1.3

**Group B** (Frontend - can start after 1.6):
- Task 1.6 (npm install)
- Task 1.7 (API client) - after 1.6
- Task 1.8 (hook) - after 1.7
- Task 1.9 (TaskNode) - after 1.6
- Task 1.10 (Canvas) - after 1.8, 1.9
- Task 1.11 (Page) - after 1.10
- Task 1.12 (Nav link) - anytime

**Integration** (must be sequential):
- Task 1.13-1.16 (testing, debugging, commit)

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

## Implementation Notes

### Environment Compatibility ✅

| Component | Version | Status |
|-----------|---------|--------|
| React | 19.2.0 | ✅ Exceeds React 18+ requirement |
| Next.js | 16.0.0 | ✅ App Router fully supported |
| TypeScript | ^5 | ✅ Strict mode enabled |
| Tailwind CSS | ^4 | ✅ PostCSS v4 configured |

**No conflicting libraries**: react-grid-layout is for dashboards, not graphs.

**Dependencies to install**:
- `@xyflow/react` - NOT installed
- `dagre` - NOT installed
- `@types/dagre` - NOT installed

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

### SSE Stream Limitations

**SSE stream does NOT include active task info** due to performance (~4s Celery inspection delay).

**Data available in SSE (`useStatusStream`)**:
- Service status (backend, celery, beat, frontend)
- Database/Redis health checks
- Workflow health summary (24h aggregates only)
- Data source health

**Data NOT in SSE (requires polling)**:
- Active/running tasks → use `fetchCeleryTasks()` with 30s polling
- Pending tasks
- Individual workflow details

**Implementation**: Use `useCeleryTasks()` hook with manual refresh (already configured with `enabled: false` for on-demand fetching).

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

Badge viz-variants pre-defined: `viz-0` through `viz-5` for score visualization.

### Reverse Dependencies (`called_by`)

The CeleryScanner detects `called_by` (who calls this task) in memory but does NOT persist it to the database. The `celery_capabilities` table has no `called_by` column.

**Solution**: Compute reverse edges client-side from `depends_on_tasks` data. If task A has `depends_on_tasks: ["B"]`, then B is called by A.

### Multi-Agent Workflows Data

The `agent_workflows` table (migration 044) exists with proper schema. Three workflow tasks are implemented in `backend/app/tasks/workflow_tasks.py`:
- `daily_gap_analysis_workflow` - Gemini → Claude → Report
- `paper_trade_validation_workflow` - Strategy → Risk → Execution
- `research_corroboration_workflow` - Agent A → Agent B → Consensus

These workflows use `WorkflowOrchestrator` to track state. However, the table may be empty if workflows haven't been triggered recently. The Multi-Agent tab should handle empty state gracefully.

### Status Colors (from CeleryTaskTable)

```css
ACTIVE:    bg-blue-500 animate-pulse
PENDING:   bg-yellow-500
SUCCESS:   bg-green-500
FAILURE:   bg-red-500
IDLE:      bg-gray-300
```

