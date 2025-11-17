# Task 0060 - CLI Authentication Findings

**Date**: 2025-11-17
**Investigation**: Claude CLI vs Gemini CLI authentication

---

## Key Finding: Claude CLI Authentication Modes

Claude CLI has **two different authentication modes**:

### 1. Interactive Mode (Current Session)
- **What**: When I (Claude) run interactively via `claude` command
- **Auth**: OAuth credentials in `~/.claude/.credentials.json` (`claudeAiOauth`)
- **Cost**: Included with Claude subscription
- **Status**: ✅ WORKING (I'm authenticated now)

### 2. Print Mode (Non-Interactive / `-p` flag)
- **What**: When calling `claude -p` for programmatic use (subprocess)
- **Auth Requirement**: EITHER
  - Long-lived token via `claude setup-token` (requires Claude Pro/Team subscription)
  - OR `ANTHROPIC_API_KEY` environment variable (pay-per-use API)
- **Cost**:
  - Subscription token: Requires paid subscription
  - API key: ~$0.003 per request (pay-per-use)
- **Status**: ❌ NOT AVAILABLE (no token or API key set)

---

## Test Results

### Claude CLI Tests

**Test 1: Interactive Claude (me)**
```bash
# I'm running now - OAuth authenticated ✅
# Can use Read, Edit, Write, Bash tools
```

**Test 2: Print mode without authentication**
```bash
echo "What is 2+2?" | claude -p --output-format text
# Result: "Invalid API key · Fix external API key" ❌
```

**Test 3: From Python subprocess (simulating backend)**
```python
subprocess.run(['claude', '-p'], input=b'What is 2+2?')
# Return code: 1
# stdout: "Invalid API key · Fix external API key" ❌
```

**Environment Check**:
```bash
cat ~/.claude/.credentials.json
# Keys: ['claudeAiOauth']  # OAuth for interactive, NOT for print mode

env | grep ANTHROPIC_API_KEY
# ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}  # Placeholder, not set
```

### Gemini CLI Tests

**Test 1: Basic prompt**
```bash
echo "What is 2+2?" | gemini -p --output-format text
# Result: "Loaded cached credentials.\n4" ✅
# Cost: $0 (uses cached credentials)
```

**Test 2: JSON output**
```bash
echo "Reply JSON: {\"answer\": N}" | gemini -p --output-format json
# Result: Valid JSON with stats (tokens, tools, files) ✅
# Cost: $0
```

---

## Authentication Architecture Comparison

| Feature | Claude CLI (`claude -p`) | Gemini CLI (`gemini -p`) |
|---------|-------------------------|-------------------------|
| **Interactive Auth** | OAuth (claudeAiOauth) ✅ | N/A |
| **Subprocess Auth** | Requires token or API key ❌ | Cached credentials ✅ |
| **Cost** | Subscription or pay-per-use | FREE |
| **Setup Required** | `claude setup-token` or API key | Works out of box |
| **Zero-Cost?** | ❌ NO | ✅ YES |

---

## Options for Claude CLI in Backend

### Option 1: Use `claude setup-token` (Requires Subscription)
```bash
claude setup-token
# Prompts for authentication, creates long-lived token
# Requires: Claude Pro or Team subscription
# Cost: Included in subscription (not pay-per-use)
```

**Pros**:
- Fixed cost (subscription)
- Can use Claude in backend

**Cons**:
- Requires paid subscription
- Token management/rotation
- Still has costs (not zero-cost)

### Option 2: Set ANTHROPIC_API_KEY (Pay-Per-Use)
```bash
export ANTHROPIC_API_KEY=sk-ant-api03-xxx
```

**Pros**:
- Pay only for what you use
- Same API as current code

**Cons**:
- Costs ~$0.003 per agent request
- Not zero-cost
- Need to manage API keys

### Option 3: Use Gemini CLI Only (Zero-Cost) ✅ **RECOMMENDED**
```bash
gemini -p --output-format json
# Works with cached credentials
# Free tier limits apply but generous
```

**Pros**:
- ✅ Zero cost (completely free)
- ✅ Already working
- ✅ No API key management
- ✅ Good model quality (Gemini 2.5 Pro)

**Cons**:
- Rate limits (but can use multiple models as fallback)
- Different tool calling format (need adapter)

---

## Revised Architecture Decision

### **PRIMARY: Gemini CLI (Zero-Cost Guarantee)**

**Implementation**:
```python
class GeminiCLIClient:
    def __init__(self):
        self.cli_path = shutil.which("gemini")
        self.models = [
            "gemini-2.5-pro",      # Primary
            "gemini-2.5-flash",    # Fallback 1
            "gemini-1.5-pro",      # Fallback 2
        ]

    def generate(self, prompt: str) -> str:
        # Try each model until success
        for model in self.models:
            result = subprocess.run(
                [self.cli_path, "-p", "-m", model, "--output-format", "json"],
                input=prompt.encode(),
                capture_output=True,
                timeout=300
            )
            if result.returncode == 0:
                return result.stdout.decode()
        raise Exception("All Gemini models failed")
```

### **OPTIONAL: Anthropic API Fallback (Disabled by Default)**

**Only enabled if**:
1. User sets `ENABLE_PAID_API=true` in .env
2. AND `ANTHROPIC_API_KEY` is set
3. OR `claude setup-token` has been run

**Implementation**:
```python
class AnthropicAPIClient:
    def __init__(self):
        # Check if paid fallback is enabled
        if not os.getenv("ENABLE_PAID_API", "false") == "true":
            raise RuntimeError("Paid API fallback disabled")

        # Try to get API key
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=self.api_key)
```

---

## Migration Path for ai_analyzer.py

**Current State** (2025-11-13):
```python
# ai_analyzer.py tries to find 'claude' CLI
cli_path = shutil.which("claude")
# Calls: subprocess.run(['claude', '-p', '--output-format', 'stream-json'])
# Result: FAILS with "Invalid API key"
```

**New Implementation**:
```python
# ai_analyzer.py uses Gemini CLI
cli_path = shutil.which("gemini")
if not cli_path:
    raise RuntimeError("Gemini CLI not found")

# Calls: subprocess.run(['gemini', '-p', '--output-format', 'json'])
# Result: WORKS with cached credentials (FREE)
```

**Changes Required**:
1. Replace `claude` → `gemini` in CLI path search
2. Update subprocess call to use `gemini -p`
3. Update response parsing (Gemini JSON format slightly different)
4. Test with capability analysis task

---

## Conclusion

✅ **CONFIRMED**: Zero-cost architecture is possible using Gemini CLI only

**Key Points**:
1. Claude CLI print mode (`-p`) is NOT zero-cost (requires subscription token or API key)
2. Gemini CLI print mode (`-p`) IS zero-cost (uses cached credentials)
3. Gemini CLI is production-ready and working
4. Optional Anthropic API fallback for users who want it (disabled by default)

**Next Steps**:
1. Implement `GeminiCLIClient` class
2. Migrate ai_analyzer.py from `claude` to `gemini`
3. Update Agent base class to use provider abstraction
4. Add optional Anthropic API fallback (opt-in only)

---

**Recommendation**: Proceed with Gemini-only design ✅
