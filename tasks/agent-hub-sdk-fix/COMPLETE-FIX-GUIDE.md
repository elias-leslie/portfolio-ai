# Complete Agent Hub SDK & agent_slug Fix Guide
**For Portfolio-AI and SummitFlow**

---

## Executive Summary

### Issues Identified

| Issue | Portfolio-AI | SummitFlow | Severity |
|-------|--------------|------------|----------|
| **SDK Not in Dependencies** | ❌ Dev mode only | ✅ Correct | 🔴 Critical |
| **Missing agent_slug Support** | ❌ Zero usage | ❌ Zero usage | 🔴 Critical |
| **Wrong Model Syntax** | N/A | ❌ Uses "agent:slug" | 🟡 Medium |
| **mypy Ignores** | ❌ Has ignores | ✅ No ignores | 🟡 Medium |

### What's Broken

**Portfolio-AI:**
- SDK installed in dev mode, not declared in `pyproject.toml`
- Zero `agent_slug` usage across 9 agent invocation points
- mypy ignores hiding import problems

**SummitFlow:**
- Uses "agent:coder" as `model` parameter (wrong!)
- Should use `agent_slug="coder"` parameter instead
- Missing mandate injection, fallback chains, agent tracking

### Benefits After Fix

✅ **Agent-specific configs** - Load specialized prompts/settings per agent type
✅ **Mandate injection** - Automatic context/rules via semantic search
✅ **Fallback chains** - Auto-retry with different models on failure
✅ **Proper tracking** - Cost attribution per agent type
✅ **Type safety** - Full mypy validation

---

## Part 1: Portfolio-AI Fixes

### 1.1 SDK Dependency (Subtask 1.1)

**File:** `backend/pyproject.toml`

**Add to dependencies array:**
```toml
[project]
dependencies = [
    # ... existing deps ...
    "agent-hub-client @ file:///home/kasadis/agent-hub/packages/agent-hub-client",
]
```

**Remove mypy ignore:**
```toml
# DELETE these lines (around line 189-190):
[[tool.mypy.overrides]]
module = ["agent_hub", "agent_hub.*"]
ignore_missing_imports = true  # ← DELETE THIS
```

**Install:**
```bash
cd backend
.venv/bin/pip install -e .
```

**Verify:**
```bash
cd backend
.venv/bin/pip show agent-hub-client | grep Location
# Should show: /home/kasadis/agent-hub/packages/agent-hub-client

.venv/bin/python -c 'from agent_hub import AgentHubClient; print("Import OK")'
# Should print: Import OK
```

---

### 1.2 Add agent_slug to AgentHubAPIClient (Subtask 2.1)

**File:** `backend/app/agents/clients/agent_hub_client.py`

**Update generate() signature (around line 112):**
```python
def generate(
    self,
    prompt: str,
    system: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    purpose: str | None = None,
    agent_slug: str | None = None,  # ← ADD THIS
    **kwargs: Any,
) -> LLMResponse:
```

**Update docstring:**
```python
"""Generate completion using Agent Hub API.

Args:
    prompt: User prompt
    system: System prompt (optional)
    tools: Tool definitions for function calling
    max_tokens: Maximum tokens
    temperature: Sampling temperature
    purpose: Purpose of this request for session tracking
    agent_slug: Agent slug for routing (e.g., "discovery", "coder")  # ← ADD THIS
    **kwargs: Additional options

Returns:
    LLMResponse with completion
```

**Pass to SDK (around line 149):**
```python
response = self._client.complete(
    model=self.model,
    messages=messages,
    max_tokens=max_tokens,
    temperature=temperature,
    tools=tools,
    project_id="portfolio-ai",
    purpose=purpose,
    agent_slug=agent_slug,  # ← ADD THIS
)
```

---

### 1.3 Discovery Agent & Portfolio Analyzer (Subtask 3.1)

**Discovery Agent Implementation Options:**

**Option A: Pass agent_slug through base Agent class**

File: `backend/app/agents/base.py`

