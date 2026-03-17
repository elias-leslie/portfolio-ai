"""SEC EDGAR data source adapter using edgartools library.

This module provides access to SEC EDGAR filings as a news source,
including 8-K material events, Form 4 insider trades, and quarterly/annual reports.

Free tier, no API key required. Uses edgartools library for compliance and performance.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar

import polars as pl

from ..constants import SEC_USER_AGENT
from ..logging_config import get_logger
from .base import BaseSource
from .sec_cik_fetcher import get_cik

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

# Lazy import to avoid startup overhead
_edgar = None
_set_identity_called = False

logger = get_logger(__name__)


def _get_edgar() -> Any:
    """Lazy import edgartools and set User-Agent identity."""
    global _edgar, _set_identity_called  # noqa: PLW0603

    if _edgar is None:
        # Ensure HOME environment variable is set to a writable directory
        # This prevents edgartools and other libraries from trying to create
        # cache files in non-existent /home/portfolio-ai directory
        if not os.environ.get("HOME"):
            os.environ["HOME"] = "/var/cache/portfolio-ai"
            logger.info("home_env_set", home_dir="/var/cache/portfolio-ai")

        import edgar as edgar_module  # noqa: PLC0415

        _edgar = edgar_module

        # Set User-Agent for SEC compliance (required)
        # SEC requests traffic identification with company/contact info
        # See: https://www.sec.gov/os/webmaster-faq#developers
        if not _set_identity_called:
            edgar_module.set_identity(SEC_USER_AGENT)
            _set_identity_called = True
            logger.info("sec_edgar_identity_set")

    return _edgar


class SECEdgarSource(BaseSource):
    """SEC EDGAR filings source using edgartools library.

    Provides access to:
    - 8-K: Material events (earnings, M&A, exec changes)
    - Form 4: Insider trades
    - 10-Q: Quarterly reports
    - 10-K: Annual reports

    All filings are free and publicly available. No API key required.
    Compliance (User-Agent, rate limiting) handled by edgartools.
    """

    name = "sec_edgar"
    priority = 5  # Highest priority (above all other news sources)
    supports_day = False
    supports_reference = False
    supports_news = True

    # Filing types to fetch
    FILING_TYPES: ClassVar[list[str]] = ["8-K", "10-Q", "10-K", "4"]

    def __init__(self, storage: PortfolioStorage | None = None) -> None:
        """Initialize SEC EDGAR source.

        Args:
            storage: Optional PortfolioStorage instance for CIK cache lookups.
                    If not provided, will create one on first use.
        """
        # edgartools will be imported lazily on first use
        self._storage = storage
        logger.info("sec_edgar_source_initialized")

    def fetch_day_bars(self, request: Any) -> pl.DataFrame | None:
        """Not implemented - SEC EDGAR only provides news/filings."""
        return None

    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Not implemented - SEC EDGAR only provides news/filings."""
        return None

    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch SEC filings as news articles.

        Args:
            symbols: List of symbols
            start: Start datetime (UTC)
            end: End datetime (UTC)

        Returns:
            DataFrame with columns: symbol, headline, url, published_at, source, summary,
                                   filing_type, filing_items, is_material_event
        """
        edgar = _get_edgar()
        records: list[dict[str, Any]] = []

        # Convert to dates for edgartools API
        start_date = start.date()
        end_date = end.date()

        symbol_list = list(symbols) or ["__MARKET__"]

        logger.info(
            "sec_edgar_fetch_start",
            num_symbols=len(symbol_list),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        for symbol in symbol_list:
            # Skip market-level requests (SEC is symbol-specific)
            if symbol in (None, "__MARKET__"):
                continue

            try:
                # Get CIK from local cache (bypasses SEC API symbol lookup)
                if self._storage is None:
                    # Lazy import to avoid circular dependency
                    from ..storage import PortfolioStorage  # noqa: PLC0415

                    self._storage = PortfolioStorage()

                cik = get_cik(symbol, self._storage)
                if not cik:
                    logger.warning("sec_edgar_cik_not_found", symbol=symbol)
                    continue

                # Get company by CIK (bypasses ticker lookup, works despite IP block)
                company = edgar.Company(cik)

                # Fetch filings in date range
                filings = company.get_filings(
                    form=self.FILING_TYPES, date=f"{start_date}:{end_date}"
                )

                if len(filings) == 0:
                    logger.debug("sec_edgar_no_filings", symbol=symbol)
                    continue

                # Process each filing
                # Work around pyarrow version issue by accessing data directly
                for i, _ in enumerate(filings.data):
                    try:
                        filing_record = self._process_filing(filings, i, symbol)
                        if filing_record:
                            records.append(filing_record)
                    except Exception as filing_error:
                        logger.warning(
                            "sec_edgar_filing_parse_error",
                            symbol=symbol,
                            index=i,
                            error=str(filing_error),
                        )
                        continue

                logger.debug(
                    "sec_edgar_symbol_complete",
                    symbol=symbol,
                    filings_found=len(filings.data),
                )

            except Exception as exc:
                logger.warning(
                    "sec_edgar_fetch_error",
                    symbol=symbol,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                continue

        if not records:
            logger.info("sec_edgar_no_data")
            return None

        logger.info(
            "sec_edgar_fetch_complete",
            total_filings=len(records),
            unique_symbols=len({r["symbol"] for r in records}),
        )

        # Create dataframe with explicit schema to avoid type inference issues during concat
        df = pl.from_dicts(records)

        # Explicitly cast nullable columns to ensure consistent types across sources
        df = df.with_columns(
            [
                pl.col("author").cast(pl.Utf8),
                pl.col("image_url").cast(pl.Utf8),
                pl.col("raw_payload").cast(pl.Utf8),
                pl.col("filing_type").cast(pl.Utf8),
            ]
        )

        return df

    def _process_filing(self, filings: Any, index: int, symbol: str) -> dict[str, Any] | None:
        """Process a single filing into a news record.

        Args:
            filings: Filings object from edgartools
            index: Index of filing to process
            symbol: Stock symbol

        Returns:
            Dictionary with filing data, or None if processing fails
        """
        # Extract fields from pyarrow data (workaround for version incompatibility)
        form = self._get_pyarrow_value(filings.data["form"][index])
        filing_date = self._get_pyarrow_value(filings.data["filing_date"][index])
        accession = self._get_pyarrow_value(filings.data["accession_number"][index])

        if not form or not filing_date:
            return None

        # Generate plain language headline
        headline = self._generate_headline(form, symbol)

        # Build filing URL
        # Format: https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession}&xbrl_type=v
        # Simplified: use accession number format
        filing_url = f"https://www.sec.gov/cgi-bin/viewer?action=view&accession_number={accession}"

        # Determine if material event
        is_material = self._is_material_event(form)

        # Build record with ALL standard news fields (for schema compatibility)
        record = {
            "symbol": symbol,
            "headline": headline,
            "url": filing_url,
            "summary": f"{form} filed on {filing_date}",
            "news_source_name": "SEC EDGAR",  # Standard field name
            "author": None,  # SEC filings don't have authors
            "image_url": None,  # SEC filings don't have images
            "published_at": dt.datetime.combine(filing_date, dt.time.min).replace(tzinfo=dt.UTC),
            "raw_payload": None,  # Will be populated later if needed
            "source": "sec_edgar",  # Source identifier
            # SEC-specific fields
            "vendor": "sec_edgar",
            "filing_type": form,
            "is_material_event": is_material,
        }

        return record

    def _get_pyarrow_value(self, value: Any) -> Any:
        """Extract Python value from pyarrow object.

        Args:
            value: PyArrow value

        Returns:
            Python native value
        """
        if hasattr(value, "as_py"):
            return value.as_py()
        return value

    def _generate_headline(self, form: str, symbol: str) -> str:
        """Generate plain-language headline for filing.

        Args:
            form: Filing type (8-K, 10-Q, etc.)
            symbol: Stock symbol

        Returns:
            Plain language headline
        """
        # Plain language translations (no jargon)
        if form == "8-K":
            return "Company filed material event report"
        if form == "10-Q":
            return "Quarterly financial report filed"
        if form == "10-K":
            return "Annual financial report filed"
        if form == "4":
            return "Insider trading activity reported"
        return f"{form} filed with SEC"

    def _is_material_event(self, form: str) -> bool:
        """Determine if filing represents a material event.

        Args:
            form: Filing type

        Returns:
            True if material event
        """
        # All 8-Ks are material events (by definition)
        if form == "8-K":
            return True

        # Form 4 (insider trades) are material events
        return form == "4"
