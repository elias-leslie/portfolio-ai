"""One explicit content unit for package comparisons; invoice units stay separate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services._household_report_builder import _extract_package_measure

UNIT_LABELS = {"weight_oz": "oz", "volume_fl_oz": "fl oz", "count": "ct"}


@dataclass(frozen=True)
class UnitPriceBasis:
    package_quantity: float
    package_count: float
    unit: str
    unit_label: str
    package_label: str
    line_total: float
    package_price: float
    unit_price: float
    evidence_text: str


def positive_number(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def unit_price_basis(
    *,
    description: str,
    metadata: dict[str, Any],
    line_total: object,
    packages: object,
    source: str,
    quote_package_label: str = "",
) -> UnitPriceBasis | None:
    confirmation = metadata.get("package_confirmation")
    if (
        isinstance(confirmation, dict)
        and confirmation.get("confirmed_by")
        and source != "vendor_quote"
    ):
        description = str(confirmation.get("package_label") or "")
        packages = confirmation.get("packages")
        metadata = {}
    paid = positive_number(line_total)
    count = 1.0 if source == "vendor_quote" else positive_number(packages)
    if paid is None or count is None:
        return None
    # Quotes explicitly price one advertised package. Purchase rows price the
    # whole line, so a two-package purchase contains twice one package's contents.
    if source == "vendor_quote":
        measure = _extract_package_measure(quote_package_label, {}) if quote_package_label else None
    else:
        measure = _extract_package_measure(description, metadata)
    if measure is None or measure.normalized_unit not in UNIT_LABELS:
        return None
    total_contents = count * measure.normalized_quantity
    return UnitPriceBasis(
        package_quantity=measure.normalized_quantity,
        package_count=count,
        unit=measure.normalized_unit,
        unit_label=UNIT_LABELS[measure.normalized_unit],
        package_label=measure.display_label,
        line_total=paid,
        package_price=paid / count,
        unit_price=paid / total_contents,
        evidence_text=measure.evidence_text,
    )


def offer_is_ready(metadata: dict[str, Any], observed_date: object, *, today: object) -> bool:
    """A researched price is provisional until its buying conditions are confirmed."""
    if not isinstance(today, date) or not isinstance(observed_date, date):
        return False
    age = (today - observed_date).days
    if not 0 <= age <= 14:
        return False
    try:
        valid_until = date.fromisoformat(str(metadata.get("valid_until") or ""))
    except ValueError:
        return False
    if today > valid_until or valid_until < observed_date:
        return False
    return (
        metadata.get("equivalence_confirmed") is True
        and metadata.get("availability_confirmed") is True
        and metadata.get("fees_confirmed") is True
        and metadata.get("coupon_confirmed") is True
        and metadata.get("membership_confirmed") is True
    )
