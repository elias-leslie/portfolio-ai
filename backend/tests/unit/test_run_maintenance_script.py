from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_maintenance.py"


def _load_run_maintenance_module():
    spec = importlib.util.spec_from_file_location("run_maintenance_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_maintenance_supports_vacuum_alias(monkeypatch) -> None:
    module = _load_run_maintenance_module()
    captured: dict[str, bool] = {}

    def fake_vacuum(*, dry_run: bool) -> dict[str, bool]:
        captured["dry_run"] = dry_run
        return {"success": True}

    monkeypatch.setitem(
        module.TASK_REGISTRY,
        "vacuum_database",
        {
            "function": fake_vacuum,
            "args": [],
            "description": "VACUUM ANALYZE all database tables",
            "supports_dry_run": True,
        },
    )

    result = module.run_task("vacuum", dry_run=True)

    assert result == {"success": True}
    assert captured == {"dry_run": True}


def test_run_maintenance_script_is_executable() -> None:
    assert SCRIPT_PATH.stat().st_mode & 0o111
