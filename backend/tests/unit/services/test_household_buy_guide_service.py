from __future__ import annotations

from datetime import date

from app.services.household_buy_guide_service import _guide_item, _monthly_units, _Observation


def _obs(
    *,
    observed: date,
    total: float,
    qty: float,
    merchant: str = "Amazon",
    source: str = "order_history",
    label: str = "10 oz",
    metadata: dict[str, object] | None = None,
) -> _Observation:
    return _Observation(
        product_id="product-olive-oil",
        product_name="Olive Oil",
        brand=None,
        merchant=merchant,
        observed_date=observed,
        total_price=total,
        package_label=label,
        package_quantity=qty,
        package_unit="weight_oz",
        source=source,
        metadata=metadata or {},
    )


def test_buy_guide_flags_larger_vendor_quote_unit_savings() -> None:
    today = date(2026, 6, 19)
    item = _guide_item(
        product_id="product-olive-oil",
        observations=[
            _obs(observed=date(2026, 4, 1), total=9.50, qty=10),
            _obs(observed=date(2026, 5, 1), total=10.00, qty=10),
            _obs(
                observed=date(2026, 6, 18),
                total=24.00,
                qty=40,
                merchant="Walmart",
                source="vendor_quote",
                label="40 oz",
                metadata={"url": "https://example.test/oil", **_CONFIRMED},
            ),
        ],
        today=today,
    )

    assert item is not None
    assert item.finding_kind == "buy_bigger_elsewhere"
    assert item.current_unit_cost == 1.0
    assert item.best_unit_cost == 0.6
    assert item.savings_pct == 40.0
    assert item.best_url == "https://example.test/oil"
    assert item.months_to_use is not None


def test_buy_guide_ignores_stale_historical_bulk_prices() -> None:
    today = date(2026, 6, 19)
    item = _guide_item(
        product_id="product-olive-oil",
        observations=[
            _obs(observed=date(2026, 4, 1), total=9.50, qty=10),
            _obs(observed=date(2026, 5, 1), total=10.00, qty=10),
            _obs(observed=date(2020, 1, 1), total=12.00, qty=40, label="40 oz"),
        ],
        today=today,
    )

    assert item is None


def test_buy_guide_ignores_low_confidence_vendor_quotes() -> None:
    today = date(2026, 6, 19)
    item = _guide_item(
        product_id="product-olive-oil",
        observations=[
            _obs(observed=date(2026, 4, 1), total=9.50, qty=10),
            _obs(observed=date(2026, 5, 1), total=10.00, qty=10),
            _obs(
                observed=date(2026, 6, 18),
                total=16.59,
                qty=68,
                merchant="Publix",
                source="vendor_quote",
                label="68 oz",
                metadata={"url": "https://example.test/oil", "confidence": 0.58},
            ),
        ],
        today=today,
    )

    assert item is None


def test_meaningful_dollars_are_not_rejected_by_a_ten_percent_threshold():
    item = _guide_item(
        product_id="product-olive-oil",
        today=date(2026, 6, 19),
        observations=[
            _obs(observed=date(2026, 4, 1), total=32, qty=32, label="32 oz"),
            _obs(observed=date(2026, 5, 1), total=32, qty=32, label="32 oz"),
            _obs(
                observed=date(2026, 6, 18),
                total=60,
                qty=64,
                label="64 oz",
                merchant="Walmart",
                source="vendor_quote",
                metadata=_CONFIRMED,
            ),
        ],
    )
    assert item and item.savings_pct == 6.2
    assert item.estimated_monthly_savings and 1 < item.estimated_monthly_savings < 3


def test_two_purchases_do_not_double_the_observed_restocking_pace():
    pace = _monthly_units(
        [
            _obs(observed=date(2026, 4, 1), total=32, qty=32),
            _obs(observed=date(2026, 5, 1), total=32, qty=32),
        ],
        today=date(2026, 6, 1),
    )
    assert pace and 32 < pace < 33


_CONFIRMED: dict[str, object] = dict.fromkeys(
    (
        "equivalence_confirmed",
        "availability_confirmed",
        "fees_confirmed",
        "coupon_confirmed",
        "membership_confirmed",
    ),
    True,
)

_CONFIRMED["valid_until"] = "2026-07-01"


def test_same_store_offer_is_useful_but_a_coupon_is_not_recurring_savings():
    item = _guide_item(
        product_id="product-olive-oil",
        today=date(2026, 6, 19),
        observations=[
            _obs(observed=date(2026, 4, 1), total=32, qty=32),
            _obs(observed=date(2026, 5, 1), total=32, qty=32),
            _obs(
                observed=date(2026, 6, 18),
                total=28,
                qty=32,
                source="vendor_quote",
                metadata={**_CONFIRMED, "coupon": 4},
            ),
        ],
    )
    assert item and item.finding_kind == "lower_price_same_store"
    assert item.estimated_monthly_savings is None


def test_offer_expiry_overrides_the_fourteen_day_freshness_window():
    item = _guide_item(
        product_id="product-olive-oil",
        today=date(2026, 6, 19),
        observations=[
            _obs(observed=date(2026, 4, 1), total=32, qty=32),
            _obs(observed=date(2026, 5, 1), total=32, qty=32),
            _obs(
                observed=date(2026, 6, 18),
                total=20,
                qty=32,
                source="vendor_quote",
                metadata={**_CONFIRMED, "valid_until": "2026-06-18"},
            ),
        ],
    )
    assert item is None
