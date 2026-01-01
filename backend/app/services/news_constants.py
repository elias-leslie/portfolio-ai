"""Shared constants for news services."""

from app.constants import MARKET_SYMBOL

# Backwards compatibility alias (deprecated, use MARKET_SYMBOL)
MARKET_TICKER = MARKET_SYMBOL

# Default configuration
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10
ARTICLE_OVERFETCH_MULTIPLIER = 3
ARTICLE_OVERFETCH_CAP = 45
ALLOWED_LOOKBACK_HOURS = {6, 12, 24, 48}