```python
class Agent:
    def __init__(
        self,
        storage: PortfolioStorage,
        tools: list[Tool],
        llm_client: LLMClient,
        agent_slug: str | None = None,  # ← ADD THIS
    ) -> None:
        self.storage = storage
        self.tools = tools
        self.llm_client = llm_client
        self.agent_slug = agent_slug  # ← ADD THIS
```

Then in `backend/app/agents/llm_flow.py` (around line where generate is called):
```python
response: LLMResponse = self.llm_client.generate(
    prompt=prompt,
    system=system_prompt,
    temperature=temperature,
    max_tokens=max_tokens,
    purpose=purpose,
    agent_slug=self.agent_slug,  # ← ADD THIS
)
```

**Option B: Set agent_slug in subclass constructors**

File: `backend/app/agents/discovery.py`
```python
class DiscoveryAgent(Agent):
    def __init__(
        self,
        storage: PortfolioStorage,
        tools: list[Tool],
        llm_client: LLMClient,
    ) -> None:
        super().__init__(
            storage=storage,
            tools=tools,
            llm_client=llm_client,
            agent_slug="discovery",  # ← ADD THIS
        )
```

File: `backend/app/agents/portfolio_analyzer.py`
```python
class PortfolioAnalyzerAgent(Agent):
    def __init__(
        self,
        storage: PortfolioStorage,
        tools: list[Tool],
        llm_client: LLMClient,
    ) -> None:
        super().__init__(
            storage=storage,
            tools=tools,
            llm_client=llm_client,
            agent_slug="portfolio_analyzer",  # ← ADD THIS
        )
```

**Recommended: Option B** (cleaner, agent-specific)

---

### 1.4 Strategy Reviewer (Subtask 4.1)

**File:** `backend/app/agents/strategy_reviewer.py`

**Update _ensure_client() method (around line 45):**
```python
def _ensure_client(self, name: str, model: str) -> AgentHubAPIClient:
    """Lazy-load client for given model."""
    if name not in self._clients:
        self._clients[name] = AgentHubAPIClient(model=model)
        # Set agent_slug attribute
        self._clients[name].agent_slug = "strategy_reviewer"  # ← ADD THIS
    return self._clients[name]
```

**OR update generate calls (around line 80):**
```python
response: LLMResponse = await asyncio.to_thread(
    client.generate,
    prompt=prompt,
    system=get_system_prompt(self.storage),
    max_tokens=GUARDRAILS["max_tokens"],
    temperature=GUARDRAILS["temperature"],
    agent_slug="strategy_reviewer",  # ← ADD THIS
)
```

---

### 1.5 Multi-Reviewer (Subtask 4.1)

**File:** `backend/app/agents/multi_reviewer.py`

**Update _ensure_client() method (around line 90):**
```python
def _ensure_client(self, name: str, model: str) -> AgentHubAPIClient:
    """Lazy-load client for given model."""
    if name not in self._clients:
        self._clients[name] = AgentHubAPIClient(model=model)
    return self._clients[name]
```

**Update _generate_review() method (around line 110):**
```python
async def _generate_review(
    self, reviewer_name: str, prompt: str, rationale: str
) -> dict[str, Any]:
    """Generate a review using specified reviewer."""
    try:
        client = self._ensure_client(reviewer_name, self._models[reviewer_name])

        # Determine agent_slug based on reviewer
        agent_slug = f"multi_reviewer_{reviewer_name}"  # "multi_reviewer_gemini" or "multi_reviewer_claude"

        response: LLMResponse = await asyncio.to_thread(
            client.generate,
            prompt=prompt,
            system=REVIEW_SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.3,
            purpose="signal_review",
            agent_slug=agent_slug,  # ← ADD THIS
        )
```

---

### 1.6 Strategy Evolution & Services (Subtask 5.1)

**File:** `backend/app/agents/strategy_evolution_agent.py`

**Update agent instantiation (around line 170):**
```python
def __init__(self) -> None:
    """Initialize evolution agent."""
    from .llm_client import AgentHubAPIClient
    from ..constants import CLAUDE_SONNET

    self._client = AgentHubAPIClient(model=CLAUDE_SONNET)
    self._client.agent_slug = "strategy_evolution"  # ← ADD THIS
```

