"""The trend keeps every score and the latest provenance without repeating all detail."""

import pytest

from app.api import macro_routes


@pytest.mark.asyncio
async def test_trend_points_keep_scores_and_latest_evidence(monkeypatch):
    rows = [
        {
            "snapshot_date": "2026-09-10",
            "deployment_score": 48.0,
            "zone": "selective",
            "vix_score": 20.0,
            "raw_json": {},
        },
        {
            "snapshot_date": "2026-09-11",
            "deployment_score": 49.0,
            "zone": "selective",
            "vix_score": 21.0,
            "raw_json": {
                "coverage": 0.8,
                "component_quality": {"vix": {"status": "stale", "reason": "awaiting close"}},
            },
        },
    ]

    def history(days, *, latest_detail_only):
        assert days == 90
        assert latest_detail_only is True
        return rows

    monkeypatch.setattr(macro_routes.repository, "get_history", history)
    result = await macro_routes.trend_history(90)
    assert [point.deployment_score for point in result.points] == [48, 49]
    assert result.points[0].components["vix"] == 20
    assert result.latest.coverage == 0.8
    assert result.latest.component_quality["vix"]["reason"] == "awaiting close"
    assert "raw" not in result.points[0].model_dump()
