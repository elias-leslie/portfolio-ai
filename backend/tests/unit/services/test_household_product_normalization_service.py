"""Unit tests for the product normalization ladder."""

from __future__ import annotations

from typing import Any

from app.services.household_product_normalization_service import (
    HouseholdProductNormalizationService,
)


class _Conn:
    """Routes the normalization service's SQL by distinctive substrings."""

    def __init__(
        self,
        *,
        identifier_hits: dict[tuple[str, str], str] | None = None,
        key_hit: tuple[str, str | None] | None = None,
    ) -> None:
        self.identifier_hits = identifier_hits or {}
        self.key_hit = key_hit
        self.product_inserts: list[list[Any]] = []
        self.identifier_inserts: list[list[Any]] = []
        self._result: Any = None

    def execute(self, sql: str, params: list[Any] | None = None) -> _Conn:
        params = params or []
        if "JOIN household_products p" in sql:
            self._result = self.key_hit
        elif "FROM household_product_identifiers" in sql:
            product_id = self.identifier_hits.get((str(params[0]), str(params[1])))
            self._result = (product_id,) if product_id else None
        elif "INSERT INTO household_products" in sql:
            self.product_inserts.append(params)
            self._result = None
        elif "INSERT INTO household_product_identifiers" in sql:
            self.identifier_inserts.append(params)
            self._result = None
        else:
            self._result = None
        return self

    def fetchone(self) -> Any:
        return self._result

    def fetchall(self) -> list[Any]:
        return []


_ENRICHMENT = {
    "identifiers": {"asin": "B00AQ664H6"},
    "normalized_item_key": "amazon freekey system",
    "package_measure": None,
    "open_food_facts": None,
}


def test_identifier_exact_hit_matches_with_high_confidence() -> None:
    conn = _Conn(identifier_hits={("asin", "B00AQ664H6"): "prod-1"})
    match = HouseholdProductNormalizationService().match_or_create_product(
        conn, merchant="Amazon", item_name="FreeKey System", enrichment=_ENRICHMENT
    )
    assert (match.product_id, match.status, match.created) == ("prod-1", "auto", False)
    assert match.confidence == 0.98
    # The variant's normalized key is attached to the matched product.
    assert any(params[2] == "normalized_key" for params in conn.identifier_inserts)


def test_normalized_key_hit_with_compatible_units_is_auto() -> None:
    enrichment = {
        "normalized_item_key": "amazon freekey system",
        "package_measure": {"normalized_unit": "count", "normalized_quantity": 12},
    }
    conn = _Conn(key_hit=("prod-2", "count"))
    match = HouseholdProductNormalizationService().match_or_create_product(
        conn, merchant="Amazon", item_name="FreeKey System", enrichment=enrichment
    )
    assert (match.product_id, match.status) == ("prod-2", "auto")
    assert match.confidence == 0.85


def test_normalized_key_hit_with_incompatible_units_needs_review() -> None:
    enrichment = {
        "normalized_item_key": "amazon freekey system",
        "package_measure": {"normalized_unit": "weight_oz", "normalized_quantity": 16},
    }
    conn = _Conn(key_hit=("prod-3", "volume_fl_oz"))
    match = HouseholdProductNormalizationService().match_or_create_product(
        conn, merchant="Amazon", item_name="FreeKey System", enrichment=enrichment
    )
    assert (match.product_id, match.status) == ("prod-3", "needs_review")
    assert match.confidence == 0.7


def test_no_hit_creates_product_with_identifiers() -> None:
    conn = _Conn()
    enrichment = {
        **_ENRICHMENT,
        "package_measure": {
            "display_label": "2 x 12 fl oz",
            "normalized_quantity": 24.0,
            "normalized_unit": "volume_fl_oz",
        },
        "open_food_facts": {"brands": "FreeKey", "image_url": "https://img.example/x.jpg"},
    }
    match = HouseholdProductNormalizationService().match_or_create_product(
        conn, merchant="Amazon", item_name="FreeKey System", enrichment=enrichment
    )
    assert match.created is True
    assert match.status == "auto"
    assert len(conn.product_inserts) == 1
    insert = conn.product_inserts[0]
    assert insert[1] == "FreeKey System"
    assert insert[2] == "FreeKey"
    assert insert[3] == "2 x 12 fl oz"
    kinds = {params[2] for params in conn.identifier_inserts}
    assert kinds == {"asin", "normalized_key"}
