"""Cross-document/source duplicate collapse for household_transactions.

Root cause: ``import_document_transactions`` builds ``row_hash`` from
``document.id``, so the same card charge re-imported from an overlapping
CSV export — or arriving again via Plaid / a parsed statement — always
mints a brand-new row. One real $132.08 charge was found 8x on a single
date (4 overlapping Chase exports x 2 parse variants) before this service
existed.

Design:

- Rows cluster when they share (household_account_id, amount, flow_type)
  and either land on the same calendar date, or come from *different*
  source systems within ``FUZZY_DATE_TOLERANCE_DAYS`` with compatible
  merchant strings (Plaid posts can lag statement dates by a day or two).
- The true charge count for a cluster is the row count of its most
  complete provenance unit (= document_id): an export that contains the
  date twice proves two real charges, so legitimate same-day same-amount
  pairs survive without any merchant-identity matching.
- Survivors are all rows of the best unit (most rows, then most manual
  categorizations, then source priority plaid > statement_activity >
  statement_csv, then oldest). Other rows get ``removed=TRUE`` plus a
  ``metadata.dedup`` audit blob — never deleted. Manual categorizations
  on removed rows are copied onto a compatible survivor.
- Only ``plaid`` / ``statement_csv`` / ``statement_activity`` rows are
  considered; pending rows are skipped (the soft-charge reconciler owns
  the pending lifecycle).

Known limit: two distinct real charges with identical amount, compatible
merchants, dates <= 3 days apart, *each seen by only one source*, would
collapse to one. Statement windows make that combination implausible.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

DEDUP_SOURCE_SYSTEMS = ("plaid", "statement_csv", "statement_activity")
SOURCE_PRIORITY = {"plaid": 3, "statement_activity": 2, "statement_csv": 1}
FUZZY_DATE_TOLERANCE_DAYS = 3
_MERCHANT_MIN_PREFIX = 6
_MERCHANT_MIN_SUBSUMED = 3
_MANUAL_SOURCES = {"manual", "manual_rule", "merchant_rule"}


def merchant_key(row: dict[str, Any]) -> str:
    """Alpha-only lowercase merchant fingerprint for cross-source matching."""
    raw = str(row.get("raw_merchant") or row.get("description") or "")
    return "".join(ch for ch in raw.lower() if ch.isalpha())


def merchants_compatible(a: str, b: str) -> bool:
    """True when the fingerprints share a long-enough common prefix.

    Sources decorate the same merchant differently — "WAL-MART #5831 | Sale"
    vs "Walmart (Store #5831)" vs "WAL-MART #5831 LARGO FL" — so strict
    prefix-subsumption misses real twins. A common prefix of at least
    ``_MERCHANT_MIN_PREFIX`` chars covering >= 60% of the shorter
    fingerprint accepts suffix decorations while keeping near-namesakes
    ("amazonmktpl" vs "amazonprime", common prefix 55%) apart.

    Fingerprints shorter than the minimum prefix ("cvs" from a bare Plaid
    label vs "cvspharmacymiamifl" from the statement) pass instead when the
    shorter key is wholly a prefix of the longer one — the surrounding
    cluster already gates on same account, same amount, and dates within
    tolerance, so a short exact-prefix match is the same merchant.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    common = 0
    for ch_a, ch_b in zip(a, b, strict=False):
        if ch_a != ch_b:
            break
        common += 1
    if common == min(len(a), len(b)) >= _MERCHANT_MIN_SUBSUMED:
        return True
    return common >= _MERCHANT_MIN_PREFIX and common >= 0.6 * min(len(a), len(b))


