"""Symbol Intelligence API - Backwards compatibility re-export.

This module has been refactored into app.api.symbols/ package.
This file provides backwards compatibility by re-exporting the router.

New structure:
- symbols/models.py: Pydantic response models
- symbols/data_fetchers.py: Data fetching functions
- symbols/builders.py: Response section builders
- symbols/recommendations.py: Recommendation logic
- symbols/router.py: FastAPI router and endpoint
"""

from __future__ import annotations

# Re-export router for backwards compatibility
from app.api.symbols.router import router

__all__ = ["router"]
