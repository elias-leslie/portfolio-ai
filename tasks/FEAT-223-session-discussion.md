# Session Discussion & History Enhancement

**Implements**: FEAT-223 (subtasks: schema-004, backend-006, backend-007, backend-008, ui-007, ui-008, fix-shared-history)
**Status**: planning
**Effort**: MEDIUM
**Priority**: P2

## Context

The Agent Hub needs enhanced session management:
1. **Roundtable shared history** - Both agents must see full conversation with proper attribution
2. **Session History UI** - List sessions with metadata (type, description, dates)
3. **Discuss Any Session** - Open any historical session for agent discussion

## Session Types

| Type | Description |
|------|-------------|
| `single:claude` | Single-agent chat with Claude |
| `single:gemini` | Single-agent chat with Gemini |
| `roundtable` | Multi-agent roundtable discussion |
| `automated` | System-triggered agent run (strategy review, etc.) |
| `discuss` | Follow-up discussion on a previous session |

## Schema Changes

**File**: `services/dev-companion/dev_companion/database.py`

Add columns to `sessions` table:
```sql
ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'single:claude';
ALTER TABLE sessions ADD COLUMN description TEXT;
ALTER TABLE sessions ADD COLUMN discussed_at TEXT;
```

**Migration strategy**:
- Run ALTER TABLE on existing DB
- Infer type from metadata or default to 'single:claude'
- Description initially NULL, populated by LLM summarization

## Session Description Generation

### Recommended Approach: Inline Agent Summarization

**Why**: The responding agent(s) have full context and can summarize as they go - zero extra API calls.

**Implementation**:
1. Add instruction to agent system prompt to include hidden session summary
2. Parse `<!-- SESSION: ... -->` from each response
3. Strip before displaying to user
4. Update session description in DB on each response
5. Dynamic updates as conversation topic evolves

**System prompt addition** (for both Claude and Gemini):
```
At the end of every response, include a hidden session summary tag:
<!-- SESSION: 5-10 word description of this conversation so far -->

Update this each response to reflect the current topic/focus. Examples:
<!-- SESSION: Debugging WebSocket reconnection issues -->
<!-- SESSION: Roundtable debate on JWT vs session auth -->
<!-- SESSION: 20 questions game - thinking of a fruit -->
<!-- SESSION: Portfolio rebalancing strategy discussion -->
```

**Parsing logic**:
```python
import re

def extract_session_summary(response: str) -> tuple[str, str | None]:
    """Extract and strip session summary from response.

    Returns: (cleaned_response, summary_or_none)
    """
    pattern = r'<!-- SESSION: (.+?) -->'
    match = re.search(pattern, response)

    if match:
        summary = match.group(1).strip()
        cleaned = re.sub(pattern, '', response).strip()
        return cleaned, summary

    return response, None
```

**Benefits**:
- Zero extra API calls (piggybacks on existing responses)
- Agent with full context is the summarizer (most accurate)
- Dynamic updates as topic evolves
- No threshold/trigger logic needed
- For roundtable: both agents contribute, most recent wins

### Alternative Approaches (Not Recommended)

| Approach | Issues |
|----------|--------|
| Separate LLM call | Extra cost, latency, complexity |
| Keyword extraction | Poor quality, requires NLP pipeline |
| First message truncation | Misses context, often just "hi" |
| Word count thresholds | Edge cases, still needs LLM call |

## Session History UI

**Location**: Top-right corner button in Agent Hub header

**Panel Design**:
```
┌─────────────────────────────────────────────┐
│ Session History                        [×] │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ abc12345  roundtable                    │ │
│ │ "Claude vs Gemini on auth approaches"  │ │
│ │ Created: 12/12 20:30  Discussed: -      │ │
│ │                              [Discuss]  │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ def67890  single:claude                 │ │
│ │ "Debugging WebSocket reconnection"      │ │
│ │ Created: 12/12 19:15  Discussed: -      │ │
│ │                              [Discuss]  │ │
│ └─────────────────────────────────────────┘ │
│ ... (max 10 visible, scrollbar if more)    │
└─────────────────────────────────────────────┘
```

**Fields per session**:
- Session ID (short, like `abc12345`)
- Session type badge (color-coded)
- Description (auto-generated or "(No description)")
- Created timestamp
- Discussed timestamp (if ever opened for discussion)
- [Discuss] button

## Discuss Session Flow

1. User clicks [Discuss] on a session
2. Frontend calls `POST /api/agents/sessions/{id}/discuss`
3. Backend loads full message history
4. Creates new session of type `discuss` with `parent_session_id` in metadata
5. Injects history as context:
   ```
   You are about to discuss a previous conversation session.

   Session type: roundtable
   Created: 2024-12-12 20:30:00

   Conversation history:
   [USER] How should we implement auth?
   [CLAUDE] I recommend JWT because...
   [GEMINI] I agree with Claude but would add...
   [USER] What about refresh tokens?
   ...

   The user wants to continue this discussion. Respond naturally.
   ```
6. Opens chat with the selected agent(s)
7. Updates `discussed_at` on original session

## Roundtable Shared History Fix

**Current problem**: Each agent only sees their own previous turns, not the full conversation.

**Fix in `server.py`**:
```python
async def build_roundtable_context(db: Database, session_id: str) -> str:
    """Build full conversation context for roundtable mode."""
    messages = await db.get_messages(session_id)

    context_parts = []
    for msg in messages:
        # Parse agent from content prefix like "[CLAUDE] response"
        if msg["role"] == "assistant":
            if msg["content"].startswith("[CLAUDE]"):
                context_parts.append(f"Claude: {msg['content'][9:]}")
            elif msg["content"].startswith("[GEMINI]"):
                context_parts.append(f"Gemini: {msg['content'][9:]}")
            else:
                context_parts.append(f"Assistant: {msg['content']}")
        elif msg["role"] == "user":
            context_parts.append(f"User: {msg['content']}")

    return "\n\n".join(context_parts)
```

Then inject this context when starting roundtable responses:
```python
# In handle_roundtable_message:
history_context = await build_roundtable_context(bridge.db, session_id)

if history_context:
    full_prompt = f"""Previous conversation:
{history_context}

User's new message: {content}

Respond to the user's new message, considering the conversation history."""
else:
    full_prompt = content
```

## Steps

- [ ] **Step 1**: Add session_type, description, discussed_at columns to DB
- [ ] **Step 2**: Fix roundtable shared history (inject full context)
- [ ] **Step 3**: Implement session description generation (Gemini Flash summarization)
- [ ] **Step 4**: Add GET /api/agents/sessions endpoint
- [ ] **Step 5**: Add POST /api/agents/sessions/{id}/discuss endpoint
- [ ] **Step 6**: Build Session History panel UI
- [ ] **Step 7**: Wire up Discuss button to open session in chat

## Verification

- [ ] Roundtable: Both agents see full conversation history with proper attribution
- [ ] Session History shows 10 sessions with scrollbar
- [ ] Each session shows ID, type badge, description, timestamps
- [ ] Clicking Discuss opens session context in chat
- [ ] Session descriptions auto-generate after 3+ messages
- [ ] discussed_at updates when session is opened for discussion

## Rollback

If issues occur: git reset --hard HEAD~1
