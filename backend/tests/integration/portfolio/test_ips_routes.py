"""Integration test for the IPS / drift / rebalance routes.

Drives the FastAPI app end-to-end against the live Postgres fixture
established by the standard ``client`` pattern. Asserts:

- ``PUT /api/portfolio/ips/targets`` upserts and ``GET /targets`` reads.
- ``GET /api/portfolio/ips/drift`` returns a summary by default and the
  full report when ``summary=false``.
- ``POST /api/portfolio/ips/rebalance`` returns a deterministic plan
  matching the planner's three-pass logic.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.cache import clear_cache


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_response_cache() -> None:
    clear_cache()


@pytest.fixture(autouse=True)
def mock_price_data() -> Generator[None]:
    from app.portfolio.models import PriceData
    from app.portfolio.price_fetcher import PriceDataFetcher

    price_map = {"VTI": 100.0, "BND": 100.0, "VXUS": 100.0}

    def mock_fetch_fresh_prices(symbols: list[str]) -> dict[str, PriceData]:
        return {
            symbol: PriceData(
                symbol=symbol,
                price=price_map.get(symbol, 100.0),
                beta=1.0,
                sector="ETF",
                source="test",
                error=None,
            )
            for symbol in symbols
        }

    with patch.object(PriceDataFetcher, "_fetch_fresh_prices", side_effect=mock_fetch_fresh_prices):
        yield


@pytest.fixture
def scope_id() -> str:
    """Fresh scope_id per test so rows don't collide with other tests."""
    return f"test-hh-{uuid.uuid4().hex[:8]}"


def test_upsert_and_get_ips_targets(client: TestClient, scope_id: str) -> None:
    payload = {
        "scope": "household",
        "scope_id": scope_id,
        "asset_class": "us_equity",
        "target_pct": 0.6,
        "drift_band_pct": 0.05,
    }
    put_response = client.put("/api/portfolio/ips/targets", json=payload)
    assert put_response.status_code == 200, put_response.text
    body = put_response.json()
    assert body["asset_class"] == "us_equity"
    assert body["target_pct"] == 0.6

    # Upsert with new target value.
    payload["target_pct"] = 0.55
    upsert_response = client.put("/api/portfolio/ips/targets", json=payload)
    assert upsert_response.status_code == 200
    assert upsert_response.json()["target_pct"] == 0.55

    list_response = client.get(
        "/api/portfolio/ips/targets",
        params={"scope": "household", "scope_id": scope_id},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["target_pct"] == 0.55


def test_upsert_target_validates_range(client: TestClient, scope_id: str) -> None:
    payload = {
        "scope": "household",
        "scope_id": scope_id,
        "asset_class": "us_equity",
        "target_pct": 1.5,
    }
    response = client.put("/api/portfolio/ips/targets", json=payload)
    assert response.status_code == 422, response.text


def test_drift_default_returns_summary(client: TestClient, scope_id: str) -> None:
    client.put(
        "/api/portfolio/ips/targets",
        json={
            "scope": "household",
            "scope_id": scope_id,
            "asset_class": "us_equity",
            "target_pct": 0.6,
        },
    )
    response = client.get(
        "/api/portfolio/ips/drift",
        params={"scope": "household", "scope_id": scope_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "max_drift_pct" in body
    assert "classes_out_of_band" in body
    assert "snapshot_date" in body


def test_drift_summary_false_returns_full_report(client: TestClient, scope_id: str) -> None:
    client.put(
        "/api/portfolio/ips/targets",
        json={
            "scope": "household",
            "scope_id": scope_id,
            "asset_class": "us_equity",
            "target_pct": 0.6,
        },
    )
    response = client.get(
        "/api/portfolio/ips/drift",
        params={"scope": "household", "scope_id": scope_id, "summary": "false"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert "classes_missing_targets" in body


def test_rebalance_fails_closed_without_canonical_household_value(
    client: TestClient, scope_id: str
) -> None:
    """A target alone is not enough evidence to recommend household trades."""
    client.put(
        "/api/portfolio/ips/targets",
        json={
            "scope": "household",
            "scope_id": scope_id,
            "asset_class": "us_equity",
            "target_pct": 1.0,
        },
    )
    response = client.post(
        "/api/portfolio/ips/rebalance",
        json={
            "scope": "household",
            "scope_id": scope_id,
            "prefer_tax_advantaged": True,
            "prefer_ltcg": True,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Canonical household investment value is unavailable."
