"""Dashboard composition helpers for household finance views."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    BudgetReadiness,
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
    JennyNeed,
    JennyProgression,
    PortfolioHouseholdContext,
    RetirementPreparedness,
)
from app.services._household_dashboard_builders import (
    build_budget_snapshot,
    build_retirement_contribution_tracker,
    build_retirement_scenarios,
    build_sinking_funds,
    build_starter_lanes,
)
from app.services._household_dashboard_queries import (
    check_statement_freshness,
    detect_unknown_accounts,
    fetch_categorization_queue,
    fetch_confirmed_facts,
    fetch_current_month_spend,
    fetch_monthly_retirement_contributions,
    fetch_recurring_commitments,
    infer_profile_from_transactions,
)

_IMPORT_CENTER = ImportCenter(
    headline="Use statements for coverage, then receipts and invoices for savings intelligence.",
    tracked_documents=0,
    parsed_documents=0,
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

_JENNY_BRIEF = JennyMoneyBrief(
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


def _build_jenny_needs(
    *,
    profile: Any,
    documents: list[Any],
    questions: list[Any],
    resolved_values: list[Any],
    reports: Any,
    confirmed_facts: dict[str, str],
    detected_accounts: list[dict[str, str]],
    freshness: dict[str, Any],
    categorization_queue: list[Any],
) -> list[JennyNeed]:
    """Build the unified priority-ordered jenny_needs list. Only unsatisfied needs are returned."""
    needs: list[JennyNeed] = []
    coverage_months = freshness.get("coverage_months", 0)
    days_since_latest = freshness.get("days_since_latest")

    # 1. Upload statements (critical)
    statements_satisfied = coverage_months >= 3 and (days_since_latest is not None and days_since_latest < 45)
    if not statements_satisfied:
        detail = "Jenny needs at least 3 months of recent statements to build accurate spending baselines."
        if coverage_months > 0 and days_since_latest is not None:
            detail = f"Currently {coverage_months} month{'s' if coverage_months != 1 else ''} of data, most recent {days_since_latest} days ago. More coverage improves accuracy."
        needs.append(JennyNeed(
            id="need_statements",
            need_type="provide",
            title="Upload statements",
            detail=detail,
            priority="critical",
            status="unsatisfied",
            recurrence="periodic",
            action_href="/money",
        ))

    # 2. Account completeness (high)
    if "account_completeness" not in confirmed_facts:
        needs.append(JennyNeed(
            id="need_account_completeness",
            need_type="confirm",
            title="Are all accounts covered?",
            detail="Confirm that the uploaded statements cover all your active bank and credit card accounts.",
            priority="high",
            status="unsatisfied",
            recurrence="one_time",
            field_name="account_completeness",
        ))

    # 3. Household scope (high)
    if "household_scope" not in confirmed_facts:
        needs.append(JennyNeed(
            id="need_household_scope",
            need_type="confirm",
            title="Who is in this household?",
            detail="Confirm whether this is a single-person or multi-person household so Jenny sizes the budget correctly.",
            priority="high",
            status="unsatisfied",
            recurrence="one_time",
            field_name="household_scope",
        ))

    # 4. Income sources (high)
    if "income_sources" not in confirmed_facts:
        needs.append(JennyNeed(
            id="need_income_sources",
            need_type="confirm",
            title="Confirm income sources",
            detail="Tell Jenny about your income sources (salary, freelance, etc.) so she can track completeness.",
            priority="high",
            status="unsatisfied",
            recurrence="one_time",
            field_name="income_sources",
        ))

    # 5. Detected unknown accounts (high, per account)
    for account in detected_accounts:
        institution = account.get("institution", "Unknown")
        partial = account.get("partial_account", "")
        acct_key = account.get("key", institution)
        label = f"{institution} ...{partial}" if partial else institution
        needs.append(JennyNeed(
            id=f"need_account_{acct_key}",
            need_type="provide",
            title=f"Upload {label} statements",
            detail=f"Jenny spotted references to {label} in your transactions but has no statements for it.",
            priority="high",
            status="unsatisfied",
            recurrence="one_time",
            action_href="/money",
        ))

    # 6. Document review confirmations (medium)
    open_questions = [q for q in questions if q.status == "open"]
    for q in open_questions[:3]:
        needs.append(JennyNeed(
            id=f"need_question_{q.id}",
            need_type="confirm",
            title="Review Jenny's finding",
            detail=q.question,
            priority="medium",
            status="unsatisfied",
            recurrence="as_needed",
            related_question_id=q.id,
        ))

    # 7. Retirement age (medium)
    if profile.target_retirement_age is None:
        needs.append(JennyNeed(
            id="need_retirement_age",
            need_type="set",
            title="Set retirement age",
            detail="Jenny needs a target retirement age to run scenario planning.",
            priority="medium",
            status="unsatisfied",
            recurrence="one_time",
            field_name="target_retirement_age",
        ))

    # 8. Retirement spending (medium)
    if profile.target_retirement_spend is None:
        needs.append(JennyNeed(
            id="need_retirement_spend",
            need_type="set",
            title="Set retirement spending target",
            detail="Define a monthly retirement spending target so Jenny can project readiness.",
            priority="medium",
            status="unsatisfied",
            recurrence="one_time",
            field_name="target_retirement_spend",
        ))

    # 9. Category corrections (medium)
    if categorization_queue:
        count = len(categorization_queue)
        needs.append(JennyNeed(
            id="need_category_corrections",
            need_type="review",
            title="Review spending categories",
            detail=f"{count} transaction{'s' if count != 1 else ''} need category confirmation so Jenny can trust the budget lanes.",
            priority="medium",
            status="unsatisfied",
            recurrence="as_needed",
        ))

    # 10. Statement freshness (low, only when docs exist but stale)
    if documents and days_since_latest is not None and days_since_latest >= 45:
        needs.append(JennyNeed(
            id="need_freshness",
            need_type="provide",
            title="Upload newer statements",
            detail=f"The most recent transaction is {days_since_latest} days old. Fresher data keeps pacing accurate.",
            priority="low",
            status="unsatisfied",
            recurrence="periodic",
            action_href="/money",
        ))

    return needs


def _build_progression(
    *,
    reports: Any,
    resolved_values: list[Any],
    profile: Any,
) -> JennyProgression:
    """Build the found/working-on progression for the Jenny brief."""
    executive = reports.executive

    # --- found ---
    found: list[str] = []
    if executive.recurring_merchant_count > 0:
        found.append(
            f"Detected {executive.recurring_merchant_count} recurring monthly "
            f"commitment{'s' if executive.recurring_merchant_count != 1 else ''} "
            f"from your statements"
        )
    if executive.average_monthly_essentials > 0:
        found.append(
            f"Your essential spending averages ${executive.average_monthly_essentials:,.0f}/mo "
            f"across {executive.coverage_months} month{'s' if executive.coverage_months != 1 else ''}"
        )
    if executive.tracked_expense_count > 0:
        found.append(
            f"{executive.tracked_expense_count} transaction{'s' if executive.tracked_expense_count != 1 else ''} "
            f"tracked and categorized from your statements"
        )
    inferred_count = sum(
        1 for rv in resolved_values
        if rv.source == "jenny_inference" and rv.value is not None
    )
    if inferred_count > 0:
        found.append(
            f"{inferred_count} profile value{'s' if inferred_count != 1 else ''} "
            f"auto-resolved from your data"
        )

    # --- working_on ---
    inferred_fields = _fields_with_confident_inferences(resolved_values, threshold=0.7)
    profile_fields = {
        "monthly_net_income_target",
        "monthly_essential_target",
        "monthly_discretionary_target",
        "monthly_savings_target",
        "target_retirement_age",
        "target_retirement_spend",
    }
    confirmed_fields = {
        rv.field_name for rv in resolved_values
        if rv.source == "user" and rv.field_name in profile_fields
    }
    all_known = inferred_fields | confirmed_fields

    if executive.coverage_months < 3:
        working_on = (
            "Building spending baselines \u2014 more statement history will improve accuracy"
        )
    elif len(all_known) < len(profile_fields):
        working_on = "Refining your financial picture as more data comes in"
    else:
        working_on = "Monitoring budget pacing and identifying optimization opportunities"

    return JennyProgression(
        found=found,
        working_on=working_on,
    )


def _fields_with_confident_inferences(resolved_values: list[Any], *, threshold: float) -> set[str]:
    """Return field names that have inferred values at or above the given confidence threshold."""
    fields: set[str] = set()
    for rv in resolved_values:
        if (
            rv.source == "jenny_inference"
            and rv.confidence is not None
            and rv.confidence >= threshold
            and rv.value is not None
        ):
            fields.add(rv.field_name)
    return fields


def _build_import_center(documents: list[Any]) -> ImportCenter:
    parsed_count = sum(1 for d in documents if d.status in {"parsed", "needs_review"})
    return ImportCenter(
        headline=_IMPORT_CENTER.headline,
        tracked_documents=len(documents),
        parsed_documents=parsed_count,
        suggested_first_uploads=_IMPORT_CENTER.suggested_first_uploads,
        automations=_IMPORT_CENTER.automations,
        supported_documents=_IMPORT_CENTER.supported_documents,
    )


def _build_overview(
    *,
    service: Any,
    accounts: list[Any],
    live_positions: list[Any],
    holdings_by_account: dict[str, float],
    documents: list[Any],
    questions: list[Any],
    resolved_values: list[Any],
) -> tuple[HouseholdOverview, float, float, float, float]:
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
    return (
        HouseholdOverview(
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
        ),
        retirement_assets,
        taxable_assets,
        cash_reserve,
        total_tracked_assets,
    )


def _resolved_numeric_value(field: Any, resolved_values: list[Any], service: Any) -> Any:
    """Get resolved numeric value for a field."""
    return service._resolved_numeric_value(resolved_values, field)


def _build_budget_readiness(*, service: Any, resolved_values: list[Any], documents: list[Any]) -> BudgetReadiness:
    budget_inputs = service._budget_input_status(resolved_values, documents)

    def resolved_numeric_value(field: Any) -> Any:
        """Get resolved numeric value for the given field."""
        return service._resolved_numeric_value(resolved_values, field)

    return BudgetReadiness(
        status="ready_for_budgeting" if budget_inputs["budget_ready"] else "setup_needed",
        summary=(
            "Jenny can enforce budget guardrails once household income targets and transaction documents are in place."
            if budget_inputs["budget_ready"]
            else "Budgeting is one step away: define the monthly plan and keep feeding the system statements."
        ),
        priorities=budget_inputs["priorities"],
        missing_inputs=budget_inputs["missing_inputs"],
        starter_lanes=build_starter_lanes(resolved_numeric_value),
    )


def _build_retirement_preparedness(
    *,
    service: Any,
    resolved_values: list[Any],
    documents: list[Any],
    retirement_assets: float,
    taxable_assets: float,
    cash_reserve: float,
    total_tracked_assets: float,
) -> RetirementPreparedness:
    retirement_share = (retirement_assets / total_tracked_assets) * 100 if total_tracked_assets > 0 else 0.0
    return RetirementPreparedness(
        status="scenario_ready" if service._retirement_ready(resolved_values, documents) else "baseline_visible",
        summary=(
            "Retirement planning can move from rough intuition to defensible scenario planning."
            if service._retirement_ready(resolved_values, documents)
            else "Retirement assets are visible, but retirement readiness still depends on real spending and future-income assumptions."
        ),
        retirement_account_share=retirement_share,
        strengths=service._retirement_strengths(retirement_assets, taxable_assets, cash_reserve, resolved_values),
        blockers=service._retirement_blockers(resolved_values, documents),
        next_steps=service._retirement_next_steps(resolved_values, documents),
    )


def _build_portfolio_context(
    *,
    total_tracked_assets: float,
    cash_reserve: float,
    profile: Any,
    reports: Any,
) -> PortfolioHouseholdContext | None:
    """Bridge portfolio data with household spending to produce cross-domain insights."""
    monthly_essential: float | None = None
    annual_spend: float | None = None

    # Prefer profile targets; fall back to transaction-derived averages
    if profile.monthly_essential_target is not None and profile.monthly_essential_target > 0:
        monthly_essential = profile.monthly_essential_target
    elif reports.executive.average_monthly_essentials > 0:
        monthly_essential = reports.executive.average_monthly_essentials

    monthly_discretionary: float | None = None
    if profile.monthly_discretionary_target is not None and profile.monthly_discretionary_target > 0:
        monthly_discretionary = profile.monthly_discretionary_target
    elif reports.executive.average_monthly_discretionary > 0:
        monthly_discretionary = reports.executive.average_monthly_discretionary

    if monthly_essential is not None:
        if monthly_discretionary is not None:
            annual_spend = (monthly_essential + monthly_discretionary) * 12
        else:
            annual_spend = monthly_essential * 12

    # Compute metrics — only when both sides have data
    cash_reserves_months: float | None = None
    if cash_reserve > 0 and monthly_essential is not None and monthly_essential > 0:
        cash_reserves_months = cash_reserve / monthly_essential

    portfolio_to_annual_spend_ratio: float | None = None
    if total_tracked_assets > 0 and annual_spend is not None and annual_spend > 0:
        portfolio_to_annual_spend_ratio = total_tracked_assets / annual_spend

    total_portfolio_value: float | None = total_tracked_assets if total_tracked_assets > 0 else None

    # Build insight strings only when backed by real numbers
    insights: list[str] = []
    if cash_reserves_months is not None:
        insights.append(f"Your cash reserves cover {cash_reserves_months:.1f} months of essential spending.")
    if portfolio_to_annual_spend_ratio is not None:
        insights.append(
            f"Your portfolio represents {portfolio_to_annual_spend_ratio:.1f}x your annual spending."
        )

    # Only return context when there is at least one useful data point
    if total_portfolio_value is None and cash_reserves_months is None and portfolio_to_annual_spend_ratio is None:
        return None

    return PortfolioHouseholdContext(
        total_portfolio_value=total_portfolio_value,
        cash_reserves_months=cash_reserves_months,
        portfolio_to_annual_spend_ratio=portfolio_to_annual_spend_ratio,
        insights=insights,
    )


class HouseholdDashboardComposer:
    """Build the household dashboard from existing service dependencies."""

    def build_dashboard(self, service: Any) -> HouseholdFinanceDashboard:
        profile = service.get_profile()
        documents = service.list_documents(limit=12).items
        questions = service.list_questions(limit=12).items
        accounts = [a for a in service.portfolio_mgr.get_accounts() if a.account_type != "paper"]
        positions = service.portfolio_mgr.get_positions()
        account_ids = {a.id for a in accounts}
        live_positions = [p for p in positions if p.account_id in account_ids]
        price_data = service._fetch_prices(live_positions)
        holdings_by_account = service._calculate_holdings_by_account(live_positions, price_data)

        # Build reports first so we can infer profile values from transaction data
        reports = service.transaction_service.build_reports()

        # Auto-infer profile fields from transaction data before resolving values
        existing_inferences = service._get_inferred_value_rows()
        infer_profile_from_transactions(
            service.storage,
            profile=profile,
            reports=reports,
            existing_inferences=existing_inferences,
        )

        # Re-fetch resolved values now that transaction inferences are persisted
        resolved_values = service.get_resolved_values(profile=profile, questions=questions)

        # Filter out questions for fields that have high-confidence transaction inferences.
        # Only target_retirement_age and target_retirement_spend genuinely need user input.
        non_inferable_fields = {"target_retirement_age", "target_retirement_spend"}
        inferred_fields = _fields_with_confident_inferences(resolved_values, threshold=0.7)
        visible_questions = [
            q for q in questions
            if q.field_name is None
            or q.field_name in non_inferable_fields
            or q.field_name not in inferred_fields
        ]

        overview, retirement_assets, taxable_assets, cash_reserve, total_tracked_assets = _build_overview(
            service=service,
            accounts=accounts,
            live_positions=live_positions,
            holdings_by_account=holdings_by_account,
            documents=documents,
            questions=visible_questions,
            resolved_values=resolved_values,
        )
        budget_readiness = _build_budget_readiness(
            service=service, resolved_values=resolved_values, documents=documents
        )
        retirement_preparedness = _build_retirement_preparedness(
            service=service,
            resolved_values=resolved_values,
            documents=documents,
            retirement_assets=retirement_assets,
            taxable_assets=taxable_assets,
            cash_reserve=cash_reserve,
            total_tracked_assets=total_tracked_assets,
        )
        budget_snapshot = service._build_budget_snapshot(profile=profile, reports=reports)
        categorization_queue = service._build_categorization_queue()
        recurring_commitments = service._build_recurring_commitments()
        sinking_funds = service._build_sinking_funds(recurring_commitments=recurring_commitments)
        retirement_contribution_tracker = service._build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=service._estimate_monthly_retirement_contributions(),
        )
        retirement_scenarios = service._build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=profile.target_retirement_spend,
            baseline_monthly_spend=reports.executive.average_monthly_spend,
        )
        portfolio_context = _build_portfolio_context(
            total_tracked_assets=total_tracked_assets,
            cash_reserve=cash_reserve,
            profile=profile,
            reports=reports,
        )

        # Unified needs system
        confirmed_facts = fetch_confirmed_facts(service.storage)
        detected_accounts = detect_unknown_accounts(service.storage, documents)
        freshness = check_statement_freshness(service.storage)
        jenny_needs = _build_jenny_needs(
            profile=profile,
            documents=documents,
            questions=visible_questions,
            resolved_values=resolved_values,
            reports=reports,
            confirmed_facts=confirmed_facts,
            detected_accounts=detected_accounts,
            freshness=freshness,
            categorization_queue=categorization_queue,
        )

        # Derive next_best_action from top unsatisfied need
        if jenny_needs:
            overview = HouseholdOverview(
                invested_assets=overview.invested_assets,
                retirement_assets=overview.retirement_assets,
                taxable_assets=overview.taxable_assets,
                cash_reserve=overview.cash_reserve,
                total_tracked_assets=overview.total_tracked_assets,
                visibility_score=overview.visibility_score,
                visibility_label=overview.visibility_label,
                next_best_action=jenny_needs[0].title,
            )

        return HouseholdFinanceDashboard(
            generated_at=datetime.now(UTC).isoformat(),
            overview=overview,
            profile=profile,
            resolved_values=resolved_values,
            budget_readiness=budget_readiness,
            budget_snapshot=budget_snapshot,
            retirement_preparedness=retirement_preparedness,
            jenny_needs=jenny_needs,
            action_items=[],
            reports=reports,
            categorization_queue=categorization_queue,
            recurring_commitments=recurring_commitments,
            sinking_funds=sinking_funds,
            retirement_contribution_tracker=retirement_contribution_tracker,
            retirement_scenarios=retirement_scenarios,
            import_center=_build_import_center(documents),
            questions=visible_questions,
            jenny_brief=JennyMoneyBrief(
                headline=_JENNY_BRIEF.headline,
                body=_JENNY_BRIEF.body,
                prompts=_JENNY_BRIEF.prompts,
                progression=_build_progression(
                    reports=reports,
                    resolved_values=resolved_values,
                    profile=profile,
                ),
            ),
            portfolio_context=portfolio_context,
        )

    def build_budget_snapshot(
        self,
        service: Any,
        *,
        profile: Any,
        reports: Any,
    ) -> HouseholdBudgetSnapshot:
        return build_budget_snapshot(
            profile=profile,
            reports=reports,
            month_to_date_spend=service._current_month_spend(),
        )

    def build_categorization_queue(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdCategorizationCandidate]:
        return fetch_categorization_queue(service.storage, limit)

    def build_recurring_commitments(
        self, service: Any, limit: int = 6
    ) -> list[HouseholdRecurringCommitment]:
        return fetch_recurring_commitments(service.storage, service.transaction_service, limit)

    def build_sinking_funds(
        self, *, recurring_commitments: list[HouseholdRecurringCommitment]
    ) -> list[HouseholdSinkingFund]:
        return build_sinking_funds(recurring_commitments=recurring_commitments)

    def build_retirement_contribution_tracker(
        self,
        *,
        profile: Any,
        estimated_monthly_contributions: float,
    ) -> HouseholdRetirementContributionTracker:
        return build_retirement_contribution_tracker(
            profile=profile,
            estimated_monthly_contributions=estimated_monthly_contributions,
        )

    def build_retirement_scenarios(
        self,
        *,
        retirement_assets: float,
        target_retirement_spend: float | None,
        baseline_monthly_spend: float,
    ) -> list[HouseholdRetirementScenario]:
        return build_retirement_scenarios(
            retirement_assets=retirement_assets,
            target_retirement_spend=target_retirement_spend,
            baseline_monthly_spend=baseline_monthly_spend,
        )

    def estimate_monthly_retirement_contributions(self, service: Any) -> float:
        return fetch_monthly_retirement_contributions(service.storage)

    def current_month_spend(self, service: Any) -> float:
        return fetch_current_month_spend(service.storage)
