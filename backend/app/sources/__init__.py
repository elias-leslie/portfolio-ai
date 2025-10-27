"""Data sources for portfolio-ai.

This module provides data sources for news and macroeconomic indicators.
"""

from .fred import FREDSource
from .news import GoogleNewsSource

__all__ = ["FREDSource", "GoogleNewsSource"]
