import uuid

import pytest

from app.services.card_terms_review_service import CardTermsReviewService
from app.storage import get_storage


@pytest.fixture
def terms():
    storage = get_storage()
    slug = f"terms-{uuid.uuid4()}"
    with storage.connection() as conn:
        conn.execute("INSERT INTO credit_card_products (id,slug,issuer,product_name,annual_fee) VALUES (%s,%s,'Chase','Example',95)", [str(uuid.uuid4()), slug])
        conn.commit()
    return CardTermsReviewService(storage), slug


def propose(service, slug, *, source="https://creditcards.chase.com/rewards-credit-cards/sapphire/reserve"):
    return service.stage({"updates": [{"slug": slug, "fields": {"annual_fee": 195},
        "evidence": {"annual_fee": {"source_url": source, "excerpt": "Example fee terms"}}}]})


def test_research_stays_pending_and_exact_approval_keeps_field_provenance(terms):
    service, slug = terms
    assert propose(service, slug) == 1
    assert propose(service, slug) == 0
    with service.storage.connection() as conn:
        assert conn.execute("SELECT annual_fee FROM credit_card_products WHERE slug=%s", [slug]).fetchone() == (95,)
    proposal = next(p for p in service.list_pending() if p["product_slug"] == slug)
    with pytest.raises(ValueError, match="changed"):
        service.decide(proposal["id"], expected_fingerprint="old", accept=True)
    service.decide(proposal["id"], expected_fingerprint=proposal["fingerprint"], accept=True)
    with service.storage.connection() as conn:
        row = conn.execute("SELECT annual_fee, verified_terms FROM credit_card_products WHERE slug=%s", [slug]).fetchone()
        assert row is not None
        assert row[0] == 195
        assert row[1]["annual_fee"]["value"] == 195
        assert "checked_at" in row[1]["annual_fee"]
    assert not any(p["product_slug"] == slug for p in service.list_pending())


def test_a_lookalike_domain_cannot_verify_a_term(terms):
    service, slug = terms
    propose(service, slug, source="https://chase.com.attacker.example/terms")
    proposal = next(p for p in service.list_pending() if p["product_slug"] == slug)
    with pytest.raises(ValueError, match="issuer source"):
        service.decide(proposal["id"], expected_fingerprint=proposal["fingerprint"], accept=True)


def test_a_changed_catalog_cannot_be_overwritten_by_an_old_proposal(terms):
    service, slug = terms
    propose(service, slug)
    proposal = next(p for p in service.list_pending() if p["product_slug"] == slug)
    with service.storage.connection() as conn:
        conn.execute("UPDATE credit_card_products SET annual_fee=150 WHERE slug=%s", [slug])
        conn.commit()
    with pytest.raises(ValueError, match="Catalog changed"):
        service.decide(proposal["id"], expected_fingerprint=proposal["fingerprint"], accept=True)


def test_credit_comparison_accepts_legacy_rows_with_new_model_defaults(terms):
    service, slug = terms
    with service.storage.connection() as conn:
        conn.execute("UPDATE credit_card_products SET credits='[{\"name\":\"Old\",\"annual_value\":50,\"type\":\"moderate\"}]'::jsonb WHERE slug=%s", [slug])
        conn.commit()
    service.stage({'updates':[{'slug':slug,'fields':{'credits':[]},'evidence':{'credits':{'source_url':'https://creditcards.chase.com/','excerpt':'Unsupported credits excluded.'}}}]})
    proposal = next(p for p in service.list_pending() if p['product_slug'] == slug)
    service.decide(proposal['id'], expected_fingerprint=proposal['fingerprint'], accept=True)


def test_new_offers_are_staged_and_only_create_catalog_entries_after_review(terms):
    service, _ = terms
    data = {"slug": "new-travel-card", "issuer": "Chase", "product_name": "New travel card", "annual_fee": 95,
            "welcome_min_spend": 4000, "welcome_window_days": 90, "welcome_bonus_points": 60000}
    evidence = {key: {"source_url": "https://creditcards.chase.com/example", "excerpt": str(value)}
                for key, value in data.items() if key != "slug"}
    payload = {"new_candidates": [{"product": data, "evidence": evidence}]}
    assert service.stage(payload) == 1
    assert service.stage(payload) == 0
    with service.storage.connection() as conn:
        assert conn.execute("SELECT count(*) FROM credit_card_products WHERE slug=%s", [data["slug"]]).fetchone()[0] == 0
    proposal = next(p for p in service.list_pending() if p["product_slug"] == data["slug"])
    assert proposal["previous_fields"] == {}
    service.decide(proposal["id"], expected_fingerprint=proposal["fingerprint"], accept=True)
    with service.storage.connection() as conn:
        assert conn.execute("SELECT welcome_bonus_points FROM credit_card_products WHERE slug=%s", [data["slug"]]).fetchone()[0] == 60000
        assert conn.execute("SELECT count(*) FROM household_credit_cards").fetchone()[0] == 0


def test_new_offer_cannot_bypass_field_evidence(terms):
    service, _ = terms
    service.stage({"new_candidates": [{"product": {"slug": "unsupported-card", "issuer": "Chase", "product_name": "Unsupported",
        "annual_fee": 95, "welcome_min_spend": 4000, "welcome_window_days": 90, "welcome_bonus_points": 60000}}]})
    proposal = next(p for p in service.list_pending() if p["product_slug"] == "unsupported-card")
    with pytest.raises(ValueError, match="issuer source"):
        service.decide(proposal["id"], expected_fingerprint=proposal["fingerprint"], accept=True)
