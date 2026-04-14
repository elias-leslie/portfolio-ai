import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdDocumentsMock = vi.fn()
const useHouseholdLedgerMock = vi.fn()
const useAnswerHouseholdQuestionMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdDocuments: () => useHouseholdDocumentsMock(),
  useHouseholdLedger: () => useHouseholdLedgerMock(),
  useAnswerHouseholdQuestion: () => useAnswerHouseholdQuestionMock(),
}))

vi.mock('@/components/money/MoneyOverviewPanel', () => ({
  MoneyOverviewPanel: () => <div>Money Overview Panel</div>,
}))
vi.mock('@/components/money/MoneyAccountsPanel', () => ({
  MoneyAccountsPanel: ({
    focus,
    selectedAccountId,
    intent,
  }: {
    focus?: string | null
    selectedAccountId?: string | null
    intent?: string | null
  }) => (
    <div>
      Money Accounts Panel
      {focus === 'coverage' ? <span>Account coverage focused</span> : null}
      {focus === 'discovered' ? <span>Discovered accounts focused</span> : null}
      {selectedAccountId ? (
        <span>Selected account: {selectedAccountId}</span>
      ) : null}
      {intent ? <span>Account intent: {intent}</span> : null}
    </div>
  ),
}))
vi.mock('@/components/money/HouseholdDocumentCenter', () => ({
  HouseholdDocumentCenter: ({ focusedReview }: { focusedReview?: boolean }) => (
    <div>
      Document Center
      {focusedReview ? <span>Date quality focused</span> : null}
    </div>
  ),
}))
vi.mock('@/components/money/HouseholdProfileCard', () => ({
  HouseholdProfileCard: () => <div>Profile Card</div>,
}))
vi.mock('@/components/money/MoneyLedgerPanel', () => ({
  MoneyLedgerPanel: () => <div>Money Ledger Panel</div>,
}))
vi.mock('@/components/money/MoneySpendingPanel', () => ({
  MoneySpendingPanel: () => <div>Money Spending Panel</div>,
}))
vi.mock('@/components/money/HouseholdPlanningPanels', () => ({
  HouseholdPlanningPanels: ({
    focusedSection,
  }: {
    focusedSection?: string | null
  }) => (
    <div>
      Planning Panels
      {focusedSection ? <span>Planning focus: {focusedSection}</span> : null}
    </div>
  ),
}))

