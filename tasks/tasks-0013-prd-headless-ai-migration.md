# Task List: Headless AI Migration (Claude Code → Agent System)

**PRD**: `0013-prd-headless-ai-migration.md`
**Status**: Ready for Implementation
**Completion**: 0% (Not started)
**Effort to Complete**: HIGH (3-4 weeks)
**Last Updated**: 2025-10-28
**Dependencies**: PRD #0012 (Solution Alignment Fixes) must be complete first

**Note on Effort Levels**:
- **Low**: 1-2 hours of straightforward work
- **Medium**: Half day of work with some complexity
- **High**: Full day or more, significant complexity

**⚠️ CRITICAL DECISION GATE**: Phase 1 validation determines if this PRD is viable. If headless Claude Code integration fails validation, STOP and create alternative PRD for Gemini or local LLMs.

---

## Summary

**✅ COMPLETE:**
- (None yet)

**🔄 IN PROGRESS:**
- (Not started)

**⚠️ NEXT STEPS:**
1. **MUST COMPLETE PRD #0012 FIRST** - Ensure all tests pass and Python 3.13 migration complete
2. Begin with Phase 1 (Task 1.0) - Validation & Proof-of-Concept
3. **DECISION GATE**: If Phase 1 validation succeeds, proceed to Phase 2-5
4. **DECISION GATE**: If Phase 1 validation fails, STOP and reassess approach

**EFFORT TO COMPLETE:** HIGH (3-4 weeks, ~120-160 hours if validation succeeds)

**Context from Current State**:
- Current agent system uses Anthropic API (`anthropic.Anthropic`)
- Agents: `DiscoveryAgent`, `PortfolioAnalyzerAgent` inherit from `Agent` base class
- Agent base class in `backend/app/agents/base.py` (~300 lines)
- Tool system in `backend/app/agents/tools.py` (~500 lines)
- Cost tracking exists: `cost_usd` field in `agent_runs` table
- Database has `agent_runs`, `agent_ideas`, `agent_tool_calls` tables
- Current dependencies: `anthropic>=0.3.0` in requirements.txt

---

## Relevant Files

### Files to Create (Phase 1: 3 files)

**Research & Validation:**
- `docs/research/headless-claude-research.md` (~200 lines) - Research findings on Claude Code headless integration
- `docs/research/headless-validation-results.md` (~150 lines) - Validation test results and decision rationale
- `backend/tests/test_headless_claude_validation.py` (~300 lines) - 4 validation tests (basic, tools, context, errors)

### Files to Create (Phase 2-5: 6 files, conditional on Phase 1 success)

**Backend Implementation:**
- `backend/app/agents/llm_backend.py` (~400 lines) - Abstract LLMBackend base class and ClaudeCodeBackend implementation
- `docs/research/migration-breaking-changes.md` (~200 lines) - Document all breaking changes for migration
- `docs/research/migration-performance.md` (~100 lines) - Performance benchmarks before/after migration
- `backend/tests/test_headless_claude_integration.py` (~400 lines) - Integration tests for agents with headless Claude
- `backend/migrations/remove_cost_tracking.sql` (~20 lines) - SQL migration to drop cost_usd column
- `docs/migration-guide-headless-ai.md` (~300 lines) - User migration guide for Anthropic API → Headless Claude

### Files to Update (Phase 2-5: 15+ files, conditional on Phase 1 success)

**Agent System:**
- `backend/app/agents/base.py` - Replace Anthropic client with LLMBackend abstraction, remove cost tracking
- `backend/app/agents/discovery.py` - Update to use ClaudeCodeBackend
- `backend/app/agents/portfolio_analyzer.py` - Update to use ClaudeCodeBackend
- `backend/app/agents/tools.py` - Ensure tools work with new backend (likely no changes needed)

**Database & Storage:**
- `backend/app/storage/schema.py` - Drop cost_usd column from agent_runs table
- `backend/app/storage/migrations.py` - Add migration for cost_usd removal

**Tests:**
- `backend/tests/test_api_ideas.py` - Update mocks to use ClaudeCodeBackend
- `backend/tests/test_discovery_agent.py` - Update mocks to use ClaudeCodeBackend
- `backend/tests/test_portfolio_analyzer.py` - Update mocks to use ClaudeCodeBackend
- `backend/tests/test_agent_tools.py` - Verify tools work with new backend

