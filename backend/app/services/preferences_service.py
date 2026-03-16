"""Business logic for user preferences."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from app.models.preferences import (
    DEFAULT_NEWS_LOOKBACK_HOURS,
    DEFAULT_NEWS_MAX_ARTICLES,
    DEFAULT_PREFERENCES,
    MIN_WATCHLIST_REFRESH_MINUTES,
    PreferencesResponse,
    PreferencesUpdate,
    ScoringWeightsUpdate,
    clamp_optional_watchlist_refresh_minutes,
    clamp_watchlist_refresh_minutes,
)
from app.rules.loader import get_rules
from app.storage import get_storage

AUTOMATION_PREFERENCE_KEYS = (
    "thesis_generation_enabled",
    "auto_remove_on_invalidation",
    "auto_trim_enabled",
)


def _normalize_watchlist_refresh_preferences(prefs: dict[str, Any]) -> dict[str, Any]:
    """Clamp legacy watchlist refresh values to the supported product floor."""
    prefs["default_refresh_minutes"] = clamp_watchlist_refresh_minutes(
        int(prefs.get("default_refresh_minutes") or MIN_WATCHLIST_REFRESH_MINUTES)
    )
    prefs["watchlist_refresh_override"] = clamp_optional_watchlist_refresh_minutes(
        prefs.get("watchlist_refresh_override")
    )
    prefs["watchlist_refresh_minutes"] = clamp_watchlist_refresh_minutes(
        int(prefs.get("watchlist_refresh_minutes") or MIN_WATCHLIST_REFRESH_MINUTES)
    )
    return prefs


def get_automation_defaults() -> dict[str, bool]:
    """Return automation defaults from trading rules."""
    rules = get_rules()
    return {
        "thesis_generation_enabled": rules.thesis_management.thesis_generation_enabled,
        "auto_remove_on_invalidation": rules.thesis_management.auto_remove_on_invalidation,
        "auto_trim_enabled": rules.watchlist_management.auto_trim_enabled,
    }


def get_automation_preferences(
    prefs: dict[str, Any] | None = None,
) -> dict[str, dict[str, bool | str]]:
    """Resolve runtime automation settings from preferences with rule fallbacks."""
    defaults = get_automation_defaults()
    current = get_or_create_automation_preferences()
    if prefs is not None:
        for key in AUTOMATION_PREFERENCE_KEYS:
            if key in prefs:
                current[key] = prefs.get(key)
    resolved: dict[str, dict[str, bool | str]] = {}
    for key, default_value in defaults.items():
        stored_value = current.get(key)
        resolved[key] = {
            "enabled": bool(stored_value) if stored_value is not None else default_value,
            "source": "preferences" if stored_value is not None else "rules_default",
        }
    return resolved


def get_or_create_automation_preferences() -> dict[str, Any]:
    """Get or create runtime automation override settings."""
    row: dict[str, Any] | None = None

    with get_storage().connection() as conn:
        result_df = conn.execute(
            "SELECT * FROM automation_preferences WHERE id = %s",
            ["default"],
        ).fetchdf()
        if not result_df.is_empty():
            row = cast(dict[str, Any], result_df.row(0, named=True))

    if row is not None:
        return dict(row)

    now = datetime.now(UTC)
    with get_storage().connection() as conn:
        conn.execute(
            """
            INSERT INTO automation_preferences (
                id,
                thesis_generation_enabled,
                auto_remove_on_invalidation,
                auto_trim_enabled,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ["default", None, None, None, now, now],
        )
        conn.commit()

    return {
        "id": "default",
        "thesis_generation_enabled": None,
        "auto_remove_on_invalidation": None,
        "auto_trim_enabled": None,
        "created_at": now,
        "updated_at": now,
    }


