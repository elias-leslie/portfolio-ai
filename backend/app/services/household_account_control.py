"""Household account control checks for source aliases and total safety."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models.household_finance import (
    HouseholdAccountControl,
    HouseholdAccountControlIssue,
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdInboxItem,
)

_MATERIALITY = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class SourceAccountRow:
    source: str
    source_account_id: str
    connection_id: str | None
    household_account_id: str | None
    account_label: str
    institution_name: str | None
    account_mask: str | None
    current_value: Decimal | None
    cash_balance: Decimal | None
    currency: str | None
    last_synced_at: datetime | None


@dataclass(frozen=True, slots=True)
class HouseholdAccountControlResult:
    control: HouseholdAccountControl
    source_owned_household_account_ids: set[str]
    source_owned_account_values: dict[str, dict[str, Any]]


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _normalized(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _money_key(value: Decimal | None) -> str:
    if value is None:
        return "null"
    return str(value.quantize(_MATERIALITY))


def _is_material(value: Decimal | None) -> bool:
    return value is not None and abs(value) >= _MATERIALITY


def _effective_value(row: SourceAccountRow) -> Decimal | None:
    return row.current_value if row.current_value is not None else row.cash_balance


def _source_value(row: SourceAccountRow) -> dict[str, Any]:
    return {
        "current_value": row.current_value,
        "cash_balance": row.cash_balance,
        "last_synced_at": row.last_synced_at,
        "account_mask": row.account_mask,
    }


def _issue_id(code: str, *parts: object) -> str:
    suffix = "|".join(_normalized(part) for part in parts if _normalized(part))
    return f"{code}:{suffix}" if suffix else code


def _source_rows(storage: Any) -> list[SourceAccountRow]:
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT
                'snaptrade' AS source,
                sa.account_id AS source_account_id,
                sa.authorization_id AS connection_id,
                sa.household_account_id::text,
                COALESCE(ha.canonical_label, sa.name, 'SnapTrade account') AS account_label,
                sa.institution_name,
                sa.account_mask,
                sa.balance AS current_value,
                sa.cash_balance,
                sa.currency,
                sa.last_synced_at
            FROM snaptrade_accounts sa
            LEFT JOIN household_accounts ha ON ha.id = sa.household_account_id
            WHERE sa.balance IS NOT NULL OR sa.cash_balance IS NOT NULL
            UNION ALL
            SELECT
                'plaid' AS source,
                pa.account_id AS source_account_id,
                pa.item_id AS connection_id,
                pa.household_account_id::text,
                COALESCE(ha.canonical_label, pa.name, 'Plaid account') AS account_label,
                pi.institution_name,
                pa.mask AS account_mask,
                COALESCE(pa.current_balance, pa.available_balance) AS current_value,
                NULL::numeric AS cash_balance,
                pa.iso_currency_code AS currency,
                pa.last_synced_at
            FROM plaid_accounts pa
            LEFT JOIN plaid_items pi ON pi.item_id = pa.item_id
            LEFT JOIN household_accounts ha ON ha.id = pa.household_account_id
            WHERE pa.current_balance IS NOT NULL OR pa.available_balance IS NOT NULL
            """
        ).fetchall()
    return [
        SourceAccountRow(
            source=str(row[0]),
            source_account_id=str(row[1]),
            connection_id=str(row[2]) if row[2] is not None else None,
            household_account_id=str(row[3]) if row[3] is not None else None,
            account_label=str(row[4]),
            institution_name=str(row[5]) if row[5] is not None else None,
            account_mask=str(row[6]) if row[6] is not None else None,
            current_value=_decimal(row[7]),
            cash_balance=_decimal(row[8]),
            currency=str(row[9]) if row[9] is not None else None,
            last_synced_at=_timestamp(row[10]),
        )
        for row in rows
    ]


