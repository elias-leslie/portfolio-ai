import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdDocumentsMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdDocuments: () => useHouseholdDocumentsMock(),
}))

vi.mock('@/components/money/MoneyOverviewPanel', () => ({
  MoneyOverviewPanel: () => <div>Money Overview Panel</div>,
}))
vi.mock('@/components/money/MoneyAccountsPanel', () => ({
  MoneyAccountsPanel: () => <div>Money Accounts Panel</div>,
}))
vi.mock('@/components/money/MoneyInboxPanel', () => ({
  MoneyInboxPanel: () => <div>Money Inbox Panel</div>,
}))
vi.mock('@/components/money/HouseholdDocumentCenter', () => ({
  HouseholdDocumentCenter: () => <div>Document Center</div>,
}))
vi.mock('@/components/money/HouseholdProfileCard', () => ({
  HouseholdProfileCard: () => <div>Profile Card</div>,
}))
vi.mock('@/components/money/HouseholdPlanningPanels', () => ({
  HouseholdPlanningPanels: () => <div>Planning Panels</div>,
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
      trackedAccountCount: 3,
      needsRefreshCount: 1,
      candidateAccountCount: 1,
      gapCount: 2,
      inboxCount: 2,
      coverageMonths: 3,
      lastTransactionDate: '2026-03-09',
      visibilityScore: 88,
      visibilityLabel: 'Strong household visibility',
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
        lastEvidenceAt: '2026-03-09T00:00:00Z',
        daysSinceEvidence: 1,
        freshnessStatus: 'fresh',
        freshnessLabel: 'Fresh',
        matchStatus: 'tracked',
        matchConfidence: 0.92,
        gapFlags: [],
      },
    ],
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
        actionHref: '/money?tab=inbox',
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

    expect(screen.getByText('Next Up')).toBeInTheDocument()
    expect(screen.getByText('Refresh Chase Amazon card')).toBeInTheDocument()
    expect(screen.getByText('Net Worth')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Overview/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Accounts/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Inbox/i })).toBeInTheDocument()
    expect(screen.getByText('Money Overview Panel')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Action' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/stage 4 of 4/i)).not.toBeInTheDocument()
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
})
