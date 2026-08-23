"""Reduce a bank-statement line to the business that actually billed the household.

Plaid rows arrive already normalized ("Get Fitness"). Statement rows do not: the
same electricity bill appears as `DIRECT DEBIT DUKEENERGY BILL PAY (Cash)` on one
export and `Dukeenergy Bill Pay 910066616132 Elias B Leslie` on another, so one
biller is counted as two merchants, neither has enough sightings to prove a
cadence, and the recurring detector misses a bill it can see twice a month
(P1-12, and the reason P0-3's real bills were invisible).

What is stripped is bank plumbing, not identity: how the money moved (`DIRECT
DEBIT`), what the transfer was called (`BILL PAY`, `AUTO_PAY`), the reference
number, the account type in brackets, and the account holder's own name trailing
the line. What is left is the counterparty.
"""

from __future__ import annotations

import re

# How the money moved. Always a prefix, never part of the merchant's name.
_MOVEMENT_PREFIXES = (
    "direct debit",
    "direct deposit",
    "recurring transfer to",
    "recurring transfer from",
    "recurring transfer",
    "online transfer to",
    "online transfer from",
    "online transfer",
    "electronic payment",
    "purchase authorized on",
    "check card purchase",
    "pos purchase",
    "pos debit",
    "ach debit",
    "ach credit",
    "preauthorized debit",
    "bill payment",
    "web payment",
)

# What the transfer was called at the far end. Always a suffix.
_SERVICE_SUFFIXES = (
    "bill pay",
    "billpay",
    "bill payment",
    "auto pay",
    "auto_pay",
    "autopay",
    "pcs svc",
    "svc",
    "epay",
    "payment",
    "bill",
    "pay",
)

# Concatenations the statement produced by running two words together. Split
# only when a real word is left in front, so "tmobile" is not cut down to "t".
_SPLITTABLE_SUFFIXES = (
    "communications",
    "bill",
    "utilities",
    "insurance",
    "wireless",
    "electric",
    "financial",
    "pharmacy",
    "energy",
    "medical",
    "dental",
    "health",
    "market",
    "water",
    "waste",
    "gas",
)
_MIN_SPLIT_STEM = 3

_PEER_PAYMENT_PROVIDERS = (
    "venmo",
    "zelle",
    "cash app",
    "cashapp",
    "paypal",
    "apple cash",
)

_ACCOUNT_TYPE_SUFFIX = re.compile(r"\(([^)]*)\)\s*$")
_REFERENCE_TOKEN = re.compile(r"^(?:#|ref|no|x+)?\d[\d\-x]*$", re.IGNORECASE)
# A reference number run onto the end of a word ("CLEA7274525278"). Four digits
# is the shortest run that is a reference rather than part of a trading name.
_TRAILING_REFERENCE = re.compile(r"\d{4,}$")
# Six digits standing alone is where a number stops being part of a trading name
# ("Store #5831") and starts being the bank's reference for the transfer. It has
# to stand alone: a card feed's "Amazon Mktpl 1273750a3" carries a long digit run
# inside an order id, and treating that as a bank reference would strip Amazon of
# its own name.
_STATEMENT_REFERENCE = re.compile(r"(?<!\w)\d{6,}(?!\w)")
_ACCOUNT_TYPE_BRACKET = re.compile(r"\((?:cash|credit|checking|savings)\)\s*$", re.IGNORECASE)


def _tokens(value: str) -> list[str]:
    cleaned = _ACCOUNT_TYPE_SUFFIX.sub(" ", value)
    cleaned = re.sub(r"[^A-Za-z0-9#]+", " ", cleaned)
    tokens: list[str] = []
    for token in cleaned.split():
        stripped = _TRAILING_REFERENCE.sub("", token) if not token.isdigit() else token
        stripped = stripped.strip("#")
        if stripped:
            tokens.append(stripped)
    return tokens


def _strip_movement_prefix(text: str) -> str:
    lowered = text.lower()
    for prefix in _MOVEMENT_PREFIXES:
        if lowered.startswith(f"{prefix} "):
            return text[len(prefix) + 1 :]
    return text


