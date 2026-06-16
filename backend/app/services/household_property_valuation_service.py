"""Property valuation refresh and history service."""

from __future__ import annotations

import html
import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.logging_config import get_logger
from app.models.household_planning import (
    HouseholdPropertyValuationHistory,
    HouseholdPropertyValuationHistoryList,
    HouseholdPropertyValuationPoint,
    HouseholdPropertyValuationRefreshResult,
)
from app.services._household_finance_utils import iso, to_float

logger = get_logger(__name__)

PINELLAS_BASE_URL = "https://www.pcpao.gov"
PINELLAS_TIMEOUT_SECONDS = 20.0
PINELLAS_USER_AGENT = "portfolio-ai-property-valuation/1.0"


@dataclass(frozen=True)
class _ResolvedProperty:
    strap: str
    parcel_number: str
    site_address: str
    property_use: str


@dataclass(frozen=True)
class _PropertyFacts:
    use_code: str
    living_sqft: float | None
    living_min: float | None
    living_max: float | None
    year_built: int | None
    year_min: int | None
    year_max: int | None
    waterfront: str | None
    pool: str | None


@dataclass(frozen=True)
class _CountyValue:
    year: int
    just_market_value: float


@dataclass(frozen=True)
class _ComparableSale:
    address: str
    distance: float | None
    sale_date: str
    price: float
    living_sqft: float
    price_per_sqft: float


@dataclass(frozen=True)
class _ValuationEstimate:
    source: str
    source_label: str
    estimate_value: float
    range_low: float | None
    range_high: float | None
    confidence: float | None
    methodology: str
    metadata: dict[str, object]


def _strip_tags(value: object) -> str:
    text = re.sub(r"<[^>]+>", "", str(value))
    return html.unescape(text).replace("\xa0", " ").strip()


def _money(value: str) -> float | None:
    cleaned = re.sub(r"[^0-9.\-]", "", value)
    if cleaned in {"", "-", "."}:
        return None
    parsed = float(cleaned)
    return parsed if math.isfinite(parsed) else None


