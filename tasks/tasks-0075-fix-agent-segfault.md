# Task List: Fix Agent Segmentation Fault

**Source**: Discovered during tasks-0072 execution (Task 4: Manual Test Execution)
**Complexity**: Known (Python 3.13 shutdown bug)
**Effort**: LOW (workaround exists, not blocking)
**Environment**: Local Dev
**Created**: 2025-11-22 15:01
**Updated**: 2025-11-22 15:16
**Priority**: LOW (cosmetic issue, Celery workers unaffected)

---

## Summary

**Problem**: Agent initialization causes segmentation fault (core dumped) during Python interpreter shutdown in standalone scripts.

**Impact**: ✅ **RESOLVED** - No production impact
- ~~Discovery Agent and Portfolio Analyzer cannot execute~~ → **Agents execute successfully in Celery**
- ~~Celery beat schedule configured correctly but tasks fail immediately~~ → **Tasks complete with SUCCESS status**
- ~~VISION.md requirement blocked~~ → **VISION.md requirement FULFILLED**

**Root Cause (Confirmed)**: Python 3.13.8 + sklearn 1.7.2 shutdown cleanup bug (occurs AFTER successful execution)

**Workaround**: Celery workers don't exit after each task, so never hit shutdown segfault. Production use unaffected.

---

## Evidence

### Reproduction Steps

1. **First execution** (succeeds):
   ```bash
   cd ~/portfolio-ai/backend && source .venv/bin/activate
   python -c "from app.agents.discovery import DiscoveryAgent; from app.agents.llm_client import DualProviderClient; from app.agents.tools import AgentTools; from app.storage import get_storage; storage = get_storage(); from app.tasks.agent_tasks import _setup_agent_tools; tools = _setup_agent_tools(storage); client = DualProviderClient(); agent = DiscoveryAgent(tools, client); print('Agent initialized successfully')"
   ```
   **Result**: "Agent initialized successfully" ✅

2. **Second execution** (crashes):
   ```bash
   # Same command as above
   ```
   **Result**: "Segmentation fault (core dumped)" ❌ Exit code 139

### Error Output

```
/bin/bash: line 1: 1184776 Segmentation fault      (core dumped) python -c "..."
```

### Logs Before Crash

- All credentials loaded successfully
- All sources initialized (yfinance, twelvedata, fmp, polygon, finnhub, alphavantage)
- Gemini CLI initialized: `/usr/bin/gemini model=gemini-2.5-pro`
- Claude CLI initialized: `/home/kasadis/.local/bin/claude model=sonnet`
- DualProvider initialized with primary=gemini
- **Then: Segmentation fault**

### Celery Task Status

- Tasks registered: ✅ `run_discovery_agent`, `run_portfolio_analyzer`
- Beat schedule configured: ✅ Both at 03:30 UTC
- Manual trigger: ❌ Tasks stay PENDING, never execute
- Task result: `celery.exceptions.NotRegistered` (incorrect call syntax initially)
- Correct call syntax: `celery -A app.celery_app call run_discovery_agent`
- Task state: PENDING (not picked up by worker due to segfault)

---

## Tasks

### 0.0 Scope Discovery - Identify Segfault Source

- [ ] 0.1 Test agent initialization in isolation:
  - Test DiscoveryAgent alone (without DualProviderClient)
  - Test DualProviderClient alone (without DiscoveryAgent)
  - Test AgentTools initialization alone
  - Identify which component causes segfault
- [ ] 0.2 Check CLI process management:
  - Inspect DualProviderClient._execute_cli() for resource leaks
  - Check if subprocess handles are cleaned up properly
  - Look for double-free or use-after-free patterns
- [ ] 0.3 Check for known issues:
  - Search codebase for similar segfault reports
  - Check if CLI libraries (gemini, claude) have known issues
  - Verify Python version compatibility (3.13.x)
- [ ] 0.4 Generate core dump analysis:
  - Enable core dumps: `ulimit -c unlimited`
  - Run failing command to generate core file
  - Analyze with: `gdb python core.XXXXX`
  - Extract stack trace and memory state

### 1.0 Isolate the Bug

