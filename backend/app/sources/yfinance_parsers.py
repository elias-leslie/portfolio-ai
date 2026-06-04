"""YFinance data parsing utilities.

Extracts and transforms raw yfinance data into standardized formats.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import math

import pandas as pd
import polars as pl

from ..logging_config import get_logger

logger = get_logger(__name__)


_SESSION_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("postMarketPrice", "postMarketTime", "post_market"),
    ("preMarketPrice", "preMarketTime", "pre_market"),
    ("regularMarketPrice", "regularMarketTime", "regular"),
)


def extract_price_from_info(
    info: dict[str, object],
) -> tuple[float | None, str | None, int | None]:
    """Pick the freshest price across regular / pre-market / post-market sessions.

    Returns (price, session_label, quote_epoch). Compares the *Time epoch fields
    and picks the most recent; quote_epoch is that vendor timestamp. Falls back to
    currentPrice (yfinance financialData) and finally previousClose when no
    timestamped session quote is available -- those carry no quote_epoch and a
    distinct session label so downstream consumers never mistake a carried-forward
    prior close for a live quote.
    """
    candidates: list[tuple[int, float, str]] = []
    for price_field, time_field, label in _SESSION_FIELDS:
        price = info.get(price_field)
        ts = info.get(time_field)
        if (
            isinstance(price, (int, float))
            and price > 0
            and isinstance(ts, (int, float))
            and ts > 0
        ):
            candidates.append((int(ts), float(price), label))

    if candidates:
        candidates.sort(key=lambda row: row[0], reverse=True)
        ts, price, label = candidates[0]
        return price, label, ts

    current = info.get("currentPrice")
    if isinstance(current, (int, float)) and current > 0:
        return float(current), "current_price", None

    previous = info.get("previousClose")
    if isinstance(previous, (int, float)) and previous > 0:
        return float(previous), "previous_close", None

    return None, None, None


def calculate_volatility_from_52w_range(info: dict[str, object]) -> float | None:
    """Calculate approximate annualized volatility from 52-week range."""
    high_52 = info.get("fiftyTwoWeekHigh")
    low_52 = info.get("fiftyTwoWeekLow")
    if (
        high_52
        and low_52
        and isinstance(high_52, (int, float))
        and isinstance(low_52, (int, float))
        and high_52 > 0
    ):
        return float((high_52 - low_52) / high_52)
    return None


def _build_reference_metrics(info: dict[str, object]) -> dict[str, object]:
    """Extract valuation, bonus, and ownership metrics from info dict."""
    return {
        # Core valuation ratios (7 target metrics)
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "priceToBook": info.get("priceToBook"),
        "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months"),
        "pegRatio": info.get("pegRatio") or info.get("trailingPegRatio"),
        "dividendYield": info.get("dividendYield"),
        "payoutRatio": info.get("payoutRatio"),
        # Bonus metrics (for comprehensive fundamentals)
        "trailingEps": info.get("trailingEps"),
        "forwardEps": info.get("forwardEps"),
        "enterpriseValue": info.get("enterpriseValue"),
        "enterpriseToRevenue": info.get("enterpriseToRevenue"),
        "enterpriseToEbitda": info.get("enterpriseToEbitda"),
        "debtToEquity": info.get("debtToEquity"),
        "currentRatio": info.get("currentRatio"),
        "returnOnEquity": info.get("returnOnEquity"),
        "returnOnAssets": info.get("returnOnAssets"),
        "profitMargins": info.get("profitMargins"),
        "operatingMargins": info.get("operatingMargins"),
        "revenueGrowth": info.get("revenueGrowth"),
        "earningsGrowth": info.get("earningsGrowth"),
        # Ownership metrics (for GAP-008 institutional ownership)
        "heldPercentInstitutions": info.get("heldPercentInstitutions"),
        "heldPercentInsiders": info.get("heldPercentInsiders"),
    }


def build_reference_payload(symbol: str, info: dict[str, object]) -> dict[str, object]:
    """Build reference payload from yfinance info dict."""
    price, price_session, quote_epoch = extract_price_from_info(info)
    quote_time = (
        dt.datetime.fromtimestamp(quote_epoch, tz=dt.UTC).isoformat()
        if quote_epoch
        else None
    )
    beta = info.get("beta")
    volatility = calculate_volatility_from_52w_range(info)

    base = {
        "symbol": symbol,
        "price": price,
        "price_session": price_session,
        "quote_time": quote_time,
        "beta": beta,
        "volatility": volatility,
        "longName": info.get("longName"),
        "shortName": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "marketCap": info.get("marketCap"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
        "country": info.get("country"),
        "website": info.get("website"),
        "description": info.get("longBusinessSummary"),
    }
    base.update(_build_reference_metrics(info))
    return base


def parse_ohlcv_to_polars(
    hist_df: pd.DataFrame,
    symbol: str,
    ingest_run_id: str | None = None,
) -> pl.DataFrame:
    """Convert pandas OHLCV DataFrame to Polars with standardized schema."""
    hist_df = hist_df.reset_index()

    df = pl.from_pandas(hist_df).select(
        [
            pl.col("Date").cast(pl.Date).alias("date"),
            pl.lit(symbol).alias("symbol"),
            pl.col("Open").alias("open"),
            pl.col("High").alias("high"),
            pl.col("Low").alias("low"),
            pl.col("Close").alias("close"),
            pl.col("Volume").cast(pl.Int64).alias("volume"),
            pl.lit(None).cast(pl.Float64).alias("vwap"),  # yfinance doesn't provide VWAP
            pl.lit("yfinance").alias("source"),
        ]
    )

    if ingest_run_id:
        df = df.with_columns(pl.lit(ingest_run_id).alias("ingest_run_id"))

    return df


def _extract_news_url(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract URL from a news item."""
    canonical: dict[str, object] = content.get("canonicalUrl") or item.get("canonicalUrl") or {}  # type: ignore[assignment]
    click_through: dict[str, object] = content.get("clickThroughUrl") or item.get("clickThroughUrl") or {}  # type: ignore[assignment]
    return canonical.get("url") or click_through.get("url") or item.get("link")  # type: ignore[return-value]


