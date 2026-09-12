"""Confirmation and card history survive subsequent catalog changes."""
import json
import uuid

import pytest
from tests.integration.services.test_household_transaction_dedup import _insert_document

from app.models.credit_cards import CreditCardCreate, CreditCardUpdate
from app.services.card_management_service import CardManagementService
from app.services.card_offer_agent_service import CardOfferAgentService
from app.services.card_terms_review_service import fingerprint
from app.storage import get_storage


@pytest.fixture
def cards():
    service = CardManagementService(get_storage())
    product = str(uuid.uuid4())
    with service.storage.connection() as conn:
        conn.execute("INSERT INTO credit_card_products (id,slug,issuer,product_name,annual_fee,welcome_min_spend,welcome_bonus_cash,welcome_window_days) VALUES (%s,%s,'Chase','Example',95,4000,500,90)", [product, f'example-{product}'])
        conn.commit()
    return service, product


def test_original_welcome_terms_and_history_survive_catalog_update(cards):
    service, product = cards
    card = service.create_owned_card(CreditCardCreate(product_id=product, status='active', opened_date='2026-07-01', player='p2'))
    with service.storage.connection() as conn:
        conn.execute('UPDATE credit_card_products SET welcome_min_spend=6000 WHERE id=%s', [product])
        conn.commit()
    owned = next(c for c in service.list_owned_cards() if c.id == card.id)
    assert owned.product is not None and owned.product.welcome_min_spend == 4000
    service.update_owned_card(card.id, CreditCardUpdate(welcome_min_spend=4500, welcome_earned_date='2026-09-01', welcome_status='earned'))
    service.delete_owned_card(card.id)
    closed = next(c for c in service.list_owned_cards() if c.id == card.id)
    assert closed.status == 'closed' and closed.welcome_earned_date == '2026-09-01' and closed.player == 'p2'
    with pytest.raises(ValueError, match='closed'):
        service.activate_card(card.id)
    corrected = service.update_owned_card(card.id, CreditCardUpdate(closed_date=None, welcome_earned_date=None))
    assert corrected.closed_date is None and corrected.welcome_earned_date is None
    assert corrected.status == 'rotated_out'


def test_offer_extraction_never_updates_existing_catalog_before_or_after_card_confirmation(cards):
    service, product_id = cards
    document = _insert_document(service.storage, source_type='credit_card_offer')
    extracted = CardOfferAgentService()._stage_product({'issuer':'Chase','product_name':'Example',
        'annual_fee':195, 'welcome':{'min_spend':8000,'bonus_cash':1000,'window_days':90}}, document_id=document, service=service)
    assert extracted.id == product_id
    with service.storage.connection() as conn:
        assert conn.execute('SELECT annual_fee,welcome_min_spend FROM credit_card_products WHERE id=%s',[product_id]).fetchone() == (95,4000)
    req = CreditCardCreate(product_id=product_id, source_document_id=document, offer_fingerprint='stale')
    with pytest.raises(ValueError, match='preview changed'):
        service.create_owned_card(req)
    req.offer_fingerprint = fingerprint(extracted.model_dump(mode='json'))
    card = service.create_owned_card(req)
    owned = next(c for c in service.list_owned_cards() if c.id == card.id)
    assert owned.product is not None and owned.product.welcome_min_spend == 8000
    assert owned.product.annual_fee == 195
    with service.storage.connection() as conn:
        assert conn.execute('SELECT annual_fee,welcome_min_spend FROM credit_card_products WHERE id=%s',[product_id]).fetchone() == (95,4000)
        row = conn.execute('SELECT metadata FROM household_documents WHERE id=%s', [document]).fetchone()
        assert row is not None and row[0]['card_offer_confirmed_at']


def test_unknown_original_terms_are_not_filled_from_todays_public_offer(cards):
    service, product_id = cards
    card = service.create_owned_card(CreditCardCreate(product_id=product_id, status='active'))
    with service.storage.connection() as conn:
        conn.execute("UPDATE household_credit_cards SET metadata=%s::jsonb WHERE id=%s",[json.dumps({}),card.id])
        conn.commit()
    owned = next(c for c in service.list_owned_cards() if c.id == card.id)
    assert owned.product is not None and owned.product.welcome_min_spend is None
