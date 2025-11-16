# Task List: Fix AI Analyzer Blocker (CRITICAL)

**Source**: Code review - Cloud agent analysis (2025-11-15)
**Complexity**: Medium
**Effort**: MEDIUM (2-3 hours)
**Environment**: Local Dev
**Created**: 2025-11-15
**Completed**: 2025-11-16 11:45
**Status**: ✅ COMPLETE
**Commit**: 29191cb (feat: Migrate AI analyzer from Anthropic API to Claude CLI)

---

## Summary

**Goal**: Fix broken `ai_analyzer.py` that currently fails silently due to missing Anthropic API key. Migrate to Claude Code CLI adapter to enable zero-cost autonomous capability analysis.

**Approach**: Replace direct Anthropic API usage with Claude Code CLI subprocess execution, maintaining existing interface and database integration.

**Scope Discovery**: Not required (single file, well-scoped)

**Dependencies (Downstream)**:
- **Task 0062 Task 4.0**: AI-Powered Gap Analysis (BLOCKED by this)
- **Scheduled task**: `analyze_capabilities` (daily 03:15 UTC) - currently failing silently
- **Task 0060**: Full CLI integration work (this is quick-win subset)

**Impact**:
- ✅ Unblocks Task 0062 Task 4.0 (AI gap analysis)
- ✅ Enables daily automated capability analysis (zero API cost)
- ✅ Fixes silent failure in production scheduled tasks
- ✅ Foundation for Task 0060 CLI migration

---

## Problem Statement

**Current State** (2025-11-15):
- File: `backend/app/services/ai_analyzer.py` (467 lines)
- Lines 46-51: Checks for `ANTHROPIC_API_KEY`, sets `self.client = None` if missing
- Lines 63-65: Returns empty list when no client → **SILENT FAILURE**
- Lines 309-348: Uses `Anthropic()` client directly for API calls
- Celery task `analyze_capabilities()` runs daily but produces zero insights

**Root Cause**:
- No Anthropic API key configured in environment
- Code gracefully degrades to no-op instead of failing loudly
- Scheduled task appears successful but does nothing

**Verification**:
```bash
# Check current behavior
cd ~/portfolio-ai/backend
source .venv/bin/activate
python -c "from app.services.ai_analyzer import CapabilityAnalyzer; from app.storage.connection import get_connection_manager; analyzer = CapabilityAnalyzer(get_connection_manager()); print(f'Enabled: {analyzer.enabled}, Has client: {analyzer.client is not None}')"

# Expected output: Enabled: True, Has client: False
# This confirms the blocker
```

**Files Affected**:
1. `backend/app/services/ai_analyzer.py` (467 lines) - Main refactor
2. `backend/app/tasks/capability_tasks.py` (line 14, 133, 136) - Imports ai_analyzer
3. Tests referencing ai_analyzer (if any)

---

## Tasks

### 1.0 Pre-Implementation Analysis

- [ ] 1.1 Verify current failure state
  - Run verification command above to confirm `client = None`
  - Check `capability_insights` table for zero rows (confirms silent failure)
  - Query: `SELECT COUNT(*) FROM capability_insights;` (expected: 0)
  - Review Celery logs for `analyze_capabilities` task (should see "ai_analysis_skipped")

- [ ] 1.2 Review ai_analyzer.py interface contract
  - Document all public methods: `__init__()`, `analyze()`, `load_capabilities()`, `build_prompt()`, `call_ai_api()`, `parse_ai_response()`, `save_insights()`
  - Identify which methods need changes: Only `__init__()` and `call_ai_api()`
  - Verify database schema for `capability_insights` table
  - Confirm Celery task `analyze_capabilities` imports and usage (line 133-136 in capability_tasks.py)

- [ ] 1.3 Verify Claude Code CLI availability
  - Check if `claude` CLI is installed: `which claude`
  - Test basic invocation: `claude --version`
  - Test headless mode: `echo "test" | claude -p "Say hello" --output-format json --permission-mode auto`
  - Document CLI path (expected: `/usr/local/bin/claude` or similar)

### 2.0 Implement CLI Adapter

- [ ] 2.1 Refactor `__init__()` method to use CLI detection
  - Remove: `api_key = os.getenv("ANTHROPIC_API_KEY")`
  - Remove: `self.client = Anthropic(api_key=api_key) if api_key else None`
  - Add: `self.cli_path = self._find_claude_cli()`
  - Add: `self._verify_cli_available()` method
  - Keep: `self.enabled`, `self.model`, `self.confidence_threshold` (no changes)
  - Update logging: Change "anthropic_api_key_missing" to "claude_cli_not_found"

