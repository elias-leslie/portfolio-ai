# Task List: Headless Gemini & Claude Code Agent Integration

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-02-14 00:00

---

## Summary

**Goal**: Replace direct Anthropic API usage with Gemini CLI and Claude Code CLI headless agents, exposing them through a provider-agnostic backend plus shared/dedicated agent experiences in the UI. **Extends to multi-agent collaboration** where multiple agents (Gemini + Claude) work together on complex tasks like daily trading intelligence analysis and strategy validation.
**Approach**: Introduce an interchangeable LLM client layer, add CLI adapters for Gemini and Claude Code, refactor the agent runtime/API/storage to use it, build UI surfaces (global dock + /agents page) with streaming and progress telemetry, **and add multi-agent orchestration** for autonomous collaborative workflows.
**Scope Discovery**: Required

**Dependencies (Downstream)**:
- **Task 0062** (Gap Detection Phase 3): Task 4.0 requires working ai_analyzer (Task 3.2a here)
- **Task 0063** (Backtesting): Agents validate strategies using backtesting framework
- **Task 0064** (Paper Trading): Agents execute autonomous paper trades

**Autonomous Behavior & Limits** (for Task 3.7 - Multi-Agent Collaboration):
- **Complete Autonomy**: Agents have full autonomy for trading/research/backtesting within rate/resource/utilization limits
- **Agent Self-Awareness**: Agents must be able to check their own limits:
  - Daily API rate limits (Gemini: check via `gemini --help`, Claude: monitor stderr warnings)
  - Hourly request limits (implement tracking in agent_runs table)
  - Token/context limits (track via CLI stats.models output, warn at 80% usage)
  - Resource limits (CPU, memory, disk space - monitor via system tools)
- **Commands to Implement**:
  - `check_agent_limits()` tool - returns current usage vs limits (API calls, tokens, context)
  - `get_agent_status()` tool - health check (can I run? any rate limit warnings?)
  - Agents should call these BEFORE starting expensive workflows
- **Failure Handling**: If agent hits limit, workflow fails gracefully (log + alert), other agent continues
- **Git Workflow**:
  - Commit to **main branch** (not feature branches)
  - Auto-push to **remote** enabled (user can review on GitHub during vacation)
  - Snapshot files: `reports/autonomous/{YYYY-MM-DD}-{workflow_type}.json`
  - Commit message format: `[AUTONOMOUS] {date} - {workflow_type} - {result_summary}`
  - Commit frequency: Daily after each workflow completion
  - Example: `[AUTONOMOUS] 2025-11-15 - Daily Gap Analysis - 3 new gaps identified, 2 resolved, SPY backtest +2.1%`

<details>
<summary><strong>Internal PRD</strong></summary>

### Objectives
- Run all Portfolio AI agents (Discovery, Portfolio Analyzer, new personas) through CLI-based Gemini and Claude Code models to avoid per-token costs.
- Maintain existing tool execution, run tracking, and telemetry while supporting multiple providers/configurations.
- Provide UI entry points everywhere (shared dock) plus a dedicated Agents page with run history, role selection, and streaming output.

### Requirements
1. Provider abstraction & configuration
   - Swappable LLM client interface supporting streaming/tool use semantics used today.
   - CLI adapters handle stdin/stdout, errors, and timeouts; configurable model + persona mapping from DB.
2. Backend updates
   - Agents no longer import Anthropic directly; runtime selects provider per profile.
   - Expand agent_runs storage to capture provider/model/latency, add SSE/WebSocket event feed and cancellation hook.
   - New API endpoints: list agent profiles, start run, stream updates, fetch transcripts.
3. UI
   - Docked agent panel available on all pages; context-aware prompts (e.g., selected portfolio data) and streaming transcript.
   - `/agents` page listing personas, recent runs, costs, and transcripts with rerun/resume actions.
4. Testing / validation
   - Headless CLI smoke tests to capture syntax/limits of Gemini + Claude Code.
   - Backend + frontend automated tests plus manual verification plan.

### Constraints / Risks
- CLI binaries already installed; must guard against hangs via timeouts + isolated Celery workers.
- Need fallbacks/logging if CLI exits with non-zero codes.
- SSE/WebSocket streaming must not block API threads.

### Acceptance Criteria
- Agents execute exclusively via Gemini CLI or Claude Code CLI, selectable per profile.
- UI dock + Agents page both initiate runs and show live output/tool logs.
- Tests cover client adapters, API endpoints, and UI flows; documentation updated.

