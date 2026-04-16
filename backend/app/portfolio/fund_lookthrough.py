"""ETF and fund look-through helpers for portfolio analytics."""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

import pandas as pd
import yfinance as yf

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)
_LOOKTHROUGH_CACHE_SOURCE = "yfinance_fund_lookthrough"
_LOOKTHROUGH_CACHE_MAX_AGE_DAYS = 7


@dataclass(slots=True)
class ExposureItem:
    symbol: str
    current_value: float
    sector: str | None = None


@dataclass(slots=True)
class FundHolding:
    symbol: str
    name: str | None
    weight: float


@dataclass(slots=True)
class FundLookthroughProfile:
    symbol: str
    quote_type: str | None
    family: str | None
    category: str | None
    legal_type: str | None
    description: str | None
    top_holdings: list[FundHolding] = field(default_factory=list)
    sector_weightings: dict[str, float] = field(default_factory=dict)
    asset_classes: dict[str, float] = field(default_factory=dict)
    source: str = "yfinance"
    as_of_date: str | None = None


@dataclass(slots=True)
class ExposureBreakdown:
    total_value: float
    vehicle_values: dict[str, float]
    single_name_values: dict[str, float]
    risk_bucket_values: dict[str, float]
    sector_values: dict[str, float]
    lookthrough_covered_value: float


def _clamp_weight(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _normalize_sector_label(value: str) -> str:
    words = value.replace("_", " ").strip()
    return words.title() if words else "Unknown"


def _normalize_weight_map(values: dict[str, float]) -> dict[str, float]:
    cleaned = {
        _normalize_sector_label(str(key)): _clamp_weight(weight)
        for key, weight in values.items()
        if _clamp_weight(weight) > 0
    }
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in cleaned.items()}


def _serialize_profile(profile: FundLookthroughProfile) -> str:
    return json.dumps(asdict(profile))


def _parse_profile(payload: str | dict[str, object]) -> FundLookthroughProfile | None:
    raw: dict[str, object]
    if isinstance(payload, str):
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            return None
    elif isinstance(payload, dict):
        raw = payload
    else:
        return None

    top_holdings: list[FundHolding] = []
    raw_top_holdings = raw.get("top_holdings")
    for item in raw_top_holdings if isinstance(raw_top_holdings, list) else []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        weight = _clamp_weight(item.get("weight"))
        if weight <= 0:
            continue
        top_holdings.append(
            FundHolding(
                symbol=symbol,
                name=str(item.get("name")) if item.get("name") else None,
                weight=weight,
            )
        )

    sector_weightings = {}
    raw_sectors = raw.get("sector_weightings") or {}
    if isinstance(raw_sectors, dict):
        sector_weightings = {
            _normalize_sector_label(str(key)): _clamp_weight(value)
            for key, value in raw_sectors.items()
            if _clamp_weight(value) > 0
        }

    asset_classes = {}
    raw_assets = raw.get("asset_classes") or {}
    if isinstance(raw_assets, dict):
        asset_classes = {
            str(key): _clamp_weight(value)
            for key, value in raw_assets.items()
            if _clamp_weight(value) > 0
        }

    if not top_holdings and not sector_weightings:
        return None

    return FundLookthroughProfile(
        symbol=str(raw.get("symbol") or "").upper(),
        quote_type=str(raw.get("quote_type")) if raw.get("quote_type") else None,
        family=str(raw.get("family")) if raw.get("family") else None,
        category=str(raw.get("category")) if raw.get("category") else None,
        legal_type=str(raw.get("legal_type")) if raw.get("legal_type") else None,
        description=str(raw.get("description")) if raw.get("description") else None,
        top_holdings=top_holdings,
        sector_weightings=sector_weightings,
        asset_classes=asset_classes,
        source=str(raw.get("source") or "yfinance"),
        as_of_date=str(raw.get("as_of_date")) if raw.get("as_of_date") else None,
    )


def _load_cached_profile(
    storage: PortfolioStorage,
    symbol: str,
) -> FundLookthroughProfile | None:
    cutoff = dt.date.today() - dt.timedelta(days=_LOOKTHROUGH_CACHE_MAX_AGE_DAYS)
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT as_of_date, payload
            FROM reference_cache
            WHERE symbol = %s AND source = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [symbol, _LOOKTHROUGH_CACHE_SOURCE],
        ).fetchone()

    if not isinstance(row, (tuple, list)) or len(row) < 2:
        return None

    raw_as_of_date = row[0]
    if isinstance(raw_as_of_date, dt.datetime):
        as_of_date = raw_as_of_date.date()
    elif isinstance(raw_as_of_date, str):
        try:
            as_of_date = dt.date.fromisoformat(raw_as_of_date)
        except ValueError:
            return None
    elif isinstance(raw_as_of_date, dt.date):
        as_of_date = raw_as_of_date
    else:
        return None
    if as_of_date < cutoff:
        return None

    profile = _parse_profile(row[1])
    if profile is not None and profile.as_of_date is None:
        profile.as_of_date = str(as_of_date)
    return profile


