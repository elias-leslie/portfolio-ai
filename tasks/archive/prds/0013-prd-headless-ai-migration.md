# PRD #0013: Headless AI Migration (Claude Code → Agent System)

**Status**: Draft
**Created**: 2025-10-28
**Priority**: High
**Effort**: High (3-4 weeks)
**Dependencies**: PRD #0012 (Solution Alignment Fixes)

---

## Introduction/Overview

The current agent system uses the Anthropic API with API keys and cost tracking ($0.50 per run limit). Since this is a personal home deployment exposed via authenticated Tailscale, we can migrate to **headless Claude Code** (and potentially Gemini/local LLMs) which eliminates API costs and latency while maintaining powerful AI capabilities.

**Problem Statement**: Anthropic API usage incurs costs (~$0.50 per agent run) and requires API key management. For personal use with headless LLMs, these constraints are unnecessary.

**Goal**: Replace Anthropic API-based agents with headless Claude Code integration, validate the approach with simple tests, and if successful, fully migrate the agent system to eliminate API dependencies and costs.

---

## Goals

1. **Validate Headless Feasibility**: Create proof-of-concept tests to confirm Claude Code headless mode works for our agent use cases
2. **Eliminate API Costs**: Remove Anthropic API dependency and associated $0.50 per-run cost tracking
3. **Maintain Agent Functionality**: Preserve all existing agent capabilities (Discovery Agent, Portfolio Analyzer)
4. **Improve Response Times**: Reduce latency by using local/headless inference
5. **Future-Proof Architecture**: Design system to support multiple backends (Claude Code, Gemini, local LLMs)

---

## User Stories

### As a User
- I want AI agent insights without incurring API costs so I can run agents frequently without budget concerns
- I want faster agent responses so I get insights more quickly
- I want the same quality of investment ideas so the migration doesn't degrade output quality

### As a Developer
- I want to validate headless Claude Code works before full migration so I don't waste time on an unviable approach
- I want clean abstraction so I can easily swap between different AI backends
- I want comprehensive tests so I can verify agents work correctly with headless LLMs

### As an AI Agent (System)
- I want to remove cost tracking logic since it's no longer applicable to headless/local LLMs
- I want to maintain execution logging so system observability is preserved
- I want tool calling to work identically so agent logic doesn't need rewriting

---

## Functional Requirements

### Phase 1: Validation & Proof-of-Concept (Week 1)

**FR-1.1**: Research Claude Code headless integration options:
- Review Claude Code documentation for headless/programmatic usage
- Identify if Claude Code provides API/SDK for integration
- Determine if MCP (Model Context Protocol) is the integration path
- Document findings in `docs/research/headless-claude-research.md`

**FR-1.2**: Create simple validation tests:
- Test 1: Basic text generation (no tools)
- Test 2: Tool calling with simple function (e.g., get current time)
- Test 3: Multi-turn conversation with context preservation
- Test 4: Error handling and timeout scenarios

**FR-1.3**: Implement validation test harness:
```python
# backend/tests/test_headless_claude_validation.py

def test_headless_claude_basic_generation():
    """Validate basic text generation works with headless Claude"""
    # Setup headless client
    # Send simple prompt
    # Assert response is coherent and non-empty
    pass

def test_headless_claude_tool_calling():
    """Validate tool calling works with headless Claude"""
    # Define simple tool (e.g., get_time)
    # Send prompt requiring tool use
    # Assert tool was called correctly
    # Assert final response incorporates tool result
    pass

def test_headless_claude_context_preservation():
    """Validate multi-turn conversation maintains context"""
    # Send first prompt
    # Send follow-up referencing first response
    # Assert context is maintained
    pass

def test_headless_claude_error_handling():
    """Validate error scenarios are handled gracefully"""
    # Test invalid tool call
    # Test timeout scenario
    # Assert errors are caught and reported
    pass
```

**FR-1.4**: Run validation tests and document results:
- Create `docs/research/headless-validation-results.md`
- Document: Success/failure of each test
- Document: Performance metrics (response time, token throughput)
- Document: Limitations discovered
- **Decision Point**: If validation fails, stop here and create alternative PRD

**FR-1.5**: Get user approval before proceeding to Phase 2:
- Present validation results to user
- Confirm migration is viable
- Confirm user wants to proceed with full migration

