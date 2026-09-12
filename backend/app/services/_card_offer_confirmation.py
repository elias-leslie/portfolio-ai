"""Apply an exact offer preview only when its card is explicitly added."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.models.credit_cards import CreditCardCreate, CreditCardProduct
from app.services.card_terms_review_service import fingerprint

WELCOME_FIELDS = ("welcome_bonus_points", "welcome_bonus_cash", "welcome_min_spend", "welcome_window_days")


def confirm_offer(conn: Any, req: CreditCardCreate) -> dict[str, object] | None:
    if not req.source_document_id:
        return None
    row = conn.execute("SELECT metadata FROM household_documents WHERE id=%s FOR UPDATE", [req.source_document_id]).fetchone()
    metadata = row[0] if row and isinstance(row[0], dict) else {}
    staged = metadata.get("card_offer")
    if not isinstance(staged, dict) or not req.offer_fingerprint or fingerprint(staged) != req.offer_fingerprint:
        raise ValueError("The offer preview changed. Extract and check the terms again.")
    product = CreditCardProduct.model_validate(staged)
    if product.id != req.product_id:
        raise ValueError("The selected card does not match the offer preview.")
    # A targeted offer belongs to this owned card. Never overwrite an existing
    # public catalog product with its personalized bonus or fees.
    exists = conn.execute("SELECT id FROM credit_card_products WHERE id=%s", [product.id]).fetchone()
    if exists is None:
        conflict = conn.execute("SELECT id FROM credit_card_products WHERE slug=%s", [product.slug]).fetchone()
        if conflict:
            raise ValueError("This product was added since extraction. Select it from the catalog and review the offer again.")
        conn.execute("""INSERT INTO credit_card_products
            (id,slug,issuer,product_name,annual_fee,reward_multipliers,point_program,
             est_point_value_cents,source,source_document_id,issuer_rules)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,'intake',%s,%s::jsonb)""",
            [product.id, product.slug, product.issuer, product.product_name, product.annual_fee,
             json.dumps(product.reward_multipliers), product.point_program, product.est_point_value_cents,
             req.source_document_id, json.dumps({"welcome_offer_unverified": True})])
    conn.execute("UPDATE household_documents SET review_status='complete', status='parsed', metadata=metadata || %s::jsonb WHERE id=%s",
                 [json.dumps({"card_offer_confirmed_at": datetime.now(UTC).isoformat()}), req.source_document_id])
    return {**{key: staged[key] for key in WELCOME_FIELDS}, "annual_fee": product.annual_fee,
            "source_document_id": req.source_document_id, "confirmed_at": datetime.now(UTC).isoformat()}
