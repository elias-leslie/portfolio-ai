"""Unit tests for shopping-list basket optimization math."""

from __future__ import annotations

from app.services._shopping_list_optimizer import optimize_shopping_list


def _item(item_id: str, product_id: str, quantity: float = 1.0, confidence: float = 1.0):
    return {
        "id": item_id,
        "product_id": product_id,
        "product_name": item_id,
        "quantity": quantity,
        "status": "open",
        "match_confidence": confidence,
    }


def _quote(
    product_id: str,
    vendor_key: str,
    price: float,
    *,
    unit_price: float | None = None,
    comparison_price: float | None = None,
    package_label: str | None = None,
    unit_label: str | None = None,
):
    return {
        "product_id": product_id,
        "vendor_key": vendor_key,
        "total_price": price,
        "unit_price": unit_price,
        "comparison_price": comparison_price,
        "package_label": package_label,
        "unit_label": unit_label,
        "is_fresh": True,
    }


def _profile(vendor_key: str, fee: float = 0.0, *, is_local_store: bool | None = None):
    return {
        "vendor_key": vendor_key,
        "display_name": vendor_key.title(),
        "enabled": True,
        "delivery_fee": fee,
        **({} if is_local_store is None else {"is_local_store": is_local_store}),
    }


def test_split_recommendation_requires_material_savings() -> None:
    result = optimize_shopping_list(
        [_item("eggs", "p-1"), _item("milk", "p-2")],
        [
            _quote("p-1", "amazon", 10.0),
            _quote("p-2", "amazon", 10.0),
            _quote("p-1", "walmart", 6.0),
            _quote("p-2", "publix", 6.0),
        ],
        [_profile("amazon"), _profile("walmart"), _profile("publix")],
    )

    assert result["best_single_vendor"]["vendor_key"] == "amazon"
    assert result["split_recommendation"]["total"] == 12.0
    assert result["split_recommendation"]["savings"] == 8.0
    assert result["split_recommendation"]["recommended"] is True


def test_small_split_savings_are_not_recommended() -> None:
    result = optimize_shopping_list(
        [_item("eggs", "p-1"), _item("milk", "p-2")],
        [
            _quote("p-1", "amazon", 10.0),
            _quote("p-2", "amazon", 10.0),
            _quote("p-1", "walmart", 9.0),
            _quote("p-2", "publix", 9.0),
        ],
        [_profile("amazon"), _profile("walmart"), _profile("publix")],
    )

    assert result["split_recommendation"]["savings"] == 2.0
    assert result["split_recommendation"]["threshold"] == 8.0
    assert result["split_recommendation"]["recommended"] is False


def test_fees_and_substitution_flags_are_included() -> None:
    result = optimize_shopping_list(
        [_item("edamame", "p-1", quantity=2, confidence=0.7)],
        [_quote("p-1", "walmart", 3.0)],
        [_profile("walmart", fee=5.0)],
    )

    basket = result["vendor_baskets"][0]
    assert basket["subtotal"] == 6.0
    assert basket["fees"] == 5.0
    assert basket["total"] == 11.0
    assert result["split_recommendation"]["assignments"][0]["substitution_flag"] is True


def test_max_local_stores_limits_split_assignments() -> None:
    result = optimize_shopping_list(
        [_item("oil", "p-1"), _item("nuts", "p-2"), _item("yogurt", "p-3")],
        [
            _quote("p-1", "amazon", 10.0),
            _quote("p-2", "amazon", 10.0),
            _quote("p-3", "amazon", 10.0),
            _quote("p-1", "walmart", 5.0),
            _quote("p-2", "publix", 5.0),
            _quote("p-3", "aldi", 5.0),
        ],
        [
            _profile("amazon", is_local_store=False),
            _profile("walmart", is_local_store=True),
            _profile("publix", is_local_store=True),
            _profile("aldi", is_local_store=True),
        ],
        max_local_stores=1,
    )

    split = result["split_recommendation"]
    local_vendors = {
        assignment["vendor_key"]
        for assignment in split["assignments"]
        if assignment["vendor_key"] != "amazon"
    }
    assert split["local_store_count"] == 1
    assert len(local_vendors) == 1
    assert split["total"] == 25.0
    assert split["recommended"] is False


def test_unit_basis_can_pick_larger_package_without_losing_sticker_price() -> None:
    result = optimize_shopping_list(
        [_item("olive oil", "oil")],
        [
            _quote(
                "oil",
                "walmart",
                21.48,
                unit_price=0.3159,
                comparison_price=31.91,
                package_label="68 fl oz",
                unit_label="fl oz",
            ),
            _quote(
                "oil",
                "amazon",
                26.38,
                unit_price=0.2612,
                comparison_price=26.38,
                package_label="101 fl oz",
                unit_label="fl oz",
            ),
        ],
        [_profile("amazon", is_local_store=False), _profile("walmart", is_local_store=True)],
    )

    assignment = result["split_recommendation"]["assignments"][0]
    assert assignment["vendor_key"] == "amazon"
    assert assignment["price"] == 26.38
    assert assignment["sticker_price"] == 26.38
    assert assignment["unit_price"] == 0.2612
    assert assignment["unit_label"] == "fl oz"
