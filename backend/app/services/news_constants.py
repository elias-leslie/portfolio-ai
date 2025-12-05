"""Shared constants for news services."""

# Special symbol used for market-level news
MARKET_SYMBOL = "__MARKET__"

# Backwards compatibility alias (deprecated, use MARKET_SYMBOL)
MARKET_TICKER = MARKET_SYMBOL

# Default configuration
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10
ARTICLE_OVERFETCH_MULTIPLIER = 3
ARTICLE_OVERFETCH_CAP = 45
ALLOWED_LOOKBACK_HOURS = {6, 12, 24, 48}