function buildDashboard() {
  return {
    generatedAt: '2026-03-10T00:00:00Z',
    overview: {
      investedAssets: 22500,
      retirementAssets: 10000,
      taxableAssets: 12500,
      cashReserve: 6000,
      totalTrackedAssets: 28500,
      liabilitiesTotal: 2500,
      netWorth: 26000,
      netWorthStatus: 'current',
      netWorthDetail: '$28,500 assets less $2,500 liabilities.',
      trackedAccountCount: 3,
      needsRefreshCount: 1,
      candidateAccountCount: 1,
      gapCount: 2,
      inboxCount: 2,
      coverageMonths: 3,
      lastTransactionDate: '2026-03-09',
      visibilityScore: 88,
      visibilityLabel: 'Strong household visibility',
      monthlySpendStatus: 'current',
      monthlySpendDetail: '3 months of recent evidence coverage.',
      nextBestAction: 'Refresh Chase Amazon card',
    },
    profile: {
      id: 'profile-1',
      householdName: 'Household',
      monthlyNetIncomeTarget: 10000,
      monthlyEssentialTarget: 4000,
      monthlyDiscretionaryTarget: 1500,
      monthlySavingsTarget: 2000,
      targetRetirementAge: 60,
      targetRetirementSpend: 5000,
      notes: null,
      createdAt: '2026-03-10T00:00:00Z',
      updatedAt: '2026-03-10T00:00:00Z',
    },
    resolvedValues: [],
    budgetReadiness: {
      status: 'ready_for_budgeting',
      summary: 'Ready',
      priorities: [],
      missingInputs: [],
      starterLanes: [],
    },
    budgetSnapshot: {
      status: 'on_track',
      summary: 'On track',
      monthlyIncomeTarget: 10000,
      monthlyPlanTotal: 7500,
      essentialTarget: 4000,
      discretionaryTarget: 1500,
      savingsTarget: 2000,
      actualMonthlySpend: 5200,
      actualEssentialMonthlySpend: 3400,
      actualDiscretionaryMonthlySpend: 1800,
      monthToDateSpend: 2400,
      monthToDatePlan: 2500,
      paceStatus: 'on_track',
      paceDetail: 'On track.',
      remainingCashAfterPlan: 2500,
      discretionaryHeadroom: -300,
    },
    retirementPreparedness: {
      status: 'baseline_visible',
      summary: 'Visible',
      retirementAccountShare: 42,
      strengths: [],
      blockers: [],
      nextSteps: [],
    },
    jennyNeeds: [],
    reports: {
      executive: {
        headline: 'Ledger ready',
        summary: 'Summary',
        averageMonthlySpend: 5200,
        averageMonthlyEssentials: 3400,
        averageMonthlyDiscretionary: 1800,
        recent30DaySpend: 4900,
        recurringMerchantCount: 4,
        trackedExpenseCount: 24,
        coverageMonths: 3,
      },
      categoryBreakdown: [],
      merchantHighlights: [],
      monthlySpendTrend: [],
      recentTransactions: [],
    },
    categorizationQueue: [],
    recurringCommitments: [],
    transactionDateIssues: [],
    sinkingFunds: [],
    retirementContributionTracker: {
      status: 'gap',
      monthlyTarget: 2000,
      estimatedMonthlyContributions: 1000,
      monthlyGap: 1000,
      detail: 'Gap remains.',
    },
    retirementScenarios: [],
    importCenter: {
      headline: 'Import',
      trackedDocuments: 2,
      parsedDocuments: 2,
      suggestedFirstUploads: [],
      automations: [],
      supportedDocuments: [],
    },
    evidenceAccounts: [],
    accounts: [
      {
        id: 'account-1',
        label: 'Fidelity · Brokerage',
        assetGroup: 'taxable',
        accountType: 'brokerage',
        sourceType: 'brokerage',
        institutionName: 'Fidelity',
        ownerName: null,
        currency: 'USD',
        currentValue: 12500,
        balance: 12500,
        holdingsValue: 12000,
        cashBalance: 500,
        evidenceCount: 2,
        documentIds: ['doc-1'],
        latestDocumentId: 'doc-1',
        sourceTypes: ['brokerage'],
        linkedPortfolioAccountId: null,
        linkedPortfolioAccountName: null,
        trackedAccountId: null,
        accountOrigin: 'evidence',
        moneyRole: 'net_worth_only',
        lastEvidenceAt: '2026-03-09T00:00:00Z',
        daysSinceEvidence: 1,
        lastBalanceAt: '2026-03-09T00:00:00Z',
        daysSinceBalance: 1,
        balanceFreshnessStatus: 'fresh',
        balanceFreshnessLabel: 'Fresh',
        lastTransactionAt: null,
        daysSinceTransaction: null,
        transactionFreshnessStatus: 'not_applicable',
        transactionFreshnessLabel: 'Not required',
        freshnessStatus: 'fresh',
        freshnessLabel: 'Fresh',
        matchStatus: 'tracked',
        matchConfidence: 0.92,
        gapFlags: [],
      },
    ],
    discoveredAccounts: [],
    inbox: [
      {
        id: 'inbox-1',
        category: 'account',
        priority: 'high',
        title: 'Refresh Chase Amazon card',
        detail: 'This account is getting stale.',
        actionLabel: 'Add evidence',
        actionHref: '/money?tab=intake',
        relatedAccountId: 'account-2',
        relatedQuestionId: null,
        relatedDocumentIds: [],
      },
      {
        id: 'inbox-2',
        category: 'question',
        priority: 'medium',
        title: 'Is this your main checking account?',
        detail: 'Jenny needs to know if it drives recurring bills.',
        actionLabel: 'Answer',
        actionHref:
          '/money?tab=review&focus=clarifications#money-clarifications',
        relatedAccountId: null,
        relatedQuestionId: 'question-1',
        relatedDocumentIds: ['doc-2'],
      },
    ],
    questions: [],
    jennyBrief: {
      headline: 'Jenny',
      body: 'Body',
      prompts: [],
    },
    planning: {
      summary: {
        completionScore: 0,
        missingDocumentCount: 0,
        readyForReview: false,
      },
      members: [],
      incomeSources: [],
      housingPlan: null,
      debtObligations: [],
      insuranceCoverage: [],
      taxProfile: null,
      recurringBills: [],
      plannedExpenses: [],
      documentRequirements: [],
    },
  }
}