def _unlinked_value_evidence_issues(storage: Any) -> list[HouseholdAccountControlIssue]:
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                COALESCE(institution_name, ''),
                COALESCE(account_name, ''),
                account_mask,
                balance,
                holdings_value,
                cash_balance
            FROM household_evidence_accounts
            WHERE household_account_id IS NULL
              AND (
                COALESCE(ABS(balance), 0) >= 0.01
                OR COALESCE(ABS(holdings_value), 0) >= 0.01
                OR COALESCE(ABS(cash_balance), 0) >= 0.01
              )
            ORDER BY updated_at DESC
            LIMIT 10
            """
        ).fetchall()
    issues: list[HouseholdAccountControlIssue] = []
    for row in rows:
        label = " · ".join(part for part in [str(row[1]), str(row[2])] if part)
        value = _decimal(row[4]) or (_decimal(row[5]) or Decimal("0")) + (
            _decimal(row[6]) or Decimal("0")
        )
        issues.append(
            HouseholdAccountControlIssue(
                id=_issue_id("unlinked_value_evidence", row[0]),
                code="unlinked_value_evidence",
                severity="high",
                title="Value evidence is not linked to an account",
                detail=(
                    f"{label or 'An evidence row'} carries {value} but has no canonical "
                    "household account, so totals cannot be trusted until it is linked or excluded."
                ),
                account_label=label or None,
                source="evidence",
                source_account_ids=[str(row[0])],
                affects_totals=True,
            )
        )
    return issues


def _transaction_suspense_issue(storage: Any) -> HouseholdAccountControlIssue | None:
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                COUNT(*) FILTER (
                    WHERE jsonb_exists(metadata, 'plaid_transaction_id')
                ) AS plaid_count
            FROM household_transactions
            WHERE household_account_id IS NULL
            """
        ).fetchone()
    total = int(row[0] or 0) if row is not None else 0
    plaid = int(row[1] or 0) if row is not None else 0
    if total <= 0:
        return None
    document_count = total - plaid
    source_parts = [
        f"{plaid} Plaid" if plaid else None,
        f"{document_count} document" if document_count else None,
    ]
    source_detail = " and ".join(part for part in source_parts if part)
    return HouseholdAccountControlIssue(
        id="transaction_suspense",
        code="transaction_suspense",
        severity="medium",
        title="Transactions are in account suspense",
        detail=(
            f"{source_detail} transaction{'' if total == 1 else 's'} "
            f"{'is' if total == 1 else 'are'} not assigned "
            "to a canonical account. "
            "Spending can still be analyzed, but account-level activity coverage is incomplete."
        ),
        source="ledger",
        affects_totals=False,
    )


def _collapse_source_rows(
    rows: list[SourceAccountRow],
) -> tuple[dict[str, dict[str, Any]], set[str], list[HouseholdAccountControlIssue]]:
    by_household_account: dict[str, list[SourceAccountRow]] = defaultdict(list)
    issues: list[HouseholdAccountControlIssue] = []
    source_owned_ids: set[str] = set()
    values: dict[str, dict[str, Any]] = {}

    for row in rows:
        if row.household_account_id is None:
            if _is_material(_effective_value(row)):
                issues.append(
                    HouseholdAccountControlIssue(
                        id=_issue_id(
                            "unlinked_source_account",
                            row.source,
                            row.source_account_id,
                        ),
                        code="unlinked_source_account",
                        severity="high",
                        title="Source account has no canonical account",
                        detail=(
                            f"{row.source.title()} account {row.account_label} has a "
                            f"{_effective_value(row)} balance but is not linked to a "
                            "household account."
                        ),
                        account_label=row.account_label,
                        source=row.source,
                        source_account_ids=[row.source_account_id],
                        affects_totals=True,
                    )
                )
            continue
        by_household_account[row.household_account_id].append(row)
        source_owned_ids.add(row.household_account_id)

    for household_account_id, account_rows in by_household_account.items():
        ordered = sorted(
            account_rows,
            key=lambda row: row.last_synced_at or datetime.min.replace(tzinfo=UTC),
        )
        chosen = ordered[-1]
        values[household_account_id] = _source_value(chosen)
        if len(account_rows) <= 1:
            continue

        value_keys = {
            (
                _money_key(row.current_value),
                _money_key(row.cash_balance),
                _normalized(row.currency),
            )
            for row in account_rows
        }
        identity_keys = {
            (
                _normalized(row.source),
                _normalized(row.institution_name),
                _normalized(row.account_label),
                _normalized(row.account_mask),
            )
            for row in account_rows
        }
        source_account_ids = [row.source_account_id for row in ordered]
        if len(value_keys) > 1:
            issues.append(
                HouseholdAccountControlIssue(
                    id=_issue_id("source_value_conflict", household_account_id),
                    code="source_value_conflict",
                    severity="high",
                    title="Source balances conflict",
                    detail=(
                        f"{chosen.account_label} has {len(account_rows)} source rows "
                        "with different balances. Totals use the latest row but need "
                        "reconciliation before they should be trusted."
                    ),
                    household_account_id=household_account_id,
                    account_label=chosen.account_label,
                    source="source_accounts",
                    source_account_ids=source_account_ids,
                    affects_totals=True,
                )
            )
        elif len(identity_keys) > 1:
            issues.append(
                HouseholdAccountControlIssue(
                    id=_issue_id("source_identity_collision", household_account_id),
                    code="source_identity_collision",
                    severity="high",
                    title="Different source accounts map to one canonical account",
                    detail=(
                        f"{chosen.account_label} has {len(account_rows)} source rows "
                        "with different source identities. Totals use one valuation, "
                        "but the account mapping must be reviewed."
                    ),
                    household_account_id=household_account_id,
                    account_label=chosen.account_label,
                    source="source_accounts",
                    source_account_ids=source_account_ids,
                    affects_totals=True,
                )
            )
        else:
            issues.append(
                HouseholdAccountControlIssue(
                    id=_issue_id("duplicate_source_alias", household_account_id),
                    code="duplicate_source_alias",
                    severity="medium",
                    title="Duplicate source aliases collapsed",
                    detail=(
                        f"{chosen.account_label} is represented by {len(account_rows)} "
                        "matching source rows. Totals include the account once, but the "
                        "duplicate connection should be removed or marked inactive."
                    ),
                    household_account_id=household_account_id,
                    account_label=chosen.account_label,
                    source=chosen.source,
                    source_account_ids=source_account_ids,
                    affects_totals=False,
                )
            )

    return values, source_owned_ids, issues


