"""Household finance dashboard and intake service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

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
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    RetirementPreparedness,
)
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

RETIREMENT_ACCOUNT_TYPES = {"IRA", "401k", "Roth", "HSA"}
TAXABLE_ACCOUNT_TYPES = {"Taxable"}
DEFAULT_HOUSEHOLD_NAME = "Household"


class HouseholdFinanceService:
    """Build household-finance views and persist intake metadata."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)

    def get_dashboard(self) -> HouseholdFinanceDashboard:
        profile = self.get_profile()
        documents = self.list_documents(limit=12).items
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
            profile=profile,
            document_count=len(documents),
        )
        budget_inputs = self._budget_input_status(profile, documents)

        overview = HouseholdOverview(
            invested_assets=invested_assets,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
            visibility_score=visibility_score,
            visibility_label=self._visibility_label(visibility_score),
            next_best_action=self._next_best_action(profile, documents, visibility_score),
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
                    status="Configured" if profile.monthly_essential_target else "Needs target",
                ),
                BudgetLane(
                    name="Lifestyle",
                    objective="Cap shopping, dining, convenience, and entertainment with clear guardrails.",
                    status="Configured" if profile.monthly_discretionary_target else "Needs target",
                ),
                BudgetLane(
                    name="Savings",
                    objective="Reserve dollars for investing, emergency cash, and future big-ticket items.",
                    status="Configured" if profile.monthly_savings_target else "Needs target",
                ),
            ],
        )

        retirement_share = (
            (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
        )
        retirement_preparedness = RetirementPreparedness(
            status="scenario_ready" if self._retirement_ready(profile, documents) else "baseline_visible",
            summary=(
                "Retirement planning can move from rough intuition to defensible scenario planning."
                if self._retirement_ready(profile, documents)
                else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
            ),
            retirement_account_share=retirement_share,
            strengths=self._retirement_strengths(retirement_assets, taxable_assets, cash_reserve, profile),
            blockers=self._retirement_blockers(profile, documents),
            next_steps=self._retirement_next_steps(profile, documents),
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
            profile=profile,
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
            budget_readiness=budget_readiness,
            retirement_preparedness=retirement_preparedness,
            opportunities=opportunities,
            import_center=import_center,
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
        content = await upload.read()
        stored_path.write_bytes(content)

        now = datetime.now(UTC).isoformat()
        metadata = {
            "original_filename": filename,
            "stored_path": str(stored_path),
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
                    statement_start, statement_end, uploaded_at, parsed_at, metadata
                FROM household_documents
                WHERE id = %s
                """,
                [document_id],
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
        return self.price_fetcher.fetch_price_data(symbols) if symbols else {}

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
        profile: HouseholdProfile,
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
        if profile.monthly_net_income_target is not None:
            score += 10
        if profile.monthly_essential_target is not None and profile.monthly_discretionary_target is not None:
            score += 10
        if profile.target_retirement_spend is not None and profile.target_retirement_age is not None:
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
        profile: HouseholdProfile,
        documents: list[HouseholdDocument],
        visibility_score: int,
    ) -> str:
        if not documents:
            return "Upload recent bank and credit-card statements so Jenny can see actual cash flow."
        if profile.monthly_net_income_target is None:
            return "Set a monthly income target so Jenny can compare inflows against spending and savings."
        if profile.monthly_essential_target is None or profile.monthly_discretionary_target is None:
            return "Define essential and discretionary targets so budget pacing alerts mean something."
        if profile.target_retirement_spend is None or profile.target_retirement_age is None:
            return "Add retirement age and spending targets so Jenny can start readiness modeling."
        if visibility_score < 80:
            return "Keep feeding statements and receipts until the full household money picture is visible."
        return "Review this month's pacing and savings opportunities instead of collecting more setup data."

    def _budget_input_status(
        self,
        profile: HouseholdProfile,
        documents: list[HouseholdDocument],
    ) -> dict[str, object]:
        missing_inputs: list[str] = []
        priorities: list[str] = []
        if profile.monthly_net_income_target is None:
            missing_inputs.append("Monthly income target")
            priorities.append("Set one monthly take-home income target for the household.")
        if profile.monthly_essential_target is None:
            missing_inputs.append("Essential spending target")
            priorities.append("Set an essentials budget that covers housing, food, utilities, and debt minimums.")
        if profile.monthly_discretionary_target is None:
            missing_inputs.append("Discretionary spending target")
            priorities.append("Set a flexible-spend cap for shopping, dining, and convenience spending.")
        if not documents:
            missing_inputs.append("Recent statements and receipts")
            priorities.append("Upload the last 90 days of statements to turn targets into monitored reality.")

        return {
            "budget_ready": not missing_inputs,
            "missing_inputs": missing_inputs,
            "priorities": priorities or ["Keep statement imports current so Jenny can monitor pacing and savings."],
        }

    def _retirement_ready(self, profile: HouseholdProfile, documents: list[HouseholdDocument]) -> bool:
        return (
            profile.target_retirement_age is not None
            and profile.target_retirement_spend is not None
            and profile.monthly_essential_target is not None
            and bool(documents)
        )

    def _retirement_strengths(
        self,
        retirement_assets: float,
        taxable_assets: float,
        cash_reserve: float,
        profile: HouseholdProfile,
    ) -> list[str]:
        strengths: list[str] = []
        if retirement_assets > 0:
            strengths.append("Retirement accounts are already visible in the same system as your portfolio.")
        if taxable_assets > 0:
            strengths.append("Taxable assets are tracked, which helps bridge flexibility before retirement accounts are tapped.")
        if cash_reserve > 0:
            strengths.append("Tracked cash provides a starting point for emergency-fund and withdrawal sequencing analysis.")
        if profile.target_retirement_age is not None:
            strengths.append("A target retirement age is saved, so future planning can anchor to a real timeline.")
        if not strengths:
            strengths.append("As soon as assets and targets are tracked here, Jenny can unify investing and retirement planning.")
        return strengths

    def _retirement_blockers(
        self,
        profile: HouseholdProfile,
        documents: list[HouseholdDocument],
    ) -> list[str]:
        blockers: list[str] = []
        if profile.target_retirement_age is None:
            blockers.append("No target retirement age yet.")
        if profile.target_retirement_spend is None:
            blockers.append("No target retirement spending figure yet.")
        if profile.monthly_essential_target is None:
            blockers.append("Essential spending is not defined, so baseline retirement needs are unclear.")
        if not documents:
            blockers.append("No household statements uploaded yet, so actual spend drift is still invisible.")
        return blockers

    def _retirement_next_steps(
        self,
        profile: HouseholdProfile,
        documents: list[HouseholdDocument],
    ) -> list[str]:
        next_steps: list[str] = []
        if not documents:
            next_steps.append("Upload recent household statements to establish a spending baseline.")
        if profile.target_retirement_age is None:
            next_steps.append("Set the age or date range you want to retire.")
        if profile.target_retirement_spend is None:
            next_steps.append("Set a target monthly retirement spending figure.")
        if profile.monthly_savings_target is None:
            next_steps.append("Add a monthly savings target so Jenny can monitor whether the plan is being funded.")
        if not next_steps:
            next_steps.append("Start scenario planning: early retirement, higher health costs, and lower-return years.")
        return next_steps

    def _build_opportunities(
        self,
        *,
        profile: HouseholdProfile,
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
        if profile.monthly_essential_target is None or profile.monthly_discretionary_target is None:
            opportunities.append(
                HouseholdOpportunity(
                    title="Turn Jenny into a budget guardrail",
                    category="budget_control",
                    impact="High",
                    detail="Jenny can only alert on overspend pace after the household budget has real targets.",
                    next_step="Set essential and discretionary monthly targets for the household.",
                )
            )
        if retirement_assets > 0 and profile.target_retirement_spend is None:
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

    def _row_to_document(self, row: tuple[Any, ...]) -> HouseholdDocument:
        raw_metadata = row[13]
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
            statement_start=self._iso_or_none(row[9]),
            statement_end=self._iso_or_none(row[10]),
            uploaded_at=self._iso(row[11]),
            parsed_at=self._iso_or_none(row[12]),
            metadata=metadata,
        )

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
