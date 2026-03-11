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

vi.mock('@/components/home/AutomationCenter', () => ({
  AutomationCenter: () => <div>Automation Center</div>,
}))

vi.mock('@/components/recommendations/TodayIdeasSection', () => ({
  TodayIdeasSection: () => <div>Today Ideas</div>,
}))

vi.mock('@/components/market/MarketIntelligence', () => ({
  MarketIntelligence: () => <div>Market Intelligence</div>,
}))

vi.mock('@/components/shared/UnifiedNewsIntelligenceCard', () => ({
  UnifiedNewsIntelligenceCard: () => <div>News Card</div>,
}))

vi.mock('@/components/portfolio/PortfolioOverview', () => ({
  PortfolioOverview: () => <div>Portfolio Overview</div>,
}))

vi.mock('@/lib/hooks/useNews', () => ({
  useNewsIntelligence: () => ({
    data: {},
    isLoading: false,
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => ({
    data: {
      generatedAt: '2026-03-10T00:00:00Z',
      overview: {
        investedAssets: 0,
        retirementAssets: 0,
        taxableAssets: 0,
        cashReserve: 0,
        totalTrackedAssets: 0,
        visibilityScore: 60,
        visibilityLabel: 'Good',
        nextBestAction: 'Review uncategorized spending.',
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
        paceDetail: 'Month-to-date spend is tracking close to the plan.',
        remainingCashAfterPlan: 2500,
        discretionaryHeadroom: -300,
      },
      retirementPreparedness: {
        status: 'baseline_visible',
        summary: 'Retirement is visible.',
        retirementAccountShare: 42,
        strengths: [],
        blockers: [],
        nextSteps: [],
      },
      actionItems: [],
      opportunities: [],
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
        trackedDocuments: 0,
        parsedDocuments: 0,
        suggestedFirstUploads: [],
        automations: [],
        supportedDocuments: [],
      },
      questions: [],
      jennyBrief: {
        headline: 'Jenny',
        body: 'Body',
        prompts: [],
      },
    },
    isLoading: false,
    error: null,
  }),
  useHouseholdDocuments: () => ({
    data: { items: [] },
  }),
}))

vi.mock('@/components/money/HouseholdOverviewGrid', () => ({
  HouseholdOverviewGrid: () => <div>Overview Grid</div>,
}))
vi.mock('@/components/money/HouseholdOperationsPanel', () => ({
  HouseholdOperationsPanel: () => <div>Operational Queue</div>,
}))
vi.mock('@/components/money/HouseholdReportsPanel', () => ({
  HouseholdReportsPanel: () => <div>Budget Tracker</div>,
}))
vi.mock('@/components/money/HouseholdDocumentCenter', () => ({
  HouseholdDocumentCenter: () => <div>Document Center</div>,
}))
vi.mock('@/components/money/HouseholdProfileCard', () => ({
  HouseholdProfileCard: () => <div>Profile Card</div>,
}))
vi.mock('@/components/money/HouseholdPlanningPanels', () => ({
  HouseholdPlanningPanels: () => <div>Retirement Preparedness</div>,
}))
vi.mock('@/components/money/JennyMoneyBoard', () => ({
  JennyMoneyBoard: () => <div>Jenny Money Board</div>,
}))

vi.mock('@/components/symbol/SymbolWorkspace', () => ({
  SymbolWorkspace: ({ symbol }: { symbol: string }) => <div>Symbol Workspace {symbol}</div>,
}))

vi.mock('@/components/status/StatusWorkspace', () => ({
  StatusWorkspace: () => <div>Status Workspace</div>,
}))

const replaceMock = vi.fn()

vi.mock('next/navigation', () => ({
  useParams: () => ({ symbol: 'VTI' }),
  usePathname: () => '/today',
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}))

describe('core product routes', () => {
  it('renders the home route shell', async () => {
    const { default: HomePage } = await import('../page')

    render(<HomePage />)

    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Home Action Queue')).toBeInTheDocument()
    expect(screen.getByText('Automation Center')).toBeInTheDocument()
  })

  it('renders the money route shell', async () => {
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money System')).toBeInTheDocument()
    expect(screen.getByText('Operational Queue')).toBeInTheDocument()
    expect(screen.getByText('Planning')).toBeInTheDocument()
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
