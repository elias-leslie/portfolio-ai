"""Single source of truth for portfolio account types.

Centralizes the AccountType literal, the canonical tuple of valid values,
and tax-treatment helpers used by F1's TransactionLedger and downstream
features (TLH, drift, rebalance, retirement). Anything outside this
module that needs to reason about account-type tax behavior must import
from here, not redefine the literal.
"""

from __future__ import annotations

from typing import Literal

AccountType = Literal["IRA", "Taxable", "401k", "Roth", "HSA", "paper"]

# Canonical ordering used by display surfaces and validation. Treat as
# the authoritative tuple of valid values; do not duplicate elsewhere.
ACCOUNT_TYPES: tuple[AccountType, ...] = (
    "IRA",
    "Taxable",
    "401k",
    "Roth",
    "HSA",
    "paper",
)

# Tax-advantaged accounts shelter realized gains/losses from current
# taxation. TLH/wash-sale logic intentionally treats Roth/IRA/HSA/401k
# as distinct from Taxable because losses inside them have no current
# tax benefit but their *purchases* still trigger wash-sale blocks
# against taxable losses (Rev. Rul. 2008-5).
_TAX_ADVANTAGED: frozenset[str] = frozenset({"IRA", "Roth", "401k", "HSA"})
_TAXABLE: frozenset[str] = frozenset({"Taxable"})
_PAPER: frozenset[str] = frozenset({"paper"})


def is_taxable(account_type: str) -> bool:
    """Return True when realized gains/losses in this account hit the user's tax return."""
    return account_type in _TAXABLE


def is_tax_advantaged(account_type: str) -> bool:
    """Return True for Roth/IRA/HSA/401k — accounts where current-year tax does not apply."""
    return account_type in _TAX_ADVANTAGED


def is_paper(account_type: str) -> bool:
    """Return True for the paper-trading sentinel account type."""
    return account_type in _PAPER
