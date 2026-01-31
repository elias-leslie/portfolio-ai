"""WebSocket parameter validation utilities."""


def validate_provider(provider: str | None) -> str:
    """Validate and normalize provider parameter.

    Args:
        provider: Provider name ("claude", "gemini", or "both")

    Returns:
        Normalized provider name
    """
    provider = provider.lower() if provider else "claude"
    if provider not in ("claude", "gemini", "both"):
        return "claude"
    return provider


def validate_order(order: str | None) -> str:
    """Validate and normalize order parameter for roundtable.

    Args:
        order: Order preference ("claude-first" or "gemini-first")

    Returns:
        Normalized order
    """
    order = order.lower() if order else "claude-first"
    if order not in ("claude-first", "gemini-first"):
        return "claude-first"
    return order


def validate_max_turns(max_turns: int) -> int:
    """Validate and clamp max_turns to reasonable range.

    Args:
        max_turns: Maximum number of turns

    Returns:
        Clamped max_turns value
    """
    return max(1, min(100, max_turns))
