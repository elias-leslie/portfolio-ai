"""Unit tests for preference-driven automation overrides."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models.preferences import PreferencesUpdate
from app.services.preferences_service import (
    dict_to_preferences_response,
    get_automation_preferences,
    update_preferences,
)


def test_get_automation_preferences_prefers_stored_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.preferences_service.get_rules",
        lambda: SimpleNamespace(
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
    assert resolved["scheduled_jenny_operator_enabled"] == {
        "enabled": False,
        "source": "rules_default",
    }
    assert resolved["scheduled_ml_labeling_enabled"] == {
        "enabled": False,
        "source": "rules_default",
    }
    assert resolved["scheduled_strategy_research_enabled"] == {
        "enabled": False,
        "source": "rules_default",
    }


def test_dict_to_preferences_response_exposes_effective_automation_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.preferences_service.get_rules",
        lambda: SimpleNamespace(
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
    assert response.scheduled_jenny_operator_enabled is False
    assert response.scheduled_ml_labeling_enabled is False
    assert response.scheduled_strategy_research_enabled is False


def test_update_preferences_allows_clearing_refresh_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.preferences_service.get_or_create_preferences",
        lambda: {
            "id": "default",
            "risk_tolerance": 5,
            "allow_long": True,
            "allow_short": False,
            "allow_options": False,
            "allow_crypto": False,
            "allow_futures": False,
            "max_position_size_pct": 10.0,
            "default_refresh_minutes": 15,
            "watchlist_refresh_override": 15,
            "portfolio_refresh_override": 10,
            "news_refresh_override": 20,
            "news_lookback_hours": 6,
            "news_max_articles": 10,
            "frontend_poll_interval": 30,
            "watchlist_refresh_minutes": 15,
            "watchlist_auto_expand": False,
            "watchlist_price_weight": 50.0,
            "watchlist_technical_weight": 50.0,
            "watchlist_show_news": True,
            "display_timezone": "America/New_York",
        },
    )

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = None
    mock_storage = MagicMock()
    mock_storage.connection.return_value = connection
    monkeypatch.setattr("app.services.preferences_service.get_storage", lambda: mock_storage)
    automation_update = MagicMock()
    monkeypatch.setattr("app.services.preferences_service._update_automation_preferences", automation_update)

    updated = update_preferences(
        PreferencesUpdate(
            watchlist_refresh_override=None,
            portfolio_refresh_override=None,
            news_refresh_override=None,
        )
    )

    assert updated["watchlist_refresh_override"] is None
    assert updated["portfolio_refresh_override"] is None
    assert updated["news_refresh_override"] is None
    automation_update.assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("default_refresh_minutes", 10),
        ("watchlist_refresh_override", 10),
        ("watchlist_refresh_minutes", 10),
    ],
)
def test_preferences_update_rejects_watchlist_refresh_values_below_floor(
    field_name: str, field_value: int
) -> None:
    with pytest.raises(ValidationError):
        PreferencesUpdate(**{field_name: field_value})


def test_dict_to_preferences_response_clamps_legacy_watchlist_refresh_values(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.preferences_service.get_rules",
        lambda: SimpleNamespace(
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
            "default_refresh_minutes": 5,
            "watchlist_refresh_override": 3,
            "portfolio_refresh_override": None,
            "news_refresh_override": None,
            "news_lookback_hours": 6,
            "news_max_articles": 10,
            "frontend_poll_interval": 30,
            "watchlist_refresh_minutes": 1,
            "watchlist_auto_expand": False,
            "watchlist_price_weight": 50.0,
            "watchlist_technical_weight": 50.0,
            "display_timezone": "America/New_York",
            "watchlist_show_news": True,
        }
    )

    assert response.default_refresh_minutes == 15
    assert response.watchlist_refresh_override == 15
    assert response.watchlist_refresh_minutes == 15


def test_update_preferences_allows_clearing_automation_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.preferences_service.get_or_create_preferences",
        lambda: {
            "id": "default",
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
            "watchlist_show_news": True,
            "display_timezone": "America/New_York",
            "thesis_generation_enabled": True,
            "auto_remove_on_invalidation": False,
            "auto_trim_enabled": True,
            "scheduled_jenny_operator_enabled": True,
            "scheduled_ml_labeling_enabled": True,
            "scheduled_strategy_research_enabled": True,
        },
    )

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = None
    mock_storage = MagicMock()
    mock_storage.connection.return_value = connection
    monkeypatch.setattr("app.services.preferences_service.get_storage", lambda: mock_storage)
    automation_update = MagicMock()
    monkeypatch.setattr("app.services.preferences_service._update_automation_preferences", automation_update)

    updated = update_preferences(
        PreferencesUpdate(
            thesis_generation_enabled=None,
            auto_remove_on_invalidation=None,
            auto_trim_enabled=None,
            scheduled_jenny_operator_enabled=None,
            scheduled_ml_labeling_enabled=None,
            scheduled_strategy_research_enabled=None,
        )
    )

    assert updated["thesis_generation_enabled"] is None
    assert updated["auto_remove_on_invalidation"] is None
    assert updated["auto_trim_enabled"] is None
    automation_update.assert_called_once_with(
        {
            "thesis_generation_enabled": None,
            "auto_remove_on_invalidation": None,
            "auto_trim_enabled": None,
            "scheduled_jenny_operator_enabled": None,
            "scheduled_ml_labeling_enabled": None,
            "scheduled_strategy_research_enabled": None,
        }
    )
