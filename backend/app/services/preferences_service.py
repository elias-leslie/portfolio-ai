"""Business logic for user preferences."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, cast

from app.models.preferences import (
    DEFAULT_NEWS_LOOKBACK_HOURS,
    DEFAULT_NEWS_MAX_ARTICLES,
    DEFAULT_PREFERENCES,
    MIN_WATCHLIST_REFRESH_MINUTES,
    PreferencesResponse,
    PreferencesUpdate,
    ScannerFanoutSettings,
    ScoringWeightsUpdate,
    clamp_optional_watchlist_refresh_minutes,
    clamp_watchlist_refresh_minutes,
)
from app.rules.loader import get_rules
from app.storage import get_storage

USER_ID = "default"

AUTOMATION_PREFERENCE_KEYS = (
    "thesis_generation_enabled",
    "auto_remove_on_invalidation",
    "auto_trim_enabled",
    "scheduled_jenny_operator_enabled",
    "scheduled_ml_labeling_enabled",
    "scheduled_strategy_research_enabled",
)

# Scanner-fanout (L3 committee) runtime knobs. Each DB column is nullable;
# when NULL we fall back to the env var, then to the hard-coded default.
SCANNER_FANOUT_DEFAULTS: dict[str, int | bool] = {
    "scanner_fanout_enabled": True,
    "scanner_fanout_top_n": 25,
    "scanner_fanout_tier1_keep": 8,
    "scanner_fanout_max_daily": 25,
    "scanner_fanout_cache_ttl_hours": 24,
}
SCANNER_FANOUT_ENV_VARS: dict[str, str] = {
    "scanner_fanout_enabled": "SCANNER_FANOUT_ENABLED",
    "scanner_fanout_top_n": "COMMITTEE_FANOUT_TOP_N",
    "scanner_fanout_tier1_keep": "COMMITTEE_TIER1_KEEP",
    "scanner_fanout_max_daily": "COMMITTEE_FANOUT_MAX_DAILY",
    "scanner_fanout_cache_ttl_hours": "COMMITTEE_FANOUT_CACHE_TTL_HOURS",
}
SCANNER_FANOUT_INT_KEYS = (
    "scanner_fanout_top_n",
    "scanner_fanout_tier1_keep",
    "scanner_fanout_max_daily",
    "scanner_fanout_cache_ttl_hours",
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
        "scheduled_jenny_operator_enabled": False,
        "scheduled_ml_labeling_enabled": False,
        "scheduled_strategy_research_enabled": False,
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
            [USER_ID],
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
                scheduled_jenny_operator_enabled,
                scheduled_ml_labeling_enabled,
                scheduled_strategy_research_enabled,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [USER_ID, None, None, None, None, None, None, now, now],
        )
        conn.commit()

    return {
        "id": USER_ID,
        "thesis_generation_enabled": None,
        "auto_remove_on_invalidation": None,
        "auto_trim_enabled": None,
        "scheduled_jenny_operator_enabled": None,
        "scheduled_ml_labeling_enabled": None,
        "scheduled_strategy_research_enabled": None,
        "scanner_fanout_enabled": None,
        "scanner_fanout_top_n": None,
        "scanner_fanout_tier1_keep": None,
        "scanner_fanout_max_daily": None,
        "scanner_fanout_cache_ttl_hours": None,
        "created_at": now,
        "updated_at": now,
    }


def dict_to_preferences_response(prefs: dict[str, Any]) -> PreferencesResponse:
    """Convert preferences dict to PreferencesResponse with proper defaults."""
    normalized = _normalize_watchlist_refresh_preferences(dict(prefs))
    automation = get_automation_preferences(prefs)

    def _bool_or(key: str, default: bool) -> bool:
        val = normalized.get(key)
        return bool(val) if val is not None else default

    return PreferencesResponse(
        risk_tolerance=int(normalized.get("risk_tolerance") or 5),
        allow_long=_bool_or("allow_long", True),
        allow_short=_bool_or("allow_short", False),
        allow_options=_bool_or("allow_options", False),
        allow_crypto=_bool_or("allow_crypto", False),
        allow_futures=_bool_or("allow_futures", False),
        max_position_size_pct=float(normalized.get("max_position_size_pct") or 10.0),
        default_refresh_minutes=int(normalized["default_refresh_minutes"]),
        watchlist_refresh_override=normalized.get("watchlist_refresh_override"),
        portfolio_refresh_override=normalized.get("portfolio_refresh_override"),
        news_refresh_override=normalized.get("news_refresh_override"),
        news_lookback_hours=int(normalized.get("news_lookback_hours") or DEFAULT_NEWS_LOOKBACK_HOURS),
        news_max_articles=int(normalized.get("news_max_articles") or DEFAULT_NEWS_MAX_ARTICLES),
        frontend_poll_interval=int(
            normalized["frontend_poll_interval"]
            if normalized.get("frontend_poll_interval") is not None
            else 30
        ),
        watchlist_refresh_minutes=int(normalized["watchlist_refresh_minutes"]),
        watchlist_auto_expand=_bool_or("watchlist_auto_expand", False),
        watchlist_price_weight=float(normalized.get("watchlist_price_weight") or 50.0),
        watchlist_technical_weight=float(normalized.get("watchlist_technical_weight") or 50.0),
        display_timezone=str(normalized.get("display_timezone") or "America/New_York"),
        watchlist_show_news=_bool_or("watchlist_show_news", True),
        thesis_generation_enabled=bool(automation["thesis_generation_enabled"]["enabled"]),
        auto_remove_on_invalidation=bool(automation["auto_remove_on_invalidation"]["enabled"]),
        auto_trim_enabled=bool(automation["auto_trim_enabled"]["enabled"]),
        scheduled_jenny_operator_enabled=bool(automation["scheduled_jenny_operator_enabled"]["enabled"]),
        scheduled_ml_labeling_enabled=bool(automation["scheduled_ml_labeling_enabled"]["enabled"]),
        scheduled_strategy_research_enabled=bool(automation["scheduled_strategy_research_enabled"]["enabled"]),
    )


def _fetch_existing_preferences() -> dict[str, Any] | None:
    """Query user_preferences for the default user, falling back to the most recent row."""
    with get_storage().connection() as conn:
        result_df = conn.execute(
            "SELECT * FROM user_preferences WHERE id = %s", [USER_ID]
        ).fetchdf()
        if not result_df.is_empty():
            return cast(dict[str, Any], result_df.row(0, named=True))

        legacy_df = conn.execute(
            "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
        ).fetchdf()
        if not legacy_df.is_empty():
            return cast(dict[str, Any], legacy_df.row(0, named=True))

    return None


def _insert_default_preferences() -> None:
    """Insert the default preference row for the default user."""
    now = datetime.now(UTC)
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
                USER_ID,
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
                now,
                now,
            ],
        )
        conn.commit()


def get_or_create_preferences() -> dict[str, str | int | float | bool | datetime | None]:
    """Get existing preferences or create default ones."""
    row = _fetch_existing_preferences()

    if row is not None:
        if "watchlist_show_news" not in row:
            row["watchlist_show_news"] = True
        if "news_lookback_hours" not in row or row["news_lookback_hours"] is None:
            row["news_lookback_hours"] = DEFAULT_NEWS_LOOKBACK_HOURS
        if "news_max_articles" not in row or row["news_max_articles"] is None:
            row["news_max_articles"] = DEFAULT_NEWS_MAX_ARTICLES
        return _normalize_watchlist_refresh_preferences(dict(row))

    _insert_default_preferences()
    return {
        "id": USER_ID,
        **DEFAULT_PREFERENCES,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


def _apply_preference_updates(
    current: dict[str, Any],
    update: PreferencesUpdate,
) -> tuple[dict[str, Any], dict[str, bool | None]]:
    """Apply fields from update onto current preferences dict.

    Returns the mutated current dict and any automation-related updates.
    """
    provided_fields = update.model_fields_set
    automation_updates: dict[str, bool | None] = {}

    simple_fields = [
        "risk_tolerance", "allow_long", "allow_short", "allow_options",
        "allow_crypto", "allow_futures", "max_position_size_pct",
        "default_refresh_minutes", "news_lookback_hours", "news_max_articles",
        "frontend_poll_interval", "watchlist_refresh_minutes",
        "watchlist_auto_expand", "watchlist_price_weight",
        "watchlist_technical_weight", "display_timezone", "watchlist_show_news",
    ]
    for field in simple_fields:
        value = getattr(update, field, None)
        if value is not None:
            current[field] = value

    nullable_override_fields = [
        "watchlist_refresh_override",
        "portfolio_refresh_override",
        "news_refresh_override",
    ]
    for field in nullable_override_fields:
        if field in provided_fields:
            current[field] = getattr(update, field)

    for key in AUTOMATION_PREFERENCE_KEYS:
        if key in provided_fields:
            value = getattr(update, key)
            current[key] = value
            automation_updates[key] = value

    return current, automation_updates


_UPDATE_PREFERENCES_SQL = """
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
"""


def _preferences_update_params(current: dict[str, Any]) -> list[Any]:
    """Build the ordered parameter list for _UPDATE_PREFERENCES_SQL."""
    return [
        current["risk_tolerance"], current["allow_long"], current["allow_short"],
        current["allow_options"], current["allow_crypto"], current["allow_futures"],
        current["max_position_size_pct"], current["default_refresh_minutes"],
        current["watchlist_refresh_override"], current["portfolio_refresh_override"],
        current["news_refresh_override"],
        current.get("news_lookback_hours", DEFAULT_NEWS_LOOKBACK_HOURS),
        current.get("news_max_articles", DEFAULT_NEWS_MAX_ARTICLES),
        current["frontend_poll_interval"], current["watchlist_refresh_minutes"],
        current["watchlist_auto_expand"], current["watchlist_price_weight"],
        current["watchlist_technical_weight"],
        current.get("watchlist_show_news", True),
        current["display_timezone"], datetime.now(UTC), current["id"],
    ]


def _save_preferences_to_db(current: dict[str, Any]) -> None:
    """Persist the current preferences dict to the database."""
    params = _preferences_update_params(current)
    with get_storage().connection() as conn:
        conn.execute(_UPDATE_PREFERENCES_SQL, params)
        conn.commit()


def update_preferences(update: PreferencesUpdate) -> dict[str, Any]:
    """Update user preferences and return updated dict."""
    current = get_or_create_preferences()
    current, automation_updates = _apply_preference_updates(current, update)
    current = _normalize_watchlist_refresh_preferences(current)
    _save_preferences_to_db(current)

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
                scheduled_jenny_operator_enabled = %s,
                scheduled_ml_labeling_enabled = %s,
                scheduled_strategy_research_enabled = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                current.get("thesis_generation_enabled"),
                current.get("auto_remove_on_invalidation"),
                current.get("auto_trim_enabled"),
                current.get("scheduled_jenny_operator_enabled"),
                current.get("scheduled_ml_labeling_enabled"),
                current.get("scheduled_strategy_research_enabled"),
                datetime.now(UTC),
                current["id"],
            ],
        )
        conn.commit()


def _coalesce_bool(stored: Any, env_var: str | None, default: bool) -> bool:
    if stored is not None:
        return bool(stored)
    if env_var:
        raw = os.environ.get(env_var)
        if raw is not None:
            lowered = raw.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
    return default


def _coalesce_int(stored: Any, env_var: str | None, default: int) -> int:
    if stored is not None:
        try:
            return int(stored)
        except (TypeError, ValueError):
            pass
    if env_var:
        raw = os.environ.get(env_var)
        if raw:
            try:
                return max(0, int(raw))
            except ValueError:
                pass
    return default


def get_scanner_fanout_settings() -> ScannerFanoutSettings:
    """Resolve scanner-fanout settings with DB → env → constant fallback."""
    row = get_or_create_automation_preferences()
    enabled_default = bool(SCANNER_FANOUT_DEFAULTS["scanner_fanout_enabled"])
    return ScannerFanoutSettings(
        enabled=_coalesce_bool(
            row.get("scanner_fanout_enabled"),
            SCANNER_FANOUT_ENV_VARS["scanner_fanout_enabled"],
            enabled_default,
        ),
        top_n=_coalesce_int(
            row.get("scanner_fanout_top_n"),
            SCANNER_FANOUT_ENV_VARS["scanner_fanout_top_n"],
            int(SCANNER_FANOUT_DEFAULTS["scanner_fanout_top_n"]),
        ),
        tier1_keep=_coalesce_int(
            row.get("scanner_fanout_tier1_keep"),
            SCANNER_FANOUT_ENV_VARS["scanner_fanout_tier1_keep"],
            int(SCANNER_FANOUT_DEFAULTS["scanner_fanout_tier1_keep"]),
        ),
        max_daily=_coalesce_int(
            row.get("scanner_fanout_max_daily"),
            SCANNER_FANOUT_ENV_VARS["scanner_fanout_max_daily"],
            int(SCANNER_FANOUT_DEFAULTS["scanner_fanout_max_daily"]),
        ),
        cache_ttl_hours=_coalesce_int(
            row.get("scanner_fanout_cache_ttl_hours"),
            SCANNER_FANOUT_ENV_VARS["scanner_fanout_cache_ttl_hours"],
            int(SCANNER_FANOUT_DEFAULTS["scanner_fanout_cache_ttl_hours"]),
        ),
    )


def update_scanner_fanout_settings(
    settings: ScannerFanoutSettings,
) -> ScannerFanoutSettings:
    """Persist the full scanner-fanout settings shape (PUT semantics)."""
    get_or_create_automation_preferences()
    with get_storage().connection() as conn:
        conn.execute(
            """
            UPDATE automation_preferences
            SET scanner_fanout_enabled = %s,
                scanner_fanout_top_n = %s,
                scanner_fanout_tier1_keep = %s,
                scanner_fanout_max_daily = %s,
                scanner_fanout_cache_ttl_hours = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                settings.enabled,
                settings.top_n,
                settings.tier1_keep,
                settings.max_daily,
                settings.cache_ttl_hours,
                datetime.now(UTC),
                USER_ID,
            ],
        )
        conn.commit()
    return get_scanner_fanout_settings()


