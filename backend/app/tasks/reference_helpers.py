"""Helper functions for reference data tasks.

Contains valuation metrics extraction, cache processing, and per-symbol
computation helpers extracted from reference_tasks.py.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, TypedDict

from app.analytics.financial_health_scores import get_financial_health_scores
from app.analytics.risk_metrics import calculate_symbol_beta, calculate_symbol_var
from app.logging_config import get_logger
from app.repositories import ReferenceRepository
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.formatters import parse_float

logger = get_logger(__name__)


class ValuationMetricsDict(TypedDict, total=False):
    """Valuation metrics extracted from reference data payloads."""

    pe_ratio_trailing: float | None
    pe_ratio_forward: float | None
    ps_ratio: float | None
    pb_ratio: float | None
    peg_ratio: float | None
    dividend_yield: float | None
    payout_ratio: float | None


_VALUATION_COLUMNS = [
    "pe_ratio_trailing",
    "pe_ratio_forward",
    "ps_ratio",
    "pb_ratio",
    "peg_ratio",
    "dividend_yield",
    "payout_ratio",
]

_VALUATION_UPDATE_SQL = """
    UPDATE reference_cache
    SET pe_ratio_trailing = %s, pe_ratio_forward = %s, ps_ratio = %s,
        pb_ratio = %s, peg_ratio = %s, dividend_yield = %s, payout_ratio = %s
    WHERE symbol = %s AND source = %s AND as_of_date = %s
"""

_HEALTH_SCORE_UPDATE_SQL = """
    UPDATE reference_cache
    SET f_score = %s, f_score_components = %s,
        z_score = %s, z_score_zone = %s
    WHERE symbol = %s
      AND as_of_date = (
          SELECT MAX(as_of_date) FROM reference_cache WHERE symbol = %s
      )
