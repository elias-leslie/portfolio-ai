"""Trailing slash redirect fix middleware.

Fixes FastAPI's redirect_slashes behavior which sends absolute URLs.
When FastAPI sends a 307 redirect with an absolute URL like http://127.0.0.1:8000/api/...,
browsers following through a proxy (like Next.js rewrites) end up bypassing the proxy.

This middleware intercepts those redirects and converts the Location header to a
relative path, ensuring the browser stays within the proxy.
"""

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    """Middleware to fix absolute URLs in redirect responses.

    FastAPI's redirect_slashes=True sends 307 redirects with absolute URLs
    including the backend's host (e.g., http://127.0.0.1:8000/api/watchlist/).
    When accessed through a proxy (Next.js rewrites, nginx), this causes the
    browser to bypass the proxy.

    This middleware converts absolute redirect URLs to relative paths.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Only process redirect responses
        if response.status_code in (301, 302, 307, 308):
            location = response.headers.get("location")
            if location:
                parsed = urlparse(location)
                # If it's an absolute URL to localhost/127.0.0.1, convert to relative
                if parsed.netloc and ("localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc):
                    # Build relative URL (path + query + fragment)
                    relative_url = parsed.path
                    if parsed.query:
                        relative_url += "?" + parsed.query
                    if parsed.fragment:
                        relative_url += "#" + parsed.fragment

                    # Create new response with fixed location
                    # MutableHeaders approach for Starlette
                    response.headers["location"] = relative_url

        return response
