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
- Token expense per agent (7d/14d/30d totals)
- Per chat session token cost
- Session types: Me↔Agent, Me↔Multiple agents, Agent↔Agent, Agent solo
- Ability to review agent work with "Discuss This Run" capability
- Full conversation history storage

## Current Schema Analysis

### Existing Tables (via `/api/db/agent-tables`)

```
agent_runs (69 rows)
├─ id, agent_type, started_at, completed_at, status
├─ provider, model, token_usage (JSONB), session_id
├─ duration_ms, exit_code, error_message
└─ Missing: run_type, parent_run_id, workflow_id

agent_messages (0 rows) - UNUSED
├─ from_agent_run_id (FK to agent_runs)
├─ to_agent_type, message_type, content
└─ Designed for inter-agent communication

agent_workflows (43 rows)
├─ workflow_type, status, agents_involved[]
├─ shared_context, result
└─ Missing: FK to agent_runs

strategy_reviews (0 rows)
├─ token_usage (JSONB) - REDUNDANT
├─ provider - REDUNDANT
└─ Missing: agent_run_id FK

cross_validation_results (1 row)
├─ generator_provider, generator_model - REDUNDANT
├─ validator_provider, validator_model - REDUNDANT
└─ Missing: generator_run_id, validator_run_id FKs
```

### DRY Violations

| Data | Locations | Fix |
|------|-----------|-----|
| token_usage | agent_runs, strategy_reviews | Keep in agent_runs only |
| provider | agent_runs, strategy_reviews, cross_validation (x2) | Keep in agent_runs only |
| model | agent_runs, cross_validation (x2) | Keep in agent_runs only |

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       agent_runs (ENHANCED)                     │
├─────────────────────────────────────────────────────────────────┤
│ EXISTING: id, agent_type, provider, model, token_usage,         │
│           started_at, completed_at, status, duration_ms,        │
│           session_id, exit_code, error_message, metadata        │
├─────────────────────────────────────────────────────────────────┤
│ NEW COLUMNS:                                                    │
│ + run_type: 'automated' | 'user_chat' | 'cross_validation'      │
│ + parent_run_id: FK to self (for validation linking)            │
│ + workflow_id: FK to agent_workflows                            │
│ + user_id: TEXT (for manual chats, future multi-user)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 1:N
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│             agent_conversation_messages (NEW)                   │
├─────────────────────────────────────────────────────────────────┤
│ id: TEXT PRIMARY KEY                                            │
│ agent_run_id: TEXT NOT NULL (FK to agent_runs)                  │
│ sequence_num: INTEGER NOT NULL                                  │
│ role: TEXT NOT NULL ('user'|'assistant'|'system'|'tool_call'|   │
│                       'tool_result')                            │
│ content: TEXT NOT NULL                                          │
│ token_count: INTEGER                                            │
│ created_at: TIMESTAMPTZ NOT NULL DEFAULT NOW()                  │
│ metadata: JSONB (tool name, function args, etc.)                │
├─────────────────────────────────────────────────────────────────┤
│ INDEXES:                                                        │
│ - idx_agent_messages_run_id ON (agent_run_id)                   │
│ - idx_agent_messages_run_seq ON (agent_run_id, sequence_num)    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│               strategy_reviews (REFACTORED)                     │
├─────────────────────────────────────────────────────────────────┤
│ + agent_run_id: TEXT (FK to agent_runs) - NEW                   │
│ ~ token_usage: DEPRECATED (get from agent_runs)                 │
│ ~ provider: DEPRECATED (get from agent_runs)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│          cross_validation_results (REFACTORED)                  │
├─────────────────────────────────────────────────────────────────┤
│ + generator_run_id: TEXT (FK to agent_runs) - NEW               │
│ + validator_run_id: TEXT (FK to agent_runs) - NEW               │
│ ~ generator_provider/model: DEPRECATED (get from agent_runs)    │
│ ~ validator_provider/model: DEPRECATED (get from agent_runs)    │
└─────────────────────────────────────────────────────────────────┘
```

## Session Type Derivation

Session types are derived from `agent_runs` data, not stored:

```sql
SELECT
  CASE
    WHEN run_type = 'user_chat' AND parent_run_id IS NULL THEN 'user_single_agent'
    WHEN run_type = 'user_chat' AND parent_run_id IS NOT NULL THEN 'user_multi_agent'
    WHEN run_type = 'cross_validation' THEN 'agent_agent_validation'
    WHEN run_type = 'automated' THEN 'agent_autonomous'
  END as session_type
