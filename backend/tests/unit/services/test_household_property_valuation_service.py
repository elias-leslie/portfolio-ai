from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.services import household_property_valuation_service as valuation_service


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class _FakeClient:
    def post(self, path: str, data: dict[str, object]) -> _FakeResponse:
        assert path == "/dal/quicksearch/searchProperty"
        return _FakeResponse(
            {
                "data": [
                    [
                        '<input value="1"><input id="select_strap_1" value="153005359820060080">',
                        "",
                        "Owner",
                        "",
                        "<a>05-30-15-35982-006-0080</a>",
                        "3636 AVOCADO RD",
                        "BTF",
                        "0110 Single Family Home",
                    ]
                ]
            }
        )


class _FakeHillsboroughClient:
    def __enter__(self) -> _FakeHillsboroughClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get(self, path: str, params: dict[str, Any]) -> _FakeResponse:
        if path.endswith("/BasicSearch"):
            assert params["address"] == "5904 N Lynn Ave"
            return _FakeResponse(
                [
                    {
                        "address": "5904 N LYNN AVE, TAMPA",
                        "displayFolio": "162350-0000",
                        "displayPin": "A-36-28-18-4EK-000017-00005.1",
                        "folio": "1623500000",
                        "landUse": "0100",
                        "owner": "PALMER REBECCA S LIFE ESTATE",
                        "pin": "1828364EK000017000051A",
                    }
                ]
            )
        assert path.endswith("/ParcelData")
        assert params["pin"] == "1828364EK000017000051A"
        return _FakeResponse(
            {
                "acreage": 0.31,
                "buildings": [
                    {
                        "bathrooms": 2,
                        "bedrooms": 2,
                        "grossArea": 1548,
                        "heatedArea": 1404,
                        "yearBuilt": 1963,
                    }
                ],
                "landUse": {"code": "0100", "description": "SINGLE FAMILY R"},
                "propertyCard": {
                    "displayFolio": "162350-0000",
                    "current": {"buildings": 165379, "extraFeatures": 8445, "land": 177660},
                },
                "valueSummary": [
                    {"marketVal": 351484, "taxDist": "Municipal"},
                    {"marketVal": 351484, "taxDist": "Public Schools"},
                ],
            }
        )


def test_address_candidates_keep_searchable_street_line_first() -> None:
    assert valuation_service._address_search_candidates(
        "3636 Avocado Road, Largo, Florida 33770"
    )[:2] == [
        "3636 Avocado Road",
        "3636 Avocado Road, Largo, Florida 33770",
    ]


def test_address_candidates_include_hashless_unit_before_broad_fallback() -> None:
    candidates = valuation_service._address_search_candidates(
        "2944 West Bay Dr #303, Belleair Bluffs, FL"
    )

    assert candidates.index("2944 West Bay Dr 303") < candidates.index("2944 West Bay")


def test_resolve_pinellas_property_uses_hidden_parcel_strap_not_checkbox_value() -> None:
    service = valuation_service.HouseholdPropertyValuationService()
    resolved = service._resolve_pinellas_property(
        _FakeClient(),
        "3636 Avocado Road, Largo, Florida 33770",
    )

    assert resolved.strap == "153005359820060080"
    assert resolved.parcel_number == "05-30-15-35982-006-0080"
    assert resolved.site_address == "3636 AVOCADO RD"


def test_fetch_hillsborough_valuation_uses_county_market_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = valuation_service.HouseholdPropertyValuationService()
    monkeypatch.setattr(
        service,
        "_hillsborough_client",
        _FakeHillsboroughClient,
    )

    estimate = service._fetch_hillsborough_valuation(
        "5904 N Lynn Ave, Tampa, Florida 33604",
        now=datetime(2026, 6, 16, tzinfo=UTC),
    )

    assert estimate.source == "hillsborough_county_just_market"
    assert estimate.estimate_value == 351_484
    assert estimate.metadata["pin"] == "1828364EK000017000051A"
    assert estimate.metadata["livingSqft"] == 1404


def test_estimate_from_sales_uses_median_price_per_sqft_and_iqr_range() -> None:
    service = valuation_service.HouseholdPropertyValuationService()
    estimate = service._estimate_from_sales(
        1_785,
        [
            valuation_service._ComparableSale(
                "A", 0.1, "01/01/2026", 400_000, 1_600, 250
            ),
            valuation_service._ComparableSale(
                "B", 0.2, "01/02/2026", 450_000, 1_800, 300
            ),
            valuation_service._ComparableSale(
                "C", 0.3, "01/03/2026", 800_000, 2_000, 400
            ),
        ],
    )

    assert estimate.estimate_value == 535_500
    assert estimate.range_low == 490_875
    assert estimate.range_high == 624_750
    assert estimate.source == "pinellas_county_comps"