**OR update generate calls:**
```python
response = self._client.generate(
    prompt=prompt,
    system=system_prompt,
    max_tokens=2048,
    temperature=0.7,
    agent_slug="strategy_evolution",  # ← ADD THIS
)
```

**File:** `backend/app/services/cross_validation.py`

**Update constructor (around line 30):**
```python
def __init__(self) -> None:
    """Initialize cross-validation service."""
    self._generator = AgentHubAPIClient(model=GEMINI_FLASH)
    self._generator.agent_slug = "cross_validator_gemini"  # ← ADD THIS

    self._validator = AgentHubAPIClient(model=CLAUDE_SONNET)
    self._validator.agent_slug = "cross_validator_claude"  # ← ADD THIS
```

**File:** `backend/app/services/thesis_service.py`

**Update generate calls (around line 85 and 130):**
```python
# Gemini generation
response = llm.generate(
    prompt=prompt,
    system=system,
    max_tokens=4096,
    temperature=0.7,
    purpose="thesis_generation",
    agent_slug="thesis_generator",  # ← ADD THIS
)

# Claude validation
response = claude.generate(
    prompt=prompt,
    system=system,
    max_tokens=2048,
    temperature=0.3,
    purpose="thesis_validation",
    agent_slug="thesis_validator",  # ← ADD THIS
)
```

---

### 1.7 Workflow Tasks (Subtask 6.1)

**File:** `backend/app/agents/llm_client.py`

**Update DualProviderClient.generate() (around line 420):**
```python
def generate(
    self,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    purpose: str | None = None,
    task_id: str | None = None,
    agent_slug: str | None = None,  # ← ADD THIS
    **kwargs: Any,
) -> LLMResponse:
    """Generate using primary provider via Agent Hub."""
    self._ensure_initialized()
    if not self._client:
        raise RuntimeError("Client not initialized")

    return self._client.generate(
        prompt=prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        purpose=purpose,
        task_id=task_id,
        agent_slug=agent_slug,  # ← ADD THIS
        **kwargs,
    )
```

**File:** `backend/app/tasks/workflow_tasks.py`

**Update gap analysis workflow (around line 50):**
```python
response = client.generate(
    prompt=prompt,
    system=system,
    purpose=purpose,
    agent_slug="gap_analysis",  # ← ADD THIS
)
```

---

### 1.8 Deploy & Verify (Subtask 7.1)

**Deploy:**
```bash
cd /home/kasadis/portfolio-ai
./scripts/rebuild.sh --backend
```

**Verify agent_slug count:**
```bash
rg 'agent_slug=' backend/app/agents backend/app/services backend/app/tasks --type py | wc -l
# Expected: 9
```

**Verify imports:**
```bash
cd backend
.venv/bin/python -c 'from agent_hub import AgentHubClient; print("Import successful")'
# Expected: Import successful
```

**Verify types:**
```bash
cd backend
.venv/bin/mypy app/agents/clients/agent_hub_client.py --strict
# Expected: Success: no issues found
```

**Verify health:**
```bash
curl -s http://localhost:8000/health | rg -q '"status":"healthy"' && echo 'Backend healthy'
# Expected: Backend healthy
```

---

## Part 2: SummitFlow Fixes

### 2.1 Issue Analysis

**Current (WRONG):**
```python
# constants.py
AGENT_WORKER = "agent:coder"

# Usage
client = AgentHubLLMClient(model="agent:coder")
response = client.generate(...)
# Internally calls: client.complete(model="agent:coder", ...)  ❌ WRONG
```

**What Happens:**
- Agent Hub treats "agent:coder" as unknown model string
- Falls back to default Claude provider detection
- **NO** mandate injection
- **NO** fallback chains
- **NO** agent tracking

**Correct:**
```python
# Usage
client = AgentHubLLMClient(model=CLAUDE_SONNET)  # or None
response = client.generate(..., agent_slug="coder")
# Internally calls: client.complete(agent_slug="coder", ...)  ✅ CORRECT
```

---

### 2.2 AgentHubLLMClient Fix

**File:** `summitflow/backend/app/services/agent_hub_client.py`

