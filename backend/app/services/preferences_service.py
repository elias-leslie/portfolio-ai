"""Business logic for user preferences."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from app.models.preferences import (
    DEFAULT_NEWS_LOOKBACK_HOURS,
    DEFAULT_NEWS_MAX_ARTICLES,
    DEFAULT_PREFERENCES,
    PreferencesResponse,
    PreferencesUpdate,
    ScoringWeightsUpdate,
)
from app.storage import get_storage

storage = get_storage()


def dict_to_preferences_response(prefs: dict[str, Any]) -> PreferencesResponse:
    """Convert preferences dict to PreferencesResponse with proper defaults."""
    return PreferencesResponse(
        risk_tolerance=int(prefs.get("risk_tolerance") or 5),
        allow_long=bool(prefs.get("allow_long")) if prefs.get("allow_long") is not None else True,
        allow_short=bool(prefs.get("allow_short"))
        if prefs.get("allow_short") is not None
        else False,
        allow_options=bool(prefs.get("allow_options"))
        if prefs.get("allow_options") is not None
        else False,
        allow_crypto=bool(prefs.get("allow_crypto"))
        if prefs.get("allow_crypto") is not None
        else False,
        allow_futures=bool(prefs.get("allow_futures"))
        if prefs.get("allow_futures") is not None
        else False,
        max_position_size_pct=float(prefs.get("max_position_size_pct") or 10.0),
        default_refresh_minutes=int(prefs.get("default_refresh_minutes") or 15),
        watchlist_refresh_override=prefs.get("watchlist_refresh_override"),
        portfolio_refresh_override=prefs.get("portfolio_refresh_override"),
        news_refresh_override=prefs.get("news_refresh_override"),
        news_lookback_hours=int(prefs.get("news_lookback_hours") or DEFAULT_NEWS_LOOKBACK_HOURS),
        news_max_articles=int(prefs.get("news_max_articles") or DEFAULT_NEWS_MAX_ARTICLES),
        frontend_poll_interval=int(prefs.get("frontend_poll_interval") or 30),
        watchlist_refresh_minutes=int(prefs.get("watchlist_refresh_minutes") or 15),
        watchlist_auto_expand=bool(prefs.get("watchlist_auto_expand"))
        if prefs.get("watchlist_auto_expand") is not None
        else False,
        watchlist_price_weight=float(prefs.get("watchlist_price_weight") or 50.0),
        watchlist_technical_weight=float(prefs.get("watchlist_technical_weight") or 50.0),
        display_timezone=str(prefs.get("display_timezone") or "America/New_York"),
        watchlist_show_news=bool(prefs.get("watchlist_show_news"))
        if prefs.get("watchlist_show_news") is not None
        else True,
    )


def get_or_create_preferences() -> dict[str, str | int | float | bool | datetime | None]:
    """Get existing preferences or create default ones."""
    user_id = "default"

    row: dict[str, str | int | float | bool | datetime | None] | None = None

    with storage.connection() as conn:
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
        return dict(row)

    # Create default preferences
    with storage.connection() as conn:
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
    if update.watchlist_refresh_override is not None:
        current["watchlist_refresh_override"] = update.watchlist_refresh_override
    if update.portfolio_refresh_override is not None:
        current["portfolio_refresh_override"] = update.portfolio_refresh_override
    if update.news_refresh_override is not None:
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

    # Save to database
    with storage.connection() as conn:
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

    return current


def get_scoring_weights() -> ScoringWeightsUpdate:
    """Get current scoring weights (4-pillar system)."""
    user_id = "default"

    with storage.connection() as conn:
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
    with storage.connection() as conn:
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
