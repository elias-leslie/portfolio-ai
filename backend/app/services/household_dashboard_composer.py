"""Dashboard composition helpers for household finance views."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.household_finance import (
    BudgetLane,
    BudgetReadiness,
    HouseholdActionItem,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdFinanceDashboard,
    HouseholdOverview,
    HouseholdRecurringCommitment,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    RetirementPreparedness,
)


class HouseholdDashboardComposer:
    """Build the household dashboard from existing service dependencies."""

    def build_dashboard(self, service: Any) -> HouseholdFinanceDashboard:
        profile = service.get_profile()
        documents = service.list_documents(limit=12).items
        questions = service.list_questions(limit=12).items
        resolved_values = service.get_resolved_values(profile=profile, questions=questions)
        accounts = [
            account
            for account in service.portfolio_mgr.get_accounts()
            if account.account_type != "paper"
        ]
        positions = service.portfolio_mgr.get_positions()
        account_ids = {account.id for account in accounts}
        live_positions = [position for position in positions if position.account_id in account_ids]
        price_data = service._fetch_prices(live_positions)
        holdings_by_account = service._calculate_holdings_by_account(live_positions, price_data)

        invested_assets = sum(holdings_by_account.values())
        cash_reserve = sum(account.cash_balance for account in accounts)
        retirement_assets = 0.0
        taxable_assets = 0.0

        for account in accounts:
            account_total = account.cash_balance + holdings_by_account.get(account.id, 0.0)
            if account.account_type in service.RETIREMENT_ACCOUNT_TYPES:
                retirement_assets += account_total
            if account.account_type in service.TAXABLE_ACCOUNT_TYPES:
                taxable_assets += account_total

        total_tracked_assets = invested_assets + cash_reserve
        visibility_score = service._compute_visibility_score(
            account_count=len(accounts),
            position_count=len(live_positions),
            cash_reserve=cash_reserve,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            resolved_values=resolved_values,
            document_count=len(documents),
        )
        budget_inputs = service._budget_input_status(resolved_values, documents)

        overview = HouseholdOverview(
            invested_assets=invested_assets,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
            visibility_score=visibility_score,
            visibility_label=service._visibility_label(visibility_score),
            next_best_action=service._next_best_action(
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
                    status=(
                        "Configured"
                        if service._resolved_numeric_value(
                            resolved_values, "monthly_essential_target"
                        )
                        is not None
                        else "Needs target"
                    ),
                ),
                BudgetLane(
                    name="Lifestyle",
                    objective="Cap shopping, dining, convenience, and entertainment with clear guardrails.",
                    status=(
                        "Configured"
                        if service._resolved_numeric_value(
                            resolved_values, "monthly_discretionary_target"
                        )
                        is not None
                        else "Needs target"
                    ),
                ),
                BudgetLane(
                    name="Savings",
                    objective="Reserve dollars for investing, emergency cash, and future big-ticket items.",
                    status=(
                        "Configured"
                        if service._resolved_numeric_value(
                            resolved_values, "monthly_savings_target"
                        )
                        is not None
                        else "Needs target"
                    ),
                ),
            ],
        )

        retirement_share = (
            (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
        )
        retirement_preparedness = RetirementPreparedness(
            status=(
                "scenario_ready"
                if service._retirement_ready(resolved_values, documents)
                else "baseline_visible"
            ),
            summary=(
                "Retirement planning can move from rough intuition to defensible scenario planning."
                if service._retirement_ready(resolved_values, documents)
                else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
            ),
            retirement_account_share=retirement_share,
            strengths=service._retirement_strengths(
                retirement_assets, taxable_assets, cash_reserve, resolved_values
            ),
            blockers=service._retirement_blockers(resolved_values, documents),
            next_steps=service._retirement_next_steps(resolved_values, documents),
        )

        import_center = ImportCenter(
            headline="Use statements for coverage, then receipts and invoices for savings intelligence.",
            tracked_documents=len(documents),
            parsed_documents=sum(
                1 for document in documents if document.status in {"parsed", "needs_review"}
            ),
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

        opportunities = service._build_opportunities(
            resolved_values=resolved_values,
            documents=documents,
            taxable_assets=taxable_assets,
            retirement_assets=retirement_assets,
        )
        reports = service.transaction_service.build_reports()
        budget_snapshot = self.build_budget_snapshot(service, profile=profile, reports=reports)
        categorization_queue = self.build_categorization_queue(service)
        recurring_commitments = self.build_recurring_commitments(service)
        sinking_funds = self.build_sinking_funds(recurring_commitments=recurring_commitments)
        retirement_contribution_tracker = self.build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=self.estimate_monthly_retirement_contributions(service),
        )
        retirement_scenarios = self.build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        )
        action_items = self.build_action_items(
            questions=questions,
            opportunities=opportunities,
            next_best_action=overview.next_best_action,
            reports=reports,
            budget_readiness=budget_readiness,
            categorization_queue=categorization_queue,
        )

        jenny_brief = JennyMoneyBrief(
            headline="Jenny can now see actual merchant flows, not just document summaries.",
            body=(
                "The household profile, documents, investment accounts, and transaction ledger now share one surface. "
                "That lets Jenny move from document review into real cash-flow analysis, merchant normalization, and budget coaching."
            ),
            prompts=[
                "Show me the executive household cash-flow report.",
                "Which merchants are driving our essentials spend?",
                "Where is our money leaking month to month?",
            ],
        )

        return HouseholdFinanceDashboard(
            generated_at=datetime.now(UTC).isoformat(),
            overview=overview,
            profile=profile,
            resolved_values=resolved_values,
            budget_readiness=budget_readiness,
            budget_snapshot=budget_snapshot,
            retirement_preparedness=retirement_preparedness,
            action_items=action_items,
            opportunities=opportunities,
            reports=reports,
            categorization_queue=categorization_queue,
            recurring_commitments=recurring_commitments,
            sinking_funds=sinking_funds,
            retirement_contribution_tracker=retirement_contribution_tracker,
            retirement_scenarios=retirement_scenarios,
            import_center=import_center,
            questions=questions,
            jenny_brief=jenny_brief,
        )

    def build_budget_snapshot(
        self,
        service: Any,
        *,
        profile: Any,
        reports: Any,
    ) -> HouseholdBudgetSnapshot:
        monthly_plan_total = sum(
            value
            for value in (
                profile.monthly_essential_target,
                profile.monthly_discretionary_target,
                profile.monthly_savings_target,
            )
            if value is not None
        )
        has_plan = any(
            value is not None
            for value in (
                profile.monthly_essential_target,
                profile.monthly_discretionary_target,
                profile.monthly_savings_target,
            )
        )
        remaining_cash_after_plan = (
            profile.monthly_net_income_target - monthly_plan_total
            if profile.monthly_net_income_target is not None and has_plan
            else None
        )
        discretionary_headroom = (
            profile.monthly_discretionary_target - reports.executive.average_monthly_discretionary
            if profile.monthly_discretionary_target is not None
            else None
        )
        month_to_date_spend = self.current_month_spend(service)
        month_to_date_plan = None
        pace_status = "unknown"
        pace_detail = "Jenny needs a monthly plan before it can judge pacing."
        if has_plan and monthly_plan_total is not None:
            today = datetime.now(UTC).date()
            days_in_month = calendar.monthrange(today.year, today.month)[1]
            month_progress = today.day / days_in_month
            month_to_date_plan = round(monthly_plan_total * month_progress, 2)
            pace_delta = month_to_date_spend - month_to_date_plan
            if abs(pace_delta) <= max(month_to_date_plan * 0.05, 100):
                pace_status = "on_track"
                pace_detail = "Month-to-date spend is tracking close to the plan."
            elif pace_delta > 0:
                pace_status = "running_hot"
                pace_detail = (
                    f"Month-to-date spend is ahead of plan by ${pace_delta:,.0f}. "
                    "Review discretionary and recurring categories before the month hardens."
                )
            else:
                pace_status = "under_plan"
                pace_detail = (
                    f"Month-to-date spend is ${abs(pace_delta):,.0f} below plan. "
                    "The plan still has room for remaining bills and savings."
                )
        if not has_plan:
            status = "setup_needed"
            summary = (
                "Set the core monthly plan so Jenny can judge whether current spending is on pace."
            )
        elif (
            profile.monthly_essential_target is not None
            and reports.executive.average_monthly_essentials > profile.monthly_essential_target
        ):
            status = "essentials_above_plan"
            summary = "Essential spending is running above the current target and needs review."
        elif (
            profile.monthly_discretionary_target is not None
            and reports.executive.average_monthly_discretionary
            > profile.monthly_discretionary_target
        ):
            status = "discretionary_above_plan"
            summary = "Discretionary spending is running above the current cap."
        else:
            status = "on_track"
            summary = "The current monthly spending profile is inside the available budget guardrails."

        return HouseholdBudgetSnapshot(
            status=status,
            summary=summary,
            monthly_income_target=profile.monthly_net_income_target,
            monthly_plan_total=monthly_plan_total if has_plan else None,
            essential_target=profile.monthly_essential_target,
            discretionary_target=profile.monthly_discretionary_target,
            savings_target=profile.monthly_savings_target,
            actual_monthly_spend=reports.executive.average_monthly_spend,
            actual_essential_monthly_spend=reports.executive.average_monthly_essentials,
            actual_discretionary_monthly_spend=reports.executive.average_monthly_discretionary,
            month_to_date_spend=month_to_date_spend,
            month_to_date_plan=month_to_date_plan,
            pace_status=pace_status,
            pace_detail=pace_detail,
            remaining_cash_after_plan=remaining_cash_after_plan,
            discretionary_headroom=discretionary_headroom,
        )

    def build_action_items(
        self,
        *,
        questions: list[Any],
        opportunities: list[Any],
        next_best_action: str,
        reports: Any,
        budget_readiness: BudgetReadiness,
        categorization_queue: list[HouseholdCategorizationCandidate] | None = None,
    ) -> list[HouseholdActionItem]:
        items: list[HouseholdActionItem] = []
        categorization_queue = categorization_queue or []

        for question in questions[:3]:
            items.append(
                HouseholdActionItem(
                    title="Answer Jenny follow-up",
                    detail=question.question,
                    action_label="Answer in Money System",
                    href="/money",
                    priority=question.priority,
                    source="question",
                )
            )

        for missing_input in budget_readiness.missing_inputs[:2]:
            items.append(
                HouseholdActionItem(
                    title="Finish the monthly plan",
                    detail=missing_input,
                    action_label="Update plan",
                    href="/money",
                    priority="high",
                    source="budget_readiness",
                )
            )

        for opportunity in opportunities[:2]:
            items.append(
                HouseholdActionItem(
                    title=opportunity.title,
                    detail=opportunity.detail,
                    action_label="Review in Money System",
                    href="/money",
                    priority="medium",
                    source=opportunity.category,
                )
            )

        if reports.executive.tracked_expense_count == 0:
            items.append(
                HouseholdActionItem(
                    title="Feed the household ledger",
                    detail="Upload a recent checking or credit-card statement so the budget view is based on real transactions.",
                    action_label="Upload documents",
                    href="/money",
                    priority="high",
                    source="documents",
                )
            )

        if categorization_queue:
            items.append(
                HouseholdActionItem(
                    title="Review uncategorized spending",
                    detail=f"{len(categorization_queue)} transaction{'s' if len(categorization_queue) != 1 else ''} still need clean categories.",
                    action_label="Categorize now",
                    href="/money",
                    priority="high",
                    source="categorization_queue",
                )
            )

        if not items:
            items.append(
                HouseholdActionItem(
                    title="Next best household step",
                    detail=next_best_action,
                    action_label="Open Money System",
                    href="/money",
                    priority="medium",
                    source="overview",
                )
            )

        priority_rank = {"high": 0, "medium": 1, "low": 2}
        deduped: list[HouseholdActionItem] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            key = (item.title, item.detail)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return sorted(
            deduped,
            key=lambda item: (priority_rank.get(item.priority, 3), item.title),
        )[:6]

    def build_categorization_queue(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdCategorizationCandidate]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    t.id,
                    COALESCE(t.raw_merchant, t.description) AS merchant,
                    t.description,
                    t.amount,
                    t.transaction_date,
                    t.category,
                    t.essentiality,
                    t.confidence,
                    COALESCE(similar_txns.similar_count, 0) AS similar_count
                FROM household_transactions t
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) AS similar_count
                    FROM household_transactions
                    WHERE flow_type = 'expense'
                    GROUP BY merchant_id
                ) similar_txns ON similar_txns.merchant_id = t.merchant_id
                WHERE t.flow_type = 'expense'
                  AND (
                    COALESCE(t.category, 'Household') = 'Household'
                    OR COALESCE(t.essentiality, 'mixed') = 'mixed'
                    OR COALESCE(t.confidence, 0) < 0.85
                  )
                ORDER BY COALESCE(t.confidence, 0) ASC, t.transaction_date DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()

        return [
            HouseholdCategorizationCandidate(
                id=str(row[0]),
                merchant=str(row[1]),
                description=str(row[2]),
                amount=float(row[3]),
                transaction_date=row[4].isoformat(),
                current_category=str(row[5] or "Household"),
                current_essentiality=str(row[6] or "mixed"),
                suggested_category=self.suggest_category(str(row[1]), str(row[2])),
                suggested_essentiality=self.suggest_essentiality(str(row[1]), str(row[2])),
                confidence=float(row[7] or 0.0),
                similar_transaction_count=max(int(row[8] or 0) - 1, 0),
                reason="Low-confidence or mixed classification needs a human pass before Jenny hardens the budget lane.",
            )
            for row in rows
        ]

    def build_recurring_commitments(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdRecurringCommitment]:
        commitments: list[HouseholdRecurringCommitment] = []
        today = datetime.now(UTC).date()
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
                    COALESCE(t.category, 'Household') AS category,
                    AVG(CAST(t.amount AS DOUBLE PRECISION)) AS average_amount,
                    COUNT(*) AS transaction_count,
                    MAX(t.transaction_date) AS last_seen
                FROM household_transactions t
                LEFT JOIN household_merchants m ON m.id = t.merchant_id
                WHERE t.flow_type = 'expense'
                GROUP BY 1, 2
                HAVING COUNT(*) >= 2
                ORDER BY average_amount DESC
                LIMIT %s
                """,
                [limit * 2],
            ).fetchall()

        for row in rows:
            merchant = str(row[0])
            cadence_info = service.transaction_service.infer_merchant_cadence(merchant=merchant) or {}
            cadence = str(cadence_info.get("label") or "irregular")
            if cadence not in {"monthly", "biweekly", "weekly", "quarterly"}:
                continue
            average_amount = float(row[2] or 0.0)
            last_seen = row[4]
            if last_seen is None:
                continue
            annualized_cost = average_amount * {
                "weekly": 52,
                "biweekly": 26,
                "monthly": 12,
                "quarterly": 4,
            }.get(cadence, 12)
            commitment_type = (
                "subscription" if str(row[1]).lower() in {"subscriptions", "dining"} else "bill"
            )
            next_expected = self.estimate_next_commitment_date(last_seen, cadence)
            next_expected_date = (
                datetime.fromisoformat(next_expected).date() if next_expected is not None else None
            )
            days_until_due = (
                (next_expected_date - today).days if next_expected_date is not None else None
            )
            if days_until_due is None:
                due_status = "unknown"
            elif days_until_due < 0:
                due_status = "overdue"
            elif days_until_due <= 3:
                due_status = "due_soon"
            else:
                due_status = "upcoming"
            commitments.append(
                HouseholdRecurringCommitment(
                    merchant=merchant,
                    category=str(row[1]),
                    cadence=cadence,
                    average_amount=round(average_amount, 2),
                    annualized_cost=round(annualized_cost, 2),
                    last_seen=last_seen.isoformat(),
                    next_expected=next_expected,
                    days_until_due=days_until_due,
                    due_status=due_status,
                    due_confidence=float(cadence_info.get("confidence") or 0.0),
                    commitment_type=commitment_type,
                )
            )
        return commitments[:limit]

    def build_sinking_funds(
        self, *, recurring_commitments: list[HouseholdRecurringCommitment]
    ) -> list[HouseholdSinkingFund]:
        funds: list[HouseholdSinkingFund] = []
        for commitment in recurring_commitments:
            if commitment.cadence not in {"quarterly", "irregular"} and commitment.average_amount < 150:
                continue
            annual_cost = commitment.annualized_cost
            monthly_target = round(annual_cost / 12, 2)
            funds.append(
                HouseholdSinkingFund(
                    name=f"{commitment.merchant} buffer",
                    monthly_target=monthly_target,
                    annual_cost=round(annual_cost, 2),
                    rationale="Set aside a monthly buffer so periodic or lumpy household costs stop surprising the budget.",
                )
            )
        return funds[:4]

    def build_retirement_contribution_tracker(
        self,
        *,
        profile: Any,
        estimated_monthly_contributions: float,
    ) -> HouseholdRetirementContributionTracker:
        monthly_target = profile.monthly_savings_target
        if monthly_target is None:
            return HouseholdRetirementContributionTracker(
                status="target_missing",
                monthly_target=None,
                estimated_monthly_contributions=estimated_monthly_contributions,
                monthly_gap=0.0,
                detail="Set the monthly savings target so Jenny can compare current retirement contributions against the plan.",
            )

        monthly_gap = max(monthly_target - estimated_monthly_contributions, 0.0)
        status = "gap" if monthly_gap > 0 else "on_track"
        detail = (
            "Recent retirement contributions are trailing the household savings target."
            if monthly_gap > 0
            else "Recent retirement contributions are keeping up with the savings target."
        )
        return HouseholdRetirementContributionTracker(
            status=status,
            monthly_target=monthly_target,
            estimated_monthly_contributions=estimated_monthly_contributions,
            monthly_gap=monthly_gap,
            detail=detail,
        )

    def build_retirement_scenarios(
        self,
        *,
        retirement_assets: float,
        target_retirement_spend: float | None,
        baseline_monthly_spend: float,
    ) -> list[HouseholdRetirementScenario]:
        base_monthly_spend = target_retirement_spend or baseline_monthly_spend or 0.0
        if base_monthly_spend <= 0:
            return []

        scenarios: list[HouseholdRetirementScenario] = []
        scenario_inputs = [
            ("Base plan", base_monthly_spend),
            ("Higher-spend stretch", round(base_monthly_spend * 1.15, 2)),
            ("Lean floor", round(base_monthly_spend * 0.85, 2)),
        ]
        for name, monthly_spend in scenario_inputs:
            annual_spend = monthly_spend * 12
            funded_years = round(retirement_assets / annual_spend, 1) if annual_spend > 0 else 0.0
            readiness = (
                "strong" if funded_years >= 25 else "developing" if funded_years >= 15 else "short"
            )
            scenarios.append(
                HouseholdRetirementScenario(
                    name=name,
                    monthly_spend=round(monthly_spend, 2),
                    annual_spend=round(annual_spend, 2),
                    funded_years=funded_years,
                    readiness=readiness,
                    detail="A plain-language spend scenario using currently visible retirement assets.",
                )
            )
        return scenarios

    def estimate_monthly_retirement_contributions(self, service: Any) -> float:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT AVG(month_total)
                FROM (
                    SELECT
                        date_trunc('month', transaction_date) AS month_bucket,
                        SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
                    FROM household_transactions
                    WHERE flow_type IN ('transfer_out', 'expense')
                      AND (
                        COALESCE(account_label, '') ILIKE '%ira%'
                        OR COALESCE(account_label, '') ILIKE '%401%'
                        OR COALESCE(account_label, '') ILIKE '%roth%'
                        OR COALESCE(account_label, '') ILIKE '%hsa%'
                      )
                    GROUP BY 1
                ) monthly_contributions
                """
            ).fetchone()
        return round(float(row[0] or 0.0), 2) if row is not None else 0.0

    def estimate_next_commitment_date(self, last_seen: datetime, cadence: str) -> str | None:
        offsets = {
            "weekly": timedelta(days=7),
            "biweekly": timedelta(days=14),
            "monthly": timedelta(days=30),
            "quarterly": timedelta(days=90),
        }
        if cadence not in offsets:
            return None
        return (last_seen + offsets[cadence]).isoformat()

    def suggest_category(self, merchant: str, description: str) -> str:
        candidate = f"{merchant} {description}".lower()
        if "spotify" in candidate or "netflix" in candidate or "prime" in candidate:
            return "Subscriptions"
        if "walmart" in candidate or "publix" in candidate or "whole foods" in candidate:
            return "Groceries"
        if "shell" in candidate or "speedway" in candidate:
            return "Gas"
        if "insurance" in candidate or "duke" in candidate or "mortgage" in candidate:
            return "Bills"
        return "Household"

    def suggest_essentiality(self, merchant: str, description: str) -> str:
        category = self.suggest_category(merchant, description)
        return "essential" if category in {"Groceries", "Gas", "Bills"} else "discretionary"

    def current_month_spend(self, service: Any) -> float:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(CAST(amount AS DOUBLE PRECISION)), 0)
                FROM household_transactions
                WHERE flow_type = 'expense'
                  AND transaction_date >= date_trunc('month', CURRENT_DATE)
                """
            ).fetchone()
        return round(float(row[0] or 0.0), 2) if row is not None else 0.0