**Update generate() signature (line 275):**
```python
def generate(
    self,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    purpose: str | None = None,
    task_id: str | None = None,
    agent_slug: str | None = None,  # ← ADD THIS
    **kwargs: Any,
) -> LLMResponse:
```

**Update docstring:**
```python
"""Generate completion via Agent Hub.

Args:
    prompt: User prompt
    system: System prompt (optional)
    max_tokens: Maximum tokens to generate
    temperature: Sampling temperature
    purpose: Purpose of this request (task_enrichment, code_generation, etc.)
    task_id: Task ID for session linkage (stored as external_id in Agent Hub)
    agent_slug: Agent slug for routing (e.g., "coder", "supervisor")  # ← ADD THIS
    **kwargs: Additional options (session_id, enable_caching, etc.)
```

**Update complete() call (line 311):**
```python
response = client.complete(
    model=self.model,
    messages=messages,
    max_tokens=max_tokens,
    temperature=temperature,
    project_id=self.project_id,
    session_id=kwargs.get("session_id"),
    purpose=purpose,
    external_id=task_id,
    enable_caching=kwargs.get("enable_caching", True),
    agent_slug=agent_slug,  # ← ADD THIS
)
```

---

### 2.3 DualProviderClient Fix

**File:** `summitflow/backend/app/services/agent_hub_client.py`

**Update generate() signature (line 420):**
```python
def generate(
    self,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    purpose: str | None = None,
    task_id: str | None = None,
    agent_slug: str | None = None,  # ← ADD THIS
    **kwargs: Any,
) -> LLMResponse:
```

**Update client.generate() call (line 438):**
```python
return self._client.generate(
    prompt=prompt,
    system=system,
    max_tokens=max_tokens,
    temperature=temperature,
    purpose=purpose,
    task_id=task_id,
    agent_slug=agent_slug,  # ← ADD THIS
    **kwargs,
)
```

---

### 2.4 Constants Refactor

**File:** `summitflow/backend/app/constants.py`

**REPLACE agent constants (lines 28-34):**
```python
# BEFORE (delete these):
AGENT_WORKER = "agent:coder"
AGENT_SUPERVISOR = "agent:supervisor"
AGENT_REVIEWER = "agent:reviewer"
AGENT_FIXER = "agent:fixer"
AGENT_QA = "agent:qa"

# AFTER (replace with):
# Agent slugs for Agent Hub routing
# These should be passed as agent_slug parameter, NOT as model
AGENT_SLUG_CODER = "coder"
AGENT_SLUG_SUPERVISOR = "supervisor"
AGENT_SLUG_REVIEWER = "reviewer"
AGENT_SLUG_FIXER = "fixer"
AGENT_SLUG_QA = "qa"

# Models to use with agents (can be None to use agent's default)
AGENT_CODER_MODEL = GEMINI_FLASH  # Fast for code generation
AGENT_SUPERVISOR_MODEL = CLAUDE_SONNET  # Sonnet for coordination
AGENT_REVIEWER_MODEL = CLAUDE_OPUS  # Opus for thorough review
AGENT_FIXER_MODEL = CLAUDE_SONNET  # Sonnet for error fixing
AGENT_QA_MODEL = CLAUDE_OPUS  # Opus for quality review
```

**Update VALID_AGENT_MODELS (remove it):**
```python
# DELETE this entire section (no longer needed):
VALID_AGENT_MODELS = (
    AGENT_WORKER,
    AGENT_SUPERVISOR,
    AGENT_REVIEWER,
    AGENT_FIXER,
    AGENT_QA,
)
```

---

### 2.5 Update All Usage Sites

**Find all usages:**
```bash
cd /home/kasadis/summitflow
rg "AGENT_WORKER|AGENT_SUPERVISOR|AGENT_REVIEWER|AGENT_FIXER|AGENT_QA" backend/app --type py
```

**Pattern to replace:**

**BEFORE:**
```python
from ..constants import AGENT_WORKER

client = get_agent("claude", model=AGENT_WORKER)
response = client.generate(
    prompt=prompt,
    system=system,
)
```

