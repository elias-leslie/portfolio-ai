"""FastAPI application entry point for portfolio-ai."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import (
    # artifacts removed - migrated to SummitFlow (portfolio-ai-5rz)
    # claude_progress removed - Beads handles session tracking
    # disagreements removed - feature disabled (no data, unused)
    # files removed - use SummitFlow for file browsing
    # gaps removed - migrated to [DEBT] subtasks on features
    health,
    # ideas removed - deprecated in favor of strategy-seeds (FEAT-218)
    news,
    news_profiling,
    portfolio,
    preferences,
    # qa removed - issues disconnected from workflow
    recommendations,
    rules,
    # solution_map removed - Vision tab replaces Dashboard
    symbols,
    thesis,
    watchlist,
)
from app.api.market import router as market_router

# vision_content_router, vision_goals_router removed - migrated to SummitFlow (portfolio-ai-5rz)
from app.logging_config import SyslogPrefixFormatter, configure_logging, get_logger
from app.storage import get_storage
from app.storage.credential_loader import load_credentials_from_database

# Configure structured logging (skip in test mode - tests configure their own logging)
if not os.getenv("PYTEST_RUNNING"):
    configure_logging()

    # Configure uvicorn loggers to use syslog prefixes for journald
    import logging

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger = logging.getLogger("uvicorn")

    # Apply syslog formatter to all uvicorn handlers
    for uvicorn_log in [uvicorn_access_logger, uvicorn_error_logger, uvicorn_logger]:
        for handler in uvicorn_log.handlers:
            handler.setFormatter(
                SyslogPrefixFormatter(
                    "%(levelname)s:     %(message)s"  # Match uvicorn's format
                )
            )

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

    # Load API credentials from database into environment variables
    load_credentials_from_database()

    yield

    # Shutdown (placeholder for future cleanup logic)
    logger.info("Shutting down Portfolio AI Platform")


# Create FastAPI app
app = FastAPI(
    title="Portfolio AI Platform",
    description="AI-led investment intelligence platform with portfolio analytics and autonomous agents",
    version="1.0.0",
    lifespan=lifespan,
    # Disable redirect_slashes to prevent 307 redirect loops through
    # Next.js rewrites (which strip trailing slashes from proxied requests)
    redirect_slashes=False,
)

# Network configuration (from environment or fallback to defaults)
_NETWORK_HOST = os.getenv("FRONTEND_HOST", "192.168.8.233")
_TAILSCALE_HOST = os.getenv("TAILSCALE_HOST", "100.123.190.81")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
        f"http://{_NETWORK_HOST}:3000",  # Network access
        f"http://{_TAILSCALE_HOST}:3000",  # Tailscale access
        "https://localhost:3000",  # HTTPS dev server
        "https://127.0.0.1:3000",
        f"https://{_NETWORK_HOST}:3000",  # HTTPS network access
        f"https://{_NETWORK_HOST}",  # HTTPS port 443
        "https://port.summitflow.dev",  # Production (CF Access)
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
# ideas.router removed - deprecated in favor of strategy-seeds (FEAT-218)
app.include_router(market_router)
app.include_router(news.router)
app.include_router(news_profiling.router)
app.include_router(preferences.router)
app.include_router(watchlist.router, prefix="/api/watchlist")
# gaps.router removed - trading requirements migrated to Features
app.include_router(recommendations.router)  # Task 0087: Trade recommendations
# disagreements.router removed - feature disabled (no data, unused)
app.include_router(rules.router)  # Trading rules viewer
# artifacts.router removed - migrated to SummitFlow (portfolio-ai-5rz)
# vision_goals_router, vision_content_router removed - migrated to SummitFlow (portfolio-ai-5rz)
# solution_map, qa, claude_progress routers removed
app.include_router(symbols.router)  # Symbol intelligence API for agents
# files.router removed - use SummitFlow for file browsing
app.include_router(thesis.router)  # Investment thesis generation and management


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Portfolio AI Platform API",
        "version": "1.0.0",
        "docs": "/docs",
    }
