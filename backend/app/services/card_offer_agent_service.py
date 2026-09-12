"""Card-offer intake extraction via the Agent Hub reviewer agent (plan §9).

A document uploaded with ``source_type='credit_card_offer'`` bypasses the
generic financial-document review loop: the ``credit-card-offer-reviewer``
Agent Hub agent extracts the card's publicly stated terms (vision + text) into
a structured payload, which remains on its source document until the user confirms the extracted
terms while adding a card. Existing catalog terms are never replaced by a
personalized offer.

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
from app.models.credit_cards import CardIntakeResult, CreditCardProduct
from app.services._household_document_llm import _build_review_image_content
from app.services._household_document_text import _extract_text
from app.services.card_terms_review_service import fingerprint
from app.services.household_document_storage import (
    household_upload_root,
    resolve_document_upload,
)

if TYPE_CHECKING:
    from app.models.household_finance_types import HouseholdDocument
    from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)

CARD_OFFER_AGENT_SLUG = "credit-card-offer-reviewer"
CARD_OFFER_SOURCE_TYPE = "credit_card_offer"


def _slugify(issuer: str, product_name: str) -> str:
    raw = f"{issuer} {product_name}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:120] or f"card-{uuid.uuid4().hex[:8]}"


class CardOfferAgentService:
    """Extract card terms for explicit review before they enter the plan."""

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
        product = self._stage_product(extracted, document_id=document.id, service=service)
        needs_review = True
        self._mark_document(
            service,
            document_id=document.id,
            confidence=confidence,
            needs_review=needs_review,
            summary=(
                f"Card offer extracted: {product.product_name} ({product.issuer}); "
                + (f"unreadable: {', '.join(unreadable)}; " if unreadable else "")
                + (notes or "no extraction notes")
            ),
        )
        logger.info(
            "credit_card_offer_extracted",
            document_id=document.id,
            slug=product.slug,
            confidence=confidence,
            needs_review=needs_review,
        )
        return CardIntakeResult(
            document_id=document.id,
            offer_fingerprint=fingerprint(product.model_dump(mode="json")),
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

    def _stage_product(self, extracted: dict[str, Any], *, document_id: str,
                       service: Any) -> CreditCardProduct:
        """Keep the extraction on its source document until the user confirms it."""
        from app.services.card_management_service import CardManagementService  # noqa: PLC0415

        issuer = str(extracted.get("issuer") or "Unknown")
        name = str(extracted["product_name"])
        slug = _slugify(issuer, name)
        existing = next((p for p in CardManagementService(service.storage).get_catalog()
                         if p.slug == slug or (p.issuer.casefold() == issuer.casefold()
                                              and p.product_name.casefold() == name.casefold())), None)
        welcome = extracted.get("welcome") if isinstance(extracted.get("welcome"), dict) else {}
        product = CreditCardProduct(
            id=existing.id if existing else str(uuid.uuid5(uuid.NAMESPACE_URL, f"card-offer:{document_id}")),
            slug=existing.slug if existing else slug, issuer=issuer, product_name=name,
            annual_fee=extracted.get("annual_fee") or 0,
            reward_multipliers=extracted.get("reward_multipliers") or {},
            point_program=extracted.get("point_program"),
            est_point_value_cents=extracted.get("est_point_value_cents"),
            welcome_bonus_points=welcome.get("bonus_points") or 0,
            welcome_bonus_cash=welcome.get("bonus_cash") or 0,
            welcome_min_spend=welcome.get("min_spend"),
            welcome_window_days=welcome.get("window_days"),
            source="intake", source_document_id=document_id,
        )
        staged = product.model_dump(mode="json")
        with service.storage.connection() as conn:
            conn.execute("UPDATE household_documents SET metadata=COALESCE(metadata,'{}'::jsonb) || %s::jsonb WHERE id=%s",
                         [json.dumps({"card_offer": staged, "card_offer_fingerprint": fingerprint(staged)}), document_id])
            conn.commit()
        return product

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
