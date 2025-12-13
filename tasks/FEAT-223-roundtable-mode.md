# Roundtable Mode Implementation

**Implements**: FEAT-223 (subtasks: fix-display-bug, fix-agent-icons, fix-roundtable-order, fix-roundtable-impl, ui-006, backend-005)
**Status**: implemented
**Effort**: MEDIUM
**Priority**: P2

## Context

The Agent Hub has a Roundtable mode selector (both agents) but it doesn't work properly:
- Header shows "Claude + Roundtable" instead of "Claude + Gemini"
- Only one agent responds (backend doesn't handle provider=both)
- Can't tell which agent gave which response
- No auto-discussion when agents disagree

## 0.0 Scope Discovery (COMPLETED)

Files to modify identified via exploration:
- `frontend/components/agents/AgentPanel.tsx` - Main chat, WebSocket, message handling
- `frontend/components/agents/AgentSelector.tsx` - Add order dropdown
- `services/dev-companion/dev_companion/server.py` - WebSocket handler, roundtable orchestration

Key findings:
- `agentProvider` state exists but isn't sent to backend
- WebSocket uses `settings.llmProvider` instead of `agentProvider`
- Backend only accepts 'claude' or 'gemini', falls back to Claude for unknown
- Each provider has separate session handlers already implemented

## Files to Modify

- `frontend/components/agents/AgentPanel.tsx` (lines 108, 209, 528, message handling)
- `frontend/components/agents/AgentSelector.tsx` (add order selection)
- `services/dev-companion/dev_companion/server.py` (handle provider=both)

## Steps

- [x] **Step 1**: Fix display bug - change "Claude + Roundtable" to "Claude + Gemini"
- [x] **Step 2**: Add agent attribution icons (Diamond/Star) to message bubbles with tooltip
- [x] **Step 3**: Add order selection dropdown in AgentSelector when "both" selected
- [x] **Step 4**: Backend roundtable handler - sequential dual-agent orchestration
- [x] **Step 5**: Auto-discussion on disagreement (keyword detection, max 2 rounds)

## Verification

- [ ] Header shows "Claude + Gemini" when roundtable selected
- [ ] Each message shows agent icon with tooltip
- [ ] Both agents respond to user messages
- [ ] User can select Gemini-first or Claude-first order
- [ ] Agents auto-discuss when disagreement keywords detected

## Rollback

If issues occur: git reset --hard HEAD~1
