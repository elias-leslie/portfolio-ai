"""Household finance dashboard and intake service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import UploadFile

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdConfirmedFact,
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdFinanceDashboard,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
    HouseholdRecurringCommitment,
    HouseholdResolvedValue,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
    HouseholdTransactionCategoryUpdate,
)
from app.models.household_planning import HouseholdPlanningSnapshot, HouseholdPlanningUpdate
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services._household_dashboard_builders import (
    estimate_next_commitment_date,
    suggest_category,
    suggest_essentiality,
)
from app.services._household_dashboard_sections import (
    budget_input_status,
    compute_visibility_score,
    next_best_action,
    retirement_blockers,
    retirement_next_steps,
    retirement_ready,
    retirement_strengths,
    visibility_label,
)
from app.services.household_dashboard_composer import HouseholdDashboardComposer
from app.services.household_document_pipeline import HouseholdDocumentPipeline
from app.services.household_document_review import HouseholdDocumentReviewService
from app.services.household_finance_rows import (
    row_to_document,
    row_to_question,
)
from app.services.household_planning_service import HouseholdPlanningService
from app.services.household_profile_service import HouseholdProfileService
from app.services.household_question_classifier import (
    clean_source_value as _clean_source_value_fn,
)
from app.services.household_question_classifier import (
    parse_answer_value as _parse_answer_value_fn,
)
from app.services.household_question_classifier import (
    question_family as _question_family_fn,
)
from app.services.household_question_classifier import (
    question_sort_key as _question_sort_key_fn,
)
from app.services.household_question_classifier import (
    questions_share_source_context as _questions_share_source_context_fn,
)
from app.services.household_question_command_service import HouseholdQuestionCommandService
from app.services.household_question_reconciler import HouseholdQuestionReconciler
from app.services.household_review_agent_service import (
    HouseholdReviewAgentService,
)
from app.services.household_transaction_rule_service import HouseholdTransactionRuleService
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import get_storage

RETIREMENT_ACCOUNT_TYPES = {"IRA", "401k", "Roth", "HSA"}
TAXABLE_ACCOUNT_TYPES = {"Taxable"}
DEFAULT_HOUSEHOLD_NAME = "Household"
FIELD_LABELS = {
    "adult_count": "Adults in household",
    "dependent_count": "Dependents",
    "monthly_net_income_target": "Monthly take-home income",
    "monthly_essential_target": "Essential budget",
    "monthly_discretionary_target": "Discretionary budget",
    "monthly_savings_target": "Monthly savings target",
    "target_retirement_age": "Target retirement age",
    "target_retirement_spend": "Target monthly retirement spend",
    "filing_status": "Tax filing status",
    "state_of_residence": "State of residence",
    "effective_tax_rate": "Effective tax rate",
    "marginal_federal_tax_rate": "Federal marginal tax rate",
    "marginal_state_tax_rate": "State marginal tax rate",
    "emergency_fund_target_months": "Emergency fund target months",
    "emergency_fund_target_amount": "Emergency fund target amount",
}
logger = get_logger(__name__)


class HouseholdFinanceService:
    """Build household-finance views and persist intake metadata."""

    RETIREMENT_ACCOUNT_TYPES = RETIREMENT_ACCOUNT_TYPES
    TAXABLE_ACCOUNT_TYPES = TAXABLE_ACCOUNT_TYPES
    FIELD_LABELS = FIELD_LABELS
    logger = logger
    DEFAULT_HOUSEHOLD_NAME = DEFAULT_HOUSEHOLD_NAME

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.review_agent_service = HouseholdReviewAgentService()
        self.review_service = HouseholdDocumentReviewService(
            agent_service=self.review_agent_service
        )
        self.transaction_service = HouseholdTransactionService()
        self.dashboard_composer = HouseholdDashboardComposer()
        self.document_pipeline = HouseholdDocumentPipeline()
        self.question_reconciler = HouseholdQuestionReconciler()
        self.profile_service = HouseholdProfileService()
        self.planning_service = HouseholdPlanningService()
        self.question_command_service = HouseholdQuestionCommandService()
        self.transaction_rule_service = HouseholdTransactionRuleService()


    def get_dashboard(self) -> HouseholdFinanceDashboard:
        return self.dashboard_composer.build_dashboard(self)

    def _build_budget_snapshot(
        self,
        *,
        profile: HouseholdProfile,
        reports: Any,
    ) -> HouseholdBudgetSnapshot:
        return self.dashboard_composer.build_budget_snapshot(self, profile=profile, reports=reports)

    def _build_categorization_queue(self, limit: int = 6) -> list[HouseholdCategorizationCandidate]:
        return self.dashboard_composer.build_categorization_queue(self, limit=limit)

    def _build_recurring_commitments(self, limit: int = 6) -> list[HouseholdRecurringCommitment]:
        return self.dashboard_composer.build_recurring_commitments(self, limit=limit)

    def _build_sinking_funds(
        self,
        *,
        recurring_commitments: list[HouseholdRecurringCommitment],
    ) -> list[HouseholdSinkingFund]:
        return self.dashboard_composer.build_sinking_funds(
            recurring_commitments=recurring_commitments
        )

    def _build_retirement_contribution_tracker(
        self,
        *,
        profile: HouseholdProfile,
        estimated_monthly_contributions: float,
    ) -> HouseholdRetirementContributionTracker:
        return self.dashboard_composer.build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=estimated_monthly_contributions,
        )

    def _build_retirement_scenarios(
        self,
        *,
        retirement_assets: float,
        target_retirement_spend: float | None,
        baseline_monthly_spend: float,
    ) -> list[HouseholdRetirementScenario]:
        return self.dashboard_composer.build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=target_retirement_spend,
            baseline_monthly_spend=baseline_monthly_spend,
        )

    def _estimate_monthly_retirement_contributions(self) -> float:
        return self.dashboard_composer.estimate_monthly_retirement_contributions(self)

    def _estimate_next_commitment_date(self, last_seen: datetime, cadence: str) -> str | None:
        return estimate_next_commitment_date(last_seen, cadence)

    def _suggest_category(self, merchant: str, description: str) -> str:
        return suggest_category(merchant, description)

    def _suggest_essentiality(self, merchant: str, description: str) -> str:
        return suggest_essentiality(merchant, description)

    def list_confirmed_facts(self) -> list[HouseholdConfirmedFact]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT fact_key, fact_value, confirmed_at FROM household_confirmed_facts ORDER BY confirmed_at"
            ).fetchall()
        return [
            HouseholdConfirmedFact(
                fact_key=str(row[0]),
                fact_value=str(row[1]),
                confirmed_at=self._iso(row[2]),
            )
            for row in rows
        ]

    def confirm_fact(self, fact_key: str, fact_value: str) -> HouseholdConfirmedFact:
        now = datetime.now(UTC)
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (fact_key) DO UPDATE
                SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
                """,
                [fact_key, fact_value, now],
            )
            conn.commit()
        return HouseholdConfirmedFact(
            fact_key=fact_key,
            fact_value=fact_value,
            confirmed_at=now.isoformat(),
        )

    def update_transaction_category(
        self,
        transaction_id: str,
        payload: HouseholdTransactionCategoryUpdate,
    ) -> bool:
        return self.transaction_rule_service.update_transaction_category(
            self,
            transaction_id,
            payload,
        )

    def _current_month_spend(self) -> float:
        return self.dashboard_composer.current_month_spend(self)

    def get_profile(self) -> HouseholdProfile:
        return self.profile_service.get_profile(self)

    def update_profile(self, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        return self.profile_service.update_profile(self, payload)

    def get_planning_snapshot(self) -> HouseholdPlanningSnapshot:
        return self.planning_service.get_snapshot(self)

    def update_planning_snapshot(self, payload: HouseholdPlanningUpdate) -> HouseholdPlanningSnapshot:
        return self.planning_service.update_snapshot(self, payload)

    def merge_planning_items(
        self,
        *,
        items: list[dict[str, object]],
        provenance: str,
        source_document_id: str | None = None,
    ) -> None:
        self.planning_service.merge_planning_items(
            self,
            items=items,
            provenance=provenance,
            source_document_id=source_document_id,
        )

    def list_questions(self, limit: int = 20) -> HouseholdQuestionList:
        self._reconcile_open_questions()
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.question_format,
                    q.options, q.direction, q.created_at, q.answered_at,
                    d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
                FROM household_questions q
                LEFT JOIN household_documents d ON d.id = q.source_document_id
                WHERE q.status = 'open'
                ORDER BY
                    CASE q.priority
                        WHEN 'high' THEN 0
                        WHEN 'medium' THEN 1
                        ELSE 2
                    END,
                    q.created_at ASC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return HouseholdQuestionList(
            items=[row_to_question(row, iso=self._iso, iso_or_none=self._iso_or_none) for row in rows]
        )

    def _reconcile_open_questions(self) -> None:
        self.question_reconciler.reconcile_open_questions(self)

    def answer_question(self, question_id: str, payload: HouseholdQuestionAnswer) -> HouseholdQuestion | None:
        return self.question_command_service.answer_question(self, question_id, payload)

    def ask_jenny(self, question_text: str) -> HouseholdQuestion:
        """Create a user-initiated question directed at Jenny."""
        question_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_questions
                    (id, field_name, status, priority, question, rationale,
                     question_format, options, direction, metadata, created_at)
                VALUES (%s, NULL, 'open', 'medium', %s, NULL,
                        'short_text', NULL, 'user_to_jenny', '{}', %s)
                """,
                [question_id, question_text.strip(), now],
            )
            conn.commit()
        return HouseholdQuestion(
            id=question_id,
            field_name=None,
            status="open",
            priority="medium",
            question=question_text.strip(),
            rationale=None,
            recommendation=None,
            answer_text=None,
            source_document_id=None,
            metadata={},
            question_format="short_text",
            options=None,
            direction="user_to_jenny",
            created_at=now,
            answered_at=None,
        )

    async def ingest_document(
        self,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
    ) -> HouseholdDocument:
        return await self.document_pipeline.ingest_document(
            self,
            upload=upload,
            source_type=source_type,
            document_type=document_type,
            account_label=account_label,
        )

    def list_documents(self, limit: int = 20) -> HouseholdDocumentList:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, filename, source_type, document_type, status, account_label,
                    file_size_bytes, content_type, classification_confidence,
                    review_status, review_summary, review_confidence,
                    statement_start, statement_end, uploaded_at, parsed_at, metadata
                FROM household_documents
                ORDER BY uploaded_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return HouseholdDocumentList(
            items=[
                row_to_document(
                    row,
                    to_float=self._to_float,
                    iso=self._iso,
                    iso_or_none=self._iso_or_none,
                )
                for row in rows
            ]
        )

    def get_document(self, document_id: str) -> HouseholdDocument | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, filename, source_type, document_type, status, account_label,
                    file_size_bytes, content_type, classification_confidence,
                    review_status, review_summary, review_confidence,
                    statement_start, statement_end, uploaded_at, parsed_at, metadata
                FROM household_documents
                WHERE id = %s
                """,
                [document_id],
            ).fetchone()
        return (
            row_to_document(
                row,
                to_float=self._to_float,
                iso=self._iso,
                iso_or_none=self._iso_or_none,
            )
            if row is not None
            else None
        )

    def get_resolved_values(
        self,
        *,
        profile: HouseholdProfile,
        questions: list[HouseholdQuestion],
    ) -> list[HouseholdResolvedValue]:
        inferred_map = self._get_inferred_value_rows()
        questions_by_field = {question.field_name: question for question in questions if question.field_name}
        resolved: list[HouseholdResolvedValue] = []

        for field_name, label in FIELD_LABELS.items():
            manual_value = getattr(profile, field_name)
            inferred = inferred_map.get(field_name)
            if manual_value is not None:
                resolved.append(
                    HouseholdResolvedValue(
                        field_name=field_name,
                        label=label,
                        value=str(manual_value),
                        confidence=1.0,
                        status="confirmed",
                        source="manual",
                        rationale="You confirmed or overrode this value directly.",
                    )
                )
                continue

            if inferred is not None:
                resolved.append(
                    HouseholdResolvedValue(
                        field_name=field_name,
                        label=label,
                        value=str(inferred["value"]),
                        confidence=self._to_float(inferred["confidence"]),
                        status=str(inferred["status"]),
                        source="jenny_inference",
                        rationale=str(inferred["rationale"]) if inferred["rationale"] is not None else None,
                        question=questions_by_field.get(field_name).question if field_name in questions_by_field else None,
                    )
                )
                continue

            question = questions_by_field.get(field_name)
            resolved.append(
                HouseholdResolvedValue(
                    field_name=field_name,
                    label=label,
                    value=None,
                    confidence=None,
                    status="missing",
                    source="unknown",
                    rationale=None,
                    question=question.question if question is not None else None,
                )
            )

        return resolved

    def _get_inferred_value_rows(self) -> dict[str, dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT ON (field_name)
                    field_name, value_text, confidence, status, rationale,
                    source_document_id, metadata->>'source' AS inference_source
                FROM household_inferred_values
                ORDER BY field_name, updated_at DESC
                """
            ).fetchall()

        return {
            str(row[0]): {
                "value": row[1],
                "confidence": row[2],
                "status": row[3],
                "rationale": row[4],
                "source_document_id": row[5],
                "source": row[6] if len(row) > 6 else None,
            }
            for row in rows
        }

    def _get_question_row(self, question_id: str) -> tuple[Any, ...] | None:
        with self.storage.connection() as conn:
            return conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.question_format,
                    q.options, q.direction, q.created_at, q.answered_at,
                    d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
                FROM household_questions q
                LEFT JOIN household_documents d ON d.id = q.source_document_id
                WHERE q.id = %s
                """,
                [question_id],
            ).fetchone()

    def _find_duplicate_document_by_hash(self, content_sha256: str) -> HouseholdDocument | None:
        return self.document_pipeline.find_duplicate_document_by_hash(self, content_sha256)

    def _get_profile_row(self) -> tuple[Any, ...] | None:
        with self.storage.connection() as conn:
            return conn.execute(
                """
                SELECT
                    id, household_name, adult_count, dependent_count,
                    monthly_net_income_target, monthly_essential_target,
                    monthly_discretionary_target, monthly_savings_target,
                    target_retirement_age, target_retirement_spend,
                    filing_status, state_of_residence, effective_tax_rate,
                    marginal_federal_tax_rate, marginal_state_tax_rate,
                    emergency_fund_target_months, emergency_fund_target_amount,
                    notes, created_at, updated_at
                FROM household_profiles
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()

    def _fetch_prices(self, positions: list[object]) -> dict[str, object]:
        symbols = sorted({position.symbol for position in positions})
        if not symbols:
            return {}
        return cast(dict[str, object], self.price_fetcher.fetch_price_data(symbols))

    def _calculate_holdings_by_account(
        self,
        positions: list[object],
        price_data: dict[str, object],
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for position in positions:
            price_info = price_data.get(position.symbol)
            current_price = price_info.price if price_info is not None else position.cost_basis
            values[position.account_id] = values.get(position.account_id, 0.0) + (
                position.shares * current_price
            )
        return values

    def _compute_visibility_score(
        self,
        *,
        account_count: int,
        position_count: int,
        cash_reserve: float,
        retirement_assets: float,
        taxable_assets: float,
        resolved_values: list[HouseholdResolvedValue],
        document_count: int,
    ) -> int:
        return compute_visibility_score(
            account_count=account_count,
            position_count=position_count,
            cash_reserve=cash_reserve,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            resolved_numeric_value=lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            document_count=document_count,
        )

    def _visibility_label(self, score: int) -> str:
        return visibility_label(score)

    def _next_best_action(
        self,
        documents: list[HouseholdDocument],
        visibility_score: int,
        *,
        questions: list[HouseholdQuestion],
        resolved_values: list[HouseholdResolvedValue],
    ) -> str:
        return next_best_action(
            documents,
            visibility_score,
            questions=[question.question for question in questions],
            resolved_numeric_value=lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
        )

    def _budget_input_status(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> dict[str, object]:
        return budget_input_status(
            lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            documents,
        )

    def _retirement_ready(self, resolved_values: list[HouseholdResolvedValue], documents: list[HouseholdDocument]) -> bool:
        return retirement_ready(
            lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            documents,
        )

    def _retirement_strengths(
        self,
        retirement_assets: float,
        taxable_assets: float,
        cash_reserve: float,
        resolved_values: list[HouseholdResolvedValue],
    ) -> list[str]:
        return retirement_strengths(
            retirement_assets,
            taxable_assets,
            cash_reserve,
            lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
        )

    def _retirement_blockers(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> list[str]:
        return retirement_blockers(
            lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            documents,
        )

    def _retirement_next_steps(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> list[str]:
        return retirement_next_steps(
            lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            documents,
        )

    def _classify_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        source_type: str | None,
        document_type: str | None,
    ) -> tuple[str, str, float]:
        return self.document_pipeline.classify_document(
            filename=filename,
            content_type=content_type,
            source_type=source_type,
            document_type=document_type,
        )

    def review_document(self, document_id: str) -> None:
        self.document_pipeline.review_document(self, document_id)

    def _process_document_review(self, document: HouseholdDocument) -> None:
        self.document_pipeline.process_document_review(self, document)

    def _resolve_related_open_questions(
        self,
        *,
        conn: Any,
        question: HouseholdQuestion,
        answer_text: str,
        answered_at: str,
    ) -> None:
        self.question_reconciler.resolve_related_open_questions(
            self,
            conn=conn,
            question=question,
            answer_text=answer_text,
            answered_at=answered_at,
        )

    def _question_is_answered_by_context(
        self,
        *,
        answered_question: HouseholdQuestion,
        candidate_question: HouseholdQuestion,
        answer_text: str,
        answered_family: str,
    ) -> bool:
        return self.question_reconciler.question_is_answered_by_context(
            answered_question=answered_question,
            candidate_question=candidate_question,
            answer_text=answer_text,
            answered_family=answered_family,
        )

    def _questions_are_semantic_duplicates(
        self,
        first: HouseholdQuestion,
        second: HouseholdQuestion,
    ) -> bool:
        return self.question_reconciler.questions_are_semantic_duplicates(first, second)

    def _question_sort_key(self, question: HouseholdQuestion) -> tuple[int, str]:
        return _question_sort_key_fn(question)

    def _questions_share_source_context(
        self,
        first: HouseholdQuestion,
        second: HouseholdQuestion,
    ) -> bool:
        return _questions_share_source_context_fn(first, second)

    def _question_family(self, question_text: str, field_name: str | None) -> str:
        return _question_family_fn(question_text, field_name)

    def _infer_question_resolution_from_existing_context(
        self,
        *,
        conn: Any,
        question: HouseholdQuestion,
    ) -> dict[str, object] | None:
        return self.question_reconciler.infer_question_resolution_from_existing_context(
            self,
            conn=conn,
            question=question,
        )

    def _clean_source_value(self, value: object) -> str | None:
        return _clean_source_value_fn(value)

    def _upsert_document_signatures(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        self.document_pipeline.upsert_document_signatures(self, document=document, reviewed=reviewed)

    def _import_document_rows(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        self.document_pipeline.import_document_rows(self, document=document, reviewed=reviewed)

    def _detect_import_dataset(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> str | None:
        return self.document_pipeline.detect_import_dataset(document=document, reviewed=reviewed)

    def _build_import_row_hash(
        self,
        *,
        dataset_type: str,
        row: dict[str, str | None],
    ) -> str | None:
        return self.document_pipeline.build_import_row_hash(dataset_type=dataset_type, row=row)

    def _parse_row_date(self, value: str | None) -> str | None:
        return self.document_pipeline.parse_row_date(value)

    def _parse_decimal(self, value: str | None) -> str | None:
        return self.document_pipeline.parse_decimal(value)

    def _apply_answer_to_profile(self, question: HouseholdQuestion, answer_text: str) -> None:
        self.question_reconciler.apply_answer_to_profile(self, question, answer_text)

    def _parse_answer_value(self, field_name: str, answer_text: str) -> str | float | int | None:
        return _parse_answer_value_fn(field_name, answer_text)

    def _normalize_priority(self, value: Any) -> str:
        priority = str(value or "medium").strip().lower()
        if priority not in {"high", "medium", "low"}:
            return "medium"
        return priority

    def _normalize_question_format(self, value: Any) -> str:
        question_format = str(value or "short_text").strip().lower()
        aliases = {
            "text": "short_text",
            "number": "integer",
            "yes_no": "boolean",
            "multiple_choice": "single_select",
        }
        normalized = aliases.get(question_format, question_format)
        if normalized not in {
            "short_text",
            "long_text",
            "boolean",
            "integer",
            "currency",
            "single_select",
            "multi_select",
            "date",
        }:
            return "short_text"
        return normalized

    def _normalize_question_options(self, value: Any) -> list[str] | None:
        if not isinstance(value, list):
            return None
        options = [str(item).strip() for item in value if str(item).strip()]
        return options or None

    def _normalize_question_direction(self, value: Any) -> str:
        direction = str(value or "jenny_to_user").strip().lower()
        if direction not in {"jenny_to_user", "user_to_jenny"}:
            return "jenny_to_user"
        return direction

    def _resolved_numeric_value(
        self,
        resolved_values: list[HouseholdResolvedValue],
        field_name: str,
    ) -> float | None:
        for value in resolved_values:
            if value.field_name != field_name or value.value is None:
                continue
            try:
                return float(str(value.value).replace(",", ""))
            except ValueError:
                return None
        return None

    def _upload_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "household_uploads"

    def _iso(self, value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _iso_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        return self._iso(value)

    def _to_float(self, value: Any) -> float | None:
        return float(value) if value is not None else None

    def _to_int(self, value: Any) -> int | None:
        return int(value) if value is not None else None
