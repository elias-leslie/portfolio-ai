'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyCardsPanel } from '../MoneyCardsPanel'

const useOwnedCardsMock = vi.fn()
const useHouseholdFactsMock = vi.fn()

vi.mock('@/lib/hooks/useCards', () => ({
  useOwnedCards: () => useOwnedCardsMock(),
  useCardCatalog: () => ({ data: [] }),
  useSoftCharges: () => ({ data: [] }),
  useRotationPlan: () => ({
    data: undefined,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useActivateCard: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteCard: () => ({ mutate: vi.fn(), isPending: false }),
  useRefreshCatalogResearch: () => ({
    mutate: vi.fn(),
    isPending: false,
    data: undefined,
  }),
}))

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdFacts: () => useHouseholdFactsMock(),
  useConfirmFact: () => ({ mutate: vi.fn(), isPending: false }),
}))

// Chart/table/dialog children pull their own hooks or Recharts — out of scope here.
vi.mock('../AddCardDialog', () => ({ AddCardDialog: () => null }))
vi.mock('../AddSoftChargeDialog', () => ({
  AddSoftChargeDialog: () => null,
  SoftChargesSection: () => null,
}))
vi.mock('../CardRankingTable', () => ({ CardRankingTable: () => null }))
vi.mock('../RotationTimeline', () => ({
  PLAYER_PRESETS: [
    { value: 'both', label: 'Both players', players: ['p1', 'p2'] },
  ],
  RotationTimeline: () => null,
}))
vi.mock('../RotationValueChart', () => ({ RotationValueChart: () => null }))
vi.mock('../WelcomeProgressChart', () => ({ WelcomeProgressChart: () => null }))

function okQuery(data: unknown[]) {
  return {
    data,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }
}

function errorQuery() {
  return {
    data: undefined,
    isError: true,
    isFetching: false,
    refetch: vi.fn(),
  }
}

describe('MoneyCardsPanel', () => {
  beforeEach(() => {
    useOwnedCardsMock.mockReset()
    useHouseholdFactsMock.mockReset()
    useOwnedCardsMock.mockReturnValue(okQuery([]))
    useHouseholdFactsMock.mockReturnValue(okQuery([]))
  })

  it('shows the genuine empty wallet state when owned cards load as empty', () => {
    render(<MoneyCardsPanel />)

    expect(screen.getByText(/No owned cards yet/i)).toBeInTheDocument()
    expect(
      screen.queryByText('Failed to load the household wallet.'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('Failed to load alert settings.'),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Alerts & research')).toBeInTheDocument()
  })

  it('renders a load error instead of the false empty state when owned cards fail', async () => {
    const user = userEvent.setup()
    const failed = errorQuery()
    useOwnedCardsMock.mockReturnValue(failed)
    render(<MoneyCardsPanel />)

    expect(
      screen.getByText('Failed to load the household wallet.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/No owned cards yet/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect(failed.refetch).toHaveBeenCalled()
  })

  it('renders a load error instead of a silent default cap when facts fail', () => {
    useHouseholdFactsMock.mockReturnValue(errorQuery())
    render(<MoneyCardsPanel />)

    expect(
      screen.getByText('Failed to load alert settings.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('The saved monthly cap could not be loaded.'),
    ).toBeInTheDocument()
    // The alert-settings card (with its $6,500 default cap) must not render.
    expect(
      screen.queryByText(/Monthly card-spend cap/i),
    ).not.toBeInTheDocument()
    // The wallet section still renders normally.
    expect(screen.getByText(/No owned cards yet/i)).toBeInTheDocument()
  })
})
