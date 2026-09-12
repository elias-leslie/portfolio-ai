from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.portfolio.lot_evidence import get_lot_evidence


def test_lot_evidence_keeps_missing_basis_unknown_and_excludes_paper():
    manager, ledger, fetcher = Mock(), Mock(), Mock()
    manager.get_accounts.return_value = [
        SimpleNamespace(id="real", name="Brokerage", account_type="Taxable"),
        SimpleNamespace(id="paper", name="Practice", account_type="paper"),
    ]
    manager.get_positions.return_value = [
        SimpleNamespace(
            account_id=account, symbol="AAPL", shares=10, position_type="long", cost_basis=100
        )
        for account in ("real", "paper")
    ]
    ledger.open_lots.return_value = []
    fetcher.fetch_cached_price_data.return_value = {}
    with (
        patch("app.portfolio.lot_evidence.PortfolioManager", return_value=manager),
        patch("app.portfolio.lot_evidence.TransactionLedger", return_value=ledger),
        patch("app.portfolio.lot_evidence.PriceDataFetcher", return_value=fetcher),
    ):
        result = get_lot_evidence(Mock(), "aapl")
    assert len(result.accounts) == 1
    assert result.accounts[0].coverage == "missing" and result.accounts[0].lots == []
    assert result.quote_price is None
    ledger.open_lots.assert_called_once_with("real", "AAPL")
    ledger.consume_lots_fifo.assert_not_called()


def test_partially_sold_lot_basis_uses_remaining_quantity_and_discloses_mismatch():
    manager, ledger, fetcher = Mock(), Mock(), Mock()
    manager.get_accounts.return_value = [
        SimpleNamespace(id="real", name="Brokerage", account_type="Taxable")
    ]
    manager.get_positions.return_value = [
        SimpleNamespace(account_id="real", symbol="AAPL", shares=2, position_type="long")
    ]
    ledger.open_lots.return_value = [
        SimpleNamespace(
            id="lot",
            acquired_date=date(2024, 1, 1),
            original_shares=10,
            remaining_shares=3,
            cost_per_share=100,
            cost_basis_total=1000,
        )
    ]
    fetcher.fetch_cached_price_data.return_value = {
        "AAPL": SimpleNamespace(price=150, error=None, source="broker", quote_time=None)
    }
    with (
        patch("app.portfolio.lot_evidence.PortfolioManager", return_value=manager),
        patch("app.portfolio.lot_evidence.TransactionLedger", return_value=ledger),
        patch("app.portfolio.lot_evidence.PriceDataFetcher", return_value=fetcher),
    ):
        result = get_lot_evidence(Mock(), "AAPL")
    account = result.accounts[0]
    assert account.coverage == "mismatch"
    assert account.lots[0].remaining_basis == 300
    assert account.lots[0].gain_at_quote == 150
    ledger.consume_lots_fifo.assert_not_called()