def _extract_news_published_at(
    item: dict[str, object], content: dict[str, object]
) -> dt.datetime | None:
    """Extract and parse publish timestamp from a news item."""
    publish_ts = (
        content.get("pubDate")
        or content.get("displayTime")
        or item.get("providerPublishTime")
        or item.get("published_at")
    )
    if isinstance(publish_ts, (int, float)):
        return dt.datetime.fromtimestamp(float(publish_ts), tz=dt.UTC)
    if isinstance(publish_ts, str):
        with contextlib.suppress(ValueError):
            return dt.datetime.fromisoformat(publish_ts.replace("Z", "+00:00"))
    return None


def _extract_news_publisher(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract publisher name from a news item."""
    provider_raw = content.get("provider") or item.get("provider")
    provider = provider_raw if isinstance(provider_raw, dict) else {}
    for key in ("displayName", "sourceId"):
        value = provider.get(key)
        if isinstance(value, str) and value:
            return value
    publisher = item.get("publisher")
    return publisher if isinstance(publisher, str) and publisher else None


def _extract_news_image(item: dict[str, object], content: dict[str, object]) -> str | None:
    """Extract image URL from a news item."""
    thumb_raw = content.get("thumbnail") or item.get("thumbnail")
    thumb = thumb_raw if isinstance(thumb_raw, dict) else {}
    resolutions = thumb.get("resolutions")
    if isinstance(resolutions, list) and resolutions:
        first = resolutions[0]
        if isinstance(first, dict):
            url = first.get("url")
            if isinstance(url, str) and url:
                return url
    original_url = thumb.get("originalUrl")
    return original_url if isinstance(original_url, str) and original_url else None


def parse_news_item(
    item: dict[str, object],
    symbol: str,
    is_market: bool,
    start_utc: dt.datetime,
    end_utc: dt.datetime,
) -> dict[str, object] | None:
    """Parse a single yfinance news item into standardized format.

    Args:
        item: Raw news item from yfinance
        symbol: Stock symbol
        is_market: Whether this is a market-level news item
        start_utc: Filter start time
        end_utc: Filter end time

    Returns:
        Parsed news dict or None if item should be filtered
    """
    content: dict[str, object] = item.get("content") or {}  # type: ignore[assignment]
    headline = content.get("title") or item.get("title")
    if not headline:
        return None

    summary = (
        content.get("summary")
        or content.get("description")
        or item.get("summary")
        or item.get("description")
    )
    url = _extract_news_url(item, content)
    published_at = _extract_news_published_at(item, content)

    if published_at and (published_at < start_utc or published_at > end_utc):
        return None

    return {
        "symbol": "__MARKET__" if is_market else symbol,
        "headline": headline,
        "url": url,
        "summary": summary,
        "news_source_name": _extract_news_publisher(item, content),
        "author": None,
        "image_url": _extract_news_image(item, content),
        "published_at": published_at,
        "raw_payload": json.dumps(item),
        "source": "yfinance",
    }


def parse_cash_flow_data(
    cf_df: pd.DataFrame, info: dict[str, object], symbol: str
) -> dict[str, object] | None:
    """Parse cash flow statement data."""
    if cf_df.empty:
        return None

    latest = cf_df.iloc[:, 0]

    operating_cf = latest.get("Operating Cash Flow", 0) or 0
    capex = latest.get("Capital Expenditure", 0) or 0
    free_cf = operating_cf + capex  # capex is negative

    market_cap = info.get("marketCap", 0) or 0
    shares_outstanding = info.get("sharesOutstanding", 0) or 0
    revenue = info.get("totalRevenue", 0) or 0
    net_income = info.get("netIncomeToCommon", 0) or 0

    fcf_yield = free_cf / market_cap if market_cap > 0 else None
    fcf_per_share = free_cf / shares_outstanding if shares_outstanding > 0 else None
    cash_flow_margin = operating_cf / revenue if revenue > 0 else None
    cash_conversion = operating_cf / net_income if net_income != 0 else None

    return {
        "symbol": symbol,
        "operating_cash_flow": operating_cf,
        "capital_expenditure": capex,
        "free_cash_flow": free_cf,
        "fcf_yield": fcf_yield,
        "fcf_per_share": fcf_per_share,
        "cash_flow_margin": cash_flow_margin,
        "cash_conversion_ratio": cash_conversion,
    }


def parse_insider_transactions(
    insiders_df: pd.DataFrame | None, symbol: str
) -> list[dict[str, object]]:
    """Parse insider transactions DataFrame."""
    if insiders_df is None or insiders_df.empty:
        return []

    return [
        {
            "symbol": symbol,
            "insider_name": row.get("Insider"),
            "insider_title": row.get("Position"),
            "transaction_type": row.get("Transaction"),
            "transaction_date": row.get("Start Date"),
            "shares": row.get("Shares"),
            "value": row.get("Value"),
            "shares_owned_after": row.get("Shares Owned After"),
        }
        for _, row in insiders_df.iterrows()
    ]


def parse_institutional_holders(
    holders_df: pd.DataFrame | None, info: dict[str, object], symbol: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Parse institutional holders DataFrame."""
    holders: list[dict[str, object]] = []
    if holders_df is not None and not holders_df.empty:
        holders = [
            {
                "symbol": symbol,
                "holder_name": row.get("Holder"),
                "shares": row.get("Shares"),
                "value": row.get("Value"),
                "pct_held": row.get("% Out"),
                "report_date": row.get("Date Reported"),
            }
            for _, row in holders_df.iterrows()
        ]

    summary: dict[str, object] = {
        "symbol": symbol,
        "total_institutions": len(holders),
        "pct_held_institutions": info.get("heldPercentInstitutions"),
        "pct_held_insiders": info.get("heldPercentInsiders"),
    }

    return holders, summary


def parse_short_interest(info: dict[str, object], symbol: str) -> dict[str, object] | None:
    """Parse short interest data from info dict."""
    short_shares = info.get("sharesShort")
    short_ratio = info.get("shortRatio")
    short_pct_float = info.get("shortPercentOfFloat")
    shares_outstanding = info.get("sharesOutstanding")

    if not any([short_shares, short_ratio, short_pct_float]):
        return None

    short_pct_outstanding = None
    if short_shares and shares_outstanding:
        short_pct_outstanding = float(short_shares) / float(shares_outstanding)

    return {
        "symbol": symbol,
        "short_shares": short_shares,
        "short_ratio": short_ratio,
        "short_percent_of_float": short_pct_float,
        "short_percent_of_outstanding": short_pct_outstanding,
        "short_prior_month": info.get("sharesShortPriorMonth"),
        "short_pct_change": info.get("sharesShortPreviousMonthDate"),  # This is actually a date
    }


# Quarterly statement row labels yfinance returns. Kept in one place
# because pandas frames don't carry a schema and yfinance occasionally
# adds/drops rows between minor releases — a single lookup table makes
# the breakage visible if it happens.
_INCOME_ROWS = {
    "revenue": ("Total Revenue", "TotalRevenue"),
    "gross_profit": ("Gross Profit", "GrossProfit"),
    "operating_income": ("Operating Income", "OperatingIncome"),
    "net_income": ("Net Income", "NetIncome", "Net Income Common Stockholders"),
    "ebit": ("EBIT",),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "tax_provision": ("Tax Provision", "Income Tax Expense"),
    "diluted_eps": ("Diluted EPS", "DilutedEPS", "Basic EPS"),
}
_BALANCE_ROWS = {
    "total_debt": ("Total Debt", "TotalDebt"),
    "stockholders_equity": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    "accounts_receivable": ("Accounts Receivable", "Receivables"),
    "total_assets": ("Total Assets",),
}
_CASHFLOW_ROWS = {
    "operating_cash_flow": ("Operating Cash Flow", "Total Cash From Operating Activities"),
    "free_cash_flow": ("Free Cash Flow",),
    "capital_expenditure": ("Capital Expenditure", "Capital Expenditures"),
}


def _pick_row(df: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for label in candidates:
        if label in df.index:
            row = df.loc[label]
            # Duplicated index labels yield a DataFrame; we only want the
            # first matching row in that case so downstream code can read
            # values positionally.
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return row
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(as_float):
        return None
    return as_float


def _last_n_values(series: pd.Series | None, n: int = 4) -> list[float | None]:
    if series is None:
        return []
    # yfinance returns columns oldest-last in some versions, newest-last in
    # others. Sorting by the column (period-end date) makes the orientation
    # explicit so we always read newest-first.
    try:
        sorted_series = series.sort_index(ascending=False)
    except (TypeError, ValueError):
        sorted_series = series
    return [_safe_float(v) for v in list(sorted_series.iloc[:n])]


def _ratio(numerator: object, denominator: object) -> float | None:
    n = _safe_float(numerator)
    d = _safe_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return n / d


def _yoy_growth(values: list[float | None]) -> float | None:
    """YoY growth from a list of 4 sequential quarters vs the prior 4.

    Needs at least 5 entries (current quarter + same quarter prior year).
    Returns ``(current_q / year_ago_q) - 1`` so a 12% YoY gain is 0.12.
    """
    if len(values) < 5:
        return None
    current = values[0]
    year_ago = values[4]
    if current is None or year_ago is None or year_ago == 0:
        return None
    return (current / year_ago) - 1


def parse_quarterly_fundamentals(
    *,
    symbol: str,
    quarterly_income: pd.DataFrame | None,
    quarterly_balance: pd.DataFrame | None,
    quarterly_cashflow: pd.DataFrame | None,
    info: dict[str, object],
) -> dict[str, object]:
    """Compute the L3-spec field bundle for one candidate.

    Returns every field the L3 analyst prompt cites, filling with ``None``
    when a row is missing from the yfinance frames. The caller decides
    whether to block on missingness (the readiness gate sees the absence)
    or hand the partial payload to the analyst with the gap declared.
    """
    revenue = _pick_row(quarterly_income, _INCOME_ROWS["revenue"])
    gross_profit = _pick_row(quarterly_income, _INCOME_ROWS["gross_profit"])
    operating_income = _pick_row(quarterly_income, _INCOME_ROWS["operating_income"])
    net_income = _pick_row(quarterly_income, _INCOME_ROWS["net_income"])
    ebit = _pick_row(quarterly_income, _INCOME_ROWS["ebit"])
    ebitda = _pick_row(quarterly_income, _INCOME_ROWS["ebitda"])
    tax_provision = _pick_row(quarterly_income, _INCOME_ROWS["tax_provision"])
    diluted_eps = _pick_row(quarterly_income, _INCOME_ROWS["diluted_eps"])

    total_debt = _pick_row(quarterly_balance, _BALANCE_ROWS["total_debt"])
    stockholders_equity = _pick_row(
        quarterly_balance, _BALANCE_ROWS["stockholders_equity"]
    )
    accounts_receivable = _pick_row(
        quarterly_balance, _BALANCE_ROWS["accounts_receivable"]
    )

    operating_cash_flow = _pick_row(
        quarterly_cashflow, _CASHFLOW_ROWS["operating_cash_flow"]
    )
    free_cash_flow = _pick_row(quarterly_cashflow, _CASHFLOW_ROWS["free_cash_flow"])
    capital_expenditure = _pick_row(
        quarterly_cashflow, _CASHFLOW_ROWS["capital_expenditure"]
    )

    revenue_8q = _last_n_values(revenue, n=8)
    net_income_8q = _last_n_values(net_income, n=8)
    eps_8q = _last_n_values(diluted_eps, n=8)
    ar_8q = _last_n_values(accounts_receivable, n=8)

    latest_revenue = revenue_8q[0] if revenue_8q else None
    latest_gross = _safe_float(gross_profit.iloc[0]) if gross_profit is not None else None
    latest_op_income = (
        _safe_float(operating_income.iloc[0]) if operating_income is not None else None
    )
    latest_net_income = net_income_8q[0] if net_income_8q else None
    latest_total_debt = _safe_float(total_debt.iloc[0]) if total_debt is not None else None
    latest_equity = (
        _safe_float(stockholders_equity.iloc[0])
        if stockholders_equity is not None
        else None
    )
    latest_ebit = _safe_float(ebit.iloc[0]) if ebit is not None else None
    latest_tax = _safe_float(tax_provision.iloc[0]) if tax_provision is not None else None

    nopat = None
    if latest_ebit is not None and latest_net_income is not None:
        # Effective tax rate from latest quarter; fall back to 0.21 (US statutory)
        # if the tax row is missing or pre-tax income is zero. ROIC is a noisy
        # number on a single quarter regardless — the analyst treats it as one
        # input among many.
        pretax = latest_net_income + (latest_tax or 0.0)
        tax_rate = 0.21
        if pretax and latest_tax is not None and pretax != 0:
            tax_rate = max(0.0, min(latest_tax / pretax, 0.5))
        nopat = latest_ebit * (1.0 - tax_rate)
    invested_capital = None
    if latest_total_debt is not None and latest_equity is not None:
        invested_capital = latest_total_debt + latest_equity

    market_cap = _safe_float(info.get("marketCap"))
    ev_ebitda_from_info = _safe_float(info.get("enterpriseToEbitda"))
    roe_from_info = _safe_float(info.get("returnOnEquity"))

    return {
        "symbol": symbol,
        "as_of": dt.datetime.now(dt.UTC).isoformat(),
        "revenue_ttm": (
            sum(v for v in revenue_8q[:4] if v is not None)
            if any(v is not None for v in revenue_8q[:4])
            else None
        ),
        "revenue_4q": revenue_8q[:4],
        "net_income_4q": net_income_8q[:4],
        "operating_cash_flow_4q": _last_n_values(operating_cash_flow, n=4),
        "free_cash_flow_4q": _last_n_values(free_cash_flow, n=4),
        "capital_expenditure_4q": _last_n_values(capital_expenditure, n=4),
        "gross_margin": _ratio(latest_gross, latest_revenue),
        "operating_margin": _ratio(latest_op_income, latest_revenue),
        "net_margin": _ratio(latest_net_income, latest_revenue),
        "roe": roe_from_info if roe_from_info is not None else _ratio(latest_net_income, latest_equity),
        "roic": _ratio(nopat, invested_capital),
        "debt_to_equity": _ratio(latest_total_debt, latest_equity),
        "market_cap": market_cap,
        "ev_ebitda": ev_ebitda_from_info,
        "ebitda_latest": _safe_float(ebitda.iloc[0]) if ebitda is not None else None,
        "revenue_growth_yoy": _yoy_growth(revenue_8q),
        "eps_growth_yoy": _yoy_growth(eps_8q),
        "ar_growth_vs_revenue_growth": (
            (_yoy_growth(ar_8q) - _yoy_growth(revenue_8q))
            if _yoy_growth(ar_8q) is not None and _yoy_growth(revenue_8q) is not None
            else None
        ),
    }
