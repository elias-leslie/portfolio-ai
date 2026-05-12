"""Contract tests for the Investment Committee REST routes.

The route handlers wrap ``app.agents.committee.store`` / ``stream`` /
``services.paper_trades``. These tests use FastAPI TestClient and
monkeypatch the storage + runner layer so each route is exercised
without a live DB or Agent Hub. The shape assertions pin the
snake_case contract the frontend reducer keys off — a camelCase
mutation anywhere in the response path would zero out the live
console.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.committee import store as committee_store
from app.agents.committee import stream as committee_stream
from app.api import committee_runs as routes
from app.api import committee_stream as stream_routes
from app.services import paper_trades as paper_trades_svc


@pytest.fixture
def test_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A FastAPI app with the two committee routers mounted."""
    app = FastAPI()
    app.include_router(routes.router)
    app.include_router(stream_routes.router)
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


# ---------- POST /runs ----------


def test_post_runs_creates_row_and_returns_run_id(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """POST /runs → 201 with the run_id + symbol + graph_version."""
    created_run_id = "11111111-1111-1111-1111-111111111111"
    created_kwargs: dict[str, Any] = {}

    def fake_create_run(**kw: Any) -> str:
        created_kwargs.update(kw)
        return created_run_id

    async def fake_register(run_id: str) -> None:
        return None

    async def fake_run_committee_safely(**kw: Any) -> None:
        return None

    monkeypatch.setattr(committee_store, "create_run", fake_create_run)
    monkeypatch.setattr(committee_stream, "register", fake_register)
    monkeypatch.setattr(routes, "_run_committee_safely", fake_run_committee_safely)

    response = client.post("/api/committee/runs", json={"symbol": "nvda"})

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == created_run_id
    assert body["symbol"] == "NVDA"
    assert body["status"] == "pending"
    assert "graph_version" in body
    assert created_kwargs["symbol"] == "nvda"


# ---------- GET /runs (list endpoint) ----------


def test_get_runs_returns_snake_case_list(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """GET /runs returns the household-scoped projection used by PriorRunsSidebar.

    Each row MUST stay snake_case so the raw-fetch path in
    ``frontend/lib/committee/api.ts`` does not need to know about
    camelCase mapping. Anything that camelCases this response is the
    regression we're guarding against (see c34c396b).
    """
    fake_rows = [
        {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "symbol": "AAPL",
            "status": "complete",
            "decision_action": "buy",
            "decision_pct_portfolio": 0.04,
            "confidence": 0.81,
            "parent_run_id": None,
            "started_at": "2026-05-12T10:00:00+00:00",
            "completed_at": "2026-05-12T10:15:00+00:00",
        },
        {
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "symbol": "NVDA",
            "status": "approved",
            "decision_action": "trim",
            "decision_pct_portfolio": 0.015,
            "confidence": 0.78,
            "parent_run_id": None,
            "started_at": "2026-05-12T09:00:00+00:00",
            "completed_at": "2026-05-12T09:14:00+00:00",
        },
    ]

    captured_limit: list[int] = []

    def fake_list_recent_runs(household_id: str | None, *, limit: int = 20) -> list[dict[str, Any]]:
        captured_limit.append(limit)
        return fake_rows

    monkeypatch.setattr(committee_store, "list_recent_runs", fake_list_recent_runs)

    response = client.get("/api/committee/runs?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)
    assert len(body["runs"]) == 2
    row = body["runs"][0]
    for key in (
        "id",
        "symbol",
        "status",
        "decision_action",
        "decision_pct_portfolio",
        "confidence",
        "parent_run_id",
        "started_at",
        "completed_at",
    ):
        assert key in row, f"expected snake_case key {key!r} in run row"
    assert row["symbol"] == "AAPL"
    assert row["decision_action"] == "buy"
    assert captured_limit == [2]


def test_get_runs_clamps_limit_to_one_hundred(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """limit=10000 must be clamped to 100 (defensive against misbehaving clients)."""
    captured: dict[str, int] = {}

    def fake_list_recent_runs(household_id: str | None, *, limit: int = 20) -> list[dict[str, Any]]:
        captured["limit"] = limit
        return []

    monkeypatch.setattr(committee_store, "list_recent_runs", fake_list_recent_runs)

    response = client.get("/api/committee/runs?limit=10000")
    assert response.status_code == 200
    assert captured["limit"] == 100


# ---------- GET /runs/{id} (snapshot) ----------


def test_get_run_snapshot_preserves_event_shape(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Snapshot events MUST carry every top-level field the reducer reads.

    The reducer in ``frontend/lib/committee/reducer.ts`` reads each
    event's top-level ``seq``, ``ts``, ``type``, ``stage``, ``agent_slug``,
    ``role``, ``content``, ``score``, ``tokens``, ``latency_ms``,
    ``run_id``. Any mutation that strips or renames these keys is the
    regression we're pinning.
    """
    run_id = "11111111-1111-1111-1111-111111111111"

    def fake_get_run_summary(rid: str) -> dict[str, Any]:
        assert rid == run_id
        return {
            "id": run_id,
            "symbol": "NVDA",
            "household_id": None,
            "status": "complete",
            "decision_action": "hold",
            "decision_qty": None,
            "decision_pct_portfolio": 0.0,
            "decision_price": None,
            "decision_horizon": "1-3 months",
            "confidence": 0.72,
            "bull_score": 0.31,
            "bear_score": -0.18,
            "parent_run_id": None,
            "graph_version": "committee.v0.3.1",
            "started_at": "2026-05-12T00:00:00+00:00",
            "completed_at": "2026-05-12T00:15:00+00:00",
            "approved_at": None,
            "aborted_at": None,
            "error": None,
            "tokens_total": 42_000,
            "cost_usd": 0.31,
        }

    def fake_load_events(rid: str) -> list[dict[str, Any]]:
        assert rid == run_id
        return [
            {
                "seq": 0,
                "ts": "2026-05-12T00:00:00+00:00",
                "type": "run.start",
                "stage": "system",
                "agent_slug": None,
                "role": None,
                "content": {"symbol": "NVDA", "graph_version": "committee.v0.3.1"},
                "score": None,
                "tokens": None,
                "latency_ms": None,
                "run_id": run_id,
            },
            {
                "seq": 1,
                "ts": "2026-05-12T00:00:01+00:00",
                "type": "agent.output",
                "stage": "analysts",
                "agent_slug": "fundamentals-v1",
                "role": "analyst",
                "content": {"content_md": "thesis…", "evidence": []},
                "score": 0.15,
                "tokens": 1200,
                "latency_ms": 980,
                "run_id": run_id,
            },
        ]

    monkeypatch.setattr(committee_store, "get_run_summary", fake_get_run_summary)
    monkeypatch.setattr(committee_store, "load_events", fake_load_events)

    response = client.get(f"/api/committee/runs/{run_id}")
    assert response.status_code == 200
    body = response.json()

    # The contract is `{ run, events }` — both snake_case.
    assert set(body.keys()) == {"run", "events"}
    run = body["run"]
    for key in (
        "id",
        "symbol",
        "status",
        "decision_action",
        "decision_pct_portfolio",
        "tokens_total",
        "graph_version",
    ):
        assert key in run, f"snake_case key {key!r} dropped from run snapshot"
    events = body["events"]
    assert len(events) == 2
    for event in events:
        for key in (
            "seq",
            "ts",
            "type",
            "stage",
            "agent_slug",
            "role",
            "content",
            "score",
            "tokens",
            "latency_ms",
            "run_id",
        ):
            assert key in event, f"top-level event key {key!r} missing — reducer would break"


def test_get_run_snapshot_404_when_missing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(committee_store, "get_run_summary", lambda _rid: None)
    monkeypatch.setattr(committee_store, "load_events", lambda _rid: [])
    response = client.get("/api/committee/runs/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404


# ---------- POST /runs/{id}/approve ----------


def test_post_approve_calls_paper_trades_execute_from_run(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Approve invokes paper_trades.execute_from_run (the source of the real DB write)."""

    class _FakeTrade:
        id = "tttttttt-tttt-tttt-tttt-tttttttttttt"
        symbol = "AAPL"
        action = "buy"
        qty = 50.0
        price = 200.0
        run_id = "11111111-1111-1111-1111-111111111111"

    captured: dict[str, str] = {}

    def fake_execute_from_run(run_id: str):
        captured["run_id"] = run_id
        return _FakeTrade()

    monkeypatch.setattr(paper_trades_svc, "execute_from_run", fake_execute_from_run)

    response = client.post(
        f"/api/committee/runs/{_FakeTrade.run_id}/approve"
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "paper_trade_id": _FakeTrade.id,
        "run_id": _FakeTrade.run_id,
        "symbol": _FakeTrade.symbol,
        "action": _FakeTrade.action,
        "qty": _FakeTrade.qty,
        "price": _FakeTrade.price,
    }
    assert captured["run_id"] == _FakeTrade.run_id


def test_post_approve_returns_409_when_paper_trade_error(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Approve on a non-buyable run should bubble PaperTradeError → 409."""

    def fake_execute(run_id: str):
        raise paper_trades_svc.PaperTradeError("decision is hold")

    monkeypatch.setattr(paper_trades_svc, "execute_from_run", fake_execute)
    response = client.post(
        "/api/committee/runs/11111111-1111-1111-1111-111111111111/approve"
    )
    assert response.status_code == 409
    assert "hold" in response.json()["detail"]


# ---------- POST /runs/{id}/feedback ----------


def test_post_feedback_persists_input_and_emits_event(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Feedback writes committee_inputs + run.feedback.received and enqueues for the runner."""
    run_id = "11111111-1111-1111-1111-111111111111"
    persist_event_calls: list[dict[str, Any]] = []
    persist_user_input_calls: list[dict[str, Any]] = []
    enqueue_calls: list[dict[str, Any]] = []
    emit_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda rid: {"id": rid, "status": "running"},
    )
    monkeypatch.setattr(committee_store, "load_events", lambda _rid: [])

    def fake_persist_event(rid: str, **kwargs: Any) -> tuple[int, int]:
        persist_event_calls.append({"run_id": rid, **kwargs})
        return 12345, 17

    def fake_persist_user_input(rid: str, **kwargs: Any) -> str:
        persist_user_input_calls.append({"run_id": rid, **kwargs})
        return "input-uuid-1"

    def fake_enqueue(rid: str, payload: dict[str, Any]) -> bool:
        enqueue_calls.append({"run_id": rid, **payload})
        return True

    async def fake_emit(rid: str, event: dict[str, Any]) -> None:
        emit_calls.append({"run_id": rid, **event})

    monkeypatch.setattr(committee_store, "persist_event", fake_persist_event)
    monkeypatch.setattr(committee_store, "persist_user_input", fake_persist_user_input)
    monkeypatch.setattr(committee_stream, "enqueue_feedback", fake_enqueue)
    monkeypatch.setattr(committee_stream, "emit", fake_emit)

    response = client.post(
        f"/api/committee/runs/{run_id}/feedback",
        json={"user_input": "What about the China tariff news?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"input_id": "input-uuid-1", "round": 1, "enqueued": True}

    assert len(persist_event_calls) == 1
    evt = persist_event_calls[0]
    assert evt["type"] == "run.feedback.received"
    assert evt["stage"] == "feedback"
    assert evt["role"] == "user"
    assert evt["content"]["user_input"] == "What about the China tariff news?"

    assert len(persist_user_input_calls) == 1
    assert persist_user_input_calls[0]["user_input"] == "What about the China tariff news?"

    assert len(enqueue_calls) == 1
    assert enqueue_calls[0]["round"] == 1
    assert enqueue_calls[0]["user_input"] == "What about the China tariff news?"

    assert len(emit_calls) == 1
    assert emit_calls[0]["type"] == "run.feedback.received"


# ---------- POST /runs/{id}/pause | /resume | /abort ----------


def test_pause_resume_abort_call_stream_helpers(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Each control endpoint flips the corresponding stream helper."""
    run_id = "11111111-1111-1111-1111-111111111111"
    calls: list[str] = []

    def _pause(rid: str) -> bool:
        calls.append(f"pause:{rid}")
        return True

    def _resume(rid: str) -> bool:
        calls.append(f"resume:{rid}")
        return True

    def _abort(rid: str) -> bool:
        calls.append(f"abort:{rid}")
        return True

    monkeypatch.setattr(committee_stream, "pause", _pause)
    monkeypatch.setattr(committee_stream, "resume", _resume)
    monkeypatch.setattr(committee_stream, "abort", _abort)

    assert client.post(f"/api/committee/runs/{run_id}/pause").json() == {"paused": True}
    assert client.post(f"/api/committee/runs/{run_id}/resume").json() == {"resumed": True}
    assert client.post(f"/api/committee/runs/{run_id}/abort").json() == {"aborted": True}

    assert calls == [
        f"pause:{run_id}",
        f"resume:{run_id}",
        f"abort:{run_id}",
    ]


def test_resume_schedules_persisted_running_run_when_registry_missing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """POST /resume re-attaches a DB-running run if the in-memory runner was lost."""
    run_id = "11111111-1111-1111-1111-111111111111"
    scheduled: dict[str, Any] = {}

    monkeypatch.setattr(committee_stream, "resume", lambda _rid: False)
    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda _rid: {
            "id": run_id,
            "symbol": "NVDA",
            "household_id": None,
            "parent_run_id": None,
            "status": "running",
        },
    )

    async def fake_schedule(run: dict[str, Any], **kw: Any) -> bool:
        scheduled.update(run)
        return True

    monkeypatch.setattr(routes, "_schedule_run", fake_schedule)

    response = client.post(f"/api/committee/runs/{run_id}/resume")

    assert response.status_code == 200
    assert response.json() == {"resumed": True}
    assert scheduled["id"] == run_id
    assert scheduled["symbol"] == "NVDA"


def test_abort_marks_persisted_running_run_when_registry_missing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """POST /abort records a terminal event even if the live queue is gone."""
    run_id = "11111111-1111-1111-1111-111111111111"
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(committee_stream, "abort", lambda _rid: False)
    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda _rid: {"id": run_id, "status": "running"},
    )

    def fake_mark_aborted(rid: str, *, reason: str) -> None:
        calls.append({"kind": "mark", "run_id": rid, "reason": reason})

    def fake_persist_event(rid: str, **kw: Any) -> tuple[int, int]:
        calls.append({"kind": "event", "run_id": rid, **kw})
        return 1, 7

    monkeypatch.setattr(committee_store, "mark_aborted", fake_mark_aborted)
    monkeypatch.setattr(committee_store, "persist_event", fake_persist_event)

    response = client.post(f"/api/committee/runs/{run_id}/abort")

    assert response.status_code == 200
    assert response.json() == {"aborted": True}
    assert calls[0] == {"kind": "mark", "run_id": run_id, "reason": "user_abort"}
    assert calls[1]["kind"] == "event"
    assert calls[1]["type"] == "run.aborted"


# ---------- POST /runs/{id}/retro ----------


def test_post_retro_starts_new_run_with_parent_run_id(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Retro reads the parent run, then forwards to start_run with parent_run_id set."""
    parent_id = "11111111-1111-1111-1111-111111111111"
    created_id = "22222222-2222-2222-2222-222222222222"

    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda _rid: {"id": _rid, "status": "approved", "symbol": "NVDA"},
    )

    create_kwargs: dict[str, Any] = {}

    def fake_create_run(**kw: Any) -> str:
        create_kwargs.update(kw)
        return created_id

    async def fake_register(rid: str) -> None:
        return None

    async def fake_run_safely(**kw: Any) -> None:
        return None

    monkeypatch.setattr(committee_store, "create_run", fake_create_run)
    monkeypatch.setattr(committee_stream, "register", fake_register)
    monkeypatch.setattr(routes, "_run_committee_safely", fake_run_safely)

    response = client.post(f"/api/committee/runs/{parent_id}/retro")
    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == created_id
    assert body["symbol"] == "NVDA"
    assert create_kwargs["parent_run_id"] == parent_id


def test_post_retro_409_when_parent_not_completed(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda _rid: {"id": _rid, "status": "running", "symbol": "NVDA"},
    )
    response = client.post(
        "/api/committee/runs/11111111-1111-1111-1111-111111111111/retro"
    )
    assert response.status_code == 409


# ---------- GET /runs/{id}/stream ----------


def test_get_stream_returns_event_stream_with_sse_framing(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """The SSE endpoint must serve text/event-stream with no-transform/no-buffering headers.

    Each event line follows the ``event: TYPE\\ndata: JSON\\n\\n``
    framing the EventSource client expects. We exercise the history
    replay path (status='complete' means no live tail).
    """
    run_id = "11111111-1111-1111-1111-111111111111"

    monkeypatch.setattr(
        committee_store,
        "get_run_summary",
        lambda _rid: {"id": _rid, "status": "complete"},
    )
    monkeypatch.setattr(
        committee_store,
        "load_events",
        lambda _rid: [
            {
                "seq": 0,
                "ts": "2026-05-12T00:00:00+00:00",
                "type": "run.start",
                "stage": "system",
                "agent_slug": None,
                "role": None,
                "content": {"symbol": "NVDA"},
                "score": None,
                "tokens": None,
                "latency_ms": None,
            },
            {
                "seq": 1,
                "ts": "2026-05-12T00:15:00+00:00",
                "type": "run.complete",
                "stage": "system",
                "agent_slug": None,
                "role": None,
                "content": {"tokens_total": 1000},
                "score": None,
                "tokens": None,
                "latency_ms": None,
            },
        ],
    )

    with client.stream("GET", f"/api/committee/runs/{run_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        body = b"".join(response.iter_bytes()).decode()

    assert "event: run.start\n" in body
    assert "event: run.complete\n" in body
    # Frames terminate with the standard SSE \n\n separator.
    assert "\n\n" in body
