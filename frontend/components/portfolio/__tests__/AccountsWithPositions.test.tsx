import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
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
      data: { positions: [] },
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
})
