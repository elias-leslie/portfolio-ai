"""
Backtesting API - organized into focused modules.

Modules:
- models.py: All request/response Pydantic models
- endpoints.py: Core CRUD endpoints (start, list, get, delete)
- strategy.py: Strategy metadata endpoints
- analysis.py: Comparison and Monte Carlo analysis
- walk_forward.py: Walk-forward validation endpoint

Usage in main.py:
    from app.api.backtest import router as backtest_router
    app.include_router(backtest_router)
"""

from fastapi import APIRouter

from app.api.backtest.analysis import router as analysis_router
from app.api.backtest.endpoints import router as endpoints_router
from app.api.backtest.models import (
    BacktestRunListItem,
    ComparisonResponse,
    MonteCarloRequest,
    MonteCarloResponse,
    StartBacktestRequest,
    StartBacktestResponse,
    StrategyDetailsResponse,
    WalkForwardRequest,
    WalkForwardResponse,
)
from app.api.backtest.strategy import STRATEGY_DETAILS
from app.api.backtest.strategy import router as strategy_router
from app.api.backtest.walk_forward import router as walk_forward_router

# Combine all routers under the /api/backtest prefix
router = APIRouter(prefix="/api/backtest", tags=["backtest"])
router.include_router(endpoints_router)
router.include_router(strategy_router)
router.include_router(analysis_router)
router.include_router(walk_forward_router)

__all__ = [
    "STRATEGY_DETAILS",
    "BacktestRunListItem",
    "ComparisonResponse",
    "MonteCarloRequest",
    "MonteCarloResponse",
    "StartBacktestRequest",
    "StartBacktestResponse",
    "StrategyDetailsResponse",
    "WalkForwardRequest",
    "WalkForwardResponse",
    "router",
]
