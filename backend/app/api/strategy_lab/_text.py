from __future__ import annotations

STALE_HELPER_TEXT = "Quote is stale. Refresh market data before acting."
INSUFFICIENT_HISTORY_TEXT = "Not enough daily history to judge this strategy yet."
NO_TRADES_TEXT = "This strategy produced no trades over the test window."
STALE_WHY_BULLETS = [
    "Quote is stale.",
    "Refresh market data before acting.",
    "Strategy details are unavailable until fresh pricing returns.",
]
STALE_WATCH_ITEM = "Refresh and re-check this symbol during market hours."


def _stale_template(held: bool) -> str:
    return "pullback_accumulator" if held else "breakout_confirmation"