def _strip_service_suffix(text: str) -> str:
    changed = True
    while changed:
        changed = False
        lowered = text.lower()
        for suffix in _SERVICE_SUFFIXES:
            if lowered.endswith(f" {suffix}"):
                text = text[: -(len(suffix) + 1)].strip()
                changed = True
                break
    return text


def _split_run_together(token: str) -> str:
    lowered = token.lower()
    for suffix in _SPLITTABLE_SUFFIXES:
        if (
            lowered.endswith(suffix)
            and len(lowered) > len(suffix) + _MIN_SPLIT_STEM - 1
            and lowered != suffix
        ):
            return f"{lowered[: -len(suffix)]} {suffix}"
    return lowered


def looks_like_statement_line(raw_merchant: str) -> bool:
    """True when a description came from a bank export rather than a card feed.

    Card-feed merchants are already clean, and running them through the stripper
    costs identity: "WM SUPERCENTER #5831" would lose its store and come back as
    "Wm Supercenter". Only lines carrying bank plumbing get rewritten.
    """
    text = (raw_merchant or "").strip()
    if not text:
        return False
    lowered = text.lower()
    # A cheque names a payee only by its number; collapsing every cheque to
    # "Check Paid" would merge unrelated payments into one merchant.
    if lowered.startswith("check paid") or lowered.startswith("check #"):
        return False
    # On a peer payment the counterparty is the person, and the person's name
    # sits after the reference number -- exactly what this stripper throws away.
    # "Venmo Payment 260117 ... Jordan Demo" must not become "Venmo".
    if any(lowered.startswith(provider) for provider in _PEER_PAYMENT_PROVIDERS):
        return False
    if any(lowered.startswith(f"{prefix} ") for prefix in _MOVEMENT_PREFIXES):
        return True
    if _ACCOUNT_TYPE_BRACKET.search(text):
        return True
    return bool(_STATEMENT_REFERENCE.search(text))


def normalize_statement_merchant(raw_merchant: str) -> str | None:
    """Return the biller behind a statement line, or None if none is left.

    Returns None rather than a guess when stripping leaves nothing — a line that
    is entirely bank plumbing names no merchant, and inventing one would merge
    unrelated rows under a shared piece of boilerplate.
    """
    if not looks_like_statement_line(raw_merchant):
        return None
    tokens = _tokens(raw_merchant)
    if not tokens:
        return None

    # The reference number is where the bank's own bookkeeping starts; the
    # account holder's name trails it. Neither identifies the counterparty.
    kept: list[str] = []
    for token in tokens:
        if _REFERENCE_TOKEN.match(token):
            break
        kept.append(token)
    if not kept:
        return None

    # Split run-together words before stripping service words, or a statement
    # that printed "COMMUBILL PAY" keeps a "Bill" the cleaner name does not have,
    # and the two spellings stay two merchants.
    split = " ".join(_split_run_together(part) for part in kept)
    text = _strip_service_suffix(_strip_movement_prefix(split).strip())
    if not text:
        return None
    return " ".join(word.capitalize() for word in text.split())


def statement_merchant_key(raw_merchant: str) -> str | None:
    """A comparable key for the biller, letters and digits only."""
    normalized = normalize_statement_merchant(raw_merchant)
    if normalized is None:
        return None
    key = re.sub(r"[^a-z0-9]+", "", normalized.lower())
    return key or None


# Statements truncate ("Frontier Communi" one month, "Frontier Commubill" the
# next), so two keys are the same biller when one leads the other by this many
# characters. Short keys must match exactly: "walmart" and "walgreens" share
# three characters and are not the same shop.
MIN_SHARED_BILLER_PREFIX = 9


def same_statement_biller(left: str | None, right: str | None) -> bool:
    """True when two statement lines name the same business."""
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    if len(shorter) < MIN_SHARED_BILLER_PREFIX:
        return False
    return shorter[:MIN_SHARED_BILLER_PREFIX] == longer[:MIN_SHARED_BILLER_PREFIX]