FROM agent_runs
```

## Migration Strategy

### Phase 1: Schema Extensions (Non-Breaking)

```sql
-- Migration: Add new columns to agent_runs
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS run_type TEXT DEFAULT 'automated';
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS parent_run_id TEXT REFERENCES agent_runs(id);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS workflow_id TEXT REFERENCES agent_workflows(id);
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS user_id TEXT;

-- Migration: Create agent_conversation_messages table
CREATE TABLE IF NOT EXISTS agent_conversation_messages (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    agent_run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence_num INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool_call', 'tool_result')),
    content TEXT NOT NULL,
    token_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB,
    UNIQUE (agent_run_id, sequence_num)
);

CREATE INDEX idx_conv_messages_run ON agent_conversation_messages(agent_run_id);
CREATE INDEX idx_conv_messages_run_seq ON agent_conversation_messages(agent_run_id, sequence_num);
```

### Phase 2: Add FKs to Existing Tables

```sql
-- Add FK to strategy_reviews (nullable initially for existing data)
ALTER TABLE strategy_reviews ADD COLUMN IF NOT EXISTS agent_run_id TEXT REFERENCES agent_runs(id);

-- Add FKs to cross_validation_results
ALTER TABLE cross_validation_results ADD COLUMN IF NOT EXISTS generator_run_id TEXT REFERENCES agent_runs(id);
ALTER TABLE cross_validation_results ADD COLUMN IF NOT EXISTS validator_run_id TEXT REFERENCES agent_runs(id);
```

### Phase 3: Instrument Agent Base Class

Modify `backend/app/agents/base.py` to store conversation messages:

```python
async def _store_conversation_message(
    self,
    run_id: str,
    sequence: int,
    role: str,
    content: str,
    token_count: int | None = None,
    metadata: dict | None = None
) -> None:
    """Store a conversation message for this run."""
    with self.storage.connection() as conn:
        conn.execute("""
            INSERT INTO agent_conversation_messages
            (agent_run_id, sequence_num, role, content, token_count, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (run_id, sequence, role, content, token_count,
              json.dumps(metadata) if metadata else None))
        conn.commit()
```

### Phase 4: API Endpoints

```python
# GET /api/agents/runs/{run_id}/messages
@router.get("/runs/{run_id}/messages")
async def get_run_messages(run_id: str) -> list[ConversationMessage]:
    """Get conversation history for a specific agent run."""

# GET /api/agents/token-summary
@router.get("/token-summary")
async def get_token_summary(
    days: int = Query(default=7, le=30)
) -> TokenSummary:
    """Get token usage summary by provider/agent over time period."""
```

### Phase 5: Agent Hub UI

1. **Sessions List**: Show recent runs with:
   - Agent type, status, timestamp
   - Token cost per run
   - Session type badge (derived)
   - "Discuss" button for runs with conversation history

2. **Token Summary Cards**:
   - 7d / 14d / 30d totals
   - Breakdown by provider (Gemini vs Claude)
   - Breakdown by agent type

3. **Discuss This Run Modal**:
   - Load conversation history
   - Pre-populate context
   - Allow follow-up questions

## Files to Modify

### Database
- `backend/migrations/111_agent_session_tracking.sql` (NEW)
- `backend/migrations/112_agent_conversation_messages.sql` (NEW)

### Backend
- `backend/app/agents/base.py` - Instrument message storage
- `backend/app/api/agents.py` - Add new endpoints
- `backend/app/services/agent_telemetry.py` - Enhanced aggregation

### Frontend
- `frontend/components/agents/AgentPanel.tsx` - Sessions section
- `frontend/components/agents/TokenSummaryCards.tsx` (NEW)
- `frontend/components/agents/SessionsList.tsx` (NEW)
- `frontend/components/agents/DiscussRunModal.tsx` (NEW)

## Verification

- [ ] schema-001: New columns exist in agent_runs
- [ ] schema-002: agent_conversation_messages table created with proper indexes
- [ ] schema-003: FKs added to strategy_reviews and cross_validation_results
- [ ] backend-001: Token aggregation API returns correct 7d/14d/30d totals
- [ ] backend-002: Conversation messages stored during agent runs
- [ ] backend-003: Messages endpoint returns conversation history
- [ ] ui-001: Sessions section visible in Agent Hub
- [ ] ui-002: Token summary cards show aggregated costs
- [ ] ui-003: "Discuss This Run" loads conversation as context

## Dependencies

- FEAT-217 (Agent Hub) - Base UI must exist
- FEAT-220 (Automation Alignment) - Determines run_type values

## Rollback

If issues occur:
1. Drop new columns (non-breaking for existing code)
2. `git reset --hard HEAD~1`
