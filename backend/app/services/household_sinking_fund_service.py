"""Per-fund judgements the trailing-spend derivation cannot make itself."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.models.household_finance import HouseholdSinkingFundUpdate
from app.services._household_dashboard_builders import SINKING_FUND_DEFINITIONS


class HouseholdSinkingFundService:
    """Store a declared monthly amount, and whether the biggest row was one-off.

    Nothing here caches the derived figure: it is recomputed from trailing spend
    on every dashboard build, so a fund cannot drift away from the purchases it
    claims to be based on (D18).
    """

    def update_fund(
        self, service: Any, *, fund_key: str, payload: HouseholdSinkingFundUpdate
    ) -> None:
        valid_keys = {definition.key for definition in SINKING_FUND_DEFINITIONS}
        if fund_key not in valid_keys:
            raise ValueError(f"Unknown sinking fund: {fund_key}")

        updates = payload.model_dump(exclude_unset=True)
        override = updates.get("monthly_override")
        # A declared amount is dated on the day it is declared, like the income
        # anchor: an undated figure cannot be told apart from a stale one.
        set_on = (
            date.today().isoformat()
            if "monthly_override" in updates and override is not None
            else None
        )
        now = datetime.now(UTC).isoformat()

        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_sinking_funds (
                    id, fund_key, monthly_override, override_set_on,
                    override_note, drop_largest, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fund_key) DO UPDATE SET
                    monthly_override = CASE
                        WHEN %s THEN EXCLUDED.monthly_override
                        ELSE household_sinking_funds.monthly_override END,
                    override_set_on = CASE
                        WHEN %s THEN EXCLUDED.override_set_on
                        ELSE household_sinking_funds.override_set_on END,
                    override_note = CASE
                        WHEN %s THEN EXCLUDED.override_note
                        ELSE household_sinking_funds.override_note END,
                    drop_largest = CASE
                        WHEN %s THEN EXCLUDED.drop_largest
                        ELSE household_sinking_funds.drop_largest END,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(uuid.uuid4()),
                    fund_key,
                    override,
                    set_on,
                    updates.get("override_note"),
                    bool(updates.get("drop_largest", False)),
                    now,
                    now,
                    "monthly_override" in updates,
                    "monthly_override" in updates,
                    "override_note" in updates,
                    "drop_largest" in updates,
                ],
            )
            conn.commit()
