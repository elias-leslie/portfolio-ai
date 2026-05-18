"""Unit tests for the S&P 500 constituent fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.sources.sp500_constituents import (
    UniverseMember,
    _load_seed,
    _parse_ivv_csv,
    _parse_wikipedia_html,
    fetch_sp500_constituents,
    to_dict_rows,
)


def test_seed_file_has_minimum_members() -> None:
    """Seed file should always parse and yield at least 25 representative rows."""
    seed = _load_seed()
    assert len(seed) >= 25
    assert all(isinstance(m, UniverseMember) for m in seed)
    assert all(m.source == "seed" for m in seed)
    # Seed must surface mega-caps so a graceful degradation still produces a
    # plausible universe.
    symbols = {m.symbol for m in seed}
    for required in ("AAPL", "MSFT", "NVDA", "GOOGL"):
        assert required in symbols, f"missing seed mega-cap {required}"


def test_parse_wikipedia_html_extracts_symbol_sector_industry() -> None:
    html = """
    <table id="constituents">
        <tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th></tr>
        <tr><td><a>AAPL</a></td><td>Apple Inc.</td><td>Information Technology</td><td>Technology Hardware</td></tr>
        <tr><td>NVDA</td><td>NVIDIA</td><td>Information Technology</td><td>Semiconductors</td></tr>
    </table>
    """
    members = _parse_wikipedia_html(html)
    assert len(members) == 2
    aapl = next(m for m in members if m.symbol == "AAPL")
    assert aapl.sector == "Information Technology"
    assert aapl.industry == "Technology Hardware"
    assert aapl.source == "wikipedia"


def test_parse_ivv_csv_skips_metadata_and_extracts_rows() -> None:
    csv_text = """\
"Holdings as of","2026-05-15"
"Fund Name","iShares Core S&P 500 ETF"

"Ticker","Name","Sector","Asset Class","Market Value","Weight (%)","Notional Value","Shares","Price","Location"
"AAPL","Apple Inc.","Information Technology","Equity","$100,000,000","6.50","$100,000,000","1,000","$200","United States"
"NVDA","NVIDIA Corp","Information Technology","Equity","$90,000,000","5.80","$90,000,000","500","$1000","United States"
"""
    members = _parse_ivv_csv(csv_text)
    assert len(members) == 2
    aapl = next(m for m in members if m.symbol == "AAPL")
    assert aapl.weight == 6.50
    assert aapl.source == "ishares_ivv"


def test_fetch_falls_back_to_seed_when_remote_fails() -> None:
    with patch("app.sources.sp500_constituents.httpx.get") as mock_get:
        mock_get.side_effect = Exception("network down")
        members = fetch_sp500_constituents(timeout=0.1)
    assert len(members) >= 25
    assert all(m.source == "seed" for m in members)


def test_fetch_returns_wikipedia_when_table_is_full() -> None:
    """A successful Wikipedia fetch >= 400 rows is preferred over the seed."""
    rows = "".join(
        f"<tr><td>SYM{i:03d}</td><td>Co{i}</td><td>Sector</td><td>Industry</td></tr>"
        for i in range(450)
    )
    html = f"<table id='constituents'>{rows}</table>"
    mock_response = MagicMock(text=html)
    mock_response.raise_for_status.return_value = None
    with patch("app.sources.sp500_constituents.httpx.get", return_value=mock_response):
        members = fetch_sp500_constituents()
    assert len(members) == 450
    assert all(m.source == "wikipedia" for m in members)


def test_to_dict_rows_round_trip() -> None:
    members = [
        UniverseMember(symbol="AAPL", sector="IT", industry="HW", weight=6.5, source="seed"),
    ]
    rows = to_dict_rows(members)
    assert rows == [
        {
            "symbol": "AAPL",
            "source": "seed",
            "sector": "IT",
            "industry": "HW",
            "weight": 6.5,
        }
    ]
