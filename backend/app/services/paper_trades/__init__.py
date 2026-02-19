"""Paper trades service subpackage.

Re-exports all public symbols so callers using the package path continue to work.
"""

from ._mutations import close_trade, reset_account, update_settings
from ._queries import get_single_trade, get_trade_summary, list_trades
from ._row_mapper import row_to_paper_trade_response

__all__ = [
    "close_trade",
    "get_single_trade",
    "get_trade_summary",
    "list_trades",
    "reset_account",
    "row_to_paper_trade_response",
    "update_settings",
]
