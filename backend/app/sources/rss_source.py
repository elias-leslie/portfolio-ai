"""RSS-based news source adapters."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import time
from collections.abc import Iterable
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import polars as pl
from dateutil import parser as date_parser
from feedparser import parse as parse_feed

from ..logging_config import get_logger
from .base import BaseSource, DatasetRequest

logger = get_logger(__name__)


class RssNewsSource(BaseSource):
    """Base class for simple RSS-backed news sources."""

    supports_day = False
    supports_reference = False
    supports_news = True

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

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

    # Unused datasets -----------------------------------------------------
    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        return None

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        return None

    # News fetching -------------------------------------------------------
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
            normalized_symbol = self._normalize_symbol(symbol)
            urls = self._urls_for_symbol(normalized_symbol)
            if not urls:
                continue

            for url in urls:
                if url in fetched_urls:
                    continue
                fetched_urls.add(url)
                for entry in self._fetch_feed_entries(url):
                    record = self._entry_to_record(entry, normalized_symbol)
                    if record is None:
                        continue

                    published_at = record.get("published_at")
                    if isinstance(published_at, dt.datetime) and (
                        published_at < start_utc or published_at > end_utc
                    ):
                        continue

                    dedupe_key = (record["symbol"], record.get("url") or record["headline"])
                    if dedupe_key in seen_keys:
                        continue
                    seen_keys.add(dedupe_key)

                    records.append(record)
                    if len(records) >= self.max_entries:
                        break

                if len(records) >= self.max_entries:
                    break
            if len(records) >= self.max_entries:
                break

        if not records:
            return None

        return pl.from_dicts(records)

    # Helpers -------------------------------------------------------------
    def _normalize_symbol(self, symbol: str) -> str:
        if not symbol:
            return "__MARKET__"
        if symbol.startswith("__"):
            return symbol
        return symbol.upper()

    def _urls_for_symbol(self, symbol: str) -> list[str]:
        if symbol == "__MARKET__":
            return self.feeds
        if self.symbol_feed_template:
            template_kwargs = {
                "symbol": symbol,
                "ticker": symbol,
                "lower": symbol.lower(),
            }
            try:
                return [self.symbol_feed_template.format(**template_kwargs)]
            except Exception as exc:
                logger.debug("%s_symbol_template_failed", self.name, symbol=symbol, error=str(exc))
                return []
        # No symbol-specific feed configured; skip to avoid mislabeling.
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
            logger.warning("%s_feed_fetch_failed", self.name, url=url, error=str(exc))
            return []
        except Exception as exc:  # pragma: no cover
            logger.warning("%s_feed_fetch_failed", self.name, url=url, error=str(exc))
            return []

        parsed = parse_feed(data)
        return parsed.entries or []

    def _entry_to_record(self, entry: Any, symbol: str) -> dict[str, Any] | None:
        title = (entry.get("title") or "").strip()
        link = entry.get("link") or entry.get("id") or ""
        if not title or not link:
            return None

        published_at = self._parse_published(entry)
        summary = entry.get("summary") or entry.get("description") or ""
        publisher = self._extract_publisher(entry)
        image_url = self._extract_image(entry)

        payload = {
            "title": title,
            "link": link,
            "summary": summary,
            "source": publisher,
            "published": entry.get("published"),
        }

        return {
            "symbol": symbol,
            "headline": title,
            "summary": summary,
            "url": link,
            "news_source_name": publisher,
            "author": entry.get("author"),
            "image_url": image_url,
            "published_at": published_at,
            "raw_payload": json.dumps(payload, default=str),
            "source": self.name,
        }

    def _parse_published(self, entry: Any) -> dt.datetime | None:
        struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct_time:
            try:
                return dt.datetime.fromtimestamp(time.mktime(struct_time), tz=dt.UTC)
            except Exception:
                pass

        date_str = entry.get("published") or entry.get("updated")
        if date_str:
            with contextlib.suppress(Exception):
                parsed = cast(dt.datetime, date_parser.parse(date_str))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.UTC)
                return parsed.astimezone(dt.UTC)
        return None

    def _extract_publisher(self, entry: Any) -> str:
        source = entry.get("source", {})
        if isinstance(source, dict):
            name = source.get("title")
            if isinstance(name, str) and name.strip():
                return name
        publisher = entry.get("publisher")
        if isinstance(publisher, str) and publisher.strip():
            return publisher
        return self.display_name

    def _extract_image(self, entry: Any) -> str | None:
        media_content = entry.get("media_content") or entry.get("media_thumbnail")
        if isinstance(media_content, list):
            for candidate in media_content:
                if isinstance(candidate, dict):
                    url = candidate.get("url")
                    if isinstance(url, str) and url:
                        return url
        return None


class CNBCRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = [
            "https://www.cnbc.com/id/10000664/device/rss/rss.html",  # Finance
            "https://www.cnbc.com/id/15839135/device/rss/rss.html",  # Earnings
        ]
        super().__init__(
            name="cnbc_rss",
            display_name="CNBC",
            feeds=feeds,
            priority=60,
        )


class MarketWatchRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://www.marketwatch.com/rss/topstories"]
        super().__init__(
            name="marketwatch_rss",
            display_name="MarketWatch",
            feeds=feeds,
            priority=60,
        )


class NasdaqRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://www.nasdaq.com/feed/nasdaq-original/rss.xml"]
        super().__init__(
            name="nasdaq_rss",
            display_name="Nasdaq",
            feeds=feeds,
            priority=60,
            symbol_feed_template="https://www.nasdaq.com/feed/rssoutbound?symbol={ticker}",
        )


class FortuneRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://fortune.com/feed"]
        super().__init__(
            name="fortune_rss",
            display_name="Fortune",
            feeds=feeds,
            priority=65,
        )


class InvestingRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://www.investing.com/rss/market_overview.rss"]
        super().__init__(
            name="investing_rss",
            display_name="Investing.com",
            feeds=feeds,
            priority=65,
        )


class FinancialTimesRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://www.ft.com/?format=rss"]
        super().__init__(
            name="ft_rss",
            display_name="Financial Times",
            feeds=feeds,
            priority=65,
        )


class SeekingAlphaRssSource(RssNewsSource):
    def __init__(self) -> None:
        feeds = ["https://seekingalpha.com/feed.xml"]
        super().__init__(
            name="seeking_alpha_rss",
            display_name="Seeking Alpha",
            feeds=feeds,
            priority=65,
            symbol_feed_template="https://seekingalpha.com/api/sa/combined/{lower}.xml",
        )


class GoogleNewsRssSource(RssNewsSource):
    def __init__(self) -> None:
        # Market-wide feed for general news
        feeds = ["https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en"]
        super().__init__(
            name="google_news_rss",
            display_name="Google News",
            feeds=feeds,
            priority=70,  # Lower priority (higher number) due to aggregation nature
            symbol_feed_template="https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en",
        )
