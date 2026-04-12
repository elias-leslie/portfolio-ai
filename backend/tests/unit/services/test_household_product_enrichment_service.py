"""Unit tests for household product enrichment service."""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from app.services.household_product_enrichment_service import (
    HouseholdProductEnrichmentService,
)


class _EnrichmentConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, list[Any] | None]] = []
        self.committed = False

    def execute(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> SimpleNamespace:
        self.executed.append((sql, params))
        if "SELECT id, dataset_type, merchant, description, row_metadata" in sql:
            return SimpleNamespace(fetchall=lambda: self.rows)
        return SimpleNamespace(fetchall=lambda: [])

    def commit(self) -> None:
        self.committed = True


class _EnrichmentStorage:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.conn = _EnrichmentConnection(rows)

    @contextmanager
    def connection(self):
        yield self.conn


def test_enrich_import_rows_caches_local_package_measure_without_external_lookup() -> None:
    service = HouseholdProductEnrichmentService()
    fake_service = SimpleNamespace(
        storage=_EnrichmentStorage(
            [
                (
                    "row-1",
                    "amazon_order_history",
                    "Amazon",
                    "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                    {
                        "ASIN": "B00CMQD3VS",
                        "Product Name": "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                        "Unit Price": "14.26",
                    },
                )
            ]
        )
    )

    summary = service.enrich_import_rows(fake_service, dataset_type="amazon_order_history")

    assert summary["updated"] == 1
    assert summary["local_matches"] == 1
    assert summary["external_hits"] == 0
    update_params = fake_service.storage.conn.executed[-1][1]
    assert update_params is not None
    payload = json.loads(update_params[0])
    assert payload["product_enrichment"]["package_measure"]["display_label"] == "32 oz"
    assert payload["product_enrichment"]["identifiers"]["asin"] == "B00CMQD3VS"
    assert fake_service.storage.conn.committed is True


def test_enrich_import_rows_merges_open_food_facts_metadata_for_barcodes(monkeypatch) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "status": 1,
                "product": {
                    "product_name": "Organic Apples",
                    "quantity": "2 lb",
                    "brands": "Example Farms",
                    "categories_tags": ["en:fruits"],
                    "image_url": "https://example.test/apple.png",
                },
            }

    def _fake_get(*args: Any, **kwargs: Any) -> _Response:
        del args, kwargs
        return _Response()

    monkeypatch.setattr(
        "app.services.household_product_enrichment_service.requests.get",
        _fake_get,
    )

    service = HouseholdProductEnrichmentService()
    fake_service = SimpleNamespace(
        storage=_EnrichmentStorage(
            [
                (
                    "row-2",
                    "walmart_receipt",
                    "Walmart",
                    "Organic apples",
                    {
                        "Product Name": "Organic apples",
                        "UPC": "012345678905",
                    },
                )
            ]
        )
    )

    summary = service.enrich_import_rows(fake_service, dataset_type="walmart_receipt")

    assert summary["updated"] == 1
    assert summary["external_hits"] == 1
    update_params = fake_service.storage.conn.executed[-1][1]
    assert update_params is not None
    payload = json.loads(update_params[0])
    assert payload["product_enrichment"]["identifiers"]["barcode"] == "012345678905"
    assert payload["product_enrichment"]["open_food_facts"]["product_name"] == "Organic Apples"
    assert payload["product_enrichment"]["package_measure"]["display_label"] == "2 lb"
