"""Integration tests for Portfolio API endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.storage import get_storage

client = TestClient(app)


def test_health_endpoint() -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    # Health status can be "healthy" or "degraded" in tests (sources may not have been used yet)
    assert response.json()["status"] in ["healthy", "degraded"]
    assert "checks" in response.json()
    assert "database" in response.json()["checks"]


def test_root_endpoint() -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_create_account() -> None:
    """Test creating a new account."""
    response = client.post(
        "/api/portfolio/account",
        json={"name": "API Test IRA", "account_type": "IRA"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "API Test IRA"
    assert data["account_type"] == "IRA"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_duplicate_named_account_skips_conflicting_household_link() -> None:
    """A duplicate manual portfolio account should not 500 if canonical link target is already taken."""
    storage = get_storage()
    household_account_id = str(uuid4())

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO household_accounts (
                id, primary_identity_key, canonical_label, asset_group, account_type, source_type,
                institution_name, owner_name, account_mask, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
            """,
            [
                household_account_id,
                "test::roth-ira",
                "ROTH IRA",
                "retirement",
                "roth_ira",
                "retirement",
                "Fidelity",
                None,
                None,
            ],
        )
        conn.execute(
            """
            INSERT INTO portfolio_accounts (
                id, name, account_type, household_account_id, cash_balance, initial_cash, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            [
                str(uuid4()),
                "ROTH IRA",
                "Roth",
                household_account_id,
                0.0,
                0.0,
            ],
        )
        conn.commit()

    response = client.post(
        "/api/portfolio/account",
        json={"name": "ROTH IRA", "account_type": "Roth"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ROTH IRA"
    assert data["household_account_id"] is None

    accounts_response = client.get("/api/portfolio/accounts")
    assert accounts_response.status_code == 200
    matching = [row for row in accounts_response.json() if row["name"] == "ROTH IRA"]
    assert len(matching) == 2
    assert sorted(row["household_account_id"] for row in matching) == [None, household_account_id]
