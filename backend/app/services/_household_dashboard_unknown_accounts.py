from __future__ import annotations

import re
from typing import Any

from app.services._household_dashboard_queries_shared import _short_excerpt

_UNKNOWN_ACCOUNT_SQL = """
    SELECT
        t.description,
        t.flow_type,
        COUNT(*) AS occurrence_count
    FROM household_transactions t
    WHERE t.flow_type IN ('transfer_out', 'payment')
      AND t.transaction_date <= CURRENT_DATE
    GROUP BY t.description, t.flow_type
    ORDER BY COUNT(*) DESC, t.description
    LIMIT 500
"""

# The query above finds accounts money was sent *to*. It cannot find an account
# money was spent *from*: a card named only on a receipt never becomes a transfer
# description. Those rows carry an account_label that failed to resolve to a
# registry account, which is the whole signal -- five receipts naming a "Visa
# ending 4635" mean a real card the household uses and the app has never heard of.
# Grouping by the mask is what collapses the merchant's spelling variants
# ("Visa Credit ****4635", "Visa credit ending 4635", "Visa ending 4635") into
# the one account they all describe.
_UNLINKED_ACCOUNT_LABEL_SQL = """
    SELECT
        t.account_label,
        COUNT(*) AS occurrence_count,
        MIN(t.transaction_date)::date AS first_seen,
        MAX(t.transaction_date)::date AS last_seen
    FROM household_transactions t
    WHERE t.household_account_id IS NULL
      AND COALESCE(t.account_label, '') <> ''
      AND t.removed IS NOT TRUE
      AND t.transaction_date <= CURRENT_DATE
    GROUP BY t.account_label
    ORDER BY COUNT(*) DESC, t.account_label
    LIMIT 200
"""

_MASK_PATTERN = re.compile(r"(\d{4})(?!.*\d)")

_KNOWN_INSTITUTIONS = [
    "CHASE", "AMEX", "DISCOVER", "CITI", "CAPITAL ONE", "BANK OF AMERICA",
    "AMERICAN EXPRESS", "WELLS FARGO", "BARCLAYS", "US BANK", "PNC",
    "TD BANK", "NAVY FEDERAL", "USAA", "FIDELITY", "SCHWAB", "VANGUARD",
]

_INSTITUTION_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(inst) for inst in _KNOWN_INSTITUTIONS) + r")"
    r"(?:\s*(?:X+|[*]+)?\s*(\d{4}))?\b",
    re.IGNORECASE,
)

_CREDIT_INSTITUTIONS = {"CHASE", "AMEX", "DISCOVER", "CITI", "CAPITAL ONE", "BARCLAYS"}
_BANK_TOKENS = ("CHECKING", "SAVINGS", "CASH MANAGEMENT")
_DEBT_TOKENS = ("MORTGAGE", "LOAN", "HELOC")


def _canonicalize_institution(description: str, fallback: str) -> str:
    desc_upper = description.upper()
    for known in _KNOWN_INSTITUTIONS:
        if known in desc_upper:
            return known
    return fallback


def _title_account_label(institution: str, partial_account: str) -> str:
    return f"{institution.title()} · …{partial_account}" if partial_account else institution.title()


def _discovered_account_profile(*, institution: str, description: str, flow_type: str) -> tuple[str, str, str, float]:
    normalized = description.upper()
    for token, profile in (
        ("ROTH", ("retirement", "roth", "retirement", 0.82)),
        ("401", ("retirement", "401k", "retirement", 0.82)),
        ("IRA", ("retirement", "ira", "retirement", 0.8)),
        ("HSA", ("retirement", "hsa", "retirement", 0.78)),
        ("529", ("education", "529", "education", 0.8)),
    ):
        if token in normalized:
            return profile
    if any(token in normalized for token in _DEBT_TOKENS):
        return "debt", "loan", "debt", 0.72
    if flow_type == "payment" or institution in _CREDIT_INSTITUTIONS:
        return "credit", "credit_card", "credit_card", 0.76
    if any(token in normalized for token in _BANK_TOKENS):
        return "cash", "checking", "bank", 0.74
    if institution in {"FIDELITY", "SCHWAB", "VANGUARD"}:
        return "taxable", "brokerage", "brokerage", 0.62
    return "other", "other", "other", 0.5


