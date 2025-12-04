"""Type definitions for data sources module.

Provides TypedDicts for API responses, removing Any types and ensuring
type safety across all source adapters (Alpha Vantage, FMP, Polygon, etc.).
"""

from typing import NotRequired, TypedDict


class HTTPResponseDict(TypedDict):
    """Generic HTTP JSON response object.

    Used by HTTP clients for raw API responses before parsing.
    Represents JSON object with string keys and object values.
    """

    pass  # Intentionally empty - represents dict[str, object]


class CompanyProfileDict(TypedDict, total=False):
    """Company profile and fundamental data from API responses.

    Contains basic company info (name, sector, country) and valuation metrics
    (P/E ratio, dividend yield, market cap). Normalized across multiple vendors.

    Uses total=False to make all fields optional, as API responses vary significantly
    across vendors and yfinance may include many additional fields.
    """

    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    website: str
    marketCap: int | None
    exchange: str
    currency: str
    price: float | None
    beta: float | None
    trailingPE: float | None
    forwardPE: float | None
    dividendYield: float | None
    description: str | None
    # Additional fields from yfinance that may be present
    volatility: float | None
    longName: str
    shortName: str
    priceToBook: float
    priceToSalesTrailing12Months: float
    pegRatio: float
    payoutRatio: float
    trailingEps: float
    forwardEps: float
    enterpriseValue: int
    enterpriseToRevenue: float
    enterpriseToEbitda: float
    debtToEquity: float
    currentRatio: float
    returnOnEquity: float
    returnOnAssets: float
    profitMargins: float
    operatingMargins: float
    revenueGrowth: float
    earningsGrowth: float


class OHLCVBarDict(TypedDict):
    """Single OHLCV bar (candle) for a trading day.

    Standard daily price data format across all sources.
    """

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: NotRequired[float | None]


class OHLCVResponseDict(TypedDict):
    """API response containing OHLCV time series data.

    Different APIs use different keys/structures:
    - Alpha Vantage: {"Time Series (Daily)": {...}}
    - Finnhub: {"c": [...], "h": [...], "l": [...], "o": [...], "t": [...], "v": [...]}
    - FMP: {"historical": [...]}
    - Twelve Data: {"values": [...]}
    - Polygon: {"results": [...]}
    """

    pass  # Intentionally empty - represents dict[str, object]


class FREDDataDict(TypedDict):
    """FRED economic indicator data point.

    Single observation from Federal Reserve Economic Data (FRED) API.
    """

    indicator: str
    series_id: str
    date: str
    value: float


class RSSEntryDict(TypedDict, total=False):
    """Single entry/item from RSS feed.

    Standard RSS entry with title, link, publication date, and optional fields.
    Uses total=False for compatibility with feedparser's dynamic attributes.
    """

    title: str
    link: str
    id: str
    published_at: str | None
    summary: str
    description: str
    author: str | None
    source: object  # Dict or any value
    published_parsed: object
    updated_parsed: object
    published: str
    updated: str
    media_content: object
    media_thumbnail: object


class NewsRecordDict(TypedDict, total=False):
    """Normalized news article record for database storage.

    Standard schema for all news sources (Reuters, CNBC, SEC, RSS feeds, etc.).
    Ensures consistent fields across different vendors.
    Uses total=False for flexibility across different sources.
    """

    symbol: str
    headline: str
    url: str
    summary: str
    news_source_name: str
    author: str | None
    image_url: str | None
    published_at: str | None
    raw_payload: str
    source: str


class SECFilingDict(TypedDict):
    """SEC EDGAR filing record (8-K, 10-Q, 10-K, Form 4).

    Filing data with material event classification.
    """

    symbol: str
    filing_type: str
    filing_date: str
    accession_number: str
    url: str
    is_material_event: bool
    headline: NotRequired[str]
    summary: NotRequired[str]


class CBOEMetricsDict(TypedDict):
    """CBOE Most Active Options aggregated metrics.

    Daily snapshot of options market sentiment and positioning.
    """

    as_of_date: str
    most_active_call_pct: float
    near_term_pct: float
    concentration_pct: float
    sector_weights: dict[str, float]
    source_timestamp: str


class ContractDict(TypedDict):
    """Single option contract from CBOE Most Active.

    Represents one option contract in the top 25 most active.
    """

    symbol: str
    strike: str
    expiration: str
    type: str  # "Call" or "Put"
    volume: str
