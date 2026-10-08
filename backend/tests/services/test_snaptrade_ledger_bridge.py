from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from app.services._snaptrade_ledger_bridge import _row_hash, bridge_cash_activities

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
    currency: str = "USD",
    synced_at: datetime = _DAY,
) -> tuple:
    return (
        vendor_account,
        activity_id,
        activity_type,
        trade_date,
        trade_date,
        Decimal(amount),
        currency,
        description,
        _HOUSEHOLD_ACCOUNT,
        "Cash Management (Joint WROS)",
        synced_at,
    )


class _ScriptedConn:
    def __init__(
        self,
        activities: list[tuple],
        twin_counts: dict[str, int] | None = None,
        existing_hashes: set[str] | None = None,
        foreign_rows: list[dict] | None = None,
        existing_rows: list[dict] | None = None,
    ) -> None:
        self.activities = activities
        self.twin_counts = twin_counts or {}
        self.existing_hashes = existing_hashes or set()
        self.foreign_rows = foreign_rows or []
        self.existing_rows = existing_rows or []
        self.transaction_inserts: list[dict[str, object]] = []
        self.transaction_updates: list[tuple[str, list[object]]] = []
        self.committed = False
        self._result: tuple[str, object] = ("none", None)

    def execute(self, sql: str, params: list[object] | None = None) -> _ScriptedConn:
        params = params or []
        if "FROM snaptrade_activities" in sql:
            self._result = ("all", list(self.activities))
        elif "SELECT COUNT(*)" in sql:
            self._result = ("one", (self.twin_counts.get(str(params[1]), len(self.foreign_rows)),))
        elif "source_system <> 'snaptrade'" in sql:
            if self.foreign_rows:
                matches = [row for row in self.foreign_rows if row["amount"] == params[1] and row["currency"] == params[2] and row["flow_type"] in params[3]]
                self._result = ("all", [(row["id"],) for row in matches])
            else:
                self._result = ("all", [(f"twin-{index}",) for index in range(self.twin_counts.get(str(params[1]), 0))])
        elif "source_system = 'snaptrade'" in sql and "SELECT" in sql:
            refs = params[2]
            ids = params[3]
            assert isinstance(refs, list)
            assert isinstance(ids, list)
            matches = []
            for row in self.existing_rows:
                metadata = json.loads(str(row["metadata"]))
                stable_refs = metadata.get("snaptrade_activity_refs", [])
                if row["row_hash"] == params[1] or any(ref in stable_refs for ref in refs) or (not stable_refs and any(identity in metadata.get("snaptrade_activity_ids", []) for identity in ids)):
                    matches.append((row["id"], row["row_hash"], metadata))
            matches.extend((value, value, {}) for value in self.existing_hashes if value == params[1])
            self._result = ("all", matches)
        elif "WHERE row_hash = %s" in sql:
            hit = (1,) if params[0] in self.existing_hashes else None
            self._result = ("one", hit)
        elif "FROM household_documents" in sql:
            self._result = ("one", None)
        elif "INSERT INTO household_transactions" in sql:
            self.transaction_inserts.append(dict(zip(_INSERT_COLUMNS, params, strict=True)))
            self._result = ("none", None)
        elif "UPDATE household_transactions" in sql:
            self.transaction_updates.append((sql, params))
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


def test_bridge_keeps_vendor_description_as_raw_evidence() -> None:
    class RenamingService(_StubTransactionService):
        def _resolve_merchant(self, *, conn, raw_merchant, category, essentiality):
            return (None, "A derived display name", category, essentiality, False, None)

    description = "DEBIT CARD PURCHASE PUBLIX #1309 (Cash)"
    conn = _ScriptedConn([_activity(vendor_account="a", activity_id="x", description=description)])
    bridge_cash_activities(_Storage(conn), RenamingService())
    assert conn.transaction_inserts[0]["raw_merchant"] == description


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
    assert by_external["act-div"]["flow_type"] == "investment"
    assert by_external["act-div"]["category"] == "Investments"
    # Ledger stores absolute amounts; direction lives in flow_type.
    assert by_external["act-duke"]["amount"] == Decimal("170.43")


