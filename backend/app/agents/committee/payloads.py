"""Per-symbol payload fetchers that hydrate analyst context slices.

The readiness gate (see ``readiness.py``) only guarantees that the
underlying rows exist; the runner still has to lift them out of the
DB and shape them into the dict each analyst's system prompt promises
to reference by name.

These fetchers are intentionally *narrow* — one table or one join
each, query-only, no LLM cost, no side effects — so the graph can
call them in series without inflating the per-run latency budget.
They return ``None`` when the underlying row is missing instead of
raising, so the runner can simply omit the field from the payload.
"""

from __future__ import annotations

import json
import math
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

from . import candidate_fundamentals as _candidate_fundamentals

logger = get_logger(__name__)


# Latest indicator columns we hand to the technical analyst. The five
# fields enforced by readiness.py (rsi_14, macd, atr_14, sma_50,
# sma_200) are a subset; we also pull every other indicator the
# pipeline already computes so the prompt can reference them by name
# without an extra query.
_TECHNICAL_COLUMNS: tuple[str, ...] = (
    "date",
    "calculated_at",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "sma_5",
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_20",
    "ema_50",
    "ema_200",
    "atr_14",
    "stoch_k",
    "stoch_d",
)

# How many recent rows to scan when computing a 5-bar slope. Keeps the
# derived-field computation cheap while still smoothing single-day
# noise out of the slope read.
_SLOPE_LOOKBACK_ROWS = 6


_VALUATION_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "pe_ratio_trailing",
    "pe_ratio_forward",
    "ps_ratio",
    "pb_ratio",
    "peg_ratio",
    "dividend_yield",
    "payout_ratio",
)
_CASH_FLOW_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "operating_cash_flow",
    "free_cash_flow",
    "capital_expenditure",
    "fcf_yield",
    "cash_flow_margin",
    "fcf_per_share",
    "cash_conversion_ratio",
)
_HEALTH_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "f_score",
    "f_score_components",
    "z_score",
    "z_score_zone",
)
_SYMBOL_META_COLUMNS: tuple[str, ...] = (
    "company_name",
    "sector",
    "industry",
    "exchange",
)
_EARNINGS_SURPRISE_LIMIT = 4

# Literature-standard fields the prompts would cite but our schema does
# not ingest. Surfaced through the log line so silent ingestion gaps
# stay visible without rerunning the audit by hand.
_FUNDAMENTALS_LITERATURE_GAPS: tuple[str, ...] = (
    "gross_margin",
    "operating_margin",
    "net_margin",
    "roe",
    "roic",
    "revenue_growth_yoy",
    "eps_growth_yoy",
    "debt_to_equity",
    "ev_ebitda",
    "insider_txns_90d",
    "market_cap",
)


