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

```bash
# Start the server
python -m dev_companion

# Or with environment variables
PORT=9999 WORKING_DIR=/path/to/project python -m dev_companion
```

## API

- `GET /health` - Health check
- `POST /sessions` - Create new session
- `GET /sessions` - List sessions
- `GET /sessions/{id}` - Get session details
- `DELETE /sessions/{id}` - Delete session
- `WS /ws/{session_id}` - WebSocket for real-time communication
