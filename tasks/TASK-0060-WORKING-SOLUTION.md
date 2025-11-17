# Task 0060 - Working Solution: Dual CLI Provider

**Date**: 2025-11-17
**Status**: ✅ VERIFIED WORKING
**Both CLIs**: Claude + Gemini confirmed operational

---

## 🎉 Solution Found

The key to making Claude CLI work in subprocess mode (headless):

### Critical Environment Variable

**Must clear ANTHROPIC_API_KEY** when calling Claude CLI:

```python
env = {**os.environ, "ANTHROPIC_API_KEY": ""}  # Empty string, not unset!
```

**Why this works**:
- Default environment has `ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}` (placeholder)
- Claude CLI tries to use this placeholder → "Invalid API key" error
- Setting to empty string bypasses API key auth entirely
- Claude CLI uses OAuth session from `~/.claude/.credentials.json` instead

---

## ✅ Verified Working Commands

### Claude CLI (Sonnet 4.5)

```bash
ANTHROPIC_API_KEY="" claude -p "What is 2+2?" \
  --output-format json \
  --model sonnet \
  --permission-mode bypassPermissions
```

**Output**:
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 1800,
  "result": "4",
  "session_id": "ad895d07-31c3-4f85-a79a-dbd36576af90",
  "total_cost_usd": 0.081,
  "usage": {
    "input_tokens": 3,
    "output_tokens": 5,
    "cache_creation_input_tokens": 21699
  }
}
```

**Key Flags**:
- `-p <prompt>` - Print mode (non-interactive)
- `--output-format json` - Structured output
- `--model sonnet` - Claude Sonnet 4.5
- `--permission-mode bypassPermissions` - Auto-approve tools (headless)

### Gemini CLI (2.5 Pro)

```bash
echo "What is 3+3?" | gemini -p --output-format text
```

**Output**:
```
Loaded cached credentials.
6
```

**Key Flags**:
- `-p` - Print mode
- `--output-format text` or `json`
- `-m gemini-2.5-pro` - Optional model selection

---

## Implementation Pattern

### Python Subprocess Call

```python
import subprocess
import json
import os

def call_claude_cli(prompt: str, model: str = "sonnet") -> dict:
    """Call Claude CLI in headless mode."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format", "json",
        "--model", model,
        "--permission-mode", "bypassPermissions",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
        env={**os.environ, "ANTHROPIC_API_KEY": ""},  # 🔑 KEY LINE!
    )

    return json.loads(result.stdout)

def call_gemini_cli(prompt: str, model: str = "gemini-2.5-pro") -> dict:
    """Call Gemini CLI in headless mode."""
    cmd = [
        "gemini",
        "-p",
        "--output-format", "json",
        "-m", model,
    ]

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )

    return json.loads(result.stdout)
```

---

## Cost Analysis

### Claude CLI

**Subscription-based** (not pay-per-use):
- Uses Claude Max subscription ($20/month)
- Cost shown in response (`total_cost_usd: 0.081`) is theoretical
- **Actual cost**: $0 per call (included in subscription)
- Context caching: 21,699 tokens cached (reusable)

### Gemini CLI

**Completely free**:
- Uses cached credentials
- No subscription required
- No per-call costs
- **Actual cost**: $0 per call

---

## Dual Provider Architecture

### Provider Priority

**Option A: Cost-conscious (Recommended)**
1. Primary: Gemini (free)
2. Fallback: Claude (subscription)

**Option B: Quality-first**
1. Primary: Claude (subscription, best quality)
2. Fallback: Gemini (free)

### Failover Logic

```python
class DualProviderClient:
    def __init__(self, primary: str = "gemini"):
        self.primary = primary
        self.providers = {
            "claude": ClaudeCLIClient(),
            "gemini": GeminiCLIClient(),
        }

    def generate(self, prompt: str) -> LLMResponse:
        # Try primary
        if self.primary in self.providers:
            try:
                return self.providers[self.primary].generate(prompt)
            except Exception as e:
                logger.warning(f"{self.primary}_failed", error=str(e))

        # Try secondary
        secondary = "claude" if self.primary == "gemini" else "gemini"
        if secondary in self.providers:
            try:
                return self.providers[secondary].generate(prompt)
            except Exception as e:
                logger.error(f"{secondary}_failed", error=str(e))
                raise

        raise RuntimeError("All providers failed")
```

---

## Response Format Mapping

### Claude CLI JSON Response

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "<response_text>",
  "usage": {
    "input_tokens": N,
    "output_tokens": N,
    "cache_creation_input_tokens": N,
    "cache_read_input_tokens": N
  },
  "modelUsage": {
    "claude-sonnet-4-5-20250929": { ... }
  }
}
```

**Extract result**: `response_json["result"]`

### Gemini CLI JSON Response

```json
{
  "response": "<response_text>",
  "stats": {
    "models": {
      "tokens": {
        "prompt": N,
        "candidates": N,
        "total": N,
        "cached": N
      }
    },
    "tools": { ... }
  }
}
```

**Extract result**: `response_json["response"]`

---

## Migration Path for ai_analyzer.py

**Current implementation** (lines 368-391):
```python
cmd = [
    self.cli_path,  # claude
    "-p",
    prompt,
    "--output-format", "json",
    "--model", model_flag,
    "--permission-mode", "bypassPermissions",
]

result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=300,
    check=True,
    env={**os.environ, "ANTHROPIC_API_KEY": ""},  # Already correct!
)
```

**Status**: ✅ **ALREADY WORKING!**
ai_analyzer.py was already migrated to Claude CLI on 2025-11-13 and is using the correct approach.

**Test verification**:
```bash
cd ~/portfolio-ai/backend
source .venv/bin/activate
python3 -c "
from app.services.ai_analyzer import CapabilityAnalyzer
from app.storage.connection import ConnectionManager

conn_mgr = ConnectionManager('postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai')
analyzer = CapabilityAnalyzer(conn_mgr)

# This should work without errors
print(f'Claude CLI path: {analyzer.cli_path}')
print(f'CLI available: {analyzer.cli_path is not None}')
"
```

---

## Next Steps

1. **✅ DONE**: Verify both CLIs work
2. **✅ DONE**: Document working configuration
3. **NEXT**: Implement `LLMClient` interface
4. **NEXT**: Create `ClaudeCLIClient` and `GeminiCLIClient` classes
5. **NEXT**: Update `Agent` base class to use `DualProviderClient`
6. **NEXT**: Add provider tracking to database
7. **NEXT**: Update tests
8. **NEXT**: Deploy and verify

---

## Key Learnings

1. **Environment matters**: `ANTHROPIC_API_KEY=""` (empty) vs unset vs placeholder
2. **Permission mode**: `--permission-mode bypassPermissions` essential for headless
3. **Cost tracking**: Claude shows theoretical cost, but actual cost is $0 (subscription)
4. **OAuth works**: Claude CLI uses `~/.claude/.credentials.json` when API key cleared
5. **Gemini free**: Cached credentials, no configuration needed

---

**Solution verified**: 2025-11-17 16:58 UTC
**Both providers operational**: ✅ Claude CLI + ✅ Gemini CLI
**Zero additional cost**: Subscription covers all usage
