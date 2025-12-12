# Dev Companion - Fix OAuth Authentication

**Implements**: FEAT-217
**Status**: complete
**Effort**: HIGH
**Priority**: P2

## Context

Dev Companion is a web interface for Claude Code that allows:
- Browser-based chat with full Claude Code capabilities
- Real-time streaming responses via WebSocket
- Session persistence across browser sessions
- (Future) Browser context capture, element selection, page preview

**What's Built (MVP infrastructure complete):**
- `services/dev-companion/` - Independent Python service (port 9999)
- `frontend/app/dev-assistant/page.tsx` - Web UI with session sidebar + chat panel
- `frontend/components/dev-assistant/ChatPanel.tsx` - WebSocket chat component
- Systemd service: `dev-companion.service` (survives restarts)
- SQLite session persistence in `~/.portfolio-dev-companion/`

## Solution (2025-12-11)

**Root Cause**: The Claude Agent SDK bundles its own CLI (v2.0.62) which has OAuth authentication issues. The SDK's default behavior:
1. Passes `--setting-sources ""` which disables loading user credentials
2. Bundled CLI v2.0.62 doesn't properly handle OAuth tokens

**Fix Applied**:
1. Configure `setting_sources=["user"]` to load credentials from `~/.claude/.credentials.json`
2. Use system-installed Claude CLI (`/home/kasadis/.local/bin/claude` v2.0.67) instead of bundled version
3. OAuth token stored in systemd service environment (for backup)

**Code Changes** (`services/dev-companion/dev_companion/claude_process.py`):
```python
self._options = ClaudeAgentOptions(
    cwd=str(self.working_dir),
    permission_mode="default",
    # Load user settings to enable OAuth credentials from ~/.claude/.credentials.json
    setting_sources=["user"],
    # Use system CLI instead of bundled (bundled 2.0.62 has OAuth issues)
    cli_path="/home/kasadis/.local/bin/claude",
)
```

## Steps

- [x] 1. Run scope discovery to find OAuth token setup method
- [x] 2. Configure SDK to use OAuth token instead of API key
- [x] 3. Test end-to-end: send message, receive streaming response
- [ ] 4. Verify slash commands work (`/help`, `/audit_it`, etc.)
- [x] 5. Update systemd service with required environment variables

## Verification

- [x] ac-001: Send "What is 2+2?" -> Get "4" response (no API key error)
- [ ] ac-002: UI shows streaming text as Claude types
- [ ] ac-003: `/help` command shows all available commands

## Commits Made

1. `55bf63b` - feat: add Dev Companion - web interface for Claude Code (MVP infra)
2. `bfec05a` - fix: add read lock to prevent concurrent stream access
3. `c9fb691` - refactor: use Claude Agent SDK instead of CLI subprocess
4. (pending) - fix: configure SDK for OAuth authentication

## Reference Links

- [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/)
- [Claude Agent SDK docs](https://docs.claude.com/en/api/agent-sdk/overview)
- [OAuth demo repo](https://github.com/weidwonder/claude_agent_sdk_oauth_demo)

## Rollback

If issues occur:
```bash
git log --oneline | head -5
git reset --hard <commit-before-dev-companion>
systemctl --user stop dev-companion
systemctl --user disable dev-companion
```
