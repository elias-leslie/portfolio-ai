"""Income actuals auto-detected from the Money ledger (retirement item E).

Recurring take-home income streams (payroll deposits, benefits, marketplace
payouts) are detected from ``flow_type='income'`` rows so the retirement
planner can show its income assumptions side by side with what actually
lands in the bank. Detection is informational only — nothing here feeds the
simulation.

Coverage months come from overall ledger row counts (any flow type): income
rows are too sparse (2-6/month) for the spend service's per-month row gate,
but they ride the same statements, so a month with substantive ledger
coverage is also a month where income would have been seen.

The DB dedup (item D-a) keys on household_account_id, so the same deposit
ingested twice under two account labels ("Wells Fargo Everyday Checking"
bank-statement PDFs vs "Wells Fargo closed checking" CSV export) survives
as cross-account twins. This service collapses those at the read layer:
compatible merchant fingerprints + identical amount + dates within 3 days
+ DIFFERENT account + different source system. Real same-account multiples
(two Depop payouts of $17.27 on one day) are untouched, and one kept row
absorbs at most one twin per (account, source) so genuine multiplicity on
the other side of an alias pair still counts.

Dividend/interest rows are listed as streams but tagged ``portfolio_yield``
and excluded from the take-home total — the simulation already models
portfolio returns, so counting them as extra income would double-count.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from importlib import import_module
from itertools import pairwise
from statistics import median
from typing import Any

from pydantic import BaseModel, Field

from app.services.household_transaction_dedup_service import (
    merchant_key,
    merchants_compatible,
)
from app.services.retirement_spending_actuals_service import (
    _coverage_window,
    _group_label,
    _merchant_groups,
    _month_key,
)

# Cross-source date skew tolerated by the alias collapse — same tolerance the
# DB dedup uses for cross-source twins (statement posted-date vs CSV date).
ALIAS_MAX_DATE_SKEW_DAYS = 3

# A recurring stream is "active" when last seen within two cadence periods
# (35-day floor covers monthly cadences with statement lag) of the coverage
# window's end.
ACTIVE_GRACE_FLOOR_DAYS = 35

MANUAL_STATUS_VALUES = {
    "active",
    "stopped",
    "one_off",
    "portfolio_yield",
    "ignored",
    "merged",
}

# Streams matching these are portfolio yield, not take-home pay. Local to
# this service on purpose: the budget-side investment predicate
# (_household_spend_filters) deliberately counts dividends as income.
_PORTFOLIO_YIELD_PATTERNS = ("dividend", "interest earned", "interest paid")

_SOURCE_PRIORITY = {"plaid": 0, "statement_activity": 1, "statement_csv": 2}


class IncomeActualsStream(BaseModel):
    stream_key: str
    label: str
    owner: str | None = None
    owner_override: bool = False
    cadence: str  # weekly | biweekly | monthly | irregular | one-off
    monthly_average: float
    run_rate_monthly: float
    total: float
    transaction_count: int
    first_date: str
    last_date: str
    months_seen: int
    months_spanned: int
    active: bool
    portfolio_yield: bool = False
    status: str  # active | stopped | one_off | portfolio_yield | ignored | merged
    status_override: str | None = None
    merged_into_stream_key: str | None = None


class IncomeActuals(BaseModel):
    generated_at: str
    first_month: str | None = None
    last_month: str | None = None
    coverage_months: int = 0
    # Window-wide average of every income row (incl. ended streams + yield).
    total_monthly_income: float = 0.0
    # Sum of active, non-portfolio-yield streams' run-rates: the number to
    # compare against plan salary/contribution assumptions.
    active_monthly_income: float = 0.0
    source_label: str
    streams: list[IncomeActualsStream] = Field(default_factory=list)
    alias_rows_collapsed: int = 0


def _source_rank(row: dict[str, Any]) -> int:
    return _SOURCE_PRIORITY.get(str(row.get("source_system") or ""), 9)


def _collapse_alias_twins(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Drop cross-account statement-alias twins of the same deposit."""
    ordered = sorted(rows, key=lambda r: (r["date"], _source_rank(r)))
    kept: list[dict[str, Any]] = []
    absorbed: dict[int, set[tuple[str, str]]] = {}
    collapsed = 0
    for row in ordered:
        twin_of: dict[str, Any] | None = None
        for candidate in kept:
            if candidate["account_id"] == row["account_id"]:
                continue
            if candidate["source_system"] == row["source_system"]:
                continue
            if abs(float(candidate["amount"]) - float(row["amount"])) >= 0.005:
                continue
            if abs((candidate["date"] - row["date"]).days) > ALIAS_MAX_DATE_SKEW_DAYS:
                continue
            if not merchants_compatible(candidate["_merchant_key"], row["_merchant_key"]):
                continue
            origin = (str(row["account_id"]), str(row["source_system"]))
            if origin in absorbed.setdefault(id(candidate), set()):
                continue  # second row from the same origin = real multiplicity
            twin_of = candidate
            break
        if twin_of is not None:
            absorbed[id(twin_of)].add((str(row["account_id"]), str(row["source_system"])))
            collapsed += 1
            continue
        kept.append(row)
    return kept, collapsed


