"""Concrete RSS news source adapters for specific providers."""

from __future__ import annotations

from .rss_source import RssNewsSource


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
