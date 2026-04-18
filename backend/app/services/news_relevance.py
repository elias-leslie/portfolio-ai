"""Heuristics for filtering symbol-specific news down to genuinely relevant articles."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from .news_constants import MARKET_SYMBOL
from .news_decision_support import assess_news_article
from .news_models import NewsArticle

_ALIAS_STOPWORDS = {
    "a",
    "an",
    "and",
    "best",
    "breaking",
    "favorite",
    "forget",
    "gotta",
    "here",
    "heres",
    "how",
    "is",
    "know",
    "lingo",
    "market",
    "markets",
    "my",
    "pick",
    "reasons",
    "stock",
    "stocks",
    "the",
    "this",
    "wall",
    "week",
    "what",
    "why",
}
_GENERIC_FLUFF_PATTERNS = (
    r"\bstocks?\s+to\s+buy\b",
    r"\bdeep dive\b",
    r"\bonce-in-a-decade\b",
    r"\bweek ahead\b",
    r"\bgotta know the lingo\b",
    r"\basked chatgpt\b",
    r"\bdominate the next decade\b",
    r"\bmy favorite\b",
)
_LEADING_ALIAS_PATTERN = re.compile(r"^([A-Z][A-Za-z0-9&.'/-]+(?:\s+[A-Z][A-Za-z0-9&.'/-]+){0,2})")
_SYMBOL_TOKEN_TEMPLATE = r"(?<![A-Z0-9]){symbol}(?![A-Z0-9])"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lower_text(value: Any) -> str:
    return _clean_text(value).lower()


def _article_text(article: NewsArticle) -> str:
    return " ".join(
        part
        for part in (
            _clean_text(article.headline),
            _clean_text(article.summary),
            _clean_text(article.url),
        )
        if part
    ).lower()


def _article_raw(article: NewsArticle) -> dict[str, Any]:
    raw = article.raw if isinstance(article.raw, dict) else {}
    nested = raw.get("raw") if isinstance(raw.get("raw"), dict) else {}
    return {**nested, **raw}


def _vendor_payload(article: NewsArticle) -> dict[str, Any]:
    payload = _article_raw(article).get("vendor_payload")
    return payload if isinstance(payload, dict) else {}


def _normalize_symbols(value: Any) -> set[str]:
    if isinstance(value, str):
        return {token.strip().upper() for token in re.split(r"[,\s]+", value) if token.strip()}
    if isinstance(value, Iterable):
        normalized: set[str] = set()
        for item in value:
            normalized |= _normalize_symbols(item)
        return normalized
    return set()


def _related_symbol(article: NewsArticle) -> str | None:
    payload = _vendor_payload(article)
    for key in ("related", "ticker"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def _ticker_set(article: NewsArticle) -> set[str]:
    payload = _vendor_payload(article)
    tickers = set()
    tickers |= _normalize_symbols(payload.get("tickers"))
    tickers |= _normalize_symbols(payload.get("symbols"))
    return tickers


def _insight_ticker_set(article: NewsArticle) -> set[str]:
    payload = _vendor_payload(article)
    insights = payload.get("insights")
    tickers: set[str] = set()
    if isinstance(insights, list):
        for insight in insights:
            if isinstance(insight, dict):
                tickers |= _normalize_symbols(insight.get("ticker"))
    return tickers


def _has_symbol_token(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(_SYMBOL_TOKEN_TEMPLATE.format(symbol=re.escape(symbol)), text, re.IGNORECASE) is not None


def _headline_aliases(headline: str) -> set[str]:
    cleaned = _clean_text(headline)
    if not cleaned:
        return set()
    match = _LEADING_ALIAS_PATTERN.match(cleaned)
    if not match:
        return set()
    phrase = match.group(1).strip(" .:-")
    if not phrase:
        return set()
    aliases = set()
    first_word = phrase.split()[0].strip(" .:-").lower()
    if first_word and first_word not in _ALIAS_STOPWORDS:
        aliases.add(first_word)
    return {
        alias
        for alias in aliases
        if len(alias) >= 3 and alias not in _ALIAS_STOPWORDS and not alias.isdigit()
    }


def _strong_direct_evidence(article: NewsArticle, symbol: str) -> bool:
    symbol = symbol.upper()
    related = _related_symbol(article)
    text = " ".join(
        part for part in (_clean_text(article.headline), _clean_text(article.url)) if part
    ).lower()
    return bool(related == symbol or _has_symbol_token(text, symbol))


def _build_aliases(symbol: str, articles: Sequence[NewsArticle]) -> set[str]:
    aliases = {symbol.lower()}
    alias_counts: Counter[str] = Counter()
    for article in articles:
        if not _strong_direct_evidence(article, symbol):
            continue
        if _related_symbol(article) == symbol:
            alias_counts.update(_headline_aliases(article.headline))
    if alias_counts:
        top_alias, top_count = alias_counts.most_common(1)[0]
        if top_count >= 2 or len(alias_counts) == 1:
            aliases.add(top_alias)
    return aliases


def _mentions_alias(article: NewsArticle, aliases: set[str], symbol: str) -> bool:
    text = _article_text(article)
    if _has_symbol_token(text, symbol):
        return True
    for alias in aliases:
        if len(alias) < 3:
            continue
        if alias in text:
            return True
    return False


def _symbol_relevance_score(article: NewsArticle, symbol: str, aliases: set[str]) -> int:
    assessment = assess_news_article(article)
    related = _related_symbol(article)
    tickers = _ticker_set(article)
    insight_tickers = _insight_ticker_set(article)
    mentions_alias = _mentions_alias(article, aliases, symbol)
    text = _article_text(article)
    score = 0

    if related and related != symbol and not mentions_alias:
        return -999
    if tickers and symbol not in tickers and related != symbol and not mentions_alias:
        return -999
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in _GENERIC_FLUFF_PATTERNS):
        return -999

    if related == symbol:
        score += 4
    if mentions_alias:
        score += 3
    if symbol in tickers:
        score += 2
    if symbol in insight_tickers:
        score += 2
    if article.url and any(alias in _lower_text(article.url) for alias in aliases if len(alias) >= 3):
        score += 1

    strong_anchor = mentions_alias or (symbol in tickers and len(tickers) <= 2)
    if related == symbol and not strong_anchor and (assessment.decision_value_score or 0.0) < 0.6:
        score -= 3
    if len(tickers) > 4 and not mentions_alias:
        score -= 2
    if symbol in insight_tickers and not strong_anchor and len(tickers) > 2:
        score -= 2
    if assessment.source_signal_tier == "commentary" and score < 4:
        score -= 1
    if (assessment.decision_value_score or 0.0) < 0.35:
        score -= 1
    if not mentions_alias and symbol not in tickers and symbol not in insight_tickers and related != symbol:
        score -= 2
    if " etf" in text and symbol not in tickers and related != symbol and not mentions_alias:
        score -= 1

    return score


def filter_symbol_relevant_articles(
    symbol: str,
    articles: Sequence[NewsArticle],
) -> list[NewsArticle]:
    """Return only articles that look genuinely relevant to *symbol*."""
    normalized_symbol = (symbol or "").upper()
    if normalized_symbol == MARKET_SYMBOL:
        return list(articles)

    aliases = _build_aliases(normalized_symbol, articles)
    filtered: list[NewsArticle] = []
    for article in articles:
        score = _symbol_relevance_score(article, normalized_symbol, aliases)
        if score >= 3:
            filtered.append(article)
    return filtered