### Phase 2: Architecture Design (Week 1-2, if Phase 1 succeeds)

**FR-2.1**: Design abstraction layer for AI backends:
```python
# backend/app/agents/llm_backend.py

from abc import ABC, abstractmethod
from typing import Any

class LLMBackend(ABC):
    """Abstract base class for AI/LLM backends"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Generate response from LLM"""
        pass

    @abstractmethod
    def supports_tools(self) -> bool:
        """Check if backend supports tool calling"""
        pass

class ClaudeCodeBackend(LLMBackend):
    """Headless Claude Code integration"""
    pass

class GeminiBackend(LLMBackend):
    """Gemini integration (via existing MCP)"""
    pass

class LocalLLMBackend(LLMBackend):
    """Local LLM integration (Ollama/LM Studio)"""
    pass
```

**FR-2.2**: Define migration strategy:
- **Option A**: Replace Anthropic code entirely (clean break)
- **Option B**: Support both backends temporarily (transition period)
- **Decision**: Option A (per user requirement "replace entirely if tests succeed")

**FR-2.3**: Map current Anthropic API usage to headless equivalents:
| Current (Anthropic API) | New (Headless Claude) |
|-------------------------|------------------------|
| `anthropic.Anthropic(api_key=...)` | `ClaudeCodeBackend()` |
| `client.messages.create(...)` | `backend.generate(...)` |
| `response.content[0].text` | `response['text']` |
| `response.usage.input_tokens` | ~~N/A (no cost tracking)~~ |
| `tool_calls` | `response['tool_calls']` (same structure) |

**FR-2.4**: Document breaking changes in `docs/research/migration-breaking-changes.md`:
- List all files requiring changes
- List all database schema changes (if any)
- List all configuration changes
- List all test changes

### Phase 3: Implementation (Week 2-3, if Phase 1 succeeds)

**FR-3.1**: Implement `ClaudeCodeBackend`:
- Connect to Claude Code headless process
- Implement `generate()` method with tool calling support
- Handle errors and timeouts gracefully
- Add logging for debugging

**FR-3.2**: Refactor `backend/app/agents/base.py`:
- Replace `anthropic.Anthropic` with `LLMBackend` abstraction
- Remove API key handling
- Remove cost calculation logic
- Keep execution logging (run_id, duration, status)
- Keep tool call logging

**FR-3.3**: Update agent classes:
- `backend/app/agents/discovery.py`: Use `ClaudeCodeBackend`
- `backend/app/agents/portfolio_analyzer.py`: Use `ClaudeCodeBackend`
- Verify system prompts work identically
- Verify tool definitions work identically

**FR-3.4**: Remove cost tracking:
- Drop `cost_usd` column from `agent_runs` table (migration)
- Remove `$0.50 per-run limit` logic
- Remove cost calculation from `_record_run_complete()`
- Update documentation to remove cost references

**FR-3.5**: Database migration for schema changes:
```sql
-- Migration: Remove cost tracking
ALTER TABLE agent_runs DROP COLUMN cost_usd;
```

**FR-3.6**: Update configuration:
- Remove `ANTHROPIC_API_KEY` from `backend/app/constants.py`
- Add `CLAUDE_CODE_PATH` or similar config if needed
- Update `.env.example` to remove API key requirement

**FR-3.7**: Remove Anthropic SDK dependency:
- Remove `anthropic` from `backend/requirements.txt`
- Remove from `backend/pyproject.toml`
- Regenerate `requirements.txt` with `pip freeze`

### Phase 4: Testing & Validation (Week 3-4, if Phase 1 succeeds)

**FR-4.1**: Update existing agent tests:
- `backend/tests/test_discovery_agent.py`: Mock `ClaudeCodeBackend` instead of Anthropic
- `backend/tests/test_portfolio_analyzer.py`: Mock `ClaudeCodeBackend` instead of Anthropic
- `backend/tests/test_api_ideas.py`: Update to reflect no cost tracking
- `backend/tests/test_agent_tools.py`: Verify tools work with new backend

