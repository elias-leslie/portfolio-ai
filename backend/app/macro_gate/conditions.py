"""Plain-language market-condition interpretation for Today.

This module intentionally derives from the existing macro gate snapshot and
nearby stored market evidence. It does not introduce a second scoring model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import Any

from ..constants import INDEX_SP500, SECTOR_ETFS
from ..storage.facade import get_storage
from ..utils.market_hours import NY_TZ, is_stale
from . import repository

SEVERE_STRESS_THRESHOLD = 65
MODERATE_CAUTION_THRESHOLD = 50
SELECTIVE_CAUTION_THRESHOLD = 35
MIN_TAPE_SECTOR_COVERAGE = 0.80


@dataclass(frozen=True, slots=True)
class YieldCurveEvidence:
    as_of: str | None
    ten_year_two_year_bps: float | None
    ten_year_three_month_bps: float | None


@dataclass(frozen=True, slots=True)
class HyOasChange:
    latest_date: str | None
    latest_value: float | None
    prior_date: str | None
    prior_value: float | None
    change_bps: float | None


@dataclass(frozen=True, slots=True)
class TapeStressEvidence:
    stress_score: int
    as_of: str | None
    sp500_change_pct: float | None
    weakest_sector_symbol: str | None
    weakest_sector_name: str | None
    weakest_sector_change_pct: float | None
    negative_sector_count: int
    sector_count: int
    sector_coverage: float | None = None


@dataclass(frozen=True, slots=True)
class CurrentQuoteChange:
    change_pct: float
    as_of: str | None
    cached_at: datetime | None


@dataclass(frozen=True, slots=True)
class YieldCurveHistoryPoint:
    as_of: str | None
    ten_year_two_year_bps: float | None
    ten_year_three_month_bps: float | None


@dataclass(frozen=True, slots=True)
class TrendConfig:
    key: str
    label: str
    higher_is_better: bool
    threshold: float
    precision: int
    unit: str = ""


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _datetime_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _aware_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _quote_market_date(value: object) -> date | None:
    if not isinstance(value, datetime):
        return None
    quote_ts = value if value.tzinfo else value.replace(tzinfo=UTC)
    return quote_ts.astimezone(NY_TZ).date()


def _parse_date(value: object) -> date | None:
    text = _date_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _fmt_number(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def _fmt_bps(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.0f} bps"


def _fmt_change_bps(value: float | None) -> str:
    if value is None:
        return "3M change unavailable"
    return f"3M change {value:+.0f} bps"


def _fmt_delta(value: float | None, precision: int, unit: str = "") -> str:
    if value is None:
        return "-"
    rounded = round(value, precision)
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded:.{precision}f}{unit}"


def _crowding_detail(score: float | None, corr: float | None) -> str:
    if score is None:
        return "Unavailable"
    if corr is not None:
        return f"|corr| {abs(corr):.2f}"
    return f"Score {score:.0f}/100"


def _zone_state(zone: object) -> str:
    normalized = str(zone or "").upper()
    if normalized == "FULL_DEPLOY":
        return "Calm"
    if normalized == "DEFENSIVE":
        return "Elevated"
    return "Caution"


def _stress_score(deployment_score: float | None) -> int | None:
    if deployment_score is None:
        return None
    return round(max(0.0, min(100.0, 100.0 - deployment_score)))


def _combined_stress_score(
    macro_stress: int | None,
    tape_stress: TapeStressEvidence | None,
) -> int | None:
    if macro_stress is None:
        return tape_stress.stress_score if tape_stress else None
    if tape_stress is None:
        return macro_stress
    return max(macro_stress, tape_stress.stress_score)


def _severe_flags(
    *,
    deployment_score: float | None,
    vix_close: float | None,
    hy_spread: float | None,
    hy_change_bps: float | None,
    tape_stress_score: int | None = None,
) -> list[str]:
    flags: list[str] = []
    if vix_close is not None and vix_close >= 30:
        flags.append("vix_stress")
    if hy_spread is not None and hy_spread >= 5:
        flags.append("credit_stress")
    if hy_change_bps is not None and hy_change_bps >= 100:
        flags.append("credit_widening")
    if deployment_score is not None and deployment_score < 40:
        flags.append("defensive_deployment")
    if tape_stress_score is not None and tape_stress_score >= SEVERE_STRESS_THRESHOLD:
        flags.append("equity_tape_stress")
    return flags


def _evidence_tone(kind: str, value: float | None) -> str:
    if value is None:
        return "neutral"
    tone = "neutral"
    if kind == "stress":
        if value >= SEVERE_STRESS_THRESHOLD:
            tone = "loss"
        elif value >= 30:
            tone = "warning"
        else:
            tone = "gain"
    elif kind == "vix":
        if value >= 30:
            tone = "loss"
        elif value >= 20:
            tone = "warning"
        else:
            tone = "gain"
    elif kind == "hy":
        if value >= 5:
            tone = "loss"
        elif value >= 3.5:
            tone = "warning"
        else:
            tone = "gain"
    elif kind == "breadth":
        if value < 45:
            tone = "loss"
        elif value < 65:
            tone = "warning"
        else:
            tone = "gain"
    elif kind == "curve":
        if value < 0:
            tone = "loss"
        elif value < 75:
            tone = "warning"
        else:
            tone = "gain"
    elif kind == "crowding":
        if value < 35:
            tone = "loss"
        elif value < 60:
            tone = "warning"
        else:
            tone = "gain"
    return tone


def _stress_from_decline(decline_pct: float) -> float:
    """Map an equity decline percentage to a 0-100 tape stress score."""
    if decline_pct <= 0:
        return 15.0
    anchors = [
        (0.0, 15.0),
        (0.5, 30.0),
        (1.5, 45.0),
        (3.0, 65.0),
        (5.0, 85.0),
        (8.0, 95.0),
    ]
    for (left_x, left_y), (right_x, right_y) in pairwise(anchors):
        if decline_pct <= right_x:
            span = right_x - left_x
            progress = (decline_pct - left_x) / span if span else 0.0
            return left_y + progress * (right_y - left_y)
    return 95.0


def _sector_tape_stress(
    weakest_sector_change_pct: float | None,
    negative_sector_count: int,
    sector_count: int,
) -> float | None:
    if weakest_sector_change_pct is None or sector_count <= 0:
        return None
    base = _stress_from_decline(-weakest_sector_change_pct)
    negative_ratio = max(0.0, min(1.0, negative_sector_count / sector_count))
    return base * (0.55 + 0.45 * negative_ratio)


def _tape_detail(tape_stress: TapeStressEvidence | None) -> str:
    if tape_stress is None:
        return "Unavailable"
    pieces: list[str] = []
    if tape_stress.sp500_change_pct is not None:
        pieces.append(f"S&P {_fmt_delta(tape_stress.sp500_change_pct, 1, '%')}")
    if (
        tape_stress.weakest_sector_name
        and tape_stress.weakest_sector_change_pct is not None
    ):
        pieces.append(
            f"{tape_stress.weakest_sector_name} "
            f"{_fmt_delta(tape_stress.weakest_sector_change_pct, 1, '%')}"
        )
    if tape_stress.sector_count > 0:
        pieces.append(
            f"{tape_stress.negative_sector_count}/{tape_stress.sector_count} sectors down"
        )
    return ", ".join(pieces) if pieces else "Current tape pressure unavailable"


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _prior_close_for_quote(
    *,
    quote_date: date | None,
    bars: list[tuple[date, float]],
) -> float | None:
    if not bars:
        return None
    latest_date, latest_close = bars[0]
    if quote_date is not None and quote_date <= latest_date and len(bars) > 1:
        return bars[1][1]
    return latest_close


def _current_quote_changes(symbols: list[str]) -> dict[str, CurrentQuoteChange]:
    normalized_symbols = sorted({symbol.upper() for symbol in symbols if symbol})
    if not normalized_symbols:
        return {}

    storage = get_storage()
    with storage.connection() as conn:
        quote_rows = conn.execute(
            """
            SELECT UPPER(symbol), price, cached_at
            FROM price_cache
            WHERE UPPER(symbol) = ANY(%s)
              AND price IS NOT NULL
              AND price > 0
            """,
            [normalized_symbols],
        ).fetchall()
        bar_rows = conn.execute(
            """
            SELECT symbol, date, close
            FROM (
                SELECT UPPER(symbol) AS symbol,
                       date,
                       close,
                       ROW_NUMBER() OVER (PARTITION BY UPPER(symbol) ORDER BY date DESC) AS rn
                FROM day_bars
                WHERE UPPER(symbol) = ANY(%s)
                  AND close IS NOT NULL
                  AND close > 0
            ) ranked
            WHERE rn <= 2
            ORDER BY symbol, date DESC
            """,
            [normalized_symbols],
        ).fetchall()

    latest_quotes: dict[str, tuple[float, datetime | None]] = {}
    for symbol, price, cached_at in quote_rows:
        if not isinstance(symbol, str):
            continue
        price_value = _maybe_float(price)
        if price_value is None or price_value <= 0:
            continue
        existing = latest_quotes.get(symbol)
        cached_dt = cached_at if isinstance(cached_at, datetime) else None
        if existing is None:
            latest_quotes[symbol] = (price_value, cached_dt)
            continue
        existing_dt = existing[1]
        if cached_dt and (existing_dt is None or cached_dt > existing_dt):
            latest_quotes[symbol] = (price_value, cached_dt)

    bars_by_symbol: dict[str, list[tuple[date, float]]] = {}
    for symbol, raw_date, close in bar_rows:
        if not isinstance(symbol, str):
            continue
        bar_date = _as_date(raw_date)
        close_value = _maybe_float(close)
        if bar_date is None or close_value is None or close_value <= 0:
            continue
        bars_by_symbol.setdefault(symbol, []).append((bar_date, close_value))

    changes: dict[str, CurrentQuoteChange] = {}
    for symbol, (price, cached_at) in latest_quotes.items():
        baseline = _prior_close_for_quote(
            quote_date=_quote_market_date(cached_at),
            bars=bars_by_symbol.get(symbol, []),
        )
        if baseline is None or baseline <= 0:
            continue
        change_pct = ((price - baseline) / baseline) * 100.0
        changes[symbol] = CurrentQuoteChange(
            change_pct=change_pct,
            as_of=_datetime_text(cached_at),
            cached_at=_aware_datetime(cached_at),
        )
    return changes


def _fresh_quote_changes(
    changes: dict[str, CurrentQuoteChange],
    *,
    now: datetime,
) -> dict[str, CurrentQuoteChange]:
    fresh: dict[str, CurrentQuoteChange] = {}
    for symbol, change in changes.items():
        if change.cached_at is None:
            continue
        if not is_stale(change.cached_at, now):
            fresh[symbol] = change
    return fresh


def _required_sector_quote_count(sector_total: int) -> int:
    return max(1, int(sector_total * MIN_TAPE_SECTOR_COVERAGE + 0.999))


def get_tape_stress(now: datetime | None = None) -> TapeStressEvidence | None:
    """Return current equity/sector tape stress from canonical quote cache."""
    market_now = (now or datetime.now(NY_TZ)).astimezone(NY_TZ)
    sector_symbols = list(SECTOR_ETFS.keys())
    changes = _current_quote_changes([INDEX_SP500, *sector_symbols])
    if not changes:
        return None
    fresh_changes = _fresh_quote_changes(changes, now=market_now)
    if not fresh_changes:
        return None

    sector_quote_count = sum(1 for symbol in sector_symbols if symbol in fresh_changes)
    sector_coverage = sector_quote_count / len(sector_symbols) if sector_symbols else 0.0
    if (
        INDEX_SP500 not in fresh_changes
        or sector_quote_count < _required_sector_quote_count(len(sector_symbols))
    ):
        return None

    sp500 = fresh_changes.get(INDEX_SP500)
    sp500_change = sp500.change_pct if sp500 else None
    sp500_stress = (
        _stress_from_decline(-sp500_change) if sp500_change is not None else None
    )
    sector_changes: list[tuple[str, float]] = []
    for symbol in sector_symbols:
        change_tuple = fresh_changes.get(symbol)
        if change_tuple is not None:
            sector_changes.append((symbol, change_tuple.change_pct))
    weakest_sector = min(sector_changes, key=lambda row: row[1], default=None)
    negative_sector_count = sum(1 for _, change in sector_changes if change < 0)
    sector_stress = _sector_tape_stress(
        weakest_sector[1] if weakest_sector else None,
        negative_sector_count,
        len(sector_changes),
    )
    stress_candidates = [
        score for score in [sp500_stress, sector_stress] if score is not None
    ]
    if not stress_candidates:
        return None
    as_of_values = [change.as_of for change in fresh_changes.values() if change.as_of]
    as_of = max(as_of_values) if as_of_values else None
    weakest_symbol = weakest_sector[0] if weakest_sector else None
    return TapeStressEvidence(
        stress_score=round(max(stress_candidates)),
        as_of=as_of,
        sp500_change_pct=sp500_change,
        weakest_sector_symbol=weakest_symbol,
        weakest_sector_name=SECTOR_ETFS.get(weakest_symbol) if weakest_symbol else None,
        weakest_sector_change_pct=weakest_sector[1] if weakest_sector else None,
        negative_sector_count=negative_sector_count,
        sector_count=len(sector_changes),
        sector_coverage=sector_coverage,
    )


def _empty_trend(config: TrendConfig, sparkline: list[float] | None = None) -> dict[str, Any]:
    return {
        "key": config.key,
        "label": config.label,
        "direction": "unavailable",
        "tone": "neutral",
        "delta": None,
        "change_label": "7D -",
        "summary": "Trend history unavailable",
        "window_days": 7,
        "latest_date": None,
        "prior_date": None,
        "reversal": False,
        "reversal_label": None,
        "sparkline": sparkline or [],
    }


def _trend_direction(delta: float, config: TrendConfig) -> str:
    if abs(delta) < config.threshold:
        return "flat"
    if config.higher_is_better:
        return "improving" if delta > 0 else "worsening"
    return "worsening" if delta > 0 else "improving"


def _trend_tone(direction: str) -> str:
    if direction == "improving":
        return "gain"
    if direction == "worsening":
        return "warning"
    return "neutral"


def _trend_summary(direction: str, reversal: bool) -> str:
    if direction == "improving":
        return "Turned better over 7D" if reversal else "Improving over 7D"
    if direction == "worsening":
        return "Reversed worse over 7D" if reversal else "Worsening over 7D"
    if direction == "flat":
        return "Stable over 7D"
    return "Trend history unavailable"


def _prior_point(
    points: list[tuple[date, float]],
    target: date,
) -> tuple[date, float] | None:
    prior = [point for point in points if point[0] <= target]
    if prior:
        return prior[-1]
    return points[0] if points else None


def _build_trend(
    raw_points: list[tuple[str | None, float | None]],
    config: TrendConfig,
) -> dict[str, Any]:
    points = sorted(
        [
            (parsed, float(value))
            for raw_date, value in raw_points
            if value is not None and (parsed := _parse_date(raw_date)) is not None
        ],
        key=lambda point: point[0],
    )
    deduped = dict(points)
    points = sorted(deduped.items(), key=lambda point: point[0])
    sparkline = [round(value, max(config.precision, 1)) for _, value in points[-30:]]
    if len(points) < 2:
        return _empty_trend(config, sparkline)

    latest_date, latest_value = points[-1]
    prior = _prior_point(points[:-1], latest_date - timedelta(days=7))
    if prior is None:
        return _empty_trend(config, sparkline)

    prior_date, prior_value = prior
    delta = latest_value - prior_value
    direction = _trend_direction(delta, config)
    previous_direction = "unavailable"
    earlier = _prior_point(
        [point for point in points if point[0] < prior_date],
        prior_date - timedelta(days=7),
    )
    if earlier is not None:
        previous_delta = prior_value - earlier[1]
        previous_direction = _trend_direction(previous_delta, config)
    reversal = (
        direction in {"improving", "worsening"}
        and previous_direction in {"improving", "worsening"}
        and previous_direction != direction
    )

    return {
        "key": config.key,
        "label": config.label,
        "direction": direction,
        "tone": _trend_tone(direction),
        "delta": round(delta, config.precision),
        "change_label": f"7D {_fmt_delta(delta, config.precision, config.unit)}",
        "summary": _trend_summary(direction, reversal),
        "window_days": 7,
        "latest_date": latest_date.isoformat(),
        "prior_date": prior_date.isoformat(),
        "reversal": reversal,
        "reversal_label": (
            "Reversed worse"
            if reversal and direction == "worsening"
            else "Turned better"
            if reversal
            else None
        ),
        "sparkline": sparkline,
    }


def _history_with_current(
    snapshot: dict[str, Any], history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows_by_date = {
        _date_text(row.get("snapshot_date")): row
        for row in history
        if _date_text(row.get("snapshot_date"))
    }
    snapshot_date = _date_text(snapshot.get("snapshot_date"))
    if snapshot_date:
        rows_by_date[snapshot_date] = {**rows_by_date.get(snapshot_date, {}), **snapshot}
    return [
        rows_by_date[key]
        for key in sorted(rows_by_date)
        if key is not None and _parse_date(key) is not None
    ]


def _row_series(
    rows: list[dict[str, Any]],
    value_key: str,
    *,
    transform: str | None = None,
) -> list[tuple[str | None, float | None]]:
    values: list[tuple[str | None, float | None]] = []
    for row in rows:
        value = _maybe_float(row.get(value_key))
        if transform == "stress" and value is not None:
            value = 100.0 - value
        values.append((_date_text(row.get("snapshot_date")), value))
    return values


def _yield_curve_series(
    rows: list[YieldCurveHistoryPoint],
    key: str,
) -> list[tuple[str | None, float | None]]:
    values: list[tuple[str | None, float | None]] = []
    for row in rows:
        value = (
            row.ten_year_two_year_bps
            if key == "ten_year_two_year"
            else row.ten_year_three_month_bps
        )
        values.append((row.as_of, value))
    return values


def _build_trends(
    snapshot: dict[str, Any],
    *,
    macro_history: list[dict[str, Any]],
    yield_curve_history: list[YieldCurveHistoryPoint],
) -> dict[str, Any]:
    rows = _history_with_current(snapshot, macro_history)
    configs = {
        "stress": TrendConfig("stress", "Macro stress", False, 3.0, 0),
        "vix": TrendConfig("vix", "VIX", False, 2.0, 2),
        "hy_oas": TrendConfig("hy_oas", "HY OAS", False, 0.25, 2),
        "breadth": TrendConfig("breadth", "Breadth", True, 3.0, 0, "%"),
        "ten_year_two_year": TrendConfig("ten_year_two_year", "10Y-2Y", True, 10.0, 0, " bps"),
        "ten_year_three_month": TrendConfig(
            "ten_year_three_month", "10Y-3M", True, 10.0, 0, " bps"
        ),
        "crowding": TrendConfig("crowding", "Crowding", True, 5.0, 0),
    }
    return {
        "stress": _build_trend(
            _row_series(rows, "deployment_score", transform="stress"),
            configs["stress"],
        ),
        "vix": _build_trend(_row_series(rows, "vix_close"), configs["vix"]),
        "hy_oas": _build_trend(_row_series(rows, "hy_spread"), configs["hy_oas"]),
        "breadth": _build_trend(_row_series(rows, "breadth_pct"), configs["breadth"]),
        "ten_year_two_year": _build_trend(
            _row_series(rows, "term_spread_bps"),
            configs["ten_year_two_year"],
        ),
        "ten_year_three_month": _build_trend(
            _yield_curve_series(yield_curve_history, "ten_year_three_month"),
            configs["ten_year_three_month"],
        ),
        "crowding": _build_trend(_row_series(rows, "crowding_score"), configs["crowding"]),
    }


def _shift_label(key: str, trend: dict[str, Any]) -> str:
    direction = trend.get("direction")
    if trend.get("reversal"):
        return (
            f"{trend['label']} reversed worse"
            if direction == "worsening"
            else f"{trend['label']} turned better"
        )
    if direction == "improving":
        return {
            "stress": "Macro stress easing",
            "vix": "Volatility easing",
            "hy_oas": "Credit improving",
            "breadth": "Breadth improving",
            "ten_year_two_year": "Curve improving",
            "ten_year_three_month": "Yield curve improving",
            "crowding": "Crowding improving",
        }.get(key, f"{trend['label']} improving")
    if direction == "worsening":
        return {
            "stress": "Macro stress rising",
            "vix": "Volatility rising",
            "hy_oas": "Credit widening",
            "breadth": "Breadth weakening",
            "ten_year_two_year": "Curve weakening",
            "ten_year_three_month": "Yield curve weakening",
            "crowding": "Crowding weakening",
        }.get(key, f"{trend['label']} weakening")
    return f"{trend['label']} stable"


def _build_market_shifts(trends: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key, trend in trends.items():
        direction = trend.get("direction")
        if direction not in {"improving", "worsening"}:
            continue
        candidates.append(
            {
                "key": key,
                "label": _shift_label(key, trend),
                "detail": f"{trend.get('change_label', '7D -')} · {trend.get('summary', '')}",
                "tone": trend.get("tone", "neutral"),
                "reversal": bool(trend.get("reversal")),
                "rank": (
                    0
                    if trend.get("reversal") and direction == "worsening"
                    else 1
                    if direction == "worsening"
                    else 2
                ),
            }
        )
    candidates.sort(key=lambda item: (item["rank"], item["key"]))
    shifts = [
        {key: value for key, value in item.items() if key != "rank"} for item in candidates[:3]
    ]
    if shifts:
        return shifts
    return [
        {
            "key": "stable",
            "label": "No major shifts",
            "detail": "7D trends are not moving enough to flag.",
            "tone": "neutral",
            "reversal": False,
        }
    ]


def _overall_read(overall_caution_score: int | None, flags: list[str]) -> str:
    if flags:
        return "defensive"
    if overall_caution_score is None:
        return "unavailable"
    if overall_caution_score >= SEVERE_STRESS_THRESHOLD:
        return "defensive"
    if overall_caution_score >= SELECTIVE_CAUTION_THRESHOLD:
        return "selective"
    return "normal"


def _primary_driver(
    *,
    overall_read: str,
    macro_stress_score: int | None,
    tape_pressure_score: int | None,
) -> str:
    driver = "data_limited"
    if overall_read == "normal":
        driver = "none" if tape_pressure_score is not None else "data_limited"
    elif overall_read != "unavailable":
        if tape_pressure_score is None:
            driver = (
                "macro"
                if macro_stress_score is not None
                and macro_stress_score >= SELECTIVE_CAUTION_THRESHOLD
                else "data_limited"
            )
        elif macro_stress_score is None:
            driver = "tape"
        elif (
            macro_stress_score >= SEVERE_STRESS_THRESHOLD
            and tape_pressure_score >= SEVERE_STRESS_THRESHOLD
        ) or (
            macro_stress_score >= MODERATE_CAUTION_THRESHOLD
            and tape_pressure_score >= MODERATE_CAUTION_THRESHOLD
            and abs(macro_stress_score - tape_pressure_score) <= 10
        ):
            driver = "both"
        else:
            driver = "macro" if macro_stress_score >= tape_pressure_score else "tape"
    return driver


def _driver_detail(
    *,
    overall_read: str,
    primary_driver: str,
    macro_stress_score: int | None,
    tape_pressure_score: int | None,
) -> str:
    details = {
        "tape": "Tape pressure is the main caution; macro stress is not severe.",
        "macro": "Buying conditions are the main caution.",
        "both": "Buying conditions and tape pressure are both elevated.",
        "none": "No major macro or tape caution is driving the read.",
    }
    detail = details.get(
        primary_driver,
        "Tape pressure is unavailable, so the read leans on macro conditions.",
    )
    if overall_read == "unavailable":
        detail = "Macro and tape inputs are too limited for a reliable read."
    elif primary_driver == "data_limited" and (
        macro_stress_score is not None
        and macro_stress_score >= SELECTIVE_CAUTION_THRESHOLD
    ):
        detail = "Tape pressure is unavailable; buying conditions drive the caution."
    elif primary_driver == "none" and tape_pressure_score is None:
        detail = "No major macro caution is driving the read; tape pressure is unavailable."
    return detail


def _state_copy(*, overall_read: str, primary_driver: str) -> tuple[str, str]:
    copy_by_key = {
        "unavailable": (
            "Unavailable — market inputs are too limited for a reliable read.",
            "Avoid changing risk based on this read until market data refreshes.",
        ),
        "defensive": (
            "Defensive — stress is high enough to protect capital first.",
            "Protect the plan first. Avoid adding broad risk until volatility, credit, and breadth stabilize.",
        ),
        "normal": (
            "Normal — conditions are supportive for planned buying.",
            "Stay with the plan. New buys can use normal selectivity, while still checking concentration.",
        ),
        "tape": (
            "Selective — tape pressure is elevated, but macro stress is not severe.",
            "Stay invested, but be selective. Do not chase the selloff; scale only into highest-conviction buys while the tape stabilizes.",
        ),
        "both": (
            "Selective — buying conditions are weaker and tape pressure is elevated.",
            "Stay invested, but protect optionality. Add risk slowly and only to highest-conviction buys.",
        ),
        "macro": (
            "Selective — buying conditions are weakening.",
            "Stay invested, but add new risk slowly. Favor highest-conviction buys until buying conditions improve.",
        ),
        "data_limited": (
            "Selective — buying conditions deserve caution; tape pressure data is limited.",
            "Use the macro read as context, but avoid treating missing tape pressure as an all-clear.",
        ),
    }
    key = overall_read if overall_read in {"unavailable", "defensive", "normal"} else primary_driver
    return copy_by_key.get(key, (
        "Selective — use higher standards for new buys.",
        "Stay invested according to plan. Be selective with new buys. Do not chase broad market strength just because indexes are up.",
    ))


def _driving_read(
    *,
    overall_read: str,
    primary_driver: str,
    tape_stress: TapeStressEvidence | None,
    vix_close: float | None,
    hy_change_bps: float | None,
    breadth_pct: float | None,
) -> dict[str, str]:
    """One plain-language line on what is moving the market today.

    Built only from signals already in the conditions payload (tape leadership,
    volatility, credit, breadth) — no new data source. The summary states the
    posture and the action text states the stance; this states the *why* so an
    amateur sees what is actually driving the read. Generalizes across regimes.
    """
    if overall_read == "unavailable":
        return {
            "headline": "Not enough fresh market data for a clean read right now.",
            "tone": "neutral",
        }

    if overall_read == "normal":
        bits = ["Broad and steady — most sectors holding up"]
        if vix_close is not None and vix_close < 18:
            bits.append(f"volatility low (VIX {_fmt_number(vix_close, 1)})")
        elif breadth_pct is not None and breadth_pct >= 60:
            bits.append(f"breadth healthy ({_fmt_number(breadth_pct, 0)}% above 200-day)")
        return {"headline": ". ".join(bits) + ".", "tone": "constructive"}

    cues: list[str] = []
    tape_active = primary_driver in {"tape", "both"} or (
        tape_stress is not None and tape_stress.negative_sector_count > 0
    )
    if tape_active and tape_stress is not None:
        cues.append(f"stocks broadly lower ({_tape_detail(tape_stress)})")
    elif primary_driver in {"macro", "data_limited"}:
        cues.append("buying conditions softening beneath the surface")
    if vix_close is not None and vix_close >= 20:
        cues.append(f"volatility up (VIX {_fmt_number(vix_close, 1)})")
    if hy_change_bps is not None and hy_change_bps >= 25:
        cues.append("credit spreads widening")
    if not cues:
        cues.append("caution building beneath a quiet tape")

    posture = "Risk-off" if overall_read == "defensive" else "Cautious"
    tone = "risk_off" if overall_read == "defensive" else "caution"
    return {"headline": f"{posture} — " + ", ".join(cues) + ".", "tone": tone}


def _what_matters(
    *,
    overall_read: str,
    primary_driver: str,
    vix_close: float | None,
    hy_spread: float | None,
    breadth_pct: float | None,
    crowding_score: float | None,
    macro_stress_score: int | None,
    tape_stress: TapeStressEvidence | None = None,
) -> list[str]:
    if overall_read == "defensive":
        return [
            "Stress is high enough that capital protection matters more than new risk.",
            "Volatility, credit, or the composite score has crossed a severe threshold.",
            "Wait for evidence to improve before treating weakness as opportunity.",
        ]
    if overall_read == "unavailable":
        return [
            "Macro and tape inputs are too limited for a reliable Today read.",
            "Do not treat missing data as a signal to add risk.",
            "Refresh the data before using this brief for new-buy decisions.",
        ]

    if primary_driver == "tape":
        first = (
            f"Tape pressure is the main caution ({_tape_detail(tape_stress)}), even though macro stress is not severe."
        )
    elif primary_driver == "macro":
        first = "Buying conditions are weaker, so new risk deserves more scrutiny."
    elif primary_driver == "both":
        first = (
            f"Buying conditions and current tape pressure are both elevated ({_tape_detail(tape_stress)})."
        )
    elif primary_driver == "data_limited":
        first = (
            "Current tape pressure is unavailable, so the read relies on slower macro conditions."
            if macro_stress_score is None
            or macro_stress_score < SELECTIVE_CAUTION_THRESHOLD
            else "Tape pressure is unavailable; the caution comes from buying conditions."
        )
    else:
        first = (
            "Credit and volatility are calm, so this is not a panic tape."
            if (
                vix_close is not None
                and vix_close < 20
                and hy_spread is not None
                and hy_spread < 3.5
            )
            else "Volatility or credit is no longer fully calm, so new risk deserves more scrutiny."
        )
    second = (
        "Breadth is middling; the rally is not broad enough to call conditions fully strong."
        if breadth_pct is None or breadth_pct < 65
        else "Breadth is broad enough to support healthier market participation."
    )
    third = (
        "Crowding is the main warning sign; avoid chasing the same narrow winners late."
        if crowding_score is not None and crowding_score < 35
        else "Crowding is not the main risk today; keep watching it for deterioration."
    )
    return [first, second, third]


def _what_to_do(
    overall_read: str,
    alert_active: bool,
    primary_driver: str,
    tape_stress: TapeStressEvidence | None = None,
) -> list[str]:
    if overall_read == "defensive" or alert_active:
        return [
            "Do not add broad risk until the brief improves.",
            "Review concentration and cash needs before making new commitments.",
            "Keep long-term allocation changes tied to your written plan.",
        ]
    if overall_read == "unavailable":
        return [
            "Wait for market data to refresh before using this read.",
            "Keep long-term allocation tied to the written plan.",
            "Do not treat missing tape pressure as an all-clear.",
        ]
    if primary_driver == "tape" or (
        tape_stress is not None and tape_stress.stress_score >= SELECTIVE_CAUTION_THRESHOLD
    ):
        return [
            "Do not chase the selloff while the tape is still under pressure.",
            "If adding money, scale only into highest-conviction setups.",
            "Review concentration in the weakest sector before adding more.",
        ]
    if overall_read == "normal":
        return [
            "Keep long-term allocation on plan.",
            "Use normal selectivity for new buys.",
            "Review concentration before adding to positions that already dominate.",
        ]
    return [
        "Keep long-term allocation unless your plan says otherwise.",
        "If adding money, favor only highest-conviction setups.",
        "Review concentration before adding more to crowded areas.",
    ]


def _watch_items() -> list[str]:
    return [
        "S&P 500 down more than 2% or broad sector selling would lift tape pressure.",
        "VIX above 30 would move volatility from calm to stressed.",
        "HY OAS above 5 or widening 100 bps would make credit a real warning.",
        "Buying conditions below 40 would turn the brief defensive.",
        "Breadth breaking materially lower would weaken rally quality.",
    ]


def _build_evidence(
    *,
    overall_caution_score: int | None,
    vix_close: float | None,
    hy_spread: float | None,
    hy_change_bps: float | None,
    breadth_pct: float | None,
    yield_curve: YieldCurveEvidence | None,
    crowding_score: float | None,
    crowding_corr: float | None,
    tape_stress: TapeStressEvidence | None,
    trends: dict[str, Any],
) -> list[dict[str, Any]]:
    ten_two = yield_curve.ten_year_two_year_bps if yield_curve else None
    ten_three_month = yield_curve.ten_year_three_month_bps if yield_curve else None
    return [
        {
            "key": "overall_caution",
            "label": "Overall Caution",
            "value": (
                _fmt_number(float(overall_caution_score), 0)
                if overall_caution_score is not None
                else "-"
            ),
            "detail": (
                "Unavailable"
                if overall_caution_score is None
                else "Defensive"
                if overall_caution_score >= SEVERE_STRESS_THRESHOLD
                else "Selective"
                if overall_caution_score >= SELECTIVE_CAUTION_THRESHOLD
                else "Normal"
            ),
            "tone": _evidence_tone(
                "stress",
                float(overall_caution_score) if overall_caution_score is not None else None,
            ),
            "tooltip": "Overall Caution is a conservative action gate: the higher of macro stress and fresh tape pressure. Higher means slow down new risk.",
            "trend": None,
        },
        {
            "key": "equity_tape",
            "label": "Tape Pressure",
            "value": (
                _fmt_number(float(tape_stress.stress_score), 0)
                if tape_stress is not None
                else "-"
            ),
            "detail": _tape_detail(tape_stress),
            "tone": _evidence_tone(
                "stress",
                float(tape_stress.stress_score) if tape_stress is not None else None,
            ),
            "tooltip": "Current tape pressure uses canonical S&P 500 and sector ETF quotes versus the prior close so selloffs can surface before slower macro feeds update.",
            "trend": None,
        },
        {
            "key": "vix",
            "label": "VIX",
            "value": _fmt_number(vix_close, 2),
            "detail": "Volatility calm"
            if vix_close is not None and vix_close < 20
            else "Volatility elevated",
            "tone": _evidence_tone("vix", vix_close),
            "tooltip": "VIX estimates expected S&P 500 volatility. A high reading means traders are paying up for protection.",
            "trend": trends.get("vix"),
        },
        {
            "key": "hy_oas",
            "label": "HY OAS",
            "value": _fmt_number(hy_spread, 2),
            "detail": _fmt_change_bps(hy_change_bps),
            "tone": _evidence_tone("hy", hy_spread),
            "tooltip": "High-yield OAS is the extra yield weaker borrowers pay over Treasuries. Wider spreads mean credit stress is rising.",
            "trend": trends.get("hy_oas"),
        },
        {
            "key": "breadth",
            "label": "Breadth",
            "value": f"{_fmt_number(breadth_pct, 0)}%",
            "detail": "Above 200-day average",
            "tone": _evidence_tone("breadth", breadth_pct),
            "tooltip": "Breadth shows how many stocks are participating. Weak breadth means indexes may rely on fewer winners.",
            "trend": trends.get("breadth"),
        },
        {
            "key": "ten_year_two_year",
            "label": "10Y-2Y",
            "value": _fmt_bps(ten_two),
            "detail": "Scored curve input",
            "tone": _evidence_tone("curve", ten_two),
            "tooltip": "The 10-year minus 2-year Treasury spread is a yield-curve health check. Inversions often point to late-cycle risk.",
            "trend": trends.get("ten_year_two_year"),
        },
        {
            "key": "ten_year_three_month",
            "label": "10Y-3M",
            "value": _fmt_bps(ten_three_month),
            "detail": "Recession-risk check",
            "tone": _evidence_tone("curve", ten_three_month),
            "tooltip": "The 10-year minus 3-month spread is another recession-risk curve check watched by economists.",
            "trend": trends.get("ten_year_three_month"),
        },
        {
            "key": "crowding",
            "label": "Crowding",
            "value": (
                "High"
                if crowding_score is not None and crowding_score < 35
                else "Medium"
                if crowding_score is not None and crowding_score < 60
                else "Low"
                if crowding_score is not None
                else "-"
            ),
            "detail": (
                _crowding_detail(crowding_score, crowding_corr)
                if crowding_score is not None and crowding_score < 35
                else "Not the main drag"
            ),
            "tone": _evidence_tone("crowding", crowding_score),
            "tooltip": "Crowding uses absolute factor-correlation magnitude: a big positive or negative correlation means popular factor trades are moving together too tightly. A 0 score means crowded, not missing.",
            "trend": trends.get("crowding"),
        },
    ]


def build_conditions_payload(
    snapshot: dict[str, Any],
    *,
    yield_curve: YieldCurveEvidence | None = None,
    hy_change: HyOasChange | None = None,
    tape_stress: TapeStressEvidence | None = None,
    macro_history: list[dict[str, Any]] | None = None,
    yield_curve_history: list[YieldCurveHistoryPoint] | None = None,
) -> dict[str, Any]:
    deployment_score = _maybe_float(snapshot.get("deployment_score"))
    vix_close = _maybe_float(snapshot.get("vix_close"))
    hy_spread = _maybe_float(snapshot.get("hy_spread"))
    breadth_pct = _maybe_float(snapshot.get("breadth_pct"))
    crowding_corr = _maybe_float(snapshot.get("factor_crowding_corr"))
    crowding_score = _maybe_float(snapshot.get("crowding_score"))
    macro_stress = _stress_score(deployment_score)
    tape_pressure_score = tape_stress.stress_score if tape_stress else None
    overall_caution_score = _combined_stress_score(macro_stress, tape_stress)
    hy_change_bps = hy_change.change_bps if hy_change else None
    flags = _severe_flags(
        deployment_score=deployment_score,
        vix_close=vix_close,
        hy_spread=hy_spread,
        hy_change_bps=hy_change_bps,
        tape_stress_score=tape_pressure_score,
    )
    state = "Elevated" if flags else _zone_state(snapshot.get("zone"))
    overall_read = _overall_read(overall_caution_score, flags)
    primary_driver = _primary_driver(
        overall_read=overall_read,
        macro_stress_score=macro_stress,
        tape_pressure_score=tape_pressure_score,
    )
    driver_detail = _driver_detail(
        overall_read=overall_read,
        primary_driver=primary_driver,
        macro_stress_score=macro_stress,
        tape_pressure_score=tape_pressure_score,
    )
    summary, action_text = _state_copy(
        overall_read=overall_read,
        primary_driver=primary_driver,
    )
    alert_active = state == "Elevated"
    priority = (
        "critical"
        if alert_active
        and overall_caution_score is not None
        and overall_caution_score >= 75
        else "high"
        if alert_active
        else None
    )
    raw_json = snapshot.get("raw_json") if isinstance(snapshot.get("raw_json"), dict) else {}
    coverage = raw_json.get("coverage") if isinstance(raw_json, dict) else None
    trends = _build_trends(
        snapshot,
        macro_history=macro_history or [],
        yield_curve_history=yield_curve_history or [],
    )

    return {
        "snapshot_date": _date_text(snapshot.get("snapshot_date")),
        "computed_at": _datetime_text(snapshot.get("computed_at")),
        "state": state,
        "stress_score": overall_caution_score,
        "macro_stress_score": macro_stress,
        "tape_pressure_score": tape_pressure_score,
        "overall_caution_score": overall_caution_score,
        "overall_read": overall_read,
        "primary_driver": primary_driver,
        "driver_detail": driver_detail,
        "deployment_score": deployment_score,
        "macro_zone": snapshot.get("zone"),
        "coverage": coverage,
        "summary": summary,
        "action_text": action_text,
        "driving": _driving_read(
            overall_read=overall_read,
            primary_driver=primary_driver,
            tape_stress=tape_stress,
            vix_close=vix_close,
            hy_change_bps=hy_change_bps,
            breadth_pct=breadth_pct,
        ),
        "what_matters": _what_matters(
            overall_read=overall_read,
            primary_driver=primary_driver,
            vix_close=vix_close,
            hy_spread=hy_spread,
            breadth_pct=breadth_pct,
            crowding_score=crowding_score,
            macro_stress_score=macro_stress,
            tape_stress=tape_stress,
        ),
        "what_to_do": _what_to_do(
            overall_read,
            alert_active,
            primary_driver,
            tape_stress,
        ),
        "watch_items": _watch_items(),
        "trend": trends,
        "market_shifts": _build_market_shifts(trends),
        "flags": flags,
        "alert": {
            "active": alert_active,
            "priority": priority,
            "reason": "Severe overall-caution threshold crossed." if alert_active else None,
        },
        "bond_signals": {
            "as_of": yield_curve.as_of if yield_curve else None,
            "ten_year_two_year_bps": yield_curve.ten_year_two_year_bps if yield_curve else None,
            "ten_year_three_month_bps": yield_curve.ten_year_three_month_bps
            if yield_curve
            else None,
        },
        "credit_signal": {
            "latest_date": hy_change.latest_date if hy_change else None,
            "latest_value": hy_change.latest_value if hy_change else hy_spread,
            "prior_date": hy_change.prior_date if hy_change else None,
            "prior_value": hy_change.prior_value if hy_change else None,
            "change_bps": hy_change.change_bps if hy_change else None,
        },
        "evidence": _build_evidence(
            overall_caution_score=overall_caution_score,
            vix_close=vix_close,
            hy_spread=hy_spread,
            hy_change_bps=hy_change_bps,
            breadth_pct=breadth_pct,
            yield_curve=yield_curve,
            crowding_score=crowding_score,
            crowding_corr=crowding_corr,
            tape_stress=tape_stress,
            trends=trends,
        ),
    }


def get_latest_yield_curve() -> YieldCurveEvidence | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT observation_date, spread_10y_2y, spread_10y_3m
            FROM yield_curve
            WHERE spread_10y_2y IS NOT NULL
               OR spread_10y_3m IS NOT NULL
            ORDER BY observation_date DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        return None
    return YieldCurveEvidence(
        as_of=_date_text(row[0]),
        ten_year_two_year_bps=None if row[1] is None else float(row[1]) * 100.0,
        ten_year_three_month_bps=None if row[2] is None else float(row[2]) * 100.0,
    )


def get_yield_curve_history(days: int = 45) -> list[YieldCurveHistoryPoint]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT observation_date, spread_10y_2y, spread_10y_3m
            FROM yield_curve
            WHERE observation_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
              AND (spread_10y_2y IS NOT NULL OR spread_10y_3m IS NOT NULL)
            ORDER BY observation_date ASC
            """,
        ).fetchall()
    return [
        YieldCurveHistoryPoint(
            as_of=_date_text(row[0]),
            ten_year_two_year_bps=None if row[1] is None else float(row[1]) * 100.0,
            ten_year_three_month_bps=None if row[2] is None else float(row[2]) * 100.0,
        )
        for row in rows
    ]


