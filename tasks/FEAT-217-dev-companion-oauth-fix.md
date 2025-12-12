# Dev Companion - Fix OAuth Authentication

**Implements**: FEAT-217
**Status**: blocked
**Effort**: HIGH
**Priority**: P2
**Blocked By**: Claude Agent SDK OAuth configuration

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

**What's Broken:**
- Claude Agent SDK (`claude-agent-sdk`) requires API key by default
- User has Max subscription with OAuth authentication
- SDK returns "Invalid API key" error when trying to send messages
- Need to configure SDK to use OAuth instead of API key

## Research Findings

### Claude Agent SDK Authentication Options

From web research (2025-12-11):

1. **Default**: SDK expects `ANTHROPIC_API_KEY` environment variable
2. **OAuth Option**: `CLAUDE_CODE_OAUTH_TOKEN` env var (requires prior Anthropic approval)
3. **Community Solution**: `claude_max` project enables OAuth with Max subscriptions

### Key GitHub Issue
- https://github.com/anthropics/claude-code/issues/6536
- Users report "Invalid API key" even with OAuth tokens
- Long-lived tokens from Max plans need special handling

### Alternative Approaches

1. **Get OAuth token from Claude Code CLI session**
   - Run `claude setup-token` to get token
   - Pass to SDK via environment variable

2. **Use CLI wrapper instead of SDK**
   - Projects like `cui` and `claude-code-webui` wrap the CLI
   - CLI automatically uses existing OAuth session
   - BUT: `-p` flag is non-interactive (one prompt, one response)

3. **Request Anthropic approval for OAuth tokens**
   - Official path for third-party developers
   - May not apply to personal use

## 0.0 Scope Discovery

- [ ] Test `claude setup-token` to get OAuth token
- [ ] Check if `CLAUDE_CODE_OAUTH_TOKEN` env var works with SDK
- [ ] Review `claude_max` project for OAuth implementation details
- [ ] Check Claude Code CLI source for OAuth token storage location
- [ ] Test SDK with explicit OAuth token configuration

## Files to Modify

After scope discovery, likely:
- `services/dev-companion/dev_companion/claude_process.py` - OAuth config
- `~/.config/systemd/user/dev-companion.service` - Add OAuth env var
- Possibly new OAuth token management module

## Current Code State

```python
# services/dev-companion/dev_companion/claude_process.py
# Currently uses SDK with default (API key) auth:

self._options = ClaudeAgentOptions(
    cwd=str(self.working_dir),
    permission_mode="default",
)
self._client = ClaudeSDKClient(options=self._options)
```

## Steps

- [ ] 1. Run scope discovery to find OAuth token setup method
- [ ] 2. Configure SDK to use OAuth token instead of API key
- [ ] 3. Test end-to-end: send message, receive streaming response
- [ ] 4. Verify slash commands work (`/help`, `/audit_it`, etc.)
- [ ] 5. Update systemd service with required environment variables

## Verification

- [ ] ac-001: Send "What is 2+2?" → Get "4" response (no API key error)
- [ ] ac-002: UI shows streaming text as Claude types
- [ ] ac-003: `/help` command shows all available commands

## Commits Made

1. `55bf63b` - feat: add Dev Companion - web interface for Claude Code (MVP infra)
2. `bfec05a` - fix: add read lock to prevent concurrent stream access
3. `c9fb691` - refactor: use Claude Agent SDK instead of CLI subprocess

## Reference Links

- [claude-agent-sdk PyPI](https://pypi.org/project/claude-agent-sdk/)
- [Claude Agent SDK docs](https://docs.claude.com/en/api/agent-sdk/overview)
- [OAuth issue #6536](https://github.com/anthropics/claude-code/issues/6536)
- [claude_max project](https://idsc2025.substack.com/p/how-i-built-claude_max-to-unlock)
- [cui project](https://github.com/wbopan/cui) - Web UI reference
- [claude-code-webui](https://github.com/sugyan/claude-code-webui) - CLI wrapper reference

## Plan File

Full architecture plan at: `/home/kasadis/.claude/plans/transient-bouncing-garden.md`

## Rollback

If issues occur:
```bash
git log --oneline | head -5
git reset --hard <commit-before-dev-companion>
systemctl --user stop dev-companion
systemctl --user disable dev-companion
```

## Notes for Next Session

1. **Start by testing OAuth token setup**: `claude setup-token`
2. **Check ~/.claude/ for token storage** - may have OAuth token already
3. **Consider if `claude_max` approach is needed** - may require forking/adapting
4. **Alternative**: If SDK OAuth is blocked, consider:
   - Building proper CLI wrapper with session management
   - Using CLI in interactive mode via PTY (pseudo-terminal)
   - Waiting for Anthropic to improve SDK OAuth support