**AFTER:**
```python
from ..constants import AGENT_SLUG_CODER, AGENT_CODER_MODEL

client = get_agent("claude", model=AGENT_CODER_MODEL)
response = client.generate(
    prompt=prompt,
    system=system,
    agent_slug=AGENT_SLUG_CODER,  # ← ADD THIS
)
```

**Common locations to update:**
1. `backend/app/services/orchestrator.py` - Uses AGENT_WORKER, AGENT_SUPERVISOR
2. `backend/app/tasks/ai_review.py` - Uses AGENT_REVIEWER
3. Any other files found in grep above

---

### 2.6 Orchestrator Specific Changes

**File:** `summitflow/backend/app/services/orchestrator.py`

**Update imports:**
```python
from ..constants import (
    AGENT_SLUG_CODER,
    AGENT_SLUG_SUPERVISOR,
    AGENT_CODER_MODEL,
    AGENT_SUPERVISOR_MODEL,
)
```

**Update model change calls (around line 150):**
```python
# BEFORE:
await self._send_model_change(AGENT_WORKER, "Starting with agent:coder worker")

# AFTER:
await self._send_model_change(
    AGENT_CODER_MODEL,
    f"Starting with coder agent (slug: {AGENT_SLUG_CODER})"
)
```

**Update LLM client calls:**
Wherever you're calling `client.generate()`, add:
```python
agent_slug=AGENT_SLUG_CODER  # or AGENT_SLUG_SUPERVISOR
```

---

### 2.7 AI Review Task

**File:** `summitflow/backend/app/tasks/ai_review.py`

**BEFORE:**
```python
reviewer = get_agent("claude", model=AGENT_REVIEWER)

response = reviewer.send_message(prompt)
```

**AFTER:**
```python
from ..constants import AGENT_SLUG_REVIEWER, AGENT_REVIEWER_MODEL

reviewer = get_agent("claude", model=AGENT_REVIEWER_MODEL)

response = reviewer.generate(
    prompt=prompt,
    agent_slug=AGENT_SLUG_REVIEWER,
)
# Note: If using send_message(), update it to pass agent_slug internally
```

---

### 2.8 Verify Agents Exist in Agent Hub

**Check Agent Hub database:**
```bash
# Connect to Agent Hub backend
curl -s http://localhost:8003/api/agents | jq '.agents[].slug'

# Expected output should include:
# "coder"
# "supervisor"
# "reviewer"
# "fixer"
# "qa"
```

**If agents don't exist, seed them:**
```bash
cd /home/kasadis/agent-hub/backend
python scripts/seed_agents.py
```

**Verify agent configs:**
```bash
# Check coder agent
curl -s http://localhost:8003/api/agents/coder | jq '{slug, primary_model, fallback_models, system_prompt_preview: (.system_prompt[:100])}'

# Verify has:
# - primary_model (e.g., "gemini-3-flash-preview")
# - fallback_models array
# - system_prompt with coding instructions
```

---

### 2.9 Deploy & Test

**Deploy backend:**
```bash
cd /home/kasadis/summitflow
./scripts/rebuild.sh --backend
```

**Verify agent_slug usage:**
```bash
rg 'agent_slug=' backend/app --type py | wc -l
# Expected: At least 3-5 (orchestrator, ai_review, etc.)
```

**Test agent routing:**
```bash
# Create a test completion with agent_slug
curl -X POST http://localhost:8003/api/complete \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a hello world function"}],
    "project_id": "summitflow",
    "agent_slug": "coder",
    "max_tokens": 1000
  }' | jq '{agent_used, model_used, content_preview: (.content[:100])}'

# Verify response includes:
# - agent_used: "coder"
# - model_used: actual model (e.g., "gemini-3-flash-preview")
# - content: actual generated code
```

**Check mandate injection:**
```bash
# Check Agent Hub logs for mandate injection
journalctl --user -u agent-hub-backend -n 50 | rg "mandate|inject"
# Should see: "Injected X mandates for agent: coder"
```

---

## Part 3: Verification Checklist

### Portfolio-AI ✓