</details>

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: All references to Anthropic API usage, agent run orchestration, and existing agent UI triggers
  - Goal: Catalog every module, API route, React component, and task touching `Anthropic` or current agents
  - Output: Complete list with file paths + line numbers for runtime, tools, APIs, UI hooks
  - **Known files requiring refactoring** (as of 2025-11-13):
    - `backend/app/agents/base.py` - Base Agent class with Anthropic client
    - `backend/app/services/ai_analyzer.py` - **BROKEN** Capability AI analyzer (no Anthropic API key configured, must refactor to CLI)
    - `backend/app/tasks/capability_tasks.py` - Calls ai_analyzer
    - Tests referencing above
  - **CRITICAL**: ai_analyzer.py is currently non-functional (no API key), blocking Task 0062 Task 4.0
- [ ] 0.2 Update this task list with ALL discovered files
  - Add concrete sub-tasks per file/area, adjust numbering/effort based on findings
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total files affected: [TBD - at least 4 known, likely more]
  - Estimated effort: [TBD]
  - Architectural concerns: [TBD]

### 1.0 Design Provider-Agnostic Agent Runtime

- [ ] 1.1 Document current agent execution flow (storage, Celery, tool calls) based on Scope Discovery results
- [ ] 1.2 Draft interface for `LLMClient` (tool use, streaming, cancellation) plus provider selection rules per agent profile
- [ ] 1.3 Review design with constraints (CLI-only providers, multi-model support); adjust PRD/this list if gaps remain

### 2.0 Implement CLI Client Adapters & Configuration

- [ ] 2.1 Build Gemini CLI adapter that:
  - [ ] 2.1.1 Invokes `gemini --prompt/-p` with stdin piping and `--output-format` (`text`, `json`, `stream-json`)
  - [ ] 2.1.2 Supports model selection via `-m` (e.g., `gemini-2.5-pro`, `gemini-2.5-flash`) and advanced flags (`--debug`, `--include-directories`, `--approval-mode`)
  - [ ] 2.1.3 Parses structured JSON responses (top-level `response`, `stats.models`, `stats.tools`, `error`) and streaming event types (`init`, `message`, `tool_use`, `tool_result`, `result`)
  - [ ] 2.1.4 Normalizes CLI exit codes, stderr output, and enforces configurable `timeout` wrappers for long prompts
- [ ] 2.2 Build Claude Code CLI adapter that:
  - [ ] 2.2.1 Runs `claude -p/--print` with `--output-format text|json|stream-json` and required `--permission-mode` / `--allowedTools` flags
  - [ ] 2.2.2 Handles session controls (`--resume`, `--continue`, `--append-system-prompt`, `--mcp-config`, `--permission-prompt-tool`)
  - [ ] 2.2.3 Streams tool events and final responses, decoding `claude` JSON blocks and enforcing log capture (stderr to error files)
  - [ ] 2.2.4 Applies sandbox limits (working directory, environment, CPU/memory) and configurable retries when the CLI declines edits
- [ ] 2.3 Add configuration model/table for agent profiles (role, provider, CLI command, default prompt, allowed/blocked tools, default output format, resume policy)
- [ ] 2.4 Add settings/env wiring for CLI paths, concurrency limits, session caching locations, and fallback provider order
- [ ] 2.5 Implement shared streaming parser that converts Gemini/Claude `stream-json` events into a unified internal event schema (text deltas, tool_use, tool_result, stats, completion), ready for SSE/WebSocket publishing.

### 3.0 Refactor Backend Agent Execution

- [ ] 3.1 Inject `LLMClient` into `Agent` base class, removing direct `Anthropic` import/usage
- [ ] 3.2 Update Discovery/Portfolio Analyzer (and future personas) to use provider profiles + new runtime
- [ ] 3.2a **Refactor CapabilityAnalyzer (Task 0059)** to use CLI adapter **[HIGH PRIORITY - UNBLOCKS TASK 0062]**
  - File: `backend/app/services/ai_analyzer.py`
  - Current: Uses `Anthropic()` client directly with model "claude-sonnet-4.5-20250929" **[BROKEN - no API key configured]**
  - Target: Use provider-agnostic LLMClient with headless `claude -p --output-format stream-json`
  - Benefit: Zero per-token costs for daily automated analysis
  - **CRITICAL**: This unblocks Task 0062 Task 4.0 (AI-Powered Gap Analysis) which depends on working ai_analyzer
  - Note: Celery task `analyze_capabilities` calls this, must continue working
