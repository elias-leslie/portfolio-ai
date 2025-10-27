"""DuckDB storage layer for portfolio-ai.

This module provides database access and management functionality.
"""

from .facade import DuckDBStorage, get_storage

__all__ = ["DuckDBStorage", "get_storage"]
