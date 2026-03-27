"""SEC CIK (Central Index Key) fetcher with multiple fallback sources.

This module downloads and caches symbol→CIK mappings from the SEC and alternative sources.
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
from typing import TYPE_CHECKING, TypedDict

import requests

from ..constants import DEFAULT_HTTP_TIMEOUT, SEC_USER_AGENT
from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

CIKData = dict[str, object] | list[object]


class CIKSource(TypedDict):
    """Type definition for CIK data source configuration."""

    name: str
    url: str
    headers: dict[str, str]
    priority: int


CIK_SOURCES: list[CIKSource] = [
    {"name": "SEC Official", "url": "https://www.sec.gov/files/company_symbols.json", "headers": {"User-Agent": SEC_USER_AGENT}, "priority": 1},
    {"name": "SEC Exchange Data", "url": "https://www.sec.gov/files/company_symbols_exchange.json", "headers": {"User-Agent": SEC_USER_AGENT}, "priority": 2},
    {"name": "GitHub Mirror (team-headstart)", "url": "https://raw.githubusercontent.com/team-headstart/Financial-Analysis-and-Automation-with-LLMs/main/company_symbols.json", "headers": {}, "priority": 3},
    {"name": "GitHub Mirror (pChitral)", "url": "https://raw.githubusercontent.com/pChitral/ETL-SEC-EDGAR-10-k-Filings/main/company_symbols.json", "headers": {}, "priority": 4},
]


def _normalize_cik(raw: object) -> str:
    return str(raw).zfill(10)


def _normalize_symbol(s: str) -> str:
    return s.strip().upper()


def _extract_entry(entry: dict[str, object], mapping: dict[str, str]) -> None:
    """Extract symbol→CIK from a dict entry and add to mapping."""
    symbol = _normalize_symbol(str(entry.get("symbol", "")))
    cik = entry.get("cik_str") or entry.get("cik")
    if symbol and cik:
        mapping[symbol] = _normalize_cik(cik)


def _parse_data_key_entry(entry: object, mapping: dict[str, str]) -> None:
    """Parse one entry from a data["data"] list (dict or array format)."""
    if isinstance(entry, dict):
        _extract_entry(entry, mapping)
        return
    if isinstance(entry, list) and len(entry) >= 3:
        symbol = _normalize_symbol(str(entry[0]))
        if symbol and entry[1]:
            mapping[symbol] = _normalize_cik(entry[1])


def _parse_direct_dict_entry(symbol: str, value: object, mapping: dict[str, str]) -> None:
    """Parse one entry from a direct symbol→value dict."""
    key = _normalize_symbol(symbol)
    if isinstance(value, (int, str)):
        mapping[key] = _normalize_cik(value)
        return
    if isinstance(value, dict):
        cik = value.get("cik_str") or value.get("cik")
        if cik:
            mapping[key] = _normalize_cik(cik)


def _dispatch_parse(data: CIKData, mapping: dict[str, str]) -> None:
    """Dispatch to the correct parser based on data shape."""
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                _extract_entry(entry, mapping)
    elif not isinstance(data, dict):
        pass
    elif all(k.isdigit() for k in list(data.keys())[:5]):
        for entry in data.values():
            if isinstance(entry, dict):
                _extract_entry(entry, mapping)
    elif "data" in data:
        entries = data.get("data", [])
        if isinstance(entries, list):
            for entry in entries:
                _parse_data_key_entry(entry, mapping)
    else:
        for symbol, value in data.items():
            _parse_direct_dict_entry(symbol, value, mapping)


def _parse_cik_data(data: CIKData, source_name: str) -> dict[str, str]:
    """Parse CIK data from various formats into a uniform symbol→CIK dict."""
    mapping: dict[str, str] = {}
    try:
        _dispatch_parse(data, mapping)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.error("cik_parse_error", source=source_name, error=str(exc), data_type=type(data).__name__, exc_info=True)
        raise
    logger.info("cik_parse_complete", source=source_name, total_parsed=len(mapping))
    return mapping


def _try_source(source: CIKSource, timeout: float) -> dict[str, str] | str:
    """Attempt to fetch CIK mapping from one source; returns mapping or error string."""
    try:
        response = requests.get(source["url"], headers=source["headers"], timeout=timeout)
        if response.status_code != 200:
            logger.warning("cik_fetch_failed", source=source["name"], status=response.status_code)
            return f"{source['name']}: HTTP {response.status_code}"
        mapping = _parse_cik_data(response.json(), source["name"])
        if not mapping:
            logger.warning("cik_fetch_empty", source=source["name"])
            return f"{source['name']}: Empty mapping after parsing"
        logger.info("cik_fetch_success", source=source["name"], total_symbols=len(mapping))
        return mapping
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("cik_fetch_error", source=source["name"], error=str(exc), error_type=type(exc).__name__)
        return f"{source['name']}: {exc}"


def fetch_cik_mapping(timeout: float = DEFAULT_HTTP_TIMEOUT) -> dict[str, str]:
    """Fetch symbol→CIK mapping from SEC or fallback sources, trying each in priority order.

    Returns:
        Dictionary mapping symbols to CIK numbers (zero-padded to 10 digits)

    Raises:
        RuntimeError: If all sources fail
    """
    logger.info("cik_fetch_start", num_sources=len(CIK_SOURCES))
    errors: list[str] = []
    for source in sorted(CIK_SOURCES, key=lambda s: s["priority"]):
        logger.info("cik_fetch_attempt", source=source["name"], url=source["url"])
        result = _try_source(source, timeout)
        if isinstance(result, dict):
            return result
        errors.append(result)
    error_summary = "; ".join(errors)
    logger.error("cik_fetch_all_failed", errors=error_summary)
    raise RuntimeError(f"All CIK sources failed: {error_summary}")


_UPSERT_SQL = (
    "INSERT INTO sec_cik_cache (symbol, cik, last_updated) VALUES (%s, %s, %s) "
    "ON CONFLICT (symbol) DO UPDATE SET cik = EXCLUDED.cik, last_updated = EXCLUDED.last_updated"
)


def _write_batch(conn: object, batch: list[tuple[str, str]], batch_num: int) -> None:
    """Execute upsert for each row in a batch and log completion."""
    ts = datetime.now(UTC)
    for symbol, cik in batch:
        conn.execute(_UPSERT_SQL, (symbol, cik, ts))  # type: ignore[union-attr]
    logger.debug("cik_db_batch_saved", batch_num=batch_num, batch_size=len(batch))


def save_to_database(storage: PortfolioStorage, mapping: dict[str, str]) -> None:
    """Save CIK mapping to database in batches of 1000."""
    logger.info("cik_db_save_start", total_entries=len(mapping))
    items = list(mapping.items())
    with storage.connection() as conn:
        for batch_num, i in enumerate(range(0, len(items), 1000), start=1):
            _write_batch(conn, items[i : i + 1000], batch_num)
        conn.commit()
    logger.info("cik_db_save_complete", total_saved=len(mapping))


def load_from_database(storage: PortfolioStorage) -> dict[str, str]:
    """Load CIK mapping from database."""
    logger.info("cik_db_load_start")
    with storage.connection() as conn:
        rows = conn.execute("SELECT symbol, cik FROM sec_cik_cache").fetchall()
    mapping = {str(row[0]): str(row[1]) for row in rows}
    logger.info("cik_db_load_complete", total_loaded=len(mapping))
    return mapping


def _lookup_cik_in_db(storage: PortfolioStorage, symbol: str) -> str | None:
    """Query a single symbol's CIK from the database, returning None on any error."""
    try:
        with storage.connection() as conn:
            row = conn.execute("SELECT cik FROM sec_cik_cache WHERE symbol = ?", (symbol,)).fetchone()
            return str(row[0]) if row else None
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("cik_lookup_error", symbol=symbol, error=str(exc))
        return None


