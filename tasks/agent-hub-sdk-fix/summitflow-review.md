# SummitFlow Agent Hub Setup Review

## Summary

**CRITICAL FINDING:** SummitFlow uses "agent:slug" model syntax, but this appears to be a **naming convention only** - NOT actual agent routing via the `agent_slug` parameter.

## Dependencies

### ✅ SummitFlow (Correct)
```toml
# backend/pyproject.toml:25
dependencies = [
    "agent-hub-client @ file:///home/kasadis/agent-hub/packages/agent-hub-client",
]

# pyproject.toml:46
[tool.hatch.metadata]
allow-direct-references = true
```

- Uses local file URL reference (editable install)
- Has `allow-direct-references = true` for hatch build backend
- **NO mypy ignores** for agent_hub (types work correctly)

### ❌ Portfolio-AI (Needs Fix)
```python
# Current: Dev mode install, not declared in dependencies
# backend/pyproject.toml has NO agent-hub-client entry

# backend/pyproject.toml:189-190
[[tool.mypy.overrides]]
module = ["agent_hub", "agent_hub.*"]
ignore_missing_imports = true  # ← Hiding the problem
```

**Action:** Use SummitFlow's pattern - add file URL + allow-direct-references

---

## Agent Routing Patterns

### 🔍 SummitFlow's "agent:slug" Pattern

**constants.py:**
```python
# Agent Hub agents (use agent:slug format)
AGENT_WORKER = "agent:coder"
AGENT_SUPERVISOR = "agent:supervisor"
AGENT_REVIEWER = "agent:reviewer"
AGENT_FIXER = "agent:fixer"
AGENT_QA = "agent:qa"
```

**Usage:**
```python
# app/tasks/ai_review.py
reviewer = get_agent("claude", model=AGENT_REVIEWER)  # model="agent:reviewer"
```

**What Actually Happens:**
```python
# app/services/agent_hub_client.py:311-321
response = client.complete(
    model=self.model,  # "agent:reviewer" passed as model
    messages=messages,
    max_tokens=max_tokens,
    temperature=temperature,
    project_id=self.project_id,
    session_id=kwargs.get("session_id"),
    purpose=purpose,
    external_id=task_id,
    enable_caching=kwargs.get("enable_caching", True),
    # ❌ NO agent_slug parameter!
)
```

**VERDICT:** SummitFlow passes "agent:reviewer" as the `model` parameter, NOT using `agent_slug`.

---

## Agent Hub API Reality Check

### Supported Routing Methods

**From `/home/kasadis/agent-hub/backend/app/api/complete.py`:**

```python
class CompletionRequest(BaseModel):
    model: str | None = Field(
        default=None,
        description="Model identifier (e.g., claude-sonnet-4-5). Required unless agent_slug is provided.",
    )
    agent_slug: str | None = Field(
        default=None,
        description=(
            "Agent slug for routing (e.g., 'coder', 'planner'). When provided, "
            "loads agent config from database, injects mandates, and uses fallback chains."
        ),
    )
```

**Routing Logic:**
```python
# Validate: either model or agent_slug must be provided
if not request.model and not request.agent_slug:
    raise HTTPException(
        status_code=400,
        detail="Either 'model' or 'agent_slug' must be provided.",
    )

# Check for agent-based routing first (takes priority)
if request.agent_slug:
    if not db:
        raise HTTPException(
            status_code=400,
            detail="Database connection required for agent routing. agent_slug cannot be used without DB.",
        )
    resolved_agent = await resolve_agent(request.agent_slug, db)
    resolved_model = resolved_agent.model
    provider = resolved_agent.provider
    agent_used = resolved_agent.agent.slug

    # Inject mandates
    agent_mandate_injection = await inject_agent_mandates(resolved_agent.agent)
else:
    # Direct model routing (NO agent features)
    resolved_model = resolve_model(request.model)
    provider = _get_provider(resolved_model)
```

**NO AUTOMATIC PARSING:** Agent Hub does NOT automatically extract `agent_slug` from `model="agent:coder"`.

---

## What SummitFlow is Actually Missing

**By passing `model="agent:coder"` instead of `agent_slug="coder"`:**