"""


def _extract_yfinance_metrics(payload: dict[str, Any]) -> ValuationMetricsDict:
    """Extract valuation metrics from a yfinance-format payload."""
    return {
        "pe_ratio_trailing": payload.get("trailingPE"),
        "pe_ratio_forward": payload.get("forwardPE"),
        "ps_ratio": payload.get("priceToSalesTrailing12Months"),
        "pb_ratio": payload.get("priceToBook"),
        "peg_ratio": payload.get("pegRatio") or payload.get("trailingPegRatio"),
        "dividend_yield": payload.get("dividendYield"),
        "payout_ratio": payload.get("payoutRatio"),
    }


def _extract_alphavantage_metrics(payload: dict[str, Any]) -> ValuationMetricsDict:
    """Extract valuation metrics from an Alpha Vantage-format payload."""
    pe_ratio = parse_float(payload.get("PERatio") or payload.get("TrailingPE"))
    div_per_share = parse_float(payload.get("DividendPerShare"))
    eps = parse_float(payload.get("EPS"))
    payout_ratio = (div_per_share / eps) if (div_per_share and eps and eps > 0) else None
    return {
        "pe_ratio_trailing": pe_ratio,
        "pe_ratio_forward": parse_float(payload.get("ForwardPE")),
        "ps_ratio": parse_float(payload.get("PriceToSalesRatioTTM")),
        "pb_ratio": parse_float(payload.get("PriceToBookRatio")),
        "peg_ratio": parse_float(payload.get("PEGRatio")),
        "dividend_yield": parse_float(payload.get("DividendYield")),
        "payout_ratio": payout_ratio,
    }


def _extract_valuation_metrics(payload: dict[str, Any]) -> ValuationMetricsDict:
    """Extract valuation metrics from JSON payload.

    Supports both yfinance and Alpha Vantage payloads.

    Args:
        payload: JSON payload dict from reference_cache

    Returns:
        Dict with extracted metrics (values are None if not in payload)
    """
    if "trailingPE" in payload or "forwardPE" in payload:
        return _extract_yfinance_metrics(payload)
    if "PERatio" in payload or "PriceToBookRatio" in payload:
        return _extract_alphavantage_metrics(payload)
    return ValuationMetricsDict(
        pe_ratio_trailing=None,
        pe_ratio_forward=None,
        ps_ratio=None,
        pb_ratio=None,
        peg_ratio=None,
        dividend_yield=None,
        payout_ratio=None,
    )


def _update_valuation_metrics(symbol: str, source: str, payload: dict[str, Any]) -> None:
    """Update valuation metrics for a single symbol/source combination."""
    metrics = _extract_valuation_metrics(payload)
    if not any(v is not None for v in metrics.values()):
        logger.debug("no_valuation_metrics_found", symbol=symbol, source=source)
        return

    storage = get_storage()
    repo = ReferenceRepository(storage)
    as_of_date = repo.get_latest_cache_entry_date(symbol, source)
    if as_of_date is None:
        logger.debug("no_cache_entry_found", symbol=symbol, source=source)
        return

    metrics_values = [metrics.get(col) for col in _VALUATION_COLUMNS]
    repo.upsert_dual_write_metrics(
        symbol=symbol,
        as_of_date=as_of_date,
        base_table_update_sql=_VALUATION_UPDATE_SQL,
        base_table_params=[*metrics_values, symbol, source, as_of_date],
        metrics_table="valuation_metrics",
        metrics_columns=_VALUATION_COLUMNS,
        metrics_values=metrics_values,
        conflict_keys=["symbol", "as_of_date"],
    )
    logger.info(
        "valuation_metrics_updated",
        symbol=symbol,
        source=source,
        metrics_count=sum(1 for v in metrics.values() if v is not None),
    )


def _parse_payload(symbol: str, source: str, payload_json: Any) -> dict[str, Any] | None:
    """Parse a payload JSON value into a dict, returning None on error."""
    try:
        payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
    except json.JSONDecodeError:
        logger.warning("invalid_json_payload", symbol=symbol, source=source)
        return None
    if not isinstance(payload, dict):
        logger.debug(
            "skipping_non_dict_payload",
            symbol=symbol,
            source=source,
            payload_type=type(payload).__name__,
        )
        return None
    return payload


def _process_cache_entries() -> tuple[int, int]:
    """Process all cache entries and extract valuation metrics.

    Returns:
        Tuple of (entries_processed, entries_updated)
    """
    storage = get_storage()
    repo = ReferenceRepository(storage)
    results = repo.get_cache_entries_with_payloads()
    logger.info("valuation_metrics_found_entries", total_entries=len(results))

    processed_pairs: set[tuple[str, str]] = set()
    entries_processed = 0
    entries_updated = 0

    for symbol, source, payload_json in results:
        if not isinstance(symbol, str) or not isinstance(source, str):
            continue
        pair = (symbol, source)
        if pair in processed_pairs:
            continue
        entries_processed += 1
        processed_pairs.add(pair)

        payload = _parse_payload(symbol, source, payload_json)
        if payload is None:
            continue

        metrics = _extract_valuation_metrics(payload)
        if any(v is not None for v in metrics.values()):
            entries_updated += 1
            _update_valuation_metrics(symbol, source, payload)

    return entries_processed, entries_updated


def _fetch_stale_symbols() -> list[str]:
    """Return symbols with missing or stale (>7d) yfinance data."""
    storage = get_storage()
    repo = ReferenceRepository(storage)
    return repo.get_stale_symbols(days_threshold=7)


def _store_alphavantage_payload(symbols: list[str]) -> int:
    """Fetch and store Alpha Vantage reference data. Returns rows upserted."""
    source = AlphaVantageSource()
    df = source.fetch_reference_payload(symbols, dt.date.today())
    if df is None or df.is_empty():
        logger.warning("alphavantage_backup_fetch_failed")
        return 0

    storage = get_storage()
    repo = ReferenceRepository(storage)
    count = 0
    for row in df.iter_rows(named=True):
        repo.upsert_reference_cache(
            symbol=row["symbol"],
            as_of_date=row["as_of_date"],
            payload=row["payload"],
            source="alphavantage",
        )
        count += 1
    return count


def _store_yfinance_payload(symbols: list[str]) -> int:
    """Fetch and store yfinance reference data. Returns rows upserted."""
    source = YFinanceSource()
    df = source.fetch_reference_payload(symbols, dt.date.today())
    if df is None or df.is_empty():
        logger.warning("yfinance_reference_fetch_failed")
        return 0

    storage = get_storage()
    repo = ReferenceRepository(storage)
    count = 0
    for row in df.iter_rows(named=True):
        repo.upsert_reference_cache(
            symbol=row["symbol"],
            as_of_date=row["as_of_date"],
            payload=row["payload"],
            source="yfinance",
        )
        count += 1
    return count


def _backfill_symbol_company_names() -> int:
    """Populate symbols.company_name from freshly-cached yfinance reference payloads.

    Runs after the reference payloads are stored so the scanner can join a
    human-readable company name onto each watchlist row. Returns rows updated.
    """
    storage = get_storage()
    repo = ReferenceRepository(storage)
    return repo.backfill_company_names_from_cache()


def _process_health_score_for_symbol(
    symbol: str,
    repo: ReferenceRepository,
) -> bool:
    """Calculate and store financial health scores for one symbol.

    Returns True if scores were stored, False otherwise.
    """
    scores = get_financial_health_scores(symbol)
    if scores.f_score is None and scores.z_score is None:
        return False

    f_components_json = (
        json.dumps(scores.f_score_components) if scores.f_score_components else None
    )
    score_values = [scores.f_score, f_components_json, scores.z_score, scores.z_score_zone]

    repo.upsert_dual_write_metrics(
        symbol=symbol,
        as_of_date=dt.date.today(),
        base_table_update_sql=_HEALTH_SCORE_UPDATE_SQL,
        base_table_params=[*score_values, symbol, symbol],
        metrics_table="financial_health_scores",
        metrics_columns=["f_score", "f_score_components", "z_score", "z_score_zone"],
        metrics_values=score_values,
        conflict_keys=["symbol", "as_of_date"],
    )
    logger.debug(
        "financial_health_scores_calculated",
        symbol=symbol,
        f_score=scores.f_score,
        z_score=scores.z_score,
    )
    return True


def _process_risk_metrics_for_symbol(
    symbol: str,
    repo: ReferenceRepository,
    as_of_date: dt.date,
) -> bool:
    """Calculate and store risk metrics for one symbol.

    Returns True if metrics were stored, False otherwise.
    """
    var_result = calculate_symbol_var(get_storage(), symbol)
    beta_result = calculate_symbol_beta(get_storage(), symbol)
    if var_result.var_95 is None and beta_result.beta_90d is None:
        return False

    repo.upsert_risk_metrics(
        symbol=symbol,
        as_of_date=as_of_date,
        var_95=var_result.var_95,
        var_99=var_result.var_99,
        cvar_95=var_result.cvar_95,
        cvar_99=var_result.cvar_99,
        beta_90d=beta_result.beta_90d,
        beta_1y=beta_result.beta_1y,
        beta_2y=beta_result.beta_2y,
        r_squared_1y=beta_result.r_squared_1y,
        observations=var_result.observations,
    )
    logger.debug(
        "risk_metrics_calculated",
        symbol=symbol,
        var_95=var_result.var_95,
        beta_1y=beta_result.beta_1y,
    )
    return True
