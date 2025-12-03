"""SEC CIK (Central Index Key) fetcher with multiple fallback sources.

This module downloads and caches ticker→CIK mappings from the SEC and alternative sources.
CIK numbers are permanent identifiers (never recycled), so once cached, they remain valid forever.

Usage:
    # Fetch and cache all CIKs
    python -m app.sources.sec_cik_fetcher fetch

    # Load from database
    from app.sources.sec_cik_fetcher import get_cik
    cik = get_cik("NVDA")  # Returns "0001045810"
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

import requests

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


class CIKSource(TypedDict):
    """Type definition for CIK data source configuration."""

    name: str
    url: str
    headers: dict[str, str]
    priority: int


# Multiple sources for CIK data (fallback chain)
CIK_SOURCES: list[CIKSource] = [
    {
        "name": "SEC Official",
        "url": "https://www.sec.gov/files/company_tickers.json",
        "headers": {
            "User-Agent": "Portfolio AI https://github.com/kasadis/portfolio-ai contact@example.com"
        },
        "priority": 1,
    },
    {
        "name": "SEC Exchange Data",
        "url": "https://www.sec.gov/files/company_tickers_exchange.json",
        "headers": {
            "User-Agent": "Portfolio AI https://github.com/kasadis/portfolio-ai contact@example.com"
        },
        "priority": 2,
    },
    {
        "name": "GitHub Mirror (team-headstart)",
        "url": "https://raw.githubusercontent.com/team-headstart/Financial-Analysis-and-Automation-with-LLMs/main/company_tickers.json",
        "headers": {},
        "priority": 3,
    },
    {
        "name": "GitHub Mirror (pChitral)",
        "url": "https://raw.githubusercontent.com/pChitral/ETL-SEC-EDGAR-10-k-Filings/main/company_tickers.json",
        "headers": {},
        "priority": 4,
    },
]


def fetch_cik_mapping(timeout: int = 30) -> dict[str, str]:
    """Fetch ticker→CIK mapping from SEC or fallback sources.

    Tries multiple sources in priority order until one succeeds.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Dictionary mapping ticker symbols to CIK numbers (zero-padded to 10 digits)

    Raises:
        Exception: If all sources fail
    """
    logger.info("cik_fetch_start", num_sources=len(CIK_SOURCES))

    errors = []

    for source in sorted(CIK_SOURCES, key=lambda s: s["priority"]):
        logger.info("cik_fetch_attempt", source=source["name"], url=source["url"])

        try:
            response = requests.get(
                source["url"],
                headers=source["headers"],
                timeout=timeout,
            )

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                logger.warning(
                    "cik_fetch_failed",
                    source=source["name"],
                    status=response.status_code,
                )
                errors.append(f"{source['name']}: {error_msg}")
                continue

            # Parse JSON
            data = response.json()

            # Convert to ticker→CIK mapping
            mapping = _parse_cik_data(data, source["name"])

            if not mapping:
                error_msg = "Empty mapping after parsing"
                logger.warning("cik_fetch_empty", source=source["name"])
                errors.append(f"{source['name']}: {error_msg}")
                continue

            logger.info(
                "cik_fetch_success",
                source=source["name"],
                total_tickers=len(mapping),
            )

            return mapping

        except Exception as exc:
            logger.warning(
                "cik_fetch_error",
                source=source["name"],
                error=str(exc),
                error_type=type(exc).__name__,
            )
            errors.append(f"{source['name']}: {exc}")
            continue

    # All sources failed
    error_summary = "; ".join(errors)
    logger.error("cik_fetch_all_failed", errors=error_summary)
    raise Exception(f"All CIK sources failed: {error_summary}")


def _parse_cik_data(data: dict[str, Any] | list[Any], source_name: str) -> dict[str, str]:
    """Parse CIK data from various formats.

    SEC data can come in different formats:
    - Dict with numeric keys: {"0": {"cik_str": 123, "ticker": "AAPL", ...}, ...}
    - Dict with "data" key: {"data": [...]}
    - List of objects: [{"cik_str": 123, "ticker": "AAPL", ...}, ...]

    Args:
        data: JSON data from source
        source_name: Name of source (for logging)

    Returns:
        Dictionary mapping ticker→CIK (zero-padded to 10 digits)
    """
    mapping: dict[str, str] = {}

    try:
        # Format 1: Dict with numeric string keys
        if isinstance(data, dict) and all(k.isdigit() for k in list(data.keys())[:5]):
            for entry in data.values():
                ticker = entry.get("ticker", "").strip().upper()
                cik = entry.get("cik_str") or entry.get("cik")
                if ticker and cik:
                    mapping[ticker] = str(cik).zfill(10)

        # Format 2: Dict with "data" key
        elif isinstance(data, dict) and "data" in data:
            for entry in data["data"]:
                if isinstance(entry, dict):
                    ticker = entry.get("ticker", "").strip().upper()
                    cik = entry.get("cik_str") or entry.get("cik")
                    if ticker and cik:
                        mapping[ticker] = str(cik).zfill(10)
                elif isinstance(entry, list) and len(entry) >= 3:
                    # Some formats use arrays: [ticker, cik, name]
                    ticker = str(entry[0]).strip().upper()
                    cik = entry[1]
                    if ticker and cik:
                        mapping[ticker] = str(cik).zfill(10)

        # Format 3: List of dicts
        elif isinstance(data, list):
            for entry in data:
                ticker = entry.get("ticker", "").strip().upper()
                cik = entry.get("cik_str") or entry.get("cik")
                if ticker and cik:
                    mapping[ticker] = str(cik).zfill(10)

        # Format 4: Direct ticker→CIK dict
        elif isinstance(data, dict):
            for ticker, value in data.items():
                if isinstance(value, (int, str)):
                    mapping[ticker.strip().upper()] = str(value).zfill(10)
                elif isinstance(value, dict):
                    cik = value.get("cik_str") or value.get("cik")
                    if cik:
                        mapping[ticker.strip().upper()] = str(cik).zfill(10)

    except Exception as exc:
        logger.error(
            "cik_parse_error",
            source=source_name,
            error=str(exc),
            data_type=type(data).__name__,
        )
        raise

    logger.info(
        "cik_parse_complete",
        source=source_name,
        total_parsed=len(mapping),
    )

    return mapping


def save_to_database(storage: PortfolioStorage, mapping: dict[str, str]) -> None:
    """Save CIK mapping to database.

    Args:
        storage: PortfolioStorage instance
        mapping: Ticker→CIK mapping dictionary
    """
    logger.info("cik_db_save_start", total_entries=len(mapping))

    with storage.connection() as conn:
        # Insert or update CIK mappings in batches
        batch_size = 1000
        items = list(mapping.items())

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            for ticker, cik in batch:
                conn.execute(
                    """
                    INSERT INTO sec_cik_cache (ticker, cik, last_updated)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE SET
                        cik = EXCLUDED.cik,
                        last_updated = EXCLUDED.last_updated
                    """,
                    (ticker, cik, datetime.now(UTC)),
                )

            logger.debug(
                "cik_db_batch_saved",
                batch_num=i // batch_size + 1,
                batch_size=len(batch),
            )

        # Commit all changes (context manager does NOT auto-commit)
        conn.commit()

    logger.info("cik_db_save_complete", total_saved=len(mapping))


def load_from_database(storage: PortfolioStorage) -> dict[str, str]:
    """Load CIK mapping from database.

    Args:
        storage: PortfolioStorage instance

    Returns:
        Dictionary mapping ticker→CIK
    """
    logger.info("cik_db_load_start")

    with storage.connection() as conn:
        rows = conn.execute("SELECT symbol, cik FROM sec_cik_cache").fetchall()

    # Cast row values to strings (they are returned as Union types from database)
    mapping = {str(row[0]): str(row[1]) for row in rows}

    logger.info("cik_db_load_complete", total_loaded=len(mapping))

    return mapping


def get_cik(ticker: str, storage: PortfolioStorage | None = None) -> str | None:
    """Get CIK for a ticker symbol.

    Args:
        ticker: Stock ticker symbol
        storage: Optional PortfolioStorage instance (loads from DB if provided)

    Returns:
        CIK number (10-digit string) or None if not found
    """
    ticker = ticker.strip().upper()

    if storage:
        try:
            with storage.connection() as conn:
                row = conn.execute(
                    "SELECT cik FROM sec_cik_cache WHERE symbol = ?", (ticker,)
                ).fetchone()
                # Cast to string (database returns Union type)
                return str(row[0]) if row else None
        except Exception as exc:
            logger.warning("cik_lookup_error", ticker=ticker, error=str(exc))
            return None

    return None


def fetch_and_save(storage: PortfolioStorage) -> dict[str, str]:
    """Fetch CIK mapping and save to database.

    This is the main entry point for updating the CIK cache.

    Args:
        storage: PortfolioStorage instance

    Returns:
        Ticker→CIK mapping dictionary
    """
    logger.info("cik_fetch_and_save_start")

    # Fetch from sources
    mapping = fetch_cik_mapping()

    # Save to database
    save_to_database(storage, mapping)

    logger.info(
        "cik_fetch_and_save_complete",
        total_tickers=len(mapping),
    )

    return mapping


def main() -> None:
    """Command-line interface for CIK fetcher.

    Usage:
        python -m app.sources.sec_cik_fetcher fetch
        python -m app.sources.sec_cik_fetcher stats
    """
    # Import at runtime to avoid circular dependency
    from ..storage import PortfolioStorage  # noqa: PLC0415

    if len(sys.argv) < 2:
        print("Usage: python -m app.sources.sec_cik_fetcher <command>")
        print("Commands:")
        print("  fetch   - Fetch CIK mapping and save to database")
        print("  stats   - Show cache statistics")
        print("  test    - Test with sample tickers")
        sys.exit(1)

    command = sys.argv[1]
    storage = PortfolioStorage()

    if command == "fetch":
        print("Fetching CIK mapping from SEC sources...")
        mapping = fetch_and_save(storage)
        print(f"✅ Successfully cached {len(mapping):,} ticker→CIK mappings")

        # Show sample
        print("\nSample mappings:")
        for ticker, cik in list(mapping.items())[:10]:
            print(f"  {ticker:8} → {cik}")

    elif command == "stats":
        print("Loading CIK cache statistics...")
        mapping = load_from_database(storage)
        print(f"📊 Total tickers in cache: {len(mapping):,}")

        # Show last update time
        with storage.connection() as conn:
            row = conn.execute("SELECT MAX(last_updated) FROM sec_cik_cache").fetchone()
            if row and row[0]:
                print(f"🕐 Last updated: {row[0]}")

    elif command == "test":
        print("Testing CIK lookups...")
        test_tickers = ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META"]

        for ticker in test_tickers:
            result = get_cik(ticker, storage)
            status = "✅" if result else "❌"
            print(f"  {status} {ticker:8} → {result or 'NOT FOUND'}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
