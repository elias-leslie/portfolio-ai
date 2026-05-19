from __future__ import annotations

import pytest

from app.agents.committee.cluster_weights import compute_cluster_weights


def test_cluster_weights_decay_low_sample_to_priors() -> None:
    weights = compute_cluster_weights([
        {
            "cluster": "market_regime",
            "freshness": "fresh",
            "sample_size": 5,
            "direction_hit_rate": 1.0,
            "move_mae_pct": 0.0,
            "brier_score": 0.0,
        },
        {"cluster": "sentiment", "freshness": "fresh", "sample_size": 0},
        {"cluster": "options_positioning", "freshness": "fresh", "sample_size": 0},
        {"cluster": "macro_calendar", "freshness": "fresh", "sample_size": 0},
    ])

    assert {cluster: round(weight.effective_weight, 6) for cluster, weight in weights.items()} == {
        "market_regime": 0.25,
        "sentiment": 0.25,
        "options_positioning": 0.25,
        "macro_calendar": 0.25,
    }


def test_cluster_weights_upweight_recent_accurate_cluster_and_decay_stale_cluster() -> None:
    weights = compute_cluster_weights([
        {
            "cluster": "market_regime",
            "freshness": "fresh",
            "sample_size": 24,
            "direction_hit_rate": 1.0,
            "move_mae_pct": 0.0,
            "brier_score": 0.0,
        },
        {
            "cluster": "sentiment",
            "freshness": "stale",
            "sample_size": 24,
            "direction_hit_rate": 0.0,
            "move_mae_pct": 2.0,
            "brier_score": 1.0,
        },
        {"cluster": "options_positioning", "freshness": "fresh", "sample_size": 0},
        {"cluster": "macro_calendar", "freshness": "missing", "sample_size": 0},
    ])

    assert weights["market_regime"].effective_weight > weights["options_positioning"].effective_weight
    assert weights["sentiment"].effective_weight < weights["options_positioning"].effective_weight
    assert weights["macro_calendar"].effective_weight == pytest.approx(0.0)
    assert weights["market_regime"].recommended_action == "upweight"
    assert weights["macro_calendar"].recommended_action == "downweight"
    assert sum(weight.effective_weight for weight in weights.values()) == pytest.approx(1.0)