def _rows_joined(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a["transaction_date"] == b["transaction_date"]:
        return True
    if a["source_system"] == b["source_system"]:
        return False
    delta = abs((a["transaction_date"] - b["transaction_date"]).days)
    if delta > FUZZY_DATE_TOLERANCE_DAYS:
        return False
    return merchants_compatible(merchant_key(a), merchant_key(b))


def cluster_rows(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Union-find clustering within one (account, amount, flow_type) group."""
    parent = list(range(len(rows)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    ordered = sorted(range(len(rows)), key=lambda i: rows[i]["transaction_date"])
    for pos, i in enumerate(ordered):
        for j in ordered[pos + 1 :]:
            if (rows[j]["transaction_date"] - rows[i]["transaction_date"]).days > FUZZY_DATE_TOLERANCE_DAYS:
                break
            if _rows_joined(rows[i], rows[j]):
                parent[find(i)] = find(j)
    clusters: dict[int, list[dict[str, Any]]] = {}
    for i, row in enumerate(rows):
        clusters.setdefault(find(i), []).append(row)
    return list(clusters.values())


def plan_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick survivors for one duplicate cluster.

    Returns None when nothing should be removed. Otherwise:
    ``{"survivors": [...], "removed": [...], "category_copies": [...]}``
    where each category copy is ``(survivor_row, donor_row)``.
    """
    if len(cluster) < 2:
        return None
    units: dict[str, list[dict[str, Any]]] = {}
    for row in cluster:
        units.setdefault(str(row["document_id"]), []).append(row)
    if len(units) < 2:
        # Same-document rows have distinct row_hashes by construction:
        # they are distinct real charges, not duplicates.
        return None

    def manual_count(unit: list[dict[str, Any]]) -> int:
        return sum(1 for r in unit if r.get("categorization_source") in _MANUAL_SOURCES)

    def unit_rank(unit: list[dict[str, Any]]) -> tuple[int, int, int, float]:
        priority = max(SOURCE_PRIORITY.get(str(r["source_system"]), 0) for r in unit)
        oldest = min(
            (r["created_at"].timestamp() if r.get("created_at") else 0.0) for r in unit
        )
        return (len(unit), manual_count(unit), priority, -oldest)

    best = max(units.values(), key=unit_rank)
    if len(best) == len(cluster):
        return None
    survivor_ids = {str(r["id"]) for r in best}
    removed = [r for r in cluster if str(r["id"]) not in survivor_ids]

    category_copies: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for donor in removed:
        if donor.get("categorization_source") not in _MANUAL_SOURCES:
            continue
        donor_key = merchant_key(donor)
        candidates = [
            s
            for s in best
            if s.get("categorization_source") not in _MANUAL_SOURCES
            and merchants_compatible(merchant_key(s), donor_key)
        ]
        if candidates:
            category_copies.append((candidates[0], donor))
    return {"survivors": best, "removed": removed, "category_copies": category_copies}


class HouseholdTransactionDedupService:
    """Detects and soft-removes cross-document duplicate transactions."""

    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or get_storage()

    def dedupe_transactions(
        self,
        *,
        household_account_ids: list[str] | None = None,
        date_start: date | None = None,
        date_end: date | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Collapse duplicates, optionally scoped to accounts / a date window.

        The window is padded by the fuzzy tolerance so an import at a window
        edge still meets its cross-source twin.
        """
        where = [
            "removed IS NOT TRUE",
            "pending IS NOT TRUE",
            "source_system = ANY(%s)",
            "household_account_id IS NOT NULL",
        ]
        params: list[Any] = [list(DEDUP_SOURCE_SYSTEMS)]
        if household_account_ids:
            where.append("household_account_id = ANY(%s)")
            params.append([str(a) for a in household_account_ids])
        pad = timedelta(days=FUZZY_DATE_TOLERANCE_DAYS)
        if date_start is not None:
            where.append("transaction_date >= %s")
            params.append(datetime.combine(date_start - pad, datetime.min.time(), tzinfo=UTC))
        if date_end is not None:
            where.append("transaction_date <= %s")
            params.append(datetime.combine(date_end + pad, datetime.max.time(), tzinfo=UTC))

        batch_id = str(uuid.uuid4())
        summary = {
            "examined": 0,
            "clusters": 0,
            "removed": 0,
            "category_copies": 0,
            "dry_run": dry_run,
            "batch_id": batch_id,
            "samples": [],
        }
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, document_id, household_account_id, source_system,
                       transaction_date::date, amount, flow_type, raw_merchant,
                       description, categorization_source, category, essentiality,
                       category_updated_at, category_updated_by,
                       transaction_rule_id, created_at
                FROM household_transactions
                WHERE {' AND '.join(where)}
                """,
                params,
            ).fetchall()
            summary["examined"] = len(rows)
            groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
            for row in rows:
                record = {
                    "id": str(row[0]),
                    "document_id": str(row[1]),
                    "household_account_id": str(row[2]),
                    "source_system": str(row[3] or ""),
                    "transaction_date": row[4],
                    "amount": row[5],
                    "flow_type": str(row[6] or ""),
                    "raw_merchant": row[7],
                    "description": row[8],
                    "categorization_source": row[9],
                    "category": row[10],
                    "essentiality": row[11],
                    "category_updated_at": row[12],
                    "category_updated_by": row[13],
                    "transaction_rule_id": row[14],
                    "created_at": row[15],
                }
                key = (
                    record["household_account_id"],
                    f"{record['amount']:.4f}",
                    record["flow_type"],
                )
                groups.setdefault(key, []).append(record)

            now = datetime.now(UTC)
            for group in groups.values():
                if len(group) < 2:
                    continue
                for cluster in cluster_rows(group):
                    plan = plan_cluster(cluster)
                    if plan is None:
                        continue
                    summary["clusters"] += 1
                    summary["removed"] += len(plan["removed"])
                    summary["category_copies"] += len(plan["category_copies"])
                    if len(summary["samples"]) < 10:
                        sample = plan["removed"][0]
                        summary["samples"].append(
                            {
                                "date": sample["transaction_date"].isoformat(),
                                "amount": str(sample["amount"]),
                                "merchant": sample["raw_merchant"] or sample["description"],
                                "removed": len(plan["removed"]),
                                "kept": len(plan["survivors"]),
                            }
                        )
                    if dry_run:
                        continue
                    survivor_id = str(plan["survivors"][0]["id"])
                    for removed_row in plan["removed"]:
                        conn.execute(
                            """
                            UPDATE household_transactions
                            SET removed = TRUE,
                                metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                                updated_at = %s
                            WHERE id = %s
                            """,
                            [
                                json.dumps(
                                    {
                                        "dedup": {
                                            "batch_id": batch_id,
                                            "kept_transaction_id": survivor_id,
                                            "reason": "cross_document_duplicate",
                                        }
                                    }
                                ),
                                now,
                                removed_row["id"],
                            ],
                        )
                    for survivor, donor in plan["category_copies"]:
                        conn.execute(
                            """
                            UPDATE household_transactions
                            SET category = %s,
                                essentiality = %s,
                                categorization_source = %s,
                                category_updated_at = %s,
                                category_updated_by = %s,
                                transaction_rule_id = %s,
                                updated_at = %s
                            WHERE id = %s
                              AND categorization_source NOT IN ('manual', 'manual_rule', 'merchant_rule')
                            """,
                            [
                                donor["category"],
                                donor["essentiality"],
                                donor["categorization_source"],
                                donor["category_updated_at"],
                                donor["category_updated_by"],
                                donor["transaction_rule_id"],
                                now,
                                survivor["id"],
                            ],
                        )
            if not dry_run:
                conn.commit()
        if summary["removed"]:
            logger.info(
                "household_transaction_dedup",
                removed=summary["removed"],
                clusters=summary["clusters"],
                dry_run=dry_run,
                batch_id=batch_id,
            )
        return summary
