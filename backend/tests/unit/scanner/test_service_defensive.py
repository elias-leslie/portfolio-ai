"""DEFENSIVE-zone short-circuit behaviour for the scanner service."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch
from uuid import UUID, uuid4

from app.scanner import service


def test_defensive_zone_writes_empty_run_with_skip_reason() -> None:
    """When the macro gate says DEFENSIVE, the scanner must persist a
    header row marked ``skip_reason='gate_defensive'`` and zero scores.
    """
    fixed_run_id = uuid4()

    created: dict[str, object] = {}
    finalized: dict[str, object] = {}

    def fake_get_latest() -> dict:
        return {"zone": "DEFENSIVE", "deployment_score": 22.0}

    def fake_list_active_symbols() -> list[str]:
        return ["AAPL", "MSFT", "GOOG"]

    def fake_create_run(**kwargs: object) -> UUID:
        created.update(kwargs)
        return fixed_run_id

    def fake_finalize_run(run_id: UUID, scored_count: int) -> None:
        finalized["run_id"] = run_id
        finalized["scored_count"] = scored_count

    def fail_insert(*args: object, **kwargs: object) -> int:
        raise AssertionError("DEFENSIVE zone must not insert any scores")

    with patch.object(service.macro_repo, "get_latest", side_effect=fake_get_latest), \
         patch.object(service.universe_service, "list_active_symbols",
                      side_effect=fake_list_active_symbols), \
         patch.object(service.repository, "create_run", side_effect=fake_create_run), \
         patch.object(service.repository, "finalize_run", side_effect=fake_finalize_run), \
         patch.object(service.repository, "insert_scores", side_effect=fail_insert):
        out = service.run(snapshot_date=date(2026, 5, 17))

    assert out is not None
    assert out.gate_zone == "DEFENSIVE"
    assert out.scored_count == 0
    assert out.skip_reason == "gate_defensive"
    assert out.universe_size == 3
    assert created["skip_reason"] == "gate_defensive"
    assert created["gate_zone"] == "DEFENSIVE"
    assert created["universe_size"] == 3
    assert finalized == {"run_id": fixed_run_id, "scored_count": 0}


def test_no_macro_snapshot_yields_none() -> None:
    with patch.object(service.macro_repo, "get_latest", return_value=None):
        assert service.run() is None
