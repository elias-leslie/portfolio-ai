"""Strategy catalog API.

Surfaces the universe-wide screening results as a browseable catalog,
plus follow/unfollow controls so user-selected strategies feed into the
daily signal workflow.
"""

from app.api.strategy_catalog import router

__all__ = ["router"]