❌ **Missing Features:**
1. Agent-specific system prompts (stored in DB)
2. Mandate injection via semantic search
3. Fallback chains (e.g., Flash → Sonnet on failure)
4. `agent_used` tracking in responses
5. Agent config versioning

✅ **What They Get:**
- Just direct model routing
- "agent:coder" treated as an unknown model string
- Falls back to default Claude provider detection

**VERDICT:** SummitFlow's "agent:" constants are **decorative** - they're not getting agent routing benefits.

---

## Correct Agent Hub Usage

### ✅ Using agent_slug Parameter (RECOMMENDED)

```python
from agent_hub import AgentHubClient

client = AgentHubClient(
    base_url="http://localhost:8003",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    request_source="portfolio-ai",
)

response = client.complete(
    model=None,  # Not needed when using agent_slug
    agent_slug="coder",  # ← Activates agent routing
    messages=[{"role": "user", "content": "Write a function"}],
    project_id="portfolio-ai",
    purpose="code_generation",
)
```

**Benefits:**
- ✅ Loads agent config from DB (system prompts, temperature, etc.)
- ✅ Injects mandates via semantic search
- ✅ Uses fallback chains (coder: flash → sonnet on failure)
- ✅ Response includes `agent_used` field
- ✅ Proper telemetry and cost attribution

---

## Impact on Portfolio-AI Task

### Task Changes Required

**BEFORE (Original Plan):**
```python
# Planned approach
agent_slug="discovery"
agent_slug="portfolio_analyzer"
agent_slug="strategy_reviewer"
# ... etc
```

**AFTER (Still Correct!):**
The original plan is CORRECT. Use `agent_slug` parameter, not "agent:slug" model syntax.

### SummitFlow Should Also Be Fixed

**Issue to Track:**
- [ ] SummitFlow: Replace "agent:coder" model pattern with proper `agent_slug="coder"` usage
- [ ] Verify agents exist in Agent Hub DB (coder, supervisor, reviewer, fixer, qa)
- [ ] Update all AgentHubLLMClient.generate() calls to pass agent_slug

---

## Dependency Installation Pattern

### Use SummitFlow's Pattern

**Portfolio-AI `backend/pyproject.toml` should use:**

```toml
[project]
dependencies = [
    # ... existing deps ...
    "agent-hub-client @ file:///home/kasadis/agent-hub/packages/agent-hub-client",
]

[tool.setuptools]
packages = ["app"]

[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

# NOTE: If using hatch instead, add:
# [tool.hatch.metadata]
# allow-direct-references = true
```

**Why file URL?**
- Allows local development against Agent Hub changes
- Automatically picks up SDK updates when Agent Hub is modified
- No need for separate PyPI package (yet)

**Why NOT just rely on dev mode install?**
- Breaks in fresh environments
- CI/CD doesn't know about dev install
- Dependencies not tracked in lockfile
- Type checking may fail (hence the mypy ignores)

---

## Recommendations

### For Portfolio-AI Task (task-8e70705f)

**Keep Original Plan With One Adjustment:**

1. ✅ Use file URL dependency like SummitFlow
2. ✅ Use `agent_slug` parameter (original plan is correct)
3. ✅ Remove mypy ignores (original plan is correct)
4. ❌ DON'T use "agent:slug" model syntax (SummitFlow's pattern is broken)

### For SummitFlow (Separate Task)

**Create follow-up task:**
- Replace all `AGENT_*` constant usage with proper `agent_slug` parameter
- Verify agents are seeded in Agent Hub database
- Test mandate injection is working
- Verify fallback chains activate on failures

---

## Test Verification

```bash
# Verify SDK imports work
cd backend && .venv/bin/python -c 'from agent_hub import AgentHubClient; print("OK")'

# Verify types work (no mypy ignores needed)
cd backend && .venv/bin/mypy app/agents/clients/agent_hub_client.py --strict

# Verify file URL dependency installed
cd backend && .venv/bin/pip show agent-hub-client | grep Location
# Should show: /home/kasadis/agent-hub/packages/agent-hub-client
```

---

## Conclusion

**Portfolio-AI task plan is CORRECT** - use `agent_slug` parameter approach.

**SummitFlow's "agent:slug" pattern is BROKEN** - they're not getting agent routing benefits.

**Dependency approach:** Use file URL like SummitFlow + allow-direct-references.
