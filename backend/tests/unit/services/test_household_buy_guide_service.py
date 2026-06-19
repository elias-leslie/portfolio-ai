from __future__ import annotations

from datetime import date

from app.services.household_buy_guide_service import _guide_item, _Observation


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
                metadata={"url": "https://example.test/oil", "confidence": 0.9},
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