def dict_to_preferences_response(prefs: dict[str, Any]) -> PreferencesResponse:
    """Convert preferences dict to PreferencesResponse with proper defaults."""
    normalized = _normalize_watchlist_refresh_preferences(dict(prefs))
    automation = get_automation_preferences(prefs)
    return PreferencesResponse(
        risk_tolerance=int(normalized.get("risk_tolerance") or 5),
        allow_long=bool(normalized.get("allow_long")) if normalized.get("allow_long") is not None else True,
        allow_short=bool(normalized.get("allow_short"))
        if normalized.get("allow_short") is not None
        else False,
        allow_options=bool(normalized.get("allow_options"))
        if normalized.get("allow_options") is not None
        else False,
        allow_crypto=bool(normalized.get("allow_crypto"))
        if normalized.get("allow_crypto") is not None
        else False,
        allow_futures=bool(normalized.get("allow_futures"))
        if normalized.get("allow_futures") is not None
        else False,
        max_position_size_pct=float(normalized.get("max_position_size_pct") or 10.0),
        default_refresh_minutes=int(normalized["default_refresh_minutes"]),
        watchlist_refresh_override=normalized.get("watchlist_refresh_override"),
        portfolio_refresh_override=normalized.get("portfolio_refresh_override"),
        news_refresh_override=normalized.get("news_refresh_override"),
        news_lookback_hours=int(normalized.get("news_lookback_hours") or DEFAULT_NEWS_LOOKBACK_HOURS),
        news_max_articles=int(normalized.get("news_max_articles") or DEFAULT_NEWS_MAX_ARTICLES),
        frontend_poll_interval=int(normalized.get("frontend_poll_interval") or 30),
        watchlist_refresh_minutes=int(normalized["watchlist_refresh_minutes"]),
        watchlist_auto_expand=bool(normalized.get("watchlist_auto_expand"))
        if normalized.get("watchlist_auto_expand") is not None
        else False,
        watchlist_price_weight=float(normalized.get("watchlist_price_weight") or 50.0),
        watchlist_technical_weight=float(normalized.get("watchlist_technical_weight") or 50.0),
        display_timezone=str(normalized.get("display_timezone") or "America/New_York"),
        watchlist_show_news=bool(normalized.get("watchlist_show_news"))
        if normalized.get("watchlist_show_news") is not None
        else True,
        thesis_generation_enabled=bool(automation["thesis_generation_enabled"]["enabled"]),
        auto_remove_on_invalidation=bool(automation["auto_remove_on_invalidation"]["enabled"]),
        auto_trim_enabled=bool(automation["auto_trim_enabled"]["enabled"]),
    )


