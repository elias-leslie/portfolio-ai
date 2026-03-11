import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import { AccountsWithPositionsContent } from '../AccountsWithPositions'
import {
  useAccounts,
  useDeleteAccount,
  useDeletePosition,
  usePortfolio,
  useUpdatePosition,
} from '@/lib/hooks/usePortfolio'
import { AccountsWithPositions } from '../AccountsWithPositions'

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAccounts: vi.fn(),
  usePortfolio: vi.fn(),
  useDeleteAccount: vi.fn(),
  useDeletePosition: vi.fn(),
  useUpdatePosition: vi.fn(),
}))

const mockUseAccounts = useAccounts as unknown as Mock
const mockUsePortfolio = usePortfolio as unknown as Mock
const mockUseDeleteAccount = useDeleteAccount as unknown as Mock
const mockUseDeletePosition = useDeletePosition as unknown as Mock
const mockUseUpdatePosition = useUpdatePosition as unknown as Mock

describe('AccountsWithPositions', () => {
  beforeEach(() => {
    mockUsePortfolio.mockReturnValue({
      data: { positions: [], cashBalanceTotal: 0, totalValue: 0, totalCostBasis: 0, totalGain: 0, totalGainPct: 0 },
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
      screen.getByText(/No accounts yet\. Click "Add Account"/i),
    ).toBeVisible()
  })

  it('shows cash-only accounts without treating them as empty', () => {
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Roth IRA',
          accountType: 'Roth',
          cashBalance: 47880.13,
          createdAt: '2026-03-07T00:00:00Z',
          updatedAt: '2026-03-07T00:00:00Z',
        },
      ],
      isLoading: false,
    })

    render(<AccountsWithPositions />)

    expect(screen.getByText('Roth IRA')).toBeVisible()
    expect(screen.getByText('$47,880.13')).toBeVisible()
    expect(screen.getByText(/Cash \$47,880\.13/)).toBeVisible()
    expect(screen.queryByText(/No positions in this account yet/i)).not.toBeInTheDocument()
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

    expect(screen.getByText(/failed to load portfolio accounts/i)).toBeInTheDocument()
    expect(retryAccounts).toHaveBeenCalled()
  })
})
