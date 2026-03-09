"""Household finance dashboard and intake service."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from csv import DictReader
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import UploadFile

from app.logging_config import get_logger
from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdFinanceDashboard,
    HouseholdOpportunity,
    HouseholdOverview,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdQuestion,
    HouseholdQuestionAnswer,
    HouseholdQuestionList,
    HouseholdResolvedValue,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    RetirementPreparedness,
)
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.household_document_review import HouseholdDocumentReviewService
from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_MEMORY_TAGS,
    HouseholdReviewAgentService,
)
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

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.review_agent_service = HouseholdReviewAgentService()
        self.review_service = HouseholdDocumentReviewService(
            agent_service=self.review_agent_service
        )

    def get_dashboard(self) -> HouseholdFinanceDashboard:
        profile = self.get_profile()
        documents = self.list_documents(limit=12).items
        questions = self.list_questions(limit=12).items
        resolved_values = self.get_resolved_values(profile=profile, questions=questions)
        accounts = [account for account in self.portfolio_mgr.get_accounts() if account.account_type != "paper"]
        positions = self.portfolio_mgr.get_positions()
        account_ids = {account.id for account in accounts}
        live_positions = [position for position in positions if position.account_id in account_ids]
        price_data = self._fetch_prices(live_positions)
        holdings_by_account = self._calculate_holdings_by_account(live_positions, price_data)

        invested_assets = sum(holdings_by_account.values())
        cash_reserve = sum(account.cash_balance for account in accounts)
        retirement_assets = 0.0
        taxable_assets = 0.0

        for account in accounts:
            account_total = account.cash_balance + holdings_by_account.get(account.id, 0.0)
            if account.account_type in RETIREMENT_ACCOUNT_TYPES:
                retirement_assets += account_total
            if account.account_type in TAXABLE_ACCOUNT_TYPES:
                taxable_assets += account_total

        total_tracked_assets = invested_assets + cash_reserve
        visibility_score = self._compute_visibility_score(
            account_count=len(accounts),
            position_count=len(live_positions),
            cash_reserve=cash_reserve,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            resolved_values=resolved_values,
            document_count=len(documents),
        )
        budget_inputs = self._budget_input_status(resolved_values, documents)

        overview = HouseholdOverview(
            invested_assets=invested_assets,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
            visibility_score=visibility_score,
            visibility_label=self._visibility_label(visibility_score),
            next_best_action=self._next_best_action(
                documents,
                visibility_score,
                questions=questions,
                resolved_values=resolved_values,
            ),
        )

        budget_readiness = BudgetReadiness(
            status="ready_for_budgeting" if budget_inputs["budget_ready"] else "setup_needed",
            summary=(
                "Jenny can enforce budget guardrails once household income targets and transaction documents are in place."
                if budget_inputs["budget_ready"]
                else "Budgeting is one step away: define the monthly plan and keep feeding the system statements."
            ),
            priorities=budget_inputs["priorities"],
            missing_inputs=budget_inputs["missing_inputs"],
            starter_lanes=[
                BudgetLane(
                    name="Essentials",
                    objective="Protect fixed bills and groceries before lifestyle spending expands.",
                    status="Configured" if self._resolved_numeric_value(resolved_values, "monthly_essential_target") is not None else "Needs target",
                ),
                BudgetLane(
                    name="Lifestyle",
                    objective="Cap shopping, dining, convenience, and entertainment with clear guardrails.",
                    status="Configured" if self._resolved_numeric_value(resolved_values, "monthly_discretionary_target") is not None else "Needs target",
                ),
                BudgetLane(
                    name="Savings",
                    objective="Reserve dollars for investing, emergency cash, and future big-ticket items.",
                    status="Configured" if self._resolved_numeric_value(resolved_values, "monthly_savings_target") is not None else "Needs target",
                ),
            ],
        )

        retirement_share = (
            (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
        )
        retirement_preparedness = RetirementPreparedness(
            status="scenario_ready" if self._retirement_ready(resolved_values, documents) else "baseline_visible",
            summary=(
                "Retirement planning can move from rough intuition to defensible scenario planning."
                if self._retirement_ready(resolved_values, documents)
                else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
            ),
            retirement_account_share=retirement_share,
            strengths=self._retirement_strengths(retirement_assets, taxable_assets, cash_reserve, resolved_values),
            blockers=self._retirement_blockers(resolved_values, documents),
            next_steps=self._retirement_next_steps(resolved_values, documents),
        )

        import_center = ImportCenter(
            headline="Use statements for coverage, then receipts and invoices for savings intelligence.",
            tracked_documents=len(documents),
            parsed_documents=sum(1 for document in documents if document.status in {"parsed", "needs_review"}),
            suggested_first_uploads=[
                "Checking statements for the last 3 months",
                "Primary household credit-card statements for the last 3 months",
                "Most recent brokerage and retirement statements",
                "Utility, insurance, and mortgage or rent invoices",
            ],
            automations=[
                "Normalize merchants across accounts into one spend ledger.",
                "Detect recurring charges, annual renewals, and price creep.",
                "Reconcile brokerage cash flows, dividends, and fees against account balances.",
            ],
            supported_documents=[
                ImportFormat(
                    label="Bank and credit statements",
                    formats=["PDF", "CSV", "OFX", "QFX"],
                    extracts=["transactions", "merchant names", "statement totals", "fees"],
                ),
                ImportFormat(
                    label="Brokerage and retirement statements",
                    formats=["PDF", "CSV"],
                    extracts=["holdings", "cash flows", "dividends", "contributions", "fees"],
                ),
                ImportFormat(
                    label="Receipts and invoices",
                    formats=["PDF", "PNG", "JPG", "HEIC"],
                    extracts=["merchant", "date", "line items", "subtotal", "tax", "total"],
                ),
            ],
        )

        opportunities = self._build_opportunities(
            resolved_values=resolved_values,
            documents=documents,
            taxable_assets=taxable_assets,
            retirement_assets=retirement_assets,
        )

        jenny_brief = JennyMoneyBrief(
            headline="Jenny should run your household money system, not just your portfolio.",
            body=(
                "The household profile, documents, and investment accounts now share one surface. "
                "That gives Jenny enough structure to coach budgeting, savings, and retirement preparedness off the same data foundation."
            ),
            prompts=[
                "Show me what would break our budget this month.",
                "What retirement assumptions are still missing?",
                "Which uploaded documents still need categorization or review?",
            ],
        )

        return HouseholdFinanceDashboard(
            generated_at=datetime.now(UTC).isoformat(),
            overview=overview,
            profile=profile,
            resolved_values=resolved_values,
            budget_readiness=budget_readiness,
            retirement_preparedness=retirement_preparedness,
            opportunities=opportunities,
            import_center=import_center,
            questions=questions,
            jenny_brief=jenny_brief,
        )

    def get_profile(self) -> HouseholdProfile:
        row = self._get_profile_row()
        if row is None:
            now = datetime.now(UTC).isoformat()
            profile_id = str(uuid.uuid4())
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO household_profiles (
                        id, household_name, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    [profile_id, DEFAULT_HOUSEHOLD_NAME, now, now],
                )
                conn.commit()
            row = self._get_profile_row()
            if row is None:
                raise RuntimeError("Failed to create household profile")
        return self._row_to_profile(row)

    def update_profile(self, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        profile = self.get_profile()
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return profile

        set_clauses = ", ".join(f"{field} = %s" for field in updates)
        params: list[Any] = list(updates.values())
        params.extend([datetime.now(UTC).isoformat(), profile.id])

        with self.storage.connection() as conn:
            conn.execute(
                f"""
                UPDATE household_profiles
                SET {set_clauses}, updated_at = %s
                WHERE id = %s
                """,
                params,
            )
            conn.commit()

        return self.get_profile()

    def list_questions(self, limit: int = 20) -> HouseholdQuestionList:
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
        return HouseholdQuestionList(items=[self._row_to_question(row) for row in rows])

    def answer_question(self, question_id: str, payload: HouseholdQuestionAnswer) -> HouseholdQuestion | None:
        question = self._get_question_row(question_id)
        if question is None:
            return None

        row_question = self._row_to_question(question)
        self._apply_answer_to_profile(row_question, payload.answer_text)

        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_questions
                SET status = 'answered', answer_text = %s, answered_at = %s
                WHERE id = %s
                """,
                [payload.answer_text.strip(), now, question_id],
            )
            if row_question.field_name:
                conn.execute(
                    """
                    UPDATE household_inferred_values
                    SET status = 'confirmed', updated_at = %s
                    WHERE field_name = %s
                    """,
                    [now, row_question.field_name],
                )
            conn.commit()

        self._store_confirmed_question_learning(row_question, payload.answer_text.strip())

        answered = self._get_question_row(question_id)
        return self._row_to_question(answered) if answered is not None else None

    async def ingest_document(
        self,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
    ) -> HouseholdDocument:
        document_id = str(uuid.uuid4())
        filename = upload.filename or f"{document_id}.bin"
        content = await upload.read()
        content_sha256 = hashlib.sha256(content).hexdigest()
        duplicate_document = self._find_duplicate_document_by_hash(content_sha256)
        if duplicate_document is not None:
            duplicate_document.metadata["duplicate_detected"] = True
            duplicate_document.metadata["duplicate_reason"] = "exact_content_match"
            return duplicate_document

        inferred_source, inferred_type, confidence = self._classify_document(
            filename=filename,
            content_type=upload.content_type,
            source_type=source_type,
            document_type=document_type,
        )
        suffix = Path(filename).suffix or ".bin"
        upload_dir = self._upload_root()
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path = upload_dir / f"{document_id}{suffix.lower()}"
        stored_path.write_bytes(content)

        now = datetime.now(UTC).isoformat()
        metadata = {
            "original_filename": filename,
            "stored_path": str(stored_path),
            "content_sha256": content_sha256,
        }

        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_documents (
                    id, filename, stored_path, source_type, document_type, status,
                    account_label, content_type, file_size_bytes, classification_confidence,
                    uploaded_at, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [
                    document_id,
                    filename,
                    str(stored_path),
                    inferred_source,
                    inferred_type,
                    "staged",
                    account_label,
                    upload.content_type,
                    len(content),
                    confidence,
                    now,
                    json.dumps(metadata),
                ],
            )
            conn.commit()

        document = self.get_document(document_id)
        if document is None:
            raise RuntimeError("Failed to persist uploaded document")
        return document

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
        return HouseholdDocumentList(items=[self._row_to_document(row) for row in rows])

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
        return self._row_to_document(row) if row is not None else None

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
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, filename, source_type, document_type, status, account_label,
                    file_size_bytes, content_type, classification_confidence,
                    review_status, review_summary, review_confidence,
                    statement_start, statement_end, uploaded_at, parsed_at, metadata
                FROM household_documents
                WHERE metadata->>'content_sha256' = %s
                ORDER BY uploaded_at DESC
                LIMIT 1
                """,
                [content_sha256],
            ).fetchone()
        return self._row_to_document(row) if row is not None else None

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
        score = 0
        if account_count > 0:
            score += 20
        if position_count > 0:
            score += 20
        if retirement_assets > 0:
            score += 10
        if taxable_assets > 0:
            score += 10
        if cash_reserve > 0:
            score += 10
        if self._resolved_numeric_value(resolved_values, "monthly_net_income_target") is not None:
            score += 10
        if (
            self._resolved_numeric_value(resolved_values, "monthly_essential_target") is not None
            and self._resolved_numeric_value(resolved_values, "monthly_discretionary_target") is not None
        ):
            score += 10
        if (
            self._resolved_numeric_value(resolved_values, "target_retirement_spend") is not None
            and self._resolved_numeric_value(resolved_values, "target_retirement_age") is not None
        ):
            score += 5
        if document_count > 0:
            score += 5
        return score

    def _visibility_label(self, score: int) -> str:
        if score >= 80:
            return "Strong household visibility"
        if score >= 50:
            return "Partial money visibility"
        return "Early household setup"

    def _next_best_action(
        self,
        documents: list[HouseholdDocument],
        visibility_score: int,
        *,
        questions: list[HouseholdQuestion],
        resolved_values: list[HouseholdResolvedValue],
    ) -> str:
        action = "Review this month's pacing and savings opportunities instead of collecting more setup data."
        if questions:
            action = questions[0].question
        elif not documents:
            action = "Upload recent bank and credit-card statements so Jenny can see actual cash flow."
        elif self._resolved_numeric_value(resolved_values, "monthly_net_income_target") is None:
            action = "Jenny still needs enough evidence to infer your monthly take-home income."
        elif (
            self._resolved_numeric_value(resolved_values, "monthly_essential_target") is None
            or self._resolved_numeric_value(resolved_values, "monthly_discretionary_target") is None
        ):
            action = "Jenny still needs enough evidence to infer your spending guardrails."
        elif (
            self._resolved_numeric_value(resolved_values, "target_retirement_spend") is None
            or self._resolved_numeric_value(resolved_values, "target_retirement_age") is None
        ):
            action = "Jenny still needs enough evidence to model retirement readiness."
        elif visibility_score < 80:
            action = "Keep feeding statements and receipts until the full household money picture is visible."
        return action

    def _budget_input_status(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> dict[str, object]:
        missing_inputs: list[str] = []
        priorities: list[str] = []
        if self._resolved_numeric_value(resolved_values, "monthly_net_income_target") is None:
            missing_inputs.append("Monthly income target")
            priorities.append("Upload paystubs, deposit screenshots, or answer Jenny's income question.")
        if self._resolved_numeric_value(resolved_values, "monthly_essential_target") is None:
            missing_inputs.append("Essential spending target")
            priorities.append("Jenny still needs bills and core spending data to infer the essentials budget.")
        if self._resolved_numeric_value(resolved_values, "monthly_discretionary_target") is None:
            missing_inputs.append("Discretionary spending target")
            priorities.append("Feed more card and checking data so Jenny can separate flexible spend from essentials.")
        if not documents:
            missing_inputs.append("Recent statements and receipts")
            priorities.append("Upload the last 90 days of statements to turn targets into monitored reality.")

        return {
            "budget_ready": not missing_inputs,
            "missing_inputs": missing_inputs,
            "priorities": priorities or ["Keep statement imports current so Jenny can monitor pacing and savings."],
        }

    def _retirement_ready(self, resolved_values: list[HouseholdResolvedValue], documents: list[HouseholdDocument]) -> bool:
        return (
            self._resolved_numeric_value(resolved_values, "target_retirement_age") is not None
            and self._resolved_numeric_value(resolved_values, "target_retirement_spend") is not None
            and self._resolved_numeric_value(resolved_values, "monthly_essential_target") is not None
            and bool(documents)
        )

    def _retirement_strengths(
        self,
        retirement_assets: float,
        taxable_assets: float,
        cash_reserve: float,
        resolved_values: list[HouseholdResolvedValue],
    ) -> list[str]:
        strengths: list[str] = []
        if retirement_assets > 0:
            strengths.append("Retirement accounts are already visible in the same system as your portfolio.")
        if taxable_assets > 0:
            strengths.append("Taxable assets are tracked, which helps bridge flexibility before retirement accounts are tapped.")
        if cash_reserve > 0:
            strengths.append("Tracked cash provides a starting point for emergency-fund and withdrawal sequencing analysis.")
        if self._resolved_numeric_value(resolved_values, "target_retirement_age") is not None:
            strengths.append("A target retirement age is saved, so future planning can anchor to a real timeline.")
        if not strengths:
            strengths.append("As soon as assets and targets are tracked here, Jenny can unify investing and retirement planning.")
        return strengths

    def _retirement_blockers(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> list[str]:
        blockers: list[str] = []
        if self._resolved_numeric_value(resolved_values, "target_retirement_age") is None:
            blockers.append("No target retirement age yet.")
        if self._resolved_numeric_value(resolved_values, "target_retirement_spend") is None:
            blockers.append("No target retirement spending figure yet.")
        if self._resolved_numeric_value(resolved_values, "monthly_essential_target") is None:
            blockers.append("Essential spending is not defined, so baseline retirement needs are unclear.")
        if not documents:
            blockers.append("No household statements uploaded yet, so actual spend drift is still invisible.")
        return blockers

    def _retirement_next_steps(
        self,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
    ) -> list[str]:
        next_steps: list[str] = []
        if not documents:
            next_steps.append("Upload recent household statements to establish a spending baseline.")
        if self._resolved_numeric_value(resolved_values, "target_retirement_age") is None:
            next_steps.append("Set the age or date range you want to retire.")
        if self._resolved_numeric_value(resolved_values, "target_retirement_spend") is None:
            next_steps.append("Set a target monthly retirement spending figure.")
        if self._resolved_numeric_value(resolved_values, "monthly_savings_target") is None:
            next_steps.append("Add a monthly savings target so Jenny can monitor whether the plan is being funded.")
        if not next_steps:
            next_steps.append("Start scenario planning: early retirement, higher health costs, and lower-return years.")
        return next_steps

    def _build_opportunities(
        self,
        *,
        resolved_values: list[HouseholdResolvedValue],
        documents: list[HouseholdDocument],
        taxable_assets: float,
        retirement_assets: float,
    ) -> list[HouseholdOpportunity]:
        opportunities: list[HouseholdOpportunity] = []
        if not documents:
            opportunities.append(
                HouseholdOpportunity(
                    title="Build a statement-first data foundation",
                    category="data_foundation",
                    impact="High",
                    detail=(
                        "Bank and card statements unlock real budgeting, recurring-charge detection, "
                        "merchant comparisons, and future card optimization."
                    ),
                    next_step="Import 90 days of checking and primary credit-card statements.",
                )
            )
        if self._resolved_numeric_value(resolved_values, "monthly_essential_target") is None or self._resolved_numeric_value(resolved_values, "monthly_discretionary_target") is None:
            opportunities.append(
                HouseholdOpportunity(
                    title="Turn Jenny into a budget guardrail",
                    category="budget_control",
                    impact="High",
                    detail="Jenny can only alert on overspend pace after she has enough evidence to infer your budget guardrails.",
                    next_step="Keep feeding statements and answer open Jenny questions so she can finalize the budget.",
                )
            )
        if retirement_assets > 0 and self._resolved_numeric_value(resolved_values, "target_retirement_spend") is None:
            opportunities.append(
                HouseholdOpportunity(
                    title="Connect retirement assets to a real spending target",
                    category="retirement",
                    impact="High",
                    detail="Retirement balances are visible, but readiness still depends on what life actually costs.",
                    next_step="Add a target retirement spending figure and keep statements current.",
                )
            )
        if documents and taxable_assets >= 0:
            opportunities.append(
                HouseholdOpportunity(
                    title="Prepare for merchant and rewards optimization",
                    category="savings",
                    impact="Medium",
                    detail="Once spending data is stable, Jenny can start comparing merchants, brands, and card usage.",
                    next_step="Keep uploading statements and receipts so category patterns become trustworthy.",
                )
            )
        return opportunities

    def _classify_document(
        self,
        *,
        filename: str,
        content_type: str | None,
        source_type: str | None,
        document_type: str | None,
    ) -> tuple[str, str, float]:
        if source_type and document_type:
            return source_type, document_type, 0.99

        lowered = filename.lower()
        inferred_source = source_type or "other"
        inferred_type = document_type or "other"
        confidence = 0.55

        if any(token in lowered for token in ["checking", "bank", "statement"]):
            inferred_source = source_type or "bank"
            inferred_type = document_type or "statement"
            confidence = 0.82
        if any(token in lowered for token in ["visa", "mastercard", "amex", "credit"]):
            inferred_source = source_type or "credit_card"
            inferred_type = document_type or "statement"
            confidence = 0.88
        if any(token in lowered for token in ["brokerage", "fidelity", "schwab", "vanguard"]):
            inferred_source = source_type or "brokerage"
            inferred_type = document_type or "brokerage_statement"
            confidence = 0.9
        if any(token in lowered for token in ["ira", "401k", "roth", "retirement"]):
            inferred_source = source_type or "retirement"
            inferred_type = document_type or "retirement_statement"
            confidence = 0.9
        if any(token in lowered for token in ["receipt", "walmart", "target", "costco"]):
            inferred_source = source_type or "receipt"
            inferred_type = document_type or "receipt"
            confidence = 0.8
        if any(token in lowered for token in ["invoice", "bill", "utility", "insurance"]):
            inferred_source = source_type or "billing"
            inferred_type = document_type or "invoice"
            confidence = 0.8
        if content_type and content_type.startswith("image/") and inferred_type == "other":
            inferred_type = "receipt"
            inferred_source = source_type or "receipt"
            confidence = max(confidence, 0.72)

        return inferred_source, inferred_type, confidence

    def review_document(self, document_id: str) -> None:
        document = self.get_document(document_id)
        if document is None:
            logger.warning("household_document_missing_for_review", document_id=document_id)
            return
        try:
            self._process_document_review(document)
        except Exception as exc:
            logger.exception("household_document_review_failed", document_id=document_id, error=str(exc))
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    UPDATE household_documents
                    SET status = 'needs_review',
                        review_status = 'failed',
                        review_summary = %s,
                        parsed_at = %s
                    WHERE id = %s
                    """,
                    [
                        "Jenny could not finish reviewing this document yet. Re-upload or add more context.",
                        datetime.now(UTC).isoformat(),
                        document_id,
                    ],
                )
                conn.commit()

    def _process_document_review(self, document: HouseholdDocument) -> None:
        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return

        now = datetime.now(UTC).isoformat()
        reviewed = self.review_service.review(
            document_id=document.id,
            filename=document.filename,
            stored_path=Path(stored_path),
            content_type=document.content_type,
            source_type=document.source_type,
            document_type=document.document_type,
        )
        review_confidence = self._to_float(reviewed.get("confidence"))
        review_status = "complete" if (review_confidence or 0.0) >= 0.65 else "needs_review"
        document_status = "parsed" if review_status == "complete" else "needs_review"
        structured_data = reviewed.get("structured_data") or {}
        extracted_text = reviewed.get("extracted_text")
        resolved_source_type = str(reviewed.get("source_type") or document.source_type)
        resolved_document_type = str(reviewed.get("document_type") or document.document_type)
        account_hint = structured_data.get("account_hint")

        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_documents
                SET source_type = %s,
                    document_type = %s,
                    status = %s,
                    review_status = %s,
                    review_summary = %s,
                    review_confidence = %s,
                    account_label = COALESCE(%s, account_label),
                    parsed_at = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                [
                    resolved_source_type,
                    resolved_document_type,
                    document_status,
                    review_status,
                    reviewed.get("summary"),
                    review_confidence,
                    str(account_hint) if account_hint is not None else None,
                    now,
                    json.dumps({"structured_data": structured_data}),
                    document.id,
                ],
            )
            conn.execute(
                """
                INSERT INTO household_document_reviews (
                    id, document_id, status, summary, confidence,
                    extracted_text, structured_data, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    document.id,
                    review_status,
                    reviewed.get("summary"),
                    review_confidence,
                    extracted_text,
                    json.dumps(structured_data),
                    now,
                    now,
                ],
            )
            conn.execute(
                """
                UPDATE household_inferred_values
                SET status = CASE
                    WHEN status = 'confirmed' THEN status
                    ELSE 'superseded'
                END,
                    updated_at = %s
                WHERE source_document_id = %s
                """,
                [now, document.id],
            )
            conn.execute(
                """
                UPDATE household_questions
                SET status = CASE
                    WHEN status = 'answered' THEN status
                    ELSE 'dismissed'
                END,
                    answered_at = COALESCE(answered_at, %s)
                WHERE source_document_id = %s
                """,
                [now, document.id],
            )

            for inferred in reviewed.get("inferred_values", []):
                field_name = str(inferred.get("field_name") or "").strip()
                if field_name not in FIELD_LABELS:
                    continue
                conn.execute(
                    """
                    INSERT INTO household_inferred_values (
                        id, field_name, value_text, confidence, status, rationale,
                        source_document_id, metadata, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    [
                        str(uuid.uuid4()),
                        field_name,
                        str(inferred.get("value") or "").strip() or None,
                        self._to_float(inferred.get("confidence")),
                        "inferred",
                        inferred.get("rationale"),
                        document.id,
                        json.dumps({"document_id": document.id}),
                        now,
                        now,
                    ],
                )

            for question in reviewed.get("questions", []):
                prompt = str(question.get("question") or "").strip()
                if not prompt:
                    continue
                field_name = str(question.get("field_name") or "").strip() or None
                conn.execute(
                    """
                    INSERT INTO household_questions (
                        id, field_name, status, priority, question, rationale,
                        source_document_id, metadata, created_at
                    ) VALUES (%s, %s, 'open', %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    [
                        str(uuid.uuid4()),
                        field_name,
                        self._normalize_priority(question.get("priority")),
                        prompt,
                        question.get("rationale"),
                        document.id,
                        json.dumps(
                            {
                                "document_id": document.id,
                                "recommendation": question.get("recommendation"),
                            }
                        ),
                        now,
                    ],
                )

            conn.commit()

        self._store_document_learning(
            document=document,
            reviewed=reviewed,
            review_confidence=review_confidence,
        )
        self._upsert_document_signatures(document=document, reviewed=reviewed)
        self._import_document_rows(document=document, reviewed=reviewed)

    def _row_to_profile(self, row: tuple[Any, ...]) -> HouseholdProfile:
        return HouseholdProfile(
            id=str(row[0]),
            household_name=str(row[1]),
            monthly_net_income_target=self._to_float(row[2]),
            monthly_essential_target=self._to_float(row[3]),
            monthly_discretionary_target=self._to_float(row[4]),
            monthly_savings_target=self._to_float(row[5]),
            target_retirement_age=self._to_int(row[6]),
            target_retirement_spend=self._to_float(row[7]),
            notes=str(row[8]) if row[8] is not None else None,
            created_at=self._iso(row[9]),
            updated_at=self._iso(row[10]),
        )

    def _row_to_question(self, row: tuple[Any, ...]) -> HouseholdQuestion:
        raw_metadata = row[8]
        metadata: dict[str, object]
        if isinstance(raw_metadata, dict):
            metadata = raw_metadata
        elif isinstance(raw_metadata, str) and raw_metadata:
            metadata = json.loads(raw_metadata)
        else:
            metadata = {}
        source_document = self._question_source_document(row)
        if source_document is not None:
            metadata = {
                **metadata,
                "source_document": source_document,
            }
        return HouseholdQuestion(
            id=str(row[0]),
            field_name=str(row[1]) if row[1] is not None else None,
            status=str(row[2]),
            priority=str(row[3]),
            question=str(row[4]),
            rationale=str(row[5]) if row[5] is not None else None,
            recommendation=self._question_recommendation(
                field_name=str(row[1]) if row[1] is not None else None,
                metadata=metadata,
                source_document=source_document,
            ),
            answer_text=str(row[6]) if row[6] is not None else None,
            source_document_id=str(row[7]) if row[7] is not None else None,
            metadata=metadata,
            created_at=self._iso(row[9]),
            answered_at=self._iso_or_none(row[10]),
        )

    def _question_source_document(self, row: tuple[Any, ...]) -> dict[str, object] | None:
        if len(row) < 17 or row[11] is None:
            return None

        raw_document_metadata = row[16]
        document_metadata: dict[str, object]
        if isinstance(raw_document_metadata, dict):
            document_metadata = raw_document_metadata
        elif isinstance(raw_document_metadata, str) and raw_document_metadata:
            document_metadata = json.loads(raw_document_metadata)
        else:
            document_metadata = {}

        structured_data = document_metadata.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}

        merchant = structured_data.get("merchant")
        account_hint = structured_data.get("account_hint")

        return {
            "id": str(row[7]) if row[7] is not None else None,
            "filename": str(row[11]),
            "source_type": str(row[12]) if row[12] is not None else None,
            "document_type": str(row[13]) if row[13] is not None else None,
            "account_label": str(row[14]) if row[14] is not None else None,
            "review_summary": str(row[15]) if row[15] is not None else None,
            "merchant": str(merchant) if isinstance(merchant, str) and merchant else None,
            "account_hint": str(account_hint) if isinstance(account_hint, str) and account_hint else None,
        }

    def _question_recommendation(
        self,
        *,
        field_name: str | None,
        metadata: dict[str, object],
        source_document: dict[str, object] | None,
    ) -> str | None:
        recommendation = (
            "Give Jenny the shortest clarification needed so she can classify the document and continue automatically."
        )
        explicit = metadata.get("recommendation")
        if isinstance(explicit, str) and explicit.strip():
            recommendation = explicit.strip()
        elif field_name == "monthly_essential_target":
            recommendation = (
                "Answer 'yes' if this account is used for regular household bills, groceries, gas, or everyday spending."
            )
        elif field_name == "target_retirement_spend":
            recommendation = (
                "Answer 'yes' if this account should shape retirement readiness and future spending plans."
            )
        elif source_document is not None:
            merchant = source_document.get("merchant")
            account_label = source_document.get("account_label")
            account_hint = source_document.get("account_hint")
            filename = source_document.get("filename")

            if isinstance(merchant, str) and merchant:
                recommendation = (
                    f"Confirm that this is a {merchant} purchase or order and say whether it belongs in your regular household budget."
                )
            elif isinstance(account_label, str) and account_label:
                recommendation = (
                    f"Confirm what '{account_label}' is used for and whether Jenny should treat it as part of your main household plan."
                )
            elif isinstance(account_hint, str) and account_hint:
                recommendation = (
                    f"Confirm whether '{account_hint}' is the right account or institution for this document."
                )
            elif isinstance(filename, str) and filename:
                recommendation = (
                    f"Identify the merchant, institution, or account behind '{filename}' so Jenny can classify it correctly."
                )

        return recommendation

    def _store_confirmed_question_learning(
        self,
        question: HouseholdQuestion,
        answer_text: str,
    ) -> None:
        field_label = FIELD_LABELS.get(question.field_name or "", question.question)
        source_document = question.metadata.get("source_document")
        filename = None
        if isinstance(source_document, dict):
            raw_filename = source_document.get("filename")
            if isinstance(raw_filename, str) and raw_filename:
                filename = raw_filename

        context_parts = ["User confirmed a household finance question."]
        if filename:
            context_parts.append(f"Source document: {filename}.")
        context_parts.append(f"Question: {question.question}")
        context_parts.append(f"Answer: {answer_text}")

        self.review_agent_service.save_learning(
            content=" ".join(context_parts),
            summary=f"Confirmed {field_label}"[:80],
            confidence=95,
            tags=[
                *HOUSEHOLD_REVIEW_MEMORY_TAGS,
                "confirmed-household-fact",
            ],
            context="household_question_confirmation",
        )

    def _store_document_learning(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
        review_confidence: float | None,
    ) -> None:
        confidence = review_confidence or 0.0
        if confidence < 0.8:
            return

        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            return

        merchant = structured_data.get("merchant")
        account_hint = structured_data.get("account_hint")
        statement_period = structured_data.get("statement_period")

        if not any(isinstance(value, str) and value for value in [merchant, account_hint, statement_period]):
            return

        learnings = [
            f"Document pattern for this household: '{document.filename}' classified as {reviewed.get('document_type')} from {reviewed.get('source_type')}."
        ]
        if isinstance(merchant, str) and merchant:
            learnings.append(f"Merchant or provider: {merchant}.")
        if isinstance(account_hint, str) and account_hint:
            learnings.append(f"Account hint: {account_hint}.")
        if isinstance(statement_period, str) and statement_period:
            learnings.append(f"Statement period example: {statement_period}.")
        if reviewed.get("summary"):
            learnings.append(f"Summary: {reviewed['summary']}")

        summary_subject = None
        for candidate in [merchant, account_hint, document.filename]:
            if isinstance(candidate, str) and candidate:
                summary_subject = candidate
                break

        self.review_agent_service.save_learning(
            content=" ".join(learnings),
            summary=f"Pattern {summary_subject or document.id}"[:80],
            confidence=max(75, int(confidence * 100)),
            tags=[
                *HOUSEHOLD_REVIEW_MEMORY_TAGS,
                "document-pattern",
            ],
            context="household_document_review",
        )

    def _upsert_document_signatures(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        extracted_text = reviewed.get("extracted_text")
        if not isinstance(extracted_text, str) or not extracted_text:
            return

        signature_candidates = self.review_service.build_signature_candidates(
            filename=document.filename,
            extracted_text=extracted_text,
        )
        if not signature_candidates:
            return

        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}

        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            for signature_type, signature_key, metadata in signature_candidates:
                conn.execute(
                    """
                    INSERT INTO household_document_signatures (
                        id, signature_key, signature_type, source_type, document_type,
                        merchant, account_hint, confidence, sample_document_id,
                        metadata, match_count, created_at, updated_at, last_seen_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 1, %s, %s, %s)
                    ON CONFLICT (signature_key) DO UPDATE SET
                        source_type = EXCLUDED.source_type,
                        document_type = EXCLUDED.document_type,
                        merchant = COALESCE(EXCLUDED.merchant, household_document_signatures.merchant),
                        account_hint = COALESCE(EXCLUDED.account_hint, household_document_signatures.account_hint),
                        confidence = GREATEST(
                            COALESCE(household_document_signatures.confidence, 0),
                            COALESCE(EXCLUDED.confidence, 0)
                        ),
                        sample_document_id = EXCLUDED.sample_document_id,
                        metadata = household_document_signatures.metadata || EXCLUDED.metadata,
                        match_count = household_document_signatures.match_count + 1,
                        updated_at = EXCLUDED.updated_at,
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    [
                        str(uuid.uuid4()),
                        signature_key,
                        signature_type,
                        str(reviewed.get("source_type") or document.source_type),
                        str(reviewed.get("document_type") or document.document_type),
                        structured_data.get("merchant"),
                        structured_data.get("account_hint"),
                        self._to_float(reviewed.get("confidence")),
                        document.id,
                        json.dumps(metadata),
                        now,
                        now,
                        now,
                    ],
                )
            conn.commit()

    def _import_document_rows(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> None:
        dataset_type = self._detect_import_dataset(document=document, reviewed=reviewed)
        if dataset_type is None:
            return

        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return

        inserted = 0
        duplicates = 0
        now = datetime.now(UTC).isoformat()
        with Path(stored_path).open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = DictReader(handle)
            with self.storage.connection() as conn:
                for row in reader:
                    row_hash = self._build_import_row_hash(dataset_type=dataset_type, row=row)
                    if row_hash is None:
                        continue
                    row_date = self._parse_row_date(row.get("Order Date"))
                    inserted_row = conn.execute(
                        """
                        INSERT INTO household_import_rows (
                            id, document_id, dataset_type, row_hash, external_row_id,
                            row_date, merchant, description, amount, currency, row_metadata,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (row_hash) DO NOTHING
                        RETURNING id
                        """,
                        [
                            str(uuid.uuid4()),
                            document.id,
                            dataset_type,
                            row_hash,
                            row.get("Order ID"),
                            row_date,
                            "Amazon",
                            row.get("ASIN"),
                            None,
                            row.get("Currency"),
                            json.dumps(row),
                            now,
                            now,
                        ],
                    ).fetchone()
                    if inserted_row is not None:
                        inserted += 1
                    else:
                        duplicates += 1

                conn.execute(
                    """
                    UPDATE household_documents
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                    """,
                    [
                        json.dumps(
                            {
                                "import_summary": {
                                    "dataset_type": dataset_type,
                                    "inserted_rows": inserted,
                                    "duplicate_rows": duplicates,
                                }
                            }
                        ),
                        document.id,
                    ],
                )
                conn.commit()

    def _detect_import_dataset(
        self,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, Any],
    ) -> str | None:
        if not document.filename.lower().endswith(".csv"):
            return None
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}
        merchant = structured_data.get("merchant")
        if document.filename.lower() == "order history.csv" and merchant == "Amazon":
            return "amazon_order_history"
        return None

    def _build_import_row_hash(
        self,
        *,
        dataset_type: str,
        row: dict[str, str | None],
    ) -> str | None:
        if dataset_type == "amazon_order_history":
            order_id = (row.get("Order ID") or "").strip()
            asin = (row.get("ASIN") or "").strip()
            order_date = (row.get("Order Date") or "").strip()
            quantity = (row.get("Original Quantity") or "").strip()
            if not order_id or not asin or not order_date:
                return None
            fingerprint = "|".join([dataset_type, order_id, asin, order_date, quantity])
            return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        return None

    def _parse_row_date(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).isoformat()
        except ValueError:
            return None

    def _row_to_document(self, row: tuple[Any, ...]) -> HouseholdDocument:
        raw_metadata = row[16]
        metadata: dict[str, object]
        if isinstance(raw_metadata, dict):
            metadata = raw_metadata
        elif isinstance(raw_metadata, str) and raw_metadata:
            metadata = json.loads(raw_metadata)
        else:
            metadata = {}
        return HouseholdDocument(
            id=str(row[0]),
            filename=str(row[1]),
            source_type=str(row[2]),
            document_type=str(row[3]),
            status=str(row[4]),
            account_label=str(row[5]) if row[5] is not None else None,
            file_size_bytes=int(row[6]),
            content_type=str(row[7]) if row[7] is not None else None,
            classification_confidence=self._to_float(row[8]),
            review_status=str(row[9]) if row[9] is not None else None,
            review_summary=str(row[10]) if row[10] is not None else None,
            review_confidence=self._to_float(row[11]),
            statement_start=self._iso_or_none(row[12]),
            statement_end=self._iso_or_none(row[13]),
            uploaded_at=self._iso(row[14]),
            parsed_at=self._iso_or_none(row[15]),
            metadata=metadata,
        )

    def _apply_answer_to_profile(self, question: HouseholdQuestion, answer_text: str) -> None:
        cleaned_answer = answer_text.strip()
        if not cleaned_answer:
            return

        parsed_value = None
        updates: dict[str, Any] = {}
        if question.field_name in FIELD_LABELS:
            parsed_value = self._parse_answer_value(question.field_name, cleaned_answer)
            if parsed_value is not None:
                updates[question.field_name] = parsed_value

        if not updates:
            return

        now = datetime.now(UTC).isoformat()
        profile = self.get_profile()
        set_clauses = ", ".join(f"{field} = %s" for field in updates)
        params: list[Any] = list(updates.values())
        params.extend([now, profile.id])
        with self.storage.connection() as conn:
            conn.execute(
                f"""
                UPDATE household_profiles
                SET {set_clauses}, updated_at = %s
                WHERE id = %s
                """,
                params,
            )
            if question.field_name:
                conn.execute(
                    """
                    UPDATE household_inferred_values
                    SET value_text = %s,
                        status = 'confirmed',
                        updated_at = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE field_name = %s
                    """,
                    [
                        str(parsed_value),
                        now,
                        json.dumps({"confirmed_by_question_id": question.id}),
                        question.field_name,
                    ],
                )
            conn.commit()

    def _parse_answer_value(self, field_name: str, answer_text: str) -> float | int | None:
        normalized = answer_text.replace(",", "").replace("$", "").strip().lower()
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if match is None:
            return None
        number = float(match.group(0))
        if field_name == "target_retirement_age":
            return round(number)
        return round(number, 2)

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
