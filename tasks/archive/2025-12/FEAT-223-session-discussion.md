# Session Management & Agent Association

**Implements**: FEAT-223 (subtasks: fix-session-delete, fix-agent-badges, schema-004, schema-005, backend-006, backend-007, backend-008, backend-009, backend-010, ui-007, ui-008)
**Status**: in_progress
**Effort**: MEDIUM
**Priority**: P1

## Context

Fix session management issues in Agent Hub:
1. **Session deletion bug** - Chat stays visible after delete, returns on refresh
2. **No agent association visible** - Sessions don't show which agent(s) they started with
3. **Crash-resilient context** - Need incremental logging that survives abrupt session ends
4. **Discuss mode** - Inject session context when switching agents

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent switching | Seamless, allow mixed | User can switch agents freely within a session |
| Original agent tracking | Store `original_provider` | Track who started the session (first message) |
| Context capture | JSON response wrapper | Reliable parsing, incremental saves, crash-resilient |
| Badge locations | 3 places | Sessions dropdown, chat header, Session History panel |

## Schema Changes

**File**: `services/dev-companion/dev_companion/database.py`

```sql
-- Session metadata columns
ALTER TABLE sessions ADD COLUMN original_provider TEXT;  -- 'claude', 'gemini', 'both', NULL
ALTER TABLE sessions ADD COLUMN message_count INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN description TEXT;
ALTER TABLE sessions ADD COLUMN participants TEXT;  -- JSON array: ["claude", "gemini"]

-- Incremental log storage (crash-resilient)
CREATE TABLE session_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,  -- 'claude' or 'gemini'
    log_entry TEXT,       -- Terse worklog-style entry
    key_files TEXT,       -- JSON array of file:line references
    learnings TEXT,       -- Any lessons learned
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX idx_session_logs_session ON session_logs(session_id);
```

## JSON Response Wrapper

**Format** (agents wrap responses):
```json
{
  "message": "The actual response to show user...",
  "meta": {
    "description": "Debugging WebSocket reconnection issues",
    "log_entry": "Fixed provider switch race condition in AgentPanel",
    "key_files": ["AgentPanel.tsx:226", "server.py:150"],
    "learnings": "Gemini CLI requires -p flag when resuming sessions"
  }
}
```

**Processing** (`server.py`):
```python
async def process_agent_response(session_id: str, agent: str, response: str, db: Database):
    try:
        data = json.loads(response)
        message = data.get("message", response)
        meta = data.get("meta", {})
    except json.JSONDecodeError:
        message = response
        meta = {}

    # Save log entry immediately (crash-resilient)
    if meta.get("log_entry"):
        await db.add_session_log(
            session_id=session_id,
            agent=agent,
            log_entry=meta.get("log_entry"),
            key_files=json.dumps(meta.get("key_files", [])),
            learnings=meta.get("learnings")
        )

    # Update session metadata
    if meta.get("description"):
        await db.update_session(session_id, description=meta["description"])
    await db.increment_message_count(session_id)
    await db.add_participant(session_id, agent)

    return message  # Return clean message for display
```

## System Prompt Addition

Add to both Claude and Gemini system prompts:
```
When responding, wrap your response in JSON format:
{"message": "your response here", "meta": {"description": "brief topic", "log_entry": "what you did", "key_files": ["file:line"], "learnings": "any insights"}}
If you cannot provide meta fields, just respond normally.
```

## Handoff Context Injection

When user switches agents, inject session context from logs:

```python
async def build_handoff_context(db: Database, session_id: str) -> str:
    session = await db.get_session(session_id)
    logs = await db.get_session_logs(session_id, limit=20)

    parts = []
    parts.append(f"## Session Context (ID: {session_id[:8]})")
    parts.append(f"**Topic**: {session.get('description', 'No description')}")
    parts.append(f"**Started by**: {session.get('original_provider', 'Unknown')}")
    parts.append(f"**Participants**: {', '.join(json.loads(session.get('participants', '[]')))}")
    parts.append(f"**Messages**: {session.get('message_count', 0)}")
    parts.append("")
    parts.append("## Recent Activity (worklog)")
    for log in logs:
        agent_icon = "diamond" if log["agent"] == "claude" else "star"
        parts.append(f"- [{agent_icon}] {log['log_entry']}")
        if log.get("key_files"):
            files = json.loads(log["key_files"])
            if files:
                parts.append(f"  Files: {', '.join(files)}")
        if log.get("learnings"):
            parts.append(f"  Learning: {log['learnings']}")
    parts.append("")
    parts.append("## Learnings from Session")
    learnings = [l["learnings"] for l in logs if l.get("learnings")]
    for learning in learnings[-5:]:
        parts.append(f"- {learning}")

    return "\n".join(parts)
```

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/components/agents/AgentPanel.tsx` | Fix delete clearing, add badges, show original provider |
| `frontend/components/agents/SessionsList.tsx` | Show all session fields with badges |
| `services/dev-companion/dev_companion/database.py` | Add columns + session_logs table |
| `services/dev-companion/dev_companion/server.py` | JSON parsing, set/return fields, build handoff context |
| `services/dev-companion/dev_companion/claude_process.py` | Add JSON wrapper system prompt |
| `services/dev-companion/dev_companion/gemini_process.py` | Add JSON wrapper system prompt |

## Steps

- [ ] **Step 1**: Fix deletion bug - clear messages when deleting current session in AgentPanel.tsx
- [ ] **Step 2**: Add DB schema - columns + session_logs table
- [ ] **Step 3**: Add DB methods - add_session_log(), get_session_logs(), increment_message_count(), add_participant()
- [ ] **Step 4**: Set original_provider on first message
- [ ] **Step 5**: JSON response processing - parse wrapper, extract meta, save log entry
- [ ] **Step 6**: Return new fields in API (SessionResponse model)
- [ ] **Step 7**: Add ProviderBadge component - show in dropdown, header, Session History
- [ ] **Step 8**: Update Session History panel - created, last activity, count, description, participants
- [ ] **Step 9**: Context injection - build handoff context when agent switches

## Verification

- [ ] Delete session -> chat clears immediately, doesn't return on refresh
- [ ] New session shows no badge until first message sent
- [ ] After first message, session shows Claude/Gemini/Both badge
- [ ] Badge visible in: dropdown, chat header, Session History
- [ ] Switching agents in existing session shows "Started with: X"
- [ ] Session History shows: created time, "X ago", message count, description
- [ ] Participants shows all agents who responded
- [ ] JSON response parsing extracts description and stores in DB
- [ ] Log entries saved to session_logs immediately (check DB)
- [ ] Sending message with different agent gets handoff context injected
- [ ] Session survives simulated crash (logs persist)

## Rollback

If issues occur: git reset --hard HEAD~1
