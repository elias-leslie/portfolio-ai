"""Profile read/write helpers for household finance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdProfile, HouseholdProfileUpdate
from app.services.household_finance_rows import row_to_profile

DEFAULT_HOUSEHOLD_NAME = "Household"


class HouseholdProfileService:
    """Load and persist the singleton household profile."""

    def get_profile(self, service: Any) -> HouseholdProfile:
        row = service._get_profile_row()
        if row is None:
            now = datetime.now(UTC).isoformat()
            profile_id = str(uuid.uuid4())
            with service.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO household_profiles (
                        id, household_name, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    [profile_id, DEFAULT_HOUSEHOLD_NAME, now, now],
                )
                conn.commit()
            row = service._get_profile_row()
            if row is None:
                raise RuntimeError("Failed to create household profile")
        return row_to_profile(row, to_float=service._to_float, to_int=service._to_int, iso=service._iso)

    def update_profile(self, service: Any, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        profile = self.get_profile(service)
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return profile

        set_clauses = ", ".join(f"{field} = %s" for field in updates)
        params: list[Any] = list(updates.values())
        params.extend([datetime.now(UTC).isoformat(), profile.id])

        with service.storage.connection() as conn:
            conn.execute(
                f"""
                UPDATE household_profiles
                SET {set_clauses}, updated_at = %s
                WHERE id = %s
                """,
                params,
            )
            conn.commit()

        return self.get_profile(service)
