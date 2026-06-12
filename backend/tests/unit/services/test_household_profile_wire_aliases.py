"""Wire-shape regression: es-toolkit snake-cases camelCase keys with a
split at every letter/digit boundary, so the frontend's
``acaPremiumAge21Override`` arrives as ``aca_premium_age_21_override``.
The update model must accept both spellings and keep dumping the field
name (= the DB column) for update_profile's SET clause.
"""

from app.models.household_finance import HouseholdProfileUpdate


def test_profile_update_accepts_wire_split_aca_premium_key() -> None:
    payload = HouseholdProfileUpdate.model_validate(
        {"aca_premium_age_21_override": 450.0}
    )
    assert payload.aca_premium_age21_override == 450.0
    # model_dump must keep the canonical column name for the SQL SET clause.
    assert payload.model_dump(exclude_unset=True) == {
        "aca_premium_age21_override": 450.0
    }


def test_profile_update_accepts_canonical_aca_premium_key() -> None:
    payload = HouseholdProfileUpdate.model_validate(
        {"aca_premium_age21_override": 425.0}
    )
    assert payload.aca_premium_age21_override == 425.0


def test_profile_update_partial_window_keys_are_digit_free_columns() -> None:
    """The partial-retirement levers were named digit-free on purpose, so
    the wire conversion is lossless and model_dump names == DB columns."""
    payload = HouseholdProfileUpdate.model_validate(
        {
            "spouse_net_monthly_income": 5_300.0,
            "partial_retirement_monthly_spend": 7_200.0,
            "spouse_gross_annual_income": 84_000.0,
        }
    )
    assert payload.model_dump(exclude_unset=True) == {
        "spouse_net_monthly_income": 5_300.0,
        "partial_retirement_monthly_spend": 7_200.0,
        "spouse_gross_annual_income": 84_000.0,
    }

    # Explicit nulls clear the columns (feature off).
    cleared = HouseholdProfileUpdate.model_validate(
        {
            "spouse_net_monthly_income": None,
            "partial_retirement_monthly_spend": None,
            "spouse_gross_annual_income": None,
        }
    )
    assert cleared.model_dump(exclude_unset=True) == {
        "spouse_net_monthly_income": None,
        "partial_retirement_monthly_spend": None,
        "spouse_gross_annual_income": None,
    }
