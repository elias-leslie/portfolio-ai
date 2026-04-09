import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

class MockIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = '0px'
  readonly thresholds = [0]
  disconnect = vi.fn()
  observe = vi.fn()
  takeRecords = vi.fn(() => [])
  unobserve = vi.fn()
}

global.IntersectionObserver =
  MockIntersectionObserver as unknown as typeof IntersectionObserver

vi.mock('@/components/home/HomeActionQueue', () => ({
  HomeActionQueue: () => <div>Home Action Queue</div>,
}))

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => ({
    data: {
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
      accounts: [],
      inbox: [],
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
    },
    isLoading: false,
    error: null,
  }),
  useHouseholdDocuments: () => ({
    data: { items: [] },
  }),
}))

vi.mock('@/components/money/MoneyOverviewPanel', () => ({
  MoneyOverviewPanel: () => <div>Money Overview Panel</div>,
}))
vi.mock('@/components/money/MoneyAccountsPanel', () => ({
  MoneyAccountsPanel: () => <div>Money Accounts Panel</div>,
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

vi.mock('@/components/symbol/SymbolWorkspace', () => ({
  SymbolWorkspace: ({ symbol }: { symbol: string }) => (
    <div>Symbol Workspace {symbol}</div>
  ),
}))

vi.mock('@/components/status/StatusWorkspace', () => ({
  StatusWorkspace: () => <div>Status Workspace</div>,
}))

const replaceMock = vi.fn()
const redirectMock = vi.fn()

vi.mock('next/navigation', () => ({
  useParams: () => ({ symbol: 'VTI' }),
  usePathname: () => '/today',
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
  redirect: redirectMock,
}))

describe('core product routes', () => {
  it('renders the home route shell', async () => {
    const { default: HomePage } = await import('../page')

    render(<HomePage />)

    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Home Action Queue')).toBeInTheDocument()
    expect(screen.queryByText('Automation Center')).not.toBeInTheDocument()
  })

  it('renders the money route shell', async () => {
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money')).toBeInTheDocument()
    expect(screen.getByText('Money Overview Panel')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Accounts/i }),
    ).toBeInTheDocument()
  })

  it('redirects the legacy watchlist route to investing', async () => {
    const { default: WatchlistPage } = await import('../watchlist/page')

    WatchlistPage()

    expect(redirectMock).toHaveBeenCalledWith('/portfolio?tab=symbols')
  })

  it('renders the symbol route shell', async () => {
    const { default: SymbolPage } = await import('../symbols/[symbol]/page')

    render(<SymbolPage />)

    expect(screen.getByText(/Symbol Workspace VTI/i)).toBeInTheDocument()
  })

  it('renders the status route shell', async () => {
    const { default: StatusPage } = await import('../status/page')

    render(<StatusPage />)

    expect(screen.getByText('Status Workspace')).toBeInTheDocument()
  })
})
