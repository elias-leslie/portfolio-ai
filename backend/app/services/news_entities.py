"""Conservative subject matching, independent of vendor tags and event impact."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .news_constants import MARKET_SYMBOL

# Stable common names supplement the canonical symbol registry (never headline-derived).
COMMON_NAMES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "ETN": "Eaton",
    "TSLA": "Tesla",
    "GOOG": "Alphabet",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "NVDA": "Nvidia",
    "META": "Meta Platforms",
    "QCOM": "Qualcomm",
}
_SUFFIX = re.compile(
    r",?\s+(?:incorporated|inc\.?|corporation|corp\.?|plc|ltd\.?|limited|class [a-z])(?:\s|$)", re.I
)
_CONNECTION = re.compile(
    r"\b(?:supplier|customer|competitor|rival|partner(?:ship)?|competes?|supplies|supplied|exposure|contract with)\b",
    re.I,
)
_COMPANY_EVENT = re.compile(
    r"\b(?:earnings|revenue|guidance|outlook|sales|announc\w*|launch\w*|reports?|reported|raises?|cuts?)\b",
    re.I,
)
_MARKET = re.compile(
    r"\b(?:federal reserve|fed|central bank|interest rates?|treasury yields?|inflation|cpi|ppi|pce|nonfarm payrolls?|jobs report|unemployment|gdp|recession|stock market|stocks|wall street|s&p(?: 500)?|nasdaq|dow jones|market breadth|vix|oil prices?|tariffs?|trade war)\b",
    re.I,
)
_FLUFF = re.compile(
    r"\b(?:stocks? to buy|deep dive|once-in-a-decade|asked chatgpt|dominate the next decade|my favorite|hold or fold|buy or sell)\b",
    re.I,
)


@dataclass(frozen=True)
class NewsRelationship:
    kind: str
    reason: str


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html.unescape(value or ""))).strip()


def _names(symbol: str, company_name: str | None) -> list[str]:
    name = _SUFFIX.sub(" ", company_name or "").strip(" ,.")
    return list(
        dict.fromkeys(value for value in [name, COMMON_NAMES.get(symbol, "")] if len(value) >= 3)
    )


def _mention(text: str, symbol: str, names: list[str]) -> str | None:
    for name in names:
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.I):
            return name
    # Short/common-word tickers need explicit financial syntax, not an English word.
    if re.search(
        rf"(?:\${re.escape(symbol)}\b|\({re.escape(symbol)}\)|(?:NYSE|NASDAQ):\s*{re.escape(symbol)}\b)",
        text,
    ):
        return symbol
    if len(symbol) >= 3 and re.search(rf"(?<!\w){re.escape(symbol)}(?!\w)", text):
        return symbol
    return None


def identify_news_relationship(  # noqa: PLR0911 - explicit relationship cases
    symbol: str, headline: str, summary: str | None = None, company_name: str | None = None
) -> NewsRelationship:
    symbol = symbol.upper()
    title, body = _clean(headline), _clean(summary)
    if _FLUFF.search(title):
        return NewsRelationship(
            "unverified",
            "Generic stock-selection commentary; no specific decision connection established.",
        )
    if symbol == MARKET_SYMBOL:
        match = _MARKET.search(title)
        if match:
            return NewsRelationship(
                "market", f"Broad-market context: {match.group(0)} in the headline."
            )
        return NewsRelationship(
            "unverified", "The headline does not establish a broad-market connection."
        )
    names = _names(symbol, company_name)
    named = _mention(title, symbol, names)
    if named:
        return NewsRelationship(
            "direct", f"Direct coverage: the headline names {named} ({symbol})."
        )
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        named = _mention(sentence, symbol, names)
        if not named:
            continue
        if _CONNECTION.search(sentence):
            return NewsRelationship("peer", f"Connection to {named} ({symbol}): {sentence[:300]}")
        # An incidental ticker list does not establish an event about this company.
        event = re.search(
            rf"{re.escape(named)}(?:\s+\({re.escape(symbol)}\))?['\u2019]?s?\s+(.{{0,65}})",
            sentence,
            re.I,
        )
        if event and _COMPANY_EVENT.search(event.group(1)):
            return NewsRelationship("direct", f"Company event in the summary: {sentence[:300]}")
    return NewsRelationship(
        "unverified",
        f"No explicit company event or named business connection to {symbol}; vendor ticker tags alone are insufficient.",
    )
