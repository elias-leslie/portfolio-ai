import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import {
  useAccounts,
  useAddPosition,
  useCreateAccount,
} from '@/lib/hooks/usePortfolio'

vi.mock('@/components/portfolio/PortfolioOverview', () => ({
  PortfolioOverview: () => <div>Portfolio Overview</div>,
}))

vi.mock('@/components/portfolio/AccountsWithPositions', () => ({
  AccountsWithPositions: ({
    onAddAccount,
    onAddPosition,
  }: {
    onAddAccount?: () => void
    onAddPosition?: (accountId?: string) => void
  }) => (
    <div>
      <button type="button" onClick={onAddAccount}>
        Open Add Account
      </button>
      <button type="button" onClick={() => onAddPosition?.('acct-2')}>
        Open Add Position
      </button>
      <button type="button" onClick={() => onAddPosition?.()}>
        Open Generic Add Position
      </button>
    </div>
  ),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAccounts: vi.fn(),
  useAddPosition: vi.fn(),
  useCreateAccount: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const mockUseAccounts = useAccounts as unknown as Mock
const mockUseAddPosition = useAddPosition as unknown as Mock
const mockUseCreateAccount = useCreateAccount as unknown as Mock

describe('PortfolioPage', () => {
  const addPositionMutate = vi.fn()
  const createAccountMutate = vi.fn()

  beforeEach(() => {
    addPositionMutate.mockReset()
    createAccountMutate.mockReset()

    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
        {
          id: 'acct-2',
          name: 'Roth IRA',
          accountType: 'Roth',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseAddPosition.mockReturnValue({
      mutate: addPositionMutate,
      isPending: false,
    })
    mockUseCreateAccount.mockReturnValue({
      mutate: createAccountMutate,
      isPending: false,
    })
  })

  it('submits a normalized account name from the add-account dialog', async () => {
    const user = userEvent.setup()
    createAccountMutate.mockImplementation(
      (
        _payload: unknown,
        options?: { onSuccess?: () => void; onError?: (error: Error) => void },
      ) => {
        options?.onSuccess?.()
      },
    )

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('button', { name: 'Open Add Account' }))
    await user.type(screen.getByLabelText('Account Name'), '  Joint   Brokerage  ')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    expect(createAccountMutate).toHaveBeenCalledWith(
      {
        name: 'Joint Brokerage',
        accountType: 'Taxable',
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    )
  })

  it('normalizes symbol and keeps the requested account when adding a position', async () => {
    const user = userEvent.setup()
    addPositionMutate.mockImplementation(
      (
        _payload: unknown,
        options?: { onSuccess?: () => void; onError?: (error: Error) => void },
      ) => {
        options?.onSuccess?.()
      },
    )

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('button', { name: 'Open Add Position' }))
    await user.type(screen.getByLabelText('Symbol'), ' msft ')
    await user.type(screen.getByLabelText('Shares'), '10')
    await user.type(screen.getByLabelText('Cost Basis (per share)'), '123.45')
    await user.click(screen.getByRole('button', { name: 'Add Position' }))

    expect(addPositionMutate).toHaveBeenCalledWith(
      {
        accountId: 'acct-2',
        symbol: 'MSFT',
        shares: 10,
        costBasis: 123.45,
        positionType: 'long',
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    )
  })

  it('preselects the only account for the generic add-position action', async () => {
    const user = userEvent.setup()
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
      ],
      isLoading: false,
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(
      screen.getByRole('button', { name: 'Open Generic Add Position' }),
    )

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Account' })).toHaveTextContent(
        'Brokerage (Taxable)',
      )
    })
  })
})