def _detect_owner(rows: list[dict[str, Any]], owner_names: list[str]) -> str | None:
    text = " ".join(str(row.get("merchant") or "") for row in rows).lower()
    for name in owner_names:
        cleaned = name.strip().lower()
        if cleaned and re.search(rf"\b{re.escape(cleaned)}\b", text):
            return name.strip()
    return None


def _stream_key(rows: list[dict[str, Any]]) -> str:
    keys = sorted(
        {
            str(row.get("_merchant_key") or "").strip()
            or merchant_key(
                {
                    "raw_merchant": str(
                        row.get("merchant") or row.get("description") or ""
                    )
                }
            )
            for row in rows
        }
    )
    identity = "|".join(key for key in keys if key) or _display_label(_group_label(rows))
    return sha256(identity.encode("utf-8")).hexdigest()[:16]


def _cadence(dates: list[date]) -> str:
    distinct = sorted(set(dates))
    if len(distinct) < 2:
        return "one-off"
    gaps = [(b - a).days for a, b in pairwise(distinct)]
    typical = median(gaps)
    if typical <= 9:
        return "weekly"
    if typical <= 18:
        return "biweekly"
    if typical <= 45:
        return "monthly"
    return "irregular"


def _median_gap_days(dates: list[date]) -> float | None:
    distinct = sorted(set(dates))
    if len(distinct) < 2:
        return None
    return float(median((b - a).days for a, b in pairwise(distinct)))


def _months_spanned(first: str, last: str) -> int:
    years = int(last[:4]) - int(first[:4])
    return years * 12 + int(last[5:7]) - int(first[5:7]) + 1


def _is_portfolio_yield(label: str) -> bool:
    lowered = label.lower()
    return any(pattern in lowered for pattern in _PORTFOLIO_YIELD_PATTERNS)


def _auto_status(cadence: str, *, active: bool, portfolio_yield: bool) -> str:
    if portfolio_yield:
        return "portfolio_yield"
    if cadence == "one-off":
        return "one_off"
    return "active" if active else "stopped"


def _effective_active(auto_active: bool, status_override: str | None) -> bool:
    if status_override == "active":
        return True
    if status_override in {"stopped", "one_off", "ignored", "merged"}:
        return False
    return auto_active


def _effective_portfolio_yield(
    auto_portfolio_yield: bool, status_override: str | None
) -> bool:
    if status_override == "portfolio_yield":
        return True
    if status_override is not None:
        return False
    return auto_portfolio_yield


def _normalize_manual_status(value: Any) -> str | None:
    if value is None:
        return None
    status = str(value).strip()
    if status in {"", "auto"}:
        return None
    if status not in MANUAL_STATUS_VALUES:
        raise ValueError(f"Unsupported income stream status: {status}")
    return status


def _normalized_owner_name(value: Any) -> str | None:
    if value is None:
        return None
    owner = str(value).strip()
    return owner or None


def _run_rate_monthly(
    *, total: float, transaction_count: int, cadence: str, monthly_average: float
) -> float:
    if transaction_count <= 0:
        return 0.0
    average_deposit = total / transaction_count
    if cadence == "weekly":
        return round(average_deposit * 52 / 12, 2)
    if cadence == "biweekly":
        return round(average_deposit * 26 / 12, 2)
    if cadence == "monthly":
        return round(average_deposit, 2)
    return round(monthly_average, 2)


