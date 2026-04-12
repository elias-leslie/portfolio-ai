"""Product metadata enrichment for imported household purchase rows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import requests

from app.logging_config import get_logger
from app.services._household_report_builder import (
    _coerce_metadata,
    _extract_package_measure,
    _normalized_item_key,
)

logger = get_logger(__name__)

_OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
_OPEN_FOOD_FACTS_FIELDS = (
    "code,product_name,quantity,product_quantity,product_quantity_unit,brands,categories_tags,image_url"
)
_OPEN_FOOD_FACTS_TIMEOUT = 4.0
_OPEN_FOOD_FACTS_HEADERS = {
    "User-Agent": "portfolio-ai household-money-enrichment/1.0",
}
_BARCODE_KEYS = (
    "UPC",
    "UPC Code",
    "EAN",
    "GTIN",
    "Barcode",
    "Bar Code",
    "Product Code",
)


def _normalize_barcode(value: Any) -> str | None:
    if value in (None, ""):
        return None
    digits = re.sub(r"\D+", "", str(value))
    return digits if 8 <= len(digits) <= 14 else None


def _extract_identifiers(metadata: dict[str, Any]) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    asin = str(metadata.get("ASIN") or "").strip()
    if asin:
        identifiers["asin"] = asin
    for key in _BARCODE_KEYS:
        barcode = _normalize_barcode(metadata.get(key))
        if barcode:
            identifiers["barcode"] = barcode
            break
    return identifiers


def _package_measure_payload(description: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
    measure = _extract_package_measure(description, metadata)
    if measure is None:
        return None
    return {
        "display_label": measure.display_label,
        "normalized_quantity": measure.normalized_quantity,
        "normalized_unit": measure.normalized_unit,
        "raw_quantity": measure.raw_quantity,
        "raw_unit": measure.raw_unit,
    }


def _open_food_facts_package_measure(product: dict[str, Any]) -> dict[str, Any] | None:
    quantity_text = str(product.get("quantity") or "").strip()
    if quantity_text:
        payload = _package_measure_payload(quantity_text, {"Product Name": quantity_text})
        if payload is not None:
            return payload
    quantity_value = product.get("product_quantity")
    quantity_unit = str(product.get("product_quantity_unit") or "").strip()
    if quantity_value and quantity_unit:
        payload = _package_measure_payload(
            f"{quantity_value} {quantity_unit}",
            {"Product Name": f"{quantity_value} {quantity_unit}"},
        )
        if payload is not None:
            return payload
    return None


class HouseholdProductEnrichmentService:
    """Fetch and cache extra product metadata for imported household rows."""

    def _fetch_open_food_facts(self, barcode: str) -> dict[str, Any] | None:
        try:
            response = requests.get(
                _OPEN_FOOD_FACTS_URL.format(code=barcode),
                params={"fields": _OPEN_FOOD_FACTS_FIELDS},
                headers=_OPEN_FOOD_FACTS_HEADERS,
                timeout=_OPEN_FOOD_FACTS_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.debug(
                "household_product_enrichment_open_food_facts_failed",
                barcode=barcode,
                error=str(exc),
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            return None
        if payload.get("status") != 1:
            return None
        product = payload.get("product")
        return product if isinstance(product, dict) else None

    def enrich_import_rows(
        self,
        service: Any,
        *,
        document_id: str | None = None,
        dataset_type: str | None = None,
        limit: int = 5000,
    ) -> dict[str, int]:
        sql = """
            SELECT id, dataset_type, merchant, description, row_metadata
            FROM household_import_rows
            WHERE 1=1
        """
        params: list[object] = []
        if document_id is not None:
            sql += " AND document_id = %s"
            params.append(document_id)
        if dataset_type is not None:
            sql += " AND dataset_type = %s"
            params.append(dataset_type)
        sql += " ORDER BY row_date DESC NULLS LAST LIMIT %s"
        params.append(limit)

        with service.storage.connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        updates: list[tuple[str, dict[str, Any]]] = []
        summary = {
            "scanned": 0,
            "updated": 0,
            "local_matches": 0,
            "external_hits": 0,
            "external_misses": 0,
        }

        for row_id, row_dataset_type, merchant, description, raw_metadata in rows:
            summary["scanned"] += 1
            metadata = _coerce_metadata(raw_metadata)
            existing = metadata.get("product_enrichment")
            existing_enrichment = existing if isinstance(existing, dict) else {}
            identifiers = _extract_identifiers(metadata)
            item_name = str(metadata.get("Product Name") or description or "").strip()
            if not item_name:
                continue

            package_measure = _package_measure_payload(item_name, metadata)
            if package_measure is not None:
                summary["local_matches"] += 1

            barcode = identifiers.get("barcode")
            existing_external = existing_enrichment.get("open_food_facts")
            existing_external_dict = existing_external if isinstance(existing_external, dict) else {}
            open_food_facts = existing_external_dict if existing_external_dict else None
            external_attempted = (
                isinstance(existing_enrichment.get("external_lookup"), dict)
                and existing_enrichment["external_lookup"].get("source") == "open_food_facts"
                and existing_enrichment["external_lookup"].get("barcode") == barcode
            )

            if barcode and not external_attempted:
                product = self._fetch_open_food_facts(barcode)
                if product is not None:
                    open_food_facts = {
                        "barcode": barcode,
                        "product_name": str(product.get("product_name") or "").strip() or None,
                        "quantity": str(product.get("quantity") or "").strip() or None,
                        "brands": str(product.get("brands") or "").strip() or None,
                        "categories_tags": product.get("categories_tags") if isinstance(product.get("categories_tags"), list) else [],
                        "image_url": str(product.get("image_url") or "").strip() or None,
                    }
                    summary["external_hits"] += 1
                    if package_measure is None:
                        package_measure = _open_food_facts_package_measure(product)
                else:
                    summary["external_misses"] += 1

            enrichment = {
                "version": 1,
                "dataset_type": str(row_dataset_type or ""),
                "merchant": str(merchant or ""),
                "item_name": item_name,
                "normalized_item_key": _normalized_item_key(str(merchant or ""), item_name),
                "identifiers": identifiers,
                "package_measure": package_measure,
                "open_food_facts": open_food_facts,
                "external_lookup": {
                    "source": "open_food_facts",
                    "barcode": barcode,
                    "attempted": bool(barcode),
                    "matched": bool(open_food_facts),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }

            if enrichment == existing_enrichment:
                continue

            updated_metadata = dict(metadata)
            updated_metadata["product_enrichment"] = enrichment
            updates.append((str(row_id), updated_metadata))

        if not updates:
            return summary

        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            for row_id, row_metadata in updates:
                conn.execute(
                    """
                    UPDATE household_import_rows
                    SET row_metadata = %s::jsonb,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    [json.dumps(row_metadata), now, row_id],
                )
            conn.commit()

        summary["updated"] = len(updates)
        return summary
