from __future__ import annotations

from datetime import date

from app.macro_gate.signals import term_structure


class _Connection:
    def execute(self, _query: str):
        return self

    def fetchone(self):
        return (date(2026, 5, 20), 4.57, 4.04, 0.53)


class _ConnectionContext:
    def __enter__(self):
        return _Connection()

    def __exit__(self, *_args):
        return False


class _Storage:
    def connection(self):
        return _ConnectionContext()


class _DisabledSource:
    def is_enabled(self):
        return False


def test_term_structure_falls_back_to_stored_yield_curve(monkeypatch) -> None:
    storage = _Storage()
    monkeypatch.setattr(term_structure, "get_storage", lambda: storage)

    observation = term_structure.fetch_latest(_DisabledSource())

    assert observation is not None
    assert observation.as_of == date(2026, 5, 20)
    assert observation.yield_10y == 4.57
    assert observation.yield_2y == 4.04
    assert round(observation.spread_bps, 2) == 53.0
    assert observation.is_inverted is False
