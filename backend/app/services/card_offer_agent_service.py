"""Card-offer intake extraction via the Agent Hub reviewer agent (plan §9).

A document uploaded with ``source_type='credit_card_offer'`` bypasses the
generic financial-document review loop: the ``credit-card-offer-reviewer``
Agent Hub agent extracts the card's publicly stated terms (vision + text) into
a structured payload, which is upserted into ``credit_card_products``
(``source='intake'``) keyed by slug. Low-confidence or partially unreadable
extractions are surfaced on the document row (``review_status='needs_review'``)
so the Cards tab can ask the user to confirm.

Agent configuration lives in Agent Hub ([M:9a51cbd8]); portfolio-ai routes by
slug only ([M:7ce57b1e]).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_hub.models.content import MessageInput, TextContent

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.models.credit_cards import CardIntakeResult
from app.services._household_document_llm import _build_review_image_content
from app.services._household_document_text import _extract_text
from app.services.household_document_storage import (
    household_upload_root,
    resolve_document_upload,
)
from app.storage import get_storage

if TYPE_CHECKING:
    from app.models.household_finance_types import HouseholdDocument
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)

CARD_OFFER_AGENT_SLUG = "credit-card-offer-reviewer"
CARD_OFFER_SOURCE_TYPE = "credit_card_offer"

# Below this the extraction needs a human look before it is trusted.
_CONFIDENCE_FLOOR = 0.65



def _slugify(issuer: str, product_name: str) -> str:
    raw = f"{issuer} {product_name}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:120] or f"card-{uuid.uuid4().hex[:8]}"


class CardOfferAgentService:
    """Extract card terms from an offer document and upsert the catalog row."""

    def __init__(self) -> None:
        self._client_cls = AgentHubAPIClient

    def process_offer_document(
        self, service: HouseholdFinanceService, document: HouseholdDocument
    ) -> CardIntakeResult:
        stored_file = resolve_document_upload(
            document.metadata,
            household_upload_root(service),
        )
        extracted = self._run_extraction(document=document, stored_file=stored_file)

        confidence = float(extracted.get("confidence") or 0.0)
        unreadable = [str(f) for f in (extracted.get("unreadable_fields") or [])]
        notes = str(extracted.get("extraction_notes") or "")
        product_row = self._upsert_product(extracted, document_id=document.id)
        needs_review = confidence < _CONFIDENCE_FLOOR or bool(unreadable)
        self._mark_document(
            service,
            document_id=document.id,
            confidence=confidence,
            needs_review=needs_review,
            summary=(
                f"Card offer extracted: {product_row['product_name']} ({product_row['issuer']}); "
                + (f"unreadable: {', '.join(unreadable)}; " if unreadable else "")
                + (notes or "no extraction notes")
            ),
        )
        logger.info(
            "credit_card_offer_extracted",
            document_id=document.id,
            slug=product_row["slug"],
            confidence=confidence,
            needs_review=needs_review,
        )
        # Lazy: card_management_service pulls the transaction-service stack;
        # importing it at module load would slow every pipeline import.
        from app.services.card_management_service import CardManagementService  # noqa: PLC0415

        product = next(
            (p for p in CardManagementService().get_catalog() if p.slug == product_row["slug"]),
            None,
        )
        if product is None:  # row was just upserted; absence means a bug
            raise RuntimeError(f"Card product {product_row['slug']} missing after upsert.")
        return CardIntakeResult(
            document_id=document.id,
            status="needs_review" if needs_review else "extracted",
            product=product,
            confidence=confidence,
            unreadable_fields=unreadable,
            extraction_notes=notes or None,
        )

    # -- internals ---------------------------------------------------------

    def _run_extraction(
        self, *, document: HouseholdDocument, stored_file: Path | None
    ) -> dict[str, Any]:
        text = _extract_text(stored_file, document.content_type) if stored_file else None
        content: list[Any] = [
            TextContent(
                text=(
                    "Extract the credit-card offer terms from this document into the JSON "
                    "schema from your instructions.\n"
                    f"Filename: {document.filename}\n"
                    + (f"Extracted text (rough aid):\n{text[:8000]}" if text else "No machine-extracted text.")
                )
            )
        ]
        if stored_file and (document.content_type or "").startswith("image/"):
            image = _build_review_image_content(stored_file)
            if image is not None:
                content.append(image)
        client = self._client_cls(agent_slug=CARD_OFFER_AGENT_SLUG, use_memory=False)
        response = client.complete_messages(
            messages=[MessageInput(role="user", content=content)],
            response_format={"type": "json_object"},
            purpose="credit_card_offer_extraction",
        )
        payload = json.loads(response.content)
        if not isinstance(payload, dict) or not payload.get("product_name"):
            raise ValueError("Card offer extraction returned no product_name.")
        return payload

    def _upsert_product(self, extracted: dict[str, Any], *, document_id: str) -> dict[str, Any]:
        issuer = str(extracted.get("issuer") or "Unknown")
        product_name = str(extracted["product_name"])
        slug = _slugify(issuer, product_name)
        welcome = extracted.get("welcome") if isinstance(extracted.get("welcome"), dict) else {}
        row = {
            "slug": slug,
            "issuer": issuer,
            "network": extracted.get("network"),
            "product_name": product_name,
            "card_kind": str(extracted.get("card_kind") or "personal"),
            "annual_fee": float(extracted.get("annual_fee") or 0.0),
            "reward_multipliers": json.dumps(extracted.get("reward_multipliers") or {"other": 1.0}),
            "point_program": extracted.get("point_program"),
            "est_point_value_cents": float(extracted.get("est_point_value_cents") or 1.0),
            "welcome_bonus_points": int(welcome.get("bonus_points") or 0),
            "welcome_bonus_cash": float(welcome.get("bonus_cash") or 0.0),
            "welcome_min_spend": float(welcome.get("min_spend") or 0.0),
            "welcome_window_days": int(welcome.get("window_days") or 0),
            "transfer_partners": json.dumps(extracted.get("transfer_partners") or []),
            "credits": json.dumps(extracted.get("credits") or []),
            "issuer_rules": json.dumps(extracted.get("issuer_rules") or {}),
            "source_document_id": document_id,
        }
        storage = get_storage()
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO credit_card_products (
                    id, slug, issuer, network, product_name, card_kind, annual_fee,
                    reward_multipliers, point_program, est_point_value_cents,
                    welcome_bonus_points, welcome_bonus_cash, welcome_min_spend,
                    welcome_window_days, transfer_partners, credits, issuer_rules,
                    source, source_document_id, last_verified_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, 'intake', %s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (slug) DO UPDATE SET
                    issuer = EXCLUDED.issuer,
                    network = EXCLUDED.network,
                    product_name = EXCLUDED.product_name,
                    card_kind = EXCLUDED.card_kind,
                    annual_fee = EXCLUDED.annual_fee,
                    reward_multipliers = EXCLUDED.reward_multipliers,
                    point_program = EXCLUDED.point_program,
                    est_point_value_cents = EXCLUDED.est_point_value_cents,
                    welcome_bonus_points = EXCLUDED.welcome_bonus_points,
                    welcome_bonus_cash = EXCLUDED.welcome_bonus_cash,
                    welcome_min_spend = EXCLUDED.welcome_min_spend,
                    welcome_window_days = EXCLUDED.welcome_window_days,
                    transfer_partners = EXCLUDED.transfer_partners,
                    credits = EXCLUDED.credits,
                    issuer_rules = EXCLUDED.issuer_rules,
                    source = 'intake',
                    source_document_id = EXCLUDED.source_document_id,
                    last_verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    str(uuid.uuid4()), row["slug"], row["issuer"], row["network"],
                    row["product_name"], row["card_kind"], row["annual_fee"],
                    row["reward_multipliers"], row["point_program"], row["est_point_value_cents"],
                    row["welcome_bonus_points"], row["welcome_bonus_cash"], row["welcome_min_spend"],
                    row["welcome_window_days"], row["transfer_partners"], row["credits"],
                    row["issuer_rules"], row["source_document_id"],
                ],
            )
            conn.commit()
        return row

    def _mark_document(
        self,
        service: HouseholdFinanceService,
        *,
        document_id: str,
        confidence: float,
        needs_review: bool,
        summary: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_documents
                SET status = %s, review_status = %s, review_confidence = %s,
                    review_summary = %s, parsed_at = %s
                WHERE id = %s
                """,
                [
                    "needs_review" if needs_review else "parsed",
                    "needs_review" if needs_review else "complete",
                    confidence,
                    summary,
                    now,
                    document_id,
                ],
            )
            conn.commit()


@lru_cache(maxsize=1)
def get_card_offer_agent_service() -> CardOfferAgentService:
    return CardOfferAgentService()
