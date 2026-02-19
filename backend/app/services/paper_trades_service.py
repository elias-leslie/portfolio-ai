"""Business logic for paper trading operations.

This module re-exports all public symbols from the paper_trades subpackage.
The API router and any other callers continue to import from this path unchanged.

Implementation is split across focused submodules:
  - paper_trades/_row_mapper.py  - DB row → Pydantic model conversion
  - paper_trades/_queries.py     - Read-only queries (list, summary, single)
  - paper_trades/_mutations.py   - Write operations (close, reset, settings)
"""

from __future__ import annotations

from app.services.paper_trades._mutations import close_trade, reset_account, update_settings
from app.services.paper_trades._queries import get_single_trade, get_trade_summary, list_trades
from app.services.paper_trades._row_mapper import row_to_paper_trade_response

__all__ = [
    "close_trade",
    "get_single_trade",
    "get_trade_summary",
    "list_trades",
    "reset_account",
    "row_to_paper_trade_response",
    "update_settings",
]