**FR-4.2**: Create integration tests for headless Claude:
```python
# backend/tests/test_headless_claude_integration.py

def test_discovery_agent_with_headless_claude():
    """Test Discovery Agent generates ideas using headless Claude"""
    agent = DiscoveryAgent()
    result = agent.run()
    assert result['status'] == 'completed'
    assert len(result['ideas']) >= 3
    # Assert no cost tracking
    assert 'cost_usd' not in result

def test_portfolio_analyzer_with_headless_claude():
    """Test Portfolio Analyzer generates ideas using headless Claude"""
    agent = PortfolioAnalyzerAgent()
    result = agent.run()
    assert result['status'] == 'completed'
    assert len(result['ideas']) >= 3
    # Assert no cost tracking
    assert 'cost_usd' not in result
```

**FR-4.3**: Manual end-to-end testing:
- Start backend with headless Claude
- Trigger Discovery Agent via API: `POST /api/ideas/generate`
- Verify ideas are generated and stored
- Trigger Portfolio Analyzer via API
- Verify personalized ideas are generated
- Compare output quality to previous Anthropic-based runs

**FR-4.4**: Performance benchmarking:
- Measure agent run time before migration (Anthropic API baseline)
- Measure agent run time after migration (headless Claude)
- Document results in `docs/research/migration-performance.md`
- Expected improvement: 30-50% faster (no network latency)

**FR-4.5**: Verify test coverage maintained:
- Run `pytest backend/tests/ -v --cov=app`
- Ensure coverage remains ≥86%
- Fix any coverage regressions

### Phase 5: Documentation & Cleanup (Week 4, if Phase 1 succeeds)

**FR-5.1**: Update documentation to remove API references:
- `CLAUDE.md`: Remove "Cost tracking - All agent runs tracked with $0.50 per-run limit"
- `CLAUDE.md`: Update to "Headless Claude Code for AI agents (no API costs)"
- `docs/core/ARCHITECTURE.md`: Update agent system section
- `docs/core/API_REFERENCE.md`: Remove cost-related fields from agent_runs responses
- `docs/core/SETUP.md`: Remove API key setup instructions

**FR-5.2**: Update architecture documentation:
```markdown
## AI Agent System (Headless Claude Code)

**Discovery Agent**:
- Uses headless Claude Code via MCP or direct integration
- Scans news and economic data
- Generates 5 general market ideas
- No API costs, runs locally

**Portfolio Analyzer Agent**:
- Uses headless Claude Code via MCP or direct integration
- Analyzes user's portfolio holdings
- Generates personalized ideas based on positions
- No API costs, runs locally

**Agent Features**:
- Tool calling with headless Claude
- Asynchronous execution via Celery workers
- Background task processing with Redis broker
- Execution tracking (agent_runs table without cost_usd)
- Tool call logging (agent_tool_calls table)
- Max iterations limit (10)
```

**FR-5.3**: Create migration guide for users:
```markdown
# Migration Guide: Anthropic API → Headless Claude Code

## What Changed
- Agents now use headless Claude Code instead of Anthropic API
- No API key required
- No per-run costs
- Faster response times (local inference)

## Migration Steps
1. Remove ANTHROPIC_API_KEY from environment
2. Install Claude Code (if not already installed)
3. Run database migration: `python -m app.storage.migrations`
4. Restart backend: `uvicorn app.main:app --reload`
5. Test agents: `POST /api/ideas/generate`

## Breaking Changes
- `agent_runs` table no longer has `cost_usd` column
- API responses no longer include cost information
- Agent configuration may require new environment variables

## Rollback Plan
If issues arise, revert to commit <COMMIT_HASH_BEFORE_MIGRATION> and restore database from backup.
```

**FR-5.4**: Update `REFACTOR_STATUS.md`:
```markdown
### PRD #0013: Headless AI Migration - Complete
- [x] Validation testing confirmed Claude Code headless mode viable
- [x] Replaced Anthropic API with ClaudeCodeBackend
- [x] Removed cost tracking ($0.50 limit no longer needed)
- [x] All tests passing with new backend
- [x] Documentation updated
```

