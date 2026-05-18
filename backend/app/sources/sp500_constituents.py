"""S&P 500 constituent fetcher.

Primary: Wikipedia "List of S&P 500 companies" — public, no auth, refreshed
on every index rebalance. Fallback: iShares IVV holdings CSV. Last-resort
fallback: a committed seed file with a representative slice.

Notes for callers:
- Wikipedia gives **current** membership only — historical point-in-time
  membership requires preserving past rows via ``removed_at`` in the
  ``research_universe_symbols`` table. Live forward use is unaffected.
- Symbols with dots (e.g. ``BRK.B``) are returned with the dot preserved;
  downstream price systems use a normalized form (``BRK-B``) but the
  universe table is the source of truth.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..logging_config import get_logger

logger = get_logger(__name__)

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
ISHARES_IVV_URL = (
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund"
)
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "sp500_seed.json"


@dataclass(frozen=True, slots=True)
class UniverseMember:
    symbol: str
    sector: str | None
    industry: str | None
    weight: float | None
    source: str


def _normalise_symbol(raw: str) -> str:
    return raw.strip().upper()


def _parse_wikipedia_html(html: str) -> list[UniverseMember]:
    """Extract members from the Wikipedia constituent table.

    The article has a stable table with id ``constituents``. We avoid pulling
    in a full HTML parser dependency by lifting the table rows with a small
    regex; Wikipedia keeps the column order stable: Symbol, Security, GICS
    Sector, GICS Sub-Industry, Headquarters, Date added, CIK, Founded.
    """
    # Locate the constituents table by id; fall back to the first wikitable.
    table_match = re.search(
        r'<table[^>]*id=["\']?constituents["\']?[^>]*>(.*?)</table>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if table_match is None:
        table_match = re.search(
            r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    if table_match is None:
        return []

    members: list[UniverseMember] = []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.DOTALL | re.IGNORECASE)
    for row in rows:
        # Skip header rows — Wikipedia uses <th> for column labels.
        if re.search(r"<th[^>]*>", row, flags=re.IGNORECASE):
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.DOTALL | re.IGNORECASE)
        if len(cells) < 4:
            continue
        symbol = _strip_html(cells[0])
        if not symbol or not symbol[0].isalpha():
            continue
        sector = _strip_html(cells[2]) or None
        industry = _strip_html(cells[3]) or None
        members.append(
            UniverseMember(
                symbol=_normalise_symbol(symbol),
                sector=sector,
                industry=industry,
                weight=None,
                source="wikipedia",
            )
        )
    return members


def _strip_html(fragment: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", fragment)
    cleaned = cleaned.replace("&amp;", "&").replace("&nbsp;", " ")
    return cleaned.strip()


def _parse_ivv_csv(text: str) -> list[UniverseMember]:
    """Parse iShares IVV holdings CSV.

    iShares prefixes the CSV with metadata lines and a blank row before the
    real header. We seek the header row containing ``Ticker``.
    """
    reader = csv.reader(io.StringIO(text))
    header_idx: int | None = None
    rows: list[list[str]] = []
    for i, row in enumerate(reader):
        if header_idx is None:
            if any("Ticker" in cell for cell in row):
                header_idx = i
                header = row
                continue
        else:
            rows.append(row)
    if header_idx is None:
        return []
    cols = {name.strip(): idx for idx, name in enumerate(header)}
    ticker_col = cols.get("Ticker")
    sector_col = cols.get("Sector")
    weight_col = cols.get("Weight (%)") or cols.get("Weight")
    if ticker_col is None:
        return []
    members: list[UniverseMember] = []
    for row in rows:
        if len(row) <= ticker_col:
            continue
        symbol_raw = row[ticker_col].strip()
        if not symbol_raw or not symbol_raw[0].isalpha():
            continue
        weight = None
        if weight_col is not None and len(row) > weight_col:
            try:
                weight = float(row[weight_col].strip().replace("%", "") or 0) or None
            except ValueError:
                weight = None
        sector = row[sector_col].strip() if sector_col is not None and len(row) > sector_col else None
        members.append(
            UniverseMember(
                symbol=_normalise_symbol(symbol_raw),
                sector=sector or None,
                industry=None,
                weight=weight,
                source="ishares_ivv",
            )
        )
    return members


def _load_seed() -> list[UniverseMember]:
    if not SEED_PATH.exists():
        return []
    raw = json.loads(SEED_PATH.read_text())
    members: list[UniverseMember] = []
    for entry in raw.get("members", []):
        members.append(
            UniverseMember(
                symbol=_normalise_symbol(entry["symbol"]),
                sector=entry.get("sector"),
                industry=entry.get("industry"),
                weight=None,
                source="seed",
            )
        )
    return members


def fetch_sp500_constituents(timeout: float = 15.0) -> list[UniverseMember]:
    """Return the current S&P 500 membership.

    Tries Wikipedia, then iShares IVV holdings CSV, then a committed seed
    file. Returns whatever the first successful source yields; never raises.
    """
    headers = {"User-Agent": "portfolio-ai/research-universe (no contact)"}
    try:
        resp = httpx.get(WIKIPEDIA_URL, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        members = _parse_wikipedia_html(resp.text)
        if len(members) >= 400:
            logger.info("sp500_constituents_fetched", source="wikipedia", count=len(members))
            return members
        logger.warning("sp500_wikipedia_short", count=len(members))
    except Exception as exc:
        logger.warning("sp500_wikipedia_failed", error=str(exc))

    try:
        resp = httpx.get(ISHARES_IVV_URL, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        members = _parse_ivv_csv(resp.text)
        if len(members) >= 400:
            logger.info("sp500_constituents_fetched", source="ishares_ivv", count=len(members))
            return members
        logger.warning("sp500_ivv_short", count=len(members))
    except Exception as exc:
        logger.warning("sp500_ivv_failed", error=str(exc))

    members = _load_seed()
    logger.warning("sp500_using_seed_fallback", count=len(members))
    return members


def to_dict_rows(members: list[UniverseMember]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": m.symbol,
            "source": m.source,
            "sector": m.sector,
            "industry": m.industry,
            "weight": m.weight,
        }
        for m in members
    ]