**Configuration:**
- `backend/app/constants.py` - Remove ANTHROPIC_API_KEY, add CLAUDE_CODE_PATH or similar
- `backend/requirements.txt` - Remove anthropic dependency
- `backend/pyproject.toml` - Remove anthropic from dependencies
- `.env.example` - Remove ANTHROPIC_API_KEY, add new config if needed

**Documentation:**
- `CLAUDE.md` - Update agent system description, remove cost tracking mention
- `docs/core/ARCHITECTURE.md` - Update agent system section to reflect headless Claude
- `docs/core/API_REFERENCE.md` - Remove cost fields from agent_runs responses
- `docs/core/SETUP.md` - Remove API key setup, add Claude Code setup if needed
- `docs/core/REFACTOR_STATUS.md` - Mark PRD #0013 complete

### Notes

- **Phase 1 is BLOCKING**: If validation fails, do NOT proceed to Phase 2-5
- **Backup Database**: Create backup before Phase 3 implementation: `cp data/portfolio-ai.db data/portfolio-ai.db.pre-migration-backup`
- **Git Tag**: Tag commit before Phase 3: `git tag pre-headless-migration`
- **Rollback Plan**: If migration fails, revert to backup and tagged commit
- Use `pytest backend/tests/ -v --cov=app` to run all tests
- Use `./scripts/lint.sh` to run linting suite
- Target test coverage: ≥86% (must maintain)

---

## Tasks