```bash
cd /home/kasadis/portfolio-ai

# 1. SDK installed
cd backend && .venv/bin/pip show agent-hub-client | rg "Name: agent-hub-client"

# 2. Imports work
cd backend && .venv/bin/python -c 'from agent_hub import AgentHubClient; print("OK")'

# 3. Types pass
cd backend && .venv/bin/mypy app/agents/clients/agent_hub_client.py --strict | rg "Success"

# 4. agent_slug count
rg 'agent_slug=' backend/app --type py | wc -l
# Expected: 9

# 5. No mypy ignores for agent_hub
rg 'agent_hub.*ignore' backend/pyproject.toml
# Expected: no results

# 6. Backend healthy
curl -s http://localhost:8000/health | rg '"status":"healthy"'

# 7. File URL dependency
rg 'agent-hub-client.*file://' backend/pyproject.toml
```

### SummitFlow ✓

```bash
cd /home/kasadis/summitflow

# 1. Updated constants
rg "AGENT_SLUG_" backend/app/constants.py | wc -l
# Expected: At least 5 (one per agent)

# 2. No old AGENT_WORKER pattern
rg 'AGENT_WORKER.*=.*"agent:' backend/app/constants.py
# Expected: no results

# 3. agent_slug usage
rg 'agent_slug=' backend/app --type py | wc -l
# Expected: At least 3-5

# 4. Generate() has agent_slug param
rg 'def generate.*agent_slug' backend/app/services/agent_hub_client.py
# Expected: 2 results (AgentHubLLMClient and DualProviderClient)

# 5. Backend healthy
curl -s http://localhost:8001/health | rg '"status":"healthy"'
```

### Agent Hub ✓

```bash
# 1. Agents exist
curl -s http://localhost:8003/api/agents | jq -r '.agents[].slug' | sort
# Expected: coder, fixer, qa, reviewer, supervisor

# 2. Coder agent config
curl -s http://localhost:8003/api/agents/coder | jq '{slug, primary_model, has_fallback: (.fallback_models | length > 0)}'
# Expected: {slug: "coder", primary_model: "gemini-3-flash-preview", has_fallback: true}

# 3. Service healthy
curl -s http://localhost:8003/health
```

---

## Part 4: Testing Agent Routing

### Test 1: Portfolio-AI Discovery Agent

**With AGENT_HUB_ENABLED=true:**

```bash
# 1. Enable Agent Hub
echo "AGENT_HUB_ENABLED=true" >> /home/kasadis/portfolio-ai/backend/.env

# 2. Restart
cd /home/kasadis/portfolio-ai
./scripts/restart.sh

# 3. Trigger discovery agent via API
curl -X POST http://localhost:8000/api/agents/discovery/run \
  -H "Content-Type: application/json" | jq

# 4. Check logs for agent_slug usage
journalctl --user -u portfolio-backend -n 100 | rg "agent_slug|discovery"

# Expected:
# - "agent_slug='discovery'" in logs
# - Agent Hub receives request with agent_slug
# - Mandates injected (if configured in Agent Hub)
```

### Test 2: SummitFlow Coder Agent

```bash
# 1. Check orchestrator starts coder
cd /home/kasadis/summitflow

# 2. Create test task
st create "Write hello world function" --complexity simple

# 3. Execute task
st do <task-id>

# 4. Monitor Agent Hub logs
journalctl --user -u agent-hub-backend -f | rg "agent_slug|coder|mandate"

# Expected:
# - "agent_slug='coder'" in requests
# - "Resolved agent: coder" in Agent Hub logs
# - "Injected X mandates" for coder agent
# - Response includes "agent_used: coder"
```

### Test 3: Mandate Injection Verification

```bash
# Create completion with agent_slug
curl -X POST http://localhost:8003/api/complete \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a test"}],
    "project_id": "test",
    "agent_slug": "coder",
    "max_tokens": 500
  }' | jq '{agent_used, model_used, mandates_count: (.metadata.mandates_injected // 0)}'

# Expected response includes:
{
  "agent_used": "coder",
  "model_used": "gemini-3-flash-preview",
  "mandates_count": 5  // or however many mandates exist
}
```

### Test 4: Fallback Chain Verification

**Simulate primary model failure:**