def get_or_create_preferences() -> dict[str, str | int | float | bool | datetime | None]:
    """Get existing preferences or create default ones."""
    user_id = "default"

    row: dict[str, str | int | float | bool | datetime | None] | None = None

    with get_storage().connection() as conn:
        result_df = conn.execute(
            "SELECT * FROM user_preferences WHERE id = %s", [user_id]
        ).fetchdf()
        if not result_df.is_empty():
            row = cast(
                dict[str, str | int | float | bool | datetime | None], result_df.row(0, named=True)
            )
        else:
            # Legacy fallback: use most recent preferences regardless of ID
            legacy_df = conn.execute(
                "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
            ).fetchdf()
            if not legacy_df.is_empty():
                row = cast(
                    dict[str, str | int | float | bool | datetime | None],
                    legacy_df.row(0, named=True),
                )

    if row is not None:
        if "watchlist_show_news" not in row:
            row["watchlist_show_news"] = True
        if "news_lookback_hours" not in row or row["news_lookback_hours"] is None:
            row["news_lookback_hours"] = DEFAULT_NEWS_LOOKBACK_HOURS
        if "news_max_articles" not in row or row["news_max_articles"] is None:
            row["news_max_articles"] = DEFAULT_NEWS_MAX_ARTICLES
        return _normalize_watchlist_refresh_preferences(dict(row))

    # Create default preferences
    with get_storage().connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                default_refresh_minutes, watchlist_refresh_override,
                portfolio_refresh_override, news_refresh_override,
                news_lookback_hours, news_max_articles, frontend_poll_interval,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                watchlist_show_news,
                display_timezone,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                user_id,
                5,
                True,
                False,
                False,
                False,
                False,
                10.0,
                15,  # default_refresh_minutes
                None,  # watchlist_refresh_override
                None,  # portfolio_refresh_override
                None,  # news_refresh_override
                DEFAULT_NEWS_LOOKBACK_HOURS,
                DEFAULT_NEWS_MAX_ARTICLES,
                30,  # frontend_poll_interval
                15,  # watchlist_refresh_minutes (legacy)
                False,
                50.0,
                50.0,
                True,
                "America/New_York",
                datetime.now(UTC),
                datetime.now(UTC),
            ],
        )
        conn.commit()

    return {
        "id": user_id,
        **DEFAULT_PREFERENCES,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def update_preferences(update: PreferencesUpdate) -> dict[str, Any]:
    """Update user preferences and return updated dict."""
    current = get_or_create_preferences()
    automation_updates: dict[str, bool | None] = {}
    provided_fields = update.model_fields_set

    # Update fields
    if update.risk_tolerance is not None:
        current["risk_tolerance"] = update.risk_tolerance
    if update.allow_long is not None:
        current["allow_long"] = update.allow_long
    if update.allow_short is not None:
        current["allow_short"] = update.allow_short
    if update.allow_options is not None:
        current["allow_options"] = update.allow_options
    if update.allow_crypto is not None:
        current["allow_crypto"] = update.allow_crypto
    if update.allow_futures is not None:
        current["allow_futures"] = update.allow_futures
    if update.max_position_size_pct is not None:
        current["max_position_size_pct"] = update.max_position_size_pct
    if update.default_refresh_minutes is not None:
        current["default_refresh_minutes"] = update.default_refresh_minutes
    if "watchlist_refresh_override" in provided_fields:
        current["watchlist_refresh_override"] = update.watchlist_refresh_override
    if "portfolio_refresh_override" in provided_fields:
        current["portfolio_refresh_override"] = update.portfolio_refresh_override
    if "news_refresh_override" in provided_fields:
        current["news_refresh_override"] = update.news_refresh_override
    if update.news_lookback_hours is not None:
        current["news_lookback_hours"] = update.news_lookback_hours
    if update.news_max_articles is not None:
        current["news_max_articles"] = update.news_max_articles
    if update.frontend_poll_interval is not None:
        current["frontend_poll_interval"] = update.frontend_poll_interval
    if update.watchlist_refresh_minutes is not None:
        current["watchlist_refresh_minutes"] = update.watchlist_refresh_minutes
    if update.watchlist_auto_expand is not None:
        current["watchlist_auto_expand"] = update.watchlist_auto_expand
    if update.watchlist_price_weight is not None:
        current["watchlist_price_weight"] = update.watchlist_price_weight
    if update.watchlist_technical_weight is not None:
        current["watchlist_technical_weight"] = update.watchlist_technical_weight
    if update.display_timezone is not None:
        current["display_timezone"] = update.display_timezone
    if update.watchlist_show_news is not None:
        current["watchlist_show_news"] = update.watchlist_show_news
    if "thesis_generation_enabled" in provided_fields:
        current["thesis_generation_enabled"] = update.thesis_generation_enabled
        automation_updates["thesis_generation_enabled"] = update.thesis_generation_enabled
    if "auto_remove_on_invalidation" in provided_fields:
        current["auto_remove_on_invalidation"] = update.auto_remove_on_invalidation
        automation_updates["auto_remove_on_invalidation"] = update.auto_remove_on_invalidation
    if "auto_trim_enabled" in provided_fields:
        current["auto_trim_enabled"] = update.auto_trim_enabled
        automation_updates["auto_trim_enabled"] = update.auto_trim_enabled

    current = _normalize_watchlist_refresh_preferences(current)

    # Save to database
    with get_storage().connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET risk_tolerance = %s,
                allow_long = %s,
                allow_short = %s,
                allow_options = %s,
                allow_crypto = %s,
                allow_futures = %s,
                max_position_size_pct = %s,
                default_refresh_minutes = %s,
                watchlist_refresh_override = %s,
                portfolio_refresh_override = %s,
                news_refresh_override = %s,
                news_lookback_hours = %s,
                news_max_articles = %s,
                frontend_poll_interval = %s,
                watchlist_refresh_minutes = %s,
                watchlist_auto_expand = %s,
                watchlist_price_weight = %s,
                watchlist_technical_weight = %s,
                watchlist_show_news = %s,
                display_timezone = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                current["risk_tolerance"],
                current["allow_long"],
                current["allow_short"],
                current["allow_options"],
                current["allow_crypto"],
                current["allow_futures"],
                current["max_position_size_pct"],
                current["default_refresh_minutes"],
                current["watchlist_refresh_override"],
                current["portfolio_refresh_override"],
                current["news_refresh_override"],
                current.get("news_lookback_hours", DEFAULT_NEWS_LOOKBACK_HOURS),
                current.get("news_max_articles", DEFAULT_NEWS_MAX_ARTICLES),
                current["frontend_poll_interval"],
                current["watchlist_refresh_minutes"],
                current["watchlist_auto_expand"],
                current["watchlist_price_weight"],
                current["watchlist_technical_weight"],
                current.get("watchlist_show_news", True),
                current["display_timezone"],
                datetime.now(UTC),
                current["id"],
            ],
        )
        conn.commit()

    if automation_updates:
        _update_automation_preferences(automation_updates)

    return current


