"""Reconcile taxable basis evidence to the actual retirement account universe."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.portfolio.price_fetcher import PriceDataFetcher
from app.services._retirement_ownership import is_education_account
from app.services.retirement_planning_assumptions import TAXABLE_WITHDRAWAL_GAIN_RATIO, _bucket_type


def basis_fingerprint(positions: list[dict[str, Any]], value: float, cash: float) -> str:
    # A new quote does not change basis; a holding/share/cash change does.
    shape = sorted((str(p["account_id"]), str(p["symbol"]), float(p["shares"])) for p in positions)
    return hashlib.sha256(
        json.dumps([shape, cash, value if not shape else None]).encode()
    ).hexdigest()


def summarize_basis(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(a["market_value"] for a in accounts)
    covered = sum(a["covered_value"] for a in accounts)
    gain = sum(a["known_gain"] for a in accounts)
    missing = max(0, total - covered)
    ratio = (gain + missing * TAXABLE_WITHDRAWAL_GAIN_RATIO) / total if total else 0
    return {
        "accounts": accounts,
        "market_value": round(total, 2),
        "covered_value": round(covered, 2),
        "coverage": min(1, covered / total) if total else 1,
        "cost_basis": round(sum(a["cost_basis"] for a in accounts), 2),
        "gain_ratio": min(1, max(0, ratio)),
        "gain_ratio_low": min(1, gain / total) if total else 0,
        "gain_ratio_high": min(1, (gain + missing) / total) if total else 0,
        "source": "account_basis"
        if missing <= 1
        else "partial_basis"
        if covered > 0
        else "planning_assumption",
    }


class RetirementBasisService:
    def __init__(self, storage: Any):
        self.storage = storage

    def coverage(self, dashboard: Any) -> dict[str, Any]:
        accounts = [
            a
            for a in getattr(dashboard, "accounts", [])
            if not is_education_account(a)
            and str(getattr(a, "asset_group", "")).lower() not in {"credit", "debt"}
            and _bucket_type(
                str(getattr(a, "asset_group", "")), str(getattr(a, "account_type", ""))
            )
            == "taxable"
            and float(getattr(a, "current_value", 0) or 0) > 0
        ]
        ids = [
            str(a.household_account_id)
            for a in accounts
            if getattr(a, "household_account_id", None)
        ]
        links = [
            str(a.linked_portfolio_account_id)
            for a in accounts
            if getattr(a, "linked_portfolio_account_id", None)
        ]
        with self.storage.connection() as conn:
            rows = (
                conn.execute(
                    """SELECT p.account_id,a.household_account_id,p.symbol,p.shares,
                    sp.average_purchase_price,sp.last_synced_at,
                    lots.shares,lots.cost
                FROM portfolio_positions p JOIN portfolio_accounts a ON a.id=p.account_id
                LEFT JOIN LATERAL (SELECT average_purchase_price,last_synced_at FROM snaptrade_positions
                    WHERE portfolio_position_id=p.id ORDER BY last_synced_at DESC LIMIT 1) sp ON true
                LEFT JOIN LATERAL (SELECT SUM(remaining_shares) shares,SUM(remaining_shares*cost_per_share) cost
                    FROM portfolio_tax_lots WHERE account_id=p.account_id AND symbol=p.symbol
                    AND disposed_at IS NULL AND remaining_shares>0) lots ON true
                WHERE (a.household_account_id::text=ANY(%s) OR a.id=ANY(%s))
                  AND p.position_type='long' AND p.shares>0""",
                    [ids, links],
                ).fetchall()
                if ids or links
                else []
            )
            saved = (
                conn.execute(
                    "SELECT id,metadata FROM household_accounts WHERE id::text=ANY(%s)", [ids]
                ).fetchall()
                if ids
                else []
            )
        confirmed = {str(k): (v or {}).get("retirement_cost_basis") for k, v in saved}
        prices = (
            PriceDataFetcher(self.storage).fetch_cached_price_data(
                sorted({str(r[2]) for r in rows})
            )
            if rows
            else {}
        )
        result = []
        for account in accounts:
            aid = str(getattr(account, "household_account_id", "") or "")
            link = str(getattr(account, "linked_portfolio_account_id", "") or "")
            cash = max(0, float(getattr(account, "cash_balance", 0) or 0))
            value = max(0, float(account.current_value) - cash)
            if value <= 0:
                continue
            positions = []
            for row in rows:
                pid, hid, symbol, shares, average, as_of, lot_shares, lot_cost = row
                if (aid and str(hid) == aid) or (link and str(pid) == link):
                    info = prices.get(str(symbol))
                    price = (
                        float(getattr(info, "price", 0) or 0)
                        if info and not getattr(info, "error", None)
                        else 0
                    )
                    shares = float(shares)
                    basis = None
                    source = "unknown"
                    if lot_shares is not None and abs(float(lot_shares) - shares) < 0.0001:
                        basis = float(lot_cost)
                        source = "tax_lots"
                    elif average is not None and float(average) >= 0:
                        basis = float(average) * shares
                        source = "broker_average_cost"
                    positions.append(
                        {
                            "account_id": str(pid),
                            "symbol": str(symbol),
                            "shares": shares,
                            "value": price * shares,
                            "basis": basis,
                            "source": source,
                            "as_of": str(as_of) if as_of else None,
                        }
                    )
            fingerprint = basis_fingerprint(positions, value, cash)
            evidence = confirmed.get(aid)
            covered = sum(p["value"] for p in positions if p["basis"] is not None)
            cost = sum(p["basis"] for p in positions if p["basis"] is not None and p["value"] > 0)
            known_gain = max(0, covered - cost)
            source = "positions"
            if isinstance(evidence, dict) and evidence.get("fingerprint") == fingerprint:
                covered = value
                cost = float(evidence["cost_basis"])
                known_gain = max(0, value - cost)
                source = "confirmed"
            elif covered > value + max(1, value * 0.01):
                # Conflicting aliases/snapshots must not manufacture complete coverage.
                covered = 0
                cost = 0
                known_gain = 0
                source = "reconcile"
            elif covered > value:
                known_gain *= value / covered
                cost *= value / covered
                covered = value
            result.append(
                {
                    "account_id": aid,
                    "label": str(getattr(account, "label", "Taxable account")),
                    "market_value": round(value, 2),
                    "covered_value": round(covered, 2),
                    "cost_basis": round(cost, 2),
                    "known_gain": round(known_gain, 2),
                    "source": source,
                    "fingerprint": fingerprint,
                    "positions": positions,
                    "confirmation_stale": bool(
                        evidence and evidence.get("fingerprint") != fingerprint
                    ),
                }
            )
        return summarize_basis(result)

    def confirm(
        self, dashboard: Any, account_id: str, fingerprint: str, cost_basis: float
    ) -> dict[str, Any]:
        coverage = self.coverage(dashboard)
        account = next((a for a in coverage["accounts"] if a["account_id"] == account_id), None)
        if account is None or account["fingerprint"] != fingerprint:
            raise ValueError(
                "Account holdings changed. Refresh and review the current account before confirming basis."
            )
        record = {
            "fingerprint": fingerprint,
            "cost_basis": cost_basis,
            "confirmed_at": datetime.now(UTC).isoformat(),
            "market_value_at_confirmation": account["market_value"],
        }
        with self.storage.connection() as conn:
            conn.execute(
                "UPDATE household_accounts SET metadata=jsonb_set(COALESCE(metadata,'{}'::jsonb),'{retirement_cost_basis}',%s::jsonb),updated_at=now() WHERE id=%s",
                [json.dumps(record), account_id],
            )
            conn.commit()
        return record
