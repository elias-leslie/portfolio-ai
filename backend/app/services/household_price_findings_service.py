"""Price-check findings: cheaper-elsewhere detection with noise thresholds.

A finding is worth showing only when the saving is material — at least
max($3, 15% of what the household pays) on a product bought at least twice.
A single aggregate roll-up rides along only when the run's combined savings
reach $25. Findings are in-app only ([G:2d62382d]): they never feed Money or
Today alerts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdPriceFinding
from app.services._household_finance_utils import iso_or_none, to_float
from app.storage import get_storage

MIN_SAVINGS_ABS = 3.0
MIN_SAVINGS_PCT = 0.15
MIN_PURCHASE_COUNT = 2
ROLLUP_MIN_TOTAL = 25.0
_OPEN_FINDINGS_CAP = 50


@dataclass(frozen=True)
class FindingCandidate:
    """One product's best vendor quote vs what the household pays."""

    product_id: str
    product_name: str
    purchase_count: int
    household_price: float
    vendor_key: str
    vendor_price: float
    vendor_url: str | None = None
    vendor_title: str | None = None
    vendor_package_label: str | None = None
    vendor_promo_text: str | None = None


@dataclass(frozen=True)
class FindingDraft:
    kind: str  # cheaper_elsewhere | savings_rollup
    savings_estimate: float
    product_id: str | None = None
    vendor_key: str | None = None
    payload: dict[str, Any] | None = None


def evaluate_candidates(candidates: list[FindingCandidate]) -> list[FindingDraft]:
    """Pure threshold logic: per-product findings plus an optional roll-up."""
    drafts: list[FindingDraft] = []
    for candidate in candidates:
        if candidate.purchase_count < MIN_PURCHASE_COUNT:
            continue
        if candidate.household_price <= 0:
            continue
        savings = round(candidate.household_price - candidate.vendor_price, 2)
        threshold = max(MIN_SAVINGS_ABS, MIN_SAVINGS_PCT * candidate.household_price)
        if savings < threshold:
            continue
        drafts.append(
            FindingDraft(
                kind="cheaper_elsewhere",
                savings_estimate=savings,
                product_id=candidate.product_id,
                vendor_key=candidate.vendor_key,
                payload={
                    "product_name": candidate.product_name,
                    "household_price": candidate.household_price,
                    "vendor_price": candidate.vendor_price,
                    "vendor_url": candidate.vendor_url,
                    "vendor_title": candidate.vendor_title,
                    "vendor_package_label": candidate.vendor_package_label,
                    "vendor_promo_text": candidate.vendor_promo_text,
                },
            )
        )
    total = round(sum(d.savings_estimate for d in drafts), 2)
    if drafts and total >= ROLLUP_MIN_TOTAL:
        drafts.append(
            FindingDraft(
                kind="savings_rollup",
                savings_estimate=total,
                payload={
                    "finding_count": len(drafts),
                    "product_names": [
                        d.payload["product_name"] for d in drafts if d.payload
                    ],
                },
            )
        )
    return drafts


class HouseholdPriceFindingsService:
    """Persists evaluated findings and serves the open list."""

    def __init__(self) -> None:
        self.storage = get_storage()

    def replace_run_findings(
        self,
        conn: Any,
        *,
        run_id: str,
        candidates: list[FindingCandidate],
    ) -> int:
        """Supersede prior open price-check findings and insert this run's."""
        drafts = evaluate_candidates(candidates)
        # A fresh run is the new truth for every product it priced — and for
        # the roll-up, which only ever reflects the latest run.
        conn.execute(
            """
            UPDATE household_price_findings
            SET status = 'superseded', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'open'
              AND (
                  kind = 'savings_rollup'
                  OR (kind = 'cheaper_elsewhere' AND product_id = ANY(%s::uuid[]))
              )
            """,
            [[c.product_id for c in candidates] or [str(uuid.uuid4())]],
        )
        now = datetime.now(UTC).isoformat()
        for draft in drafts:
            conn.execute(
                """
                INSERT INTO household_price_findings (
                    id, kind, product_id, vendor_key, price_check_run_id,
                    savings_estimate, status, payload, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'open', %s::jsonb, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    draft.kind,
                    draft.product_id,
                    draft.vendor_key,
                    run_id,
                    draft.savings_estimate,
                    json.dumps(draft.payload or {}),
                    now,
                    now,
                ],
            )
        return len(drafts)

    def list_open_findings(self) -> list[HouseholdPriceFinding]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.kind, f.status, f.product_id, p.canonical_name,
                       f.vendor_key, f.savings_estimate, f.payload, f.created_at
                FROM household_price_findings f
                LEFT JOIN household_products p ON p.id = f.product_id
                WHERE f.status = 'open'
                ORDER BY (f.kind = 'savings_rollup') DESC,
                         f.savings_estimate DESC NULLS LAST,
                         f.created_at DESC
                LIMIT %s
                """,
                [_OPEN_FINDINGS_CAP],
            ).fetchall()
        return [_finding(row) for row in rows]


def _finding(row: Any) -> HouseholdPriceFinding:
    payload = row[7] if isinstance(row[7], dict) else json.loads(row[7] or "{}")
    return HouseholdPriceFinding(
        id=str(row[0]),
        kind=str(row[1]),
        status=str(row[2]),
        product_id=str(row[3]) if row[3] is not None else None,
        product_name=str(row[4]) if row[4] else payload.get("product_name"),
        vendor_key=str(row[5]) if row[5] else None,
        savings_estimate=to_float(row[6]),
        household_price=to_float(payload.get("household_price")),
        vendor_price=to_float(payload.get("vendor_price")),
        vendor_url=payload.get("vendor_url"),
        vendor_title=payload.get("vendor_title"),
        vendor_package_label=payload.get("vendor_package_label"),
        vendor_promo_text=payload.get("vendor_promo_text"),
        detail=(
            f"{payload.get('finding_count')} products are cheaper elsewhere"
            if str(row[1]) == "savings_rollup"
            else None
        ),
        created_at=iso_or_none(row[8]),
    )