```bash
# 1. Temporarily disable Gemini in Agent Hub (or set invalid API key)
# This will force fallback to Claude Sonnet

# 2. Make request with coder agent
curl -X POST http://localhost:8003/api/complete \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Write a function"}],
    "project_id": "test",
    "agent_slug": "coder",
    "max_tokens": 500
  }' | jq '{agent_used, model_used, used_fallback}'

# Expected:
{
  "agent_used": "coder",
  "model_used": "claude-sonnet-4-5",  // Fallback model!
  "used_fallback": true
}
```

---

## Part 5: Rollback Plan

### If Portfolio-AI Breaks

```bash
cd /home/kasadis/portfolio-ai

# 1. Disable Agent Hub
export AGENT_HUB_ENABLED=false
./scripts/restart.sh

# 2. Restore mypy ignores if needed
# Add back to backend/pyproject.toml:
[[tool.mypy.overrides]]
module = ["agent_hub", "agent_hub.*"]
ignore_missing_imports = true

# 3. Verify backend works
curl http://localhost:8000/health
```

### If SummitFlow Breaks

```bash
cd /home/kasadis/summitflow

# 1. Git revert changes
git diff backend/app/constants.py  # Review changes
git checkout backend/app/constants.py  # Revert if needed

# 2. Restore old patterns temporarily
# Change agent_slug= back to model="agent:..."

# 3. Rebuild
./scripts/rebuild.sh --backend
```

---

## Part 6: Summary Checklist

### Portfolio-AI Changes

- [ ] SDK added to `pyproject.toml` with file URL
- [ ] mypy ignores removed
- [ ] `AgentHubAPIClient.generate()` accepts `agent_slug`
- [ ] Discovery Agent uses `agent_slug="discovery"`
- [ ] Portfolio Analyzer uses `agent_slug="portfolio_analyzer"`
- [ ] Strategy Reviewer uses `agent_slug="strategy_reviewer"`
- [ ] Multi-Reviewer uses `agent_slug="multi_reviewer_{gemini|claude}"`
- [ ] Strategy Evolution uses `agent_slug="strategy_evolution"`
- [ ] Cross-Validation uses `agent_slug="cross_validator_{gemini|claude}"`
- [ ] Thesis Service uses `agent_slug="thesis_{generator|validator}"`
- [ ] Gap Analysis uses `agent_slug="gap_analysis"`
- [ ] All 9 usages verified with grep
- [ ] Types pass without ignores
- [ ] Backend deploys successfully
- [ ] Health check passes

### SummitFlow Changes

- [ ] `AgentHubLLMClient.generate()` accepts `agent_slug`
- [ ] `DualProviderClient.generate()` accepts `agent_slug`
- [ ] Constants refactored to `AGENT_SLUG_*` pattern
- [ ] Old `"agent:..."` constants removed
- [ ] Orchestrator uses `agent_slug=AGENT_SLUG_CODER`
- [ ] Orchestrator uses `agent_slug=AGENT_SLUG_SUPERVISOR`
- [ ] AI Review uses `agent_slug=AGENT_SLUG_REVIEWER`
- [ ] All usages updated (grep verified)
- [ ] Agents exist in Agent Hub DB
- [ ] Backend deploys successfully
- [ ] Test completion shows `agent_used` in response
- [ ] Mandate injection verified in logs

### Agent Hub Verification

- [ ] All 5 agents seeded (coder, supervisor, reviewer, fixer, qa)
- [ ] Each agent has primary_model configured
- [ ] Each agent has fallback_models configured
- [ ] Each agent has system_prompt configured
- [ ] Service healthy and responding

---

## Appendix A: Agent Slug Reference

### Portfolio-AI Agents

