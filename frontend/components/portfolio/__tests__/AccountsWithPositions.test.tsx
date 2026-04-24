import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import {
  useAccounts,
  useDeleteAccount,
  useDeletePosition,
  usePortfolio,
  useUpdatePosition,
} from '@/lib/hooks/usePortfolio'
import {
  AccountsWithPositions,
  AccountsWithPositionsContent,
} from '../AccountsWithPositions'

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAccounts: vi.fn(),
  usePortfolio: vi.fn(),
  useDeleteAccount: vi.fn(),
  useDeletePosition: vi.fn(),
  useUpdatePosition: vi.fn(),
}))
vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: vi.fn(),
}))

const mockUseAccounts = useAccounts as unknown as Mock
const mockUsePortfolio = usePortfolio as unknown as Mock
const mockUseDeleteAccount = useDeleteAccount as unknown as Mock
const mockUseDeletePosition = useDeletePosition as unknown as Mock
const mockUseUpdatePosition = useUpdatePosition as unknown as Mock
const mockUseHouseholdDashboard = useHouseholdDashboard as unknown as Mock

describe('AccountsWithPositions', () => {
  beforeEach(() => {
    mockUsePortfolio.mockReturnValue({
      data: {
        positions: [],
        cashBalanceTotal: 0,
        totalValue: 0,
        totalCostBasis: 0,
        totalGain: 0,
        totalGainPct: 0,
      },
      isLoading: false,
    })
    mockUseDeleteAccount.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
    mockUseDeletePosition.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
    mockUseUpdatePosition.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    mockUseHouseholdDashboard.mockReturnValue({
      data: null,
      isLoading: false,
    })
  })

  it('renders skeleton while accounts or portfolio are loading', () => {
    mockUseAccounts.mockReturnValue({
      data: undefined,
      isLoading: true,
    })
    mockUsePortfolio.mockReturnValue({
      data: undefined,
      isLoading: true,
    })

    render(<AccountsWithPositions />)

    expect(
      screen.getByTestId('accounts-with-positions-skeleton'),
    ).toBeInTheDocument()
  })

  it('shows empty state when no accounts exist', () => {
    mockUseAccounts.mockReturnValue({
      data: [],
      isLoading: false,
    })

    render(<AccountsWithPositions />)

    expect(
      screen.getByText(
        /No accounts yet\. Create one above to start organizing your portfolio\./i,
      ),
    ).toBeVisible()
  })

  it('shows an add-account action in the empty state when a handler is provided', async () => {
    const user = userEvent.setup()
    const handleAddAccount = vi.fn()

    mockUseAccounts.mockReturnValue({
      data: [],
      isLoading: false,
    })

    render(<AccountsWithPositions onAddAccount={handleAddAccount} />)

    await user.click(screen.getByRole('button', { name: 'Add Account' }))

    expect(handleAddAccount).toHaveBeenCalledTimes(1)
  })

  it('shows cash-only accounts without treating them as empty', () => {
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Roth IRA',
          accountType: 'Roth',
          householdAccountId: null,
          householdLinkageState: 'unmapped',
          householdLinkageLabel: 'Unmapped investment account',
          householdLinkageDetail:
            'Included in holdings totals, but Money Accounts has no linked household evidence.',
          cashBalance: 47880.13,
          createdAt: '2026-03-07T00:00:00Z',
          updatedAt: '2026-03-07T00:00:00Z',
        },
      ],
      isLoading: false,
    })

    render(<AccountsWithPositions />)

    expect(screen.getByText('Roth IRA')).toBeVisible()
    expect(screen.getByText('Unmapped investment account')).toBeVisible()
    expect(screen.getByText('$47,880.13')).toBeVisible()
    expect(screen.getByText(/Cash \$47,880\.13/)).toBeVisible()
    expect(
      screen.queryByText(/No positions in this account yet/i),
    ).not.toBeInTheDocument()
  })

  it('prefers linked household account truth when a portfolio account is linked', () => {
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          householdAccountId: 'household-1',
          householdLinkageState: 'linked',
          householdLinkageLabel: 'Linked household account',
          householdLinkageDetail:
            'Money Accounts links this to Individual - TOD. Evidence is fresh.',
          cashBalance: 0,
          createdAt: '2026-03-07T00:00:00Z',
          updatedAt: '2026-03-07T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUsePortfolio.mockReturnValue({
      data: {
        positions: [],
        cashBalanceTotal: 0,
        totalValue: 0,
        totalCostBasis: 0,
        totalGain: 0,
        totalGainPct: 0,
        householdInvestmentAccountsCount: 1,
      },
      isLoading: false,
    })
    mockUseHouseholdDashboard.mockReturnValue({
      data: {
        accounts: [
          {
            id: 'household-1',
            label: 'Individual - TOD',
            assetGroup: 'taxable',
            accountType: 'brokerage',
            sourceType: 'brokerage',
            institutionName: 'Fidelity',
            ownerName: 'Elias',
            accountMask: '5444',
            notes: null,
            currency: 'USD',
            currentValue: 507248.61,
            balance: 507248.61,
            holdingsValue: 506000,
            cashBalance: 1248.61,
            evidenceCount: 1,
            documentIds: ['doc-1'],
            latestDocumentId: 'doc-1',
            sourceTypes: ['brokerage'],
            linkedPortfolioAccountId: 'acct-1',
            linkedPortfolioAccountName: 'Brokerage',
            trackedAccountId: 'tracked-1',
            accountOrigin: 'evidence',
            moneyRole: 'net_worth_only',
            lastEvidenceAt: '2026-04-13T00:00:00Z',
            daysSinceEvidence: 1,
            lastBalanceAt: '2026-04-13T00:00:00Z',
            daysSinceBalance: 1,
            balanceFreshnessStatus: 'fresh',
            balanceFreshnessLabel: 'Fresh',
            lastTransactionAt: null,
            daysSinceTransaction: null,
            transactionFreshnessStatus: 'not_applicable',
            transactionFreshnessLabel: 'Not required',
            freshnessStatus: 'fresh',
            freshnessLabel: 'Fresh',
            matchStatus: 'linked',
            matchConfidence: 0.99,
            gapFlags: [],
          },
        ],
      },
      isLoading: false,
    })

    render(<AccountsWithPositions />)

    expect(screen.getByText('Individual - TOD')).toBeVisible()
    expect(screen.getByText('Linked household account')).toBeVisible()
    expect(screen.getByText('$507,248.61')).toBeVisible()
    expect(screen.getByText(/Cash \$1,248\.61/)).toBeVisible()
  })

  it('explains that unmapped accounts remain included in holdings totals', () => {
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          householdAccountId: null,
          householdLinkageState: 'unmapped',
          householdLinkageLabel: 'Unmapped investment account',
          householdLinkageDetail:
            'Included in holdings totals, but Money Accounts has no linked household evidence.',
          cashBalance: 0,
          createdAt: '2026-03-07T00:00:00Z',
          updatedAt: '2026-03-07T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUsePortfolio.mockReturnValue({
      data: {
        positions: [],
        cashBalanceTotal: 0,
        totalValue: 0,
        totalCostBasis: 0,
        totalGain: 0,
        totalGainPct: 0,
        householdInvestmentAccountsCount: 2,
      },
      isLoading: false,
    })

    render(<AccountsWithPositions />)

    expect(screen.getByText('2 Money investments')).toBeVisible()
    expect(screen.getByText('1 unmapped')).toBeVisible()
  })

  it('shows a top-level add-position action and preselects the only account', async () => {
    const user = userEvent.setup()
    const handleAddPosition = vi.fn()
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          householdAccountId: null,
          cashBalance: 0,
          createdAt: '2026-03-07T00:00:00Z',
          updatedAt: '2026-03-07T00:00:00Z',
        },
      ],
      isLoading: false,
    })

    render(<AccountsWithPositions onAddPosition={handleAddPosition} />)

    await user.click(screen.getByRole('button', { name: 'Add Position' }))

    expect(handleAddPosition).toHaveBeenCalledWith('acct-1')
  })

  it('shows a retryable error state when account data fails', async () => {
    const user = userEvent.setup()
    const retryAccounts = vi.fn()

    render(
      <AccountsWithPositionsContent
        accounts={undefined}
        accountsLoading={false}
        accountsError={new Error('accounts down')}
        onRetryAccounts={retryAccounts}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Retry' }))

    expect(
      screen.getByText(/failed to load portfolio accounts/i),
    ).toBeInTheDocument()
    expect(retryAccounts).toHaveBeenCalled()
  })
})
