"""Auxiliary Pydantic models for the household finance dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HouseholdAssetAllocationSlice(BaseModel):
    """Per-asset-group rollup for the allocation chart.

    Same rules the chart uses: credit/debt groups and non-positive values are
    excluded, sorted by value descending. Note this keeps education separate,
    unlike overview.taxable_assets which folds education in.
    """

    asset_group: str
    total_value: float


class HouseholdOverview(BaseModel):
    invested_assets: float
    retirement_assets: float
    taxable_assets: float
    cash_reserve: float
    total_tracked_assets: float
    liabilities_total: float = 0.0
    net_worth: float = 0.0
    asset_allocation: list[HouseholdAssetAllocationSlice] = Field(default_factory=list)
    tracked_account_count: int = 0
    needs_refresh_count: int = 0
    candidate_account_count: int = 0
    gap_count: int = 0
    inbox_count: int = 0
    coverage_months: int = 0
    last_transaction_date: str | None = None
    visibility_score: int
    visibility_label: str
    next_best_action: str
    net_worth_status: str = "current"
    net_worth_detail: str = "Net worth reflects current covered accounts."
    monthly_spend_status: str = "current"
    monthly_spend_detail: str = "Monthly spend reflects current covered transaction accounts."


class HouseholdAccountControlIssue(BaseModel):
    id: str
    code: str
    severity: str
    title: str
    detail: str
    household_account_id: str | None = None
    account_label: str | None = None
    source: str | None = None
    source_account_ids: list[str] = Field(default_factory=list)
    affects_totals: bool = False


class HouseholdAccountControl(BaseModel):
    status: str
    summary: str
    issue_count: int = 0
    blocking_issue_count: int = 0
    checked_at: str
    issues: list[HouseholdAccountControlIssue] = Field(default_factory=list)


class HouseholdResolvedValue(BaseModel):
    field_name: str
    label: str
    value: str | None = None
    confidence: float | None = None
    status: str
    source: str
    rationale: str | None = None
    question: str | None = None


class BudgetLane(BaseModel):
    name: str
    objective: str
    status: str


class BudgetReadiness(BaseModel):
    status: str
    summary: str
    priorities: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    starter_lanes: list[BudgetLane] = Field(default_factory=list)


class RetirementPreparedness(BaseModel):
    status: str
    summary: str
    retirement_account_share: float
    strengths: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class HouseholdOpportunity(BaseModel):
    title: str
    category: str
    impact: str
    detail: str
    next_step: str


class HouseholdExecutiveReport(BaseModel):
    headline: str
    summary: str
    average_monthly_spend: float
    average_monthly_essentials: float
    average_monthly_discretionary: float
    recent_30_day_spend: float
    recurring_merchant_count: int
    tracked_expense_count: int
    coverage_months: int


class HouseholdCategoryBreakdown(BaseModel):
    category: str
    essentiality: str
    monthly_average: float
    share_of_spend: float
    total_spend: float


class HouseholdMerchantInsight(BaseModel):
    merchant: str
    total_spend: float
    average_ticket: float
    transaction_count: int
    cadence: str
    category: str
    recommendation: str


class HouseholdPriceInsight(BaseModel):
    merchant: str
    item_name: str
    signal_type: str = "price_change"
    latest_price: float
    previous_price: float
    price_change: float
    price_change_pct: float | None = None
    latest_date: str
    previous_date: str
    latest_unit_label: str | None = None
    previous_unit_label: str | None = None
    unit_measure: str | None = None
    latest_unit_price: float | None = None
    previous_unit_price: float | None = None
    unit_price_change_pct: float | None = None
    size_change_pct: float | None = None
    shrinkflation_flag: bool = False
    confidence: float = 0.0
    recommendation: str


class HouseholdMonthlyTrendPoint(BaseModel):
    month: str
    total_spend: float
    transaction_count: int


class HouseholdNetWorthTrendPoint(BaseModel):
    date: str
    net_worth: float
    total_assets: float
    liabilities: float
    priced_holdings_value: float
    fixed_assets: float


class HouseholdNetWorthTrend(BaseModel):
    generated_at: str
    as_of_date: str | None = None
    status: str
    detail: str
    methodology: str
    points: list[HouseholdNetWorthTrendPoint] = Field(default_factory=list)
    holdings_symbol_count: int = 0
    holdings_position_count: int = 0
    gap_count: int = 0
    needs_refresh_count: int = 0
    missing_balance_account_count: int = 0
    stale_account_count: int = 0


class HouseholdRecentTransaction(BaseModel):
    date: str
    merchant: str
    description: str
    amount: float
    category: str
    essentiality: str
    account_label: str | None = None
    source_document_id: str | None = None


class HouseholdLedgerEntry(BaseModel):
    id: str
    kind: str
    # Linked purchase items (itemized receipts/orders). Count + distinct item
    # categories drive the ledger "items" badge and row expansion affordance.
    item_count: int = 0
    item_categories: list[str] = Field(default_factory=list)
    flow_type: str | None = None
    # Accounting direction ("debit" | "credit" | "neutral") resolved once on the server
    # so the client never re-derives it from flow_type string sets.
    direction: str = "neutral"
    household_account_id: str | None = None
    account_label: str | None = None
    date: str | None = None
    posted_date: str | None = None
    merchant: str | None = None
    description: str
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    essentiality: str | None = None
    original_category: str | None = None
    categorization_source: str | None = None
    categorization_version: str | None = None
    category_updated_at: str | None = None
    category_updated_by: str | None = None
    source_system: str | None = None
    external_transaction_id: str | None = None
    pending: bool = False
    removed: bool = False
    transaction_rule_id: str | None = None
    dataset_type: str | None = None
    external_row_id: str | None = None
    row_hash: str
    source_document_id: str | None = None
    source_document_filename: str | None = None
    source_type: str | None = None
    document_type: str | None = None
    balance_after: float | None = None
    uploaded_at: str | None = None
    included_in_spend: bool = False
    exclusion_reason: str | None = None


class HouseholdLedger(BaseModel):
    generated_at: str
    timeframe_key: str = "all"
    timeframe_label: str
    start_date: str | None = None
    end_date: str | None = None
    transaction_count: int
    import_row_count: int
    total_entry_count: int = 0
    # Counts after server-side status/account/search filtering (drives pagination + summary).
    filtered_count: int = 0
    included_count: int = 0
    excluded_count: int = 0
    offset: int = 0
    limit: int = 0
    returned_count: int = 0
    # Distinct account labels across the whole window so the filter dropdown is complete
    # even though only a page of rows is returned.
    account_options: list[str] = Field(default_factory=list)
    # Distinct effective categories across the whole window so the inline category
    # editor offers every in-use category, not just those on the current page.
    category_options: list[str] = Field(default_factory=list)
    debit_total: float = 0.0
    credit_total: float = 0.0
    entries: list[HouseholdLedgerEntry] = Field(default_factory=list)


class HouseholdSpendingCategory(BaseModel):
    category: str
    essentiality: str
    total_spend: float
    average_monthly_spend: float
    share_of_spend: float
    transaction_count: int
    # Gross spend before refund credits — the cap-recommendation input so a refund
    # does not silently lower the suggested cap.
    gross_monthly_spend: float = 0.0
    refund_total: float = 0.0
    found_monthly_budget: float | None = None
    confirmed_monthly_budget: float | None = None
    budget_source: str = "no_budget"
    budget_status: str = "no_budget"
    budget_note: str | None = None
    budget_disabled: bool = False


class HouseholdSpendingTransaction(BaseModel):
    id: str
    # Reconciled purchase-item splits behind this charge (same load_item_splits
    # source that moves category totals), so drill-downs can badge split rows.
    item_count: int = 0
    item_categories: list[str] = Field(default_factory=list)
    date: str
    merchant: str
    description: str
    amount: float
    category: str
    essentiality: str
    original_category: str | None = None
    categorization_source: str | None = None
    source_system: str | None = None
    external_transaction_id: str | None = None
    transaction_rule_id: str | None = None
    category_confidence: float | None = None
    needs_category_review: bool = False
    account_label: str | None = None
    source_document_id: str | None = None
    source_kind: str | None = None
    source_type: str | None = None
    document_type: str | None = None


class HouseholdCategoryMonthlyTrendPoint(BaseModel):
    month: str
    category: str
    essentiality: str
    total_spend: float
    transaction_count: int


class HouseholdSpendingSummary(BaseModel):
    timeframe_key: str
    timeframe_label: str
    start_date: str | None = None
    end_date: str | None = None
    total_spend: float = 0.0
    average_monthly_spend: float = 0.0
    transaction_count: int = 0
    coverage_months: int = 0
    account_count: int = 0
    # Gross expense before refund credits, the refund credits themselves, and the
    # income/savings view so the Budget tab can show cash-flow rather than just spend.
    gross_spend: float = 0.0
    refund_total: float = 0.0
    total_income: float = 0.0
    average_monthly_income: float = 0.0
    net_cash_flow: float = 0.0
    savings_rate: float | None = None
    month_to_date_spend: float = 0.0
    found_budget_total: float = 0.0
    confirmed_budget_total: float = 0.0
    budgeted_category_count: int = 0
    found_budget_category_count: int = 0
    confirmed_budget_category_count: int = 0
    over_budget_count: int = 0
    found_over_budget_count: int = 0
    confirmed_over_budget_count: int = 0


class HouseholdSpendingView(BaseModel):
    generated_at: str
    summary: HouseholdSpendingSummary
    categories: list[HouseholdSpendingCategory] = Field(default_factory=list)
    monthly_trend: list[HouseholdMonthlyTrendPoint] = Field(default_factory=list)
    category_monthly_trend: list[HouseholdCategoryMonthlyTrendPoint] = Field(default_factory=list)
    transactions: list[HouseholdSpendingTransaction] = Field(default_factory=list)


class HouseholdMonthComparison(BaseModel):
    """Latest vs previous *completed* month of spend (server clock decides
    the current month, so client timezones cannot shift the boundary)."""

    latest_month: str
    previous_month: str
    latest_total: float
    previous_total: float
    change: float
    change_pct: float | None = None


class HouseholdReports(BaseModel):
    executive: HouseholdExecutiveReport
    category_breakdown: list[HouseholdCategoryBreakdown] = Field(default_factory=list)
    merchant_highlights: list[HouseholdMerchantInsight] = Field(default_factory=list)
    price_insights: list[HouseholdPriceInsight] = Field(default_factory=list)
    monthly_spend_trend: list[HouseholdMonthlyTrendPoint] = Field(default_factory=list)
    month_comparison: HouseholdMonthComparison | None = None
    recent_transactions: list[HouseholdRecentTransaction] = Field(default_factory=list)


class HouseholdBudgetSnapshot(BaseModel):
    status: str
    summary: str
    monthly_income_target: float | None = None
    monthly_plan_total: float | None = None
    monthly_plan_source: str = "none"
    monthly_plan_source_label: str = "No monthly plan"
    essential_target: float | None = None
    discretionary_target: float | None = None
    savings_target: float | None = None
    actual_monthly_spend: float = 0.0
    actual_essential_monthly_spend: float = 0.0
    actual_discretionary_monthly_spend: float = 0.0
    month_to_date_spend: float = 0.0
    month_to_date_plan: float | None = None
    pace_status: str = "unknown"
    pace_detail: str
    # True when a plan exists but not every component (essential/discretionary/savings)
    # is set, so total spend cannot be paced like-for-like against the partial plan.
    plan_is_partial: bool = False
    missing_plan_components: list[str] = Field(default_factory=list)
    remaining_cash_after_plan: float | None = None
    discretionary_headroom: float | None = None
    # Headline discretionary figure = min(cash after cushion and 14-day bills,
    # remaining_cash_after_plan, discretionary_headroom), floored at 0. Null when
    # the snapshot is built without cash/commitment context.
    safe_to_spend: float | None = None
    # Which input bounded it: cash_after_cushion | plan_residual | discretionary_cap.
    safe_to_spend_constraint: str | None = None
    # Commitments due within the next 14 days (digit-free name: es-toolkit
    # camelizes trailing digits unpredictably, e.g. _14d -> 14D).
    due_soon_bills_total: float | None = None
    operating_cushion: float | None = None


class HouseholdCategorizationCandidate(BaseModel):
    id: str
    merchant: str
    description: str
    amount: float
    transaction_date: str
    current_category: str
    current_essentiality: str
    suggested_category: str
    suggested_essentiality: str
    confidence: float
    similar_transaction_count: int = 0
    reason: str


class HouseholdRecurringCommitment(BaseModel):
    merchant: str
    category: str
    cadence: str
    average_amount: float
    annualized_cost: float
    last_seen: str
    next_expected: str | None = None
    days_until_due: int | None = None
    due_status: str = "unknown"
    due_confidence: float = 0.0
    commitment_type: str


class HouseholdTransactionDateIssue(BaseModel):
    id: str
    transaction_id: str | None = None
    document_id: str
    filename: str
    source_type: str
    document_type: str
    transaction_date: str
    uploaded_at: str | None = None
    merchant: str
    description: str
    amount: float
    account_label: str | None = None
    confidence: float | None = None
    reason: str
    source_excerpt: str | None = None


class HouseholdSinkingFund(BaseModel):
    name: str
    monthly_target: float
    annual_cost: float
    rationale: str


class HouseholdRetirementContributionTracker(BaseModel):
    status: str
    monthly_target: float | None = None
    estimated_monthly_contributions: float = 0.0
    monthly_gap: float = 0.0
    detail: str


class HouseholdRetirementScenario(BaseModel):
    name: str
    monthly_spend: float
    annual_spend: float
    funded_years: float
    readiness: str
    detail: str


class ImportFormat(BaseModel):
    label: str
    formats: list[str] = Field(default_factory=list)
    extracts: list[str] = Field(default_factory=list)


class ImportCenter(BaseModel):
    headline: str
    tracked_documents: int = 0
    parsed_documents: int = 0
    suggested_first_uploads: list[str] = Field(default_factory=list)
    automations: list[str] = Field(default_factory=list)
    supported_documents: list[ImportFormat] = Field(default_factory=list)


class HouseholdEvidenceAccount(BaseModel):
    id: str
    document_id: str
    household_account_id: str | None = None
    source_type: str
    asset_group: str
    account_type: str
    institution_name: str | None = None
    account_name: str | None = None
    account_mask: str | None = None
    owner_name: str | None = None
    currency: str | None = None
    balance: float | None = None
    holdings_value: float | None = None
    cash_balance: float | None = None
    as_of_date: str | None = None
    confidence: float | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HouseholdTrackedAccount(BaseModel):
    id: str
    household_account_id: str | None = None
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdTrackedAccountInput(BaseModel):
    household_account_id: str | None = None
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None


class HouseholdAccountGap(BaseModel):
    code: str
    severity: str
    title: str
    detail: str


class HouseholdAccountSummary(BaseModel):
    id: str
    household_account_id: str | None = None
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None
    currency: str | None = None
    current_value: float | None = None
    balance: float | None = None
    holdings_value: float | None = None
    cash_balance: float | None = None
    valuation_source: str | None = None
    evidence_count: int = 0
    document_ids: list[str] = Field(default_factory=list)
    latest_document_id: str | None = None
    source_types: list[str] = Field(default_factory=list)
    linked_portfolio_account_id: str | None = None
    linked_portfolio_account_name: str | None = None
    tracked_account_id: str | None = None
    account_origin: str = "evidence"
    money_role: str = "net_worth_only"
    last_evidence_at: str | None = None
    days_since_evidence: int | None = None
    last_balance_at: str | None = None
    days_since_balance: int | None = None
    balance_freshness_status: str = "needs_evidence"
    balance_freshness_label: str = "Needs evidence"
    last_transaction_at: str | None = None
    days_since_transaction: int | None = None
    transaction_freshness_status: str = "needs_evidence"
    transaction_freshness_label: str = "Needs evidence"
    quote_updated_at: str | None = None
    quote_freshness_status: str = "not_applicable"
    quote_freshness_label: str = "No live quotes"
    quote_source: str | None = None
    priced_position_count: int = 0
    freshness_status: str
    freshness_label: str
    match_status: str
    match_confidence: float | None = None
    gap_flags: list[HouseholdAccountGap] = Field(default_factory=list)


class HouseholdInboxItem(BaseModel):
    id: str
    category: str
    priority: str
    title: str
    detail: str
    action_label: str
    action_href: str | None = None
    related_account_id: str | None = None
    related_question_id: str | None = None
    related_document_ids: list[str] = Field(default_factory=list)
    # Canonical metrics this item degrades (e.g. "safe_to_spend", "budget_status",
    # "monthly_spend", "net_worth") so surfaces can filter by what an item blocks
    # instead of substring-matching the human detail text.
    affects: list[str] = Field(default_factory=list)


class HouseholdDiscoveredAccount(BaseModel):
    key: str
    institution: str
    partial_account: str | None = None
    suggested_label: str
    asset_group: str
    account_type: str
    source_type: str
    confidence: float = 0.0
    occurrence_count: int = 1
    sample_description: str | None = None
    detail: str


class HouseholdDocument(BaseModel):
    id: str
    filename: str
    source_type: str
    document_type: str
    status: str
    account_label: str | None = None
    file_size_bytes: int
    content_type: str | None = None
    classification_confidence: float | None = None
    review_status: str | None = None
    review_summary: str | None = None
    review_confidence: float | None = None
    statement_start: str | None = None
    statement_end: str | None = None
    uploaded_at: str
    parsed_at: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HouseholdDocumentReview(BaseModel):
    id: str
    document_id: str
    status: str
    summary: str | None = None
    confidence: float | None = None
    extracted_text: str | None = None
    structured_data: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class HouseholdDocumentList(BaseModel):
    items: list[HouseholdDocument] = Field(default_factory=list)


class HouseholdQuestion(BaseModel):
    id: str
    field_name: str | None = None
    status: str
    priority: str
    question: str
    rationale: str | None = None
    recommendation: str | None = None
    answer_text: str | None = None
    source_document_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    question_format: str = "short_text"
    options: list[str] | None = None
    direction: str = "jenny_to_user"
    created_at: str
    answered_at: str | None = None


class HouseholdQuestionList(BaseModel):
    items: list[HouseholdQuestion] = Field(default_factory=list)


class JennyNeed(BaseModel):
    id: str
    need_type: str  # "provide" | "confirm" | "set" | "review"
    title: str
    detail: str
    priority: str  # "critical" | "high" | "medium" | "low"
    status: str  # "unsatisfied" | "satisfied"
    recurrence: str  # "periodic" | "one_time" | "as_needed"
    satisfaction_detail: str | None = None
    action_href: str | None = None
    related_question_id: str | None = None
    field_name: str | None = None
    question_format: str | None = None
    options: list[str] | None = None


class HouseholdConfirmedFact(BaseModel):
    fact_key: str
    fact_value: str
    confirmed_at: str


class ConfirmFactRequest(BaseModel):
    fact_key: str
    fact_value: str


class JennyProgression(BaseModel):
    found: list[str] = Field(default_factory=list)
    working_on: str | None = None


class JennyMoneyBrief(BaseModel):
    headline: str
    body: str
    prompts: list[str] = Field(default_factory=list)
    progression: JennyProgression | None = None


class PortfolioHouseholdContext(BaseModel):
    total_portfolio_value: float | None = None
    cash_reserves_months: float | None = None
    portfolio_to_annual_spend_ratio: float | None = None
    insights: list[str] = Field(default_factory=list)


class HouseholdPurchaseItemCategoryUpdate(BaseModel):
    category: str
    essentiality: str
    apply_to_product: bool = False


# Wire keys on every purchase/product model stay digit-free: the frontend
# camelization layer (es-toolkit) splits camelCase at letter/digit boundaries.


class HouseholdPurchaseItem(BaseModel):
    id: str
    transaction_id: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    product_match_status: str = "unmatched"
    product_match_confidence: float | None = None
    purchase_date: str | None = None
    merchant: str | None = None
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float
    allocated_amount: float | None = None
    category: str
    essentiality: str
    categorization_source: str = "suggested"


class HouseholdProductPricePoint(BaseModel):
    observed_date: str
    merchant: str | None = None
    total_price: float
    quantity: float | None = None
    unit_price: float | None = None
    source: str


class HouseholdProductSummary(BaseModel):
    id: str
    canonical_name: str
    brand: str | None = None
    package_display_label: str | None = None
    image_url: str | None = None
    purchase_count: int = 0
    observation_count: int = 0
    needs_review_count: int = 0
    first_observed_date: str | None = None
    last_observed_date: str | None = None
    latest_price: float | None = None
    latest_unit_price: float | None = None
    latest_merchant: str | None = None
    # Most recent observations, oldest first, capped server-side — the
    # sparkline + hover tooltip payload.
    price_points: list[HouseholdProductPricePoint] = Field(default_factory=list)


class HouseholdProductList(BaseModel):
    generated_at: str
    total_count: int = 0
    needs_review_total: int = 0
    offset: int = 0
    limit: int = 0
    returned_count: int = 0
    products: list[HouseholdProductSummary] = Field(default_factory=list)


class HouseholdProductIdentifier(BaseModel):
    kind: str
    value: str


class HouseholdProductDetail(BaseModel):
    generated_at: str
    product: HouseholdProductSummary
    identifiers: list[HouseholdProductIdentifier] = Field(default_factory=list)
    observations: list[HouseholdProductPricePoint] = Field(default_factory=list)
    recent_items: list[HouseholdPurchaseItem] = Field(default_factory=list)


class HouseholdPurchaseItemReviewQueue(BaseModel):
    generated_at: str
    total_count: int = 0
    items: list[HouseholdPurchaseItem] = Field(default_factory=list)


class HouseholdPurchaseItemProductAssignment(BaseModel):
    action: str  # confirm | reassign | detach
    product_id: str | None = None


class HouseholdProductMergeRequest(BaseModel):
    source_product_id: str
    target_product_id: str


class HouseholdPriceCheckVendorStatus(BaseModel):
    vendor_key: str
    status: str  # ok | blocked | error | skipped
    quote_count: int = 0
    error: str | None = None


class HouseholdPriceCheckRun(BaseModel):
    id: str
    status: str  # queued | running | completed | completed_with_errors | failed
    triggered_by: str = "manual"
    product_count: int = 0
    quote_count: int = 0
    finding_count: int = 0
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    vendors: list[HouseholdPriceCheckVendorStatus] = Field(default_factory=list)


class HouseholdPriceFinding(BaseModel):
    id: str
    kind: str  # cheaper_elsewhere | savings_rollup
    status: str = "open"
    product_id: str | None = None
    product_name: str | None = None
    vendor_key: str | None = None
    savings_estimate: float | None = None
    household_price: float | None = None
    vendor_price: float | None = None
    vendor_url: str | None = None
    detail: str | None = None
    created_at: str | None = None


class HouseholdPriceCheckStatus(BaseModel):
    generated_at: str
    latest_run: HouseholdPriceCheckRun | None = None
    open_findings: list[HouseholdPriceFinding] = Field(default_factory=list)


class HouseholdPriceCheckTriggerResponse(BaseModel):
    run_id: str
    already_running: bool = False
