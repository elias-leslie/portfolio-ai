"""Service monitoring and management modules."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "NewsArticle": (".news_models", "NewsArticle"),
    "NewsBundle": (".news_models", "NewsBundle"),
    "NewsService": (".news_service", "NewsService"),
    "NewsSummary": (".news_models", "NewsSummary"),
}


def __getattr__(name: str) -> Any:
    """Lazily resolve service exports to avoid unrelated heavy imports."""
    export = _EXPORTS.get(name)
    if export is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attribute_name = export
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


__all__ = ["NewsArticle", "NewsBundle", "NewsService", "NewsSummary"]
