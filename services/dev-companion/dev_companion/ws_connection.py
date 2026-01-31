"""WebSocket connection management utilities."""

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connection state and safe sending."""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.ws_closed = False

    async def safe_send_json(self, data: dict) -> bool:
        """Send JSON to WebSocket, return False if closed."""
        if self.ws_closed:
            return False
        try:
            await self.websocket.send_json(data)
            return True
        except Exception:
            self.ws_closed = True
            return False

    def close(self) -> None:
        """Mark connection as closed."""
        self.ws_closed = True

    def is_closed(self) -> bool:
        """Check if connection is closed."""
        return self.ws_closed
