from __future__ import annotations

from app.services import household_property_valuation_service as valuation_service


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
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


def test_address_candidates_keep_searchable_street_line_first() -> None:
    assert valuation_service._address_search_candidates(
        "3636 Avocado Road, Largo, Florida 33770"
    )[:2] == [
        "3636 Avocado Road",
        "3636 Avocado Road, Largo, Florida 33770",
    ]


def test_resolve_pinellas_property_uses_hidden_parcel_strap_not_checkbox_value() -> None:
    service = valuation_service.HouseholdPropertyValuationService()
    resolved = service._resolve_pinellas_property(
        _FakeClient(),
        "3636 Avocado Road, Largo, Florida 33770",
    )

    assert resolved.strap == "153005359820060080"
    assert resolved.parcel_number == "05-30-15-35982-006-0080"
    assert resolved.site_address == "3636 AVOCADO RD"


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