**FR-5.5**: Clean up deprecated code:
- Remove `backend/app/agents/anthropic_client.py` (if exists)
- Remove API key validation logic
- Remove cost calculation utilities
- Archive old code in git history (don't delete, just stop using)

---

## Non-Goals (Out of Scope)

1. **Gemini Integration**: Start with Claude Code only; Gemini is future work
2. **Local LLM Integration**: Start with Claude Code only; Ollama/LM Studio is future work
3. **Multi-Backend Support**: No configuration flag to switch backends (single backend only)
4. **Token Usage Tracking**: No replacement for cost tracking (execution time tracking is sufficient)
5. **Performance Optimization**: Focus on functional migration, not performance tuning
6. **Agent Architecture Refactor**: Keep existing agent logic; only change backend
7. **New Agent Types**: No new agents; migrate existing Discovery + Portfolio Analyzer only

---

## Technical Considerations

### Claude Code Headless Integration
- **Unknown**: How to programmatically invoke Claude Code from Python
- **Research Needed**: Does Claude Code expose an API/SDK, or is MCP the integration path?
- **Fallback**: If headless Claude is not viable, consider Gemini or local LLMs

### Tool Calling Compatibility
- **Assumption**: Headless Claude supports function calling similar to Anthropic API
- **Risk**: Tool calling format may differ, requiring adapter logic
- **Mitigation**: Validation tests in Phase 1 will verify tool calling works

### Database Schema Changes
- **Impact**: Dropping `cost_usd` column is a breaking change
- **Mitigation**: Create migration script, backup database before migration
- **Rollback**: Restore from backup and revert to previous commit if needed

### Testing Challenges
- **Mocking**: Headless Claude is harder to mock than API calls
- **Solution**: Create mock `ClaudeCodeBackend` for unit tests, use real backend for integration tests
- **CI/CD**: May need to install Claude Code in CI environment (or skip integration tests in CI)

### Error Handling
- **Headless Process Crashes**: Need to detect and restart Claude Code process
- **Timeout Handling**: Implement timeouts for long-running agent executions
- **Graceful Degradation**: If Claude Code unavailable, return error instead of crashing

---

## Success Metrics

### Phase 1 (Validation)
1. ✅ All 4 validation tests pass (basic generation, tool calling, context, errors)
2. ✅ Response quality is comparable to Anthropic API
3. ✅ Response time is <10 seconds for simple prompts
4. ✅ Tool calling works correctly with sample tools

### Phase 2-5 (Full Migration, conditional on Phase 1 success)
1. ✅ All existing agent tests pass with `ClaudeCodeBackend`
2. ✅ Discovery Agent generates 5 ideas successfully
3. ✅ Portfolio Analyzer generates personalized ideas successfully
4. ✅ Test coverage remains ≥86%
5. ✅ Agent response time improves by 20%+ vs Anthropic API
6. ✅ No API costs incurred (zero external API calls)
7. ✅ Documentation fully updated (no Anthropic references remain)
8. ✅ `cost_usd` column removed from database
9. ✅ Manual end-to-end test confirms full functionality

---

## Open Questions

### Phase 1 Critical Questions (Block migration if answers are negative)
1. **Q1**: Does Claude Code provide a programmatic API for headless usage?
   - **Research**: Check Claude Code docs, GitHub, community forums
   - **Blocking**: If NO, this entire PRD is not viable
2. **Q2**: Does headless Claude support tool/function calling?
   - **Research**: Test in validation phase
   - **Blocking**: If NO, agents cannot call tools (core requirement)
3. **Q3**: Can headless Claude maintain conversation context across multiple turns?
   - **Research**: Test in validation phase
   - **Blocking**: If NO, agents cannot iterate (core requirement)

### Phase 2+ Questions (Non-blocking, can adapt during implementation)
4. **Q4**: What is the maximum context window for headless Claude?
   - **Research**: Check specs or test empirically
   - **Impact**: May need to truncate tool results if context is limited
5. **Q5**: How do we handle concurrent agent runs with headless Claude?
   - **Research**: Can one Claude Code instance handle multiple requests, or need process pool?
   - **Impact**: May affect Celery worker configuration
6. **Q6**: Should we keep `anthropic` dependency as fallback?
   - **Decision**: NO (per user requirement "replace entirely")

---

## Implementation Phases & Decision Gates

### Gate 1: After Phase 1 (Validation)
**Criteria to Proceed**:
- ✅ All 4 validation tests pass
- ✅ Tool calling works correctly
- ✅ User approves migration based on validation results

**If Gate 1 FAILS**:
- **Action**: STOP migration, create alternative PRD for Gemini or local LLMs
- **Deliverable**: `docs/research/headless-validation-results.md` explaining why migration is not viable

### Gate 2: After Phase 2 (Architecture Design)
**Criteria to Proceed**:
- ✅ `LLMBackend` abstraction designed and reviewed
- ✅ Migration strategy documented
- ✅ Breaking changes identified and acceptable

**If Gate 2 FAILS**:
- **Action**: Revise architecture design, consult with user

### Gate 3: After Phase 3 (Implementation)
**Criteria to Proceed**:
- ✅ `ClaudeCodeBackend` implemented
- ✅ Agents refactored to use new backend
- ✅ Code compiles and basic smoke tests pass

**If Gate 3 FAILS**:
- **Action**: Debug implementation issues, may require architecture changes

### Gate 4: After Phase 4 (Testing)
**Criteria to Proceed**:
- ✅ All tests pass (unit + integration)
- ✅ Test coverage ≥86%
- ✅ Manual end-to-end test confirms functionality

**If Gate 4 FAILS**:
- **Action**: Fix failing tests, may require code changes or test rewrites

### Gate 5: After Phase 5 (Documentation)
**Criteria to Complete PRD**:
- ✅ All documentation updated
- ✅ Migration guide created
- ✅ Old code cleaned up
- ✅ User accepts migration

**If Gate 5 FAILS**:
- **Action**: Complete remaining documentation tasks

---

## Rollback Plan

If migration fails at any phase:

1. **Phase 1 Failure**: No rollback needed (no code changes yet)
2. **Phase 2 Failure**: No rollback needed (design phase only)
3. **Phase 3-5 Failure**:
   - Revert to git commit before migration: `git revert <MIGRATION_COMMITS>`
   - Restore database from backup: `cp data/portfolio-ai.db.backup data/portfolio-ai.db`
   - Reinstall Anthropic SDK: `pip install anthropic`
   - Restart backend: `uvicorn app.main:app --reload`
   - Verify agents work with Anthropic API

**Backup Strategy**:
- Create database backup before Phase 3: `cp data/portfolio-ai.db data/portfolio-ai.db.pre-migration-backup`
- Tag git commit before Phase 3: `git tag pre-headless-migration`
- Document rollback procedure in migration guide

---

## Acceptance Criteria

### Phase 1 Complete When:
1. ✅ `docs/research/headless-claude-research.md` created with integration findings
2. ✅ `backend/tests/test_headless_claude_validation.py` created with 4 validation tests
3. ✅ All 4 validation tests pass
4. ✅ `docs/research/headless-validation-results.md` created with test results
5. ✅ User approves proceeding to Phase 2

### Full PRD Complete When (conditional on Phase 1 success):
1. ✅ `ClaudeCodeBackend` implemented and functional
2. ✅ Anthropic API references removed from codebase
3. ✅ `cost_usd` column removed from `agent_runs` table
4. ✅ All 118+ tests pass with ≥86% coverage
5. ✅ Discovery Agent generates ideas using headless Claude
6. ✅ Portfolio Analyzer generates ideas using headless Claude
7. ✅ Manual end-to-end test confirms full agent functionality
8. ✅ Documentation updated (all Anthropic references removed)
9. ✅ Migration guide created for users
10. ✅ Performance benchmarking shows ≥20% improvement
11. ✅ Git commit created with conventional commits format
12. ✅ Database backup created and rollback plan documented

---

## Related PRDs

- **PRD #0012**: Solution Alignment Fixes (dependency - complete this first)
- **PRD #0011**: Multi-Source Data & Trading Intelligence (85% complete)
- **Future**: Gemini integration (if Claude Code migration successful, apply same pattern)
- **Future**: Local LLM integration (if Claude Code migration successful, apply same pattern)

---

## References

- Claude Code Documentation: https://docs.anthropic.com/claude-code
- Model Context Protocol (MCP): https://github.com/anthropics/mcp
- Solution Alignment Report: `docs/core/SOLUTION_ALIGNMENT.md`
- Current Agent Implementation: `backend/app/agents/base.py`
