"""Owner identity and age rules shared by deterministic and sampled paths."""

from __future__ import annotations

import re
from typing import Any

AGE_RESTRICTED_BUCKETS = frozenset({"pre_tax", "governmental_457b", "hsa", "roth"})


def bucket_kind(key: str) -> str:
    return key.split("__", 1)[-1]


def bucket_owner(key: str) -> str:
    return key.split("__", 1)[0] if "__" in key else "primary"


def owned_bucket_key(kind: str, owner: str) -> str:
    return f"{owner}__{kind}" if kind in AGE_RESTRICTED_BUCKETS and owner != "primary" else kind


def owner_age(key: str, primary: int, spouse: int | None, *, rmd: bool = False) -> int:
    owner = bucket_owner(key)
    if owner == "spouse" and spouse is not None:
        return spouse
    if owner == "unknown":
        # Unknown ownership cannot imply either penalty-free early access or
        # the absence of an older person's RMD. The UI flags this assumption.
        return (max if rmd else min)(primary, spouse if spouse is not None else primary)
    return primary


def rmd_start_age(birth_year: int | None) -> float:
    if birth_year is None:
        return 73  # Compatibility for old standalone calls; runtime supplies cohort.
    if birth_year >= 1960:
        return 75
    if birth_year >= 1951:
        return 73  # 1959 follows the IRS proposed clarification; surfaced in assumptions.
    if birth_year >= 1949:
        return 72
    return 70.5


def member_role(member: dict[str, Any]) -> str | None:
    if member.get("is_dependent"):
        return None
    role = str(member.get("role") or "").lower()
    relationship = str(member.get("relationship") or "").lower()
    if role in {"primary", "self", "owner"} or relationship in {
        "father",
        "husband",
        "self",
        "owner",
    }:
        return "primary"
    if role in {"spouse", "partner"} or relationship in {"mother", "wife", "spouse", "partner"}:
        return "spouse"
    return None


def account_owner(name: str | None, members: list[dict[str, Any]]) -> str:
    tokens = re.findall(r"[a-z]+", (name or "").casefold())
    matches = set()
    for member in members:
        role = member_role(member)
        registered = re.findall(r"[a-z]+", str(member.get("display_name") or "").casefold())
        if not role or not tokens or not registered or tokens[0] != registered[0]:
            continue
        if len(tokens) == 1 or len(registered) == 1 or tokens[-1] == registered[-1]:
            matches.add(role)
    return next(iter(matches)) if len(matches) == 1 else "unknown"


def source_account_owners(storage: Any) -> dict[str, str]:
    """Use saved connection ownership only where every active source agrees."""
    with storage.connection() as conn:
        rows=conn.execute("""SELECT sa.household_account_id,c.owner_is_spouse
            FROM snaptrade_accounts sa JOIN snaptrade_connections c USING(authorization_id)
            WHERE sa.is_active=true AND c.is_active=true AND c.disabled=false
              AND sa.household_account_id IS NOT NULL""").fetchall()
    roles: dict[str, set[str]] = {}
    for account_id,is_spouse in rows:
        roles.setdefault(str(account_id),set()).add('spouse' if is_spouse else 'primary')
    return {key:next(iter(value)) if len(value)==1 else 'unknown' for key,value in roles.items()}


def is_education_account(account: Any) -> bool:
    label = ' '.join(str(getattr(account,key,'') or '') for key in ('label','name','account_type'))
    return str(getattr(account,'asset_group','')).lower() == 'education' or bool(re.search(r'\b529\b',label))


def totals_by_bucket(balances: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, amount in balances.items():
        kind = bucket_kind(key)
        result[kind] = result.get(kind, 0) + amount
    return {key: round(value, 2) for key, value in result.items()}


def totals_by_owner(balances: dict[str, float]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for key, amount in balances.items():
        if amount <= 0.005:
            continue
        kind = bucket_kind(key)
        owner = bucket_owner(key) if kind in AGE_RESTRICTED_BUCKETS else "shared"
        result.setdefault(owner, {})[kind] = round(amount, 2)
    return result


def withdrawal_owner_context(
    inputs: Any, year_index: int, prior_balances: dict[str, float]
) -> dict[str, Any]:
    """The same cohort, owner, and prior-year snapshot for both execution paths."""
    retirements = {"primary": inputs.retirement_age}
    if inputs.spouse_age is not None:
        retirements["spouse"] = (
            inputs.spouse_retirement_age
            if inputs.spouse_retirement_age is not None
            else inputs.spouse_age + max(0, inputs.retirement_age - inputs.primary_age)
        )
    return {
        "calendar_year": inputs.as_of_date.year + year_index,
        "primary_birth_year": inputs.primary_birth_year
        or inputs.as_of_date.year - inputs.primary_age,
        "spouse_birth_year": inputs.spouse_birth_year
        or (inputs.as_of_date.year - inputs.spouse_age if inputs.spouse_age is not None else None),
        "rmd_balances": prior_balances,
        "owner_retirement_ages": retirements,
    }


def contribution_key(balances: dict[str, float], inputs: Any, year_index: int) -> str:
    """Route savings to a working owner's existing account, else taxable savings."""
    primary_working = inputs.primary_age + year_index < inputs.retirement_age
    spouse_retirement = inputs.spouse_retirement_age
    spouse_working = (
        inputs.spouse_age is not None
        and spouse_retirement is not None
        and inputs.spouse_age + year_index < spouse_retirement
    )
    for owner, working in (("primary", primary_working), ("spouse", spouse_working)):
        if working:
            for kind in ("pre_tax", "governmental_457b", "roth"):
                key = owned_bucket_key(kind, owner)
                if balances.get(key, 0) > 0:
                    return key
    return "taxable"


def before_rmd_age(inputs: Any, year_index: int) -> bool:
    context = withdrawal_owner_context(inputs, year_index, {})
    return all(
        context["calendar_year"] - birth < rmd_start_age(birth)
        for birth in (context["primary_birth_year"], context["spouse_birth_year"])
        if birth is not None
    )