def get_hy_oas_change() -> HyOasChange | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            WITH latest AS (
                SELECT as_of_date, hy_spread
                FROM fear_greed_inputs
                WHERE hy_spread IS NOT NULL
                ORDER BY as_of_date DESC
                LIMIT 1
            ),
            prior AS (
                SELECT as_of_date, hy_spread
                FROM fear_greed_inputs
                WHERE hy_spread IS NOT NULL
                  AND as_of_date <= (SELECT as_of_date - INTERVAL '90 days' FROM latest)
                ORDER BY as_of_date DESC
                LIMIT 1
            )
            SELECT latest.as_of_date, latest.hy_spread,
                   prior.as_of_date, prior.hy_spread,
                   (latest.hy_spread - prior.hy_spread) * 100.0
            FROM latest
            LEFT JOIN prior ON TRUE
            """,
        ).fetchone()
    if row is None:
        return None
    return HyOasChange(
        latest_date=_date_text(row[0]),
        latest_value=_maybe_float(row[1]),
        prior_date=_date_text(row[2]),
        prior_value=_maybe_float(row[3]),
        change_bps=_maybe_float(row[4]),
    )


def get_conditions_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return build_conditions_payload(
        snapshot,
        yield_curve=get_latest_yield_curve(),
        hy_change=get_hy_oas_change(),
        tape_stress=get_tape_stress(),
        macro_history=repository.get_history(days=45),
        yield_curve_history=get_yield_curve_history(days=45),
    )