def test_already_bridged_rows_are_left_alone() -> None:
    conn = _ScriptedConn(
        [_activity(vendor_account="vend-a", activity_id="act-1")],
    )
    first = _run(conn)
    assert first["bridged"] == 1
    rerun = _ScriptedConn(
        [_activity(vendor_account="vend-a", activity_id="act-1")],
        existing_rows=conn.transaction_inserts,
    )
    counts = _run(rerun)

    assert counts["bridged"] == 0
    assert counts["already_bridged"] == 1
    assert rerun.transaction_inserts == []


def test_foreign_twin_requires_compatible_direction_and_currency() -> None:
    for foreign in [
        {"id": "opposite", "amount": Decimal("2900.43"), "currency": "USD", "flow_type": "expense"},
        {"id": "foreign-currency", "amount": Decimal("2900.43"), "currency": "EUR", "flow_type": "income"},
    ]:
        conn = _ScriptedConn([_activity(vendor_account="a", activity_id="x")], foreign_rows=[foreign])
        counts = _run(conn)
        assert counts["bridged"] == 1
        assert counts["twin_skipped"] == 0


def test_one_foreign_twin_cannot_absorb_two_distinct_activity_groups() -> None:
    conn = _ScriptedConn(
        [_activity(vendor_account="a", activity_id="first"), _activity(vendor_account="a", activity_id="second", description="SECOND PAYROLL")],
        foreign_rows=[{"id": "statement", "amount": Decimal("2900.43"), "currency": "USD", "flow_type": "income"}],
    )
    counts = _run(conn)
    assert counts["twin_skipped"] == 1
    assert counts["bridged"] == 1


def test_currency_is_part_of_activity_deduplication() -> None:
    conn = _ScriptedConn([_activity(vendor_account="a", activity_id="usd"), _activity(vendor_account="b", activity_id="eur", currency="EUR")])
    counts = _run(conn)
    assert counts["bridged"] == 2
    assert {row["currency"] for row in conn.transaction_inserts} == {"USD", "EUR"}


def test_corrected_stable_activity_updates_existing_row_without_duplicate() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="stable")])
    _run(first)
    existing = first.transaction_inserts[0]
    corrected = _ScriptedConn([_activity(vendor_account="a", activity_id="stable", amount="2910.00", description="CORRECTED PAYROLL", trade_date=datetime(2026, 5, 15, tzinfo=UTC))], existing_rows=[existing])
    counts = _run(corrected)
    assert counts["bridged"] == 0
    assert counts["already_bridged"] == 1
    assert corrected.transaction_inserts == []
    assert len(corrected.transaction_updates) == 1
    sql, params = corrected.transaction_updates[0]
    assert Decimal("2910.00") in params
    assert "CORRECTED PAYROLL" in params
    assert "removed =" not in sql
    assert "'transaction_audit'" in sql
    assert "THEN flow_type" in sql
    assert "THEN category" in sql


def test_legacy_linkage_survives_correction_and_preserves_audit_metadata() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="stable")])
    _run(first)
    existing = first.transaction_inserts[0]
    metadata = json.loads(str(existing["metadata"]))
    metadata.pop("snaptrade_activity_refs", None)
    metadata["audit"] = {"status": "reviewed"}
    existing["metadata"] = json.dumps(metadata)
    corrected = _ScriptedConn([_activity(vendor_account="a", activity_id="stable", amount="2910.00")], existing_rows=[existing])
    assert _run(corrected)["already_bridged"] == 1
    assert corrected.transaction_inserts == []
    assert "COALESCE(metadata" in corrected.transaction_updates[0][0]


def test_multiplicity_assigns_stable_activity_linkage_per_occurrence() -> None:
    first = _ScriptedConn([_activity(vendor_account=vendor, activity_id=f"{vendor}-{index}") for vendor in ("a", "b") for index in range(2)])
    _run(first)
    refs = [json.loads(str(row["metadata"]))["snaptrade_activity_refs"] for row in first.transaction_inserts]
    assert len(refs) == 2
    assert not any(ref in refs[1] for ref in refs[0])


