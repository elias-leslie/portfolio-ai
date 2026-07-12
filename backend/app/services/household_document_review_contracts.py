"""Typed contracts for untrusted document-review output and user decisions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class HouseholdDocumentReviewApplicationError(RuntimeError):
    """Approval paused after its exact decision was durably recorded."""


class HouseholdDocumentReviewChecks(BaseModel):
    """Trust-relevant checks from the reviewer, with extensible diagnostics."""

    model_config = ConfigDict(extra="allow")

    ambiguity_remaining: bool = False
    ambiguity_reason: str | None = None
    expected_account_count: int | None = Field(default=None, ge=0)
    expects_transaction_activity: bool | None = None


class HouseholdDocumentReviewPayload(BaseModel):
    """Strict outer envelope accepted from the document-review agent.

    Nested finance records remain source-specific JSON, but the agent cannot
    invent new top-level actions that an application path might later trust.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source_type: str
    document_type: str
    summary: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extracted_text: str | None = None
    structured_data: dict[str, object] = Field(default_factory=dict)
    inferred_values: list[dict[str, object]] = Field(default_factory=list)
    planning_items: list[dict[str, object]] = Field(default_factory=list)
    questions: list[dict[str, object]] = Field(default_factory=list)
    review_checks: HouseholdDocumentReviewChecks = Field(
        default_factory=HouseholdDocumentReviewChecks
    )
    review_strategy: str = Field(default="unknown", alias="_review_strategy")

    @model_validator(mode="before")
    @classmethod
    def derive_unresolved_question_ambiguity(cls, value: object) -> object:
        """Fail closed when questions exist without an explicit resolution check."""
        if not isinstance(value, dict):
            return value
        questions = value.get("questions")
        if not isinstance(questions, list) or not questions:
            return value
        raw_checks = value.get("review_checks")
        checks = dict(raw_checks) if isinstance(raw_checks, dict) else {}
        if "ambiguity_remaining" in checks:
            return value
        normalized = dict(value)
        checks["ambiguity_remaining"] = True
        checks.setdefault(
            "ambiguity_reason", "The review returned unresolved user questions."
        )
        normalized["review_checks"] = checks
        return normalized


class HouseholdDocumentReviewProposalImpact(BaseModel):
    """Count of one kind of data mutation held for user approval."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["accounts", "transactions", "holdings", "planning", "inferences"]
    label: str
    count: int = Field(ge=1)


class HouseholdDocumentReviewAccountPreview(BaseModel):
    """Redacted account values that will be written from the review."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=160)
    account_suffix: str | None = Field(default=None, pattern=r"^[0-9]{1,4}$")
    balance: Decimal | None = None
    holdings_value: Decimal | None = None
    cash_balance: Decimal | None = None
    currency: str | None = Field(default=None, max_length=12)
    as_of_date: date | None = None


class HouseholdDocumentReviewTransactionPreview(BaseModel):
    """Exact transaction fields visible before the review is approved."""

    model_config = ConfigDict(extra="forbid")

    account_label: str | None = Field(default=None, max_length=160)
    transaction_date: date | None = None
    merchant: str | None = Field(default=None, max_length=300)
    amount: Decimal | None = None
    currency: str | None = Field(default=None, max_length=12)


class HouseholdDocumentReviewHoldingPreview(BaseModel):
    """Exact security fields visible before a holdings snapshot is applied."""

    model_config = ConfigDict(extra="forbid")

    account_label: str | None = Field(default=None, max_length=160)
    symbol: str | None = Field(default=None, max_length=32)
    shares: Decimal | None = None
    value: Decimal | None = None


class HouseholdDocumentReviewFieldPreview(BaseModel):
    """One typed planning or inferred field/value pair."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=200)
    value: JsonValue


class HouseholdDocumentReviewProposalPreview(BaseModel):
    """Typed, redacted representation of every proposed money-data mutation."""

    model_config = ConfigDict(extra="forbid")

    accounts: list[HouseholdDocumentReviewAccountPreview] = Field(default_factory=list)
    transactions: list[HouseholdDocumentReviewTransactionPreview] = Field(
        default_factory=list
    )
    holdings: list[HouseholdDocumentReviewHoldingPreview] = Field(default_factory=list)
    planning: list[HouseholdDocumentReviewFieldPreview] = Field(default_factory=list)
    inferences: list[HouseholdDocumentReviewFieldPreview] = Field(default_factory=list)

    def has_changes(self) -> bool:
        """Return whether the preview contains at least one visible mutation."""
        return any(
            (self.accounts, self.transactions, self.holdings, self.planning, self.inferences)
        )


class HouseholdDocumentReviewProposal(BaseModel):
    """Persisted proposal that binds a visible review to its exact audit row."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    status: Literal["pending"] = "pending"
    review_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    summary: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: str
    document_type: str
    blocker: str
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    preview: HouseholdDocumentReviewProposalPreview
    proposed_changes: list[HouseholdDocumentReviewProposalImpact] = Field(
        default_factory=list
    )


class HouseholdDocumentReviewDecisionRequest(BaseModel):
    """One explicit user decision for one persisted review proposal."""

    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(min_length=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposal_preview: HouseholdDocumentReviewProposalPreview
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)


class HouseholdDocumentReviewDecisionResult(BaseModel):
    """Outcome of claiming and processing a review decision."""

    document_id: str
    review_id: str
    decision: Literal["approve", "reject"]
    status: Literal["applied", "rejected", "failed"]
    application_summary: dict[str, object] | None = None
