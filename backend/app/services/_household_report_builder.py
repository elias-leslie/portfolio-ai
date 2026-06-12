"""Helpers for assembling household transaction reports."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models.household_finance import (
    HouseholdCategoryBreakdown,
    HouseholdExecutiveReport,
    HouseholdMerchantInsight,
    HouseholdMonthlyTrendPoint,
    HouseholdPriceInsight,
    HouseholdRecentTransaction,
    HouseholdReports,
)
from app.services._household_document_pipeline_utils import parse_decimal_value

_EXECUTIVE_WINDOW_MONTHS = 6
_UNIT_PATTERN = (
    r"fluid ounces?|fl\.?\s*oz|ounces?|ounce|oz|pounds?|lbs?|lb|grams?|gram|g|kilograms?|kg|"
    r"milliliters?|milliliter|ml|liters?|liter|l|count|ct|capsules?|softgels?|tablets?|pieces?"
)
_MULTIPACK_SIZE_RE = re.compile(
    rf"\b(?P<count>\d+(?:\.\d+)?)\s*(?:x|-)\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
_SIMPLE_SIZE_RE = re.compile(
    rf"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
_SIZE_TOKEN_RE = re.compile(
    rf"\b\d+(?:\.\d+)?\s*(?:x|-)?\s*\d*(?:\.\d+)?\s*(?:{_UNIT_PATTERN})\b",
    re.IGNORECASE,
)
_STRIP_TOKENS_RE = re.compile(
    r"\b(pack|packs|box|boxes|bottle|bottles|bag|bags|jar|jars|case|cases|day supply|serving|servings)\b",
    re.IGNORECASE,
)
_WEIGHT_CONVERSIONS = {
    "oz": ("weight_oz", 1.0, "oz"),
    "ounce": ("weight_oz", 1.0, "oz"),
    "ounces": ("weight_oz", 1.0, "oz"),
    "lb": ("weight_oz", 16.0, "lb"),
    "lbs": ("weight_oz", 16.0, "lb"),
    "pound": ("weight_oz", 16.0, "lb"),
    "pounds": ("weight_oz", 16.0, "lb"),
    "g": ("weight_oz", 0.035274, "g"),
    "gram": ("weight_oz", 0.035274, "g"),
    "grams": ("weight_oz", 0.035274, "g"),
    "kg": ("weight_oz", 35.274, "kg"),
    "kilogram": ("weight_oz", 35.274, "kg"),
    "kilograms": ("weight_oz", 35.274, "kg"),
}
_VOLUME_CONVERSIONS = {
    "fl oz": ("volume_fl_oz", 1.0, "fl oz"),
    "fluid ounce": ("volume_fl_oz", 1.0, "fl oz"),
    "fluid ounces": ("volume_fl_oz", 1.0, "fl oz"),
    "ml": ("volume_fl_oz", 0.033814, "ml"),
    "milliliter": ("volume_fl_oz", 0.033814, "ml"),
    "milliliters": ("volume_fl_oz", 0.033814, "ml"),
    "l": ("volume_fl_oz", 33.814, "L"),
    "liter": ("volume_fl_oz", 33.814, "L"),
    "liters": ("volume_fl_oz", 33.814, "L"),
}
_COUNT_CONVERSIONS = {
    "count": ("count", 1.0, "count"),
    "ct": ("count", 1.0, "count"),
    "capsule": ("count", 1.0, "capsules"),
    "capsules": ("count", 1.0, "capsules"),
    "softgel": ("count", 1.0, "softgels"),
    "softgels": ("count", 1.0, "softgels"),
    "tablet": ("count", 1.0, "tablets"),
    "tablets": ("count", 1.0, "tablets"),
    "piece": ("count", 1.0, "count"),
    "pieces": ("count", 1.0, "count"),
}


@dataclass(frozen=True)
class _PackageMeasure:
    normalized_quantity: float
    normalized_unit: str
    display_label: str
    raw_quantity: float
    raw_unit: str
    score: float


def _coerce_metadata(raw_metadata: Any) -> dict[str, Any]:
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if isinstance(raw_metadata, str) and raw_metadata.strip():
        try:
            parsed = json.loads(raw_metadata)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_decimal_text(value: Any) -> float | None:
    if value in (None, ""):
        return None
    parsed = parse_decimal_value(str(value))
    if parsed is None or parsed <= 0:
        return None
    return float(parsed)


def _singularize_unit(raw_unit: str) -> str:
    normalized = raw_unit.strip().lower().replace(".", "")
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in {"floz", "fl oz", "fluid ounce", "fluid ounces"}:
        return "fl oz"
    return normalized


def _build_measure(*, quantity: float, raw_unit: str, multiplier: float = 1.0) -> _PackageMeasure | None:
    unit = _singularize_unit(raw_unit)
    conversion = (
        _WEIGHT_CONVERSIONS.get(unit)
        or _VOLUME_CONVERSIONS.get(unit)
        or _COUNT_CONVERSIONS.get(unit)
    )
    if conversion is None:
        return None
    normalized_unit, factor, label_unit = conversion
    raw_total = quantity * multiplier
    normalized_quantity = raw_total * factor
    if normalized_quantity <= 0:
        return None
    score = 0.0
    if normalized_unit.startswith("weight") or normalized_unit.startswith("volume"):
        score += 70.0
    else:
        score += 55.0
    if multiplier > 1:
        score += 12.0
    score += min(normalized_quantity, 500.0) / 50.0
    raw_display = f"{multiplier:g} x {quantity:g} {label_unit}" if multiplier > 1 else f"{quantity:g} {label_unit}"
    return _PackageMeasure(
        normalized_quantity=round(normalized_quantity, 4),
        normalized_unit=normalized_unit,
        display_label=raw_display,
        raw_quantity=raw_total,
        raw_unit=label_unit,
        score=round(score, 4),
    )


def _extract_package_measure(description: str, metadata: dict[str, Any]) -> _PackageMeasure | None:
    cached_enrichment = metadata.get("product_enrichment")
    cached_enrichment_dict = cached_enrichment if isinstance(cached_enrichment, dict) else {}
    cached_measure = cached_enrichment_dict.get("package_measure")
    if isinstance(cached_measure, dict):
        normalized_quantity = _parse_decimal_text(cached_measure.get("normalized_quantity"))
        normalized_unit = str(cached_measure.get("normalized_unit") or "").strip()
        display_label = str(cached_measure.get("display_label") or "").strip()
        raw_quantity = _parse_decimal_text(cached_measure.get("raw_quantity")) or normalized_quantity
        raw_unit = str(cached_measure.get("raw_unit") or "").strip() or normalized_unit
        if (
            normalized_quantity is not None
            and normalized_unit
            and display_label
            and raw_quantity is not None
        ):
            return _PackageMeasure(
                normalized_quantity=normalized_quantity,
                normalized_unit=normalized_unit,
                display_label=display_label,
                raw_quantity=raw_quantity,
                raw_unit=raw_unit,
                score=999.0,
            )

    text = " ".join(
        part
        for part in (
            str(metadata.get("Product Name") or "").strip(),
            description.strip(),
        )
        if part
    )
    if not text:
        return None

    candidates: list[_PackageMeasure] = []
    for match in _MULTIPACK_SIZE_RE.finditer(text):
        count = _parse_decimal_text(match.group("count"))
        value = _parse_decimal_text(match.group("value"))
        if count is None or value is None:
            continue
        candidate = _build_measure(quantity=value, raw_unit=match.group("unit"), multiplier=count)
        if candidate is not None:
            candidates.append(candidate)

    for match in _SIMPLE_SIZE_RE.finditer(text):
        value = _parse_decimal_text(match.group("value"))
        if value is None:
            continue
        candidate = _build_measure(quantity=value, raw_unit=match.group("unit"))
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda candidate: (candidate.score, candidate.normalized_quantity),
    )


def _transaction_date(row: dict[str, Any]) -> date | None:
    raw_date = row.get("date")
    if isinstance(raw_date, date):
        return raw_date
    if hasattr(raw_date, "date"):
        return raw_date.date()
    return None


def _is_current_transaction(row: dict[str, Any], *, today: date) -> bool:
    transaction_date = _transaction_date(row)
    return transaction_date is not None and transaction_date <= today


def _merchant_root(merchant: str) -> str:
    normalized = merchant.strip().lower()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _merchant_aliases(raw_merchant: str) -> set[str]:
    root = _merchant_root(raw_merchant)
    aliases: set[str] = {root, root.replace(" ", "")} if root else set()
    collapsed = root.replace(" ", "") if root else ""
    if "walmart" in collapsed or "wmsupercenter" in collapsed:
        aliases.update({"walmart", "wal mart", "walmart supercenter", "wm supercenter", "wmsupercenter"})
    if "amazon" in collapsed or "amzn" in collapsed:
        aliases.update({"amazon", "amzn", "amazon mktpl", "amazoncom", "amazon com"})
    if "wholefoods" in collapsed:
        aliases.update({"whole foods", "wholefoods"})
    return {alias for alias in aliases if alias}


_NOISE_TOKENS = {
    "sale",
    "payment",
    "thank",
    "purchase",
    "debit",
    "credit",
    "card",
    "online",
    "pending",
    "posted",
    "bill",
    "wa",
    "com",
}
_OVERLAP_NOISE_TOKENS = _NOISE_TOKENS | {
    "amzn",
    "bill",
    "pmts",
    "mktpl",
    "mktplace",
    "store",
}
_PHONE_RE = re.compile(r"\b\d{3}[- ]?\d{3,4}[- ]?\d{2,4}\b", re.IGNORECASE)
_TRAILING_STATE_RE = re.compile(r"\b[a-z]{2}\b$", re.IGNORECASE)
_TRAILING_CITY_STATE_RE = re.compile(r"\b[a-z]+(?:\s+[a-z]+)?\s+[a-z]{2}\b$", re.IGNORECASE)


def _transaction_identity_tokens(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value)
        for value in (
            row.get("merchant") or "",
            row.get("description") or "",
        )
        if value
    ).lower()
    tokens = {
        token
        for token in re.findall(r"[a-z0-9#]{4,}", text)
        if token not in _NOISE_TOKENS
    }
    return tokens


def _transaction_overlap_signature(row: dict[str, Any]) -> tuple[str, ...]:
    text = " ".join(
        str(value)
        for value in (
            row.get("merchant") or "",
            row.get("description") or "",
        )
        if value
    ).lower()
    text = text.replace("amzn.com/bill", " ")
    text = text.replace("mktplace pmts", " ")
    text = text.replace("|", " ")
    text = _PHONE_RE.sub(" ", text)
    text = _TRAILING_CITY_STATE_RE.sub(" ", text)
    text = _TRAILING_STATE_RE.sub(" ", text)
    tokens = [
        token
        for token in re.findall(r"[a-z0-9#]{3,}", text)
        if token not in _OVERLAP_NOISE_TOKENS
    ]
    return tuple(sorted(dict.fromkeys(tokens)))


def _signatures_overlap(
    existing_signature: tuple[str, ...],
    candidate_signature: tuple[str, ...],
) -> bool:
    if not existing_signature or not candidate_signature:
        return False
    if existing_signature == candidate_signature:
        return True
    existing_tokens = set(existing_signature)
    candidate_tokens = set(candidate_signature)
    shared_tokens = existing_tokens.intersection(candidate_tokens)
    if len(shared_tokens) >= 2:
        return True
    return bool(shared_tokens) and (
        len(existing_tokens) == 1 or len(candidate_tokens) == 1
    )


def _date_distance_days(existing_row: dict[str, Any], candidate_row: dict[str, Any]) -> int | None:
    existing_date = _transaction_date(existing_row)
    candidate_date = _transaction_date(candidate_row)
    if existing_date is None or candidate_date is None:
        return None
    return abs((existing_date - candidate_date).days)


def _same_spending_account(existing_row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    existing_account_id = str(existing_row.get("household_account_id") or "").strip()
    candidate_account_id = str(candidate_row.get("household_account_id") or "").strip()
    if existing_account_id and existing_account_id == candidate_account_id:
        return True

    existing_label = _merchant_root(str(existing_row.get("account_label") or ""))
    candidate_label = _merchant_root(str(candidate_row.get("account_label") or ""))
    return bool(existing_label and existing_label == candidate_label)


def _different_evidence_sources(existing_row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    source_types = {
        str(existing_row.get("source_type") or ""),
        str(candidate_row.get("source_type") or ""),
    }
    document_types = {
        str(existing_row.get("document_type") or ""),
        str(candidate_row.get("document_type") or ""),
    }
    source_kinds = {
        str(existing_row.get("source_kind") or ""),
        str(candidate_row.get("source_kind") or ""),
    }
    return len(source_types) > 1 or len(document_types) > 1 or "import" in source_kinds


def report_rows_overlap(existing_row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    same_date = existing_row.get("date") == candidate_row.get("date")
    same_amount = (
        abs(float(existing_row.get("amount", 0.0)) - float(candidate_row.get("amount", 0.0)))
        <= 0.005
    )
    if not same_amount:
        return False
    source_kinds = {
        str(existing_row.get("source_kind") or ""),
        str(candidate_row.get("source_kind") or ""),
    }
    document_types = {
        str(existing_row.get("document_type") or ""),
        str(candidate_row.get("document_type") or ""),
    }
    # household_transaction_dedup_service owns plain transaction-vs-transaction
    # duplicates at the DB layer, and it deliberately keeps legitimate same-day
    # same-amount pairs (two kids' identical ortho charges) that the signature
    # heuristics here would merge. This layer only reconciles evidence the DB
    # ledger can't see: import rows and receipt documents.
    if "import" not in source_kinds and "receipt" not in document_types:
        return False
    near_cross_source_duplicate = (
        _different_evidence_sources(existing_row, candidate_row)
        and (date_distance := _date_distance_days(existing_row, candidate_row)) is not None
        and date_distance <= 2
    )
    if not (same_date or near_cross_source_duplicate):
        return False

    existing_aliases = _merchant_aliases(str(existing_row.get("merchant") or ""))
    candidate_aliases = _merchant_aliases(str(candidate_row.get("merchant") or ""))
    shared_aliases = existing_aliases.intersection(candidate_aliases)

    same_account = _same_spending_account(existing_row, candidate_row)
    signature_overlap = False
    generic_alias_overlap = False
    if same_account:
        existing_signature = _transaction_overlap_signature(existing_row)
        candidate_signature = _transaction_overlap_signature(candidate_row)
        signature_overlap = _signatures_overlap(existing_signature, candidate_signature)
        generic_alias_overlap = (
            (not existing_signature or not candidate_signature)
            and bool(shared_aliases)
        )

    cross_source_duplicate = near_cross_source_duplicate and bool(shared_aliases) and (
        "import" in source_kinds
        or ("receipt" in document_types and len(document_types) > 1)
    )
    return (
        (same_date or near_cross_source_duplicate)
        and (signature_overlap or generic_alias_overlap)
    ) or cross_source_duplicate


def report_row_exclusion_reason(
    existing_row: dict[str, Any],
    candidate_row: dict[str, Any],
) -> str | None:
    if not report_rows_overlap(existing_row, candidate_row):
        return None
    source_kinds = {
        str(existing_row.get("source_kind") or ""),
        str(candidate_row.get("source_kind") or ""),
    }
    if "import" in source_kinds:
        return "duplicate_of_import"
    document_types = {
        str(existing_row.get("document_type") or ""),
        str(candidate_row.get("document_type") or ""),
    }
    if "receipt" in document_types and len(document_types) > 1:
        return "duplicate_of_receipt"
    return "duplicate_overlap"


def report_row_priority(row: dict[str, Any]) -> tuple[int, str]:
    if row.get("source_kind") == "import":
        return (0, str(row.get("document_id") or ""))

    document_type = str(row.get("document_type") or "")
    if document_type == "receipt":
        return (1, str(row.get("document_id") or ""))

    return (2, str(row.get("document_id") or ""))


def collapse_report_rows(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collapsed_rows, _ = collapse_report_rows_with_exclusions(report_rows)
    return collapsed_rows


def collapse_report_rows_with_exclusions(
    report_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    collapsed_rows: list[dict[str, Any]] = []
    excluded_rows: dict[str, str] = {}
    for row in sorted(report_rows, key=report_row_priority):
        exclusion_reason = next(
            (
                report_row_exclusion_reason(existing_row, row)
                for existing_row in collapsed_rows
                if report_row_exclusion_reason(existing_row, row) is not None
            ),
            None,
        )
        if exclusion_reason is not None:
            row_key = str(row.get("row_hash") or row.get("id") or "")
            if row_key:
                excluded_rows[row_key] = exclusion_reason
            continue
        collapsed_rows.append(row)
    return collapsed_rows, excluded_rows


def _normalized_item_key(merchant: str, description: str) -> str:
    description_without_sizes = _SIZE_TOKEN_RE.sub(" ", description.lower())
    description_without_sizes = _STRIP_TOKENS_RE.sub(" ", description_without_sizes)
    normalized = _merchant_root(f"{merchant} {description_without_sizes}")
    return re.sub(r"\s+", " ", normalized).strip()


def _observed_import_price(row: dict[str, Any], metadata: dict[str, Any]) -> float | None:
    unit_price = _parse_decimal_text(metadata.get("Unit Price"))
    if unit_price is not None:
        return unit_price
    subtotal = _parse_decimal_text(metadata.get("Shipment Item Subtotal"))
    quantity = _parse_decimal_text(metadata.get("Original Quantity"))
    if subtotal is not None and quantity not in (None, 0):
        return round(subtotal / quantity, 2)
    amount = row.get("amount")
    try:
        parsed_amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        parsed_amount = None
    return parsed_amount if parsed_amount and parsed_amount > 0 else None


def _signal_priority(insight: HouseholdPriceInsight) -> tuple[int, float, str]:
    if insight.shrinkflation_flag:
        magnitude = abs(insight.unit_price_change_pct or insight.size_change_pct or 0.0)
        return (0, -magnitude, insight.latest_date)
    if (insight.unit_price_change_pct or 0.0) > 0:
        return (1, -abs(insight.unit_price_change_pct or 0.0), insight.latest_date)
    if insight.price_change > 0:
        return (2, -abs(insight.price_change), insight.latest_date)
    return (3, -abs(insight.price_change), insight.latest_date)


def _build_price_insights(
    *,
    expense_rows: list[dict[str, Any]],
) -> list[HouseholdPriceInsight]:
    item_history: dict[str, list[dict[str, Any]]] = {}
    for row in expense_rows:
        if row.get("source_kind") != "import":
            continue
        metadata = _coerce_metadata(row.get("metadata"))
        description = str(metadata.get("Product Name") or row.get("description") or "").strip()
        merchant = str(row.get("merchant") or "").strip()
        row_date = row.get("date")
        amount = _observed_import_price(row, metadata)
        if not description or not merchant or not isinstance(row_date, date) or amount is None or amount <= 0:
            continue
        item_key = _normalized_item_key(merchant, description)
        if not item_key:
            continue
        package_measure = _extract_package_measure(description, metadata)
        item_history.setdefault(item_key, []).append(
            {
                "merchant": merchant,
                "description": description,
                "date": row_date,
                "amount": amount,
                "identifier": str(metadata.get("ASIN") or metadata.get("UPC") or metadata.get("GTIN") or "").strip(),
                "measure": package_measure,
            }
        )

    insights: list[HouseholdPriceInsight] = []
    for rows in item_history.values():
        if len(rows) < 2:
            continue
        ordered = sorted(rows, key=lambda row: row["date"], reverse=True)
        latest = ordered[0]
        previous = next(
            (
                row
                for row in ordered[1:]
                if (
                    row["date"] != latest["date"]
                    or abs(row["amount"] - latest["amount"]) > 0.01
                    or (
                        row.get("measure") is not None
                        and latest.get("measure") is not None
                        and row["measure"].display_label != latest["measure"].display_label
                    )
                )
            ),
            None,
        )
        if previous is None:
            continue
        price_change = round(latest["amount"] - previous["amount"], 2)
        price_change_pct = (
            round((price_change / previous["amount"]) * 100, 1)
            if previous["amount"] > 0
            else None
        )
        latest_measure = latest.get("measure")
        previous_measure = previous.get("measure")
        measures_comparable = (
            latest_measure is not None
            and previous_measure is not None
            and latest_measure.normalized_unit == previous_measure.normalized_unit
        )
        latest_unit_price = (
            round(latest["amount"] / latest_measure.normalized_quantity, 4)
            if measures_comparable and latest_measure.normalized_quantity > 0
            else None
        )
        previous_unit_price = (
            round(previous["amount"] / previous_measure.normalized_quantity, 4)
            if measures_comparable and previous_measure.normalized_quantity > 0
            else None
        )
        unit_price_change_pct = (
            round(((latest_unit_price - previous_unit_price) / previous_unit_price) * 100, 1)
            if latest_unit_price is not None
            and previous_unit_price is not None
            and previous_unit_price > 0
            else None
        )
        size_change_pct = (
            round(
                ((latest_measure.normalized_quantity - previous_measure.normalized_quantity)
                 / previous_measure.normalized_quantity)
                * 100,
                1,
            )
            if measures_comparable and previous_measure.normalized_quantity > 0
            else None
        )
        shrinkflation_flag = bool(
            measures_comparable
            and latest_measure.normalized_quantity < previous_measure.normalized_quantity * 0.985
            and latest["amount"] >= previous["amount"] - 0.05
        )
        if not shrinkflation_flag and abs(price_change) < 0.15 and abs(unit_price_change_pct or 0.0) < 3.0:
            continue

        same_identifier = bool(latest["identifier"] and latest["identifier"] == previous["identifier"])
        confidence = 0.58
        if measures_comparable:
            confidence += 0.18
        if same_identifier:
            confidence += 0.18
        if latest_measure is not None and previous_measure is not None:
            confidence += 0.06
        confidence = round(min(confidence, 0.95), 2)

        if shrinkflation_flag:
            signal_type = "shrinkflation"
            recommendation = (
                "Sticker price held roughly flat while package size shrank. Track unit price first and compare the current pack against Walmart, Target, or another equivalent size before rebuying."
            )
        elif (unit_price_change_pct or 0.0) >= 5.0:
            signal_type = "unit_price_up"
            recommendation = (
                "Unit price is up materially versus the prior buy. Compare equivalent pack sizes across Amazon, Walmart, Target, or local stores before reordering."
            )
        elif price_change > 0:
            signal_type = "price_up"
            recommendation = (
                "Ticket price is up versus the prior buy. Compare Amazon against Walmart, Target, or local alternatives before reordering."
            )
        else:
            signal_type = "price_down"
            recommendation = (
                "Price is down versus the prior buy. This is a better re-buy window if you still need it."
            )
        insights.append(
            HouseholdPriceInsight(
                merchant=str(latest["merchant"]),
                item_name=str(latest["description"]),
                signal_type=signal_type,
                latest_price=round(latest["amount"], 2),
                previous_price=round(previous["amount"], 2),
                price_change=price_change,
                price_change_pct=price_change_pct,
                latest_date=latest["date"].isoformat(),
                previous_date=previous["date"].isoformat(),
                latest_unit_label=latest_measure.display_label if latest_measure is not None else None,
                previous_unit_label=previous_measure.display_label if previous_measure is not None else None,
                unit_measure=latest_measure.normalized_unit if latest_measure is not None else None,
                latest_unit_price=latest_unit_price,
                previous_unit_price=previous_unit_price,
                unit_price_change_pct=unit_price_change_pct,
                size_change_pct=size_change_pct,
                shrinkflation_flag=shrinkflation_flag,
                confidence=confidence,
                recommendation=recommendation,
            )
        )

    return sorted(insights, key=_signal_priority)[:6]


def build_household_reports(
    *,
    report_rows: list[dict[str, Any]],
    cadence_for_dates: Callable[[list[date]], dict[str, object] | None],
    merchant_recommendation: Callable[..., str],
) -> HouseholdReports:
    today = date.today()
    current_rows = [row for row in report_rows if _is_current_transaction(row, today=today)]
    collapsed_rows = collapse_report_rows(current_rows)
    analytics_source_rows = [
        row for row in current_rows if row.get("source_kind") != "import"
    ]
    analytics_rows = [
        row
        for row in collapse_report_rows(analytics_source_rows)
        if row["amount"] > 0
    ]
    if not analytics_rows:
        return HouseholdReports(
            executive=HouseholdExecutiveReport(
                headline="Jenny needs more transaction evidence to build a cash-flow report.",
                summary="Upload recent statements and receipts so the transaction ledger can estimate real household spending.",
                average_monthly_spend=0.0,
                average_monthly_essentials=0.0,
                average_monthly_discretionary=0.0,
                recent_30_day_spend=0.0,
                recurring_merchant_count=0,
                tracked_expense_count=0,
                coverage_months=0,
            ),
            price_insights=_build_price_insights(expense_rows=collapsed_rows),
        )

    monthly_totals: dict[str, float] = {}
    monthly_counts: dict[str, int] = {}
    recent_cutoff = today.toordinal() - 30

    for row in analytics_rows:
        month_key = row["date"].strftime("%Y-%m")
        monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + row["amount"]
        monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

    recent_month_keys = sorted(monthly_totals.keys())[-_EXECUTIVE_WINDOW_MONTHS:]
    recent_month_set = set(recent_month_keys)
    recent_rows = [
        row
        for row in analytics_rows
        if row["date"].strftime("%Y-%m") in recent_month_set
    ]
    category_totals: dict[tuple[str, str], float] = {}
    merchant_totals: dict[str, dict[str, Any]] = {}

    for row in recent_rows:
        category_key = (row["category"], row["essentiality"])
        category_totals[category_key] = category_totals.get(category_key, 0.0) + row["amount"]
        merchant_state = merchant_totals.setdefault(
            row["merchant"],
            {"amount": 0.0, "count": 0, "category": row["category"], "dates": []},
        )
        merchant_state["amount"] += row["amount"]
        merchant_state["count"] += 1
        merchant_state["dates"].append(row["date"])

    coverage_months = max(len(recent_month_keys), 1)
    total_spend = sum(monthly_totals[month_key] for month_key in recent_month_keys)
    essential_spend = sum(
        amount for (_, essentiality), amount in category_totals.items() if essentiality == "essential"
    )
    discretionary_spend = sum(
        amount for (_, essentiality), amount in category_totals.items() if essentiality == "discretionary"
    )
    recent_30_day_spend = sum(
        row["amount"] for row in recent_rows if row["date"].toordinal() >= recent_cutoff
    )
    recurring_merchant_count = sum(
        1
        for state in merchant_totals.values()
        if (cadence_for_dates(state["dates"]) or {}).get("label", "one-off") != "one-off"
    )

    executive = HouseholdExecutiveReport(
        headline="Jenny now has a real household spending ledger to work from.",
        summary=(
            f"Average monthly spend is ${total_spend / coverage_months:,.0f} across "
            f"{coverage_months} recent tracked month{'s' if coverage_months != 1 else ''}, "
            f"with {recurring_merchant_count} recurring merchant patterns already visible."
        ),
        average_monthly_spend=round(total_spend / coverage_months, 2),
        average_monthly_essentials=round(essential_spend / coverage_months, 2),
        average_monthly_discretionary=round(discretionary_spend / coverage_months, 2),
        recent_30_day_spend=round(recent_30_day_spend, 2),
        recurring_merchant_count=recurring_merchant_count,
        tracked_expense_count=len(recent_rows),
        coverage_months=coverage_months,
    )

    category_breakdown = [
        HouseholdCategoryBreakdown(
            category=category,
            essentiality=essentiality,
            monthly_average=round(amount / coverage_months, 2),
            share_of_spend=round(amount / total_spend if total_spend > 0 else 0.0, 4),
            total_spend=round(amount, 2),
        )
        for (category, essentiality), amount in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )[:6]
    ]

    merchant_highlights = []
    for merchant, state in sorted(merchant_totals.items(), key=lambda item: item[1]["amount"], reverse=True)[:6]:
        cadence_data = cadence_for_dates(state["dates"])
        cadence = str(cadence_data["label"]) if cadence_data else "one-off"
        merchant_highlights.append(
            HouseholdMerchantInsight(
                merchant=merchant,
                total_spend=round(state["amount"], 2),
                average_ticket=round(state["amount"] / state["count"], 2),
                transaction_count=state["count"],
                cadence=cadence,
                category=str(state["category"]),
                recommendation=merchant_recommendation(
                    merchant=merchant,
                    category=str(state["category"]),
                    cadence=cadence,
                ),
            )
        )

    monthly_spend_trend = [
        HouseholdMonthlyTrendPoint(
            month=month,
            total_spend=round(monthly_totals[month], 2),
            transaction_count=monthly_counts[month],
        )
        for month in recent_month_keys
    ]

    recent_transactions = [
        HouseholdRecentTransaction(
            date=row["date"].isoformat(),
            merchant=row["merchant"],
            description=row["description"],
            amount=round(row["amount"], 2),
            category=row["category"],
            essentiality=row["essentiality"],
            account_label=row["account_label"],
            source_document_id=row["document_id"],
        )
        for row in sorted(recent_rows, key=lambda item: item["date"], reverse=True)[:10]
    ]

    return HouseholdReports(
        executive=executive,
        category_breakdown=category_breakdown,
        merchant_highlights=merchant_highlights,
        price_insights=_build_price_insights(expense_rows=collapsed_rows),
        monthly_spend_trend=monthly_spend_trend,
        recent_transactions=recent_transactions,
    )