def _discovered_account_detail(*, occurrence_count: int, description: str, asset_group: str) -> str:
    role = "monthly spending" if asset_group in {"cash", "credit", "debt"} else "net worth"
    example = _short_excerpt(description, max_length=120) or description
    suffix = f" Example: {example}." if description else ""
    return (
        f"Seen {occurrence_count} time{'s' if occurrence_count != 1 else ''} in transfer or payment descriptions. "
        f"If this is yours, add it so Jenny can stop treating it as an unknown {role} endpoint."
        f"{suffix}"
    )


def _known_entities(documents: list[Any]) -> tuple[set[str], set[str], dict[str, set[str]]]:
    known_labels: set[str] = set()
    known_hints: set[str] = set()
    known_entities_by_source: dict[str, set[str]] = {}
    for doc in documents:
        doc_source_type = str(getattr(doc, "source_type", "") or "")
        labels = _label_candidates(doc)
        for candidate in labels:
            known_labels.add(candidate)
            if not doc_source_type:
                continue
            source_entities = known_entities_by_source.setdefault(doc_source_type, set())
            source_entities.add(candidate)
            source_entities.update(
                institution_name
                for institution_name in _KNOWN_INSTITUTIONS
                if institution_name in candidate
            )
    return known_labels, known_hints | {label for label in known_labels if label.isdigit()}, known_entities_by_source


def _label_candidates(doc: Any) -> set[str]:
    labels: set[str] = set()
    account_label = getattr(doc, "account_label", None)
    if account_label:
        labels.add(str(account_label).upper())
    meta = getattr(doc, "metadata", {}) or {}
    if not isinstance(meta, dict):
        return labels
    structured = meta.get("structured_data")
    structured_data = structured if isinstance(structured, dict) else {}
    for hint in (meta.get("account_hint", ""), structured_data.get("account_hint", "")):
        if hint:
            labels.add(str(hint).upper())
    for institution in (meta.get("institution", ""), structured_data.get("institution", "")):
        if institution:
            labels.add(str(institution).upper())
    return labels


def _skip_detected_account(
    *,
    institution: str,
    partial_account: str,
    source_type: str,
    known_labels: set[str],
    known_hints: set[str],
    known_entities_by_source: dict[str, set[str]],
) -> bool:
    if institution in known_labels or partial_account in known_hints:
        return True
    known_for_source = known_entities_by_source.get(source_type, set())
    return institution in known_for_source or any(institution in candidate for candidate in known_for_source)


def _update_detected_account(
    detected: dict[str, dict[str, Any]],
    *,
    key: str,
    institution: str,
    partial_account: str,
    occurrence_count: int,
    description: str,
    asset_group: str,
    account_type: str,
    source_type: str,
    confidence: float,
) -> None:
    if key not in detected:
        detected[key] = {
            "institution": institution,
            "partial_account": partial_account,
            "key": key,
            "suggested_label": _title_account_label(institution, partial_account),
            "asset_group": asset_group,
            "account_type": account_type,
            "source_type": source_type,
            "confidence": confidence,
            "occurrence_count": occurrence_count,
            "sample_description": description,
            "detail": _discovered_account_detail(
                occurrence_count=occurrence_count,
                description=description,
                asset_group=asset_group,
            ),
        }
        return
    existing = detected[key]
    existing["occurrence_count"] = int(existing["occurrence_count"]) + occurrence_count
    if len(description) <= len(str(existing.get("sample_description") or "")):
        return
    existing["sample_description"] = description
    existing["detail"] = _discovered_account_detail(
        occurrence_count=int(existing["occurrence_count"]),
        description=description,
        asset_group=str(existing["asset_group"]),
    )