def test_split_correction_does_not_reuse_one_existing_row_for_two_events() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="a-0"), _activity(vendor_account="b", activity_id="b-0")])
    _run(first)
    corrected = _ScriptedConn(
        [_activity(vendor_account="a", activity_id="a-0", amount="3000.00", synced_at=datetime(2026, 5, 16, tzinfo=UTC)), _activity(vendor_account="b", activity_id="b-0")],
        existing_rows=first.transaction_inserts,
    )
    counts = _run(corrected)
    assert counts["bridged"] == 0
    assert len(corrected.transaction_updates) == 1
    assert corrected.transaction_inserts == []
    assert corrected.transaction_updates[0][1][2] == Decimal("3000.00")


def test_correction_prefers_stable_identity_over_another_events_natural_hash() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="corrected", amount="2900.43"), _activity(vendor_account="a", activity_id="other", amount="3000.00")])
    _run(first)
    by_activity = {row["external_transaction_id"]: row for row in first.transaction_inserts}
    by_activity["other"]["row_hash"] = _row_hash(household_account_id=_HOUSEHOLD_ACCOUNT, trade_date=_DAY.date().isoformat(), amount="3000.00", activity_type="CONTRIBUTION", description="DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)", occurrence=0)
    corrected = _ScriptedConn([_activity(vendor_account="a", activity_id="corrected", amount="3000.00")], existing_rows=[by_activity["other"], by_activity["corrected"]])
    assert _run(corrected)["already_bridged"] == 1
    assert corrected.transaction_updates[0][1][-1] == by_activity["corrected"]["id"]


def test_new_activity_at_corrected_rows_old_hash_remains_a_distinct_event() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="original")])
    _run(first)
    existing = first.transaction_inserts[0]
    # Simulate a migrated production row: provider facts were corrected while
    # the historical natural hash and stable linkage remained on that row.
    old_hash = _row_hash(household_account_id=_HOUSEHOLD_ACCOUNT, trade_date=_DAY.date().isoformat(), amount="2900.43", activity_type="CONTRIBUTION", description="DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)", occurrence=0)
    existing["row_hash"] = old_hash
    existing["amount"] = Decimal("3000.00")
    conn = _ScriptedConn(
        [_activity(vendor_account="a", activity_id="original", amount="3000.00"), _activity(vendor_account="a", activity_id="new-event")],
        existing_rows=[existing],
    )
    counts = _run(conn)
    assert counts["already_bridged"] == 1
    assert counts["bridged"] == 1
    assert conn.transaction_updates[0][1][2] == Decimal("3000.00")
    assert conn.transaction_inserts[0]["external_transaction_id"] == "new-event"
    assert conn.transaction_inserts[0]["row_hash"] != old_hash
    refs = json.loads(str(conn.transaction_updates[0][1][-3]))["snaptrade_activity_refs"]
    assert json.dumps(["a", "new-event"]) not in refs


def test_legacy_reviewed_row_cannot_transfer_to_a_new_activity_at_its_old_hash() -> None:
    first = _ScriptedConn([_activity(vendor_account="a", activity_id="original")])
    _run(first)
    existing = first.transaction_inserts[0]
    metadata = json.loads(str(existing["metadata"]))
    metadata.pop("snaptrade_activity_refs")
    metadata["audit"] = {"status": "reviewed"}
    existing["metadata"] = json.dumps(metadata)
    existing["categorization_source"] = "transaction_audit"
    existing["category"] = "Reviewed income"
    existing["removed"] = True
    existing["row_hash"] = _row_hash(household_account_id=_HOUSEHOLD_ACCOUNT, trade_date=_DAY.date().isoformat(), amount="2900.43", activity_type="CONTRIBUTION", description="DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)", occurrence=0)
    conn = _ScriptedConn(
        [_activity(vendor_account="a", activity_id="original", amount="3000.00"), _activity(vendor_account="a", activity_id="new-event")],
        existing_rows=[existing],
    )
    counts = _run(conn)
    assert counts["already_bridged"] == counts["bridged"] == 1
    assert len(conn.transaction_updates) == 1
    sql, params = conn.transaction_updates[0]
    assert params[-1] == existing["id"]
    assert params[2] == Decimal("3000.00")
    linked = json.loads(str(params[-3]))
    assert linked["snaptrade_activity_ids"] == ["original"]
    assert json.dumps(["a", "new-event"]) not in linked["snaptrade_activity_refs"]
    assert "THEN category" in sql and "'transaction_audit'" in sql
    assert "removed =" not in sql
    assert conn.transaction_inserts[0]["external_transaction_id"] == "new-event"