def _update_automation_preferences(updates: dict[str, bool | None]) -> None:
    current = get_or_create_automation_preferences()
    current.update(updates)
    with get_storage().connection() as conn:
        conn.execute(
            """
            UPDATE automation_preferences
            SET thesis_generation_enabled = %s,
                auto_remove_on_invalidation = %s,
                auto_trim_enabled = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                current.get("thesis_generation_enabled"),
                current.get("auto_remove_on_invalidation"),
                current.get("auto_trim_enabled"),
                datetime.now(UTC),
                current["id"],
            ],
        )
        conn.commit()


def get_scoring_weights() -> ScoringWeightsUpdate:
    """Get current scoring weights (4-pillar system)."""
    user_id = "default"

    with get_storage().connection() as conn:
        result_df = conn.execute(
            "SELECT watchlist_score_weights FROM user_preferences WHERE id = %s LIMIT 1",
            [user_id],
        ).fetchdf()

    if result_df.is_empty():
        return ScoringWeightsUpdate(price=25.0, technical=25.0, fundamental=30.0, catalyst=20.0)

    row = result_df.row(0, named=True)
    weights_json = row.get("watchlist_score_weights")

    if not weights_json:
        return ScoringWeightsUpdate(price=25.0, technical=25.0, fundamental=30.0, catalyst=20.0)

    return ScoringWeightsUpdate(
        price=float(weights_json.get("price", 25.0)),
        technical=float(weights_json.get("technical", 25.0)),
        fundamental=float(weights_json.get("fundamental", 30.0)),
        catalyst=float(weights_json.get("catalyst", 20.0)),
    )


def update_scoring_weights(weights: ScoringWeightsUpdate) -> ScoringWeightsUpdate:
    """Update scoring weights (4-pillar system)."""
    user_id = "default"

    # Ensure user preferences exist
    get_or_create_preferences()

    # Build JSONB value for PostgreSQL
    weights_json = {
        "price": weights.price,
        "technical": weights.technical,
        "fundamental": weights.fundamental,
        "catalyst": weights.catalyst,
    }

    # Update the JSONB column
    with get_storage().connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET watchlist_score_weights = %s::jsonb,
                updated_at = %s
            WHERE id = %s
            """,
            [str(weights_json).replace("'", '"'), datetime.now(UTC), user_id],
        )
        conn.commit()

    return weights