def _build_profile_from_yfinance(symbol: str) -> FundLookthroughProfile | None:
    try:
        ticker = yf.Ticker(symbol)
        funds_data = ticker.funds_data
        top_holdings_frame = funds_data.top_holdings
        sector_weightings = getattr(funds_data, "sector_weightings", None) or {}
        asset_classes = getattr(funds_data, "asset_classes", None) or {}
        fund_overview = getattr(funds_data, "fund_overview", None) or {}
        quote_type = getattr(funds_data, "quote_type", None)
        description = getattr(funds_data, "description", None)
    except Exception as exc:  # pragma: no cover - passthrough from remote source
        logger.debug("fund_lookthrough_fetch_failed", symbol=symbol, error=str(exc))
        return None

    holdings: list[FundHolding] = []
    if isinstance(top_holdings_frame, pd.DataFrame) and not top_holdings_frame.empty:
        for holding_symbol, row in top_holdings_frame.iterrows():
            holding_pct = _clamp_weight(row.get("Holding Percent"))
            normalized_symbol = str(holding_symbol or "").upper().strip()
            if not normalized_symbol or holding_pct <= 0:
                continue
            holdings.append(
                FundHolding(
                    symbol=normalized_symbol,
                    name=str(row.get("Name")) if row.get("Name") else None,
                    weight=holding_pct,
                )
            )

    normalized_sectors = {}
    if isinstance(sector_weightings, dict):
        normalized_sectors = {
            _normalize_sector_label(str(key)): _clamp_weight(value)
            for key, value in sector_weightings.items()
            if _clamp_weight(value) > 0
        }

    normalized_assets = {}
    if isinstance(asset_classes, dict):
        normalized_assets = {
            str(key): _clamp_weight(value)
            for key, value in asset_classes.items()
            if _clamp_weight(value) > 0
        }

    if not holdings and not normalized_sectors:
        return None

    return FundLookthroughProfile(
        symbol=symbol,
        quote_type=str(quote_type) if quote_type else None,
        family=str(fund_overview.get("family")) if fund_overview.get("family") else None,
        category=str(fund_overview.get("categoryName"))
        if fund_overview.get("categoryName")
        else None,
        legal_type=str(fund_overview.get("legalType"))
        if fund_overview.get("legalType")
        else None,
        description=str(description) if description else None,
        top_holdings=holdings,
        sector_weightings=normalized_sectors,
        asset_classes=normalized_assets,
        as_of_date=dt.date.today().isoformat(),
    )


def get_fund_lookthroughs(
    symbols: list[str],
    storage: PortfolioStorage | None,
) -> dict[str, FundLookthroughProfile]:
    if storage is None:
        return {}

    profiles: dict[str, FundLookthroughProfile] = {}
    normalized_symbols = sorted({str(symbol).upper().strip() for symbol in symbols if symbol})
    for symbol in normalized_symbols:
        cached = _load_cached_profile(storage, symbol)
        if cached is not None:
            profiles[symbol] = cached
            continue

        profile = _build_profile_from_yfinance(symbol)
        if profile is None:
            continue

        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO reference_cache (symbol, as_of_date, payload, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date, source)
                DO UPDATE SET payload = EXCLUDED.payload
                """,
                [
                    symbol,
                    profile.as_of_date or dt.date.today().isoformat(),
                    _serialize_profile(profile),
                    _LOOKTHROUGH_CACHE_SOURCE,
                ],
            )
            conn.commit()

        profiles[symbol] = profile

    return profiles


def build_exposure_breakdown(
    items: list[ExposureItem],
    storage: PortfolioStorage | None,
) -> ExposureBreakdown:
    usable_items = [
        ExposureItem(
            symbol=str(item.symbol).upper(),
            current_value=float(item.current_value),
            sector=item.sector,
        )
        for item in items
        if item.current_value is not None and float(item.current_value) > 0
    ]
    profiles = get_fund_lookthroughs([item.symbol for item in usable_items], storage)

    vehicle_values: dict[str, float] = defaultdict(float)
    single_name_values: dict[str, float] = defaultdict(float)
    risk_bucket_values: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    total_value = 0.0
    lookthrough_covered_value = 0.0

    for item in usable_items:
        value = float(item.current_value)
        total_value += value
        vehicle_values[item.symbol] += value

        profile = profiles.get(item.symbol)
        if profile is None or not profile.top_holdings:
            single_name_values[item.symbol] += value
            risk_bucket_values[item.symbol] += value
            sector_values[item.sector or "Unknown"] += value
            continue

        lookthrough_covered_value += value
        allocated_weight = 0.0
        for holding in profile.top_holdings:
            if holding.weight <= 0:
                continue
            exposure_value = value * holding.weight
            single_name_values[holding.symbol] += exposure_value
            risk_bucket_values[holding.symbol] += exposure_value
            allocated_weight += holding.weight

        normalized_sector_weights = _normalize_weight_map(profile.sector_weightings)
        if normalized_sector_weights:
            for sector, weight in normalized_sector_weights.items():
                sector_values[sector] += value * weight

        residual_weight = max(0.0, 1.0 - allocated_weight)
        if residual_weight <= 0:
            continue

        if normalized_sector_weights:
            for sector, weight in normalized_sector_weights.items():
                risk_bucket_values[f"sector::{item.symbol}::{sector}"] += (
                    value * residual_weight * weight
                )
        else:
            risk_bucket_values[f"other::{item.symbol}"] += value * residual_weight

    return ExposureBreakdown(
        total_value=total_value,
        vehicle_values=dict(vehicle_values),
        single_name_values=dict(single_name_values),
        risk_bucket_values=dict(risk_bucket_values),
        sector_values=dict(sector_values),
        lookthrough_covered_value=lookthrough_covered_value,
    )
