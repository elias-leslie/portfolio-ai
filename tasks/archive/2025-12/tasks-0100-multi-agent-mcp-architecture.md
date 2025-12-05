# Task List: Multi-Agent MCP Architecture

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: VERY HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 18:30

---

## Summary

**Goal**: Replace existing Gemini/Claude CLI integrations with a dedicated MCP server for centralized agent coordination, providing agent registry, LLM provider abstraction, tool routing, persistent shared state, and flexible orchestration patterns.

**Approach**: Build an MCP server that acts as the single interface for all LLM agent interactions. Migrate existing agents one by one, then deprecate direct CLI calls.

**Scope Discovery**: Required (understand current agent landscape)

**Design Decisions** (from user input):
- Orchestration: All patterns (sequential, parallel+merge, hierarchical)
- State: Persistent DB-backed state across sessions
- Providers: Gemini + Claude initially (match current implementation)

---

## Current State (Files with TODO breadcrumbs)

These files reference this task and will be migrated:
- `backend/app/agents/llm_client.py` - Current unified interface (to be replaced)
- `backend/app/agents/strategy_reviewer.py` - Strategy review agent
- `backend/app/agents/multi_reviewer.py` - Dual-provider consensus detection
- `backend/app/agents/strategy_evolution_agent.py` - LLM-guided evolution
- `backend/app/agents/clients/` - Gemini/Claude CLI wrappers

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run Explore subagent in "very thorough" mode
  - Pattern: All LLM/agent invocations across codebase
  - Find: GeminiCLIClient, ClaudeCLIClient, DualProviderClient usage
  - Find: Any agent-to-agent communication patterns
  - Find: Agent state storage patterns (DB tables, caches)
- [ ] 0.2 Document current agent architecture
  - List all agent classes and their responsibilities
  - Map data flow between agents
  - Identify shared state requirements
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Total agent files: [TBD]
  - LLM call sites: [TBD]
  - State requirements: [TBD]
  - Effort estimate: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Design MCP Server Architecture

- [ ] 1.1 Define MCP server protocol
  - Agent registration schema
  - Tool/capability declaration format
  - Request/response message format
  - Error handling protocol
- [ ] 1.2 Design provider abstraction layer
  - Unified LLMProvider interface
  - GeminiProvider implementation spec
  - ClaudeProvider implementation spec
  - Failover/fallback strategy
- [ ] 1.3 Design state management layer
  - Session state schema (in-memory)
  - Persistent state schema (PostgreSQL)
  - State sharing between agents
  - State cleanup/TTL policies
- [ ] 1.4 Design orchestration patterns
  - Sequential pipeline pattern
  - Parallel fan-out/merge pattern
  - Hierarchical delegation pattern
  - Pattern selection API
- [ ] 1.5 Create architecture document
  - Save to `docs/reference/mcp-agent-architecture.md`
  - Include diagrams, schemas, examples

---

### 2.0 Implement MCP Server Core

- [ ] 2.1 Create MCP server package structure
  - `backend/app/mcp_agents/` directory
  - `__init__.py`, `server.py`, `protocol.py`
  - `providers/`, `state/`, `orchestration/`
- [ ] 2.2 Implement agent registry
  - Agent registration/deregistration
  - Capability discovery
  - Health check for registered agents
- [ ] 2.3 Implement message router
  - Route requests to appropriate agents
  - Handle agent unavailability
  - Request/response logging

---

### 3.0 Implement LLM Provider Layer

- [ ] 3.1 Create unified LLMProvider interface
  - `providers/base.py` with abstract class
  - Standard request/response types
  - Token counting, rate limiting hooks
- [ ] 3.2 Implement GeminiProvider
  - Wrap existing GeminiCLIClient
  - Add MCP-compatible interface
  - Handle Gemini-specific features
- [ ] 3.3 Implement ClaudeProvider
  - Wrap existing ClaudeCLIClient
  - Add MCP-compatible interface
  - Handle Claude-specific features
- [ ] 3.4 Implement failover logic
  - Primary/secondary provider config
  - Automatic failover on error
  - Failover metrics/logging

---

### 4.0 Implement State Management