def fetch_fundamental_snapshot(symbol: str) -> dict[str, Any] | None:
    """Return the joined fundamentals snapshot the analyst's prompt cites.

    Pulls the latest row from each of the populated fundamentals
    sources:

    - ``symbols``                 — sector / industry / exchange metadata
    - ``valuation_metrics``       — P/E (trailing & forward), P/S, P/B,
                                    PEG, dividend yield, payout ratio
    - ``cash_flow_metrics``       — operating cash flow, free cash flow,
                                    FCF yield, cash-flow margin
    - ``financial_health_scores`` — Piotroski F-score, Altman Z-score
    - ``earnings_surprises``      — last few EPS surprises
    - ``watchlist_snapshots``     — pillar score, company-health
                                    narrative, earnings days-away

    Returns ``None`` only when every source is empty — partial coverage
    still ships so the analyst can reason from whatever is available.
    Logs one summary line per call listing which sources surfaced
    fields and which literature-standard fields the schema lacks.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None

    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            valuation_row = _latest_by_as_of_date(
                conn,
                table="valuation_metrics",
                columns=_VALUATION_COLUMNS,
                symbol=upper_symbol,
            )
            cash_flow_row = _latest_by_as_of_date(
                conn,
                table="cash_flow_metrics",
                columns=_CASH_FLOW_COLUMNS,
                symbol=upper_symbol,
            )
            health_row = _latest_by_as_of_date(
                conn,
                table="financial_health_scores",
                columns=_HEALTH_COLUMNS,
                symbol=upper_symbol,
            )
            symbol_meta_row = conn.execute(
                f"""
                SELECT {", ".join(_SYMBOL_META_COLUMNS)}
                FROM symbols
                WHERE upper(symbol) = upper(%s)
                LIMIT 1
                """,
                (upper_symbol,),
            ).fetchone()
            earnings_rows = conn.execute(
                """
                SELECT earnings_date, fiscal_quarter, eps_estimate, eps_actual,
                       surprise_pct, surprise_direction, revenue_estimate, revenue_actual
                FROM earnings_surprises
                WHERE upper(symbol) = upper(%s)
                ORDER BY earnings_date DESC NULLS LAST
                LIMIT %s
                """,
                (upper_symbol, _EARNINGS_SURPRISE_LIMIT),
            ).fetchall()
            snapshot_row = conn.execute(
                """
                SELECT
                    s.fetched_at,
                    s.fundamental_score,
                    s.overall_score,
                    s.company_health,
                    s.earnings_date,
                    s.earnings_days_away,
                    s.raw_metrics
                FROM watchlist_snapshots s
                JOIN watchlist_items i ON i.id = s.item_id
                WHERE upper(i.symbol) = upper(%s)
                ORDER BY s.fetched_at DESC
                LIMIT 1
                """,
                (upper_symbol,),
            ).fetchone()
    except Exception as exc:
        logger.warning(
            "committee_payload_fundamental_query_failed",
            symbol=upper_symbol,
            error=str(exc),
        )
        return None

    company = _row_to_dict(symbol_meta_row, _SYMBOL_META_COLUMNS) or None
    valuation = _row_to_dict(valuation_row, _VALUATION_COLUMNS) or None
    cash_flow = _row_to_dict(cash_flow_row, _CASH_FLOW_COLUMNS) or None
    health = _row_to_dict(health_row, _HEALTH_COLUMNS) or None
    earnings_history: list[dict[str, Any]] = []
    for row in earnings_rows or []:
        entry = {
            "earnings_date": _to_jsonable(row[0]),
            "fiscal_quarter": row[1],
            "eps_estimate": _to_jsonable(row[2]),
            "eps_actual": _to_jsonable(row[3]),
            "surprise_pct": _to_jsonable(row[4]),
            "surprise_direction": row[5],
            "revenue_estimate": _to_jsonable(row[6]),
            "revenue_actual": _to_jsonable(row[7]),
        }
        if any(v not in (None, "") for v in entry.values()):
            earnings_history.append(entry)

    watchlist = None
    if snapshot_row is not None:
        (
            fetched_at,
            fundamental_score,
            overall_score,
            company_health,
            earnings_date,
            earnings_days_away,
            raw_metrics,
        ) = snapshot_row
        raw_metrics_dict = _json_dict(raw_metrics)
        fundamental_component = (
            raw_metrics_dict.get("fundamental") if raw_metrics_dict else None
        )
        watchlist = _drop_empty(
            {
                "fetched_at": _to_jsonable(fetched_at),
                "fundamental_score": _to_jsonable(fundamental_score),
                "overall_score": _to_jsonable(overall_score),
                "company_health": company_health,
                "earnings_date": _to_jsonable(earnings_date),
                "earnings_days_away": _to_jsonable(earnings_days_away),
                "fundamental_component": (
                    fundamental_component if isinstance(fundamental_component, dict) else None
                ),
            }
        )

    # On-demand candidate snapshot — present for scanner-sourced runs after
    # the fan-out's per-candidate fetch step. Includes the L3 spec fields
    # (gross/operating/net margins, ROE/ROIC, D/E, EV/EBITDA, YoY growth)
    # that the watchlist-scoped cron does not ingest.
    candidate_quarterly = _candidate_fundamentals.latest_snapshot(upper_symbol)

    sections = {
        "company": company,
        "valuation": valuation,
        "cash_flow": cash_flow,
        "health": health,
        "earnings_surprise_history": earnings_history or None,
        "watchlist": watchlist,
        "candidate_quarterly": candidate_quarterly,
    }
    populated = {k: v for k, v in sections.items() if v}
    if not populated:
        return None

    # Literature gaps only matter when the on-demand snapshot is absent;
    # the candidate_quarterly section carries those fields directly.
    remaining_gaps = (
        list(_FUNDAMENTALS_LITERATURE_GAPS) if candidate_quarterly is None else []
    )
    logger.info(
        "committee_payload_fundamental_coverage",
        symbol=upper_symbol,
        sources=sorted(populated.keys()),
        literature_gaps=remaining_gaps,
    )
    return populated


def _latest_by_as_of_date(
    conn: Any, *, table: str, columns: tuple[str, ...], symbol: str
) -> tuple[Any, ...] | None:
    """Latest row by ``as_of_date`` from ``table`` for ``symbol``."""
    sql = f"""
        SELECT {", ".join(columns)}
        FROM {table}
        WHERE upper(symbol) = upper(%s)
        ORDER BY as_of_date DESC NULLS LAST
        LIMIT 1
    """
    return conn.execute(sql, (symbol,)).fetchone()


def _row_to_dict(
    row: tuple[Any, ...] | None, columns: tuple[str, ...]
) -> dict[str, Any]:
    """Map a positional DB row to a JSON-safe dict; empty row → empty dict."""
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for col, value in zip(columns, row, strict=True):
        out[col] = _to_jsonable(value)
    return out


def fetch_news_sentiment(symbol: str, *, limit: int = 10) -> dict[str, Any] | None:
    """Return the latest news rows sorted ``published_at DESC``.

    The news analyst's prompt promises a freshness-ordered catalyst
    feed; the watchlist snapshot's pre-scored news ranks by sentiment
    or signal weight, which buries time-critical catalysts under
    older-but-strongly-toned coverage. Pulling ``news_cache`` directly
    by ``published_at DESC`` fixes that.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None

    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    headline,
                    summary,
                    url,
                    news_source_name,
                    published_at,
                    sentiment_score,
                    sentiment_label,
                    sentiment_confidence,
                    is_material_event,
                    impact_summary,
                    actionable_insight
                FROM news_cache
                WHERE upper(symbol) = upper(%s)
                ORDER BY published_at DESC NULLS LAST, fetched_at DESC NULLS LAST
                LIMIT %s
                """,
                (upper_symbol, limit),
            ).fetchall()
    except Exception as exc:
        logger.warning(
            "committee_payload_news_query_failed",
            symbol=upper_symbol,
            error=str(exc),
        )
        return None

    articles = [
        _drop_empty(
            {
                "headline": row[0],
                "summary": row[1],
                "url": row[2],
                "source": row[3],
                "published_at": _to_jsonable(row[4]),
                "sentiment_score": _to_jsonable(row[5]),
                "sentiment_label": row[6],
                "sentiment_confidence": _to_jsonable(row[7]),
                "is_material_event": row[8],
                "impact_summary": row[9],
                "actionable_insight": row[10],
            }
        )
        for row in rows
    ]
    if not articles:
        return None

    scores = [
        a["sentiment_score"]
        for a in articles
        if isinstance(a.get("sentiment_score"), (int, float))
    ]
    return _drop_empty(
        {
            "article_count": len(articles),
            "avg_sentiment_score": sum(scores) / len(scores) if scores else None,
            "articles": articles,
        }
    )


_PORTFOLIO_TOP_N = 5


def fetch_portfolio_context(
    symbol: str, household_id: str | None = None
) -> dict[str, Any] | None:
    """Return portfolio context for trader / risk / PM payloads.

    Surfaces the fields the trader prompt and IPS-style guardrails in
    risk + PM need to reason about sizing and concentration:

    - ``position_in_symbol``  : shares, cost basis, current value, weight
    - ``sector_exposure_pct`` : combined weight of every holding in the
                                same sector as ``symbol`` (so the trader
                                sees "we already own 28% in tech before
                                adding NVDA")
    - ``sector_breakdown``    : full sector weight map
    - ``top_5_positions``     : largest holdings by current value
    - ``cash_pct``            : cash balance / (cash + position value)

    Paper-trading accounts are excluded so the figures reflect live
    capital. ``household_id`` is accepted to mirror the IPS call
    signature; when supplied the query filters on it.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None

    household_filter = "AND a.household_account_id = %s" if household_id else ""
    household_params: tuple[Any, ...] = (household_id,) if household_id else ()

    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            per_symbol_rows = conn.execute(
                f"""
                SELECT
                    upper(p.symbol) AS symbol,
                    SUM(p.shares) AS shares,
                    SUM(p.shares * p.cost_basis) / NULLIF(SUM(p.shares), 0) AS avg_cost,
                    MAX(lpc.price) AS price,
                    SUM(p.shares * COALESCE(lpc.price, p.cost_basis)) AS value,
                    MAX(s.sector) AS sector
                FROM portfolio_positions p
                JOIN portfolio_accounts a ON a.id = p.account_id
                LEFT JOIN (
                    SELECT symbol, price
                    FROM (
                        SELECT
                            upper(symbol) AS symbol,
                            price,
                            ROW_NUMBER() OVER (
                                PARTITION BY upper(symbol)
                                ORDER BY cached_at DESC
                            ) AS rn
                        FROM price_cache
                    ) ranked_price_cache
                    WHERE rn = 1
                ) lpc ON lpc.symbol = upper(p.symbol)
                LEFT JOIN symbols s ON upper(s.symbol) = upper(p.symbol)
                WHERE a.account_type != 'paper'
                  AND p.position_type != 'paper'
                  {household_filter}
                GROUP BY upper(p.symbol)
                """,
                household_params or None,
            ).fetchall()
            cash_row = conn.execute(
                f"""
                SELECT COALESCE(SUM(a.cash_balance), 0)
                FROM portfolio_accounts a
                WHERE a.account_type != 'paper'
                  {household_filter}
                """,
                household_params or None,
            ).fetchone()
    except Exception as exc:
        logger.warning(
            "committee_payload_portfolio_query_failed",
            symbol=upper_symbol,
            error=str(exc),
        )
        return None

    positions: list[dict[str, Any]] = []
    for row in per_symbol_rows or []:
        shares_val = _to_finite_float(row[1])
        if not shares_val or shares_val <= 0:
            continue
        value = _to_finite_float(row[4]) or 0.0
        positions.append(
            {
                "symbol": row[0],
                "shares": shares_val,
                "avg_cost": _to_finite_float(row[2]),
                "current_price": _to_finite_float(row[3]),
                "value": value,
                "sector": row[5],
            }
        )
    positions_value = sum(p["value"] for p in positions)
    cash_balance = _to_finite_float(cash_row[0]) if cash_row else 0.0
    total_capital = positions_value + (cash_balance or 0.0)

    target_sector: str | None = None
    position_in_symbol: dict[str, Any] | None = None
    for pos in positions:
        if pos["symbol"] == upper_symbol:
            target_sector = pos["sector"]
            position_in_symbol = _drop_empty(
                {
                    "shares": pos["shares"],
                    "cost_basis": pos["avg_cost"],
                    "current_price": pos["current_price"],
                    "current_value": pos["value"],
                    "weight_pct": (
                        (pos["value"] / total_capital) * 100.0
                        if total_capital and total_capital > 0
                        else None
                    ),
                    "sector": pos["sector"],
                }
            )
            break

    if target_sector is None:
        try:
            with cm.connection() as conn:
                sector_row = conn.execute(
                    """
                    SELECT sector
                    FROM symbols
                    WHERE upper(symbol) = upper(%s)
                    LIMIT 1
                    """,
                    (upper_symbol,),
                ).fetchone()
                if sector_row and sector_row[0] is not None:
                    target_sector = str(sector_row[0])
        except Exception as exc:
            logger.warning(
                "committee_payload_portfolio_sector_lookup_failed",
                symbol=upper_symbol,
                error=str(exc),
            )

    sector_totals: dict[str, float] = {}
    for pos in positions:
        sector = pos["sector"] or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + pos["value"]
    sector_breakdown = (
        {
            sector: round((value / total_capital) * 100.0, 2)
            for sector, value in sector_totals.items()
        }
        if total_capital and total_capital > 0
        else {}
    )
    sector_exposure_pct = (
        sector_breakdown.get(target_sector or "", 0.0) if sector_breakdown else None
    )

    top_5 = sorted(positions, key=lambda p: p["value"], reverse=True)[:_PORTFOLIO_TOP_N]
    top_5_positions = [
        {
            "symbol": p["symbol"],
            "weight_pct": (
                round((p["value"] / total_capital) * 100.0, 2)
                if total_capital and total_capital > 0
                else None
            ),
            "sector": p["sector"],
        }
        for p in top_5
    ]
    cash_pct = (
        ((cash_balance or 0.0) / total_capital) * 100.0
        if total_capital and total_capital > 0
        else None
    )

    return _drop_empty(
        {
            "held": position_in_symbol is not None,
            "position_in_symbol": position_in_symbol,
            "target_sector": target_sector,
            "sector_exposure_pct": sector_exposure_pct,
            "sector_breakdown": sector_breakdown or None,
            "top_5_positions": top_5_positions or None,
            "cash_pct": cash_pct,
            "cash_balance": cash_balance,
            "total_capital": total_capital,
            "positions_value": positions_value,
            "num_holdings": len(positions),
        }
    )


def fetch_technical_indicators(symbol: str) -> dict[str, Any] | None:
    """Return the latest technical_indicators row + derived fields, or None.

    Derived fields (computed here, not stored in the table):
    - ``ma_slope_50_pct``      : 5-bar % change of ``sma_50``
    - ``ma_slope_200_pct``     : 5-bar % change of ``sma_200``
    - ``price_vs_sma_50_pct``  : (latest close - sma_50) / sma_50 * 100
    - ``price_vs_sma_200_pct`` : (latest close - sma_200) / sma_200 * 100
    - ``rsi_zone``             : "oversold" (<30) / "neutral" / "overbought" (>70)
    - ``bb_pct_b``             : (close - bb_lower) / (bb_upper - bb_lower)

    The trailing close used for the comparisons comes from
    ``day_bars`` so the slope/zone use the same anchor the trader will.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None

    cm = get_connection_manager()
    columns_sql = ", ".join(_TECHNICAL_COLUMNS)
    try:
        with cm.connection() as conn:
            latest_rows = conn.execute(
                f"""
                SELECT {columns_sql}
                FROM technical_indicators
                WHERE upper(symbol) = upper(%s)
                ORDER BY date DESC
                LIMIT %s
                """,
                (upper_symbol, _SLOPE_LOOKBACK_ROWS),
            ).fetchall()
            close_row = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE upper(symbol) = upper(%s)
                ORDER BY date DESC
                LIMIT 1
                """,
                (upper_symbol,),
            ).fetchone()
    except Exception as exc:
        logger.warning(
            "committee_payload_technical_query_failed",
            symbol=upper_symbol,
            error=str(exc),
        )
        return None

    if not latest_rows:
        return None

    rows = [dict(zip(_TECHNICAL_COLUMNS, row, strict=True)) for row in latest_rows]
    latest = rows[0]
    payload: dict[str, Any] = {
        col: _to_jsonable(latest.get(col)) for col in _TECHNICAL_COLUMNS
    }

    latest_close = _to_finite_float(close_row[0]) if close_row else None
    payload["latest_close"] = latest_close

    payload["ma_slope_50_pct"] = _slope_pct(rows, "sma_50")
    payload["ma_slope_200_pct"] = _slope_pct(rows, "sma_200")
    payload["price_vs_sma_50_pct"] = _delta_vs_pct(latest_close, latest.get("sma_50"))
    payload["price_vs_sma_200_pct"] = _delta_vs_pct(latest_close, latest.get("sma_200"))
    payload["rsi_zone"] = _rsi_zone(latest.get("rsi_14"))
    payload["bb_pct_b"] = _bb_pct_b(
        latest_close,
        latest.get("bb_lower"),
        latest.get("bb_upper"),
    )
    return payload