describe('MoneyPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/money')
    useAnswerHouseholdQuestionMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    useHouseholdDashboardMock.mockReturnValue({
      data: buildDashboard(),
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    useHouseholdDocumentsMock.mockReturnValue({
      data: { items: [] },
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    useHouseholdLedgerMock.mockReturnValue({
      data: {
        generatedAt: '2026-03-10T00:00:00Z',
        transactionCount: 12,
        importRowCount: 6,
        entries: [],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('offers retry when the household workspace fails to load', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    useHouseholdDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('down'),
      refetch,
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    await user.click(screen.getByRole('button', { name: 'Retry workspace' }))

    expect(refetch).toHaveBeenCalled()
  })

  it('renders the simplified summary and overview-first tabs', async () => {
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByRole('button', { name: 'Accounts' }).textContent).toBe(
      'Accounts3',
    )
    expect(screen.queryByText('Coverage')).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /add anything/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Dashboard/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Spending/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Levers/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Allocation/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Accounts/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Intake/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review/i })).toBeInTheDocument()
    expect(screen.getByText('Money Overview Panel')).toBeInTheDocument()
    expect(screen.queryByText('Net Worth')).not.toBeInTheDocument()
    expect(screen.queryByText('Fix Money Data')).not.toBeInTheDocument()
  })

  it('keeps missing-data asks out of the money dashboard', async () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        ...buildDashboard(),
        overview: {
          ...buildDashboard().overview,
          monthlySpendStatus: 'estimated',
          monthlySpendDetail:
            'Monthly spend estimate: 1 spending account missing transactions.',
        },
        inbox: [
          {
            id: 'account-main-checking-missing_transaction_history',
            category: 'account',
            priority: 'high',
            title: 'Add statements for Main Checking',
            detail:
              'Jenny has some account evidence here but not enough linked transaction history to trust cash-flow calculations.',
            actionLabel: 'Add statements',
            actionHref: '/money?tab=intake',
            relatedAccountId: 'account-1',
            relatedQuestionId: null,
            relatedDocumentIds: ['doc-1'],
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.queryByText('Fix Money Data')).not.toBeInTheDocument()
    expect(
      screen.queryByText('Add statements for Main Checking'),
    ).not.toBeInTheDocument()
  })

  it('shows retry for the intake tab when document loading fails', async () => {
    const user = userEvent.setup()
    const refetchDocuments = vi.fn()
    useHouseholdDocumentsMock.mockReturnValue({
      data: undefined,
      isFetching: false,
      error: new Error('docs down'),
      refetch: refetchDocuments,
    })

    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    await user.click(screen.getByRole('button', { name: 'Intake' }))
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(refetchDocuments).toHaveBeenCalled()
  })

  it('opens intake from the intake tab query param', async () => {
    window.history.replaceState({}, '', '/money?tab=intake')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Document Center')).toBeInTheDocument()
  })

  it('keeps planning-only document requirements out of the default money intake flow', async () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        ...buildDashboard(),
        planning: {
          ...buildDashboard().planning,
          documentRequirements: [
            {
              id: 'req-tax',
              requirementKey: 'core-tax-return',
              documentKind: 'tax_return',
              label: 'Most recent tax return',
              status: 'missing',
              priority: 'high',
              relatedSection: 'taxes',
              relatedRecordId: null,
              rationale: 'Needed for taxes.',
              notes: null,
              source: 'system',
              satisfiedByDocumentId: null,
              createdAt: '2026-04-01T00:00:00Z',
              updatedAt: '2026-04-01T00:00:00Z',
            },
          ],
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    window.history.replaceState({}, '', '/money?tab=intake')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Document Center')).toBeInTheDocument()
  })

  it('focuses the date-quality evidence review from the focus query param', async () => {
    window.history.replaceState({}, '', '/money?tab=intake&focus=date-quality')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Document Center')).toBeInTheDocument()
    expect(screen.getByText('Date quality focused')).toBeInTheDocument()
  })

  it('opens the accounts tab with account coverage focus from the focus query param', async () => {
    window.history.replaceState(
      {},
      '',
      '/money?tab=accounts&focus=account-coverage',
    )
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money Accounts Panel')).toBeInTheDocument()
    expect(screen.getByText('Account coverage focused')).toBeInTheDocument()
  })

  it('opens the accounts tab with discovered-account focus from the focus query param', async () => {
    window.history.replaceState(
      {},
      '',
      '/money?tab=accounts&focus=discovered-accounts',
    )
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money Accounts Panel')).toBeInTheDocument()
    expect(screen.getByText('Discovered accounts focused')).toBeInTheDocument()
  })

  it('opens the accounts tab on the exact account upload step from query params', async () => {
    window.history.replaceState(
      {},
      '',
      '/money?tab=accounts&account=evidence%7Ccash-management%7Cbrokerage&intent=evidence',
    )
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money Accounts Panel')).toBeInTheDocument()
    expect(
      screen.getByText('Selected account: evidence|cash-management|brokerage'),
    ).toBeInTheDocument()
    expect(screen.getByText('Account intent: evidence')).toBeInTheDocument()
  })

  it('opens the review tab from the clarification route', async () => {
    window.history.replaceState(
      {},
      '',
      '/money?tab=review&focus=clarifications#money-clarifications',
    )
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Clarifications')).toBeInTheDocument()
  })

  it('opens focused planning from the utility and focus query params', async () => {
    window.history.replaceState({}, '', '/money?utility=planning&focus=housing')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Planning Panels')).toBeInTheDocument()
    expect(screen.getByText('Planning focus: housing')).toBeInTheDocument()
  })
})