- [ ] 2.2 Add CLI detection helper method
  ```python
  def _find_claude_cli(self) -> str:
      """Find Claude CLI executable path.

      Checks:
      1. Environment variable CLAUDE_CLI_PATH
      2. Standard locations: /usr/local/bin/claude, /usr/bin/claude
      3. PATH search via shutil.which()

      Returns:
          Path to claude CLI executable

      Raises:
          FileNotFoundError: If claude CLI not found
      """
      # Implementation here
  ```

- [ ] 2.3 Refactor `call_ai_api()` method to use CLI
  - Remove: Lines 308-348 (Anthropic API call)
  - Add: CLI subprocess execution with timeout (300 seconds)
  - Use: `subprocess.run([self.cli_path, "-p", prompt, "--output-format", "json", "--model", model_id, "--permission-mode", "auto"], capture_output=True, text=True, timeout=300, check=True)`
  - Parse: JSON stdout to extract `response` field
  - Handle: `subprocess.TimeoutExpired`, `subprocess.CalledProcessError`, `json.JSONDecodeError`
  - Log: CLI command, duration, exit code, stderr (if failed)
  - Map: Model names to CLI equivalents ("claude-sonnet-4.5" → CLI model flag)

- [ ] 2.4 Update error handling and logging
  - Replace: "calling_claude_api" log → "calling_claude_cli"
  - Replace: "claude_api_success" → "claude_cli_success"
  - Replace: "claude_api_failed" → "claude_cli_failed"
  - Add: New log fields: `cli_command`, `exit_code`, `stderr_preview`
  - Update: `analyze()` method error handling (lines 101-103) to handle CLI errors

### 3.0 Testing & Verification

- [ ] 3.1 Create unit test for CLI detection
  - Test: `_find_claude_cli()` finds CLI when available
  - Test: `_find_claude_cli()` raises error when not found
  - Test: `_find_claude_cli()` respects CLAUDE_CLI_PATH env var
  - File: `backend/tests/unit/services/test_ai_analyzer_cli.py` (new file)

- [ ] 3.2 Create integration test for full analysis flow
  - Test: `analyze()` executes CLI and parses response
  - Test: `analyze()` saves insights to database
  - Test: CLI timeout handling (mock slow CLI with sleep)
  - Test: CLI error handling (mock failed CLI with non-zero exit)
  - Mock: Claude CLI response with sample insights JSON
  - File: `backend/tests/integration/services/test_ai_analyzer_integration.py` (new file)

- [ ] 3.3 Manual testing with real CLI
  - Run: `analyze()` method manually from Python REPL
  - Verify: Claude CLI executes and returns insights
  - Check: `capability_insights` table has new rows
  - Verify: Insights have correct structure (all required fields)
  - Test: Confidence filtering (insights with confidence < 0.70 excluded)

- [ ] 3.4 Test scheduled Celery task
  - Trigger: `analyze_capabilities` task manually via Celery
  - Command: `cd ~/portfolio-ai/backend && source .venv/bin/activate && celery -A app.celery_app call app.tasks.capability_tasks.analyze_capabilities`
  - Verify: Task succeeds and logs "ai_capability_analysis_complete"
  - Check: `capability_insights` table updated with new insights
  - Verify: No "ai_analysis_skipped" logs

### 4.0 Update Dependencies & Documentation

- [ ] 4.1 Update import statements (if needed)
  - Check: No changes needed (existing imports still work)
  - Verify: `from anthropic import Anthropic` can be removed (line 14)
  - Update: Type hints if `Anthropic` type removed

- [ ] 4.2 Update configuration documentation
  - File: `backend/app/config/capabilities_config.yaml` (if exists)
  - Update: AI analysis section to document CLI requirement
  - Add: Note about CLAUDE_CLI_PATH environment variable
  - Document: CLI model mapping ("claude-sonnet-4.5" config → CLI model flag)

- [ ] 4.3 Update capability_tasks.py documentation
  - File: `backend/app/tasks/capability_tasks.py`
  - Update: Docstring for `analyze_capabilities()` task (lines 109-123)
  - Add: Note about CLI requirement and zero API cost
  - Document: Typical execution time with CLI (vs API)

