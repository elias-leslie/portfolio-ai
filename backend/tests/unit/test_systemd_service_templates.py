from __future__ import annotations

from pathlib import Path

SYSTEMD_DIR = Path(__file__).resolve().parents[3] / "scripts" / "systemd"


def test_portfolio_frontend_template_uses_control_group_shutdown() -> None:
    text = (SYSTEMD_DIR / "portfolio-frontend.service").read_text()

    assert "KillMode=control-group" in text
