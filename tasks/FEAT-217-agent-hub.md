# Agent Hub (Dev Companion Evolution)

**Implements**: FEAT-217
**Status**: in_progress (75% base complete, extending to Agent Hub)
**Effort**: HIGH
**Priority**: P2

## Context
Dev Companion is currently a standalone page at `/dev-assistant`. This feature evolves it into a unified "Agent Hub" - a slideout panel accessible from any page that provides:
- Context-aware AI assistance (knows what page you're on)
- Dual role: Dev mode (code help) / Financial Advisor mode (market analysis)
- Multi-LLM support (Claude + Gemini)
- Cross-validation of AI outputs
- Visibility into automated agent runs with "Discuss This Run" capability

**Current state verified:**
- Services running on port 9999
- Claude SDK + OAuth working
- WebSocket streaming working
- Session persistence (SQLite)

## 0.0 Scope Discovery (MANDATORY)
- [ ] Run 2-3 "very thorough" Explore agents on:
  - Current Dev Companion implementation (`services/dev-companion/`)
  - Frontend page (`frontend/app/dev-assistant/`)
  - Existing agents page (`frontend/app/agents/`) - to migrate content
  - GeminiCLIClient (`backend/app/agents/clients/gemini_client.py`)
- [ ] Document all files to modify with line ranges
- [ ] Identify similar slideout patterns in codebase
- [ ] Note WebSocket/streaming dependencies

## Files to Modify
[Populated after scope discovery]
- frontend/app/dev-assistant/page.tsx → DELETE (standalone page removed)
- frontend/components/agents/AgentPanel.tsx (NEW) - Main slideout panel
- frontend/components/agents/RoleToggle.tsx (NEW) - Dev/Financial mode switch
- frontend/components/agents/StatusModal.tsx (NEW) - Agent telemetry from /agents
- frontend/components/agents/SettingsModal.tsx (NEW) - Role prompts, cross-validation
- frontend/components/agents/PageContextProvider.tsx (NEW) - Current page info
- frontend/components/layout/AppLayout.tsx - Add AgentPanel to layout
- services/dev-companion/dev_companion/server.py - Add Gemini endpoint
- backend/app/services/cross_validation.py (NEW) - Multi-agent review service

## UI Layout: Slideout Panel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [EXISTING PAGE - Watchlist, Dashboard, etc.]    │ AGENT PANEL (slideout)  │
│                                                  │ ───────────────────────│
│ ┌─────────────────────────────────────────────┐ │ [Dev] [Financial] toggle│
│ │                                             │ │ [⚙️ Settings] [📊 Status]│
│ │   User stays on current page                │ │                        │
│ │   No shrinking/layout change                │ │ Chat Interface         │
│ │                                             │ │ ─────────────────────  │
│ │   Agent panel slides in from right          │ │ User: "Why is NVDA     │
│ │   Panel has context of current page         │ │ showing BUY signal?"   │
│ │                                             │ │                        │
│ │                                             │ │ Claude: "Based on the  │
│ │                                             │ │ watchlist data..."     │
│ └─────────────────────────────────────────────┘ │                        │
│                                                  │ [Send Message]         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Steps

### fix-217-slideout: Convert to Slideout Panel (MEDIUM)
**What**: Convert Dev Companion from standalone `/dev-assistant` page to slideout panel
**Why**: Non-intrusive - slideout doesn't change existing pages, accessible from anywhere
**How**:
- Create `AgentPanel.tsx` component that slides from right
- Add to `AppLayout.tsx` so it's available on all pages
- Add trigger button (floating or in header)
- Preserve WebSocket connection across page navigation
**Files**:
- frontend/components/agents/AgentPanel.tsx (NEW)
- frontend/components/layout/AppLayout.tsx
- frontend/app/dev-assistant/page.tsx (DELETE after migration)
**Verification**: Slideout opens from any page, chat works, doesn't shrink main content

### fix-217-gemini: Add Gemini Client Support (LOW)
**What**: Add Gemini as second LLM option in Dev Companion
**Why**: Dual-LLM capability for cross-validation and cost optimization
**How**:
- Add Gemini endpoint to dev_companion server
- Use existing GeminiCLIClient from backend (OAuth, free)
- Add LLM selector in settings
**Files**:
- services/dev-companion/dev_companion/server.py
- services/dev-companion/dev_companion/gemini_client.py (NEW or reuse backend)
**Verification**: Can switch between Claude and Gemini, both respond correctly

### fix-217-role-toggle: Dev/Financial Advisor Mode Toggle (LOW)
**What**: Add mode toggle with separate system prompts for each role
**Why**: Same UI for dev work and financial oversight
**How**:
- Create RoleToggle.tsx component
- Store role preference in localStorage
- Each role has editable system prompt in settings
**Files**:
- frontend/components/agents/RoleToggle.tsx (NEW)
- frontend/components/agents/AgentPanel.tsx
**Verification**: Toggle switches roles, prompts change appropriately

| Mode | Context | Example Questions |
|------|---------|-------------------|
| **Dev** | Code, features, bugs | "Fix the TypeScript error on this page" |
| **Financial** | Markets, signals, strategies | "Explain the signal reasoning for NVDA" |

### fix-217-settings: Settings Modal (MEDIUM)
**What**: Add Settings modal with editable role prompts and cross-validation settings
**Why**: User customization of AI behavior
**How**:
- Create SettingsModal.tsx with tabs: Role Prompts, Cross-Validation, LLM Settings
- Store settings in localStorage (or backend API)
- Cross-validation settings: enabled, require_human_review, full_auto_mode, notify_on_disagreement, auto_apply_threshold
**Files**:
- frontend/components/agents/SettingsModal.tsx (NEW)
**Verification**: Settings persist, affect agent behavior

```
┌─────────────────────────────────────────────┐
│ Agent Settings                              │
├─────────────────────────────────────────────┤
│ Role: [Dev ▼]                               │
│                                             │
│ System Prompt:                              │
│ ┌─────────────────────────────────────────┐ │
│ │ You are a senior developer helping      │ │
│ │ with the Portfolio AI codebase...       │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ☐ Full Auto Cross-Validation               │
│ ☐ Notify on disagreements                  │
│ ☐ Auto-apply low-risk changes              │
│                                             │
│ [Save]  [Reset to Defaults]                 │
└─────────────────────────────────────────────┘
```

### fix-217-status-modal: Move Agent Telemetry to Modal (LOW)
**What**: Move content from `/agents` page to Status modal in slideout panel
**Why**: Unified location for all AI activity
**How**:
- Create StatusModal.tsx showing agent runs, success rates, token usage, queue status
- Migrate relevant components from /agents page
- Add "Automated Runs" tab to browse logged conversations
**Files**:
- frontend/components/agents/StatusModal.tsx (NEW)
- frontend/app/agents/page.tsx (reduce or redirect)
**Verification**: All /agents page functionality accessible from Status modal

### fix-217-page-context: Pass Current Page Info to Agent (LOW)
**What**: Agent knows what page user is on for context-aware responses
**Why**: "Why is NVDA showing BUY signal?" works because agent sees watchlist data
**How**:
- Create PageContextProvider that tracks current route and page data
- Inject page context into agent system prompt
- Include relevant data (e.g., current symbol, strategy, filters)
**Files**:
- frontend/components/agents/PageContextProvider.tsx (NEW)
- frontend/components/agents/AgentPanel.tsx
**Verification**: Agent responses reference current page context accurately

### fix-217-xval: Multi-Agent Cross-Validation (HIGH)
**What**: Gemini generates, Claude validates - automated quality control
**Why**: Catch errors, improve accuracy, build trust before full auto
**How**:
- Create CrossValidationService backend
- Automated validation flow: Gemini output → Claude review → human queue (initially)
- Full auto mode (later) when trust established
- Track disagreements and resolutions
**Files**:
- backend/app/services/cross_validation.py (NEW)
- frontend/components/agents/ReviewQueue.tsx (NEW)
- frontend/components/agents/DisagreementPanel.tsx (NEW)
**Verification**: Cross-validation runs, disagreements shown, human can approve/reject

Cross-Validation Settings:
| Setting | Default | Description |
|---------|---------|-------------|
| `cross_validation_enabled` | true | Run validation on automated outputs |
| `require_human_review` | true | Queue changes for user approval |
| `full_auto_mode` | false | Auto-apply validated changes |
| `notify_on_disagreement` | true | Alert when agents disagree |
| `auto_apply_threshold` | 0.9 | Confidence for auto-apply (when full auto) |

## Future Enhancement: "Discuss This Run"
Allow post-mortem conversations with agents about automated work:
- Load automated run's full conversation as context
- Ask questions: "Why did you recommend NVDA?"
- Agent feedback loop: "What would you change based on outcome?"
- Requires: `agent_conversations` table for full message history

## Verification
- [ ] Slideout panel opens from any page without shrinking content
- [ ] Role toggle switches between Dev/Financial with different prompts
- [ ] Settings modal persists preferences
- [ ] Status modal shows agent telemetry (migrated from /agents)
- [ ] Page context injected into agent prompts
- [ ] Cross-validation queues items for human review
- [ ] Both Claude and Gemini respond correctly

## Rollback
If issues occur: `git reset --hard HEAD~1`

## Dependencies
- EXISTING: Dev Companion services on port 9999
- EXISTING: Claude Agent SDK + OAuth
- EXISTING: GeminiCLIClient
- FEAT-219 (Cross-Validation) - detailed implementation there
