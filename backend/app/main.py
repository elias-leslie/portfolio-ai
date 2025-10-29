"""FastAPI application entry point for portfolio-ai."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import analytics, health, ideas, indicators, market, portfolio, preferences, watchlist
from app.logging_config import configure_logging, get_logger
from app.storage import get_storage

# Configure structured logging
configure_logging()

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to inject request_id into each request for structured logging."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and add request_id to context."""
        request_id = str(uuid.uuid4())

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Add request_id to request state for access in endpoints
        request.state.request_id = request_id

        response = await call_next(request)

        # Add request_id to response headers for tracing
        response.headers["X-Request-ID"] = request_id

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Portfolio AI Platform")

    # Initialize storage and ensure schema exists
    storage = get_storage()
    storage.ensure_schema()

    logger.info("Database schema initialized")

    yield

    # Shutdown (placeholder for future cleanup logic)
    logger.info("Shutting down Portfolio AI Platform")


# Create FastAPI app
app = FastAPI(
    title="Portfolio AI Platform",
    description="AI-led investment intelligence platform with portfolio analytics and autonomous agents",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
        "http://192.168.8.233:3000",  # Network access
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request ID middleware for structured logging
app.add_middleware(RequestIDMiddleware)

# Register routers
app.include_router(health.router)
app.include_router(portfolio.router)
app.include_router(ideas.router)
app.include_router(market.router)
app.include_router(preferences.router)
app.include_router(analytics.router)
app.include_router(indicators.router)
app.include_router(watchlist.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Portfolio AI Platform API",
        "version": "1.0.0",
        "docs": "/docs",
    }
