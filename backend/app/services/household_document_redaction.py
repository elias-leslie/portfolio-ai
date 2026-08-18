"""Mask account-shaped and tax-id-shaped numbers before a document leaves the box.

Household documents are reviewed by whichever model the agent ladder picks,
which may be a hosted provider on a free tier whose terms allow training on
submitted content. Nothing downstream of the reviewer needs a full account
number: ``normalize_account_mask`` strips punctuation and
``account_masks_match`` treats a four-digit mask as a suffix match against a
stored full number, so a redacted document still binds to the right account.

Redaction is deliberately narrow. Amounts, dates, quantities and zip codes must
survive intact or the reconciliation gate starts rejecting good documents, so
only runs long enough to be an identifier are touched.
"""

from __future__ import annotations

import re
from typing import Any

_SSN_PLACEHOLDER = "[redacted-ssn]"
_MIN_IDENTIFIER_DIGITS = 9

# 123-45-6789 / 123 45 6789. Dropped whole rather than suffixed: no part of the
# review pipeline consumes a tax id, so there is nothing to preserve.
_SSN = re.compile(r"(?<!\d)\d{3}[- ]\d{2}[- ]\d{4}(?!\d)")

# 1234 5678 9012 3456 / 1234-5678-9012-345. Grouped identifiers are matched
# before bare runs so the separators do not hide the length.
_GROUPED_IDENTIFIER = re.compile(r"(?<![\d-])\d{3,6}(?:[ -]\d{3,6}){2,}(?![\d-])")

# A bare run. The lookbehind for "." keeps the fractional half of a decimal from
# being read as an identifier; a trailing "." is left alone because it is far
# more often sentence punctuation than part of a number.
_BARE_IDENTIFIER = re.compile(r"(?<![\d.])\d{9,}(?!\d)")


def _mask_tail(digits: str) -> str:
    return f"••••{digits[-4:]}"


def _redact_grouped(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < _MIN_IDENTIFIER_DIGITS:
        return match.group(0)
    return _mask_tail(digits)


def redact_sensitive_text(value: str) -> str:
    """Return ``value`` with tax ids dropped and long identifiers masked to last 4."""
    redacted = _SSN.sub(_SSN_PLACEHOLDER, value)
    redacted = _GROUPED_IDENTIFIER.sub(_redact_grouped, redacted)
    return _BARE_IDENTIFIER.sub(lambda m: _mask_tail(m.group(0)), redacted)


def redact_sensitive_value(value: Any) -> Any:
    """Walk a JSON-shaped payload applying :func:`redact_sensitive_text` to strings.

    Bare ``int`` values are covered too: extractors sometimes hand back an
    account number as a number rather than a string, and it would otherwise be
    serialised straight into the prompt.
    """
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        redacted = redact_sensitive_text(str(value))
        return value if redacted == str(value) else redacted
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_sensitive_value(item) for key, item in value.items()}
    return value
