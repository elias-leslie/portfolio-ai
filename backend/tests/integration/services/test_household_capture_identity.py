"""Real persistence proves member isolation and idempotent camera upload."""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import app
from app.models.household_capture import CaptureReview
from app.models.push_alerts import PushSubscriptionInput, PushSubscriptionKeys
from app.services import household_identity
from app.services.household_capture_service import HouseholdCaptureService
from app.services.household_identity import HouseholdIdentity
from app.services.push_service import PushService
from app.storage import get_storage


def member(name, role, email):
    member_id = str(uuid.uuid4())
    with get_storage().connection() as conn:
        conn.execute(
            "INSERT INTO household_members (id, display_name, role, email, is_dependent) VALUES (%s,%s,%s,%s,%s)",
            [member_id, name, role, email, role == "child"],
        )
        conn.commit()
    return HouseholdIdentity(
        member_id=member_id,
        display_name=name,
        access="capture_only" if role == "child" else "adult",
    )


def test_provisioning_sets_only_unassigned_members(monkeypatch):
    one = member("Test Adult", "primary", None)
    member("Second Adult", "spouse", "existing@example.invalid")
    monkeypatch.setattr(
        household_identity.settings,
        "household_member_emails",
        SecretStr('{"first@example.invalid":"Test Adult","old@example.invalid":"Second Adult"}'),
    )
    assert household_identity.seed_member_emails() == 1
    assert household_identity.seed_member_emails() == 0
    with get_storage().connection() as conn:
        row = conn.execute(
            "SELECT email FROM household_members WHERE id=%s", [one.member_id]
        ).fetchone()
        assert row and row[0] == "first@example.invalid"
        row = conn.execute(
            "SELECT email FROM household_members WHERE display_name='Second Adult'"
        ).fetchone()
        assert row and row[0] == "existing@example.invalid"


def test_capture_retry_and_ownership_do_not_manufacture_purchase(monkeypatch, tmp_path):
    a = member("Test Child A", "child", "a@example.invalid")
    b = member("Test Child B", "child", "b@example.invalid")
    adult = member("Test Adult", "primary", "adult@example.invalid")
    monkeypatch.setattr(household_identity.settings, "household_upload_dir", tmp_path)
    service = HouseholdCaptureService()
    params = {
        "client_id": str(uuid.uuid4()),
        "kind": "shelf_tag",
        "content": b"test image",
        "filename": "photo.jpg",
        "content_type": "image/jpeg",
        "store_name": "Test store",
        "note": "Test only",
    }
    before = None
    with get_storage().connection() as conn:
        row = conn.execute("SELECT count(*) FROM household_transactions").fetchone()
        assert row
        before = row[0]
    saved = service.save(a, **params)
    assert service.save(a, **params).id == saved.id
    assert saved.captured_by == a.member_id
    assert saved.purchased_by is None and saved.purchased_for is None and saved.outcome == "unknown"
    assert len(list(tmp_path.rglob("*.jpg"))) == 1
    assert service.list_captures(b) == []
    with pytest.raises(HTTPException) as exc:
        service.image(b, saved.id)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException):
        service.review(
            a, saved.id, CaptureReview(status="verified", review_note="Cannot self-approve")
        )
    with pytest.raises(HTTPException):
        service.save(a, **{**params, "content": b"changed"})
    reviewed = service.review(
        adult,
        saved.id,
        CaptureReview(
            status="verified",
            outcome="purchased",
            purchased_by=uuid.UUID(adult.member_id),
            purchased_for=uuid.UUID(b.member_id),
            review_note="Buyer explicitly confirmed for test.",
        ),
    )
    assert (
        reviewed.captured_by == a.member_id
        and reviewed.purchased_by == adult.member_id
        and reviewed.purchased_for == b.member_id
    )
    with get_storage().connection() as conn:
        row = conn.execute("SELECT count(*) FROM household_transactions").fetchone()
        assert row and row[0] == before


def test_child_cannot_read_finances_or_spoof_member(monkeypatch, tmp_path):
    a = member("Test Child", "child", "child@example.invalid")
    adult = member("Test Adult", "primary", "adult@example.invalid")
    monkeypatch.setattr(household_identity.settings, "household_upload_dir", tmp_path)
    monkeypatch.setattr(
        household_identity,
        "verify_access_assertion",
        lambda _assertion: {"email": "child@example.invalid"},
    )
    client = TestClient(app, client=("192.0.2.1", 5000))
    headers = {"cf-access-jwt-assertion": "test-signed", "x-household-member-id": adult.member_id}
    assert client.get("/api/identity", headers=headers).json()["member_id"] == a.member_id
    for path in [
        "/api/household/dashboard",
        "/api/portfolio/jenny",
        "/api/household/push/subscriptions",
    ]:
        assert client.get(path, headers=headers).status_code == 403
    assert (
        client.post(
            "/api/captures",
            headers=headers,
            data={"client_id": str(uuid.uuid4()), "kind": "receipt", "member_scope": a.member_id},
            files={"file": ("photo.jpg", b"\xff\xd8\xfftest", "image/jpeg")},
        ).status_code
        == 200
    )
    rows = client.get("/api/captures", headers=headers).json()
    assert rows[0]["captured_by"] == a.member_id
    assert (
        client.patch(
            f"/api/captures/{rows[0]['id']}",
            headers=headers,
            json={"status": "verified", "review_note": "No"},
        ).status_code
        == 403
    )


def test_push_target_and_registration_respect_signed_in_member():
    a = member("Adult A", "primary", "a@example.invalid")
    b = member("Adult B", "spouse", "b@example.invalid")
    service = PushService()
    payload = PushSubscriptionInput(
        endpoint="https://push.example.invalid/test",
        keys=PushSubscriptionKeys(encryption_key="public-test", auth_secret="test"),
        household_member_id=a.member_id,
    )
    first = service.register(payload, enforce_owner=True)
    with pytest.raises(ValueError):
        service.register(
            payload.model_copy(update={"household_member_id": b.member_id}), enforce_owner=True
        )
    assert service._targets(subscription_id=first.id, household_member_ids=[b.member_id]) == []
    assert not service.unregister(first.id, member_id=b.member_id)
    assert service.unregister(first.id, member_id=a.member_id)


def test_chat_session_cannot_be_replayed_by_another_member(monkeypatch):
    from app.api.portfolio import jenny_routes
    from app.api.portfolio.models import JennyChatResponseModel

    a = member("Adult A", "primary", "a@example.invalid")
    member("Adult B", "spouse", "b@example.invalid")
    monkeypatch.setattr(household_identity, "verify_access_assertion", lambda assertion: {"email": f"{assertion}@example.invalid"})
    calls = []
    def respond(payload):
        calls.append(payload)
        return JennyChatResponseModel(reply="Test reply", session_id="isolated-test-session")
    monkeypatch.setattr(jenny_routes, "_chat_with_jenny_payload", respond)
    client = TestClient(app, client=("192.0.2.1", 5000))
    assert client.post("/api/portfolio/jenny/chat", headers={"cf-access-jwt-assertion": "a"}, json={"message": "Test only"}).status_code == 200
    with get_storage().connection() as conn:
        row = conn.execute("SELECT member_id FROM household_chat_sessions WHERE session_id='isolated-test-session'").fetchone()
        assert row and str(row[0]) == a.member_id
    response = client.post("/api/portfolio/jenny/chat", headers={"cf-access-jwt-assertion": "b"}, json={"message": "Test only", "session_id": "isolated-test-session"})
    assert response.status_code == 403 and len(calls) == 1