def get_cik(symbol: str, storage: PortfolioStorage | None = None) -> str | None:
    """Get CIK for a symbol.

    Args:
        symbol: Stock symbol (case-insensitive)
        storage: Optional PortfolioStorage instance; returns None if not provided

    Returns:
        CIK number (10-digit string) or None if not found
    """
    if not storage:
        return None
    return _lookup_cik_in_db(storage, _normalize_symbol(symbol))


def fetch_and_save(storage: PortfolioStorage) -> dict[str, str]:
    """Fetch CIK mapping from SEC and save to database. Main entry point for cache updates."""
    logger.info("cik_fetch_and_save_start")
    mapping = fetch_cik_mapping()
    save_to_database(storage, mapping)
    logger.info("cik_fetch_and_save_complete", total_symbols=len(mapping))
    return mapping


def _cmd_fetch(storage: PortfolioStorage) -> None:
    print("Fetching CIK mapping from SEC sources...")
    mapping = fetch_and_save(storage)
    print(f"Successfully cached {len(mapping):,} symbol→CIK mappings\n\nSample mappings:")
    for symbol, cik in list(mapping.items())[:10]:
        print(f"  {symbol:8} → {cik}")


def _cmd_stats(storage: PortfolioStorage) -> None:
    mapping = load_from_database(storage)
    print(f"Total symbols in cache: {len(mapping):,}")
    with storage.connection() as conn:
        row = conn.execute("SELECT MAX(last_updated) FROM sec_cik_cache").fetchone()
    if row and row[0]:
        print(f"Last updated: {row[0]}")


def _cmd_test(storage: PortfolioStorage) -> None:
    print("Testing CIK lookups...")
    for symbol in ["NVDA", "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META"]:
        result = get_cik(symbol, storage)
        print(f"  {'OK' if result else 'MISSING'} {symbol:8} → {result or 'NOT FOUND'}")


def main() -> None:
    """CLI for CIK fetcher: fetch | stats | test."""
    from ..storage import PortfolioStorage  # noqa: PLC0415

    if len(sys.argv) < 2:
        print("Usage: python -m app.sources.sec_cik_fetcher <fetch|stats|test>")
        sys.exit(1)
    commands = {"fetch": _cmd_fetch, "stats": _cmd_stats, "test": _cmd_test}
    command = sys.argv[1]
    if command not in commands:
        print(f"Unknown command: {command}")
        sys.exit(1)
    commands[command](PortfolioStorage())


if __name__ == "__main__":
    main()