def get_scoring_weights() -> ScoringWeightsUpdate:
    """Get current scoring weights (4-pillar system)."""
    with get_storage().connection() as conn:
        result_df = conn.execute(
            "SELECT watchlist_score_weights FROM user_preferences WHERE id = %s LIMIT 1",
            [USER_ID],
        ).fetchdf()

    default_weights = ScoringWeightsUpdate(price=25.0, technical=25.0, fundamental=30.0, catalyst=20.0)

    if result_df.is_empty():
        return default_weights

    weights_json = result_df.row(0, named=True).get("watchlist_score_weights")
    if not weights_json:
        return default_weights

    return ScoringWeightsUpdate(
        price=float(weights_json.get("price", 25.0)),
        technical=float(weights_json.get("technical", 25.0)),
        fundamental=float(weights_json.get("fundamental", 30.0)),
        catalyst=float(weights_json.get("catalyst", 20.0)),
    )


def update_scoring_weights(weights: ScoringWeightsUpdate) -> ScoringWeightsUpdate:
    """Update scoring weights (4-pillar system)."""
    get_or_create_preferences()

    weights_json = {
        "price": weights.price,
        "technical": weights.technical,
        "fundamental": weights.fundamental,
        "catalyst": weights.catalyst,
    }

    with get_storage().connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET watchlist_score_weights = %s::jsonb,
                updated_at = %s
            WHERE id = %s
            """,
            [str(weights_json).replace("'", '"'), datetime.now(UTC), USER_ID],
        )
        conn.commit()

    return weights
