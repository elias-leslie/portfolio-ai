"""Constants, schemas, and system prompts for Jenny conversation service."""

from __future__ import annotations

import re
from pathlib import Path

from app.utils.project_paths import resolve_project_root

# ── Symbol detection ──────────────────────────────────────────────────────────
SYMBOL_TOKEN_PATTERN = re.compile(r"\b[A-Za-z]{1,5}\b")
SYMBOL_STOPWORDS = frozenset(
    {
        "A",
        "AN",
        "AND",
        "ARE",
        "AT",
        "FOR",
        "FROM",
        "HOW",
        "IRA",
        "HSA",
        "IN",
        "IS",
        "IT",
        "MY",
        "OF",
        "ON",
        "OR",
        "OUR",
        "ROTH",
        "THE",
        "TO",
        "WE",
        "WHAT",
        "WITH",
    }
)

# ── Context limits ─────────────────────────────────────────────────────────────
MAX_CONTEXT_SYMBOLS = 3
MAX_PORTFOLIO_POSITIONS = 12
MAX_RECENT_DOCUMENTS = 6
MAX_RECENT_ROUTINES = 3
MAX_OPEN_NOTIFICATIONS = 5

# ── File paths ─────────────────────────────────────────────────────────────────
PROJECT_ROOT = resolve_project_root(Path(__file__).resolve())
PROJECT_INDEX_PATH = PROJECT_ROOT / ".index.yaml"

# ── Behavioral identifiers ─────────────────────────────────────────────────────
STATUS_OPEN = "open"
DIRECTION_JENNY_TO_USER = "jenny_to_user"
PROVENANCE_JENNY_CHAT = "jenny_chat"
PURPOSE_CHAT = "portfolio_jenny_chat"
PURPOSE_RECONCILE = "portfolio_jenny_reconcile"
PURPOSE_PLANNING_EXTRACT = "portfolio_jenny_planning_extract"

# ── System prompts ─────────────────────────────────────────────────────────────
SYSTEM_CHAT = (
    "You are Jenny inside Portfolio-AI. Help with household planning, retirement, "
    "portfolio accounts, held positions, symbol questions, uploads, routines, status, and any "
    "Portfolio-AI workflow or product context. "
    "Use the supplied context as your live source of truth. If the user asks for data that is not "
    "present in the supplied context, say what is missing instead of inventing it. "
    "If the user appears to have answered one of Jenny's open household questions, acknowledge it naturally. "
    "Be proactive about diagnosis and the next best corrective step, but do not claim a mutation, ingest, "
    "or workflow side effect unless the supplied context proves it."
)
SYSTEM_RECONCILE = (
    "Return JSON only. Extract only confident answers that the user's message directly supports."
)
SYSTEM_PLANNING_EXTRACT = (
    "Return JSON only. Extract only information the user clearly stated and that should update"
    " the household planning record."
)

# ── Response schemas ───────────────────────────────────────────────────────────
RECONCILIATION_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "answers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_id": {"type": "string"},
                        "answer_text": {"type": "string"},
                    },
                    "required": ["question_id", "answer_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["answers"],
        "additionalProperties": False,
    },
}

PLANNING_UPDATE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "profile_updates": {
            "type": "object",
            "properties": {
                "adult_count": {"type": ["integer", "null"]},
                "dependent_count": {"type": ["integer", "null"]},
                "monthly_net_income_target": {"type": ["number", "null"]},
                "monthly_essential_target": {"type": ["number", "null"]},
                "monthly_discretionary_target": {"type": ["number", "null"]},
                "monthly_savings_target": {"type": ["number", "null"]},
                "target_retirement_age": {"type": ["integer", "null"]},
                "target_retirement_spend": {"type": ["number", "null"]},
                "filing_status": {"type": ["string", "null"]},
                "state_of_residence": {"type": ["string", "null"]},
                "effective_tax_rate": {"type": ["number", "null"]},
                "marginal_federal_tax_rate": {"type": ["number", "null"]},
                "marginal_state_tax_rate": {"type": ["number", "null"]},
                "emergency_fund_target_months": {"type": ["number", "null"]},
                "emergency_fund_target_amount": {"type": ["number", "null"]},
            },
            "additionalProperties": False,
        },
        "planning_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "label": {"type": "string"},
                    "role": {"type": ["string", "null"]},
                    "relationship": {"type": ["string", "null"]},
                    "owner_name": {"type": ["string", "null"]},
                    "source_type": {"type": ["string", "null"]},
                    "pay_frequency": {"type": ["string", "null"]},
                    "employer_or_source": {"type": ["string", "null"]},
                    "debt_type": {"type": ["string", "null"]},
                    "lender": {"type": ["string", "null"]},
                    "housing_type": {"type": ["string", "null"]},
                    "occupancy_role": {"type": ["string", "null"]},
                    "coverage_type": {"type": ["string", "null"]},
                    "carrier": {"type": ["string", "null"]},
                    "expense_kind": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "monthly_amount": {"type": ["number", "null"]},
                    "annual_amount": {"type": ["number", "null"]},
                    "gross_amount": {"type": ["number", "null"]},
                    "net_amount": {"type": ["number", "null"]},
                    "monthly_payment": {"type": ["number", "null"]},
                    "balance": {"type": ["number", "null"]},
                    "interest_rate": {"type": ["number", "null"]},
                    "premium_monthly": {"type": ["number", "null"]},
                    "coverage_amount": {"type": ["number", "null"]},
                    "deductible": {"type": ["number", "null"]},
                    "target_amount": {"type": ["number", "null"]},
                    "target_date": {"type": ["string", "null"]},
                    "monthly_saving_target": {"type": ["number", "null"]},
                    "start_age": {"type": ["integer", "null"]},
                    "birth_year": {"type": ["integer", "null"]},
                    "is_dependent": {"type": ["boolean", "null"]},
                    "inflation_adjusted": {"type": ["boolean", "null"]},
                    "survivor_benefit": {"type": ["boolean", "null"]},
                    "notes": {"type": ["string", "null"]},
                    "rationale": {"type": ["string", "null"]},
                },
                "required": ["section", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["profile_updates", "planning_items"],
    "additionalProperties": False,
}
