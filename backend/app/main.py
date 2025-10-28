"""FastAPI application entry point for portfolio-ai."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ideas, market, portfolio, preferences
from app.storage import get_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(portfolio.router)
app.include_router(ideas.router)
app.include_router(market.router)
app.include_router(preferences.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Portfolio AI Platform API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
