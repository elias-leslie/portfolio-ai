from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware import cache as cache_module
from app.middleware.cache import cache_response, clear_cache, invalidate_cache_pattern


def test_cache_response_honors_decorator_ttl(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)
    now = 100.0
    monkeypatch.setattr(cache_module, "monotonic", lambda: now)
    clear_cache()

    app = FastAPI()
    calls = 0

    @app.get("/short")
    @cache_response(ttl=30)
    async def short_cache(request: Request) -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"calls": calls}

    client = TestClient(app)

    assert client.get("/short").json() == {"calls": 1}

    now = 129.0
    assert client.get("/short").json() == {"calls": 1}

    now = 131.0
    assert client.get("/short").json() == {"calls": 2}


def test_cache_response_keeps_longer_ttl_entries(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)
    now = 200.0
    monkeypatch.setattr(cache_module, "monotonic", lambda: now)
    clear_cache()

    app = FastAPI()
    calls = 0

    @app.get("/long")
    @cache_response(ttl=900)
    async def long_cache(request: Request) -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"calls": calls}

    client = TestClient(app)

    assert client.get("/long").json() == {"calls": 1}

    now = 800.0
    assert client.get("/long").json() == {"calls": 1}


def test_cache_response_finds_request_with_underscored_parameter(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)
    monkeypatch.setattr(cache_module, "monotonic", lambda: 300.0)
    clear_cache()

    app = FastAPI()
    calls = 0

    @app.get("/underscored")
    @cache_response(ttl=30)
    async def underscored_cache(_request: Request) -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"calls": calls}

    client = TestClient(app)

    assert client.get("/underscored").json() == {"calls": 1}
    assert client.get("/underscored").json() == {"calls": 1}


def test_invalidate_cache_pattern_uses_glob_not_regex(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "CACHE_ENABLED", True)
    clear_cache()
    cache_module._cache["GET:/api/v1:{}:"] = ({}, 200, {}, 999.0)
    cache_module._cache["GET:/apiXv1:{}:"] = ({}, 200, {}, 999.0)

    assert invalidate_cache_pattern("GET:/api/v1*") == 1
    assert "GET:/api/v1:{}:" not in cache_module._cache
    assert "GET:/apiXv1:{}:" in cache_module._cache
