"""Plain-language market-condition interpretation for Today.

This module intentionally derives from the existing macro gate snapshot and
nearby stored market evidence. It does not introduce a second scoring model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from ..storage.facade import get_storage
from . import repository


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
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{precision}f}{unit}"


def _crowding_detail(score: float | None, corr: float | None) -> str:
    if score is None:
        return "Unavailable"
    if corr is not None:
        return f"Corr {corr:+.2f}"
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


def _severe_flags(
    *,
    deployment_score: float | None,
    vix_close: float | None,
    hy_spread: float | None,
    hy_change_bps: float | None,
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
    return flags


def _evidence_tone(kind: str, value: float | None) -> str:
    if value is None:
        return "neutral"
    tone = "neutral"
    if kind == "stress":
        if value >= 60:
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
        "stress": TrendConfig("stress", "Stress", False, 3.0, 0),
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
            "stress": "Stress easing",
            "vix": "Volatility easing",
            "hy_oas": "Credit improving",
            "breadth": "Breadth improving",
            "ten_year_two_year": "Curve improving",
            "ten_year_three_month": "Yield curve improving",
            "crowding": "Crowding improving",
        }.get(key, f"{trend['label']} improving")
    if direction == "worsening":
        return {
            "stress": "Stress rising",
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


def _state_copy(state: str, flags: list[str]) -> tuple[str, str]:
    if state == "Elevated":
        return (
            "Market stress is elevated.",
            "Protect the plan first. Avoid adding broad risk until volatility, credit, and breadth stabilize.",
        )
    if state == "Calm":
        return (
            "Market conditions are supportive.",
            "Stay with the plan. New buys can use normal selectivity, while still checking concentration.",
        )
    if flags:
        return (
            "Market stress is elevated.",
            "Protect the plan first. Avoid adding broad risk until volatility, credit, and breadth stabilize.",
        )
    return (
        "Market stress is low-to-moderate.",
        "Stay invested according to plan. Be selective with new buys. Do not chase broad market strength just because indexes are up.",
    )


def _what_matters(
    *,
    state: str,
    vix_close: float | None,
    hy_spread: float | None,
    breadth_pct: float | None,
    crowding_score: float | None,
) -> list[str]:
    if state == "Elevated":
        return [
            "Stress is high enough that capital protection matters more than new risk.",
            "Volatility, credit, or the composite score has crossed a severe threshold.",
            "Wait for evidence to improve before treating weakness as opportunity.",
        ]

    first = (
        "Credit and volatility are calm, so this is not a panic tape."
        if (vix_close is not None and vix_close < 20 and hy_spread is not None and hy_spread < 3.5)
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


def _what_to_do(state: str, alert_active: bool) -> list[str]:
    if state == "Elevated" or alert_active:
        return [
            "Do not add broad risk until the brief improves.",
            "Review concentration and cash needs before making new commitments.",
            "Keep long-term allocation changes tied to your written plan.",
        ]
    if state == "Calm":
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
        "VIX above 30 would move volatility from calm to stressed.",
        "HY OAS above 5 or widening 100 bps would make credit a real warning.",
        "Deployment score below 40 would turn the brief defensive.",
        "Breadth breaking materially lower would weaken rally quality.",
    ]


def _build_evidence(
    *,
    stress_score: int | None,
    vix_close: float | None,
    hy_spread: float | None,
    hy_change_bps: float | None,
    breadth_pct: float | None,
    yield_curve: YieldCurveEvidence | None,
    crowding_score: float | None,
    crowding_corr: float | None,
    trends: dict[str, Any],
) -> list[dict[str, Any]]:
    ten_two = yield_curve.ten_year_two_year_bps if yield_curve else None
    ten_three_month = yield_curve.ten_year_three_month_bps if yield_curve else None
    return [
        {
            "key": "stress",
            "label": "Stress",
            "value": (_fmt_number(float(stress_score), 0) if stress_score is not None else "-"),
            "detail": (
                "Unavailable"
                if stress_score is None
                else "Low-to-moderate"
                if stress_score < 60
                else "Elevated"
            ),
            "tone": _evidence_tone(
                "stress", float(stress_score) if stress_score is not None else None
            ),
            "tooltip": "Stress is the inverse of the deployment score. Higher means market conditions are less supportive.",
            "trend": trends.get("stress"),
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
            "tooltip": "Crowding estimates whether popular trades are clustering together. A 0 score means factor correlation is extremely high, not missing data.",
            "trend": trends.get("crowding"),
        },
    ]


def build_conditions_payload(
    snapshot: dict[str, Any],
    *,
    yield_curve: YieldCurveEvidence | None = None,
    hy_change: HyOasChange | None = None,
    macro_history: list[dict[str, Any]] | None = None,
    yield_curve_history: list[YieldCurveHistoryPoint] | None = None,
) -> dict[str, Any]:
    deployment_score = _maybe_float(snapshot.get("deployment_score"))
    vix_close = _maybe_float(snapshot.get("vix_close"))
    hy_spread = _maybe_float(snapshot.get("hy_spread"))
    breadth_pct = _maybe_float(snapshot.get("breadth_pct"))
    crowding_corr = _maybe_float(snapshot.get("factor_crowding_corr"))
    crowding_score = _maybe_float(snapshot.get("crowding_score"))
    stress = _stress_score(deployment_score)
    hy_change_bps = hy_change.change_bps if hy_change else None
    flags = _severe_flags(
        deployment_score=deployment_score,
        vix_close=vix_close,
        hy_spread=hy_spread,
        hy_change_bps=hy_change_bps,
    )
    state = "Elevated" if flags else _zone_state(snapshot.get("zone"))
    summary, action_text = _state_copy(state, flags)
    alert_active = state == "Elevated"
    priority = (
        "critical"
        if alert_active and stress is not None and stress >= 75
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
        "stress_score": stress,
        "deployment_score": deployment_score,
        "macro_zone": snapshot.get("zone"),
        "coverage": coverage,
        "summary": summary,
        "action_text": action_text,
        "what_matters": _what_matters(
            state=state,
            vix_close=vix_close,
            hy_spread=hy_spread,
            breadth_pct=breadth_pct,
            crowding_score=crowding_score,
        ),
        "what_to_do": _what_to_do(state, alert_active),
        "watch_items": _watch_items(),
        "trend": trends,
        "market_shifts": _build_market_shifts(trends),
        "flags": flags,
        "alert": {
            "active": alert_active,
            "priority": priority,
            "reason": "Severe market-stress threshold crossed." if alert_active else None,
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
            stress_score=stress,
            vix_close=vix_close,
            hy_spread=hy_spread,
            hy_change_bps=hy_change_bps,
            breadth_pct=breadth_pct,
            yield_curve=yield_curve,
            crowding_score=crowding_score,
            crowding_corr=crowding_corr,
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
        macro_history=repository.get_history(days=45),
        yield_curve_history=get_yield_curve_history(days=45),
    )