- [ ] 3.3 Extend `agent_runs` schema to capture provider/model/status telemetry (CLI command, model flag, session/resume token, exit code, duration stats) and expose via API
- [ ] 3.4 Implement cancellation/timeouts + error handling for CLI processes with retries/fallback, mirroring doc best practices (e.g., wrap with `timeout 300`, capture stderr logs when `claude`/`gemini` fail)
- [ ] 3.5 Add SSE/WebSocket streaming endpoint for run events (text chunks, tool calls, completion)
- [ ] 3.6 Persist CLI usage metadata (Gemini `stats.models/tools`, Claude stream summaries) and multi-turn session IDs so `/agents` UI can show model usage, token counts, and support `--resume/--continue` follow-ups.
- [ ] 3.7 **Multi-Agent Collaboration Infrastructure** (for Tasks 0063/0064 autonomous workflows)
  - [ ] 3.7.1 Create `agent_messages` table for inter-agent communication
    - Schema: `id`, `from_agent_run_id`, `to_agent_type`, `message_type` (question/answer/data/consensus), `content` (JSONB), `status` (pending/read/replied), `created_at`, `read_at`
    - Enables: Agent A asks Agent B for validation, Agent B responds with analysis
  - [ ] 3.7.2 Create `agent_workflows` table for orchestration state
    - Schema: `id`, `workflow_type` (daily_gap_analysis, paper_trade_validation), `status` (running/blocked/complete), `current_step`, `agents_involved` (array), `shared_context` (JSONB), `result` (JSONB), `started_at`, `completed_at`
    - Enables: Multi-agent workflows like "daily gap analysis → strategy validation → paper trade execution"
  - [ ] 3.7.3 Add agent tools for collaboration
    - `send_message_to_agent(agent_type, message, data)` - Send message to another agent type
    - `query_agent_memory(workflow_id, key)` - Query shared workflow context
    - `vote_on_decision(workflow_id, decision_id, vote, reasoning)` - Consensus mechanism
    - `wait_for_agent_response(message_id, timeout_seconds)` - Blocking wait for response
  - [ ] 3.7.4 Create WorkflowOrchestrator service
    - `start_workflow(workflow_type, config)` - Launches multi-agent workflow
    - `assign_task_to_agent(workflow_id, agent_type, task, context)` - Task distribution
    - `collect_agent_outputs(workflow_id)` - Gather results from all agents
    - `resolve_conflicts(workflow_id, conflicting_outputs)` - Consensus logic (voting, majority, confidence-weighted)
  - [ ] 3.7.5 Add fallback/redundancy logic
    - If Agent A fails/timeouts → Agent B continues alone
    - If agents disagree → Use confidence scores to decide OR escalate to user
    - Maximum workflow time limit (prevent infinite loops)
  - [ ] 3.7.6 Add scheduled multi-agent workflows (for daily autonomous operation)
    - Daily gap analysis workflow: Gemini agent → Claude agent → Consensus → Report generation
    - Paper trade validation workflow: Strategy agent → Risk agent → Consensus → Execution decision
    - Celery beat tasks trigger workflows automatically

- [ ] 4.1 Add FastAPI routes for agent profiles (list/detail), run creation, run history, run transcripts
- [ ] 4.2 Wire Celery/background tasks (or async workers) to execute CLI runs without blocking HTTP threads
- [ ] 4.3 Provide API to supply contextual data (portfolio snapshot, watchlist, preferences) to agents via tools
- [ ] 4.4 Write integration tests covering run lifecycle, streaming, and data access checks

### 5.0 Frontend Agent Experiences

- [ ] 5.1 Implement global Agent dock component with context infusion + SSE streaming UI
- [ ] 5.2 Create `/agents` page listing personas, recent runs, transcripts, and rerun controls
- [ ] 5.3 Add entry points (buttons/shortcuts) on key pages that open the dock with seeded prompts
- [ ] 5.4 Integrate permissions/status indicators (provider used, last run duration, cost) into UI
- [ ] 5.5 Add React Query hooks/tests for new APIs and streaming layer

### 6.0 Testing, Docs, and Verification

- [ ] 6.1 Run headless smoke tests for Gemini CLI + Claude Code CLI covering:
  - [ ] 6.1.1 Text vs JSON vs `stream-json` output parsing
  - [ ] 6.1.2 Tool invocation flows (`--allowedTools`/`--permission-mode`, Gemini tool stats)
  - [ ] 6.1.3 Session resume/continue scenarios and timeout/error handling
- [ ] 6.2 Update backend unit/integration tests, ensuring mypy/ruff pass and pytest suite green
- [ ] 6.3 Add frontend component/e2e tests for dock + Agents page behaviors
- [ ] 6.4 Update documentation (README, ARCHITECTURE, CLAUDE/GEMINI guides) describing new agents + UI
- [ ] 6.5 Create rollout/ops checklist (timeouts, monitoring, log review) and verify services restarted cleanly

---

## Verification

- [ ] Functional: All requirements met, zero regressions in agent workflows
- [ ] Tests: Backend `pytest -v`, frontend `npm test` & `npm run test:e2e` passing
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Services: `bash ~/portfolio-ai/scripts/restart.sh` succeeds and health endpoints green
- [ ] Clean: No stray Anthropic references; provider abstraction documented
- [ ] Docs: README/ARCHITECTURE/agent docs updated with new flow
