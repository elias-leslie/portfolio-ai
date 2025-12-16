# Dev Companion

Web interface for Claude Code with browser context integration.

## Features

- Wraps the real Claude Code CLI (all features work automatically)
- WebSocket streaming for real-time responses
- Session persistence across browser sessions
- Browser context capture (screenshots, DOM, console)

## Installation

```bash
cd services/dev-companion
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Managed via systemd user service (do NOT start manually):

```bash
# Start/stop/restart
systemctl --user start portfolio-dev-companion
systemctl --user stop portfolio-dev-companion
systemctl --user restart portfolio-dev-companion

# Check status
systemctl --user status portfolio-dev-companion

# View logs
journalctl --user -u portfolio-dev-companion -f

# Or use the restart script (restarts all services)
bash ~/portfolio-ai/scripts/restart.sh
```

## API

- `GET /health` - Health check
- `POST /sessions` - Create new session
- `GET /sessions` - List sessions
- `GET /sessions/{id}` - Get session details
- `DELETE /sessions/{id}` - Delete session
- `WS /ws/{session_id}` - WebSocket for real-time communication
