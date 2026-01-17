import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import { useAccounts, useDeleteAccount } from '@/lib/hooks/usePortfolio'
import { AccountsCard } from '../AccountsCard'

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAccounts: vi.fn(),
  useDeleteAccount: vi.fn(),
}))

const mockUseAccounts = useAccounts as unknown as Mock
const mockUseDeleteAccount = useDeleteAccount as unknown as Mock

describe('AccountsCard', () => {
  beforeEach(() => {
    mockUseDeleteAccount.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
  })

  it('renders skeleton while accounts are loading', () => {
    mockUseAccounts.mockReturnValue({
      data: undefined,
      isLoading: true,
    })

    render(<AccountsCard />)

    expect(screen.getByTestId('accounts-skeleton')).toBeInTheDocument()
  })

  it('lists accounts when data is available', () => {
    mockUseAccounts.mockReturnValue({
      data: [
        { id: 'acct-1', name: 'My IRA', accountType: 'IRA' },
        { id: 'acct-2', name: 'Growth', accountType: 'Taxable' },
      ],
      isLoading: false,
    })

    render(<AccountsCard />)

    expect(screen.getByText('Accounts')).toBeVisible()
    expect(screen.getByText('My IRA')).toBeVisible()
    expect(screen.getByText('Growth')).toBeVisible()
  })
})
