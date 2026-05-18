"""Entrypoint for the ``portfolio-ai-mcp`` console script.

Invoked by Claude Code / Codex CLI as a child process; FastMCP owns
stdin/stdout for the JSON-RPC framing. We deliberately do **not** call
``configure_logging()`` here — that handler writes to stdout, which would
corrupt the MCP wire protocol. Unhandled warnings/errors fall through to
Python's last-resort handler on stderr, which the parent CLI captures.
"""

from __future__ import annotations

from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
