# Gemini Chat Parity

**Implements**: FEAT-221
**Status**: planned
**Effort**: HIGH
**Priority**: P2
**Depends on**: FEAT-217 (Agent Hub)

## Context
Make Gemini a full interactive chat alternative in Agent Hub with feature parity to Claude. Currently the LLM toggle in Settings shows Gemini as "Beta" but is non-functional - selecting it does nothing. This feature will make the toggle actually switch the chat backend.

## Current State (Claude)
- Full Agent SDK integration via `dev-companion` service
- WebSocket streaming (`/ws/{session_id}`)
- Conversation memory (session-based)
- Slash commands support
- Tool use / function calling
- Context awareness (page context injection)

## Target State (Gemini Parity)
- GeminiProcessManager parallel to ClaudeProcessManager
- WebSocket streaming for Gemini responses
- Conversation history management
- Provider routing based on `llmProvider` setting
- Graceful fallback if Gemini unavailable

## 0.0 Scope Discovery (MANDATORY)
- [ ] Run Explore agent on `services/dev-companion/dev_companion/` (Claude implementation)
- [ ] Run Explore agent on `backend/app/agents/clients/gemini_client.py` (existing Gemini client)
- [ ] Document WebSocket message protocol
- [ ] Identify session management patterns
- [ ] Note streaming chunk format differences

## Files to Modify
[Populated after scope discovery]
- services/dev-companion/dev_companion/gemini_process.py (NEW) - GeminiProcessManager
- services/dev-companion/dev_companion/server.py - Provider routing
- services/dev-companion/dev_companion/session_bridge.py - Multi-provider sessions
- frontend/components/agents/AgentPanel.tsx - Send provider preference
- frontend/lib/hooks/useAgentSettings.ts (NEW) - Settings hook for provider

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT HUB - PROVIDER ROUTING                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Frontend (AgentPanel.tsx)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Settings: llmProvider = "claude" | "gemini"                         │   │
│  │ WebSocket: ws://localhost:9999/ws/{session_id}?provider={provider}  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  Dev-Companion Server (server.py)                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Route by provider query param:                                      │   │
│  │   provider=claude → ClaudeProcessManager                            │   │
│  │   provider=gemini → GeminiProcessManager                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                    │                              │                         │
│                    ▼                              ▼                         │
│  ┌──────────────────────────┐    ┌──────────────────────────┐              │
│  │ ClaudeProcessManager     │    │ GeminiProcessManager     │              │
│  │ (claude_process.py)      │    │ (gemini_process.py) NEW  │              │
│  │ - Agent SDK streaming    │    │ - Gemini API streaming   │              │
│  │ - Tool use               │    │ - Function calling       │              │
│  │ - Conversation history   │    │ - Conversation history   │              │
│  └──────────────────────────┘    └──────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Steps

### gem-001-process-manager: Create GeminiProcessManager (HIGH)
**What**: Backend process manager for Gemini chat with streaming
**Why**: Enable Gemini as interactive chat agent, not just background tasks
**How**:
- Create `gemini_process.py` mirroring `claude_process.py` structure
- Use existing `GeminiCLIClient` or direct Gemini API
- Implement streaming response chunks
- Handle conversation history (multi-turn)
- Support system prompts from settings
**Files**:
- `services/dev-companion/dev_companion/gemini_process.py` (NEW)
**Verification**: Unit test shows Gemini streaming response

### gem-002-provider-routing: Add Provider Routing to Server (MEDIUM)
**What**: Route WebSocket connections to correct provider based on setting
**Why**: Single endpoint, multiple backends
**How**:
- Accept `provider` query param on WebSocket endpoint
- Route to ClaudeProcessManager or GeminiProcessManager
- Default to Claude if not specified (backward compatible)
- Handle provider unavailable gracefully
**Files**:
- `services/dev-companion/dev_companion/server.py`
**Verification**: `wscat -c "ws://localhost:9999/ws/test?provider=gemini"` connects

### gem-003-frontend-integration: Wire Frontend to Send Provider (LOW)
**What**: AgentPanel sends selected provider to backend
**Why**: User's LLM preference must reach the server
**How**:
- Read `llmProvider` from settings (useAgentSettings hook)
- Append `?provider=${llmProvider}` to WebSocket URL
- Show provider indicator in chat header
- Handle connection errors with provider-specific messages
**Files**:
- `frontend/components/agents/AgentPanel.tsx`
**Verification**: Screenshot shows Gemini chat with provider indicator

### gem-004-conversation-history: Unified Session Management (MEDIUM)
**What**: Conversation history works for both providers
**Why**: Switching providers mid-session should preserve context (or start fresh cleanly)
**How**:
- Option A: Separate history per provider (simpler)
- Option B: Unified history with provider tags (complex)
- Store provider used for each message
- Clear session when switching providers (with confirmation)
**Files**:
- `services/dev-companion/dev_companion/session_bridge.py`
- `services/dev-companion/dev_companion/database.py`
**Verification**: Switching providers starts fresh session with confirmation

### gem-005-feature-parity-check: Verify Feature Parity (LOW)
**What**: Ensure Gemini has same capabilities as Claude in chat
**Why**: Users expect consistent experience
**How**:
- Test slash commands (may not apply to Gemini)
- Test tool use / function calling
- Test context injection (page context)
- Document any intentional differences
**Files**: None (testing only)
**Verification**: Parity checklist completed

## Acceptance Criteria
- [ ] ac-001: Gemini chat streams responses in real-time
- [ ] ac-002: LLM toggle in Settings actually switches provider
- [ ] ac-003: Provider indicator shows which LLM is active in chat
- [ ] ac-004: Conversation history maintained per provider
- [ ] ac-005: Graceful error when Gemini unavailable

## Rollback
If issues occur: `git reset --hard HEAD~1`
Services: `bash ~/portfolio-ai/scripts/restart.sh`

## Dependencies
- FEAT-217 (Agent Hub) - Must be complete (verified ✓)
- GeminiCLIClient (existing) - Or direct Gemini API
- Gemini API credentials configured

## Notes
- Gemini may not support all Claude Agent SDK features (tools, slash commands)
- Document differences rather than forcing parity where it doesn't fit
- Consider adding "capabilities" indicator per provider in UI
