"""Data quality service for watchlist symbols."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)

StatusType = Literal["complete", "partial", "stale", "n/a"]

PILLAR_WEIGHTS = {
    "technical": 25.0,
    "fundamental": 25.0,
    "catalyst": 15.0,
    "options": 10.0,
    "price": 25.0,
}

APPLICABLE_PILLARS: dict[str, set[str]] = {
    "equity": {"technical", "fundamental", "catalyst", "options", "price"},
    "etf": {"technical", "options", "price"},
    "index": {"technical", "price"},
    "other": {"technical", "fundamental", "catalyst", "options", "price"},
}

DEFAULT_SECURITY_TYPE = "equity"


@dataclass
class PillarQuality:
    """Quality assessment for a single scoring pillar."""

    status: StatusType
    score: float
    details: str

    def __post_init__(self) -> None:
        self.score = max(0.0, min(100.0, self.score))


@dataclass
class DataQuality:
    """Overall data quality assessment for a symbol."""

    overall_pct: float
    pillars: dict[str, PillarQuality]

    def __post_init__(self) -> None:
        self.overall_pct = max(0.0, min(100.0, self.overall_pct))


def _na(details: str) -> PillarQuality:
    return PillarQuality(status="n/a", score=0.0, details=details)


def _as_date(value: object) -> object:
    return value.date() if isinstance(value, datetime) else value


def get_security_type(storage: PortfolioStorage, symbol: str) -> str:
    try:
        df = storage.query("SELECT security_type FROM symbols WHERE symbol = ?", [symbol])
        if df.is_empty():
            return DEFAULT_SECURITY_TYPE
        st = df.item(0, "security_type")
        return str(st) if st and st in APPLICABLE_PILLARS else DEFAULT_SECURITY_TYPE
    except Exception as e:
        logger.warning("security_type_lookup_failed", symbol=symbol, error=str(e))
        return DEFAULT_SECURITY_TYPE


def _check_technical_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    try:
        df = storage.query(
            "SELECT date, rsi_14, macd, sma_20, ema_20, sma_50, sma_200, calculated_at"
            " FROM technical_indicators WHERE symbol = ? ORDER BY date DESC LIMIT 1",
            [symbol],
        )
        if df.is_empty():
            return _na("No technical indicators data")
        row = df.to_dicts()[0]
        fields = ["rsi_14", "macd", "sma_20", "ema_20", "sma_50", "sma_200"]
        non_null = sum(1 for f in fields if row.get(f) is not None)
        total = len(fields)
        today = now.date()
        ind_date = _as_date(row.get("date"))
        days_old = (today - ind_date).days if ind_date else 0
        is_fresh = ind_date in (today, today - timedelta(days=1)) if ind_date else False
        score = (non_null / total) * 70.0 + (30.0 if is_fresh else max(0.0, 30.0 - days_old * 3.0))
        status: StatusType = "complete" if (non_null == total and is_fresh) else ("stale" if days_old > 3 else "partial")
        details = f"{non_null}/{total} indicators" + (f", {days_old}d old" if ind_date else "")
        if isinstance(row.get("calculated_at"), datetime):
            details += f", calc {int((now - row['calculated_at']).total_seconds() / 3600)}h ago"
        return PillarQuality(status=status, score=score, details=details)
    except Exception as e:
        logger.error("technical_quality_check_failed", symbol=symbol, error=str(e), exc_info=True)
        return _na(f"Error: {e!s}")


def _check_fundamental_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    try:
        df = storage.query(
            "SELECT as_of_date, payload FROM reference_cache"
            " WHERE symbol = ? AND source = 'yfinance' ORDER BY as_of_date DESC LIMIT 1",
            [symbol],
        )
        if df.is_empty():
            return PillarQuality(status="partial", score=0.0, details="No fundamental data")
        row = df.to_dicts()[0]
        payload = row.get("payload") or {}
        metrics = [
            payload.get("profitMargins"), payload.get("debtToEquity"),
            payload.get("revenueGrowth"), payload.get("trailingPE") or payload.get("forwardPE"),
        ]
        non_null = sum(1 for m in metrics if m is not None)
        total = len(metrics)
        aod = _as_date(row.get("as_of_date"))
        days_old = (now.date() - aod).days if aod else 0
        is_fresh = days_old <= 120
        score = (non_null / total) * 60.0 + (40.0 if is_fresh else (20.0 if days_old <= 240 else 0.0))
        status: StatusType = "complete" if (non_null >= 3 and is_fresh) else ("stale" if days_old > 240 else "partial")
        details = f"{non_null}/{total} metrics" + (f", {days_old}d old" if aod else "")
        return PillarQuality(status=status, score=score, details=details)
    except Exception as e:
        logger.error("fundamental_quality_check_failed", symbol=symbol, error=str(e), exc_info=True)
        return _na(f"Error: {e!s}")


def _check_catalyst_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    try:
        cutoff = now - timedelta(days=90)
        e_df = storage.query(
            "SELECT COUNT(*) as count, MAX(earnings_date) as latest_date FROM earnings_surprises"
            " WHERE symbol = ? AND earnings_date >= ?",
            [symbol, cutoff],
        )
        i_df = storage.query(
            "SELECT COUNT(*) as count, MAX(transaction_date) as latest_date FROM insider_transactions"
            " WHERE symbol = ? AND transaction_date >= ?",
            [symbol, cutoff],
        )
        er = e_df.to_dicts()[0] if not e_df.is_empty() else {}
        ir = i_df.to_dicts()[0] if not i_df.is_empty() else {}
        ec, ic = er.get("count", 0), ir.get("count", 0)
        total = ec + ic
        if total == 0:
            return _na("No catalyst events in 90d")
        dates = [d for d in [er.get("latest_date"), ir.get("latest_date")] if d]
        most_recent = _as_date(max(dates)) if dates else None
        days_since = (now.date() - most_recent).days if most_recent else 0
        score = max(0.0, 50.0 - days_since * 0.5) + min(50.0, total * 10.0)
        status: StatusType = "complete" if (total >= 2 and days_since <= 30) else "partial"
        details = f"{total} events in 90d" + (f", latest {days_since}d ago" if most_recent else "")
        if ec > 0:
            details += f" ({ec} earnings)"
        if ic > 0:
            details += f" ({ic} insider)"
        return PillarQuality(status=status, score=score, details=details)
    except Exception as e:
        logger.error("catalyst_quality_check_failed", symbol=symbol, error=str(e), exc_info=True)
        return _na(f"Error: {e!s}")


_OPTIONS_TIERS: list[tuple[int, StatusType, float]] = [
    (1, "complete", 100.0),
    (3, "partial", 70.0),
    (7, "partial", 40.0),
]


def _check_options_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    try:
        df = storage.query(
            "SELECT COUNT(*) as count, MAX(as_of_date) as latest_date FROM options_market_metrics"
            " WHERE as_of_date >= ?",
            [now - timedelta(days=7)],
        )
        if df.is_empty():
            return _na("No options market data")
        row = df.to_dicts()[0]
        count = row.get("count", 0)
        if count == 0:
            return _na("No options data in 7d")
        latest = _as_date(row.get("latest_date"))
        days_old = (now.date() - latest).days if latest else 0
        detail = f"{count} days in 7d, latest {days_old}d ago"
        for threshold, status, score in _OPTIONS_TIERS:
            if days_old <= threshold:
                return PillarQuality(status=status, score=score, details=detail)
        return PillarQuality(status="stale", score=0.0, details=detail)
    except Exception as e:
        logger.error("options_quality_check_failed", symbol=symbol, error=str(e), exc_info=True)
        return _na(f"Error: {e!s}")


def _check_price_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    try:
        df = storage.query(
            "SELECT date, close, volume FROM day_bars WHERE symbol = ? ORDER BY date DESC LIMIT 1",
            [symbol],
        )
        if df.is_empty():
            return _na("No price data")
        row = df.to_dicts()[0]
        close = row.get("close")
        if close is None:
            return _na("No close price")
        pd_ = _as_date(row.get("date"))
        days_old = (now.date() - pd_).days if pd_ else 0
        if days_old <= 1:
            status: StatusType = "complete"
            score = 100.0
        elif days_old <= 3:
            status = "partial"
            score = 60.0
        elif days_old <= 7:
            status = "stale"
            score = 30.0
        else:
            status = "stale"
            score = 0.0
        details = f"close ${close:.2f}" + (f", {days_old}d old" if pd_ else "")
        vol = row.get("volume")
        if vol:
            details += f", vol {vol:,.0f}" if vol >= 1000 else f", vol {vol:.0f}"
        return PillarQuality(status=status, score=score, details=details)
    except Exception as e:
        logger.error("price_quality_check_failed", symbol=symbol, error=str(e), exc_info=True)
        return _na(f"Error: {e!s}")


def _check_all_pillars(storage: PortfolioStorage, symbol: str, now: datetime) -> dict[str, PillarQuality]:
    return {
        "technical": _check_technical_quality(storage, symbol, now),
        "fundamental": _check_fundamental_quality(storage, symbol, now),
        "catalyst": _check_catalyst_quality(storage, symbol, now),
        "options": _check_options_quality(storage, symbol, now),
        "price": _check_price_quality(storage, symbol, now),
    }


def _weighted_score(pillars: dict[str, PillarQuality], security_type: str) -> float:
    applicable = APPLICABLE_PILLARS.get(security_type, APPLICABLE_PILLARS["equity"])
    total_weight = sum(PILLAR_WEIGHTS[n] for n in applicable)
    if not total_weight:
        return 0.0
    return sum(pillars[n].score * PILLAR_WEIGHTS[n] for n in applicable) / total_weight


def _error_quality() -> DataQuality:
    err = _na("Error")
    return DataQuality(overall_pct=0.0, pillars=dict.fromkeys(PILLAR_WEIGHTS, err))


def calculate_data_quality(storage: PortfolioStorage, symbols: list[str]) -> dict[str, DataQuality]:
    """Calculate data quality for multiple symbols."""
    if not symbols:
        return {}
    now = datetime.now(UTC)
    results: dict[str, DataQuality] = {}
    logger.info("calculating_data_quality", symbol_count=len(symbols))
    for symbol in symbols:
        try:
            security_type = get_security_type(storage, symbol)
            raw_pillars = _check_all_pillars(storage, symbol, now)
            # Weighted score uses only applicable pillars; DataQuality stores all raw pillar data
            overall_pct = _weighted_score(raw_pillars, security_type)
            results[symbol] = DataQuality(overall_pct=overall_pct, pillars=raw_pillars)
            logger.debug(
                "symbol_quality_calculated", symbol=symbol, overall_pct=overall_pct,
                **{f"{p}_status": raw_pillars[p].status for p in raw_pillars},
            )
        except Exception as e:
            logger.error("symbol_quality_calculation_failed", symbol=symbol, error=str(e), exc_info=True)
            results[symbol] = _error_quality()
    logger.info(
        "data_quality_calculation_complete",
        symbol_count=len(symbols),
        avg_quality=sum(r.overall_pct for r in results.values()) / len(results) if results else 0.0,
    )
    return results
