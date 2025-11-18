# Task 0060 - Dual Provider Architecture (Claude + Gemini)

**Date**: 2025-11-17
**Status**: Architecture Design
**Goal**: Both Claude CLI and Gemini CLI with bidirectional failover

---

## Architecture: True Dual-Provider Failover

### Design Principles
1. **Both providers equal** - Either can be primary
2. **Automatic failover** - If one fails, try the other
3. **Cost tracking** - Log which provider was used
4. **Graceful degradation** - Clear errors if both fail

---

## Provider Implementation

### Abstract Interface

```python
from abc import ABC, abstractmethod
from typing import Literal

class LLMResponse:
    """Standardized LLM response."""
    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        usage: dict[str, int],
        tool_calls: list[dict] | None = None,
    ):
        self.content = content
        self.provider = provider  # "claude" or "gemini"
        self.model = model
        self.usage = usage  # {prompt_tokens, completion_tokens, total_tokens}
        self.tool_calls = tool_calls or []

class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict] | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion with optional tool use."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and authenticated."""
        pass
```

### Claude CLI Client

```python
import json
import shutil
import subprocess
from pathlib import Path

class ClaudeCLIClient(LLMClient):
    """Claude Code CLI client."""

    def __init__(self):
        """Initialize Claude CLI client.

        Auth: Uses ~/.claude/.credentials.json (OAuth session)
        Cost: Included in Claude subscription
        """
        self.cli_path = shutil.which("claude")
        if not self.cli_path:
            raise RuntimeError("Claude CLI not found in PATH")

        # Check credentials file exists
        creds_file = Path.home() / ".claude" / ".credentials.json"
        if not creds_file.exists():
            raise RuntimeError("Claude credentials not found")

        self.models = [
            "sonnet",           # claude-sonnet-4-5 (latest)
            "claude-3-5-sonnet-20241022",  # Specific version
        ]

    def is_available(self) -> bool:
        """Check if Claude CLI is available."""
        if not self.cli_path:
            return False

        # Quick test: --version should work without auth
        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict] | None = None,
        model: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate using Claude CLI."""
        cmd = [
            self.cli_path,
            "-p",  # Print mode (non-interactive)
            "--output-format", "json",
            "--model", model or self.models[0],
        ]

        # Add system prompt if provided
        if system:
            cmd.extend(["--system-prompt", system])

        # Add tools if provided (need to serialize)
        if tools:
            # Claude CLI tools format needs investigation
            # For now, tools will be handled differently
            pass

        # Run command
        result = subprocess.run(
            cmd,
            input=prompt.encode(),
            capture_output=True,
            timeout=300,  # 5 min
        )

        if result.returncode != 0:
            error = result.stderr.decode()
            raise CLIError(f"Claude CLI failed: {error}")

        # Parse response
        response_data = json.loads(result.stdout.decode())

        # Extract content and usage
        # Format needs to be determined based on actual Claude CLI output
        content = response_data.get("response", "")
        usage = {
            "prompt_tokens": response_data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": response_data.get("usage", {}).get("output_tokens", 0),
            "total_tokens": response_data.get("usage", {}).get("total_tokens", 0),
        }

        return LLMResponse(
            content=content,
            provider="claude",
            model=model or self.models[0],
            usage=usage,
        )
```

### Gemini CLI Client

```python
class GeminiCLIClient(LLMClient):
    """Gemini CLI client."""

    def __init__(self):
        """Initialize Gemini CLI client.

        Auth: Uses cached credentials (free)
        Cost: FREE
        """
        self.cli_path = shutil.which("gemini")
        if not self.cli_path:
            raise RuntimeError("Gemini CLI not found in PATH")

        self.models = [
            "gemini-2.5-pro",     # Best quality
            "gemini-2.5-flash",   # Faster
            "gemini-1.5-pro",     # Fallback
        ]

    def is_available(self) -> bool:
        """Check if Gemini CLI is available."""
        if not self.cli_path:
            return False

        # Test with simple prompt
        try:
            result = subprocess.run(
                [self.cli_path, "-p", "--output-format", "json", "test"],
                input=b"test",
                capture_output=True,
                timeout=10
            )
            # Even if prompt fails, CLI is available if no "not found" error
            return result.returncode in [0, 1]  # 0 = success, 1 = rate limit
        except:
            return False

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict] | None = None,
        model: str | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate using Gemini CLI."""
        # Prepend system prompt to user prompt if provided
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        cmd = [
            self.cli_path,
            "-p",
            "--output-format", "json",
            "-m", model or self.models[0],
        ]

        result = subprocess.run(
            cmd,
            input=full_prompt.encode(),
            capture_output=True,
            timeout=300,
        )

        if result.returncode != 0:
            error = result.stderr.decode()
            raise CLIError(f"Gemini CLI failed: {error}")

        # Parse Gemini JSON response
        response_data = json.loads(result.stdout.decode())

        # Extract content from Gemini format
        content = response_data.get("response", "")
        stats = response_data.get("stats", {}).get("models", {})
        tokens = stats.get("tokens", {})

        usage = {
            "prompt_tokens": tokens.get("prompt", 0),
            "completion_tokens": tokens.get("candidates", 0),
            "total_tokens": tokens.get("total", 0),
        }

        return LLMResponse(
            content=content,
            provider="gemini",
            model=model or self.models[0],
            usage=usage,
        )
```