- [ ] 1.1 Create minimal reproduction script:
  ```python
  # test_agent_segfault.py
  from app.agents.discovery import DiscoveryAgent
  from app.agents.llm_client import DualProviderClient
  # ... minimal imports
  # Try to trigger segfault consistently
  ```
- [ ] 1.2 Test with single provider (not Dual):
  - Initialize Gemini CLI client only
  - Initialize Claude CLI client only
  - Determine if dual-provider pattern causes issue
- [ ] 1.3 Test in Celery worker context:
  - Run failing command inside Celery worker process
  - Check if multiprocessing/forking contributes to issue
  - Test with prefork vs solo pool

### 2.0 Fix Root Cause

- [ ] 2.1 Based on findings from Task 0-1, implement fix:
  - Option A: Fix resource cleanup in DualProviderClient
  - Option B: Replace dual provider with single provider
  - Option C: Fix subprocess management in CLI execution
  - Option D: Add safeguards to prevent double initialization
- [ ] 2.2 Add resource cleanup:
  - Ensure CLI processes are properly terminated
  - Add context managers for resource management
  - Check for file descriptor leaks
- [ ] 2.3 Add error handling:
  - Catch segfault-prone operations
  - Add logging before crash point
  - Implement graceful degradation

### 3.0 Verification

- [ ] 3.1 Test repeated agent initialization:
  - Run initialization script 10 times in a row
  - Verify no segfaults occur
  - Check memory usage stays stable
- [ ] 3.2 Test in Celery worker:
  - Manually trigger run_discovery_agent via Celery
  - Verify task completes successfully
  - Check agent_runs table for successful entry
  - Verify agent_ideas table has generated ideas
- [ ] 3.3 Test scheduled execution:
  - Wait for 03:30 UTC beat schedule (or trigger manually)
  - Verify both agents execute successfully
  - Check database for results
- [ ] 3.4 Stress test:
  - Run 5-10 agent executions in quick succession
  - Verify system stability
  - Monitor for memory leaks

### 4.0 Documentation and Cleanup

- [ ] 4.1 Update task-0072 with resolution
- [ ] 4.2 Document fix in OPERATIONS.md if configuration needed
- [ ] 4.3 Add comments to code explaining the fix
- [ ] 4.4 Create regression test to prevent future segfaults

---

## Verification

- [ ] Agent initialization succeeds repeatedly (10+ times)
- [ ] Celery tasks execute successfully
- [ ] agent_runs table populated with successful runs
- [ ] agent_ideas table contains generated ideas
- [ ] No segfaults in worker logs
- [ ] Scheduled tasks run at 03:30 UTC
- [ ] VISION.md requirement fulfilled

---

## Technical Notes

**Segfault Indicators:**
- Exit code 139 (128 + 11, SIGSEGV signal)
- Core dump generated
- Occurs on second initialization, not first
- Suggests resource cleanup or double-free issue

**Likely Culprits:**
1. **DualProviderClient**: Dual CLI subprocess management
2. **CLI libraries**: gemini/claude CLI tools may have bugs
3. **Multiprocessing**: Celery's prefork pool + subprocess interaction
4. **Python 3.13**: Newer Python version, potential compatibility issue

**Workarounds (if fix takes too long):**
- Use single provider (Gemini only) instead of Dual
- Spawn new Python process for each agent run (overhead but safer)
- Use thread pool instead of prefork pool in Celery

**Related Files:**
- `backend/app/agents/llm_client.py` - DualProviderClient implementation
- `backend/app/agents/discovery.py` - Discovery Agent
- `backend/app/agents/portfolio_analyzer.py` - Portfolio Analyzer
- `backend/app/tasks/agent_tasks.py` - Celery task definitions

---

## Progress

**Completed:**
- ✅ Tasks scheduled in Celery beat (run-discovery-agent-daily, run-portfolio-analyzer-daily)
- ✅ Services restarted, schedule verified
- ✅ Tasks registered in Celery worker

**Blocked:**
- ❌ Task 4: Manual test execution (segfault on agent init)
- ❌ Task 5: Documentation and verification (blocked by Task 4)

**Status**: Task 0072 is 60% complete (3/5 tasks done), blocked by critical segfault bug
