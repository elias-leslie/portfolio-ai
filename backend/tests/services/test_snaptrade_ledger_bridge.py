from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.services._snaptrade_ledger_bridge import bridge_cash_activities

# Mirrors the INSERT INTO household_transactions column order in the bridge.
_INSERT_COLUMNS = [
    "id",
    "document_id",
    "household_account_id",
    "merchant_id",
    "row_hash",
    "transaction_date",
    "posted_date",
    "description",
    "raw_merchant",
    "account_label",
    "amount",
    "currency",
    "flow_type",
    "category",
    "essentiality",
    "metadata",
    "external_transaction_id",
    "original_category",
    "categorization_source",
    "categorization_version",
    "category_updated_at",
    "category_updated_by",
    "transaction_rule_id",
    "created_at",
    "updated_at",
]

_HOUSEHOLD_ACCOUNT = "hh-cash-1"
_DAY = datetime(2026, 5, 14, 4, 0, tzinfo=UTC)


def _activity(
    *,
    vendor_account: str,
    activity_id: str,
    activity_type: str = "CONTRIBUTION",
    trade_date: datetime = _DAY,
    amount: str = "2900.43",
    description: str = "DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)",
) -> tuple:
    return (
        vendor_account,
        activity_id,
        activity_type,
        trade_date,
        trade_date,
        Decimal(amount),
        "USD",
        description,
        _HOUSEHOLD_ACCOUNT,
        "Cash Management (Joint WROS)",
    )


class _ScriptedConn:
    def __init__(
        self,
        activities: list[tuple],
        twin_counts: dict[str, int] | None = None,
        existing_hashes: set[str] | None = None,
    ) -> None:
        self.activities = activities
        self.twin_counts = twin_counts or {}
        self.existing_hashes = existing_hashes or set()
        self.transaction_inserts: list[dict[str, object]] = []
        self.committed = False
        self._result: tuple[str, object] = ("none", None)

    def execute(self, sql: str, params: list[object] | None = None) -> _ScriptedConn:
        params = params or []
        if "FROM snaptrade_activities" in sql:
            self._result = ("all", list(self.activities))
        elif "SELECT COUNT(*)" in sql:
            self._result = ("one", (self.twin_counts.get(str(params[1]), 0),))
        elif "WHERE row_hash = %s" in sql:
            hit = (1,) if params[0] in self.existing_hashes else None
            self._result = ("one", hit)
        elif "FROM household_documents" in sql:
            self._result = ("one", None)
        elif "INSERT INTO household_transactions" in sql:
            self.transaction_inserts.append(dict(zip(_INSERT_COLUMNS, params, strict=True)))
            self._result = ("none", None)
        else:
            self._result = ("none", None)
        return self

    def fetchall(self) -> list[tuple]:
        kind, payload = self._result
        if kind == "all" and isinstance(payload, list):
            return [tuple(item) for item in payload]
        return []

    def fetchone(self) -> object:
        return self._result[1] if self._result[0] == "one" else None

    def commit(self) -> None:
        self.committed = True


class _Storage:
    def __init__(self, conn: _ScriptedConn) -> None:
        self.conn = conn

    def connection(self) -> _Storage:
        return self

    def __enter__(self) -> _ScriptedConn:
        return self.conn

    def __exit__(self, *args: object) -> None:
        return None


class _StubTransactionService:
    def _resolve_merchant(self, *, conn, raw_merchant, category, essentiality):
        return (None, raw_merchant, category, essentiality, False, None)


def _run(conn: _ScriptedConn) -> dict[str, int]:
    return bridge_cash_activities(_Storage(conn), _StubTransactionService())