| Agent Slug | Class | Purpose | Files |
|------------|-------|---------|-------|
| `discovery` | DiscoveryAgent | Market discovery | discovery.py, agent_tasks.py |
| `portfolio_analyzer` | PortfolioAnalyzerAgent | Portfolio analysis | portfolio_analyzer.py, agent_tasks.py |
| `strategy_reviewer` | StrategyReviewer | Strategy review | strategy_reviewer.py |
| `multi_reviewer_gemini` | MultiReviewer | Dual review (Gemini) | multi_reviewer.py |
| `multi_reviewer_claude` | MultiReviewer | Dual review (Claude) | multi_reviewer.py |
| `strategy_evolution` | StrategyEvolutionAgent | Strategy optimization | strategy_evolution_agent.py |
| `cross_validator_gemini` | CrossValidationService | Cross-validation (Gemini) | cross_validation.py |
| `cross_validator_claude` | CrossValidationService | Cross-validation (Claude) | cross_validation.py |
| `thesis_generator` | ThesisService | Thesis generation | thesis_service.py |
| `thesis_validator` | ThesisService | Thesis validation | thesis_service.py |
| `gap_analysis` | Workflow | Daily gap analysis | workflow_tasks.py |

**Total:** 11 unique agent slugs (9 locations, some have multiple slugs)

### SummitFlow Agents

| Agent Slug | Purpose | Primary Model | Fallback |
|------------|---------|---------------|----------|
| `coder` | Code generation | gemini-3-flash-preview | claude-sonnet-4-5 |
| `supervisor` | Task coordination | claude-sonnet-4-5 | gemini-3-pro-preview |
| `reviewer` | Code review | claude-opus-4-5 | claude-sonnet-4-5 |
| `fixer` | Error fixing | claude-sonnet-4-5 | claude-opus-4-5 |
| `qa` | Quality review | claude-opus-4-5 | claude-sonnet-4-5 |

**Total:** 5 agents

---

## Appendix B: Code Diff Examples

### Portfolio-AI: AgentHubAPIClient.generate()

```diff
 def generate(
     self,
     prompt: str,
     system: str | None = None,
     tools: list[dict[str, Any]] | None = None,
     max_tokens: int = 4096,
     temperature: float = 1.0,
     purpose: str | None = None,
+    agent_slug: str | None = None,
     **kwargs: Any,
 ) -> LLMResponse:
     """Generate completion using Agent Hub API.

     Args:
         prompt: User prompt
         system: System prompt (optional)
         tools: Tool definitions for function calling
         max_tokens: Maximum tokens
         temperature: Sampling temperature
         purpose: Purpose of this request for session tracking
+        agent_slug: Agent slug for routing (e.g., "discovery", "coder")
         **kwargs: Additional options

     response = self._client.complete(
         model=self.model,
         messages=messages,
         max_tokens=max_tokens,
         temperature=temperature,
         tools=tools,
         project_id="portfolio-ai",
         purpose=purpose,
+        agent_slug=agent_slug,
     )
```

### SummitFlow: Constants Refactor

```diff
-# Agent Hub agents (use agent:slug format)
-AGENT_WORKER = "agent:coder"
-AGENT_SUPERVISOR = "agent:supervisor"
-AGENT_REVIEWER = "agent:reviewer"
-AGENT_FIXER = "agent:fixer"
-AGENT_QA = "agent:qa"
+# Agent slugs for Agent Hub routing
+AGENT_SLUG_CODER = "coder"
+AGENT_SLUG_SUPERVISOR = "supervisor"
+AGENT_SLUG_REVIEWER = "reviewer"
+AGENT_SLUG_FIXER = "fixer"
+AGENT_SLUG_QA = "qa"
+
+# Models to use with agents
+AGENT_CODER_MODEL = GEMINI_FLASH
+AGENT_SUPERVISOR_MODEL = CLAUDE_SONNET
+AGENT_REVIEWER_MODEL = CLAUDE_OPUS
+AGENT_FIXER_MODEL = CLAUDE_SONNET
+AGENT_QA_MODEL = CLAUDE_OPUS
```

### SummitFlow: Usage Update

```diff
-from ..constants import AGENT_REVIEWER
+from ..constants import AGENT_SLUG_REVIEWER, AGENT_REVIEWER_MODEL

-reviewer = get_agent("claude", model=AGENT_REVIEWER)
+reviewer = get_agent("claude", model=AGENT_REVIEWER_MODEL)

 response = reviewer.generate(
     prompt=prompt,
     system=system,
+    agent_slug=AGENT_SLUG_REVIEWER,
 )
```

---

**END OF GUIDE**

This document contains everything needed to fix Agent Hub SDK and agent_slug issues in both Portfolio-AI and SummitFlow.