---

## Failover Provider

```python
class DualProviderClient:
    """Manages Claude + Gemini with automatic failover."""

    def __init__(self, primary: Literal["claude", "gemini"] = "gemini"):
        """Initialize with provider preference.

        Args:
            primary: Which provider to try first ("claude" or "gemini")
        """
        self.providers: dict[str, LLMClient] = {}
        self.primary = primary

        # Initialize Claude CLI
        try:
            self.providers["claude"] = ClaudeCLIClient()
            logger.info("claude_cli_available")
        except RuntimeError as e:
            logger.warning("claude_cli_unavailable", error=str(e))

        # Initialize Gemini CLI
        try:
            self.providers["gemini"] = GeminiCLIClient()
            logger.info("gemini_cli_available")
        except RuntimeError as e:
            logger.warning("gemini_cli_unavailable", error=str(e))

        if not self.providers:
            raise RuntimeError("No LLM providers available")

        logger.info(
            "dual_provider_initialized",
            providers=list(self.providers.keys()),
            primary=self.primary,
        )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict] | None = None,
        **kwargs
    ) -> LLMResponse:
        """Generate with automatic failover.

        Strategy:
        1. Try primary provider
        2. If fails, try secondary provider
        3. If both fail, raise error
        """
        # Determine provider order
        if self.primary == "claude":
            order = ["claude", "gemini"]
        else:
            order = ["gemini", "claude"]

        # Filter to only available providers
        order = [p for p in order if p in self.providers]

        if not order:
            raise RuntimeError("No providers available")

        last_error = None

        for provider_name in order:
            provider = self.providers[provider_name]

            try:
                logger.info("attempting_generation", provider=provider_name)
                result = provider.generate(prompt, system=system, tools=tools, **kwargs)
                logger.info(
                    "generation_success",
                    provider=provider_name,
                    model=result.model,
                    tokens=result.usage.get("total_tokens", 0),
                    fallback_used=(provider_name != order[0]),
                )
                return result

            except CLIError as e:
                logger.warning(
                    "generation_failed",
                    provider=provider_name,
                    error=str(e),
                )
                last_error = e
                continue

        # All providers failed
        raise RuntimeError(f"All providers failed. Last error: {last_error}")
```

---

## Configuration

### Environment Variables

```bash
# .env
# Primary provider preference (which to try first)
PRIMARY_LLM_PROVIDER=gemini  # Options: claude, gemini

# Individual provider toggles (optional)
ENABLE_CLAUDE_CLI=true   # Default: true
ENABLE_GEMINI_CLI=true   # Default: true
```

### Database Schema

```sql
-- Update agent_runs table
ALTER TABLE agent_runs ADD COLUMN provider VARCHAR(50);  -- 'claude' or 'gemini'
ALTER TABLE agent_runs ADD COLUMN model VARCHAR(100);    -- Specific model used
ALTER TABLE agent_runs ADD COLUMN fallback_used BOOLEAN DEFAULT FALSE;  -- Did we fail over?
ALTER TABLE agent_runs ADD COLUMN prompt_tokens INTEGER;
ALTER TABLE agent_runs ADD COLUMN completion_tokens INTEGER;
ALTER TABLE agent_runs ADD COLUMN total_tokens INTEGER;

-- Add provider_usage tracking table
CREATE TABLE provider_usage (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,  -- 'claude', 'gemini'
    model VARCHAR(100),
    success BOOLEAN NOT NULL,
    tokens_used INTEGER,
    duration_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_provider_usage_created ON provider_usage(created_at);
CREATE INDEX idx_provider_usage_provider ON provider_usage(provider);
```

