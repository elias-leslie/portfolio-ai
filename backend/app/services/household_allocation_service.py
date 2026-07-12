"""Canonical household allocation universe with explicit holdings coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.portfolio.asset_classification import HoldingValue

_INVESTMENT_ACCOUNT_GROUPS = {"retirement", "taxable", "education"}
_NUMERIC_RECONCILIATION_TOLERANCE_DOLLARS = 1.0


@dataclass(frozen=True, slots=True)
class HouseholdAllocationAccount:
    """Coverage of one canonical household investment account."""

    household_account_id: str | None
    label: str
    current_value: float
    exact_value: float
    unclassified_value: float
    manual_holdings_editable: bool
    priced_position_count: int
    mismatch: bool = False


@dataclass(frozen=True, slots=True)
class HouseholdAllocationUniverse:
    """Asset-class values reconciled to the canonical household total."""

    total_value: float
    by_class: dict[str, float]
    exact_value: float
    unclassified_value: float
    status: str
    message: str
    accounts: tuple[HouseholdAllocationAccount, ...]

    @property
    def coverage_pct(self) -> float:
        if self.total_value <= 0:
            return 0.0
        return max(0.0, min(self.exact_value / self.total_value, 1.0))


class HouseholdAllocationService:
    """Build drift inputs from controlled household accounts and exact holdings."""

    def __init__(self, storage: Any, classifier: Any, price_fetcher: Any) -> None:
        self.storage = storage
        self.classifier = classifier
        self.price_fetcher = price_fetcher

    def build(self, dashboard: Any) -> HouseholdAllocationUniverse:
        accounts = [
            account
            for account in list(getattr(dashboard, "accounts", []) or [])
            if str(getattr(account, "asset_group", "") or "").lower()
            in _INVESTMENT_ACCOUNT_GROUPS
            and float(getattr(account, "current_value", 0.0) or 0.0) > 0
        ]
        linked_ids = sorted(
            {
                str(linked_id)
                for account in accounts
                if (linked_id := getattr(account, "linked_portfolio_account_id", None))
            }
        )
        positions_by_account = self._priced_positions(linked_ids)
        by_class: dict[str, float] = {}
        coverage_accounts: list[HouseholdAllocationAccount] = []
        account_total = 0.0
        exact_total = 0.0
        unknown_total = 0.0
        mismatch = False

        for account in accounts:
            value = max(float(getattr(account, "current_value", 0.0) or 0.0), 0.0)
            account_total += value
            label = str(getattr(account, "label", "") or "Investment account")
            household_account_id = getattr(account, "household_account_id", None)
            linked_id_value = getattr(account, "linked_portfolio_account_id", None)
            linked_id = str(linked_id_value) if linked_id_value else None
            cash_value = min(
                max(float(getattr(account, "cash_balance", 0.0) or 0.0), 0.0),
                value,
            )
            position_values = positions_by_account.get(linked_id or "", [])
            classified = self.classifier.classify_value(
                HoldingValue(symbol=row["symbol"], value=row["current_value"])
                for row in position_values
            )
            class_values = {
                asset_class: float(class_value or 0.0)
                for asset_class, class_value in classified.by_class.items()
                if asset_class != "unclassified" and float(class_value or 0.0) > 0
            }
            classified_positions = sum(class_values.values())
            raw_exact = cash_value + classified_positions
            tolerance = _NUMERIC_RECONCILIATION_TOLERANCE_DOLLARS
            account_mismatch = raw_exact > value + tolerance
            mismatch = mismatch or account_mismatch

            if raw_exact > 0 and value - raw_exact <= tolerance:
                scale = value / raw_exact
                cash_value *= scale
                class_values = {
                    asset_class: class_value * scale
                    for asset_class, class_value in class_values.items()
                }
                classified_positions = sum(class_values.values())
                raw_exact = value

            # The canonical remainder includes unpriced/unclassified positions
            # and any account-value-only balance without holdings detail.
            unknown_value = max(value - raw_exact, 0.0)
            unknown_value = min(unknown_value, value)
            exact_value = max(value - unknown_value, 0.0)

            if cash_value > 0:
                by_class["cash"] = by_class.get("cash", 0.0) + cash_value
            for asset_class, class_value in class_values.items():
                by_class[asset_class] = by_class.get(asset_class, 0.0) + class_value

            exact_total += exact_value
            unknown_total += unknown_value
            coverage_accounts.append(
                HouseholdAllocationAccount(
                    household_account_id=(
                        str(household_account_id) if household_account_id else None
                    ),
                    label=label,
                    current_value=round(value, 2),
                    exact_value=round(exact_value, 2),
                    unclassified_value=round(unknown_value, 2),
                    manual_holdings_editable=bool(household_account_id)
                    and not (linked_id or "").startswith("snaptrade:"),
                    priced_position_count=len(position_values),
                    mismatch=account_mismatch,
                )
            )

        overview = getattr(dashboard, "overview", None)
        canonical_total = float(getattr(overview, "invested_assets", 0.0) or 0.0)
        total_value = canonical_total if canonical_total > 0 else account_total
        total_tolerance = _NUMERIC_RECONCILIATION_TOLERANCE_DOLLARS
        if total_value > account_total + total_tolerance:
            unknown_total += total_value - account_total
        elif account_total > total_value + total_tolerance:
            mismatch = True
            total_value = account_total

        unknown_total = min(max(unknown_total, 0.0), max(total_value, 0.0))
        exact_total = max(total_value - unknown_total, 0.0)
        if unknown_total > 0:
            by_class["unclassified"] = unknown_total

        blocking_count = int(
            getattr(getattr(dashboard, "account_control", None), "blocking_issue_count", 0)
            or 0
        )
        if blocking_count > 0:
            status = "blocked"
            message = (
                f"{blocking_count} account-control issue"
                f"{'s' if blocking_count != 1 else ''} block trusted allocation totals."
            )
        elif total_value <= 0:
            status = "unverified"
            message = "Canonical household investment value is unavailable."
        elif mismatch:
            status = "mismatch"
            message = (
                "One or more priced account holdings exceed the canonical account balance. "
                "Reconcile the account before relying on allocation or generating trades."
            )
        elif unknown_total > total_tolerance:
            status = "partial"
            message = (
                f"Exact holdings classify {exact_total / total_value:.1%} of canonical "
                "household investments. Add holdings for the remaining account value."
            )
        else:
            status = "complete"
            message = "Exact holdings and cash cover canonical household investments."

        return HouseholdAllocationUniverse(
            total_value=round(total_value, 4),
            by_class={
                asset_class: round(value, 4)
                for asset_class, value in by_class.items()
                if value > 0
            },
            exact_value=round(exact_total, 4),
            unclassified_value=round(unknown_total, 4),
            status=status,
            message=message,
            accounts=tuple(coverage_accounts),
        )

    def _priced_positions(self, account_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not account_ids:
            return {}
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT account_id, symbol, shares
                FROM portfolio_positions
                WHERE account_id = ANY(%s)
                  AND position_type = 'long'
                  AND shares > 0
                """,
                [account_ids],
            ).fetchall()
        if not rows:
            return {}
        symbols = sorted({str(row[1]).upper() for row in rows})
        prices = self.price_fetcher.fetch_cached_price_data(symbols)
        out: dict[str, list[dict[str, Any]]] = {}
        for account_id, raw_symbol, raw_shares in rows:
            symbol = str(raw_symbol).upper()
            shares = float(raw_shares or 0.0)
            info = prices.get(symbol)
            price = float(getattr(info, "price", 0.0) or 0.0) if info else 0.0
            if shares <= 0 or price <= 0 or getattr(info, "error", None):
                continue
            out.setdefault(str(account_id), []).append(
                {"symbol": symbol, "current_value": shares * price}
            )
        return out