def build_household_account_control(storage: Any) -> HouseholdAccountControlResult:
    values, source_owned_ids, issues = _collapse_source_rows(_source_rows(storage))
    issues.extend(_unlinked_value_evidence_issues(storage))
    transaction_issue = _transaction_suspense_issue(storage)
    if transaction_issue is not None:
        issues.append(transaction_issue)

    blocking_count = sum(1 for issue in issues if issue.affects_totals)
    status = "blocked" if blocking_count else "review" if issues else "clear"
    if status == "clear":
        summary = "Account source controls are clear."
    elif status == "blocked":
        summary = (
            f"{blocking_count} account control issue"
            f"{'' if blocking_count == 1 else 's'} block trusted totals."
        )
    else:
        summary = (
            f"{len(issues)} account control review item"
            f"{'' if len(issues) == 1 else 's'} found; totals are not double-counting them."
        )
    control = HouseholdAccountControl(
        status=status,
        summary=summary,
        issue_count=len(issues),
        blocking_issue_count=blocking_count,
        checked_at=datetime.now(UTC).isoformat(),
        issues=issues,
    )
    return HouseholdAccountControlResult(
        control=control,
        source_owned_household_account_ids=source_owned_ids,
        source_owned_account_values=values,
    )


def apply_account_control_to_summaries(
    account_summaries: list[HouseholdAccountSummary],
    account_control: HouseholdAccountControl,
) -> list[HouseholdAccountSummary]:
    if not account_control.issues:
        return account_summaries
    issues_by_account: dict[str, list[HouseholdAccountControlIssue]] = defaultdict(list)
    for issue in account_control.issues:
        if issue.household_account_id:
            issues_by_account[issue.household_account_id].append(issue)
    if not issues_by_account:
        return account_summaries

    updated: list[HouseholdAccountSummary] = []
    for account in account_summaries:
        account_id = account.household_account_id
        account_issues = issues_by_account.get(account_id or "", [])
        if not account_issues:
            updated.append(account)
            continue
        gap_flags = [
            *account.gap_flags,
            *[
                HouseholdAccountGap(
                    code=issue.code,
                    severity=issue.severity,
                    title=issue.title,
                    detail=issue.detail,
                )
                for issue in account_issues
            ],
        ]
        updated.append(account.model_copy(update={"gap_flags": gap_flags}))
    return updated


def account_control_inbox_items(
    account_control: HouseholdAccountControl,
) -> list[HouseholdInboxItem]:
    if not account_control.issues:
        return []
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_issues = sorted(
        account_control.issues,
        key=lambda issue: priority_order.get(issue.severity, 3),
    )
    items: list[HouseholdInboxItem] = []
    for issue in sorted_issues[:3]:
        items.append(
            HouseholdInboxItem(
                id=f"account-control-{issue.id}",
                category="account",
                priority="high" if issue.affects_totals else issue.severity,
                title=issue.title,
                detail=issue.detail,
                action_label="Review accounts",
                action_href="/money?tab=accounts&focus=account-coverage",
                related_account_id=issue.household_account_id,
            )
        )
    return items
