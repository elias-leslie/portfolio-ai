"""Shared retirement-plan assumptions, tax rules, and input normalization."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from app.portfolio.contracts.retirement import (
    RetirementAccountBucket,
    RetirementAccountRule,
    RetirementDrawdownYear,
    RetirementIncomeSource,
    RetirementInputs,
    WithdrawalBridgeConfig,
    WithdrawalConfig,
    WithdrawalHealthcarePoint,
    WithdrawalPhaseConfig,
)
from app.services._aca_estimator import ACAPerson, ACAYearPlan, build_aca_year_plans
from app.services._withdrawal_engine import BridgeConfig as EngineBridgeConfig
from app.services._withdrawal_engine import HealthcarePoint as EngineHealthcarePoint
from app.services._withdrawal_engine import PhaseConfig as EnginePhaseConfig
from app.services._withdrawal_engine import SpendingReduction as EngineSpendingReduction
from app.services._withdrawal_engine import WithdrawalConfig as EngineWithdrawalConfig
from app.services._withdrawal_engine import healthcare_ltc

DEFAULT_TRIALS = 10_000
MAX_TRIALS = 50_000
DEFAULT_HORIZON_YEARS = 30
DEFAULT_RETIREMENT_AGE = 65
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
CMA_PATH = Path(__file__).parent / "retirement_cma.yaml"
DEFAULT_PREVIEW_TRIALS = 2_500
RMD_START_AGE = 73
# 10% additional tax on pre-tax withdrawals before 59½ (limited exceptions).
EARLY_WITHDRAWAL_PENALTY_AGE = 59.5
# IRS Uniform Lifetime Table (effective 2022) — distribution-period divisors
# by age. RMDs begin at 73; 72 is kept for completeness, and ages past 120 use
# the 120+ divisor.
IRS_UNIFORM_LIFETIME_DIVISORS: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6, 106: 4.3,
    107: 4.1, 108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1,
    114: 3.0, 115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3, 120: 2.0,
}
# HSA draws are modeled as non-medical (taxed as ordinary income, 20%
# penalty before 65) since the engine can't earmark medical spending — so
# the HSA is the costliest bucket to tap and drains after Roth.
DEFAULT_DRAWDOWN_ORDER = (
    "cash",
    "taxable",
    "governmental_457b",
    "pre_tax",
    "roth",
    "hsa",
    "other",
)
BUCKET_WITHDRAWAL_PRIORITY = {
    bucket: index + 1 for index, bucket in enumerate(DEFAULT_DRAWDOWN_ORDER)
}
BUCKET_LABELS = {
    "cash": "Cash bridge",
    "taxable": "Taxable brokerage",
    "governmental_457b": "Governmental 457(b)",
    "pre_tax": "Traditional retirement",
    "roth": "Roth IRA",
    "hsa": "HSA",
    "other": "Other assets",
}
BUCKET_TAX_TREATMENTS = {
    "cash": "already_taxed",
    "taxable": "taxable_capital_gains_estimate",
    "governmental_457b": "ordinary_income_no_10pct_early_penalty",
    "pre_tax": "ordinary_income",
    "roth": "tax_free_if_qualified",
    "hsa": "tax_free_for_qualified_medical",
    "other": "planning_estimate",
}
STRATEGY_BUCKET_LABELS = {
    "now": "Now / liquidity",
    "soon": "Soon / stability",
    "later": "Later / growth",
}
STRATEGY_BUCKET_HORIZONS = {
    "now": "Retirement year 1",
    "soon": "Retirement years 2-6",
    "later": "Years 7+",
}
STRATEGY_BUCKET_PURPOSES = {
    "now": "Cash and cash equivalents for the first year of portfolio withdrawals.",
    "soon": "High-quality bond exposure for the next five years of portfolio withdrawals.",
    "later": "Stock, real-estate, and other growth exposure for long-horizon spending.",
}
TAXABLE_WITHDRAWAL_GAIN_RATIO = 0.15
FEDERAL_TAX_YEAR = 2026
# Plain-language audit of how each bucket is modeled, keyed by bucket type.
# Kept terse on purpose: one early-access line and one RMD line each, sourced
# from the constants above — no advice, just what the simulation assumes.
BUCKET_RULE_EXPLANATIONS: dict[str, dict[str, str]] = {
    "cash": {
        "early_access": "Already-taxed cash; no withdrawal penalty.",
        "rmd": "Not subject to RMDs.",
    },
    "taxable": {
        "early_access": "No early-withdrawal penalty; only realized gains are taxed, at long-term rates.",
        "rmd": "Not subject to RMDs.",
    },
    "governmental_457b": {
        "early_access": "Penalty-free at any age after you separate from service; taxed as ordinary income.",
        "rmd": "Required minimum distributions begin at 73.",
    },
    "pre_tax": {
        "early_access": "10% penalty on withdrawals before 59½ (limited exceptions); taxed as ordinary income.",
        "rmd": "Required minimum distributions begin at 73.",
    },
    "roth": {
        "early_access": "Contributions withdrawable anytime; earnings tax-free after 59½ and the 5-year rule.",
        "rmd": "Roth IRAs have no lifetime RMDs for the original owner.",
    },
    "hsa": {
        "early_access": (
            "Tax-free for qualified medical costs; 20% penalty plus tax on non-medical use "
            "before 65. Modeled conservatively as non-medical: ordinary income tax, plus the "
            "penalty before 65."
        ),
        "rmd": "Not subject to RMDs; after 65 non-medical withdrawals are taxed as ordinary income.",
    },
    "other": {
        "early_access": "Modeled with planning-grade assumptions; confirm the specific account's rules.",
        "rmd": "RMD treatment depends on the underlying account type.",
    },
}
BUCKET_TAX_TREATMENT_LABELS: dict[str, str] = {
    "already_taxed": "Already taxed",
    "taxable_capital_gains_estimate": "Long-term capital gains on realized gains",
    "ordinary_income_no_10pct_early_penalty": "Ordinary income, no early-withdrawal penalty",
    "ordinary_income": "Ordinary income",
    "tax_free_if_qualified": "Tax-free if qualified",
    "tax_free_for_qualified_medical": "Tax-free for qualified medical",
    "planning_estimate": "Planning estimate",
}
SSA_2026_TAXABLE_WAGE_BASE = 184_500.0
SSA_2026_FIRST_BEND_POINT = 1_286.0
SSA_2026_SECOND_BEND_POINT = 7_749.0
SSA_FULL_RETIREMENT_AGE = 67
SSA_ASSUMED_CAREER_START_AGE = 22
DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR = 2033
DEFAULT_SOCIAL_SECURITY_PAYABLE_RATIO = 0.77
DEFAULT_SPAXX_CASH_YIELD = 0.0328
DEFAULT_SPAXX_CASH_YIELD_AS_OF = date(2026, 5, 7)
DEFAULT_SPAXX_CASH_YIELD_SOURCE = "Fidelity SPAXX 7-day yield"
# Freshness windows (days) shared with the frontend freshnessTone palette.
YIELD_FRESH_MAX_DAYS = 14
YIELD_AGING_MAX_DAYS = 45
INCOME_YIELD_BY_ASSET_CLASS = {
    "us_equity": 0.014,
    "intl_equity": 0.025,
    "bonds": 0.04,
    "cash": DEFAULT_SPAXX_CASH_YIELD,
    "real_estate": 0.035,
    "alts": 0.0,
}
CASH_EQUIVALENT_SYMBOLS = {"SPAXX", "FDRXX", "VMFXX", "SWVXX", "BIL", "SHV", "SGOV"}
DEFAULT_HOLDING_INCOME_YIELDS = {
    "VTI": 0.0106,
    "VOO": 0.011,
    "SPY": 0.011,
    "SCHD": 0.036,
    "VYM": 0.028,
    "DGRO": 0.021,
    "HDV": 0.034,
    "JEPI": 0.075,
    "BND": 0.04,
    "AGG": 0.04,
}
FILING_STATUS_LABELS = {
    "single": "Single",
    "married_filing_jointly": "Married filing jointly",
    "married_filing_separately": "Married filing separately",
    "head_of_household": "Head of household",
}
STANDARD_DEDUCTION_2026 = {
    "single": 16_100.0,
    "married_filing_jointly": 32_200.0,
    "married_filing_separately": 16_100.0,
    "head_of_household": 24_150.0,
}
ADDITIONAL_STANDARD_DEDUCTION_65_2026 = {
    "single": 2_050.0,
    "married_filing_jointly": 1_650.0,
    "married_filing_separately": 1_650.0,
    "head_of_household": 2_050.0,
}
ORDINARY_TAX_BRACKETS_2026 = {
    "single": (
        (12_400.0, 0.10),
        (50_400.0, 0.12),
        (105_700.0, 0.22),
        (201_775.0, 0.24),
        (256_225.0, 0.32),
        (640_600.0, 0.35),
        (float("inf"), 0.37),
    ),
    "married_filing_jointly": (
        (24_800.0, 0.10),
        (100_800.0, 0.12),
        (211_400.0, 0.22),
        (403_550.0, 0.24),
        (512_450.0, 0.32),
        (768_700.0, 0.35),
        (float("inf"), 0.37),
    ),
    "married_filing_separately": (
        (12_400.0, 0.10),
        (50_400.0, 0.12),
        (105_700.0, 0.22),
        (201_775.0, 0.24),
        (256_225.0, 0.32),
        (384_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    "head_of_household": (
        (17_700.0, 0.10),
        (67_450.0, 0.12),
        (105_700.0, 0.22),
        (201_750.0, 0.24),
        (256_200.0, 0.32),
        (640_600.0, 0.35),
        (float("inf"), 0.37),
    ),
}
LONG_TERM_CAPITAL_GAINS_BRACKETS_2026 = {
    "single": (49_450.0, 545_500.0),
    "married_filing_jointly": (98_900.0, 613_700.0),
    "married_filing_separately": (49_450.0, 306_850.0),
    "head_of_household": (66_200.0, 579_600.0),
}
NIIT_THRESHOLDS_2026 = {
    "single": 200_000.0,
    "married_filing_jointly": 250_000.0,
    "married_filing_separately": 125_000.0,
    "head_of_household": 200_000.0,
}
NO_STATE_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}


@dataclass(frozen=True, slots=True)
class FederalTaxContext:
    filing_status: str
    filing_status_source: str
    state_tax_rate: float
    state_tax_source: str


@dataclass(frozen=True, slots=True)
class WithdrawalOutcome:
    withdrawals: dict[str, float]
    tax_estimate: float
    penalty_estimate: float
    rmd_amount: float
    shortfall: float


def load_cma(path: Path | None = None) -> dict[str, Any]:
    """Load the long-term return estimates YAML.

    Module-level function so the simulation engine and tests can drive
    it without a service instance.
    """
    target = path or CMA_PATH
    with target.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _yield_freshness(as_of: date | None, anchor: date) -> tuple[str, str]:
    """Map a yield's as-of date to a (status, label) the UI can colour.

    Status values match the frontend ``freshnessTone`` palette so the
    planner reuses the existing badge styling rather than inventing one.
    A missing ``as_of`` means the number is a hardcoded planning
    assumption, not observed market data.
    """
    if as_of is None:
        return "needs_evidence", "Planning assumption"
    age_days = max((anchor - as_of).days, 0)
    if age_days <= YIELD_FRESH_MAX_DAYS:
        return "fresh", f"As of {as_of:%b %-d, %Y}"
    if age_days <= YIELD_AGING_MAX_DAYS:
        return "aging", f"{age_days} days old (as of {as_of:%b %-d, %Y})"
    return "stale", f"Stale — as of {as_of:%b %-d, %Y}"


# Worst-first so the rollup reflects the least-trustworthy input.
_FRESHNESS_PRIORITY = ("stale", "needs_evidence", "aging", "fresh", "not_applicable")
_FRESHNESS_ROLLUP_LABELS = {
    "stale": "Some yields are stale",
    "needs_evidence": "Some yields use planning assumptions",
    "aging": "Some yields are aging",
    "fresh": "Yields are current",
    "not_applicable": "Yields entered by you",
}


def _aggregate_income_yield_freshness(
    holding_yields: list[dict[str, Any]],
) -> tuple[str, str]:
    """Roll per-holding yield freshness into one status for the income card."""
    statuses = {str(row.get("freshness_status") or "fresh") for row in holding_yields}
    if not statuses:
        return "needs_evidence", "Income yield uses planning assumptions"
    for status in _FRESHNESS_PRIORITY:
        if status in statuses:
            return status, _FRESHNESS_ROLLUP_LABELS[status]
    return "fresh", _FRESHNESS_ROLLUP_LABELS["fresh"]

def _split_members(
    members: list[dict[str, Any]],
    anchor: date | int | None = None,
    *,
    current_year: int | None = None,
) -> tuple[int, int | None]:
    if anchor is None:
        anchor = current_year if current_year is not None else date.today()
    current_date = date(anchor, 12, 31) if isinstance(anchor, int) else anchor
    primary_age: int | None = None
    spouse_age: int | None = None
    for row in members:
        age = _member_age(row, current_date)
        if age is None:
            continue
        role = (row.get("role") or "").strip().lower()
        relationship = (row.get("relationship") or "").strip().lower()
        if row.get("is_dependent") or role in {"child", "dependent"} or relationship in {
            "child",
            "daughter",
            "son",
            "dependent",
        }:
            continue
        if primary_age is None and (
            role in {"primary", "self", "owner"}
            or relationship in {"father", "husband", "self", "owner"}
        ):
            primary_age = age
        elif spouse_age is None and (
            role in {"spouse", "partner"}
            or relationship in {"mother", "wife", "spouse", "partner"}
        ):
            spouse_age = age
        elif primary_age is None:
            primary_age = age
    return primary_age if primary_age is not None else 50, spouse_age


def _member_age(row: dict[str, Any], anchor: date) -> int | None:
    birth_year = row.get("birth_year")
    if birth_year is None:
        return None
    birth_month, birth_day = _member_birth_month_day(row)
    age = anchor.year - int(birth_year)
    if (
        birth_month is not None
        and birth_day is not None
        and (anchor.month, anchor.day) < (birth_month, birth_day)
    ):
        age -= 1
    return max(0, age)


def _member_birth_month_day(row: dict[str, Any]) -> tuple[int | None, int | None]:
    notes = str(row.get("notes") or "")
    iso_match = re.search(
        r"\b(?:dob|birth(?:day)?)\s*:\s*\d{4}-(\d{1,2})-(\d{1,2})\b",
        notes,
        re.IGNORECASE,
    )
    if iso_match:
        return int(iso_match.group(1)), int(iso_match.group(2))
    month_match = re.search(
        r"\b(?:dob|birth(?:day)?)\s*:\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{1,2})\b",
        notes,
        re.IGNORECASE,
    )
    if not month_match:
        return None, None
    month_token = month_match.group(1).lower()[:3]
    month = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }[month_token]
    return month, int(month_match.group(2))


def _coerce_json(value: Any) -> dict[str, Any] | None:
    if value is None or isinstance(value, dict):
        return value
    raw: str | None = None
    if isinstance(value, str):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        try:
            raw = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _bucket_type(asset_group: str, account_type: str) -> str:
    normalized_type = account_type.strip().lower().replace("-", "_").replace(" ", "_")
    bucket = "other"
    if "roth" in normalized_type:
        bucket = "roth"
    elif normalized_type in {"governmental_457b", "gov_457b", "457b_governmental"}:
        bucket = "governmental_457b"
    elif normalized_type == "hsa" or "health_savings" in normalized_type:
        bucket = "hsa"
    elif asset_group == "cash":
        bucket = "cash"
    elif asset_group in {"taxable", "brokerage"}:
        bucket = "taxable"
    elif asset_group == "retirement" or normalized_type in {
        "ira",
        "401k",
        "403b",
        "457",
        "457b",
        "457_b",
        "retirement",
        "traditional_ira",
    }:
        bucket = "pre_tax"
    return bucket


def _tax_context_from_profile(profile: Any, inputs: RetirementInputs) -> FederalTaxContext:
    filing_status, filing_status_source = _filing_status_from_profile(profile, inputs.spouse_age)
    return FederalTaxContext(
        filing_status=filing_status,
        filing_status_source=filing_status_source,
        state_tax_rate=_state_tax_rate_from_profile(profile),
        state_tax_source=_state_tax_source_from_profile(profile),
    )


def _bucket_balances(
    inputs: RetirementInputs,
    buckets: tuple[RetirementAccountBucket, ...],
) -> dict[str, float]:
    balances = dict.fromkeys(DEFAULT_DRAWDOWN_ORDER, 0.0)
    for bucket in buckets:
        balances[bucket.bucket_type] = balances.get(bucket.bucket_type, 0.0) + bucket.current_value
    if sum(balances.values()) <= 0 and inputs.portfolio_value > 0:
        balances["taxable"] = inputs.portfolio_value
    return balances


def _holding_field(holding: Any, field: str) -> Any:
    if isinstance(holding, dict):
        return holding.get(field)
    return getattr(holding, field, None)


def _normalized_asset_allocation(
    allocation: dict[str, float],
    cma: dict[str, Any],
) -> dict[str, float]:
    asset_classes = cma.get("asset_classes", {})
    cleaned: dict[str, float] = {}
    for asset_class, raw_weight in allocation.items():
        key = str(asset_class or "").strip()
        if key not in asset_classes:
            continue
        weight = float(raw_weight or 0.0)
        if weight <= 0:
            continue
        cleaned[key] = cleaned.get(key, 0.0) + (weight / 100.0 if weight > 1.0 else weight)
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {asset_class: round(weight / total, 6) for asset_class, weight in cleaned.items()}


def _simulation_asset_classes(
    allocation: dict[str, float],
    bucket_return_allocations: dict[str, dict[str, float]],
    cma: dict[str, Any],
) -> list[str]:
    asset_classes = cma.get("asset_classes", {})
    wanted = set(_normalized_asset_allocation(allocation, cma))
    for bucket_allocation in bucket_return_allocations.values():
        wanted.update(_normalized_asset_allocation(bucket_allocation, cma))
    return [asset_class for asset_class in asset_classes if asset_class in wanted]


def _weights_for_classes(allocation: dict[str, float], classes: list[str]) -> np.ndarray:
    values = np.array([float(allocation.get(asset_class, 0.0) or 0.0) for asset_class in classes])
    total = float(np.sum(values))
    if total <= 0:
        return np.zeros(len(classes), dtype=np.float64)
    return values / total


def _cash_yield(value: float | None) -> float:
    if value is None:
        return DEFAULT_SPAXX_CASH_YIELD
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SPAXX_CASH_YIELD
    if parsed <= 0:
        return DEFAULT_SPAXX_CASH_YIELD
    return min(parsed / 100.0 if parsed > 1.0 else parsed, 0.2)


def _optional_yield(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return min(parsed / 100.0 if parsed > 1.0 else parsed, 1.0)


def _cma_with_cash_yield(cma: dict[str, Any], cash_yield: float | None) -> dict[str, Any]:
    rate = _cash_yield(cash_yield)
    out = dict(cma)
    asset_classes = {
        str(asset_class): dict(meta)
        for asset_class, meta in (cma.get("asset_classes") or {}).items()
        if isinstance(meta, dict)
    }
    cash_meta = dict(asset_classes.get("cash", {}))
    cash_meta["expected_return"] = rate
    asset_classes["cash"] = cash_meta
    out["asset_classes"] = asset_classes
    return out


def _allocation_with_bucket_cash(
    allocation: dict[str, float],
    buckets: tuple[RetirementAccountBucket, ...],
) -> dict[str, float]:
    total = sum(float(bucket.current_value or 0.0) for bucket in buckets)
    if total <= 0:
        return allocation
    cash_value = sum(
        float(bucket.current_value or 0.0)
        for bucket in buckets
        if bucket.bucket_type == "cash"
    )
    non_cash_value = max(0.0, total - cash_value)
    values: dict[str, float] = {}
    source_allocation = allocation or ({"us_equity": 1.0} if non_cash_value > 0 else {})
    for asset_class, weight in source_allocation.items():
        values[asset_class] = values.get(asset_class, 0.0) + float(weight or 0.0) * non_cash_value
    if cash_value > 0:
        values["cash"] = values.get("cash", 0.0) + cash_value
    normalized_total = sum(value for value in values.values() if value > 0)
    if normalized_total <= 0:
        return allocation
    return {
        asset_class: round(value / normalized_total, 6)
        for asset_class, value in values.items()
        if value > 0
    }


def _income_yield(allocation: dict[str, float], cash_yield: float | None) -> float:
    yields = {**INCOME_YIELD_BY_ASSET_CLASS, "cash": _cash_yield(cash_yield)}
    total = 0.0
    total_weight = 0.0
    for asset_class, weight in allocation.items():
        w = float(weight or 0.0)
        if w <= 0:
            continue
        total += w * float(yields.get(asset_class, 0.0))
        total_weight += w
    if total_weight <= 0:
        return 0.0
    return total / total_weight


def _income_tax_drag_estimate(
    inputs: RetirementInputs,
    *,
    income_yield: float,
    holding_yields: list[dict[str, Any]],
    tax_context: FederalTaxContext | None,
    buckets: tuple[RetirementAccountBucket, ...],
    baseline_ordinary_income: float = 0.0,
) -> dict[str, Any]:
    tax_context = tax_context or _tax_context_from_profile(None, inputs)
    total_value = sum(float(bucket.current_value or 0.0) for bucket in buckets) or inputs.portfolio_value
    if total_value <= 0 or income_yield <= 0:
        return _empty_tax_drag()
    taxable_value = sum(
        float(bucket.current_value or 0.0)
        for bucket in buckets
        if bucket.bucket_type in {"cash", "taxable"}
    )
    if not buckets:
        taxable_value = inputs.portfolio_value
    taxable_share = max(0.0, min(taxable_value / total_value, 1.0))
    if taxable_share <= 0:
        return _empty_tax_drag(taxable_asset_share=0.0)

    rows = holding_yields or _asset_class_income_yield_rows(inputs.asset_allocation, inputs.cash_yield)
    ordinary_income = 0.0
    qualified_income = 0.0
    for row in rows:
        weight = float(row.get("weight") or 0.0)
        row_yield = float(row.get("income_yield") or 0.0)
        amount = total_value * taxable_share * weight * row_yield
        if row.get("tax_category") == "qualified_dividend":
            qualified_income += amount
        else:
            ordinary_income += amount

    taxable_income = ordinary_income + qualified_income
    base_tax = _federal_tax_estimate(
        tax_context,
        ordinary_income=max(0.0, baseline_ordinary_income),
        social_security_benefits=0.0,
        long_term_capital_gains=0.0,
        primary_age=inputs.primary_age,
        spouse_age=inputs.spouse_age,
        inflation_factor=1.0,
    )
    tax_with_income = _federal_tax_estimate(
        tax_context,
        ordinary_income=max(0.0, baseline_ordinary_income) + ordinary_income,
        social_security_benefits=0.0,
        long_term_capital_gains=qualified_income,
        primary_age=inputs.primary_age,
        spouse_age=inputs.spouse_age,
        inflation_factor=1.0,
    )
    tax = max(0.0, tax_with_income - base_tax)
    return {
        "taxable_asset_share": round(taxable_share, 6),
        "estimated_taxable_income": round(taxable_income, 2),
        "estimated_ordinary_income": round(ordinary_income, 2),
        "estimated_qualified_dividends": round(qualified_income, 2),
        "estimated_income_tax_drag": round(tax, 2),
        "estimated_income_tax_drag_rate": round(tax / taxable_income, 6) if taxable_income > 0 else 0.0,
        "baseline_ordinary_income": round(max(0.0, baseline_ordinary_income), 2),
        "income_tax_drag_method": (
            "Incremental federal estimate on taxable-account interest/dividends over entered current salary; "
            "retirement withdrawals and Social Security are modeled separately."
        ),
    }


def _empty_tax_drag(taxable_asset_share: float = 0.0) -> dict[str, Any]:
    return {
        "taxable_asset_share": taxable_asset_share,
        "estimated_taxable_income": 0.0,
        "estimated_ordinary_income": 0.0,
        "estimated_qualified_dividends": 0.0,
        "estimated_income_tax_drag": 0.0,
        "estimated_income_tax_drag_rate": 0.0,
        "baseline_ordinary_income": 0.0,
        "income_tax_drag_method": "No taxable income drag estimated.",
    }


def _asset_class_income_yield_rows(
    allocation: dict[str, float],
    cash_yield: float | None,
) -> list[dict[str, Any]]:
    yields = {**INCOME_YIELD_BY_ASSET_CLASS, "cash": _cash_yield(cash_yield)}
    return [
        {
            "asset_class": asset_class,
            "weight": float(weight or 0.0),
            "income_yield": float(yields.get(asset_class, 0.0)),
            "source": "asset_class_default",
            "tax_category": _income_tax_category_for_asset_class(asset_class),
        }
        for asset_class, weight in allocation.items()
        if float(weight or 0.0) > 0
    ]


def _income_tax_category(symbol: str) -> str:
    if symbol in CASH_EQUIVALENT_SYMBOLS:
        return "ordinary_income"
    ac_mod = import_module("app.portfolio.asset_classification")
    asset_class = ac_mod.ASSET_CLASS_BY_SYMBOL.get(symbol, "us_equity")
    return _income_tax_category_for_asset_class(asset_class)


def _income_tax_category_for_asset_class(asset_class: str) -> str:
    if asset_class in {"us_equity", "intl_equity"}:
        return "qualified_dividend"
    return "ordinary_income"


def _withdrawal_config_from_profile(
    profile: Any,
    healthcare_schedule: tuple[WithdrawalHealthcarePoint, ...],
) -> WithdrawalConfig:
    """Build the planner WithdrawalConfig from persisted profile columns."""
    if profile is None:
        return WithdrawalConfig(healthcare_schedule=healthcare_schedule)

    def value(name: str, default: Any) -> Any:
        raw = getattr(profile, name, None)
        return default if raw is None else raw

    return WithdrawalConfig(
        strategy="guardrails",
        initial_rate=float(value("withdrawal_initial_rate", 0.05)),
        decline_mode=str(value("withdrawal_decline_mode", "smooth")),
        discretionary_decline_rate=float(value("discretionary_decline_rate", 0.01)),
        phase=WithdrawalPhaseConfig(
            slow_go_age=int(value("phase_slow_go_age", 75)),
            no_go_age=int(value("phase_no_go_age", 85)),
            go_go_pct=float(value("phase_go_go_pct", 1.0)),
            slow_go_pct=float(value("phase_slow_go_pct", 0.85)),
            no_go_pct=float(value("phase_no_go_pct", 0.75)),
        ),
        bridge=WithdrawalBridgeConfig(
            mode=str(value("bridge_mode", "auto")),
            manual_amount=getattr(profile, "bridge_manual_amount", None),
            real_return=float(value("bridge_real_return", 0.01)),
            growth=str(value("bridge_growth", "fixed")),
        ),
        healthcare_schedule=healthcare_schedule,
        essential_floor=getattr(profile, "retirement_essential_floor_override", None),
        base_discretionary=getattr(profile, "retirement_discretionary_override", None),
    )


def _withdrawal_config_from_inputs(
    inputs: RetirementInputs,
    profile: Any,
    base: WithdrawalConfig,
) -> WithdrawalConfig:
    """Resolve floor/discretionary via the budget ratio (R7 baseline carve-out).

    ``e = monthly_essential_target / (essential + discretionary)`` (0.6 when
    the budget is unset; a NULL side is derived from
    ``target_retirement_spend`` minus the other) split of
    ``annual_expenses``; healthcare at the
    household retirement age is netted out of the essential portion so the
    year-0 spending total equals the retirement spend target exactly.
    """
    essential_raw = getattr(profile, "monthly_essential_target", None)
    discretionary_raw = getattr(profile, "monthly_discretionary_target", None)
    essential = float(essential_raw) if essential_raw is not None else None
    discretionary = float(discretionary_raw) if discretionary_raw is not None else None
    # An unset target is NULL, not an explicit $0 — when only one side of the
    # budget is captured, derive the other from the retirement spend target so
    # a lone essential figure doesn't collapse the discretionary layer to zero
    # (which would make every Monte Carlo shortfall a total failure).
    monthly_spend_raw = getattr(profile, "target_retirement_spend", None)
    monthly_spend = float(monthly_spend_raw) if monthly_spend_raw is not None else None
    if discretionary is None and essential is not None and monthly_spend is not None:
        discretionary = max(0.0, monthly_spend - essential)
    if essential is None and discretionary is not None and monthly_spend is not None:
        essential = max(0.0, monthly_spend - discretionary)
    if essential is not None and discretionary is not None and essential + discretionary > 0:
        essential_share = essential / (essential + discretionary)
    else:
        essential_share = 0.6
    total = inputs.annual_expenses
    retirement_age = _household_retirement_primary_age(inputs)
    healthcare_at_retirement = healthcare_ltc(
        EngineWithdrawalConfig(
            healthcare_schedule=tuple(
                EngineHealthcarePoint(age=point.age, real_amount=point.real_amount)
                for point in base.healthcare_schedule
            )
        ),
        retirement_age,
    )
    base_discretionary = (
        base.base_discretionary
        if base.base_discretionary is not None
        else round(max(0.0, (1.0 - essential_share) * total), 2)
    )
    essential_floor = (
        base.essential_floor
        if base.essential_floor is not None
        else round(max(0.0, essential_share * total - healthcare_at_retirement), 2)
    )
    return base.model_copy(
        update={"essential_floor": essential_floor, "base_discretionary": base_discretionary}
    )


def _withdrawal_summary(
    inputs: RetirementInputs,
    drawdown: list[RetirementDrawdownYear],
) -> dict[str, Any]:
    """Bridge size/length + first-year and post-SS withdrawal rates for the UI summary strip."""
    retirement_age = _household_retirement_primary_age(inputs)
    primary_claim, spouse_claim = _ss_claim_ages(inputs)
    earliest_claim = min(
        [primary_claim] + ([spouse_claim] if spouse_claim is not None else [])
    )
    first_retirement = next((row for row in drawdown if row.primary_age >= retirement_age), None)
    post_ss = next(
        (row for row in drawdown if row.primary_age >= max(earliest_claim, retirement_age)),
        None,
    )
    bridge_rows = [row for row in drawdown if row.bridge_draw > 0]
    bridge_size = (
        round(first_retirement.bridge_draw + first_retirement.bridge_balance, 2)
        if first_retirement is not None
        else 0.0
    )
    return {
        "withdrawal_strategy": inputs.withdrawal.strategy,
        "bridge_size": bridge_size,
        "bridge_length_years": len(bridge_rows),
        "first_year_withdrawal_rate": (
            first_retirement.withdrawal_rate if first_retirement is not None else 0.0
        ),
        "post_social_security_withdrawal_rate": (
            post_ss.withdrawal_rate if post_ss is not None else 0.0
        ),
    }


def _ss_claim_ages(inputs: RetirementInputs) -> tuple[int, int | None]:
    """Social-Security claim ages from income sources (primary, spouse).

    With no SS sources the primary claim age collapses to the household
    retirement age so the auto bridge sizes to zero (there is nothing to
    bridge *to*).
    """
    claim_ages = sorted(
        source.start_age
        for source in inputs.income_sources
        if (source.source_type or "").lower() == "social_security"
    )
    if not claim_ages:
        return _household_retirement_primary_age(inputs), None
    primary = claim_ages[0]
    spouse = claim_ages[-1] if len(claim_ages) > 1 else None
    return primary, spouse


def _engine_withdrawal_config(
    inputs: RetirementInputs,
    *,
    r_real: float,
    aca_plans: tuple[ACAYearPlan, ...] | None = None,
) -> EngineWithdrawalConfig:
    """Convert the contract ``WithdrawalConfig`` to the pure-engine config.

    Unresolved floors (``essential_floor is None``, e.g. the persisted
    ``/scenarios`` route) fall back to spend-the-gap semantics: whole
    ``annual_expenses`` as floor, no discretionary layer, no bridge.

    With ``aca_plans`` the healthcare schedule becomes one point per
    retirement age summing the manual (LTC) schedule's carried-forward
    value with the year's ACA planning net and Medicare premiums (members
    65+) — summed, not appended, because ``healthcare_ltc`` is
    last-point-wins, not additive. The essential floor was already
    resolved against the manual schedule alone, so the healthcare stream
    lands *on top* of the spending target and the auto bridge sizes to
    cover it pre-Social-Security.
    """
    wc = inputs.withdrawal
    retirement_age = _household_retirement_primary_age(inputs)
    primary_claim, spouse_claim = _ss_claim_ages(inputs)
    if wc.essential_floor is None:
        essential_floor = inputs.annual_expenses
        base_discretionary = 0.0
        bridge = EngineBridgeConfig(mode="manual", manual_amount=0.0)
    else:
        essential_floor = wc.essential_floor
        base_discretionary = wc.base_discretionary or 0.0
        bridge = EngineBridgeConfig(
            mode=wc.bridge.mode,
            manual_amount=wc.bridge.manual_amount,
            real_return=wc.bridge.real_return,
            growth=wc.bridge.growth,
        )
    healthcare_points = tuple(
        EngineHealthcarePoint(age=point.age, real_amount=point.real_amount)
        for point in wc.healthcare_schedule
    )
    spending_reductions = tuple(
        EngineSpendingReduction(age=point.start_age, real_amount=point.annual_amount)
        for point in inputs.spending_reductions
    )
    if aca_plans is not None:
        manual_only = EngineWithdrawalConfig(healthcare_schedule=healthcare_points)
        healthcare_points = tuple(
            EngineHealthcarePoint(
                age=inputs.primary_age + plan.year_index,
                real_amount=healthcare_ltc(manual_only, inputs.primary_age + plan.year_index)
                + plan.planning_net
                + plan.medicare_premium,
            )
            for plan in aca_plans
            if inputs.primary_age + plan.year_index >= retirement_age
        )
    return EngineWithdrawalConfig(
        strategy=wc.strategy,
        initial_rate=wc.initial_rate,
        decline_mode=wc.decline_mode,
        discretionary_decline_rate=wc.discretionary_decline_rate,
        phase=EnginePhaseConfig(
            slow_go_age=wc.phase.slow_go_age,
            no_go_age=wc.phase.no_go_age,
            go_go_pct=wc.phase.go_go_pct,
            slow_go_pct=wc.phase.slow_go_pct,
            no_go_pct=wc.phase.no_go_pct,
        ),
        bridge=bridge,
        healthcare_schedule=healthcare_points,
        spending_reductions=spending_reductions,
        essential_floor=essential_floor,
        base_discretionary=base_discretionary,
        retirement_age=retirement_age,
        horizon_years=inputs.horizon_years,
        horizon_end_age=inputs.primary_age + inputs.horizon_years,
        primary_ss_claim_age=primary_claim,
        spouse_ss_claim_age=spouse_claim,
        r=r_real,
    )


def _aca_year_plans(inputs: RetirementInputs) -> tuple[ACAYearPlan, ...] | None:
    """Deterministic per-year ACA facts, or ``None`` when the stream is off.

    Planning MAGI uses guaranteed income only — ACA MAGI counts the FULL
    Social Security benefit (taxable or not) plus ordinary sources;
    portfolio draws are unknown here and reconcile at the tax seam.
    """
    cfg = inputs.aca
    if cfg is None or cfg.tier == "none" or not cfg.persons:
        return None
    if cfg.chosen_age21_monthly is None or cfg.benchmark_age21_monthly is None:
        return None
    retirement_age = _household_retirement_primary_age(inputs)

    def planning_magi(year_index: int) -> float:
        inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
        components = _income_components_for_age(
            inputs.income_sources,
            inputs.primary_age + year_index,
            inflation_factor=inflation_factor,
            calendar_year=inputs.as_of_date.year + year_index,
            social_security_payable_ratio=inputs.social_security_payable_ratio,
            social_security_depletion_year=inputs.social_security_depletion_year,
        )
        return components["total"] / inflation_factor

    return build_aca_year_plans(
        persons=tuple(
            ACAPerson(birth_year=person.birth_year, covered_until_year=person.covered_until_year)
            for person in cfg.persons
        ),
        start_year=inputs.as_of_date.year,
        horizon_years=inputs.horizon_years,
        retirement_year_index=max(0, retirement_age - inputs.primary_age),
        chosen_age21_monthly=cfg.chosen_age21_monthly,
        benchmark_age21_monthly=cfg.benchmark_age21_monthly,
        oop_monthly=cfg.oop_monthly,
        medicare_monthly_per_person=cfg.medicare_monthly_per_person or 0.0,
        real_inflation=cfg.healthcare_real_inflation,
        plan_anchor_year=cfg.plan_year or inputs.as_of_date.year,
        planning_magi_fn=planning_magi,
    )


def _aca_magi_nominal(
    outcome: WithdrawalOutcome,
    income_components: dict[str, float],
    gain_ratio: float,
) -> float:
    """Modeled ACA MAGI (nominal) for the year's realized draws.

    Ordinary income + full Social Security + ordinary-income bucket
    draws + the taxable draw's gain slice; Roth/cash/basis draws and
    bridge-sleeve draws stay out (interview decision 2).
    """
    draws = outcome.withdrawals
    ordinary_draws = sum(draws.get(bucket, 0.0) for bucket in _ORDINARY_INCOME_BUCKETS)
    gains = draws.get("taxable", 0.0) * gain_ratio
    return (
        income_components["ordinary"]
        + income_components["social_security"]
        + ordinary_draws
        + gains
    )


def _real_guaranteed_income_fn(inputs: RetirementInputs) -> Callable[[int], float]:
    """Real guaranteed income at a primary age, for bridge sizing."""

    def fn(age: int) -> float:
        year_index = max(0, age - inputs.primary_age)
        inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
        components = _income_components_for_age(
            inputs.income_sources,
            age,
            inflation_factor=inflation_factor,
            calendar_year=inputs.as_of_date.year + year_index,
            social_security_payable_ratio=inputs.social_security_payable_ratio,
            social_security_depletion_year=inputs.social_security_depletion_year,
        )
        return components["total"] / inflation_factor

    return fn


def _carve_bridge_from_balances(balances: dict[str, float], target: float) -> float:
    """Carve the bridge sleeve out of cash, then taxable (R2: scalar, not a bucket).

    At t=0 real == nominal, so the carve is a straight subtraction. Returns
    the amount actually carved (capped by what those buckets hold).
    """
    remaining = max(0.0, target)
    for bucket in ("cash", "taxable"):
        if remaining <= 0:
            break
        take = min(balances.get(bucket, 0.0), remaining)
        if take > 0:
            balances[bucket] -= take
            remaining -= take
    return max(0.0, target) - remaining


def _effective_gain_ratio(inputs: RetirementInputs) -> float:
    """Lots-derived embedded-gain ratio when known, else planning default."""
    if inputs.taxable_gain_ratio is not None:
        return inputs.taxable_gain_ratio
    return TAXABLE_WITHDRAWAL_GAIN_RATIO



# Buckets whose draws are taxed as ordinary income (HSA is modeled as non-medical use).
_ORDINARY_INCOME_BUCKETS = frozenset({"pre_tax", "governmental_457b", "hsa"})


def _rmd_amount(pre_tax_balance: float, primary_age: int) -> float:
    if primary_age < RMD_START_AGE or pre_tax_balance <= 0:
        return 0.0
    # Exact IRS Uniform Lifetime Table divisor. The real table is convex, so a
    # linear slope-1 approximation over-states RMDs sharply with age (and would
    # force-liquidate the account near 100); use the published divisors.
    divisor = IRS_UNIFORM_LIFETIME_DIVISORS.get(
        min(primary_age, 120), IRS_UNIFORM_LIFETIME_DIVISORS[120]
    )
    return pre_tax_balance / divisor


def _early_withdrawal_penalty_rate(bucket: str, primary_age: int) -> float:
    # Integer ages compare against 59.5 so the modeled cutoff matches the rule
    # text shown to users ("before 59½") rather than a bare magic number.
    if bucket == "pre_tax" and primary_age < EARLY_WITHDRAWAL_PENALTY_AGE:
        return 0.10
    # Non-medical HSA use: 20% penalty before 65 (the penalty, unlike pre-tax,
    # ends at the Medicare age, not 59½).
    if bucket == "hsa" and primary_age < 65:
        return 0.20
    return 0.0


def _account_rule_explanations(
    buckets: tuple[RetirementAccountBucket, ...],
) -> tuple[RetirementAccountRule, ...]:
    """One concise rule card per bucket type present in the plan."""
    rules: list[RetirementAccountRule] = []
    seen: set[str] = set()
    for bucket in sorted(buckets, key=lambda b: b.withdrawal_priority):
        bucket_type = bucket.bucket_type
        if bucket_type in seen:
            continue
        seen.add(bucket_type)
        explanation = BUCKET_RULE_EXPLANATIONS.get(bucket_type)
        if explanation is None:
            continue
        rules.append(
            RetirementAccountRule(
                bucket_type=bucket_type,
                label=BUCKET_LABELS.get(bucket_type, bucket.label),
                tax_treatment=BUCKET_TAX_TREATMENT_LABELS.get(
                    bucket.tax_treatment, bucket.tax_treatment
                ),
                early_access=explanation["early_access"],
                rmd=explanation["rmd"],
            )
        )
    return tuple(rules)


def _tax_assumptions(
    context: FederalTaxContext,
    *,
    buckets: tuple[RetirementAccountBucket, ...] = (),
    inputs: RetirementInputs | None = None,
    gain_ratio_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings = []
    if context.filing_status_source != "saved":
        warnings.append("Set filing status in saved assumptions to remove filing-status inference.")
    if context.state_tax_rate > 0:
        warnings.append("State tax is not included in the federal retirement drawdown tax estimate yet.")
    if any(bucket.bucket_type == "governmental_457b" for bucket in buckets):
        warnings.append(
            "Governmental 457(b) is modeled as penalty-free after the plan owner separates from service; "
            "confirm Pinellas plan distribution rules before relying on in-service access."
        )
    if inputs and inputs.social_security_payable_ratio < 1.0:
        percent = round(inputs.social_security_payable_ratio * 100)
        year = inputs.social_security_depletion_year or DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR
        warnings.append(f"Social Security is modeled at {percent}% of scheduled benefits starting in {year}.")
    capital_gains_zero_rate_limit, capital_gains_twenty_rate_threshold = LONG_TERM_CAPITAL_GAINS_BRACKETS_2026[
        context.filing_status
    ]
    lots_derived_gain_ratio = inputs is not None and inputs.taxable_gain_ratio is not None
    effective_gain_ratio = (
        inputs.taxable_gain_ratio
        if lots_derived_gain_ratio and inputs is not None
        else TAXABLE_WITHDRAWAL_GAIN_RATIO
    )
    if lots_derived_gain_ratio:
        gain_ratio_source = "tax_lots"
        gain_ratio_detail = (
            f"Embedded gain estimated from your taxable cost basis "
            f"({round(effective_gain_ratio * 100)}% of taxable withdrawals taxed as long-term gains)."
        )
    else:
        gain_ratio_source = "planning_assumption"
        gain_ratio_detail = (
            f"No taxable cost-basis lots found; assuming {round(effective_gain_ratio * 100)}% "
            "of each taxable withdrawal is a long-term gain."
        )
    return {
        "tax_year": FEDERAL_TAX_YEAR,
        "filing_status": context.filing_status,
        "filing_status_label": FILING_STATUS_LABELS[context.filing_status],
        "filing_status_source": context.filing_status_source,
        "standard_deduction": STANDARD_DEDUCTION_2026[context.filing_status],
        "additional_age_65_deduction": ADDITIONAL_STANDARD_DEDUCTION_65_2026[context.filing_status],
        "capital_gains_zero_rate_limit": capital_gains_zero_rate_limit,
        "capital_gains_twenty_rate_threshold": capital_gains_twenty_rate_threshold,
        "taxable_withdrawal_gain_ratio": round(effective_gain_ratio, 6),
        "taxable_withdrawal_gain_ratio_source": gain_ratio_source,
        "taxable_withdrawal_gain_ratio_detail": gain_ratio_detail,
        "taxable_cost_basis": (gain_ratio_meta or {}).get("cost_basis"),
        "taxable_market_value": (gain_ratio_meta or {}).get("market_value"),
        "state_tax_rate": context.state_tax_rate,
        "state_tax_source": context.state_tax_source,
        "withdrawal_order": list(DEFAULT_DRAWDOWN_ORDER),
        "withdrawal_order_label": "Cash, taxable brokerage, governmental 457(b), pre-tax, Roth, HSA, then other.",
        "governmental_457b_penalty_rate": 0.0,
        "pre_tax_early_withdrawal_penalty_rate": 0.10,
        "hsa_non_medical_penalty_rate_before_65": 0.20,
        "social_security_payable_ratio": inputs.social_security_payable_ratio if inputs else 1.0,
        "social_security_depletion_year": inputs.social_security_depletion_year if inputs else None,
        "method": (
            "Federal taxes are derived yearly from ordinary income, taxable Social Security, "
            "pre-tax/457(b) withdrawals, estimated taxable-brokerage gains, 2026 brackets, "
            "standard deduction, age-65 standard deduction, and the saved Social Security payable ratio."
        ),
        "manual_rate_used": False,
        "warnings": warnings,
    }


def _filing_status_from_profile(profile: Any, spouse_age: int | None) -> tuple[str, str]:
    raw = str(getattr(profile, "filing_status", "") or "").strip().lower()
    normalized = re.sub(r"[^a-z]+", "_", raw).strip("_")
    if normalized in {"married_filing_jointly", "married_jointly", "mfj", "joint"}:
        return "married_filing_jointly", "saved"
    if normalized in {"married_filing_separately", "married_separately", "mfs"}:
        return "married_filing_separately", "saved"
    if normalized in {"head_of_household", "hoh"}:
        return "head_of_household", "saved"
    if normalized in {"single"}:
        return "single", "saved"
    if spouse_age is not None:
        return "married_filing_jointly", "inferred_from_spouse"
    return "single", "default"


def _state_tax_rate_from_profile(profile: Any) -> float:
    state = str(getattr(profile, "state_of_residence", "") or "").strip().upper()
    if state in NO_STATE_INCOME_TAX_STATES:
        return 0.0
    value = getattr(profile, "marginal_state_tax_rate", None)
    if value is None:
        return 0.0
    parsed = float(value or 0.0)
    if parsed > 1:
        parsed /= 100.0
    return max(0.0, min(parsed, 0.2))


def _state_tax_source_from_profile(profile: Any) -> str:
    state = str(getattr(profile, "state_of_residence", "") or "").strip().upper()
    if state in NO_STATE_INCOME_TAX_STATES:
        return f"{state}_no_state_income_tax"
    return "saved_marginal_state_tax_rate" if getattr(profile, "marginal_state_tax_rate", None) is not None else "not_set"


def _social_security_payable_ratio(value: float | None) -> float:
    if value is None:
        return DEFAULT_SOCIAL_SECURITY_PAYABLE_RATIO
    parsed = float(value or 0.0)
    if parsed > 1.0:
        parsed /= 100.0
    return max(0.0, min(parsed, 1.0))


def _spouse_retirement_primary_age(inputs: RetirementInputs) -> int | None:
    if inputs.spouse_retirement_age is None or inputs.spouse_age is None:
        return None
    return inputs.primary_age + max(0, inputs.spouse_retirement_age - inputs.spouse_age)


def _household_retirement_primary_age(inputs: RetirementInputs) -> int:
    spouse_primary_age = _spouse_retirement_primary_age(inputs)
    if spouse_primary_age is None:
        return inputs.retirement_age
    return max(inputs.retirement_age, spouse_primary_age)


def _partial_year_amounts_real(
    inputs: RetirementInputs, primary_age: int
) -> tuple[float, float, float] | None:
    """(spend, spouse net, spouse gross) annual REAL $ for a partial-retirement year.

    A partial-retirement year is one where the primary has retired but the
    spouse is still working: ``spouse_net_monthly_income`` gates the feature
    (None == off == legacy behavior). Spend falls back to ``annual_expenses``
    when no window-specific override is set.
    """
    if inputs.spouse_net_monthly_income is None:
        return None
    if not inputs.retirement_age <= primary_age < _household_retirement_primary_age(inputs):
        return None
    spend = (
        inputs.partial_retirement_monthly_spend * 12.0
        if inputs.partial_retirement_monthly_spend is not None
        else inputs.annual_expenses
    )
    net = inputs.spouse_net_monthly_income * 12.0
    gross = inputs.spouse_gross_annual_income or 0.0
    return spend, net, gross


def _contribution_bucket(balances: dict[str, float]) -> str:
    for bucket in ("pre_tax", "governmental_457b", "taxable", "cash", "roth"):
        if balances.get(bucket, 0.0) > 0:
            return bucket
    return "taxable"


def _income_components_for_age(
    income_sources: tuple[RetirementIncomeSource, ...],
    primary_age: int,
    *,
    inflation_factor: float,
    calendar_year: int,
    social_security_payable_ratio: float,
    social_security_depletion_year: int | None,
) -> dict[str, float]:
    total = 0.0
    social_security = 0.0
    ordinary = 0.0
    for source in income_sources:
        if primary_age < source.start_age:
            continue
        annual = source.monthly_amount * 12.0
        amount = annual * inflation_factor if source.inflation_adjusted else annual
        if (source.source_type or "").lower() == "social_security":
            if (
                social_security_depletion_year is not None
                and calendar_year >= social_security_depletion_year
            ):
                amount *= social_security_payable_ratio
            social_security += amount
        else:
            ordinary += amount
        total += amount
    return {"total": total, "social_security": social_security, "ordinary": ordinary}


def _taxable_social_security(
    *,
    filing_status: str,
    social_security_benefits: float,
    other_income: float,
) -> float:
    if social_security_benefits <= 0:
        return 0.0
    if filing_status == "married_filing_jointly":
        base_amount = 32_000.0
        adjusted_base = 44_000.0
    elif filing_status == "married_filing_separately":
        base_amount = 0.0
        adjusted_base = 0.0
    else:
        base_amount = 25_000.0
        adjusted_base = 34_000.0
    provisional_income = other_income + social_security_benefits * 0.5
    if provisional_income <= base_amount:
        return 0.0
    if provisional_income <= adjusted_base:
        return min(social_security_benefits * 0.5, (provisional_income - base_amount) * 0.5)
    lower_tier_taxable = min(social_security_benefits * 0.5, (adjusted_base - base_amount) * 0.5)
    return min(
        social_security_benefits * 0.85,
        lower_tier_taxable + (provisional_income - adjusted_base) * 0.85,
    )


def _federal_tax_estimate(
    context: FederalTaxContext,
    *,
    ordinary_income: float,
    social_security_benefits: float,
    long_term_capital_gains: float,
    primary_age: int,
    spouse_age: int | None,
    inflation_factor: float,
) -> float:
    status = context.filing_status
    taxable_social_security = _taxable_social_security(
        filing_status=status,
        social_security_benefits=social_security_benefits,
        other_income=ordinary_income + long_term_capital_gains,
    )
    gross_ordinary = ordinary_income + taxable_social_security
    standard_deduction = STANDARD_DEDUCTION_2026[status] * inflation_factor
    age_65_count = int(primary_age >= 65)
    if status == "married_filing_jointly" and spouse_age is not None:
        age_65_count += int(spouse_age >= 65)
    additional_deduction = ADDITIONAL_STANDARD_DEDUCTION_65_2026[status] * inflation_factor * age_65_count
    total_deduction = standard_deduction + additional_deduction
    taxable_ordinary = max(0.0, gross_ordinary - total_deduction)
    deduction_remaining = max(0.0, total_deduction - gross_ordinary)
    taxable_capital_gains = max(0.0, long_term_capital_gains - deduction_remaining)
    ordinary_tax = _progressive_tax(
        taxable_ordinary,
        ORDINARY_TAX_BRACKETS_2026[status],
        inflation_factor=inflation_factor,
    )
    capital_gains_tax = _long_term_capital_gains_tax(
        filing_status=status,
        taxable_ordinary=taxable_ordinary,
        taxable_capital_gains=taxable_capital_gains,
        inflation_factor=inflation_factor,
    )
    niit = _niit_tax(
        filing_status=status,
        modified_agi=gross_ordinary + long_term_capital_gains,
        net_investment_income=long_term_capital_gains,
        inflation_factor=inflation_factor,
    )
    return max(0.0, ordinary_tax + capital_gains_tax + niit)


def _progressive_tax(
    taxable_income: float,
    brackets: tuple[tuple[float, float], ...],
    *,
    inflation_factor: float,
) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in brackets:
        scaled_upper = upper if upper == float("inf") else upper * inflation_factor
        if taxable_income <= lower:
            break
        taxed = min(taxable_income, scaled_upper) - lower
        if taxed > 0:
            tax += taxed * rate
        lower = scaled_upper
    return tax


def _long_term_capital_gains_tax(
    *,
    filing_status: str,
    taxable_ordinary: float,
    taxable_capital_gains: float,
    inflation_factor: float,
) -> float:
    if taxable_capital_gains <= 0:
        return 0.0
    zero_rate_limit, twenty_rate_limit = LONG_TERM_CAPITAL_GAINS_BRACKETS_2026[filing_status]
    zero_rate_limit *= inflation_factor
    twenty_rate_limit *= inflation_factor
    remaining = taxable_capital_gains
    zero_rate_amount = min(remaining, max(0.0, zero_rate_limit - taxable_ordinary))
    remaining -= zero_rate_amount
    fifteen_rate_amount = min(remaining, max(0.0, twenty_rate_limit - max(taxable_ordinary, zero_rate_limit)))
    remaining -= fifteen_rate_amount
    return fifteen_rate_amount * 0.15 + max(0.0, remaining) * 0.20


def _niit_tax(
    *,
    filing_status: str,
    modified_agi: float,
    net_investment_income: float,
    inflation_factor: float,
) -> float:
    threshold = NIIT_THRESHOLDS_2026[filing_status] * inflation_factor
    return min(max(0.0, net_investment_income), max(0.0, modified_agi - threshold)) * 0.038


def _append_preview_social_security(
    inputs: RetirementInputs,
    *,
    primary_monthly: float | None,
    spouse_monthly: float | None,
    primary_annual_earnings: float | None,
    spouse_annual_earnings: float | None,
    primary_start_age: int | None,
    spouse_start_age: int | None,
) -> RetirementInputs:
    primary_claim_age = primary_start_age or SSA_FULL_RETIREMENT_AGE
    spouse_claim_age = spouse_start_age or SSA_FULL_RETIREMENT_AGE
    estimated_primary_monthly = primary_monthly or _estimate_social_security_monthly(
        primary_annual_earnings,
        claim_age=primary_claim_age,
        stop_work_age=inputs.retirement_age,
    )
    estimated_spouse_monthly = spouse_monthly or _estimate_social_security_monthly(
        spouse_annual_earnings,
        claim_age=spouse_claim_age,
        stop_work_age=inputs.spouse_retirement_age or inputs.retirement_age,
    )
    provided = any(
        value is not None and value > 0
        for value in (estimated_primary_monthly, estimated_spouse_monthly)
    )
    if not provided:
        return inputs

    sources = [
        source
        for source in inputs.income_sources
        if (source.source_type or "").lower() != "social_security"
    ]
    if estimated_primary_monthly is not None and estimated_primary_monthly > 0:
        sources.append(
            RetirementIncomeSource(
                label="Social Security - primary",
                source_type="social_security",
                owner_name="primary",
                start_age=primary_claim_age,
                monthly_amount=estimated_primary_monthly,
                inflation_adjusted=True,
            )
        )
    if (
        estimated_spouse_monthly is not None
        and estimated_spouse_monthly > 0
        and inputs.spouse_age is not None
    ):
        primary_timeline_age = inputs.primary_age + max(0, spouse_claim_age - inputs.spouse_age)
        sources.append(
            RetirementIncomeSource(
                label=f"Social Security - spouse at {spouse_claim_age}",
                source_type="social_security",
                owner_name="spouse",
                start_age=primary_timeline_age,
                monthly_amount=estimated_spouse_monthly,
                inflation_adjusted=True,
            )
        )
    return inputs.model_copy(update={"income_sources": tuple(sources)})


def _estimate_social_security_monthly(
    annual_earnings: float | None,
    *,
    claim_age: int,
    stop_work_age: int | None = None,
) -> float | None:
    if annual_earnings is None or annual_earnings <= 0:
        return None
    aime = min(float(annual_earnings), SSA_2026_TAXABLE_WAGE_BASE) / 12.0
    if stop_work_age is not None:
        # AIME averages the best 35 years; an early retiree fills the
        # missing years with zeros. Career assumed to start at 22, and
        # earnings after the claim age never enter the average.
        years_worked = max(0.0, float(min(stop_work_age, claim_age) - SSA_ASSUMED_CAREER_START_AGE))
        aime *= min(years_worked, 35.0) / 35.0
    pia = (
        min(aime, SSA_2026_FIRST_BEND_POINT) * 0.90
        + max(min(aime, SSA_2026_SECOND_BEND_POINT) - SSA_2026_FIRST_BEND_POINT, 0.0) * 0.32
        + max(aime - SSA_2026_SECOND_BEND_POINT, 0.0) * 0.15
    )
    if claim_age < SSA_FULL_RETIREMENT_AGE:
        months_early = max(0, (SSA_FULL_RETIREMENT_AGE - claim_age) * 12)
        first_36 = min(months_early, 36)
        extra = max(months_early - 36, 0)
        factor = 1.0 - (first_36 * (5.0 / 900.0)) - (extra * (5.0 / 1200.0))
    else:
        months_late = min(max(0, (claim_age - SSA_FULL_RETIREMENT_AGE) * 12), 36)
        factor = 1.0 + months_late * (2.0 / 300.0)
    return round(max(pia * factor, 0.0), 2)
