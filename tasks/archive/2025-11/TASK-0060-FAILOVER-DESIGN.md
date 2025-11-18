# Task 0060 - Provider Failover Design

**Date**: 2025-11-17
**Status**: Design Complete
**Goal**: Zero-cost agent execution with automatic failover

---

## CLI Verification Results

### ✅ Gemini CLI (Primary)
- **Location**: `/usr/bin/gemini`
- **Version**: 0.10.0
- **Status**: ✅ WORKING (tested with simple prompt)
- **Cost**: FREE (uses cached credentials)
- **Output Formats**: `text`, `json`
- **Test Result**: Successfully returned "4" for "What is 2+2?"
- **JSON Output**: ✅ Working with structured stats (tokens, tools, files)

### ⚠️ Claude CLI (Not Usable for Zero-Cost)
- **Location**: `/home/kasadis/.local/bin/claude`
- **Version**: 2.0.42 (Claude Code)
- **Status**: ❌ REQUIRES API KEY
- **Cost**: PAID (requires ANTHROPIC_API_KEY)
- **Output Formats**: `text`, `json`, `stream-json`
- **Test Result**: "Invalid API key · Fix external API key"
- **Conclusion**: Cannot use without API costs

---

## Revised Architecture: Gemini-Only with Intelligent Retry

### Design Principles
1. **Zero API costs** - No paid API calls
2. **Single provider** - Gemini CLI only (free)
3. **Intelligent retry** - Multiple models/strategies on failure
4. **Graceful degradation** - Clear error messages if unavailable

### Provider Strategy

```python
class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        pass

class GeminiCLIClient(LLMClient):
    """Gemini CLI client with intelligent retry."""

    def __init__(self):
        self.models = [
            "gemini-2.5-pro",      # Primary: Best quality
            "gemini-2.5-flash",     # Fallback 1: Faster, lighter
            "gemini-1.5-pro",       # Fallback 2: Older, stable
        ]
        self.cli_path = shutil.which("gemini")
        if not self.cli_path:
            raise RuntimeError("Gemini CLI not found in PATH")

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate with automatic model fallback."""
        last_error = None

        for model in self.models:
            try:
                result = self._call_cli(prompt, model=model, **kwargs)
                return result
            except GeminiRateLimitError:
                # Rate limit hit, try next model
                last_error = f"Rate limit on {model}"
                continue
            except GeminiAPIError as e:
                # API error, try next model
                last_error = f"API error on {model}: {e}"
                continue

        # All models failed
        raise LLMProviderError(f"All Gemini models failed: {last_error}")

    def _call_cli(self, prompt: str, model: str, **kwargs) -> LLMResponse:
        """Call Gemini CLI with subprocess."""
        cmd = [
            self.cli_path,
            "-p",
            "--output-format", "json",
            "-m", model,
        ]

        result = subprocess.run(
            cmd,
            input=prompt.encode(),
            capture_output=True,
            timeout=300,  # 5 min timeout
        )

        if result.returncode != 0:
            self._handle_error(result.stderr.decode())

        return self._parse_response(result.stdout.decode())

class AnthropicAPIClient(LLMClient):
    """Anthropic API client (OPTIONAL - only if API key set)."""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate using Anthropic API (COSTS MONEY)."""
        # Implementation using self.client.messages.create()
        pass
```

### Failover Logic

```python
class AgentLLMProvider:
    """Provider manager with intelligent failover."""

    def __init__(self):
        # Try to initialize providers in order of preference
        self.providers: list[LLMClient] = []

        # Primary: Gemini CLI (free)
        try:
            self.providers.append(GeminiCLIClient())
            logger.info("gemini_cli_available")
        except RuntimeError:
            logger.warning("gemini_cli_not_available")

        # Optional: Anthropic API (only if key set and user enables)
        if os.getenv("ANTHROPIC_API_KEY") and os.getenv("ENABLE_PAID_API", "false") == "true":
            try:
                self.providers.append(AnthropicAPIClient())
                logger.info("anthropic_api_available_as_fallback")
            except RuntimeError:
                pass

        if not self.providers:
            raise RuntimeError("No LLM providers available")

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate with automatic provider fallback."""
        last_error = None

        for provider in self.providers:
            try:
                result = provider.generate(prompt, **kwargs)
                logger.info("llm_generation_success", provider=provider.__class__.__name__)
                return result
            except (LLMProviderError, GeminiRateLimitError) as e:
                logger.warning("llm_generation_failed", provider=provider.__class__.__name__, error=str(e))
                last_error = e
                continue

        # All providers failed
        raise LLMProviderError(f"All providers failed: {last_error}")
```

---

## Failover Scenarios

