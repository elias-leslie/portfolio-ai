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


def _quote(product_id: str, vendor_key: str, price: float):
    return {
        "product_id": product_id,
        "vendor_key": vendor_key,
        "total_price": price,
        "unit_price": None,
        "is_fresh": True,
    }


def _profile(vendor_key: str, fee: float = 0.0):
    return {
        "vendor_key": vendor_key,
        "display_name": vendor_key.title(),
        "enabled": True,
        "delivery_fee": fee,
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
