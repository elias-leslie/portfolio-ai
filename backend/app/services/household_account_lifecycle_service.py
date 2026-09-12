"""User-confirmed closure on the canonical account, preserving its history."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.household_finance import HouseholdTrackedAccountInput
from app.services._household_dashboard_unknown_accounts import detect_unknown_accounts


class AccountClosureRequest(BaseModel):
    kind: Literal["registered", "discovered"]
    id: str = Field(min_length=1, max_length=200)
    closed_date: date | None = None


def record_account_closed(service: Any, request: AccountClosureRequest) -> dict[str, object]:
    if request.closed_date and request.closed_date > date.today():
        raise ValueError("Use the actual closure date, or leave it blank if unknown.")
    account_id = request.id
    if request.kind == "discovered":
        # A retry after the candidate leaves the queue must reuse its account.
        with service.storage.connection() as conn:
            row = conn.execute(
                "SELECT id FROM household_accounts WHERE metadata->>'closure_discovery_key' = %s",
                [request.id],
            ).fetchone()
        if row:
            account_id = str(row[0])
        else:
            documents = service.list_documents(limit=100, refresh_application_state=False).items
            candidate = next((a for a in detect_unknown_accounts(service.storage, documents) if a["key"] == request.id), None)
            if candidate is None:
                raise ValueError("This possible account has changed. Refresh the account list and review it again.")
            account = service.create_tracked_account(HouseholdTrackedAccountInput(
                label=candidate["suggested_label"], asset_group=candidate["asset_group"],
                account_type=candidate["account_type"], source_type=candidate["source_type"],
                institution_name=candidate["institution"] or None,
                account_mask=candidate["partial_account"] or None,
            ))
            if not account.household_account_id:
                raise ValueError("The account could not be linked. Refresh and try again.")
            account_id = account.household_account_id

    with service.storage.connection() as conn:
        result = close_registered_account(conn, account_id=account_id, closed_date=request.closed_date,
            discovery_key=request.id if request.kind == "discovered" else None)
        conn.commit()
    return result


def close_registered_account(conn: Any, *, account_id: str, closed_date: date | None,
                             discovery_key: str | None = None) -> dict[str, object]:
    """Write registry and wallet closure together, in the caller's transaction."""
    if closed_date and closed_date > date.today():
        raise ValueError("Use the actual closure date, or leave it blank if unknown.")
    now = datetime.now(UTC).isoformat()
    metadata: dict[str, object] = {
        "account_status": "closed", "status_confirmed_by": "user",
        "status_confirmed_at": now,
    }
    if closed_date:
        metadata["closed_date"] = closed_date.isoformat()
    if discovery_key:
        metadata["closure_discovery_key"] = discovery_key
    row = conn.execute(
            """UPDATE household_accounts
               SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                   feed_status = 'closed', updated_at = %s
               WHERE id::text = %s RETURNING canonical_label""",
            [json.dumps(metadata), now, account_id],
    ).fetchone()
    if row is None:
        raise ValueError("Account not found. Refresh the account list and try again.")
    # Unknown closure dates stay unknown; no bonus or balance is invented.
    conn.execute(
            """UPDATE household_credit_cards SET status = 'closed', is_primary_active = FALSE,
                   closed_date = COALESCE(%s::date, closed_date), updated_at = %s
               WHERE household_account_id::text = %s""",
        [closed_date, now, account_id],
    )
    return {"account_id": account_id, "label": str(row[0]), "status": "closed"}
