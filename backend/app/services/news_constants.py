"""Shared constants for news services."""

# Special ticker used for market-level news
MARKET_TICKER = "__MARKET__"

# Default configuration
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10
ARTICLE_OVERFETCH_MULTIPLIER = 3
ARTICLE_OVERFETCH_CAP = 45
ALLOWED_LOOKBACK_HOURS = {6, 12, 24, 48}
