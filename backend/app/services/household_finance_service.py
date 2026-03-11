"""Household finance dashboard and intake service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, cast

from fastapi import UploadFile

from app.logging_config import get_logger
from app.models.household_finance import (
    BudgetReadiness,
    HouseholdActionItem,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdFinanceDashboard,
    HouseholdOpportunity,
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
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services._household_dashboard_builders import (
    estimate_next_commitment_date,
    suggest_category,
    suggest_essentiality,
)
from app.services._household_dashboard_sections import (
    budget_input_status,
    build_opportunities,
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
from app.services.household_profile_service import HouseholdProfileService
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
    "monthly_net_income_target": "Monthly take-home income",
    "monthly_essential_target": "Essential budget",
    "monthly_discretionary_target": "Discretionary budget",
    "monthly_savings_target": "Monthly savings target",
    "target_retirement_age": "Target retirement age",
    "target_retirement_spend": "Target monthly retirement spend",
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
        self.question_command_service = HouseholdQuestionCommandService()
        self.transaction_rule_service = HouseholdTransactionRuleService()

    def _dashboard_builder(self) -> HouseholdDashboardComposer:
        composer = getattr(self, "dashboard_composer", None)
        if composer is None:
            composer = HouseholdDashboardComposer()
            self.dashboard_composer = composer
        return composer

    def _document_pipeline(self) -> HouseholdDocumentPipeline:
        pipeline = getattr(self, "document_pipeline", None)
        if pipeline is None:
            pipeline = HouseholdDocumentPipeline()
            self.document_pipeline = pipeline
        return pipeline

    def _question_reconciler(self) -> HouseholdQuestionReconciler:
        reconciler = getattr(self, "question_reconciler", None)
        if reconciler is None:
            reconciler = HouseholdQuestionReconciler()
            self.question_reconciler = reconciler
        return reconciler

    def _profile_service(self) -> HouseholdProfileService:
        helper = getattr(self, "profile_service", None)
        if helper is None:
            helper = HouseholdProfileService()
            self.profile_service = helper
        return helper

    def _question_command_service(self) -> HouseholdQuestionCommandService:
        helper = getattr(self, "question_command_service", None)
        if helper is None:
            helper = HouseholdQuestionCommandService()
            self.question_command_service = helper
        return helper

    def _transaction_rule_service(self) -> HouseholdTransactionRuleService:
        helper = getattr(self, "transaction_rule_service", None)
        if helper is None:
            helper = HouseholdTransactionRuleService()
            self.transaction_rule_service = helper
        return helper

    def get_dashboard(self) -> HouseholdFinanceDashboard:
        return self._dashboard_builder().build_dashboard(self)

    def _build_budget_snapshot(
        self,
        *,
        profile: HouseholdProfile,
        reports: Any,
    ) -> HouseholdBudgetSnapshot:
        return self._dashboard_builder().build_budget_snapshot(self, profile=profile, reports=reports)

    def _build_action_items(
        self,
        *,
        questions: list[HouseholdQuestion],
        opportunities: list[HouseholdOpportunity],
        next_best_action: str,
        reports: Any,
        budget_readiness: BudgetReadiness,
        categorization_queue: list[HouseholdCategorizationCandidate] | None = None,
    ) -> list[HouseholdActionItem]:
        return self._dashboard_builder().build_action_items(
            questions=questions,
            opportunities=opportunities,
            next_best_action=next_best_action,
            reports=reports,
            budget_readiness=budget_readiness,
            categorization_queue=categorization_queue,
        )

    def _build_categorization_queue(self, limit: int = 6) -> list[HouseholdCategorizationCandidate]:
        return self._dashboard_builder().build_categorization_queue(self, limit=limit)

    def _build_recurring_commitments(self, limit: int = 6) -> list[HouseholdRecurringCommitment]:
        return self._dashboard_builder().build_recurring_commitments(self, limit=limit)

    def _build_sinking_funds(
        self,
        *,
        recurring_commitments: list[HouseholdRecurringCommitment],
    ) -> list[HouseholdSinkingFund]:
        return self._dashboard_builder().build_sinking_funds(
            recurring_commitments=recurring_commitments
        )

    def _build_retirement_contribution_tracker(
        self,
        *,
        profile: HouseholdProfile,
        estimated_monthly_contributions: float,
    ) -> HouseholdRetirementContributionTracker:
        return self._dashboard_builder().build_retirement_contribution_tracker(
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
        return self._dashboard_builder().build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=target_retirement_spend,
            baseline_monthly_spend=baseline_monthly_spend,
        )

    def _estimate_monthly_retirement_contributions(self) -> float:
        return self._dashboard_builder().estimate_monthly_retirement_contributions(self)

    def _estimate_next_commitment_date(self, last_seen: datetime, cadence: str) -> str | None:
        return estimate_next_commitment_date(last_seen, cadence)

    def _suggest_category(self, merchant: str, description: str) -> str:
        return suggest_category(merchant, description)

    def _suggest_essentiality(self, merchant: str, description: str) -> str:
        return suggest_essentiality(merchant, description)

    def update_transaction_category(
        self,
        transaction_id: str,
        payload: HouseholdTransactionCategoryUpdate,
    ) -> bool:
        return self._transaction_rule_service().update_transaction_category(
            self,
            transaction_id,
            payload,
        )

    def _current_month_spend(self) -> float:
        return self._dashboard_builder().current_month_spend(self)

    def get_profile(self) -> HouseholdProfile:
        return self._profile_service().get_profile(self)

    def update_profile(self, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        return self._profile_service().update_profile(self, payload)

    def list_questions(self, limit: int = 20) -> HouseholdQuestionList:
        self._reconcile_open_questions()
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.created_at, q.answered_at,
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
        self._question_reconciler().reconcile_open_questions(self)

    def answer_question(self, question_id: str, payload: HouseholdQuestionAnswer) -> HouseholdQuestion | None:
        return self._question_command_service().answer_question(self, question_id, payload)

    async def ingest_document(
        self,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
    ) -> HouseholdDocument:
        return await self._document_pipeline().ingest_document(
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
                    field_name, value_text, confidence, status, rationale, source_document_id
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
            }
            for row in rows
        }

    def _get_question_row(self, question_id: str) -> tuple[Any, ...] | None:
        with self.storage.connection() as conn:
            return conn.execute(
                """
                SELECT
                    q.id, q.field_name, q.status, q.priority, q.question, q.rationale,
                    q.answer_text, q.source_document_id, q.metadata, q.created_at, q.answered_at,
                    d.filename, d.source_type, d.document_type, d.account_label, d.review_summary, d.metadata
                FROM household_questions q
                LEFT JOIN household_documents d ON d.id = q.source_document_id
                WHERE q.id = %s
                """,
                [question_id],
            ).fetchone()

    def _find_duplicate_document_by_hash(self, content_sha256: str) -> HouseholdDocument | None:
        return self._document_pipeline().find_duplicate_document_by_hash(self, content_sha256)

    def _get_profile_row(self) -> tuple[Any, ...] | None:
        with self.storage.connection() as conn:
            return conn.execute(
                """
                SELECT
                    id, household_name, monthly_net_income_target,
                    monthly_essential_target, monthly_discretionary_target,
                    monthly_savings_target, target_retirement_age,
                    target_retirement_spend, notes, created_at, updated_at
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

    def _build_opportunities(
        self,
        *,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
        taxable_assets: float,
        retirement_assets: float,
    ) -> list[HouseholdOpportunity]:
        return build_opportunities(
            resolved_numeric_value=lambda field_name: self._resolved_numeric_value(resolved_values, field_name),
            documents=documents,
            taxable_assets=taxable_assets,
            retirement_assets=retirement_assets,
        )

    def _classify_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        source_type: str | None,
        document_type: str | None,
    ) -> tuple[str, str, float]:
        return self._document_pipeline().classify_document(
            filename=filename,
            content_type=content_type,
            source_type=source_type,
            document_type=document_type,
        )

    def review_document(self, document_id: str) -> None:
        self._document_pipeline().review_document(self, document_id)

    def _process_document_review(self, document: HouseholdDocument) -> None:
        self._document_pipeline().process_document_review(self, document)

    def _resolve_related_open_questions(
        self,
        *,
        conn: Any,
        question: HouseholdQuestion,
        answer_text: str,
        answered_at: str,
    ) -> None:
        self._question_reconciler().resolve_related_open_questions(
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
        return self._question_reconciler().question_is_answered_by_context(
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
        return self._question_reconciler().questions_are_semantic_duplicates(first, second)

    def _question_sort_key(self, question: HouseholdQuestion) -> tuple[int, str]:
        return self._question_reconciler().question_sort_key(question)

    def _questions_share_source_context(
        self,
        first: HouseholdQuestion,
        second: HouseholdQuestion,
    ) -> bool:
        return self._question_reconciler().questions_share_source_context(first, second)

    def _question_family(self, question_text: str, field_name: str | None) -> str:
        return self._question_reconciler().question_family(question_text, field_name)

    def _infer_question_resolution_from_existing_context(
        self,
        *,
        conn: Any,
        question: HouseholdQuestion,
    ) -> dict[str, object] | None:
        return self._question_reconciler().infer_question_resolution_from_existing_context(
            self,
            conn=conn,
            question=question,
        )

    def _clean_source_value(self, value: object) -> str | None:
        return self._question_reconciler().clean_source_value(value)

    def _upsert_document_signatures(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        self._document_pipeline().upsert_document_signatures(self, document=document, reviewed=reviewed)

    def _import_document_rows(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        self._document_pipeline().import_document_rows(self, document=document, reviewed=reviewed)

    def _detect_import_dataset(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> str | None:
        return self._document_pipeline().detect_import_dataset(document=document, reviewed=reviewed)

    def _build_import_row_hash(
        self,
        *,
        dataset_type: str,
        row: dict[str, str | None],
    ) -> str | None:
        return self._document_pipeline().build_import_row_hash(dataset_type=dataset_type, row=row)

    def _parse_row_date(self, value: str | None) -> str | None:
        return self._document_pipeline().parse_row_date(value)

    def _parse_decimal(self, value: str | None) -> str | None:
        return self._document_pipeline().parse_decimal(value)

    def _apply_answer_to_profile(self, question: HouseholdQuestion, answer_text: str) -> None:
        self._question_reconciler().apply_answer_to_profile(self, question, answer_text)

    def _parse_answer_value(self, field_name: str, answer_text: str) -> float | int | None:
        return self._question_reconciler().parse_answer_value(field_name, answer_text)

    def _normalize_priority(self, value: Any) -> str:
        priority = str(value or "medium").strip().lower()
        if priority not in {"high", "medium", "low"}:
            return "medium"
        return priority

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
