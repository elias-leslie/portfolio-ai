"""Unit tests for household-to-portfolio position snapshot sync."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from app.models.household_finance import HouseholdDocument
from app.services.household_portfolio_position_sync_service import (
    HouseholdPortfolioPositionSyncService,
)


class _Result:
    def __init__(
        self,
        *,
        one: tuple[Any, ...] | None = None,
        many: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._one = one
        self._many = many or []

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._one

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._many


class _Connection:
    def __init__(self) -> None:
        self.deleted_ids: list[str] = []
        self.inserted_symbols: list[str] = []
        self.updated_positions: list[tuple[float, float, str]] = []
        self.updated_cash: float | None = None
        self.committed = False

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: list[Any] | None = None) -> _Result:
        params = params or []
        if sql.strip().startswith("DELETE FROM portfolio_positions"):
            self.deleted_ids.extend([str(value) for value in params[0]])
        elif sql.strip().startswith("INSERT INTO portfolio_positions"):
            self.inserted_symbols.append(str(params[2]))
        elif sql.strip().startswith("UPDATE portfolio_positions"):
            self.updated_positions.append((float(params[0]), float(params[1]), str(params[3])))
        elif sql.strip().startswith("UPDATE portfolio_accounts"):
            self.updated_cash = float(params[0])
        elif "FROM portfolio_accounts" in sql:
            return _Result(one=("portfolio-ira", 965.11))
        elif "FROM portfolio_positions" in sql:
            return _Result(
                many=[
                    ("pos-amzn", "AMZN", 2.0, 201.17),
                    ("pos-vti", "VTI", 994.409, 255.81),
                    ("pos-vug", "VUG", 22.0, 480.08),
                ]
            )
        return _Result()

    def commit(self) -> None:
        self.committed = True


def test_position_snapshot_sync_replaces_stale_account_positions_and_cash() -> None:
    connection = _Connection()
    service = SimpleNamespace(
        storage=SimpleNamespace(connection=Mock(return_value=connection)),
        portfolio_mgr=SimpleNamespace(sync_portfolio_to_watchlist=Mock()),
    )
    document = HouseholdDocument(
        id="doc-positions",
        filename="Portfolio_Positions_May-02-2026.csv",
        source_type="retirement",
        document_type="retirement_statement",
        status="parsed",
        account_label="Traditional IRA",
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={},
    )

    summary = HouseholdPortfolioPositionSyncService().sync_from_reviewed_accounts(
        service,
        document=document,
        reviewed={
            "structured_data": {
                "financial_accounts": [
                    {
                        "household_account_id": "household-ira",
                        "cash_balance": "1976.42",
                        "position_snapshot": True,
                        "holdings": [
                            {"symbol": "SPAXX", "quantity": None, "market_value": "1976.42", "cash_like": True},
                            {"symbol": "AMZN", "quantity": "2", "average_cost_basis": "201.17"},
                            {"symbol": "VTI", "quantity": "994.409", "average_cost_basis": "255.81"},
                            {"symbol": "VGT", "quantity": "124", "average_cost_basis": "104.30"},
                        ],
                    }
                ]
            }
        },
    )

    assert connection.updated_cash == 1976.42
    assert connection.deleted_ids == ["pos-vug"]
    assert connection.inserted_symbols == ["VGT"]
    assert connection.updated_positions == []
    assert connection.committed is True
    assert summary["positions_inserted"] == 1
    assert summary["positions_deleted"] == 1
    assert summary["positions_unchanged"] == 2
    service.portfolio_mgr.sync_portfolio_to_watchlist.assert_called_once_with(["AMZN", "VGT", "VTI"])
