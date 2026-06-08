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

vi.mock('@/components/home/DailyBriefPanel', () => ({
  DailyBriefPanel: () => <div>Daily Brief Panel</div>,
}))
vi.mock('@/components/portfolio/InvestingMarketPanel', () => ({
  InvestingMarketTrendPanels: () => <div>Today Market Pulse Panel</div>,
}))

vi.mock('@/lib/hooks/useHousehold', async () => {
  const { buildHouseholdDashboard } = await import(
    './householdDashboardFixture'
  )

  return {
    useHouseholdDashboard: () => ({
      data: buildHouseholdDashboard(),
      isLoading: false,
      error: null,
    }),
    useHouseholdDocuments: () => ({
      data: { items: [] },
    }),
    useHouseholdFacts: () => ({
      data: [],
    }),
    useHouseholdLedger: () => ({
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
    }),
  }
})

vi.mock('@/components/money/MoneyOverviewPanel', () => ({
  MoneyOverviewPanel: () => <div>Money Overview Panel</div>,
}))
vi.mock('@/components/money/MoneyAccountsPanel', () => ({
  MoneyAccountsPanel: () => <div>Money Accounts Panel</div>,
}))
vi.mock('@/components/money/MoneyLedgerPanel', () => ({
  MoneyLedgerPanel: () => <div>Money Ledger Panel</div>,
}))
vi.mock('@/components/money/MoneyBudgetPanel', () => ({
  MoneyBudgetPanel: () => <div>Money Budget Panel</div>,
}))
vi.mock('@/components/money/MoneyRetirementPanel', () => ({
  MoneyRetirementPanel: () => <div>Money Retirement Panel</div>,
}))
vi.mock('@/components/money/HouseholdDocumentCenter', () => ({
  HouseholdDocumentCenter: () => <div>Document Center</div>,
}))
vi.mock('@/components/money/MoneyAssumptionsDrawer', () => ({
  MoneyAssumptionsDrawer: () => <div>Assumptions Drawer</div>,
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
    expect(screen.getByText('Daily Brief Panel')).toBeInTheDocument()
    expect(screen.getByText('Today Market Pulse Panel')).toBeInTheDocument()
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