- [ ] 1.0 Phase 1: Validation & Proof-of-Concept [EFFORT: MEDIUM, ~2-3 days]
  - [ ] 1.1 Research Claude Code headless integration
    - [ ] 1.1.1 Review Claude Code documentation for headless/programmatic usage
      - [ ] Search Claude Code docs for "headless", "API", "programmatic", "MCP"
      - [ ] Check Claude Code GitHub issues/discussions for integration examples
      - [ ] Review MCP (Model Context Protocol) documentation if relevant
    - [ ] 1.1.2 Investigate integration methods
      - [ ] Option A: Direct Claude Code API/SDK (if available)
      - [ ] Option B: MCP server integration
      - [ ] Option C: Claude Desktop automation/IPC
      - [ ] Option D: Other methods discovered during research
    - [ ] 1.1.3 Create research document
      - [ ] Create `docs/research/` directory if not exists
      - [ ] Create `docs/research/headless-claude-research.md`
      - [ ] Document all integration options discovered
      - [ ] Document pros/cons of each approach
      - [ ] Document technical feasibility assessment
      - [ ] Recommend preferred approach
  - [ ] 1.2 Create validation test harness
    - [ ] 1.2.1 Create test file: `backend/tests/test_headless_claude_validation.py`
    - [ ] 1.2.2 Implement Test 1: Basic text generation (no tools)
      - [ ] Setup headless Claude client/connection
      - [ ] Send simple prompt: "What is 2+2? Answer with just the number."
      - [ ] Assert response is coherent and contains "4"
      - [ ] Assert response time < 30 seconds
    - [ ] 1.2.3 Implement Test 2: Tool calling with simple function
      - [ ] Define simple tool: `get_current_time()` returns ISO timestamp
      - [ ] Send prompt: "What time is it? Use the get_current_time tool."
      - [ ] Assert tool was called (check response structure)
      - [ ] Assert final response mentions the time
      - [ ] Verify tool result was incorporated into response
    - [ ] 1.2.4 Implement Test 3: Multi-turn conversation with context
      - [ ] Turn 1: Send "My name is Alice"
      - [ ] Turn 2: Send "What is my name?"
      - [ ] Assert Turn 2 response mentions "Alice"
      - [ ] Verify context preservation between turns
    - [ ] 1.2.5 Implement Test 4: Error handling and timeout scenarios
      - [ ] Test invalid tool call (tool doesn't exist)
      - [ ] Test timeout scenario (set 5s timeout, send complex prompt)
      - [ ] Assert errors are caught and reported gracefully
      - [ ] Verify no crashes or unhandled exceptions
  - [ ] 1.3 Run validation tests and analyze results
    - [ ] 1.3.1 Run validation test suite: `pytest backend/tests/test_headless_claude_validation.py -v`
    - [ ] 1.3.2 Record test results:
      - [ ] Test 1 (basic): Pass/Fail + response time
      - [ ] Test 2 (tools): Pass/Fail + tool calling worked?
      - [ ] Test 3 (context): Pass/Fail + context preserved?
      - [ ] Test 4 (errors): Pass/Fail + graceful error handling?
    - [ ] 1.3.3 Measure performance metrics:
      - [ ] Average response time for basic prompt
      - [ ] Average response time for tool-calling prompt
      - [ ] Token throughput (if measurable)
    - [ ] 1.3.4 Document limitations discovered:
      - [ ] Maximum context window size
      - [ ] Tool calling format differences vs Anthropic
      - [ ] Any missing features vs Anthropic API
  - [ ] 1.4 Document validation results
    - [ ] 1.4.1 Create `docs/research/headless-validation-results.md`
    - [ ] 1.4.2 Document test results (pass/fail for each test)
    - [ ] 1.4.3 Document performance metrics
    - [ ] 1.4.4 Document limitations and gaps
    - [ ] 1.4.5 Document comparison to Anthropic API baseline (if available)
    - [ ] 1.4.6 Provide recommendation: PROCEED or STOP
  - [ ] 1.5 **DECISION GATE**: Get user approval
    - [ ] 1.5.1 Present validation results to user
    - [ ] 1.5.2 Highlight any concerns or limitations
    - [ ] 1.5.3 Confirm migration is viable and worth proceeding
    - [ ] 1.5.4 If user approves: Proceed to Phase 2
    - [ ] 1.5.5 If user rejects: STOP here, create alternative PRD for Gemini/local LLMs
  - [ ] 1.6 Commit Phase 1 deliverables
    - [ ] 1.6.1 Stage changes: `git add docs/research/ backend/tests/test_headless_claude_validation.py`
    - [ ] 1.6.2 Commit: "feat: Phase 1 validation for headless Claude Code integration"
    - [ ] 1.6.3 Include validation results summary in commit message

---

**⚠️ STOP HERE IF PHASE 1 VALIDATION FAILS**

The following phases are conditional on Phase 1 success and user approval.

---

- [ ] 2.0 Phase 2: Architecture Design [EFFORT: MEDIUM, ~2-3 days, IF PHASE 1 SUCCEEDS]
  - [ ] 2.1 Design LLMBackend abstraction layer
    - [ ] 2.1.1 Create `backend/app/agents/llm_backend.py` file
    - [ ] 2.1.2 Define `LLMBackend` abstract base class:
      - [ ] Abstract method: `generate(prompt, tools, max_tokens, temperature) -> dict`
      - [ ] Abstract method: `supports_tools() -> bool`
      - [ ] Abstract method: `get_model_name() -> str`
    - [ ] 2.1.3 Define `ClaudeCodeBackend(LLMBackend)` class:
      - [ ] `__init__`: Setup headless Claude connection
      - [ ] `generate`: Implement prompt → response logic
      - [ ] `supports_tools`: Return True
      - [ ] Tool calling integration (based on Phase 1 findings)
    - [ ] 2.1.4 Add type hints and docstrings to all methods
    - [ ] 2.1.5 Run `mypy backend/app/agents/llm_backend.py --strict` (must pass)
  - [ ] 2.2 Map Anthropic API to Headless Claude equivalents
    - [ ] 2.2.1 Create mapping document: `docs/research/migration-breaking-changes.md`
    - [ ] 2.2.2 Map API call structure:
      - [ ] Anthropic: `client.messages.create(...)` → Headless: `backend.generate(...)`
      - [ ] Anthropic: `response.content[0].text` → Headless: `response['text']`
      - [ ] Anthropic: `response.usage.input_tokens` → Headless: N/A (no cost tracking)
      - [ ] Anthropic: `tool_calls` → Headless: Document tool calling format
    - [ ] 2.2.3 Document breaking changes:
      - [ ] List all files requiring changes
      - [ ] List all database schema changes (cost_usd column removal)
      - [ ] List all configuration changes (API key removal)
      - [ ] List all test changes
    - [ ] 2.2.4 Document non-breaking aspects:
      - [ ] Tool system should work identically
      - [ ] Agent logic (prompts, system messages) unchanged
      - [ ] Database schema mostly unchanged (except cost_usd)
  - [ ] 2.3 Plan database migration for cost tracking removal
    - [ ] 2.3.1 Identify all references to `cost_usd` field:
      - [ ] `backend/app/storage/schema.py` - agent_runs table definition
      - [ ] `backend/app/agents/base.py` - _record_run_complete method
      - [ ] Any API responses that include cost_usd
    - [ ] 2.3.2 Design migration strategy:
      - [ ] SQL: `ALTER TABLE agent_runs DROP COLUMN cost_usd;`
      - [ ] Update schema.py to remove column from CREATE TABLE
      - [ ] Update code to remove cost calculation logic
  - [ ] 2.4 Get user review of architecture
    - [ ] 2.4.1 Present LLMBackend design to user
    - [ ] 2.4.2 Review breaking changes document
    - [ ] 2.4.3 Confirm user approves architecture
    - [ ] 2.4.4 Address any concerns or requested changes
  - [ ] 2.5 Commit Phase 2 deliverables
    - [ ] 2.5.1 Stage: `git add backend/app/agents/llm_backend.py docs/research/migration-breaking-changes.md`
    - [ ] 2.5.2 Commit: "feat: Phase 2 architecture design for headless AI migration"

- [ ] 3.0 Phase 3: Implementation [EFFORT: HIGH, ~1-2 weeks, IF PHASE 1 SUCCEEDS]
  - [ ] 3.1 Prepare for migration
    - [ ] 3.1.1 Create database backup: `cp data/portfolio-ai.db data/portfolio-ai.db.pre-migration-backup`
    - [ ] 3.1.2 Tag git commit: `git tag pre-headless-migration`
    - [ ] 3.1.3 Verify backup exists: `ls -lh data/*.backup`
    - [ ] 3.1.4 Document rollback procedure in commit message
  - [ ] 3.2 Implement ClaudeCodeBackend (full implementation)
    - [ ] 3.2.1 Complete `backend/app/agents/llm_backend.py` implementation
    - [ ] 3.2.2 Add error handling (connection errors, timeouts)
    - [ ] 3.2.3 Add logging for debugging (use structlog)
    - [ ] 3.2.4 Add configuration support (read from constants.py)
    - [ ] 3.2.5 Test basic functionality manually
  - [ ] 3.3 Refactor Agent base class
    - [ ] 3.3.1 Open `backend/app/agents/base.py`
    - [ ] 3.3.2 Replace `from anthropic import Anthropic` with `from .llm_backend import LLMBackend, ClaudeCodeBackend`
    - [ ] 3.3.3 Replace `self.client = Anthropic(...)` with `self.backend = ClaudeCodeBackend()`
    - [ ] 3.3.4 Update `run()` method to use `self.backend.generate(...)`
    - [ ] 3.3.5 Remove cost calculation logic from `_record_run_complete()`
    - [ ] 3.3.6 Remove API key handling from `__init__()`
    - [ ] 3.3.7 Keep execution logging (run_id, duration, status)
    - [ ] 3.3.8 Run `mypy backend/app/agents/base.py --strict` (must pass)
  - [ ] 3.4 Update agent classes
    - [ ] 3.4.1 Open `backend/app/agents/discovery.py`
    - [ ] 3.4.2 Verify no Anthropic-specific code (should work with LLMBackend)
    - [ ] 3.4.3 Test system prompt still works correctly
    - [ ] 3.4.4 Open `backend/app/agents/portfolio_analyzer.py`
    - [ ] 3.4.5 Verify no Anthropic-specific code
    - [ ] 3.4.6 Test system prompt still works correctly
  - [ ] 3.5 Remove cost tracking from database
    - [ ] 3.5.1 Create migration SQL: `backend/migrations/remove_cost_tracking.sql`
    - [ ] 3.5.2 SQL: `ALTER TABLE agent_runs DROP COLUMN cost_usd;`
    - [ ] 3.5.3 Update `backend/app/storage/schema.py`:
      - [ ] Remove `cost_usd DOUBLE,` from agent_runs CREATE TABLE
    - [ ] 3.5.4 Run migration manually: `sqlite3 data/portfolio-ai.db < backend/migrations/remove_cost_tracking.sql`
    - [ ] 3.5.5 Verify column removed: `sqlite3 data/portfolio-ai.db "PRAGMA table_info(agent_runs);"`
  - [ ] 3.6 Update configuration
    - [ ] 3.6.1 Open `backend/app/constants.py`
    - [ ] 3.6.2 Remove `ANTHROPIC_API_KEY` constant
    - [ ] 3.6.3 Add `CLAUDE_CODE_PATH` or similar config if needed (based on Phase 1 findings)
    - [ ] 3.6.4 Update `.env.example` to remove ANTHROPIC_API_KEY
    - [ ] 3.6.5 Add new environment variables to .env.example if needed
  - [ ] 3.7 Remove Anthropic SDK dependency
    - [ ] 3.7.1 Open `backend/requirements.txt`
    - [ ] 3.7.2 Remove line: `anthropic>=0.3.0` (or similar)
    - [ ] 3.7.3 Open `backend/pyproject.toml`
    - [ ] 3.7.4 Remove `anthropic` from `[project.dependencies]` section
    - [ ] 3.7.5 Regenerate requirements: `pip freeze > backend/requirements.txt`
    - [ ] 3.7.6 Test clean install: `pip install -r backend/requirements.txt`
  - [ ] 3.8 Verify implementation compiles
    - [ ] 3.8.1 Run `mypy backend/app/ --strict` (must pass)
    - [ ] 3.8.2 Run `ruff check backend/app/` (must pass)
    - [ ] 3.8.3 Run `ruff format backend/app/`
    - [ ] 3.8.4 Fix any compilation errors
  - [ ] 3.9 Commit Phase 3 implementation
    - [ ] 3.9.1 Stage all changes: `git add backend/app/ backend/requirements.txt backend/pyproject.toml backend/migrations/ .env.example`
    - [ ] 3.9.2 Commit: "feat: Phase 3 implementation - migrate to headless Claude Code"
    - [ ] 3.9.3 Include rollback instructions in commit message

- [ ] 4.0 Phase 4: Testing & Validation [EFFORT: HIGH, ~1 week, IF PHASE 1 SUCCEEDS]
  - [ ] 4.1 Update existing agent tests
    - [ ] 4.1.1 Open `backend/tests/test_api_ideas.py`
    - [ ] 4.1.2 Replace Anthropic mocks with ClaudeCodeBackend mocks
    - [ ] 4.1.3 Update mock to use `spec=ClaudeCodeBackend`
    - [ ] 4.1.4 Remove cost_usd assertions from tests
    - [ ] 4.1.5 Run tests: `pytest backend/tests/test_api_ideas.py -v`
    - [ ] 4.1.6 Fix any failures
  - [ ] 4.2 Update discovery agent tests
    - [ ] 4.2.1 Open `backend/tests/test_discovery_agent.py`
    - [ ] 4.2.2 Replace Anthropic mocks with ClaudeCodeBackend mocks
    - [ ] 4.2.3 Remove cost_usd assertions
    - [ ] 4.2.4 Run tests: `pytest backend/tests/test_discovery_agent.py -v`
    - [ ] 4.2.5 Fix any failures
  - [ ] 4.3 Update portfolio analyzer tests
    - [ ] 4.3.1 Open `backend/tests/test_portfolio_analyzer.py`
    - [ ] 4.3.2 Replace Anthropic mocks with ClaudeCodeBackend mocks
    - [ ] 4.3.3 Remove cost_usd assertions
    - [ ] 4.3.4 Run tests: `pytest backend/tests/test_portfolio_analyzer.py -v`
    - [ ] 4.3.5 Fix any failures
  - [ ] 4.4 Create integration tests
    - [ ] 4.4.1 Create `backend/tests/test_headless_claude_integration.py`
    - [ ] 4.4.2 Test: Discovery Agent generates ideas using headless Claude
      - [ ] Instantiate DiscoveryAgent()
      - [ ] Call agent.run()
      - [ ] Assert result['status'] == 'completed'
      - [ ] Assert len(result['ideas']) >= 3
      - [ ] Assert 'cost_usd' not in result
    - [ ] 4.4.3 Test: Portfolio Analyzer generates ideas using headless Claude
      - [ ] Instantiate PortfolioAnalyzerAgent()
      - [ ] Call agent.run()
      - [ ] Assert result['status'] == 'completed'
      - [ ] Assert len(result['ideas']) >= 3
      - [ ] Assert 'cost_usd' not in result
    - [ ] 4.4.4 Run integration tests: `pytest backend/tests/test_headless_claude_integration.py -v`
  - [ ] 4.5 Run full test suite
    - [ ] 4.5.1 Run all tests: `pytest backend/tests/ -v --cov=app --cov-report=term-missing`
    - [ ] 4.5.2 Verify: All tests pass (0 failures)
    - [ ] 4.5.3 Verify: Coverage ≥86%
    - [ ] 4.5.4 Fix any regressions
  - [ ] 4.6 Manual end-to-end testing
    - [ ] 4.6.1 Start backend: `cd backend && uvicorn app.main:app --reload`
    - [ ] 4.6.2 Test Discovery Agent via API: `curl -X POST http://localhost:8000/api/ideas/generate -d '{"agent_type":"discovery"}'`
    - [ ] 4.6.3 Verify ideas generated and stored in database
    - [ ] 4.6.4 Verify no cost_usd field in response
    - [ ] 4.6.5 Test Portfolio Analyzer via API: `curl -X POST http://localhost:8000/api/ideas/generate -d '{"agent_type":"portfolio_analyzer"}'`
    - [ ] 4.6.6 Verify personalized ideas generated
    - [ ] 4.6.7 Stop backend (Ctrl+C)
  - [ ] 4.7 Performance benchmarking
    - [ ] 4.7.1 Create `docs/research/migration-performance.md`
    - [ ] 4.7.2 Measure baseline (if Anthropic API still accessible):
      - [ ] Average Discovery Agent run time
      - [ ] Average Portfolio Analyzer run time
    - [ ] 4.7.3 Measure headless Claude performance:
      - [ ] Average Discovery Agent run time
      - [ ] Average Portfolio Analyzer run time
    - [ ] 4.7.4 Calculate improvement percentage
    - [ ] 4.7.5 Document results (expected: 20-50% faster)
  - [ ] 4.8 Commit Phase 4 testing
    - [ ] 4.8.1 Stage: `git add backend/tests/ docs/research/migration-performance.md`
    - [ ] 4.8.2 Commit: "test: Phase 4 testing and validation for headless AI migration"

- [ ] 5.0 Phase 5: Documentation & Cleanup [EFFORT: MEDIUM, ~2-3 days, IF PHASE 1 SUCCEEDS]
  - [ ] 5.1 Update core documentation
    - [ ] 5.1.1 Update `CLAUDE.md`:
      - [ ] Remove "Cost tracking - All agent runs tracked with $0.50 per-run limit"
      - [ ] Update to "Headless Claude Code for AI agents (no API costs)"
      - [ ] Update tech stack: "Headless Claude Code (local inference)"
    - [ ] 5.1.2 Update `docs/core/ARCHITECTURE.md`:
      - [ ] Update agent system section
      - [ ] Remove Anthropic API references
      - [ ] Add "Headless Claude Code via MCP" or similar
      - [ ] Remove cost tracking mention
      - [ ] Update architecture diagram if needed
    - [ ] 5.1.3 Update `docs/core/API_REFERENCE.md`:
      - [ ] Remove `cost_usd` field from agent_runs response examples
      - [ ] Update agent generation endpoint docs
    - [ ] 5.1.4 Update `docs/core/SETUP.md`:
      - [ ] Remove "Setup Anthropic API key" section
      - [ ] Add "Setup Claude Code" section if needed
      - [ ] Update environment variables list
  - [ ] 5.2 Create migration guide for users
    - [ ] 5.2.1 Create `docs/migration-guide-headless-ai.md`
    - [ ] 5.2.2 Section: "What Changed"
      - [ ] Agents now use headless Claude Code
      - [ ] No API key required
      - [ ] No per-run costs
      - [ ] Faster response times
    - [ ] 5.2.3 Section: "Migration Steps"
      1. Remove ANTHROPIC_API_KEY from environment
      2. Install Claude Code (if not installed)
      3. Run database migration
      4. Restart backend
      5. Test agents
    - [ ] 5.2.4 Section: "Breaking Changes"
      - [ ] cost_usd no longer in agent_runs
      - [ ] API responses no longer include cost
      - [ ] New environment variables if needed
    - [ ] 5.2.5 Section: "Rollback Plan"
      - [ ] Revert to commit: `git revert <MIGRATION_COMMITS>`
      - [ ] Restore database: `cp data/portfolio-ai.db.backup data/portfolio-ai.db`
      - [ ] Reinstall anthropic: `pip install anthropic`
  - [ ] 5.3 Update project status documentation
    - [ ] 5.3.1 Open `docs/core/REFACTOR_STATUS.md`
    - [ ] 5.3.2 Add PRD #0013 to "Recent Updates" section
    - [ ] 5.3.3 Mark PRD #0013 as complete
    - [ ] 5.3.4 Update tech debt section (remove cost tracking from issues)
  - [ ] 5.4 Clean up deprecated code
    - [ ] 5.4.1 Search for remaining Anthropic references: `grep -r "anthropic" backend/app/`
    - [ ] 5.4.2 Remove any commented-out Anthropic code
    - [ ] 5.4.3 Remove API key validation logic if exists
    - [ ] 5.4.4 Archive old code (don't delete, just stop using)
  - [ ] 5.5 Final validation
    - [ ] 5.5.1 Run full test suite: `pytest backend/tests/ -v --cov=app`
    - [ ] 5.5.2 Run linters: `./scripts/lint.sh`
    - [ ] 5.5.3 Start backend and test all agent endpoints
    - [ ] 5.5.4 Verify no Anthropic API calls made (check logs)
    - [ ] 5.5.5 Verify no API costs incurred
  - [ ] 5.6 Final commit
    - [ ] 5.6.1 Stage: `git add docs/ CLAUDE.md`
    - [ ] 5.6.2 Commit: "docs: Phase 5 documentation and cleanup for headless AI migration"
    - [ ] 5.6.3 Update task list status at top of this file to "COMPLETE"

---

## Verification & Production Readiness

**MANDATORY before marking PRD #0013 "COMPLETE ✅":**

### Phase 1 Success Criteria (BLOCKING)
- [ ] **Validation Tests**
  - [ ] All 4 validation tests pass
  - [ ] Tool calling works correctly
  - [ ] Context preservation works
  - [ ] Error handling is graceful
  - [ ] User approves proceeding to Phase 2

### Full Migration Success Criteria (Phase 2-5, conditional)
- [ ] **Functional Completeness**
  - [ ] ClaudeCodeBackend implemented and functional
  - [ ] Anthropic API references removed from codebase
  - [ ] cost_usd column removed from agent_runs table
  - [ ] All agent functionality preserved (Discovery + Portfolio Analyzer)

- [ ] **Test Coverage** (target: 86%+)
  - [ ] All tests passing: `pytest backend/tests/ -v` returns 0 failures
  - [ ] Coverage maintained: ≥86%
  - [ ] Integration tests pass with headless Claude
  - [ ] Manual end-to-end test successful

- [ ] **Type Safety & Code Quality**
  - [ ] Type checking passes: `mypy backend/app/ --strict` returns 0 errors
  - [ ] Linting passes: `./scripts/lint.sh` returns 0 errors
  - [ ] No Anthropic references remain: `grep -r "anthropic" backend/app/` returns nothing

- [ ] **Documentation**
  - [ ] ARCHITECTURE.md updated (agent system section)
  - [ ] API_REFERENCE.md updated (cost_usd removed)
  - [ ] SETUP.md updated (API key removed, Claude Code added)
  - [ ] Migration guide created
  - [ ] REFACTOR_STATUS.md shows PRD #0013 complete

- [ ] **Performance**
  - [ ] Agent response time improved by ≥20% vs Anthropic API
  - [ ] No API costs incurred (zero external API calls)
  - [ ] Agents generate quality ideas (manual verification)

- [ ] **Operational Readiness**
  - [ ] Backend starts successfully: `uvicorn app.main:app --reload`
  - [ ] Agents execute via API: POST /api/ideas/generate
  - [ ] Ideas stored in database correctly
  - [ ] Rollback plan documented and tested

**See**: `docs/core/DEVELOPMENT.md` → "Production Readiness Requirements" for complete checklist
