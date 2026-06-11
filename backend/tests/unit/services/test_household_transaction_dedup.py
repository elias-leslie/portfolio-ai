"""Unit tests for the cross-document transaction dedup clustering logic."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.household_transaction_dedup_service import (
    cluster_rows,
    merchant_key,
    merchants_compatible,
    plan_cluster,
)


def _row(
    *,
    row_id: str,
    document_id: str,
    source_system: str = "statement_csv",
    on: date = date(2026, 1, 2),
    raw_merchant: str = "ALL SMILES ORTHO LARGO | Sale",
    categorization_source: str = "parser",
    category: str = "Healthcare",
) -> dict:
    return {
        "id": row_id,
        "document_id": document_id,
        "household_account_id": "acct-1",
        "source_system": source_system,
        "transaction_date": on,
        "amount": 132.08,
        "flow_type": "expense",
        "raw_merchant": raw_merchant,
        "description": raw_merchant,
        "categorization_source": categorization_source,
        "category": category,
        "essentiality": "essential",
        "category_updated_at": None,
        "category_updated_by": None,
        "transaction_rule_id": None,
        "created_at": datetime(2026, 1, 3, tzinfo=UTC),
    }


def test_merchant_key_strips_everything_but_letters() -> None:
    assert (
        merchant_key({"raw_merchant": "ALL SMILES ORTHO LARGO 727-3086773 FL | Sale"})
        == "allsmilesortholargoflsale"
    )
    assert merchant_key({"raw_merchant": None, "description": "All Smiles Ortho"}) == "allsmilesortho"


def test_merchants_compatible_prefix_with_min_length() -> None:
    # Plaid truncation vs statement spelling.
    assert merchants_compatible("allsmilesortho", "allsmilesortholargosale")
    assert merchants_compatible("allsmilesortho", "allsmilesortho")
    # Suffix decorations on the same merchant ("| Sale" vs "(Store #...)").
    assert merchants_compatible("walmartsale", "walmartstore")
    # Different merchants never match.
    assert not merchants_compatible("walgreenssale", "cvspharmacy")
    # Near-namesakes sharing a brand prefix stay distinct.
    assert not merchants_compatible("amazonmktpl", "amazonprime")
    # Too-short fingerprints cannot vouch for identity.
    assert not merchants_compatible("cvs", "cvspharmacy")
    assert not merchants_compatible("", "anything")


def test_cluster_same_date_rows_join_regardless_of_merchant() -> None:
    rows = [
        _row(row_id="a", document_id="d1", raw_merchant="WALGREENS #6803"),
        _row(row_id="b", document_id="d1", raw_merchant="CVS/PHARMACY #05786"),
    ]
    assert len(cluster_rows(rows)) == 1


def test_cluster_cross_source_date_skew_requires_compatible_merchants() -> None:
    plaid = _row(
        row_id="p",
        document_id="dp",
        source_system="plaid",
        on=date(2026, 3, 3),
        raw_merchant="All Smiles Ortho",
    )
    csv = _row(
        row_id="c",
        document_id="dc",
        on=date(2026, 3, 2),
        raw_merchant="ALL SMILES ORTHO LARGO | Sale",
    )
    other = _row(
        row_id="o",
        document_id="do",
        on=date(2026, 3, 4),
        raw_merchant="CVS/PHARMACY #05786",
    )
    clusters = cluster_rows([plaid, csv, other])
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]


def test_cluster_same_source_different_dates_never_join() -> None:
    rows = [
        _row(row_id="a", document_id="d1", on=date(2026, 3, 2)),
        _row(row_id="b", document_id="d2", on=date(2026, 3, 4)),
    ]
    assert len(cluster_rows(rows)) == 2


def test_plan_keeps_max_per_document_multiplicity() -> None:
    # 3 overlapping exports each contain the SAME two real charges
    # (two kids, same ortho price, same day) plus Plaid's pair at +1 day.
    cluster = []
    for doc in ("d1", "d2", "d3"):
        cluster.append(_row(row_id=f"{doc}-largo", document_id=doc))
        cluster.append(
            _row(
                row_id=f"{doc}-clear",
                document_id=doc,
                raw_merchant="ALL SMILES ORTHO CLEAR | Sale",
            )
        )
    cluster.append(
        _row(
            row_id="p-largo",
            document_id="dp",
            source_system="plaid",
            on=date(2026, 1, 3),
            raw_merchant="All Smiles Ortho",
        )
    )
    cluster.append(
        _row(
            row_id="p-clear",
            document_id="dp",
            source_system="plaid",
            on=date(2026, 1, 3),
            raw_merchant="All Smiles Ortho Clear",
        )
    )
    plan = plan_cluster(cluster)
    assert plan is not None
    # Two real charges survive; plaid wins the tie on source priority.
    assert sorted(r["id"] for r in plan["survivors"]) == ["p-clear", "p-largo"]
    assert len(plan["removed"]) == 6


def test_plan_single_document_pair_is_not_a_duplicate() -> None:
    cluster = [
        _row(row_id="a", document_id="d1"),
        _row(row_id="b", document_id="d1", raw_merchant="ALL SMILES ORTHO CLEAR | Sale"),
    ]
    assert plan_cluster(cluster) is None


def test_plan_prefers_unit_with_manual_categorization() -> None:
    manual = _row(
        row_id="m",
        document_id="d1",
        categorization_source="manual",
        category="Kids",
    )
    plain = _row(row_id="p", document_id="d2", source_system="plaid", raw_merchant="All Smiles Ortho")
    plan = plan_cluster([manual, plain])
    assert plan is not None
    assert plan["survivors"][0]["id"] == "m"


def test_plan_copies_manual_category_onto_compatible_survivor() -> None:
    # Manual categorization lives on a row in the LOSING unit (the winning
    # unit has more rows), so the category must be copied across.
    winner_a = _row(row_id="wa", document_id="dw", source_system="plaid", raw_merchant="All Smiles Ortho")
    winner_b = _row(
        row_id="wb",
        document_id="dw",
        source_system="plaid",
        raw_merchant="All Smiles Ortho Clear",
    )
    loser_manual = _row(
        row_id="lm",
        document_id="dl",
        categorization_source="manual",
        category="Kids",
        raw_merchant="ALL SMILES ORTHO LARGO | Sale",
    )
    plan = plan_cluster([winner_a, winner_b, loser_manual])
    assert plan is not None
    assert [r["id"] for r in plan["removed"]] == ["lm"]
    assert len(plan["category_copies"]) == 1
    survivor, donor = plan["category_copies"][0]
    assert survivor["id"] == "wa"
    assert donor["id"] == "lm"