def test_connection_duplicates_collapse_to_one_income_row() -> None:
    conn = _ScriptedConn(
        [
            _activity(vendor_account="vend-a", activity_id="act-1"),
            _activity(vendor_account="vend-b", activity_id="act-2"),
        ]
    )

    counts = _run(conn)

    assert counts == {
        "bridged": 1,
        "already_bridged": 0,
        "twin_skipped": 0,
        "duplicate_collapsed": 1,
    }
    assert len(conn.transaction_inserts) == 1
    row = conn.transaction_inserts[0]
    assert row["flow_type"] == "income"
    assert row["category"] == "Income"
    assert row["amount"] == Decimal("2900.43")
    assert row["original_category"] == "CONTRIBUTION"
    assert row["categorization_source"] == "snaptrade"
    assert row["external_transaction_id"] == "act-1"
    assert conn.committed


def test_real_multiplicity_survives_collapse() -> None:
    # Two real PayPal micro-deposits seen through two connections = four raw
    # rows; the per-connection maximum (2) is the true event count.
    rows = [
        _activity(
            vendor_account=vendor,
            activity_id=f"act-{vendor}-{i}",
            amount="0.12",
            description="DIRECT DEPOSIT PAYPAL ACCTVERIFY (Cash)",
        )
        for vendor in ("vend-a", "vend-b")
        for i in range(2)
    ]
    conn = _ScriptedConn(rows)

    counts = _run(conn)

    assert counts["bridged"] == 2
    assert counts["duplicate_collapsed"] == 2
    occurrences = sorted({r["row_hash"] for r in conn.transaction_inserts})
    assert len(occurrences) == 2


def test_existing_foreign_twin_absorbs_instance() -> None:
    # The statement CSV already ingested this EFT; the bridge must not
    # double-count it.
    conn = _ScriptedConn(
        [
            _activity(
                vendor_account="vend-a",
                activity_id="act-1",
                trade_date=datetime(2026, 5, 1, 4, 0, tzinfo=UTC),
                amount="3200.0000",
                description="Electronic Funds Transfer Received (Cash)",
            )
        ],
        twin_counts={"3200.0000": 1},
    )

    counts = _run(conn)

    assert counts["bridged"] == 0
    assert counts["twin_skipped"] == 1
    assert conn.transaction_inserts == []


def test_flow_classification_matches_statement_csv_path() -> None:
    conn = _ScriptedConn(
        [
            _activity(
                vendor_account="vend-a",
                activity_id="act-duke",
                activity_type="WITHDRAWAL",
                amount="-170.43",
                description="DIRECT DEBIT DUKEENERGY BILL PAY (Cash)",
            ),
            _activity(
                vendor_account="vend-a",
                activity_id="act-cepay",
                activity_type="WITHDRAWAL",
                amount="-6243.47",
                description="DIRECT DEBIT CHASE CREDIT CEPAY (Cash)",
            ),
            _activity(
                vendor_account="vend-a",
                activity_id="act-div",
                activity_type="DIVIDEND",
                amount="103.29",
                description="DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)",
            ),
        ]
    )

    _run(conn)

    by_external = {r["external_transaction_id"]: r for r in conn.transaction_inserts}
    assert by_external["act-duke"]["flow_type"] == "expense"
    assert by_external["act-cepay"]["flow_type"] == "transfer_out"
    assert by_external["act-cepay"]["category"] == "Transfers"
    assert by_external["act-div"]["flow_type"] == "income"
    # Ledger stores absolute amounts; direction lives in flow_type.
    assert by_external["act-duke"]["amount"] == Decimal("170.43")


def test_already_bridged_rows_are_left_alone() -> None:
    conn = _ScriptedConn(
        [_activity(vendor_account="vend-a", activity_id="act-1")],
    )
    first = _run(conn)
    assert first["bridged"] == 1
    bridged_hash = conn.transaction_inserts[0]["row_hash"]

    rerun = _ScriptedConn(
        [_activity(vendor_account="vend-a", activity_id="act-1")],
        existing_hashes={str(bridged_hash)},
    )
    counts = _run(rerun)

    assert counts["bridged"] == 0
    assert counts["already_bridged"] == 1
    assert rerun.transaction_inserts == []
