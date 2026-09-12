"""Stage research as proposals; apply only a reviewed, unchanged comparison."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.models.credit_cards import CreditCardProduct
from app.storage import get_storage

FIELDS = frozenset({
    "annual_fee", "reward_multipliers", "welcome_bonus_points", "welcome_bonus_cash",
    "welcome_min_spend", "welcome_window_days", "transfer_partners", "credits", "issuer_rules",
})
JSON_FIELDS = {"reward_multipliers", "transfer_partners", "credits", "issuer_rules"}
ISSUER_DOMAINS = {
    "chase": "chase.com", "american express": "americanexpress.com", "amex": "americanexpress.com",
    "capital one": "capitalone.com", "citi": "citi.com", "citibank": "citi.com",
    "wells fargo": "wellsfargo.com",
}


def issuer_source(issuer: str, value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    domain = ISSUER_DOMAINS.get(issuer.casefold())
    return bool(domain and parsed.scheme == "https" and parsed.hostname
                and (parsed.hostname == domain or parsed.hostname.endswith(f".{domain}")))


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class CardTermsReviewService:
    def __init__(self, storage: Any = None):
        self.storage = storage or get_storage()

    def stage(self, payload: dict[str, Any], *, source: str = "research") -> int:
        from app.services.card_management_service import CardManagementService  # noqa: PLC0415

        products = {p.slug: p for p in CardManagementService(self.storage).get_catalog()}
        count = 0
        with self.storage.connection() as conn:
            for update in payload.get("updates", []):
                product = products.get(update.get("slug"))
                if product is None:
                    continue
                proposed = {key: val for key, val in (update.get("fields") or {}).items() if key in FIELDS}
                if not proposed:
                    continue
                # Validate the whole proposed product using the same contract as
                # the live catalog, before anything can become an approval.
                CreditCardProduct.model_validate({**product.model_dump(), **proposed})
                previous = {key: product.model_dump()[key] for key in proposed}
                evidence = update.get("evidence") or {}
                digest = fingerprint({"slug": product.slug, "previous": previous, "proposed": proposed, "evidence": evidence})
                result = conn.execute("""INSERT INTO card_term_proposals
                    (id, product_slug, proposed_fields, previous_fields, evidence, fingerprint, review_source)
                    VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) ON CONFLICT (fingerprint) DO NOTHING""",
                    [str(uuid.uuid4()), product.slug, json.dumps(proposed), json.dumps(previous), json.dumps(evidence), digest, source])
                count += result.rowcount or 0
            conn.commit()
        return count

    def list_pending(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute("""SELECT id::text, product_slug, proposed_fields, previous_fields,
                evidence, fingerprint, created_at::text FROM card_term_proposals WHERE status='pending' ORDER BY created_at DESC""").fetchall()
        return [dict(zip(("id", "product_slug", "proposed_fields", "previous_fields", "evidence", "fingerprint", "created_at"), row, strict=True)) for row in rows]

    def decide(self, proposal_id: str, *, expected_fingerprint: str, accept: bool) -> None:
        with self.storage.connection() as conn:
            row = conn.execute("SELECT product_slug, proposed_fields, previous_fields, evidence, fingerprint, status FROM card_term_proposals WHERE id=%s FOR UPDATE", [proposal_id]).fetchone()
            if row is None:
                raise KeyError("Term proposal not found.")
            slug, proposed, previous, evidence, digest, status = row
            if status != "pending" or digest != expected_fingerprint:
                raise ValueError("Proposal changed or was already reviewed. Reload the comparison.")
            if accept:
                product = conn.execute("SELECT to_jsonb(p) FROM credit_card_products p WHERE slug=%s FOR UPDATE", [slug]).fetchone()
                if product is None:
                    raise ValueError("Product no longer exists.")
                current = product[0]
                if not isinstance(current, dict) or not isinstance(proposed, dict) or not isinstance(previous, dict):
                    raise ValueError("Malformed term comparison; research the current terms again.")
                normalized = CreditCardProduct.model_validate(current).model_dump()
                if any(normalized.get(key) != value for key, value in previous.items()):
                    raise ValueError("Catalog changed since this proposal. Research the current terms again.")
                verified = dict(current.get("verified_terms") or {})
                for key, value in proposed.items():
                    proof = evidence.get(key) if isinstance(evidence, dict) else None
                    if key not in FIELDS or not isinstance(proof, dict) or not issuer_source(str(current["issuer"]), proof.get("source_url")) or not proof.get("excerpt"):
                        raise ValueError(f"{key}: an issuer source and the supporting terms are required before approval.")
                    verified[key] = {**proof, "value": value, "checked_at": datetime.now(UTC).isoformat()}
                clauses = [f"{key}=%s::jsonb" if key in JSON_FIELDS else f"{key}=%s" for key in proposed]
                params = [json.dumps(v) if k in JSON_FIELDS else v for k, v in proposed.items()]
                conn.execute(f"UPDATE credit_card_products SET {','.join(clauses)}, verified_terms=%s::jsonb, updated_at=now() WHERE slug=%s",
                             [*params, json.dumps(verified), slug])
            conn.execute("UPDATE card_term_proposals SET status=%s, reviewed_at=now() WHERE id=%s", ["accepted" if accept else "dismissed", proposal_id])
            conn.commit()