_MASK_TOKEN_RE = re.compile(r"^[Xx]+\d*$")


def _display_label(raw: str) -> str:
    """Strip statement noise (date/reference digits, masks, pipe tails)."""
    head = raw.split("|", 1)[0]
    tokens = []
    for token in head.split():
        if _MASK_TOKEN_RE.match(token):
            continue
        digits = sum(ch.isdigit() for ch in token)
        if len(token) >= 4 and digits >= len(token) / 2:
            continue
        tokens.append(token)
    cleaned = " ".join(tokens).strip()
    return cleaned or raw.strip()


def derive_income_actuals(
    income_rows: list[dict[str, Any]],
    *,
    coverage_dates: list[date],
    today: date,
    owner_names: list[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> IncomeActuals:
    generated_at = datetime.now(UTC).isoformat()
    window = _coverage_window([{"date": d} for d in coverage_dates], today=today)
    if not window:
        return IncomeActuals(
            generated_at=generated_at,
            source_label="No complete months of Money transaction coverage yet.",
        )

    window_set = set(window)
    rows = [row for row in income_rows if _month_key(row["date"]) in window_set]
    for row in rows:
        row["_merchant_key"] = merchant_key(
            {"raw_merchant": str(row.get("merchant") or row.get("description") or "")}
        )
    rows, collapsed = _collapse_alias_twins(rows)

    coverage_months = len(window)
    first_month, last_month = window[0], window[-1]
    last_day = date(int(last_month[:4]), int(last_month[5:7]), 28) + timedelta(days=4)
    window_end = last_day - timedelta(days=last_day.day)  # last day of last_month

    stream_overrides = overrides or {}
    streams: list[IncomeActualsStream] = []
    for group in _merchant_groups(rows):
        dates = sorted(row["date"] for row in group)
        total = sum(float(row["amount"]) for row in group)
        first_seen, last_seen = _month_key(dates[0]), _month_key(dates[-1])
        spanned = _months_spanned(first_seen, last_seen)
        cadence = _cadence(dates)
        gap = _median_gap_days(dates)
        grace = max(2 * gap, ACTIVE_GRACE_FLOOR_DAYS) if gap is not None else 0
        active = cadence != "one-off" and (window_end - dates[-1]).days <= grace
        label = _display_label(_group_label(group))
        stream_key = _stream_key(group)
        override = stream_overrides.get(stream_key) or {}
        status_override = _normalize_manual_status(override.get("status"))
        portfolio_yield = _effective_portfolio_yield(
            _is_portfolio_yield(label), status_override
        )
        effective_active = _effective_active(active, status_override)
        status = status_override or _auto_status(
            cadence, active=active, portfolio_yield=portfolio_yield
        )
        owner_override = _normalized_owner_name(override.get("owner_name"))
        detected_owner = _detect_owner(group, owner_names or [])
        monthly_average = round(total / spanned, 2)
        run_rate_monthly = _run_rate_monthly(
            total=total,
            transaction_count=len(group),
            cadence=cadence,
            monthly_average=monthly_average,
        )
        streams.append(
            IncomeActualsStream(
                stream_key=stream_key,
                label=label,
                owner=owner_override or detected_owner,
                owner_override=owner_override is not None,
                cadence=cadence,
                monthly_average=monthly_average,
                run_rate_monthly=run_rate_monthly,
                total=round(total, 2),
                transaction_count=len(group),
                first_date=dates[0].isoformat(),
                last_date=dates[-1].isoformat(),
                months_seen=len({_month_key(d) for d in dates}),
                months_spanned=spanned,
                active=effective_active,
                portfolio_yield=portfolio_yield,
                status=status,
                status_override=status_override,
                merged_into_stream_key=(
                    str(override.get("merged_into_stream_key") or "").strip()
                    if status == "merged"
                    else None
                )
                or None,
            )
        )
    streams.sort(key=lambda s: s.run_rate_monthly, reverse=True)

    total_income = sum(float(row["amount"]) for row in rows)
    active_income = sum(s.run_rate_monthly for s in streams if s.status == "active")
    return IncomeActuals(
        generated_at=generated_at,
        first_month=first_month,
        last_month=last_month,
        coverage_months=coverage_months,
        total_monthly_income=round(total_income / coverage_months, 2),
        active_monthly_income=round(active_income, 2),
        source_label=(
            f"Detected from Money income transactions, {first_month} to {last_month} "
            f"({coverage_months} complete months). Amounts are take-home deposits."
        ),
        streams=streams,
        alias_rows_collapsed=collapsed,
    )


class RetirementIncomeActualsService:
    """Fetch ledger income rows and derive income streams/run-rates."""

    def __init__(self) -> None:
        storage_mod = import_module("app.storage")
        self.storage = storage_mod.get_storage()

    def build(self) -> IncomeActuals:
        with self.storage.connection() as conn:
            income_rows = conn.execute(
                """
                SELECT t.transaction_date,
                       COALESCE(t.raw_merchant, t.description) AS merchant,
                       t.description,
                       t.amount,
                       t.household_account_id,
                       t.source_system
                FROM household_transactions t
                WHERE t.flow_type = 'income'
                  AND t.removed IS NOT TRUE
                ORDER BY t.transaction_date ASC
                """
            ).fetchall()
            coverage_rows = conn.execute(
                """
                SELECT t.transaction_date
                FROM household_transactions t
                WHERE t.removed IS NOT TRUE
                """
            ).fetchall()
            member_rows = conn.execute(
                "SELECT display_name FROM household_members ORDER BY created_at ASC"
            ).fetchall()
            override_rows = conn.execute(
                """
                SELECT stream_key,
                       owner_name,
                       status,
                       merged_into_stream_key
                FROM retirement_income_stream_overrides
                """
            ).fetchall()

        rows = [
            {
                "date": row[0].date() if isinstance(row[0], datetime) else row[0],
                "merchant": row[1],
                "description": row[2],
                "amount": float(row[3]),
                "account_id": str(row[4]) if row[4] is not None else "",
                "source_system": str(row[5] or ""),
            }
            for row in income_rows
            if row[0] is not None and row[3] is not None
        ]
        coverage_dates = [
            row[0].date() if isinstance(row[0], datetime) else row[0]
            for row in coverage_rows
            if row[0] is not None
        ]
        owner_names = [str(row[0]) for row in member_rows if row[0]]
        overrides = {
            str(row[0]): {
                "owner_name": row[1],
                "status": row[2],
                "merged_into_stream_key": row[3],
            }
            for row in override_rows
            if row[0]
        }
        return derive_income_actuals(
            rows,
            coverage_dates=coverage_dates,
            today=date.today(),
            owner_names=owner_names,
            overrides=overrides,
        )

    def update_override(self, stream_key: str, payload: Any) -> IncomeActuals:
        cleaned_key = stream_key.strip()
        if not cleaned_key:
            raise ValueError("Income stream key is required.")
        owner_name = _normalized_owner_name(getattr(payload, "owner_name", None))
        status = _normalize_manual_status(getattr(payload, "status", None))
        merged_into_stream_key = (
            str(getattr(payload, "merged_into_stream_key", None) or "").strip()
            if status == "merged"
            else None
        )
        if status == "merged" and not merged_into_stream_key:
            raise ValueError("Merged streams need a target stream.")
        label = str(getattr(payload, "label", "") or "").strip()[:255] or None

        with self.storage.connection() as conn:
            now = datetime.now(UTC)
            if owner_name is None and status is None:
                conn.execute(
                    "DELETE FROM retirement_income_stream_overrides WHERE stream_key = %s",
                    [cleaned_key],
                )
            else:
                conn.execute(
                    """
                    INSERT INTO retirement_income_stream_overrides (
                        stream_key,
                        label,
                        owner_name,
                        status,
                        merged_into_stream_key,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stream_key) DO UPDATE
                    SET label = EXCLUDED.label,
                        owner_name = EXCLUDED.owner_name,
                        status = EXCLUDED.status,
                        merged_into_stream_key = EXCLUDED.merged_into_stream_key,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        cleaned_key,
                        label,
                        owner_name,
                        status,
                        merged_into_stream_key,
                        now,
                        now,
                    ],
                )
            conn.commit()
        return self.build()