def _detect_unlinked_spending_accounts(
    conn: Any, known_masks: set[str]
) -> list[dict[str, Any]]:
    """Surface accounts the ledger spends from that resolve to no registry row."""
    rows = conn.execute(_UNLINKED_ACCOUNT_LABEL_SQL).fetchall()
    by_mask: dict[str, dict[str, Any]] = {}
    for label, occurrences, first_seen, last_seen in rows:
        text = str(label or "").strip()
        match = _MASK_PATTERN.search(text)
        if not match:
            continue
        mask = match.group(1)
        if mask in known_masks:
            continue
        entry = by_mask.setdefault(
            mask,
            {
                "institution": "",
                "partial_account": mask,
                "key": f"unlinked_{mask}",
                "suggested_label": text,
                "asset_group": "credit" if "credit" in text.lower() else "other",
                "account_type": "credit_card" if "credit" in text.lower() else "other",
                "source_type": "transaction_label",
                "confidence": 0.55,
                "occurrence_count": 0,
                "spellings": set(),
                "first_seen": first_seen,
                "last_seen": last_seen,
            },
        )
        entry["occurrence_count"] = int(entry["occurrence_count"]) + int(occurrences or 0)
        entry["spellings"].add(text)
        if first_seen is not None and (entry["first_seen"] is None or first_seen < entry["first_seen"]):
            entry["first_seen"] = first_seen
        if last_seen is not None and (entry["last_seen"] is None or last_seen > entry["last_seen"]):
            entry["last_seen"] = last_seen

    detected: list[dict[str, Any]] = []
    for mask, entry in by_mask.items():
        spellings = sorted(entry.pop("spellings"))
        seen = (
            f" between {entry['first_seen']} and {entry['last_seen']}"
            if entry["first_seen"] and entry["last_seen"] and entry["first_seen"] != entry["last_seen"]
            else ""
        )
        spelled = (
            f" The source spells it {len(spellings)} different ways: "
            + "; ".join(f"\u201c{name}\u201d" for name in spellings)
            + "."
            if len(spellings) > 1
            else ""
        )
        entry.pop("first_seen", None)
        entry.pop("last_seen", None)
        entry["sample_description"] = spellings[0]
        entry["detail"] = (
            f"{entry['occurrence_count']} transaction"
            f"{'s' if entry['occurrence_count'] != 1 else ''} were spent from an account "
            f"ending {mask}{seen}, and it matches no account on file.{spelled} "
            "Until it is identified these rows sit outside every account total."
        )
        detected.append(entry)
    return detected


def detect_unknown_accounts(storage: Any, documents: list[Any]) -> list[dict[str, Any]]:
    with storage.connection() as conn:
        rows = conn.execute(_UNKNOWN_ACCOUNT_SQL).fetchall()
        known_masks = {
            str(row[0])
            for row in conn.execute(
                "SELECT account_mask FROM household_accounts WHERE account_mask IS NOT NULL"
            ).fetchall()
            if row[0]
        }
        unlinked = _detect_unlinked_spending_accounts(conn, known_masks)
    known_labels, known_hints, known_entities_by_source = _known_entities(documents)
    detected: dict[str, dict[str, Any]] = {}
    for row in rows:
        description = str(row[0] or "")
        match = _INSTITUTION_PATTERN.search(description)
        if not match:
            continue
        institution = _canonicalize_institution(description, match.group(0).split()[0].upper())
        partial_account = match.group(1) or ""
        asset_group, account_type, source_type, confidence = _discovered_account_profile(
            institution=institution,
            description=description,
            flow_type=str(row[1] or ""),
        )
        if _skip_detected_account(
            institution=institution,
            partial_account=partial_account,
            source_type=source_type,
            known_labels=known_labels,
            known_hints=known_hints,
            known_entities_by_source=known_entities_by_source,
        ):
            continue
        _update_detected_account(
            detected,
            key=f"{institution}_{partial_account}" if partial_account else institution,
            institution=institution,
            partial_account=partial_account,
            occurrence_count=int(row[2] or 0),
            description=description,
            asset_group=asset_group,
            account_type=account_type,
            source_type=source_type,
            confidence=confidence,
        )
    return sorted(
        [*detected.values(), *unlinked],
        key=lambda item: (
            -int(item.get("occurrence_count") or 0),
            -float(item.get("confidence") or 0.0),
            str(item.get("suggested_label") or ""),
        ),
    )