def _int_or_none(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _mmddyyyy(value: date) -> str:
    return f"{value.month:02d}/{value.day:02d}/{value.year}"


def _sale_date_key(value: str) -> date:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return date.min


def _datatable_payload(column_count: int) -> dict[str, str]:
    payload = {
        "draw": "1",
        "start": "0",
        "length": "100",
        "search[value]": "",
        "search[regex]": "false",
    }
    for index in range(column_count):
        payload[f"columns[{index}][data]"] = str(index)
        payload[f"columns[{index}][name]"] = ""
        payload[f"columns[{index}][searchable]"] = "true"
        payload[f"columns[{index}][orderable]"] = "true"
        payload[f"columns[{index}][search][value]"] = ""
        payload[f"columns[{index}][search][regex]"] = "false"
    return payload


def _address_search_candidates(address: str) -> list[str]:
    first_line = address.split(",", 1)[0].strip()
    candidates = [first_line, address.strip()]
    suffix_swaps = {
        r"\broad\b": "rd",
        r"\bdrive\b": "dr",
        r"\bstreet\b": "st",
        r"\bavenue\b": "ave",
        r"\blane\b": "ln",
        r"\bboulevard\b": "blvd",
        r"\bcourt\b": "ct",
    }
    lower = first_line.lower()
    for pattern, replacement in suffix_swaps.items():
        swapped = re.sub(pattern, replacement, lower, flags=re.IGNORECASE)
        if swapped != lower:
            candidates.append(swapped)
    tokens = first_line.split()
    if len(tokens) >= 3:
        candidates.append(" ".join(tokens[:3]))

    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _source_label(source: str) -> str:
    return {
        "pinellas_county_comps": "Pinellas County comps",
        "pinellas_county_just_market": "Pinellas County just/market value",
    }.get(source, source.replace("_", " ").title())


def _valuation_from_row(row: tuple[Any, ...]) -> HouseholdPropertyValuationPoint:
    metadata = row[11]
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return HouseholdPropertyValuationPoint(
        id=str(row[0]),
        housing_cost_id=str(row[1]),
        source=str(row[2]),
        source_label=str(row[3]),
        estimate_value=to_float(row[4]) or 0.0,
        range_low=to_float(row[5]),
        range_high=to_float(row[6]),
        confidence=to_float(row[7]),
        as_of=iso(row[8])[:10],
        fetched_at=iso(row[9]),
        methodology=str(row[10]) if row[10] is not None else None,
        source_url=str(row[12]) if row[12] is not None else None,
        metadata=metadata,
    )


class HouseholdPropertyValuationService:
    """Refresh property values from official county data and store trend history."""

    def list_histories(
        self,
        service: Any,
        *,
        housing_cost_id: str | None = None,
        limit: int = 36,
    ) -> HouseholdPropertyValuationHistoryList:
        histories: dict[str, list[HouseholdPropertyValuationPoint]] = {}
        with service.storage.connection() as conn:
            params: list[object] = [limit]
            where = ""
            if housing_cost_id:
                where = "WHERE housing_cost_id = %s"
                params = [housing_cost_id, limit]
            rows = conn.execute(
                f"""
                SELECT id, housing_cost_id, source, source_label, estimate_value,
                       range_low, range_high, confidence, as_of, fetched_at,
                       methodology, metadata, source_url
                FROM (
                    SELECT *,
                           row_number() OVER (
                               PARTITION BY housing_cost_id ORDER BY fetched_at DESC, as_of DESC
                           ) AS rn
                    FROM household_property_valuations
                    {where}
                ) ranked
                WHERE rn <= %s
                ORDER BY housing_cost_id, fetched_at ASC, as_of ASC
                """,
                params,
            ).fetchall()
        for row in rows:
            point = _valuation_from_row(row)
            histories.setdefault(point.housing_cost_id, []).append(point)
        return HouseholdPropertyValuationHistoryList(
            items=[
                HouseholdPropertyValuationHistory(
                    housing_cost_id=key,
                    latest=points[-1] if points else None,
                    points=points,
                )
                for key, points in histories.items()
            ]
        )

    def refresh(
        self,
        service: Any,
        *,
        housing_cost_id: str,
        address: str | None = None,
    ) -> HouseholdPropertyValuationRefreshResult:
        row = self._housing_row(service, housing_cost_id)
        if row is None:
            raise LookupError(f"Property row not found: {housing_cost_id}")
        lookup_address = (address or row["property_address"] or row["label"] or "").strip()
        if not lookup_address:
            raise ValueError("Add a property address before refreshing value.")

        now = datetime.now(UTC)
        valuation = self._fetch_pinellas_valuation(lookup_address, now=now)
        point = self._store_valuation(
            service,
            housing_cost_id=housing_cost_id,
            address=lookup_address,
            valuation=valuation,
            now=now,
        )
        history = self.list_histories(
            service,
            housing_cost_id=housing_cost_id,
            limit=36,
        ).items
        return HouseholdPropertyValuationRefreshResult(
            valuation=point,
            history=history[0]
            if history
            else HouseholdPropertyValuationHistory(
                housing_cost_id=housing_cost_id,
                latest=point,
                points=[point],
            ),
        )

    def refresh_due(self, service: Any, *, max_age_days: int = 30) -> dict[str, object]:
        cutoff = date.today() - timedelta(days=max_age_days)
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM household_housing_costs
                WHERE COALESCE(property_address, '') <> ''
                  AND (value_as_of IS NULL OR value_as_of < %s)
                ORDER BY updated_at ASC
                """,
                [cutoff],
            ).fetchall()
        refreshed = 0
        errors: list[dict[str, str]] = []
        for (housing_cost_id,) in rows:
            try:
                self.refresh(service, housing_cost_id=str(housing_cost_id))
                refreshed += 1
            except Exception as exc:
                logger.warning(
                    "property_valuation_refresh_failed",
                    housing_cost_id=str(housing_cost_id),
                    error=str(exc),
                )
                errors.append({"housing_cost_id": str(housing_cost_id), "error": str(exc)})
        return {"status": "ok", "refreshed": refreshed, "error_count": len(errors), "errors": errors}

    def _housing_row(self, service: Any, housing_cost_id: str) -> dict[str, str | None] | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, label, property_address
                FROM household_housing_costs
                WHERE id = %s
                """,
                [housing_cost_id],
            ).fetchone()
        if row is None:
            return None
        return {"id": str(row[0]), "label": str(row[1]), "property_address": row[2]}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=PINELLAS_BASE_URL,
            timeout=PINELLAS_TIMEOUT_SECONDS,
            headers={
                "User-Agent": PINELLAS_USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{PINELLAS_BASE_URL}/quick-search",
            },
        )

    def _fetch_pinellas_valuation(
        self,
        address: str,
        *,
        now: datetime,
    ) -> _ValuationEstimate:
        with self._client() as client:
            resolved = self._resolve_pinellas_property(client, address)
            facts = self._fetch_property_facts(client, resolved.strap)
            county_value = self._fetch_county_value(client, resolved.strap)
            sales = self._fetch_comparable_sales(client, resolved, facts, now=now)
        return self._estimate_from_data(
            resolved=resolved,
            facts=facts,
            county_value=county_value,
            sales=sales,
        )

    def _resolve_pinellas_property(
        self,
        client: httpx.Client,
        address: str,
    ) -> _ResolvedProperty:
        for candidate in _address_search_candidates(address):
            payload = _datatable_payload(11)
            payload.update(
                {
                    "length": "10",
                    "input": candidate,
                    "searchsort": "address",
                    "url": PINELLAS_BASE_URL,
                    "order[0][column]": "2",
                    "order[0][dir]": "asc",
                }
            )
            response = client.post("/dal/quicksearch/searchProperty", data=payload)
            response.raise_for_status()
            data = response.json()
            rows = data.get("data") if isinstance(data, dict) else None
            if not isinstance(rows, list) or not rows:
                continue
            row = rows[0]
            if not isinstance(row, list) or len(row) < 8:
                continue
            strap_match = re.search(r'id="select_strap_\d+"\s+value="([^"]+)"', str(row[0]))
            if strap_match is None:
                value_matches = re.findall(r'value="([^"]+)"', str(row[0]))
                strap = value_matches[-1] if value_matches else ""
            else:
                strap = strap_match.group(1)
            if not strap:
                continue
            return _ResolvedProperty(
                strap=strap,
                parcel_number=_strip_tags(row[4]),
                site_address=_strip_tags(row[5]),
                property_use=_strip_tags(row[7]),
            )
        raise ValueError("No Pinellas County property match found for that address.")

    def _fetch_property_facts(self, client: httpx.Client, strap: str) -> _PropertyFacts:
        response = client.post("/dal/comsearchapi/getPropertyByStrap", data={"strap": strap})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise ValueError("Pinellas property facts were not available.")
        data = payload[0]
        if not isinstance(data, dict):
            raise ValueError("Pinellas property facts were malformed.")
        return _PropertyFacts(
            use_code=str(data.get("USE_CD") or ""),
            living_sqft=_float_or_none(data.get("TOTAL_LIVING_SQFT")),
            living_min=_float_or_none(data.get("TOTAL_LIVING_SQFT_MIN")),
            living_max=_float_or_none(data.get("TOTAL_LIVING_SQFT_MAX")),
            year_built=_int_or_none(data.get("YEAR_BUILT")),
            year_min=_int_or_none(data.get("YEAR_BUILT_MIN")),
            year_max=_int_or_none(data.get("YEAR_BUILT_MAX")),
            waterfront=str(data.get("WATERFRONT") or "") or None,
            pool=str(data.get("POOL_YN") or "") or None,
        )

    def _fetch_county_value(
        self,
        client: httpx.Client,
        strap: str,
    ) -> _CountyValue | None:
        response = client.get(f"/property-details?s={strap}")
        response.raise_for_status()
        table_match = re.search(
            r'id="tblLastYearValue".*?<tbody>(.*?)</tbody>',
            response.text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            return None
        row_match = re.search(
            r"<tr>\s*<td>(\d{4})</td>\s*<td>(\$[^<]+)</td>",
            table_match.group(1),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not row_match:
            return None
        value = _money(row_match.group(2))
        if value is None:
            return None
        return _CountyValue(year=int(row_match.group(1)), just_market_value=value)

    def _fetch_comparable_sales(
        self,
        client: httpx.Client,
        resolved: _ResolvedProperty,
        facts: _PropertyFacts,
        *,
        now: datetime,
    ) -> list[_ComparableSale]:
        searches = [
            {"radius": "1.0", "pool": facts.pool or "", "waterfront": facts.waterfront or ""},
            {"radius": "1.0", "pool": "", "waterfront": ""},
            {"radius": "2.0", "pool": "", "waterfront": ""},
        ]
        for search in searches:
            rows = self._fetch_comparable_sales_once(
                client,
                resolved,
                facts,
                now=now,
                radius=search["radius"],
                pool=search["pool"],
                waterfront=search["waterfront"],
            )
            if len(rows) >= 5:
                return rows
        return rows

    def _fetch_comparable_sales_once(
        self,
        client: httpx.Client,
        resolved: _ResolvedProperty,
        facts: _PropertyFacts,
        *,
        now: datetime,
        radius: str,
        pool: str,
        waterfront: str,
    ) -> list[_ComparableSale]:
        start = now.date() - timedelta(days=366)
        payload = _datatable_payload(18)
        payload.update(
            {
                "custom_search": "0",
                "address": resolved.site_address,
                "a": resolved.strap,
                "pu": facts.use_code,
                "st": "Q",
                "sdf": _mmddyyyy(start),
                "sdt": _mmddyyyy(now.date()),
                "lf": str(int(facts.living_min or 0)) if facts.living_min else "",
                "lt": str(int(facts.living_max or 0)) if facts.living_max else "",
                "yf": str(facts.year_min or ""),
                "yt": str(facts.year_max or ""),
                "p": pool,
                "wf": waterfront,
                "z": "",
                "sp": "",
                "cn": "",
                "sr": radius,
                "order[0][column]": "2",
                "order[0][dir]": "asc",
            }
        )
        response = client.post("/dal/comsearchapi/postSalesSearch", data=payload)
        response.raise_for_status()
        data = response.json()
        raw_rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(raw_rows, list):
            return []
        return [_sale for raw in raw_rows if (_sale := self._parse_sale_row(raw)) is not None]

    def _parse_sale_row(self, row: object) -> _ComparableSale | None:
        if not isinstance(row, list) or len(row) < 9:
            return None
        values = [_strip_tags(value) for value in row]
        if values[1] == "Subject Property":
            return None
        price = _money(values[5])
        living_sqft = _float_or_none(values[7])
        price_per_sqft = _money(values[8])
        if (
            price is None
            or living_sqft is None
            or price_per_sqft is None
            or price <= 1000
            or living_sqft <= 0
            or price_per_sqft <= 0
        ):
            return None
        return _ComparableSale(
            address=values[1],
            distance=_float_or_none(values[2]),
            sale_date=values[4],
            price=price,
            living_sqft=living_sqft,
            price_per_sqft=price_per_sqft,
        )

    def _estimate_from_data(
        self,
        *,
        resolved: _ResolvedProperty,
        facts: _PropertyFacts,
        county_value: _CountyValue | None,
        sales: list[_ComparableSale],
    ) -> _ValuationEstimate:
        metadata: dict[str, object] = {
            "provider": "Pinellas County Property Appraiser",
            "parcelNumber": resolved.parcel_number,
            "strap": resolved.strap,
            "siteAddress": resolved.site_address,
            "propertyUse": resolved.property_use,
            "livingSqft": facts.living_sqft,
            "yearBuilt": facts.year_built,
        }
        if county_value is not None:
            metadata["countyJustMarketYear"] = county_value.year
            metadata["countyJustMarketValue"] = county_value.just_market_value
        if sales and facts.living_sqft:
            estimate = self._estimate_from_sales(facts.living_sqft, sales)
            metadata["comparableSaleCount"] = len(sales)
            metadata["latestComparableSaleDate"] = max(
                sales,
                key=lambda sale: _sale_date_key(sale.sale_date),
            ).sale_date
            metadata["comparableSales"] = [
                {
                    "address": sale.address,
                    "distance": sale.distance,
                    "saleDate": sale.sale_date,
                    "price": sale.price,
                    "livingSqft": sale.living_sqft,
                    "pricePerSqft": sale.price_per_sqft,
                }
                for sale in sales[:20]
            ]
            return _ValuationEstimate(
                source=estimate.source,
                source_label=estimate.source_label,
                estimate_value=estimate.estimate_value,
                range_low=estimate.range_low,
                range_high=estimate.range_high,
                confidence=estimate.confidence,
                methodology=estimate.methodology,
                metadata=metadata,
            )
        if county_value is None:
            raise ValueError("Pinellas value refresh found no usable county value or comps.")
        metadata["comparableSaleCount"] = 0
        return _ValuationEstimate(
            source="pinellas_county_just_market",
            source_label=_source_label("pinellas_county_just_market"),
            estimate_value=county_value.just_market_value,
            range_low=None,
            range_high=None,
            confidence=0.55,
            methodology=(
                f"Latest {county_value.year} county just/market value. This is a tax-assessment "
                "baseline, not an appraisal."
            ),
            metadata=metadata,
        )

    def _estimate_from_sales(
        self,
        living_sqft: float,
        sales: list[_ComparableSale],
    ) -> _ValuationEstimate:
        prices_per_sqft = [sale.price_per_sqft for sale in sales]
        median_psf = _percentile(prices_per_sqft, 0.5)
        low_psf = _percentile(prices_per_sqft, 0.25)
        high_psf = _percentile(prices_per_sqft, 0.75)
        dispersion = (high_psf - low_psf) / median_psf if median_psf else 1
        confidence = max(0.45, min(0.9, 0.5 + min(len(sales), 20) * 0.02 - dispersion * 0.1))
        return _ValuationEstimate(
            source="pinellas_county_comps",
            source_label=_source_label("pinellas_county_comps"),
            estimate_value=round(median_psf * living_sqft, 2),
            range_low=round(low_psf * living_sqft, 2),
            range_high=round(high_psf * living_sqft, 2),
            confidence=round(confidence, 4),
            methodology=(
                "Median qualified comparable-sale price per square foot from Pinellas County "
                "Property Appraiser, adjusted to the subject living area."
            ),
            metadata={},
        )

    def _store_valuation(
        self,
        service: Any,
        *,
        housing_cost_id: str,
        address: str,
        valuation: _ValuationEstimate,
        now: datetime,
    ) -> HouseholdPropertyValuationPoint:
        valuation_id = str(uuid.uuid4())
        as_of = now.date()
        source_url = f"{PINELLAS_BASE_URL}/property-details?s={valuation.metadata.get('strap', '')}"
        metadata_json = json.dumps(valuation.metadata)
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO household_property_valuations (
                    id, housing_cost_id, source, source_label, estimate_value,
                    range_low, range_high, confidence, as_of, fetched_at,
                    methodology, source_url, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (housing_cost_id, source, as_of)
                DO UPDATE SET
                    source_label = EXCLUDED.source_label,
                    estimate_value = EXCLUDED.estimate_value,
                    range_low = EXCLUDED.range_low,
                    range_high = EXCLUDED.range_high,
                    confidence = EXCLUDED.confidence,
                    fetched_at = EXCLUDED.fetched_at,
                    methodology = EXCLUDED.methodology,
                    source_url = EXCLUDED.source_url,
                    metadata = EXCLUDED.metadata
                RETURNING id, housing_cost_id, source, source_label, estimate_value,
                          range_low, range_high, confidence, as_of, fetched_at,
                          methodology, metadata, source_url
                """,
                [
                    valuation_id,
                    housing_cost_id,
                    valuation.source,
                    valuation.source_label,
                    valuation.estimate_value,
                    valuation.range_low,
                    valuation.range_high,
                    valuation.confidence,
                    as_of,
                    now,
                    valuation.methodology,
                    source_url,
                    metadata_json,
                ],
            ).fetchone()
            conn.execute(
                """
                UPDATE household_housing_costs
                SET property_address = COALESCE(NULLIF(property_address, ''), %s),
                    property_value = %s,
                    value_as_of = %s,
                    valuation_source = %s,
                    valuation_confidence = %s,
                    valuation_range_low = %s,
                    valuation_range_high = %s,
                    provenance = 'pinellas_property_appraiser',
                    evidence_note = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    address,
                    valuation.estimate_value,
                    as_of,
                    valuation.source,
                    valuation.confidence,
                    valuation.range_low,
                    valuation.range_high,
                    valuation.methodology,
                    now.isoformat(),
                    housing_cost_id,
                ],
            )
            conn.commit()
        return _valuation_from_row(row)
