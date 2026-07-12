import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { buildHouseholdDashboard } from './householdDashboardFixture'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdDocumentsMock = vi.fn()
const useHouseholdFactsMock = vi.fn()
const useHouseholdLedgerMock = vi.fn()
const useAnswerHouseholdQuestionMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdDocuments: () => useHouseholdDocumentsMock(),
  useHouseholdFacts: () => useHouseholdFactsMock(),
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
  HouseholdDocumentCenter: ({
    focusedReview,
    dateQualityIssues = [],
  }: {
    focusedReview?: boolean
    dateQualityIssues?: unknown[]
  }) => (
    <div>
      Document Center
      {focusedReview ? <span>Date quality focused</span> : null}
      {dateQualityIssues.length > 0 ? (
        <span>Date quality issues: {dateQualityIssues.length}</span>
      ) : null}
    </div>
  ),
}))
vi.mock('@/components/money/MoneyAssumptionsDrawer', () => ({
  MoneyAssumptionsDrawer: ({
    planningContent,
  }: {
    planningContent?: unknown
  }) => (
    <div>
      Assumptions Drawer
      {planningContent as any}
    </div>
  ),
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

describe('MoneyPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/money')
    useAnswerHouseholdQuestionMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    useHouseholdDashboardMock.mockReturnValue({
      data: buildHouseholdDashboard(),
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
    useHouseholdFactsMock.mockReturnValue({
      data: [],
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

    expect(screen.getByRole('tab', { name: 'Accounts' }).textContent).toBe(
      'Accounts3',
    )
    expect(screen.queryByText('Coverage')).not.toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /add anything/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Budget/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Levers/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Retirement/i })).toBeInTheDocument()
    // Allocation folded into the Dashboard tab — no standalone tab anymore.
    expect(
      screen.queryByRole('tab', { name: /Allocation/i }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Accounts/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Intake/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Review/i })).toBeInTheDocument()
    expect(screen.getByText('Money Overview Panel')).toBeInTheDocument()
    expect(screen.queryByText('Net Worth')).not.toBeInTheDocument()
    expect(screen.queryByText('Fix Money Data')).not.toBeInTheDocument()
  })

  it('keeps missing-data asks out of the money dashboard', async () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        ...buildHouseholdDashboard(),
        overview: {
          ...buildHouseholdDashboard().overview,
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

    await user.click(screen.getByRole('tab', { name: 'Intake' }))
    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(refetchDocuments).toHaveBeenCalled()
  })

  it('opens intake from the intake tab query param', async () => {
    window.history.replaceState({}, '', '/money?tab=intake')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Document Center')).toBeInTheDocument()
  })

  it('opens spending from the spending tab query param', async () => {
    window.history.replaceState({}, '', '/money?tab=spending')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money Budget Panel')).toBeInTheDocument()
  })

  it('opens ledger from the ledger tab query param', async () => {
    window.history.replaceState({}, '', '/money?tab=ledger')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Money Ledger Panel')).toBeInTheDocument()
  })

  it('keeps planning-only document requirements out of the default money intake flow', async () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        ...buildHouseholdDashboard(),
        planning: {
          ...buildHouseholdDashboard().planning,
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

  it('passes date-quality issues to intake without requiring the focus param', async () => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        ...buildHouseholdDashboard(),
        transactionDateIssues: [
          {
            id: 'future-date-1',
            transactionId: 'txn-1',
            documentId: 'doc-1',
            filename: 'walmart-order.pdf',
            sourceType: 'receipt',
            documentType: 'receipt',
            transactionDate: '2026-09-03',
            uploadedAt: '2026-03-09',
            merchant: 'Walmart',
            description: 'Walmart receipt',
            amount: 164.14,
            accountLabel: 'Visa Credit ****4635',
            confidence: 0.9,
            reason: 'Extracted transaction date is after today.',
            sourceExcerpt: '09/03/2026 Order details - Walmart.com',
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })
    window.history.replaceState({}, '', '/money?tab=intake')
    const { default: MoneyPage } = await import('../money/page')

    render(<MoneyPage />)

    expect(screen.getByText('Date quality issues: 1')).toBeInTheDocument()
    expect(screen.queryByText('Date quality focused')).not.toBeInTheDocument()
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
