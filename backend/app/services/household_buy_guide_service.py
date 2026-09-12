"""Unit-cost buy guide for recurring household purchases.

The buy guide keeps the first version deliberately narrow: compare actual paid
unit costs for repeat products against known larger/vendor quote observations,
then surface only material unit-cost opportunities with confidence notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.models.household_finance_types import (
    HouseholdBuyGuide,
    HouseholdBuyGuideItem,
    HouseholdBuyGuideTrendPoint,
)
from app.services._household_finance_utils import to_float
from app.services._household_price_location import shopping_today
from app.services._household_report_builder import _coerce_metadata
from app.services.household_shopping_pilot import HouseholdShoppingPilot
from app.services.household_unit_prices import offer_is_ready, unit_price_basis
from app.storage import get_storage

MIN_ACTUAL_OBSERVATIONS = 2
MIN_PACKAGE_SAVINGS = 2.0
MIN_MONTHLY_SAVINGS = 1.0
BULK_SIZE_MULTIPLE = 1.2
BULK_TRAP_MONTHS = 6.0
FRESH_QUOTE_DAYS = 14
MIN_VENDOR_QUOTE_CONFIDENCE = 0.7
RECENT_USAGE_DAYS = 365
ACTIVE_BASELINE_DAYS = 180
ACTUAL_CANDIDATE_MAX_AGE_DAYS = 14
TREND_POINT_CAP = 8
DEFAULT_LIMIT = 12
MAX_LIMIT = 50

_UNIT_LABELS = {
    "weight_oz": "oz",
    "volume_fl_oz": "fl oz",
    "count": "ct",
}


@dataclass(frozen=True)
class _Observation:
    product_id: str
    product_name: str
    brand: str | None
    merchant: str | None
    observed_date: date
    total_price: float
    package_label: str | None
    package_quantity: float
    package_unit: str
    source: str
    metadata: dict[str, Any]
    package_count: float = 1.0

    @property
    def unit_cost(self) -> float:
        return round(self.total_price / self.package_quantity, 4)

    @property
    def source_rank(self) -> int:
        if self.source == "receipt":
            return 0
        if self.source == "order_history":
            return 1
        if self.source == "vendor_quote":
            return 2
        return 3


def _observation(row: Any) -> _Observation | None:
    observed_date = row[4]
    if hasattr(observed_date, "date"):
        observed_date = observed_date.date()
    if not isinstance(observed_date, date):
        return None
    total_price = to_float(row[5])
    if total_price is None or total_price <= 0:
        return None
    basis = unit_price_basis(
        description=str(row[13] or row[1]),
        metadata=_coerce_metadata(row[14]),
        line_total=total_price,
        packages=row[12],
        source=str(row[10]),
        quote_package_label=str(row[7] or ""),
    )
    if basis is None:
        return None
    return _Observation(
        product_id=str(row[0]),
        product_name=str(row[1] or ""),
        brand=str(row[2]) if row[2] else None,
        merchant=str(
            row[3]
            or _coerce_metadata(row[11]).get("store")
            or _coerce_metadata(row[11]).get("vendor_key")
            or ""
        )
        or None,
        observed_date=observed_date,
        total_price=round(basis.package_price, 2),
        package_label=basis.package_label,
        package_quantity=basis.package_quantity,
        package_unit=basis.unit,
        source=str(row[10] or ""),
        metadata=_coerce_metadata(row[11]),
        package_count=basis.package_count,
    )


def _unit_label(unit: str) -> str:
    return _UNIT_LABELS.get(unit, unit.replace("_", " "))


def _quote_url(observation: _Observation) -> str | None:
    url = observation.metadata.get("url")
    return str(url) if url else None


def _quote_title(observation: _Observation) -> str | None:
    title = observation.metadata.get("title")
    return str(title) if title else None


def _quote_confidence(observation: _Observation) -> float | None:
    return to_float(observation.metadata.get("confidence"))


def _is_actual(observation: _Observation) -> bool:
    return observation.source in {"receipt", "order_history"}


def _days_old(observation: _Observation, *, today: date) -> int:
    return max(0, (today - observation.observed_date).days)


def _monthly_units(actual: list[_Observation], *, today: date) -> float | None:
    recent_cutoff = today - timedelta(days=RECENT_USAGE_DAYS)
    recent = [row for row in actual if row.observed_date >= recent_cutoff]
    rows = recent if len(recent) >= MIN_ACTUAL_OBSERVATIONS else actual[-6:]
    if not rows:
        return None
    first = min(row.observed_date for row in rows)
    last = max(row.observed_date for row in rows)
    days = (last - first).days
    if days < 14:
        return None
    # Purchases at the last observation have not yet been consumed. Including
    # them over the preceding interval doubles a two-purchase frequency estimate.
    total_units = sum(
        row.package_quantity * row.package_count for row in rows if row.observed_date < last
    )
    monthly = total_units * 30.437 / days
    return round(monthly, 2) if monthly > 0 else None


def _trend_points(rows: list[_Observation]) -> list[HouseholdBuyGuideTrendPoint]:
    ordered = sorted(rows, key=lambda row: (row.observed_date, row.source_rank))[-TREND_POINT_CAP:]
    return [
        HouseholdBuyGuideTrendPoint(
            observed_date=row.observed_date.isoformat(),
            merchant=row.merchant,
            package_label=row.package_label,
            total_price=row.total_price,
            unit_cost=row.unit_cost,
            source=row.source,
        )
        for row in ordered
    ]


def _candidate_score(candidate: _Observation) -> tuple[float, int, int]:
    return (candidate.unit_cost, candidate.source_rank, -candidate.observed_date.toordinal())


def _best_candidate(
    *,
    baseline: _Observation,
    observations: list[_Observation],
    today: date,
) -> _Observation | None:
    candidates = []
    latest = {}
    for row in sorted(observations, key=lambda item: item.observed_date):
        if row.source == "vendor_quote":
            latest[(row.merchant, row.metadata.get("title"), row.package_label)] = row
    for candidate in latest.values():
        if candidate is baseline:
            continue
        if candidate.package_unit != baseline.package_unit:
            continue
        if candidate.unit_cost >= baseline.unit_cost:
            continue
        # Receipts describe a past purchase, not stock or the price today.
        if candidate.source != "vendor_quote" or not offer_is_ready(
            candidate.metadata, candidate.observed_date, today=today
        ):
            continue
        candidates.append(candidate)
    return min(candidates, key=_candidate_score) if candidates else None


def _confidence(
    *,
    actual_count: int,
    baseline: _Observation,
    candidate: _Observation,
    months_to_use: float | None,
    today: date,
) -> tuple[float, list[str]]:
    reasons = [
        f"{actual_count} purchase observations; latest {baseline.observed_date.isoformat()}",
        f"Package equivalence and buying conditions confirmed; price checked {_days_old(candidate, today=today)} days ago",
        "Monthly differences assume the current price and observed restocking pace continue; they are not realized savings.",
    ]
    if months_to_use is not None and months_to_use > BULK_TRAP_MONTHS:
        reasons.append("The package exceeds six months of observed purchases.")
    # Compatibility field only: no calibrated probability is available.
    return 0.0, reasons


def _finding_kind(
    *,
    baseline: _Observation,
    candidate: _Observation,
    months_to_use: float | None,
) -> str:
    larger_package = candidate.package_quantity >= baseline.package_quantity * BULK_SIZE_MULTIPLE
    same_merchant = (candidate.merchant or "") == (baseline.merchant or "")
    if months_to_use is not None and months_to_use > BULK_TRAP_MONTHS:
        return "bulk_trap_risk"
    if larger_package and same_merchant:
        return "buy_bigger_same_store"
    if larger_package:
        return "buy_bigger_elsewhere"
    return "lower_price_same_store" if same_merchant else "switch_vendor"


def _recommendation(
    *,
    baseline: _Observation,
    candidate: _Observation,
    savings_pct: float,
    months_to_use: float | None,
) -> str:
    unit_label = _unit_label(baseline.package_unit)
    candidate_name = candidate.merchant or "the candidate vendor"
    larger = candidate.package_quantity >= baseline.package_quantity * BULK_SIZE_MULTIPLE
    if larger and (candidate.merchant or "") == (baseline.merchant or ""):
        lead = f"Buy the larger {candidate.package_label or 'package'} at {candidate_name}."
    elif larger:
        lead = f"Check {candidate_name}'s larger {candidate.package_label or 'package'}."
    else:
        lead = f"Check {candidate_name} before rebuying."
    tail = f" It is {savings_pct:.0f}% lower per {unit_label} than the latest buy."
    if months_to_use is not None:
        tail += f" If your observed restocking pace continues, this is about {months_to_use:.1f} months of purchases; actual use may differ."
    return lead + tail


def _guide_item(
    *,
    product_id: str,
    observations: list[_Observation],
    today: date,
) -> HouseholdBuyGuideItem | None:
    actual = [
        row
        for row in observations
        if _is_actual(row) and row.product_id == product_id and row.observed_date <= today
    ]
    if len(actual) < MIN_ACTUAL_OBSERVATIONS:
        return None
    by_unit: dict[str, list[_Observation]] = {}
    for row in observations:
        by_unit.setdefault(row.package_unit, []).append(row)
    best_item: HouseholdBuyGuideItem | None = None
    for unit, unit_rows in by_unit.items():
        unit_actual = [
            row
            for row in unit_rows
            if _is_actual(row) and row.product_id == product_id and row.observed_date <= today
        ]
        if len(unit_actual) < MIN_ACTUAL_OBSERVATIONS:
            continue
        baseline = max(unit_actual, key=lambda row: (row.observed_date, -row.source_rank))
        if _days_old(baseline, today=today) > ACTIVE_BASELINE_DAYS:
            continue
        candidate = _best_candidate(baseline=baseline, observations=unit_rows, today=today)
        if candidate is None:
            continue
        savings_per_unit = round(baseline.unit_cost - candidate.unit_cost, 4)
        savings_pct = round((savings_per_unit / baseline.unit_cost) * 100, 1)
        monthly_units = _monthly_units(unit_actual, today=today)
        estimated_monthly_savings = (
            round(savings_per_unit * monthly_units, 2)
            if monthly_units is not None and not candidate.metadata.get("coupon")
            else None
        )
        package_savings = savings_per_unit * candidate.package_quantity
        if package_savings < MIN_PACKAGE_SAVINGS and (
            estimated_monthly_savings is None or estimated_monthly_savings < MIN_MONTHLY_SAVINGS
        ):
            continue
        months_to_use = (
            round(candidate.package_quantity / monthly_units, 1)
            if monthly_units and monthly_units > 0
            else None
        )
        confidence, reasons = _confidence(
            actual_count=len(unit_actual),
            baseline=baseline,
            candidate=candidate,
            months_to_use=months_to_use,
            today=today,
        )
        item = HouseholdBuyGuideItem(
            product_id=product_id,
            product_name=baseline.product_name,
            brand=baseline.brand,
            purchase_count=len(unit_actual),
            unit_label=_unit_label(unit),
            current_merchant=baseline.merchant,
            current_package_label=baseline.package_label,
            current_total_price=baseline.total_price,
            current_unit_cost=baseline.unit_cost,
            current_observed_date=baseline.observed_date.isoformat(),
            best_merchant=candidate.merchant,
            best_package_label=candidate.package_label,
            best_total_price=candidate.total_price,
            best_unit_cost=candidate.unit_cost,
            best_source=candidate.source,
            best_observed_date=candidate.observed_date.isoformat(),
            best_url=_quote_url(candidate),
            best_title=_quote_title(candidate),
            best_valid_until=str(candidate.metadata.get("valid_until") or "") or None,
            best_conditions=str(candidate.metadata.get("conditions") or "") or None,
            savings_per_unit=savings_per_unit,
            savings_pct=savings_pct,
            estimated_monthly_savings=estimated_monthly_savings,
            months_to_use=months_to_use,
            finding_kind=_finding_kind(
                baseline=baseline,
                candidate=candidate,
                months_to_use=months_to_use,
            ),
            recommendation=_recommendation(
                baseline=baseline,
                candidate=candidate,
                savings_pct=savings_pct,
                months_to_use=months_to_use,
            ),
            confidence=confidence,
            confidence_reasons=reasons,
            trend_points=_trend_points(unit_rows),
        )
        if best_item is None or _item_sort_key(item) < _item_sort_key(best_item):
            best_item = item
    return best_item


def _item_sort_key(item: HouseholdBuyGuideItem) -> tuple[float, float, str]:
    monthly = item.estimated_monthly_savings or 0.0
    return (-monthly, -item.savings_pct, item.product_name)


class HouseholdBuyGuideService:
    """Build recurring-purchase unit-cost recommendations from stored evidence."""

    def __init__(self) -> None:
        self.storage = get_storage()

    def get_buy_guide(self, *, limit: int = DEFAULT_LIMIT) -> HouseholdBuyGuide:
        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
        today = shopping_today()
        with self.storage.connection() as conn:
            pilot_ids = [p.id for p in HouseholdShoppingPilot().products(conn)]
            families = dict(
                conn.execute(
                    "SELECT id::text, metadata->'comparison_family'->>'id' FROM household_products"
                ).fetchall()
            )
            comparison_ids = list(
                set(pilot_ids)
                | {
                    pid
                    for pid, family in families.items()
                    if family and family in {families.get(p) for p in pilot_ids}
                }
            )
            rows = conn.execute(
                """
                SELECT o.product_id::text, p.canonical_name, p.brand,
                       COALESCE(m.canonical_name, m.display_name, ''),
                       o.observed_date,
                       CAST(o.total_price AS DOUBLE PRECISION),
                       CAST(o.total_price AS DOUBLE PRECISION),
                       o.package_display_label,
                       CAST(o.package_normalized_quantity AS DOUBLE PRECISION),
                       o.package_normalized_unit,
                       o.source,
                       o.metadata, o.quantity, COALESCE(i.description, p.canonical_name), COALESCE(ir.row_metadata,'{}'::jsonb) || o.metadata
                FROM household_product_price_observations o
                JOIN household_products p ON p.id = o.product_id
                LEFT JOIN household_purchase_items i ON i.id = o.purchase_item_id
                LEFT JOIN household_import_rows ir ON ir.id = i.import_row_id
                LEFT JOIN household_merchants m ON m.id = o.merchant_id
                WHERE o.product_id=ANY(%s::uuid[]) AND o.total_price > 0 AND o.observed_date<=CURRENT_DATE
                  AND (i.id IS NULL OR i.removed IS NOT TRUE)
                ORDER BY o.product_id, o.observed_date ASC, o.created_at ASC
                """,
                [comparison_ids],
            ).fetchall()
        by_product: dict[str, list[_Observation]] = {}
        unit_coverage_products: set[str] = set()
        for row in rows:
            observation = _observation(row)
            if observation is None:
                continue
            by_product.setdefault(observation.product_id, []).append(observation)
            if _is_actual(observation):
                unit_coverage_products.add(observation.product_id)

        items = [
            item
            for product_id in pilot_ids
            for observations in [
                [
                    row
                    for pid, points in by_product.items()
                    for row in points
                    if pid == product_id
                    or (
                        row.source == "vendor_quote"
                        and families.get(product_id)
                        and families.get(pid) == families.get(product_id)
                    )
                ]
            ]
            if (item := _guide_item(product_id=product_id, observations=observations, today=today))
            is not None
        ]
        items.sort(key=_item_sort_key)
        return HouseholdBuyGuide(
            generated_at=datetime.now(UTC).isoformat(),
            total_candidates=len(items),
            returned_count=min(limit, len(items)),
            unit_coverage_count=len(unit_coverage_products),
            items=items[:limit],
        )


__all__ = ["HouseholdBuyGuideService"]