---

## Agent Base Class Integration

```python
class Agent(ABC):
    """Base class for AI agents."""

    def __init__(
        self,
        storage: PortfolioStorage,
        llm_client: DualProviderClient | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize agent.

        Args:
            storage: PortfolioStorage instance
            llm_client: LLM client (or create default dual-provider)
            model: Optional specific model override
        """
        self.storage = storage
        self.llm_client = llm_client or DualProviderClient()
        self.model = model
        self.agent_type = self.__class__.__name__

    def run(self, prompt: str, max_iterations: int = 10) -> AgentRunResult:
        """Run agent with tool calling support."""
        run_id = str(uuid.uuid4())

        # Create agent run record
        self.storage.create_agent_run(run_id, self.agent_type)

        try:
            # Generate with LLM
            response = self.llm_client.generate(
                prompt=prompt,
                system=self.get_system_prompt(),
                tools=self.get_tools(),
                model=self.model,
            )

            # Update run record with provider info
            self.storage.update_agent_run(
                run_id,
                provider=response.provider,
                model=response.model,
                prompt_tokens=response.usage["prompt_tokens"],
                completion_tokens=response.usage["completion_tokens"],
            )

            # Process response (tool calls, etc.)
            final_response = self._process_response(response, run_id)

            return {
                "status": "success",
                "response": final_response,
                "run_id": run_id,
            }

        except Exception as e:
            logger.error("agent_run_failed", run_id=run_id, error=str(e))
            self.storage.mark_agent_run_failed(run_id, str(e))
            return {
                "status": "error",
                "error": str(e),
                "run_id": run_id,
            }
```

---

## Failover Scenarios

### Scenario 1: Primary Works (90% of time)
- Primary: Gemini
- Gemini → ✅ Success
- **Result**: Use Gemini, fallback_used=false

### Scenario 2: Primary Fails, Secondary Works
- Primary: Gemini
- Gemini → ❌ Rate limit
- Claude → ✅ Success
- **Result**: Use Claude, fallback_used=true

### Scenario 3: Both Fail
- Primary: Gemini
- Gemini → ❌ Rate limit
- Claude → ❌ Auth error
- **Result**: Agent run fails, error logged

### Scenario 4: Claude Primary (User Preference)
- Primary: Claude (set PRIMARY_LLM_PROVIDER=claude)
- Claude → ✅ Success
- **Result**: Use Claude, fallback_used=false

---

## Migration for ai_analyzer.py

**Current** (uses Claude CLI):
```python
# Searches for 'claude' CLI
cli_path = shutil.which("claude")
```

**Updated** (uses DualProviderClient):
```python
from app.agents.llm_client import DualProviderClient

class CapabilityAnalyzer:
    def __init__(self, conn_mgr: ConnectionManager):
        self.conn_mgr = conn_mgr
        self.llm_client = DualProviderClient(primary="gemini")  # Gemini first (free)

    def analyze(self, capabilities: dict) -> list[dict]:
        """Analyze capabilities using LLM."""
        prompt = self._build_analysis_prompt(capabilities)

        response = self.llm_client.generate(
            prompt=prompt,
            system="You are an AI system analyzer...",
        )

        return self._parse_insights(response.content)
```

---

## Next Steps

1. **Investigate Claude CLI print mode auth**
   - Why does `-p` fail with "Invalid API key"?
   - Test if it works when run by user (not subprocess)?
   - Check if there's environment inheritance needed?

2. **Implement LLMClient interface**
   - Create abstract base class
   - Implement ClaudeCLIClient
   - Implement GeminiCLIClient
   - Implement DualProviderClient

3. **Test both CLIs**
   - Unit tests for each client
   - Integration test for failover
   - Verify auth works in production context

4. **Update Agent base class**
   - Replace Anthropic() with DualProviderClient
   - Add provider tracking
   - Update Celery tasks

5. **Database migration**
   - Add provider columns to agent_runs
   - Create provider_usage table
   - Add indexes

---

## Questions for User

1. **Claude CLI auth issue**: When you run `claude -p "test"`, does it work without asking for auth?
2. **Provider preference**: Which should be primary - Claude or Gemini?
3. **Proceed with implementation**: Should I implement both providers now, or debug Claude CLI auth first?

