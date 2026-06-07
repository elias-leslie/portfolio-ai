"""SEC EDGAR data source adapter.

This module provides access to SEC EDGAR filings as a news source,
including 8-K material events, Form 4 insider trades, and quarterly/annual reports.
"""

from __future__ import annotations

import datetime as dt
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

# Plain language translations for filing headlines
_HEADLINE_MAP: dict[str, str] = {
    "8-K": "Company filed material event report",
    "10-Q": "Quarterly financial report filed",
    "10-K": "Annual financial report filed",
    "4": "Insider trading activity reported",
}

# Filing types that count as material events
_MATERIAL_FORMS: frozenset[str] = frozenset({"8-K", "4"})


def _get_edgar() -> Any:
    """Lazy import an optional EDGAR client and set User-Agent identity."""
    global _edgar, _set_identity_called  # noqa: PLW0603

    if not SEC_USER_AGENT:
        raise RuntimeError("SEC_USER_AGENT must be configured to use SEC EDGAR")

    if _edgar is None:
        try:
            import edgar as edgar_module  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError("SEC EDGAR optional client is not installed") from exc

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
    """SEC EDGAR filings source.

    Provides access to:
    - 8-K: Material events (earnings, M&A, exec changes)
    - Form 4: Insider trades
    - 10-Q: Quarterly reports
    - 10-K: Annual reports

    All filings are free and publicly available. The optional EDGAR client is
    not installed by the base public package; without it this source degrades
    to no data and logs a warning.
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
        # The optional EDGAR client is imported lazily on first use.
        self._storage = storage
        logger.info("sec_edgar_source_initialized")

    def _ensure_storage(self) -> None:
        """Lazily initialize storage to avoid circular dependency."""
        if self._storage is None:
            from ..storage import PortfolioStorage  # noqa: PLC0415

            self._storage = PortfolioStorage()

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
        try:
            edgar = _get_edgar()
        except RuntimeError as exc:
            logger.warning("sec_edgar_unavailable", error=str(exc))
            return None
        records: list[dict[str, Any]] = []

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
            if symbol in (None, "__MARKET__"):
                continue
            records.extend(
                self._fetch_symbol_filings(edgar, symbol, start_date, end_date)
            )

        if not records:
            logger.info("sec_edgar_no_data")
            return None

        logger.info(
            "sec_edgar_fetch_complete",
            total_filings=len(records),
            unique_symbols=len({r["symbol"] for r in records}),
        )

        df = pl.from_dicts(records)
        df = df.with_columns(
            [
                pl.col("author").cast(pl.Utf8),
                pl.col("image_url").cast(pl.Utf8),
                pl.col("raw_payload").cast(pl.Utf8),
                pl.col("filing_type").cast(pl.Utf8),
            ]
        )

        return df

    def _fetch_symbol_filings(
        self,
        edgar: Any,
        symbol: str,
        start_date: dt.date,
        end_date: dt.date,
    ) -> list[dict[str, Any]]:
        """Fetch and process all filings for a single symbol.

        Returns list of filing records (may be empty on error or no data).
        """
        try:
            self._ensure_storage()
            cik = get_cik(symbol, self._storage)
            if not cik:
                logger.warning("sec_edgar_cik_not_found", symbol=symbol)
                return []

            company = edgar.Company(cik)
            filings = company.get_filings(
                form=self.FILING_TYPES, date=f"{start_date}:{end_date}"
            )

            if len(filings) == 0:
                logger.debug("sec_edgar_no_filings", symbol=symbol)
                return []

            records = self._parse_filings(filings, symbol)
            logger.debug(
                "sec_edgar_symbol_complete",
                symbol=symbol,
                filings_found=len(filings.data),
            )
            return records

        except (ValueError, KeyError, TypeError, AttributeError, OSError, RuntimeError) as exc:
            logger.warning(
                "sec_edgar_fetch_error",
                symbol=symbol,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return []

    def _parse_filings(self, filings: Any, symbol: str) -> list[dict[str, Any]]:
        """Parse all filings in a filings collection for a symbol."""
        records: list[dict[str, Any]] = []
        for i, _ in enumerate(filings.data):
            record = self._safe_process_filing(filings, i, symbol)
            if record:
                records.append(record)
        return records

    def _safe_process_filing(
        self, filings: Any, index: int, symbol: str
    ) -> dict[str, Any] | None:
        """Process a single filing, returning None on any parse error."""
        try:
            return self._process_filing(filings, index, symbol)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as filing_error:
            logger.warning(
                "sec_edgar_filing_parse_error",
                symbol=symbol,
                index=index,
                error=str(filing_error),
            )
            return None

    def _process_filing(self, filings: Any, index: int, symbol: str) -> dict[str, Any] | None:
        """Process a single filing into a news record.

        Args:
            filings: Filings object from the optional EDGAR client
            index: Index of filing to process
            symbol: Stock symbol

        Returns:
            Dictionary with filing data, or None if processing fails
        """
        form = self._get_pyarrow_value(filings.data["form"][index])
        filing_date = self._get_pyarrow_value(filings.data["filing_date"][index])
        accession = self._get_pyarrow_value(filings.data["accession_number"][index])

        if not form or not filing_date:
            return None

        headline = self._generate_headline(form, symbol)
        filing_url = (
            f"https://www.sec.gov/cgi-bin/viewer?action=view&accession_number={accession}"
        )

        return {
            "symbol": symbol,
            "headline": headline,
            "url": filing_url,
            "summary": f"{form} filed on {filing_date}",
            "news_source_name": "SEC EDGAR",
            "author": None,
            "image_url": None,
            "published_at": dt.datetime.combine(filing_date, dt.time.min).replace(tzinfo=dt.UTC),
            "raw_payload": None,
            "source": "sec_edgar",
            "vendor": "sec_edgar",
            "filing_type": form,
            "is_material_event": self._is_material_event(form),
        }

    def _get_pyarrow_value(self, value: Any) -> Any:
        """Extract Python value from pyarrow object."""
        if hasattr(value, "as_py"):
            return value.as_py()
        return value

    def _generate_headline(self, form: str, symbol: str) -> str:
        """Generate plain-language headline for filing."""
        return _HEADLINE_MAP.get(form, f"{form} filed with SEC")

    def _is_material_event(self, form: str) -> bool:
        """Determine if filing represents a material event."""
        return form in _MATERIAL_FORMS
