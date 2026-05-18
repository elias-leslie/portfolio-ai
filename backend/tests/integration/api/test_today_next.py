from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_today_next_returns_three_tiers() -> None:
    client = TestClient(app)

    response = client.get('/api/today-next')

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'macro_gate', 'scanner', 'committee'}
    assert 'status' in data['macro_gate']
    assert isinstance(data['scanner'], list)
    assert isinstance(data['committee'], list)


def test_today_next_page_renders() -> None:
    client = TestClient(app)

    response = client.get('/today-next')

    assert response.status_code == 200
    assert 'Today Next' in response.text
