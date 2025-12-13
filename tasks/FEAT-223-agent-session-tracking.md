# Agent Session Tracking & Conversation History

**Implements**: FEAT-223
**Status**: planned
**Effort**: HIGH
**Priority**: P2

## Context

Portfolio AI has fragmented agent tracking across multiple tables with DRY violations:
- `agent_runs` - core execution tracking with token_usage
- `strategy_reviews` - duplicates token_usage, provider columns
- `cross_validation_results` - duplicates provider/model columns (x2)
- `agent_messages` - 0 rows, designed but unused
- `agent_workflows` - workflow orchestration (43 rows)

User requirements:
- Token usage per agent (7d/14d/30d totals) - displayed as token counts, not costs
- Per chat session token count
- Session types: Me<->Agent, Me<->Multiple agents, Agent<->Agent, Agent solo
- Ability to review agent work with "Discuss This Run" capability
- Full conversation history storage
- Icon-based selectors for agent (Claude/Gemini/Both) and mode (Financial/Dev)
- Roundtable mode where both agents collaborate

## 0.0 Scope Discovery

- [x] Analyzed existing agent tables via `/api/db/agent-tables`
- [x] Identified DRY violations (token_usage, provider, model duplicated)
- [x] Documented target architecture in plan file
- [x] Reviewed Agent Hub current implementation

## Agent Hub Header UI (5 Icons)

```
Agent Hub                          [o] [chart] [clock] [signal] [gear]
                                    |     |      |       |       |
                                    |     |      |       |       Settings
                                    |     |      |       Status
                                    |     |      Sessions
                                    |     Mode (Financial/Dev)
                                    Agent (Claude/Gemini/Both)
```

### Agent Selector (cycles on click)

| Icon | State | Tooltip |
|------|-------|---------|
| diamond | Claude | "Claude - Click to switch" |
| star | Gemini | "Gemini - Click to switch" |
| diamond+star | Both | "Roundtable - Click to switch" |

### Mode Selector (cycles on click)

| Icon | State | Tooltip |
|------|-------|---------|
| chart | Financial | "Financial Mode - Click to switch" |
| laptop | Dev | "Dev Mode - Click to switch" |

## Session Types (Derived, Not Stored)

| Badge | Type | Detection Logic |
|-------|------|-----------------|
| User Chat | `user_single_agent` | `run_type='user_chat'` + no parent |
| Roundtable | `user_multi_agent` | `run_type='user_chat'` + has parent |
| Validation | `agent_agent_validation` | `run_type='cross_validation'` |
| Automated | `agent_autonomous` | `run_type='automated'` |

## Roundtable Mode (Both Agents)

When agent selector is set to "Both":
1. User message sent to both agents simultaneously
2. Agent responses displayed with icon prefix
3. "Discuss amongst yourselves" triggers agent-to-agent exchange (N rounds)
4. Direct address with `@Claude:` or `@Gemini:` to address one

## Files to Modify

### Database
- `backend/migrations/111_agent_session_tracking.sql` (NEW)
- `backend/migrations/112_agent_conversation_messages.sql` (NEW)

### Backend
- `backend/app/agents/base.py` - Instrument message storage
- `backend/app/api/agents.py` - Add new endpoints
- `backend/app/services/agent_telemetry.py` - Token aggregation

### Frontend
- `frontend/components/agents/AgentPanel.tsx` - Header icons, sessions
- `frontend/components/agents/AgentSelector.tsx` (NEW) - Cycling icon
- `frontend/components/agents/ModeSelector.tsx` (NEW) - Cycling icon
- `frontend/components/agents/TokenSummaryCards.tsx` (NEW)
- `frontend/components/agents/SessionsList.tsx` (NEW)
- `frontend/components/agents/DiscussRunModal.tsx` (NEW)
- `frontend/components/agents/RoundtableChat.tsx` (NEW)

## Steps

### Phase 1: Schema Extensions (Non-Breaking)
- [ ] Add run_type, parent_run_id, workflow_id, user_id to agent_runs
- [ ] Create agent_conversation_messages table with indexes

### Phase 2: Add FKs to Existing Tables
- [ ] Add agent_run_id FK to strategy_reviews
- [ ] Add generator_run_id, validator_run_id FKs to cross_validation_results

### Phase 3: Backend Instrumentation
- [ ] Instrument agent base class to store conversation messages
- [ ] Create token aggregation service (7d/14d/30d by provider/agent)

### Phase 4: API Endpoints
- [ ] GET /api/agents/token-summary?days=7
- [ ] GET /api/agents/runs/{id}/messages
- [ ] GET /api/agents/sessions (with derived types)
- [ ] POST /api/agents/discuss (start follow-up on previous run)
- [ ] POST /api/agents/chat (roundtable mode support)

### Phase 5: Agent Hub UI
- [ ] Icon-based agent selector (Claude/Gemini/Both)
- [ ] Icon-based mode selector (Financial/Dev)
- [ ] Token summary cards (7d/14d/30d)
- [ ] Sessions list with type badges and token counts
- [ ] "Discuss This Run" modal
- [ ] Roundtable chat interface

## Verification

- [ ] ac-001: GET /api/agents/token-summary?days=7 returns {total_tokens, by_provider, by_agent}
- [ ] ac-002: GET /api/agents/runs/{id}/messages returns array with role, content, token_count
- [ ] ac-003: Screenshot shows sessions with type badges and token counts
- [ ] ac-004: Screenshot shows Discuss modal with conversation + input field

## Dependencies

- FEAT-217 (Agent Hub) - Base UI must exist
- FEAT-220 (Automation Alignment) - Determines run_type values

## Rollback

If issues occur:
1. Drop new columns (non-breaking for existing code)
2. `git reset --hard HEAD~1`
