"""Profile read/write helpers for household finance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import HouseholdProfile, HouseholdProfileUpdate
from app.services._household_finance_utils import iso, to_float, to_int
from app.services.household_finance_rows import row_to_profile

DEFAULT_HOUSEHOLD_NAME = "Household"


class HouseholdProfileService:
    """Load and persist the singleton household profile."""

    def _fetch_profile_row(self, service: Any) -> tuple[Any, ...] | None:
        with service.storage.connection() as conn:
            return conn.execute(
                """
                SELECT id, household_name, adult_count, dependent_count,
                       monthly_net_income_target, monthly_essential_target,
                       monthly_discretionary_target, monthly_savings_target,
                       target_retirement_age, target_retirement_spend,
                       retirement_inflation_rate, retirement_horizon_years,
                       primary_social_security_monthly, spouse_social_security_monthly,
                       primary_social_security_annual_earnings, spouse_social_security_annual_earnings,
                       primary_social_security_start_age, spouse_social_security_start_age,
                       social_security_payable_ratio,
                       filing_status, state_of_residence, effective_tax_rate,
                       marginal_federal_tax_rate, marginal_state_tax_rate,
                       emergency_fund_target_months, emergency_fund_target_amount,
                       notes, created_at, updated_at
                FROM household_profiles ORDER BY created_at ASC LIMIT 1
                """
            ).fetchone()

    def get_profile(self, service: Any) -> HouseholdProfile:
        row = self._fetch_profile_row(service)
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
            row = self._fetch_profile_row(service)
            if row is None:
                raise RuntimeError("Failed to create household profile")
        return row_to_profile(row, to_float=to_float, to_int=to_int, iso=iso)

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
