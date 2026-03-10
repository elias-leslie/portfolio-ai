"""Unit tests for preference-driven automation overrides."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.preferences_service import (
    dict_to_preferences_response,
    get_automation_preferences,
)


def test_get_automation_preferences_prefers_stored_values(mocker) -> None:
    mocker.patch(
        "app.services.preferences_service.get_rules",
        return_value=SimpleNamespace(
            thesis_management=SimpleNamespace(
                thesis_generation_enabled=False,
                auto_remove_on_invalidation=True,
            ),
            watchlist_management=SimpleNamespace(auto_trim_enabled=True),
        ),
    )

    resolved = get_automation_preferences(
        {
            "thesis_generation_enabled": True,
            "auto_remove_on_invalidation": None,
            "auto_trim_enabled": False,
        }
    )

    assert resolved["thesis_generation_enabled"] == {
        "enabled": True,
        "source": "preferences",
    }
    assert resolved["auto_remove_on_invalidation"] == {
        "enabled": True,
        "source": "rules_default",
    }
    assert resolved["auto_trim_enabled"] == {
        "enabled": False,
        "source": "preferences",
    }


def test_dict_to_preferences_response_exposes_effective_automation_values(mocker) -> None:
    mocker.patch(
        "app.services.preferences_service.get_rules",
        return_value=SimpleNamespace(
            thesis_management=SimpleNamespace(
                thesis_generation_enabled=False,
                auto_remove_on_invalidation=True,
            ),
            watchlist_management=SimpleNamespace(auto_trim_enabled=True),
        ),
    )

    response = dict_to_preferences_response(
        {
            "risk_tolerance": 5,
            "allow_long": True,
            "allow_short": False,
            "allow_options": False,
            "allow_crypto": False,
            "allow_futures": False,
            "max_position_size_pct": 10.0,
            "default_refresh_minutes": 15,
            "watchlist_refresh_override": None,
            "portfolio_refresh_override": None,
            "news_refresh_override": None,
            "news_lookback_hours": 6,
            "news_max_articles": 10,
            "frontend_poll_interval": 30,
            "watchlist_refresh_minutes": 15,
            "watchlist_auto_expand": False,
            "watchlist_price_weight": 50.0,
            "watchlist_technical_weight": 50.0,
            "display_timezone": "America/New_York",
            "watchlist_show_news": True,
            "thesis_generation_enabled": None,
            "auto_remove_on_invalidation": False,
            "auto_trim_enabled": None,
        }
    )

    assert response.thesis_generation_enabled is False
    assert response.auto_remove_on_invalidation is False
    assert response.auto_trim_enabled is True