# ---------- small helpers ----------


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if v is not None and v not in ([], {})}


def _json_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _to_finite_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(as_float):
        return None
    return as_float


def _to_jsonable(value: object) -> Any:
    """Coerce DB row values into something json.dumps + the prompts can read.

    Numbers stay numbers; datetimes/dates become ISO strings; everything
    else passes through. NaN/inf are flattened to None so the prompt
    never sees a non-finite that JSON can't represent.
    """
    if value is None:
        return None
    if isinstance(value, (int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            return str(value)
    return value


def _slope_pct(rows: list[dict[str, Any]], field: str) -> float | None:
    """% change between the latest and the oldest available row for ``field``.

    Returns None when fewer than two usable rows exist or the older
    value is non-positive (would make the % change undefined).
    """
    values: list[float] = []
    for row in rows:
        as_float = _to_finite_float(row.get(field))
        if as_float is not None:
            values.append(as_float)
    if len(values) < 2:
        return None
    latest = values[0]
    earliest = values[-1]
    if earliest <= 0:
        return None
    return ((latest - earliest) / earliest) * 100.0


def _delta_vs_pct(close: float | None, ma_value: object) -> float | None:
    ma = _to_finite_float(ma_value)
    if close is None or ma is None or ma <= 0:
        return None
    return ((close - ma) / ma) * 100.0


def _rsi_zone(rsi: object) -> str | None:
    value = _to_finite_float(rsi)
    if value is None:
        return None
    if value < 30:
        return "oversold"
    if value > 70:
        return "overbought"
    return "neutral"


def _bb_pct_b(close: float | None, lower: object, upper: object) -> float | None:
    lower_f = _to_finite_float(lower)
    upper_f = _to_finite_float(upper)
    if close is None or lower_f is None or upper_f is None:
        return None
    width = upper_f - lower_f
    if width <= 0:
        return None
    return (close - lower_f) / width
