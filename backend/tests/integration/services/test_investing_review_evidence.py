"""Persistence and source identity checks in the isolated PostgreSQL database."""

import uuid

from app.models.symbol_workflow import SymbolWorkflow
from app.services.snaptrade_service import SnapTradeService
from app.services.symbol_workflow_service import SymbolWorkflowService
from app.storage import get_storage


def test_duplicate_orders_require_same_canonical_account_broker_id_and_fill():
    canonical = str(uuid.uuid4())
    with get_storage().connection() as conn:
        conn.execute(
            "INSERT INTO household_accounts (id,asset_group,account_type,source_type) VALUES (%s,'retirement','roth_ira','snaptrade')",
            [canonical],
        )
        conn.execute(
            "INSERT INTO snaptrade_users (id,user_id,user_secret_ciphertext) VALUES (%s,'test-user','unused-test-value')",
            [str(uuid.uuid4())],
        )
        for account in ("first-link", "second-link", "unmapped-account"):
            conn.execute(
                "INSERT INTO snaptrade_accounts (id,user_id,account_id,household_account_id,name,portfolio_account_type) VALUES (%s,'test-user',%s,%s,'Test account','Roth')",
                [str(uuid.uuid4()), account, canonical if account != "unmapped-account" else None],
            )
            conn.execute(
                "INSERT INTO snaptrade_orders (id,account_id,brokerage_order_id,status,action,raw_symbol,filled_quantity,execution_price,time_executed,currency) VALUES (%s,%s,'same-order','EXECUTED','BUY','SPAXX',20,1,'2026-09-01T12:00:00Z','USD')",
                [str(uuid.uuid4()), account],
            )
        # Same canonical account and amount with a different order ID is a separate trade.
        conn.execute(
            "INSERT INTO snaptrade_orders (id,account_id,brokerage_order_id,status,action,raw_symbol,filled_quantity,execution_price,time_executed,currency) VALUES (%s,'first-link','different-order','EXECUTED','BUY','SPAXX',20,1,'2026-09-01T12:00:00Z','USD')",
            [str(uuid.uuid4())],
        )
        conn.commit()
    service = SnapTradeService()
    orders = service.get_orders(limit=200)["orders"]
    assert isinstance(orders, list)
    assert len(orders) == 3
    counts = []
    for order in orders:
        assert isinstance(order, dict)
        copies = order["source_copy_count"]
        assert isinstance(copies, int)
        counts.append(copies)
    assert sorted(counts) == [1, 1, 2]
    assert len(service.get_orders(account_id="first-link")["orders"]) == 2
    assert len(service.get_orders(limit=1)["orders"]) == 1
    with get_storage().connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM snaptrade_orders").fetchone()
        assert count and count[0] == 4


def test_pass_persists_rationale_and_server_snapshot_without_invalidating_thesis(monkeypatch):
    with get_storage().connection() as conn:
        conn.execute(
            "INSERT INTO symbols (symbol,company_name) VALUES ('TEST','Test Company') ON CONFLICT DO NOTHING"
        )
        conn.commit()
    service = SymbolWorkflowService()
    monkeypatch.setattr(service._position_builder, "build", lambda _symbol: None)
    monkeypatch.setattr(service.thesis_service, "get_thesis", lambda _symbol: None)
    monkeypatch.setattr(
        service,
        "_capture_evidence",
        lambda symbol: {
            "version": 1,
            "symbol": symbol,
            "portfolio": {"held": False},
            "decision": {
                "source_kind": "live_signal_model",
                "reasoning": ["Missing revenue evidence."],
            },
            "quote": {"price": 12},
        },
    )
    result = SymbolWorkflow.model_validate(
        service.record_outcome("TEST", "pass", "Wait for audited earnings before entry.")
    )
    assert result.stage == "passed"
    assert result.available_actions == ["watch", "pass"]
    assert result.latest_outcome and result.latest_outcome.evidence_snapshot
    quote = result.latest_outcome.evidence_snapshot["quote"]
    assert isinstance(quote, dict) and quote["price"] == 12
    assert result.history[0].note == "Wait for audited earnings before entry."
    with get_storage().connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM symbol_workflow_events WHERE symbol='TEST'"
        ).fetchone()
        assert count and count[0] == 1