- [ ] 4.4 Update ARCHITECTURE.md or system documentation
  - File: `docs/core/ARCHITECTURE.md` (if capability analysis documented)
  - Update: Section on capability insights to mention CLI execution
  - Note: Zero per-token cost benefit
  - Document: CLI vs API trade-offs (latency, cost, availability)

### 5.0 Deployment & Rollback Plan

- [ ] 5.1 Verify Claude CLI installed in production
  - Check: Claude CLI available on production server
  - Verify: Version compatibility (document required version)
  - Test: CLI executes successfully in production environment
  - Document: Installation steps if CLI missing

- [ ] 5.2 Update environment variables
  - Add: `CLAUDE_CLI_PATH` to `.env.example` (optional, for custom paths)
  - Document: Default CLI paths checked by code
  - Note: No API key required anymore

- [ ] 5.3 Create rollback plan
  - Document: Steps to revert to API-based implementation if CLI fails
  - Preserve: Original `call_ai_api()` implementation in code comments or backup
  - Test: Can quickly restore API-based code if needed
  - Note: Rollback requires setting ANTHROPIC_API_KEY again

- [ ] 5.4 Monitor first scheduled run
  - Wait: For next scheduled `analyze_capabilities` task (03:15 UTC)
  - Verify: Task completes successfully
  - Check: Insights generated and saved
  - Monitor: Celery worker logs for errors
  - Alert: User if task fails

---

## Verification

- [ ] **Functional**: AI analyzer produces insights via CLI
  - [ ] `analyze()` method executes without errors
  - [ ] Claude CLI invoked with correct arguments
  - [ ] Insights parsed and saved to `capability_insights` table
  - [ ] Confidence filtering works (≥0.70 threshold)

- [ ] **Tests**: All new tests passing
  - [ ] Unit tests: `pytest tests/unit/services/test_ai_analyzer_cli.py -v`
  - [ ] Integration tests: `pytest tests/integration/services/test_ai_analyzer_integration.py -v`
  - [ ] Existing tests: No regressions in other tests

- [ ] **Quality**: Code quality checks pass
  - [ ] `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
  - [ ] No new type errors: `cd ~/portfolio-ai/backend && mypy app/services/ai_analyzer.py --strict`
  - [ ] File size: Still under 500 lines (currently 467)

- [ ] **Scheduled Task**: Celery task works
  - [ ] Manual trigger: `celery -A app.celery_app call app.tasks.capability_tasks.analyze_capabilities` succeeds
  - [ ] Next scheduled run: Task completes at 03:15 UTC
  - [ ] Logs show: "ai_capability_analysis_complete" with insight count

- [ ] **Downstream**: Unblocks dependent work
  - [ ] Task 0062 Task 4.0 can now proceed
  - [ ] Gap analysis workflows can use AI analyzer

- [ ] **Documentation**: All docs updated
  - [ ] Configuration docs mention CLI requirement
  - [ ] Task docstrings updated
  - [ ] ARCHITECTURE.md updated (if applicable)
  - [ ] Rollback plan documented

---

## Success Criteria

1. **Zero silent failures**: AI analyzer either succeeds or fails loudly (no `client = None` silent degradation)
2. **Insights generated**: `capability_insights` table populated with AI-generated insights
3. **Scheduled task works**: `analyze_capabilities` runs successfully at 03:15 UTC daily
4. **Zero API costs**: No Anthropic API calls (all via CLI)
5. **Task 0062 unblocked**: AI gap analysis can use `CapabilityAnalyzer`
6. **Tests passing**: All new unit/integration tests green
7. **No regressions**: Existing tests still pass

---

## Notes

**Why CLI over API?**
- Zero per-token costs (API charges per token, CLI is free)
- Supports autonomous daily analysis without budget concerns
- Enables multi-agent workflows without cost tracking overhead
- Foundation for Task 0060 full CLI migration

**API vs CLI Trade-offs**:
- **Latency**: CLI slightly slower (subprocess overhead ~100-200ms)
- **Complexity**: CLI adds subprocess management (timeouts, stderr handling)
- **Cost**: CLI is free, API costs ~$0.10-0.50 per analysis
- **Reliability**: Both high, but CLI depends on local installation

**Estimated Effort Breakdown**:
- Analysis & planning: 30 minutes
- Implementation: 60 minutes
- Testing: 45 minutes
- Documentation: 15 minutes
- **Total**: 2.5 hours

**Related Work**:
- Task 0060: Full CLI integration (agents, all API usage)
- Task 0062 Task 4.0: AI gap analysis (depends on this)
- PRD #0024: Code quality refactoring (related quality effort)
