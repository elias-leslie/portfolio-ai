"""Real observations prove package arithmetic, confirmations and role boundaries."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.household_shopping_pilot import (
    FamilyConfirmation,
    OfferConfirmation,
    PackageConfirmation,
    PilotProduct,
    ShoppingComparison,
)
from app.services.household_buy_guide_service import HouseholdBuyGuideService
from app.services.household_identity import HouseholdIdentity, capture_path_allowed
from app.services.household_product_catalog_service import HouseholdProductCatalogService
from app.services.household_shopping_pilot import HouseholdShoppingPilot
from app.storage import get_storage

ADULT = HouseholdIdentity(display_name="Test operator", access="local_operator")
CHILD = HouseholdIdentity(
    member_id=str(uuid.uuid4()), display_name="Test child", access="capture_only"
)


def setup_pilot(monkeypatch):
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    with get_storage().connection() as conn:
        for pid in ids:
            conn.execute(
                "INSERT INTO household_products (id,canonical_name) VALUES (%s,'Olive oil 68 fl oz')",
                [pid],
            )
            for days, price in [(60, 59.34), (30, 59.34)]:
                conn.execute(
                    """INSERT INTO household_product_price_observations
                    (id,product_id,observed_date,total_price,quantity,unit_price,source,package_display_label,package_normalized_quantity,package_normalized_unit)
                    VALUES (%s,%s,%s,%s,2,%s,'receipt','6 x 9 softgels',54,'count')""",
                    [str(uuid.uuid4()), pid, date.today() - timedelta(days=days), price, price / 2],
                )
        conn.commit()
    monkeypatch.setattr(
        HouseholdShoppingPilot,
        "products",
        lambda _self, _conn: [
            PilotProduct(id=pid, name="Olive oil", stores=["Test store"]) for pid in ids
        ],
    )
    return HouseholdShoppingPilot(), ids


def offer(pid, **overrides):
    data = dict(  # noqa: C408
        product_id=pid,
        store="Test store",
        title="Test olive oil",
        package_label="68 fl oz",
        price=25,
        fees=0,
        coupon=2,
        observed_date=date.today(),
        valid_until=date.today() + timedelta(days=7),
        conditions="In store, no membership, coupon checked today",
        availability_confirmed=True,
        equivalence_confirmed=True,
        membership_confirmed=True,
        coupon_confirmed=True,
        fees_confirmed=True,
    )
    return OfferConfirmation(**{**data, **overrides})


def test_confirmed_offer_and_history_share_correct_units_without_a_purchase(monkeypatch):
    service, ids = setup_pilot(monkeypatch)
    review = service.review(ADULT)
    assert review[0]["baseline"]["unit_price"] == pytest.approx(29.67 / 68, abs=0.0001)
    with get_storage().connection() as conn:
        before_row = conn.execute("SELECT count(*) FROM household_transactions").fetchone()
        assert before_row is not None
        before = before_row[0]
    compare = ShoppingComparison(product_id=ids[0], package_label="68 fl oz", total_price=29.67)
    assert service.compare(compare).status == "needs_evidence"
    service.confirm_offer(ADULT, offer(ids[0]))
    result = service.compare(compare)
    assert result.status == "lower_recorded_offer"
    assert result.alternative_price == 23
    assert result.equivalent_difference == 6.67
    guide = HouseholdBuyGuideService().get_buy_guide()
    assert guide.items[0].current_total_price == 29.67
    assert guide.items[0].best_total_price == 23
    with get_storage().connection() as conn:
        best = HouseholdProductCatalogService._best_researched_prices(conn, product_ids=ids)
        assert best[ids[0]]["unit_price"] == pytest.approx(23 / 68, abs=0.0001)
        after = conn.execute("SELECT count(*) FROM household_transactions").fetchone()
        assert after and after[0] == before


def test_family_equivalence_requires_confirmation_and_compatible_units(monkeypatch):
    service, ids = setup_pilot(monkeypatch)
    service.confirm_offer(ADULT, offer(ids[1]))
    comparison = ShoppingComparison(product_id=ids[0], package_label="68 fl oz", total_price=29.67)
    assert service.compare(comparison).status == "needs_evidence"
    service.confirm_family(
        ADULT,
        FamilyConfirmation(
            product_ids=ids,
            name="Cooking olive oil",
            purpose="Same extra virgin type and acceptable cooking quality",
        ),
    )
    assert service.compare(comparison).equivalent_difference == 6.67
    assert len(HouseholdBuyGuideService().get_buy_guide().items) == 2


def test_package_confirmation_is_scoped_and_stale_preview_is_rejected(monkeypatch):
    service, ids = setup_pilot(monkeypatch)
    first = service.review(ADULT)[0]["baseline"]
    payload = PackageConfirmation(
        fingerprint=first["fingerprint"],
        package_label="32 fl oz",
        packages=2,
        evidence="Test bottle and receipt confirm two bottles",
    )
    service.confirm_package(ADULT, ids[0], payload)
    second = service.review(ADULT)[0]["baseline"]
    assert second["line_total"] == 59.34
    assert second["unit_price"] == pytest.approx(59.34 / 64, abs=0.0001)
    with pytest.raises(HTTPException) as error:
        service.confirm_package(ADULT, ids[0], payload)
    assert error.value.status_code == 409
    with get_storage().connection() as conn:
        raw = conn.execute(
            "SELECT quantity,package_normalized_quantity FROM household_product_price_observations WHERE id=(SELECT id FROM household_product_price_observations WHERE product_id=%s ORDER BY observed_date DESC LIMIT 1)",
            [ids[0]],
        ).fetchone()
    assert raw == (2, 54)  # Source stays intact; the separate confirmed basis wins.


def test_child_cannot_confirm_and_unknown_conditions_do_not_pass(monkeypatch):
    service, ids = setup_pilot(monkeypatch)
    with pytest.raises(HTTPException) as error:
        service.confirm_offer(CHILD, offer(ids[0]))
    assert error.value.status_code == 403
    with pytest.raises(ValidationError):
        offer(ids[0], membership_confirmed=False)
    with pytest.raises(HTTPException):
        service.confirm_offer(ADULT, offer(ids[0], observed_date=date.today() - timedelta(days=15)))
    assert capture_path_allowed("GET", "/api/captures/shopping/products")
    assert capture_path_allowed("POST", "/api/captures/shopping/compare")
    for path in ["review", "offers", "families", f"{ids[0]}/package"]:
        assert not capture_path_allowed("GET", f"/api/captures/shopping/{path}")
        assert not capture_path_allowed("POST", f"/api/captures/shopping/{path}")


def test_withdrawn_offer_and_ungrouped_substitute_stop_recommending(monkeypatch):
    service, ids = setup_pilot(monkeypatch)
    saved = service.confirm_offer(ADULT, offer(ids[1]))
    assert service.confirm_offer(ADULT, offer(ids[1])) == saved
    service.confirm_family(
        ADULT,
        FamilyConfirmation(
            product_ids=ids,
            name="Cooking oil",
            purpose="Same oil type and acceptable cooking quality",
        ),
    )
    check = ShoppingComparison(product_id=ids[0], package_label="68 fl oz", total_price=29.67)
    assert service.compare(check).status == "lower_recorded_offer"
    service.ungroup(ADULT, ids[0])
    assert service.compare(check).status == "needs_evidence"
    service.withdraw_offer(ADULT, saved)
    assert (
        service.compare(check.model_copy(update={"product_id": uuid.UUID(ids[1])})).status
        == "needs_evidence"
    )
    assert HouseholdBuyGuideService().get_buy_guide().items == []
    with pytest.raises(HTTPException):
        service.confirm_offer(ADULT, offer(ids[1]))


def test_shelf_tag_confirmation_updates_evidence_but_keeps_buyer_unknown(monkeypatch, tmp_path):
    from app.services.household_capture_service import HouseholdCaptureService
    from app.services.household_identity import settings

    service, ids = setup_pilot(monkeypatch)
    monkeypatch.setattr(settings, 'household_upload_dir', tmp_path)
    saved = HouseholdCaptureService().save(ADULT, client_id=str(uuid.uuid4()), kind='shelf_tag',
        content=b'test image', filename='test.png', content_type='image/png', store_name='Test store', note='Test fixture')
    service.confirm_offer(ADULT, offer(ids[0], capture_id=saved.id))
    capture = HouseholdCaptureService().get(ADULT, saved.id)
    assert capture.status == 'verified'
    assert capture.outcome == 'unknown' and capture.purchased_by is None and capture.document_id is None
