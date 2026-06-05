"""Data loaders for watchlist service.

Helper functions for loading technical indicators, preferences, and related data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..logging_config import get_logger
from ..models.preferences import clamp_watchlist_refresh_minutes
from ..storage import PortfolioStorage
from ..utils.preferences_loader import get_user_scoring_weights
from .models import ScoreWeights, TechnicalSnapshot

logger = get_logger(__name__)


def load_latest_technical(
    storage: PortfolioStorage, symbols: list[str]
) -> dict[str, TechnicalSnapshot]:
    """Load latest technical indicators for symbols.

    Args:
        storage: PortfolioStorage instance
        symbols: List of symbols

    Returns:
        Dict mapping symbol to TechnicalSnapshot
    """
    if not symbols:
        return {}

    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip())
    )
    if not normalized_symbols:
        return {}

    placeholders = ",".join(["?"] * len(normalized_symbols))
    df = storage.query(
        f"""
        WITH latest_technical AS (
            SELECT DISTINCT ON (symbol)
                *,
                symbol AS normalized_symbol
            FROM technical_indicators
            WHERE symbol IN ({placeholders})
            ORDER BY symbol, date DESC
        ),
        latest_bars AS (
            SELECT DISTINCT ON (symbol)
                symbol AS normalized_symbol,
                date AS vwap_date,
                vwap
            FROM day_bars
            WHERE symbol IN ({placeholders})
              AND vwap IS NOT NULL
              AND vwap::text <> 'NaN'
              AND vwap > 0
            ORDER BY symbol, date DESC
        )
        SELECT
            latest_technical.*,
            CASE
                WHEN latest_bars.vwap_date = latest_technical.date THEN latest_bars.vwap
                ELSE NULL
            END AS vwap,
            CASE
                WHEN latest_bars.vwap_date = latest_technical.date THEN latest_bars.vwap_date
                ELSE NULL
            END AS vwap_date
        FROM latest_technical
        LEFT JOIN latest_bars USING (normalized_symbol)
        """,
        [*normalized_symbols, *normalized_symbols],
    )

    if df.is_empty():
        return {}

    snapshots: dict[str, TechnicalSnapshot] = {}
    for row in df.iter_rows(named=True):
        calculated_at = row.get("calculated_at")
        if isinstance(calculated_at, datetime) and calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=UTC)
        snapshots[str(row["symbol"]).upper()] = TechnicalSnapshot(
            rsi_14=row.get("rsi_14"),
            sma_20=row.get("sma_20"),
            sma_5=row.get("sma_5"),
            sma_50=row.get("sma_50"),
            sma_200=row.get("sma_200"),
            ema_20=row.get("ema_20"),
            ema_50=row.get("ema_50"),
            ema_200=row.get("ema_200"),
            macd=row.get("macd"),
            macd_signal=row.get("macd_signal"),
            bb_upper=row.get("bb_upper"),
            bb_middle=row.get("bb_middle"),
            bb_lower=row.get("bb_lower"),
            stoch_k=row.get("stoch_k"),
            stoch_d=row.get("stoch_d"),
            vwap=row.get("vwap"),
            vwap_date=row.get("vwap_date"),
            price=None,
            calculated_at=calculated_at,
        )
    return snapshots


def load_default_weights(storage: PortfolioStorage, user_id: str | None = None) -> ScoreWeights:
    """Load score weights from user preferences (4-pillar system).

    This function now loads from the watchlist_score_weights JSONB column,
    which supports all 4 pillars: price, technical, fundamental, catalyst.

    Args:
        storage: PortfolioStorage instance
        user_id: User ID to fetch preferences for (defaults to 'default')

    Returns:
        ScoreWeights with all 4 pillar weights (price/technical/fundamental/catalyst)
    """
    return get_user_scoring_weights(storage, user_id)


def load_stale_ttl_minutes(storage: PortfolioStorage) -> int:
    """Load stale TTL from preferences (3x refresh interval).

    Args:
        storage: PortfolioStorage instance

    Returns:
        TTL in minutes for stale score detection
    """
    df = storage.query(
        """
        SELECT watchlist_refresh_override, default_refresh_minutes
        FROM user_preferences
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )

    if df.is_empty():
        # Default: 3x of 15 minutes = 45 minutes
        return 45

    row = df.to_dicts()[0]
    refresh_minutes = clamp_watchlist_refresh_minutes(
        row.get("watchlist_refresh_override") or row.get("default_refresh_minutes", 15)
    )

    # Stale = 3x refresh interval
    return refresh_minutes * 3
