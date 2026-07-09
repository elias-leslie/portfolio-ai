"""Guards the systemd unit templates in scripts/systemd/.

Regression test for the orphaned-worker incident: the hatchet worker unit was
set to ``KillMode=process``, so ``systemctl restart`` killed only the worker
main and left its multiprocessing action-runner children running. The orphans
stayed connected to Hatchet, kept accepting dispatched step runs, never executed
them, and black-holed scheduled jobs (account sync, data refresh) across
restarts. ``KillMode=control-group`` makes systemd kill the whole cgroup on every
stop/restart, so the leak is structurally impossible — that is the self-healing
guarantee, enforced natively by systemd alongside the unit's ``Restart=always``.

The prior version of this test only checked the frontend unit, so the worker's
drift to ``KillMode=process`` went uncaught. It now covers every unit template.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

SYSTEMD_DIR = Path(__file__).resolve().parents[3] / "scripts" / "systemd"
REPO_ROOT = SYSTEMD_DIR.parents[1]


def _kill_modes(service_path: Path) -> list[str]:
    text = service_path.read_text()
    # Anchored at line start so commented prose that documents *why* process
    # mode is wrong (which legitimately contains "KillMode=process") is not
    # mistaken for an actual directive.
    return re.findall(r"^KillMode=(.+)$", text, re.MULTILINE)


def test_all_unit_templates_use_control_group_kill_mode() -> None:
    services = sorted(SYSTEMD_DIR.glob("*.service"))
    assert services, f"no unit templates found under {SYSTEMD_DIR}"
    for service in services:
        modes = _kill_modes(service)
        assert modes, f"{service.name} declares no KillMode"
        for mode in modes:
            assert mode.strip() == "control-group", (
                f"{service.name} uses KillMode={mode!r}; must be 'control-group' "
                "so restarts reap the whole process tree and never orphan "
                "multiprocessing worker children"
            )


def test_hatchet_worker_never_uses_process_kill_mode() -> None:
    worker = SYSTEMD_DIR / "portfolio-hatchet-worker.service"
    assert worker.exists(), f"missing {worker}"
    assert "process" not in _kill_modes(worker)


def test_http_unit_templates_bind_only_to_loopback() -> None:
    backend = (SYSTEMD_DIR / "portfolio-backend.service").read_text()
    frontend = (SYSTEMD_DIR / "portfolio-frontend.service").read_text()

    assert "--host 127.0.0.1" in backend
    assert 'Environment="HOSTNAME=127.0.0.1"' in frontend


def test_standalone_compose_publishes_private_ports_on_loopback() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]
    published_services = (
        "portfolio-db",
        "portfolio-redis",
        "hatchet",
        "portfolio-api",
        "portfolio-web",
    )

    for service_name in published_services:
        ports = services[service_name]["ports"]
        assert ports, f"{service_name} has no published ports to verify"
        assert all(str(port).startswith("127.0.0.1:") for port in ports), (
            f"{service_name} exposes a non-loopback host port: {ports}"
        )