### Scenario 1: Gemini Working (99% of time)
1. Agent calls `generate()`
2. GeminiCLIClient tries `gemini-2.5-pro`
3. ✅ Success → Return result
4. **Cost**: $0

### Scenario 2: Gemini Rate Limited
1. Agent calls `generate()`
2. GeminiCLIClient tries `gemini-2.5-pro` → Rate limit
3. GeminiCLIClient tries `gemini-2.5-flash` → Rate limit
4. GeminiCLIClient tries `gemini-1.5-pro` → ✅ Success
5. **Cost**: $0 (still using Gemini, just older model)

### Scenario 3: Gemini Completely Down (rare)
1. Agent calls `generate()`
2. GeminiCLIClient tries all 3 models → All fail
3. **IF** `ENABLE_PAID_API=true` AND `ANTHROPIC_API_KEY` set:
   - AnthropicAPIClient tries `claude-3-5-sonnet`
   - ✅ Success → Return result
   - **Cost**: ~$0.003 per request (paid fallback)
4. **ELSE**:
   - ❌ Raise LLMProviderError
   - Agent run marked as failed
   - **Cost**: $0

### Scenario 4: Zero-Cost Mode (Default)
- `ENABLE_PAID_API=false` (default)
- Only Gemini CLI available
- If Gemini fails → Agent fails gracefully
- **Guaranteed Cost**: $0

---

## Configuration

### Environment Variables

```bash
# .env
# Gemini CLI (free, always enabled)
# No configuration needed - uses cached credentials

# Anthropic API (paid, optional fallback)
ANTHROPIC_API_KEY=sk-ant-xxx  # Optional: Only if you want paid fallback
ENABLE_PAID_API=false          # Must explicitly enable to use paid API

# Provider preferences
PRIMARY_LLM_PROVIDER=gemini    # Options: gemini, anthropic
FALLBACK_LLM_PROVIDER=none     # Options: anthropic, none
```

### Database Schema Extension

```sql
-- Add provider tracking to agent_runs
ALTER TABLE agent_runs ADD COLUMN provider VARCHAR(50);  -- 'gemini', 'anthropic'
ALTER TABLE agent_runs ADD COLUMN model VARCHAR(100);    -- 'gemini-2.5-pro', 'claude-3-5-sonnet'
ALTER TABLE agent_runs ADD COLUMN fallback_used BOOLEAN DEFAULT FALSE;
ALTER TABLE agent_runs ADD COLUMN cost_usd DECIMAL(10, 6) DEFAULT 0.00;
```

---

## Migration Strategy

### Phase 1: Agent Base Refactoring (Safe, No Behavior Change)
1. Create `LLMClient` interface
2. Implement `GeminiCLIClient`
3. Implement `AnthropicAPIClient` (wraps existing code)
4. Add `AgentLLMProvider` with failover logic
5. Update `Agent.__init__` to use provider instead of direct Anthropic()

### Phase 2: Testing & Verification
1. Unit tests for each client
2. Integration tests for failover logic
3. Test with real Gemini CLI
4. Test graceful degradation (Gemini unavailable)

### Phase 3: Deployment
1. Update agent_runs schema
2. Update Celery tasks to use new provider
3. Add monitoring/logging for provider usage
4. Document zero-cost architecture in ARCHITECTURE.md

---

## Key Benefits

✅ **Zero API costs** - Gemini CLI is free
✅ **Automatic retry** - 3 Gemini models tried before failing
✅ **Optional paid fallback** - Anthropic API as safety net (disabled by default)
✅ **Backwards compatible** - Anthropic API still works if configured
✅ **Clear failure modes** - Explicit errors if no providers available
✅ **Cost tracking** - All costs logged in database

---

## Updated Task 0060 Scope

### What Changed
- **Original**: "Gemini CLI and Claude Code CLI headless agents"
- **Revised**: "Gemini CLI (primary, free) with optional Anthropic API fallback"
- **Reason**: Claude CLI requires API key (same cost as direct API)

### Impact on Effort
- **Reduced**: No need to support two CLI interfaces (only Gemini)
- **Simplified**: Single free provider with optional paid fallback
- **Clearer**: Zero-cost architecture is explicit

### Task 3.2a (ai_analyzer.py)
- **Status**: Already uses CLI approach (subprocess-based)
- **Current**: Searches for `claude` CLI (fails without API key)
- **New**: Will search for `gemini` CLI (works with cached credentials)
- **Change**: Replace `claude -p` with `gemini -p` in ai_analyzer.py

---

## Recommendation

✅ **Proceed with Gemini-only design** (zero-cost guarantee)
- Primary: Gemini CLI with 3 model fallbacks
- Optional: Anthropic API fallback (disabled by default, requires explicit opt-in)
- Clear cost tracking and provider usage logging

**Next Step**: Update Task 0060 with this revised architecture and continue implementation.
