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
    committee_runs,
    committee_stream,
    health,
    home,
    household,
    intake,
    news,
    news_profiling,
    portfolio,
    preferences,
    rules,
    symbols,
    thesis,
    watchlist,
)
from app.api.catalyst_routes import router as catalyst_router
from app.api.market import router as market_router
from app.api.retirement_routes import router as retirement_router
from app.config import settings
from app.config.cors import build_cors_origins
from app.logging_config import SyslogPrefixFormatter, configure_logging, get_logger
from app.storage import get_storage
from app.storage.credential_loader import load_credentials_from_database

# Configure structured logging (skip in test mode - tests configure their own logging)
if not os.getenv("PYTEST_RUNNING"):
    configure_logging()

    # Configure uvicorn loggers to use syslog prefixes for journald
    # Only apply syslog prefixes when running under systemd (INVOCATION_ID present);
    # in Docker/standalone mode plain log lines are cleaner for `docker logs`.
    if os.getenv("INVOCATION_ID"):
        import logging

        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_error_logger = logging.getLogger("uvicorn.error")
        uvicorn_logger = logging.getLogger("uvicorn")

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
    logger.info("platform_starting")

    # Initialize storage and ensure schema exists
    storage = get_storage()
    storage.ensure_schema()

    logger.info("database_schema_initialized")

    # Load API credentials from database into environment variables
    load_credentials_from_database()

    if not os.getenv("PYTEST_RUNNING"):
        await committee_runs.resume_incomplete_runs()

    yield

    # Shutdown (placeholder for future cleanup logic)
    logger.info("platform_shutting_down")


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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=build_cors_origins(
        frontend_host=settings.frontend_host or os.getenv("FRONTEND_HOST"),
        extra_origins=settings.frontend_extra_origins,
        frontend_url=settings.frontend_url,
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request ID middleware for structured logging
app.add_middleware(RequestIDMiddleware)


# Register routers
app.include_router(health.router)
app.include_router(home.router)
app.include_router(intake.router)
app.include_router(household.router)
app.include_router(portfolio.router)
app.include_router(catalyst_router)
app.include_router(retirement_router)
app.include_router(market_router)
app.include_router(news.router)
app.include_router(news_profiling.router)
app.include_router(preferences.router)
app.include_router(watchlist.router, prefix="/api/watchlist")
app.include_router(rules.router)
app.include_router(symbols.router)
app.include_router(thesis.router)
app.include_router(committee_runs.router)
app.include_router(committee_stream.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Portfolio AI Platform API",
        "version": "1.0.0",
        "docs": "/docs",
    }
