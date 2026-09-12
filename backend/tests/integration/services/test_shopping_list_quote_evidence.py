"""Only confirmed, comparable and still-valid shelf evidence can price a basket."""

import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

from app.services._household_price_location import shopping_today
from app.services._shopping_list_optimizer import optimize_shopping_list
from app.services._shopping_list_quotes import confirmed_list_quotes, validate_saved_estimate
from app.storage import get_storage


def test_basket_quotes_preserve_package_price_conditions_and_revocation():
    pid = str(uuid.uuid4())
    today = shopping_today()
    item = SimpleNamespace(product_id=pid, quantity=1, unit=None, match_confidence=1)
    metadata = {
        "confirmed_by": "test-adult",
        "vendor_key": "walmart",
        "title": "Olive oil",
        "availability_confirmed": True,
        "equivalence_confirmed": True,
        "fees_confirmed": True,
        "coupon_confirmed": True,
        "membership_confirmed": True,
        "valid_until": str(today + timedelta(days=7)),
        "fees": 5,
        "coupon": 0,
    }
    with get_storage().connection() as conn:
        conn.execute(
            "INSERT INTO household_products (id,canonical_name) VALUES (%s,'Olive oil 68 fl oz')",
            [pid],
        )
        conn.execute(
            "INSERT INTO household_product_price_observations (id,product_id,observed_date,total_price,quantity,source) VALUES (%s,%s,%s,40,2,'receipt')",
            [str(uuid.uuid4()), pid, today],
        )
        offer_id = str(uuid.uuid4())
        for oid, label, price, meta in (
            (offer_id, "68 fl oz", 25, metadata),
            (str(uuid.uuid4()), "34 fl oz", 3, metadata),
            (str(uuid.uuid4()), "68 fl oz", 1, {"confidence": 0.99}),
            (
                str(uuid.uuid4()),
                "68 fl oz",
                2,
                {**metadata, "valid_until": str(today - timedelta(days=1))},
            ),
        ):
            conn.execute(
                "INSERT INTO household_product_price_observations (id,product_id,observed_date,total_price,quantity,source,package_display_label,metadata) VALUES (%s,%s,%s,%s,1,'vendor_quote',%s,%s::jsonb)",
                [oid, pid, today, price, label, json.dumps(meta)],
            )
        conn.commit()
        quotes = confirmed_list_quotes(conn, [item])
        assert len(quotes) == 1 and quotes[0]["observation_id"] == offer_id
        assert quotes[0]["total_price"] == 25
        result = optimize_shopping_list(
            [{"id": "item", "product_id": pid, "quantity": 1}],
            quotes,
            [{"vendor_key": "walmart", "delivery_fee": 5}],
        )
        assert result["best_single_vendor"]["total"] == 25  # Confirmed fees are not charged twice.
        saved = (
            "list",
            "Test",
            "active",
            {
                "evidence_version": 2,
                "quote_evidence": {offer_id: quotes[0]["evidence_fingerprint"]},
            },
            None,
            None,
        )
        assert validate_saved_estimate(conn, saved)[3]
        item.quantity = 2
        assert confirmed_list_quotes(conn, [item]) == []  # Fee/coupon reuse is not established.
        item.quantity = 1
        item.unit = "litres"
        assert confirmed_list_quotes(conn, [item]) == []  # No silent packages-to-litres conversion.
        conn.execute(
            "UPDATE household_product_price_observations SET metadata=metadata || '{\"availability_confirmed\":false}'::jsonb WHERE id=%s",
            [offer_id],
        )
        assert validate_saved_estimate(conn, saved)[3] is None
        assert (
            validate_saved_estimate(
                conn, ("old", "Old", "active", {"best_single_vendor": {"total": 1}}, None, None)
            )[3]
            is None
        )
