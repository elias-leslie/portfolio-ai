"""Unit tests for the cross-document transaction dedup clustering logic."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.household_transaction_dedup_service import (
    DEDUP_SOURCE_SYSTEMS,
    SOURCE_PRIORITY,
    cluster_rows,
    find_flow_contradictions,
    merchant_direction_evidence,
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


def test_merchant_key_strips_processor_prefixes() -> None:
    # Statement labels carry the card processor; Plaid strips it. Both sides
    # must fingerprint to the same merchant.
    assert merchant_key({"raw_merchant": "SQ *NU AGE ADVANCED AESTH"}) == merchant_key(
        {"raw_merchant": "Nu Age Advanced Aesth"}
    )
    assert merchant_key({"raw_merchant": "GOOGLE *Claude by Anth"}) == merchant_key(
        {"raw_merchant": "Claude By Anth"}
    )
    assert merchant_key({"raw_merchant": "SP PQ SWIM | Sale"}) == "pqswimsale"
    assert merchant_key({"raw_merchant": "TST* 37 MAIN"}) == "main"
    # Words merely starting with a processor token are untouched.
    assert merchant_key({"raw_merchant": "Spotify"}) == "spotify"
    assert merchant_key({"raw_merchant": "Square Deal Diner"}) == "squaredealdiner"
    # A label that is nothing but the processor token keeps its raw key.
    assert merchant_key({"raw_merchant": "SQ *"}) == "sq"
    # Franchise parent suffix ("... by Hilton") folds into the franchise name
    # so city-decorated statement labels subsume it.
    assert merchant_key({"raw_merchant": "Home2 Suites by Hilton"}) == "homesuites"
    assert merchants_compatible(
        merchant_key({"raw_merchant": "HOME2 SUITES-NAPLES NAPLES FL"}),
        merchant_key({"raw_merchant": "Home2 Suites by Hilton"}),
    )


def test_merchant_key_collapses_walmart_brand_family() -> None:
    assert merchant_key({"raw_merchant": "WM SUPERCENTER #5831 LARGO FL"}) == "walmart"
    assert merchant_key({"raw_merchant": "WALMART.COM AR"}) == "walmart"
    assert merchant_key({"raw_merchant": "Walmart (Store #5831)"}) == "walmart"
    assert merchant_key({"raw_merchant": "WAL-MART #5831 | Sale"}) == "walmart"
    # Non-Walmart brands are untouched.
    assert merchant_key({"raw_merchant": "Walgreens #6803"}) == "walgreens"


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
    # A short fingerprint that is wholly a prefix of the longer one is the
    # same merchant (bare Plaid "CVS" vs statement "CVS/PHARMACY #05786...").
    assert merchants_compatible("cvs", "cvspharmacymiamifl")
    # ...but only with at least a few characters to vouch for it.
    assert not merchants_compatible("bp", "bpgasstation")
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


def test_merchant_key_strips_statement_redaction_runs() -> None:
    """Two exports of one payment must fingerprint alike even when one masks digits.

    A statement that prints ``xxxxx0775`` where another prints ``990040775``
    carries five extra letters into an alpha-only fingerprint -- enough to push a
    true pair under the prefix threshold and leave one payment on the books
    twice, in opposite directions.
    """
    masked = merchant_key(
        {"raw_merchant": None, "description": "Prog Select Ins Ins Prem 260217 xxxxx0775 Elias"}
    )
    unmasked = merchant_key(
        {"raw_merchant": None, "description": "PROG SELECT INS  INS PREM   260217 990040775 Elias"}
    )

    assert masked == unmasked
    assert merchants_compatible(masked, unmasked)


def test_merchant_key_strips_leading_transaction_type() -> None:
    """Bank statements lead with the mechanism; card feeds lead with the payee."""
    from_statement = merchant_key(
        {"raw_merchant": None, "description": "DIRECT DEBIT DUKEENERGY BILL PAY (Cash)"}
    )
    from_feed = merchant_key({"raw_merchant": "DUKEENERGY BILL PAY", "description": ""})

    assert from_statement == from_feed


def test_merchant_key_keeps_the_payee_when_the_whole_label_is_a_prefix() -> None:
    """Stripping must never empty the fingerprint entirely."""
    assert merchant_key({"raw_merchant": None, "description": "DIRECT DEBIT"})


def test_flow_contradiction_pairs_one_payment_booked_both_ways() -> None:
    """One premium, two exports, opposite signs -- a $554 swing on a single payment."""
    income_row = _row(
        row_id="income",
        document_id="doc-csv",
        source_system="statement_csv",
        raw_merchant="PROG SELECT INS  INS PREM   260217 990040775 Elias",
    )
    income_row["flow_type"] = "income"
    expense_row = _row(
        row_id="expense",
        document_id="doc-bank",
        source_system="bank_statement",
        raw_merchant="Prog Select Ins Ins Prem 260217 xxxxx0775 Elias",
    )
    expense_row["household_account_id"] = "acct-2"

    pairs = find_flow_contradictions([income_row, expense_row])

    assert len(pairs) == 1
    assert pairs[0][0]["id"] == "income"
    assert pairs[0][1]["id"] == "expense"


def test_flow_contradiction_ignores_a_same_account_reversal() -> None:
    """A reversal on one account nets out on its own and is not a duplicate."""
    income_row = _row(row_id="a", document_id="doc-1")
    income_row["flow_type"] = "income"
    expense_row = _row(row_id="b", document_id="doc-1")

    assert find_flow_contradictions([income_row, expense_row]) == []


def test_flow_contradiction_ignores_internal_transfers() -> None:
    """An internal move between two owned accounts is supposed to be a matched pair."""
    out_row = _row(row_id="out", document_id="doc-1")
    out_row["flow_type"] = "transfer_out"
    in_row = _row(row_id="in", document_id="doc-2")
    in_row["flow_type"] = "transfer_in"
    in_row["household_account_id"] = "acct-2"

    assert find_flow_contradictions([out_row, in_row]) == []


def test_merchant_direction_evidence_needs_an_unambiguous_majority() -> None:
    """A merchant with genuinely mixed direction yields no verdict rather than a guess."""
    expense_one = _row(row_id="e1", document_id="doc-1")
    expense_two = _row(row_id="e2", document_id="doc-2")
    income_one = _row(row_id="i1", document_id="doc-3")
    income_one["flow_type"] = "income"

    verdicts = merchant_direction_evidence([expense_one, expense_two, income_one])
    assert verdicts[merchant_key(expense_one)] == "expense"

    tied = merchant_direction_evidence([expense_one, income_one])
    assert merchant_key(expense_one) not in tied


def test_live_feeds_outrank_one_time_uploads() -> None:
    """A provider still reporting has corrected what a static export froze."""
    assert SOURCE_PRIORITY["plaid"] > SOURCE_PRIORITY["statement_csv"]
    assert SOURCE_PRIORITY["snaptrade"] > SOURCE_PRIORITY["bank_statement"]
    # Both parsed-statement sources are in scope; receipts keep their own lifecycle.
    assert "bank_statement" in DEDUP_SOURCE_SYSTEMS
    assert "snaptrade" in DEDUP_SOURCE_SYSTEMS
    assert "receipt_summary" not in DEDUP_SOURCE_SYSTEMS


def test_cluster_cross_document_same_date_requires_compatible_merchants() -> None:
    """Same day, same amount, different payees is ordinary on a checking account.

    Money arrives and is moved onward the same day for the same figure. Without
    a merchant check these collapse into one row and a real transaction is lost --
    here a note payment received from a buyer, deleted in favour of the internal
    transfer that moved it.
    """
    received = _row(
        row_id="zelle",
        document_id="doc-a",
        raw_merchant="Zelle From Michael Wiley on 12/31 Ref # Bacpc0Vvakeh 12th Payment",
    )
    received["flow_type"] = "transfer_in"
    moved = _row(
        row_id="internal",
        document_id="doc-b",
        raw_merchant="Recurring Transfer From Leslie E Ref #Op0W9Ymw4H Everyday Checking",
    )
    moved["flow_type"] = "transfer_in"

    assert len(cluster_rows([received, moved])) == 2


def test_cluster_cross_document_same_date_still_joins_compatible_merchants() -> None:
    """The ordinary case -- one charge exported twice -- must still collapse."""
    first = _row(row_id="a", document_id="doc-a", raw_merchant="ALL SMILES ORTHO LARGO | Sale")
    second = _row(row_id="b", document_id="doc-b", raw_merchant="All Smiles Ortho")

    assert len(cluster_rows([first, second])) == 1
