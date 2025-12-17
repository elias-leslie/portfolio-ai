"""Trailing slash normalization middleware.

Normalizes request paths to strip trailing slashes, ensuring endpoints work
regardless of whether the client includes a trailing slash or not.

This replaces nginx's implicit trailing slash handling that was lost when
moving to Cloudflare Tunnel.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    """Middleware to strip trailing slashes from request paths.

    FastAPI routes are inconsistent - some use "" and some use "/".
    This middleware normalizes by stripping trailing slashes so both work.

    Exceptions:
    - Root path "/" is not modified
    - Paths that would become empty are not modified
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get the path
        path = request.scope.get("path", "")

        # Strip trailing slash if path is not root and ends with /
        if path != "/" and path.endswith("/"):
            # Modify the scope's path
            request.scope["path"] = path.rstrip("/")

        return await call_next(request)
