from __future__ import annotations

import numpy as np
import pandas as pd

from app.macro_gate.signals import factor_crowding


def test_factor_crowding_uses_enough_calendar_history(monkeypatch) -> None:
    symbols = [f"S{i:03d}" for i in range(120)]
    dates = pd.bdate_range("2025-05-23", periods=260)
    trend = np.linspace(0.0, 1.0, len(dates))
    data = {}
    for idx, symbol in enumerate(symbols):
        drift = (idx - 60) / 6000
        cycle = np.sin(np.linspace(0, 8, len(dates)) + idx / 7) / 50
        data[symbol] = 100 + trend * (20 + idx / 3) + cycle + np.arange(len(dates)) * drift
    panel = pd.DataFrame(data, index=dates)
    captured: dict[str, int] = {}

    monkeypatch.setattr(
        factor_crowding.universe_service,
        "list_active_symbols",
        lambda: symbols,
    )

    def fake_load_panel(loaded_symbols: list[str], days: int) -> pd.DataFrame:
        captured["days"] = days
        assert loaded_symbols == symbols
        return panel

    monkeypatch.setattr(factor_crowding, "_load_panel", fake_load_panel)

    observation = factor_crowding.compute_crowding()

    assert captured["days"] >= 300
    assert observation is not None
    assert observation.rolling_window_days == 60
    assert observation.universe_size == len(symbols)
    assert -1.0 <= observation.momentum_value_corr <= 1.0