- [ ] 4.1 Create session state manager
  - In-memory state for workflow runs
  - Context passing between agents
  - Session TTL and cleanup
- [ ] 4.2 Create persistent state layer
  - Database schema for agent state
  - Migration file (078_agent_state.sql)
  - CRUD operations for state
- [ ] 4.3 Create state sharing API
  - Agent can read/write shared state
  - Scoped by workflow/session/global
  - Conflict resolution strategy

---

### 5.0 Implement Orchestration Patterns

- [ ] 5.1 Implement sequential pipeline
  - Agent A -> B -> C execution
  - Output of A becomes input to B
  - Error propagation handling
- [ ] 5.2 Implement parallel fan-out/merge
  - Run multiple agents concurrently
  - Merge results (configurable strategy)
  - Handle partial failures
- [ ] 5.3 Implement hierarchical delegation
  - Orchestrator agent pattern
  - Sub-agent spawning
  - Result aggregation
- [ ] 5.4 Create orchestration API
  - Pattern selection interface
  - Workflow definition format
  - Execution monitoring

---

### 6.0 Migrate Existing Agents

- [ ] 6.1 Migrate strategy_reviewer.py
  - Update to use MCP client
  - Register with MCP server
  - Remove direct CLI calls
- [ ] 6.2 Migrate multi_reviewer.py
  - Update to use MCP orchestration
  - Use parallel pattern for dual-provider
  - Remove manual failover code
- [ ] 6.3 Migrate strategy_evolution_agent.py
  - Update to use MCP client
  - Use MCP state for lineage tracking
  - Remove direct CLI calls
- [ ] 6.4 Deprecate old llm_client.py
  - Add deprecation warnings
  - Update imports across codebase
  - Schedule for removal

---

### 7.0 Testing & Documentation

- [ ] 7.1 Unit tests for MCP server
  - Provider tests (mock LLM responses)
  - State management tests
  - Orchestration pattern tests
  - Target: 80%+ coverage
- [ ] 7.2 Integration tests
  - Full workflow tests with real providers
  - Failover scenario tests
  - State persistence tests
- [ ] 7.3 Update documentation
  - MCP architecture reference doc
  - Agent development guide
  - Migration guide for existing agents
- [ ] 7.4 Remove TODO breadcrumbs
  - Update all files that reference this task
  - Remove breadcrumb comments

---

## Verification

- [ ] Functional: All existing agents work via MCP server
- [ ] Functional: Sequential, parallel, hierarchical patterns work
- [ ] Functional: State persists across sessions
- [ ] Functional: Failover between providers works
- [ ] Tests: 80%+ coverage, all passing (pytest -v)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Services: Restarted and verified
- [ ] Docs: Architecture doc complete
- [ ] Clean: No direct CLI calls remaining (except in MCP providers)

---

## Dependencies

- This task HAS NO BLOCKERS
- This task BLOCKS: Any future agent development should use MCP
- Timeline: VERY HIGH effort - multi-week project

---

## Files to Create

- `backend/app/mcp_agents/__init__.py`
- `backend/app/mcp_agents/server.py`
- `backend/app/mcp_agents/protocol.py`
- `backend/app/mcp_agents/registry.py`
- `backend/app/mcp_agents/providers/base.py`
- `backend/app/mcp_agents/providers/gemini.py`
- `backend/app/mcp_agents/providers/claude.py`
- `backend/app/mcp_agents/state/session.py`
- `backend/app/mcp_agents/state/persistent.py`
- `backend/app/mcp_agents/orchestration/sequential.py`
- `backend/app/mcp_agents/orchestration/parallel.py`
- `backend/app/mcp_agents/orchestration/hierarchical.py`
- `backend/migrations/078_agent_state.sql`
- `docs/reference/mcp-agent-architecture.md`
- `backend/tests/unit/mcp_agents/` (test suite)

---

## Files to Modify

- `backend/app/agents/strategy_reviewer.py` (migrate)
- `backend/app/agents/multi_reviewer.py` (migrate)
- `backend/app/agents/strategy_evolution_agent.py` (migrate)
- `backend/app/agents/llm_client.py` (deprecate)
- `backend/app/agents/clients/` (wrap in MCP providers)
