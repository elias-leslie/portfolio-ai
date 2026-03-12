"""RSS-based news source adapters."""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import polars as pl
from feedparser import parse as parse_feed

from ..logging_config import get_logger
from ._rss_helpers import entry_to_record, in_window
from .base import BaseSource, DatasetRequest

logger = get_logger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class RssNewsSource(BaseSource):
    """Base class for simple RSS-backed news sources."""

    supports_day = False
    supports_reference = False
    supports_news = True
    DEFAULT_USER_AGENT = _DEFAULT_USER_AGENT

    def __init__(
        self,
        name: str,
        display_name: str,
        feeds: Iterable[str],
        *,
        priority: int = 60,
        symbol_feed_template: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.priority = priority
        self.feeds = list(feeds)
        self.symbol_feed_template = symbol_feed_template
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.request_timeout = 10.0
        self.rate_limit_delay = 0.25
        self.max_entries = 60
        self._last_request_ts = 0.0

    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        return None

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        return None

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        start_utc = start.astimezone(dt.UTC)
        end_utc = end.astimezone(dt.UTC)
        records: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        fetched_urls: set[str] = set()
        symbol_list = list(symbols) or ["__MARKET__"]

        for symbol in symbol_list:
            normalized = self._normalize_symbol(symbol)
            self._collect_symbol_records(
                normalized, start_utc, end_utc, records, seen_keys, fetched_urls
            )
            if len(records) >= self.max_entries:
                break

        return pl.from_dicts(records) if records else None

    def _collect_symbol_records(
        self,
        symbol: str,
        start_utc: dt.datetime,
        end_utc: dt.datetime,
        records: list[dict[str, Any]],
        seen_keys: set[tuple[str, str]],
        fetched_urls: set[str],
    ) -> None:
        for url in self._urls_for_symbol(symbol):
            if url in fetched_urls:
                continue
            fetched_urls.add(url)
            for entry in self._fetch_feed_entries(url):
                record = entry_to_record(entry, symbol, self.name, self.display_name)
                if record is None or not in_window(record, start_utc, end_utc):
                    continue
                dedupe_key = (record["symbol"], record.get("url") or record["headline"])
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                records.append(record)
                if len(records) >= self.max_entries:
                    return

    def _normalize_symbol(self, symbol: str) -> str:
        if not symbol:
            return "__MARKET__"
        if symbol.startswith("__"):
            return symbol
        return symbol.upper()

    def _urls_for_symbol(self, symbol: str) -> list[str]:
        if symbol == "__MARKET__":
            return self.feeds
        if not self.symbol_feed_template:
            return []
        template_kwargs = {"symbol": symbol, "ticker": symbol, "lower": symbol.lower()}
        try:
            return [self.symbol_feed_template.format(**template_kwargs)]
        except Exception as exc:
            logger.debug("symbol_template_failed", source=self.name, symbol=symbol, error=str(exc))
            return []

    def _rate_limit_wait(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_ts = time.time()

    def _fetch_feed_entries(self, url: str) -> list[Any]:
        try:
            self._rate_limit_wait()
            request = Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
                },
            )
            with urlopen(request, timeout=self.request_timeout) as response:
                data = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning("feed_fetch_failed", source=self.name, url=url, error=str(exc))
            return []
        except Exception as exc:  # pragma: no cover
            logger.warning("feed_fetch_failed", source=self.name, url=url, error=str(exc))
            return []
        parsed = parse_feed(data)
        return parsed.entries or []


# Re-export provider subclasses so existing importers continue to work.
from .rss_providers import (  # noqa: E402
    CNBCRssSource,
    FinancialTimesRssSource,
    FortuneRssSource,
    GoogleNewsRssSource,
    InvestingRssSource,
    MarketWatchRssSource,
    NasdaqRssSource,
    SeekingAlphaRssSource,
)

__all__ = [
    "CNBCRssSource",
    "FinancialTimesRssSource",
    "FortuneRssSource",
    "GoogleNewsRssSource",
    "InvestingRssSource",
    "MarketWatchRssSource",
    "NasdaqRssSource",
    "RssNewsSource",
    "SeekingAlphaRssSource",
]
