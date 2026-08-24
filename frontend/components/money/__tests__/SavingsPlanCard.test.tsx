import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdSavingsPlan } from '@/lib/api/household'
import { SavingsPlanCard } from '../SavingsPlanCard'

const updateProfileMutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdProfile: () => ({
    mutate: updateProfileMutate,
    isPending: false,
  }),
}))

function plan(overrides: Partial<HouseholdSavingsPlan> = {}) {
  return {
    status: 'undeclared',
    headline: 'The savings target is $0, which is not a plan.',
    detail: 'A $0 target reports success for saving nothing.',
    monthlyTarget: 0,
    pausedOn: null,
    pauseReason: null,
    restartIncomeThreshold: null,
    anchorMonthlyIncome: 6067.39,
    restartReady: false,
    restartDetail: '',
    leavesForSpending: null,
    ...overrides,
  } as HouseholdSavingsPlan
}

describe('SavingsPlanCard', () => {
  beforeEach(() => {
    updateProfileMutate.mockReset()
  })

  it('calls out a $0 target instead of showing it as a plan', () => {
    render(<SavingsPlanCard plan={plan()} />)

    expect(screen.getByText('Not decided')).toBeInTheDocument()
    expect(screen.getByText(/not a plan/i)).toBeInTheDocument()
  })

  it('shows an active target and what it leaves', () => {
    render(
      <SavingsPlanCard
        plan={plan({
          status: 'active',
          monthlyTarget: 1500,
          headline: '$1,500/mo, set aside on purpose.',
          detail: 'Leaves $4,567 of the $6,067 anchor for everything else.',
          leavesForSpending: 4567.39,
        })}
      />,
    )

    expect(screen.getByText('$1,500')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText(/leaves \$4,567/i)).toBeInTheDocument()
  })

  it('shows a pause with the day it was taken and what ends it', () => {
    render(
      <SavingsPlanCard
        plan={plan({
          status: 'paused',
          headline: 'Saving is paused, on purpose.',
          detail:
            'Paused since Feb 01, 2026. On unemployment. Restarts at $8,000/mo of income.',
          pausedOn: '2026-02-01',
          pauseReason: 'On unemployment',
          restartIncomeThreshold: 8000,
        })}
      />,
    )

    expect(screen.getByText('Paused')).toBeInTheDocument()
    expect(screen.getByText(/Paused since Feb 01, 2026/)).toBeInTheDocument()
    expect(screen.getByText(/Restarts at \$8,000/)).toBeInTheDocument()
  })

  it('says when income has reached the level that ends the pause', () => {
    render(
      <SavingsPlanCard
        plan={plan({
          status: 'restart_due',
          headline:
            'Income has reached the level you set to start saving again.',
          detail:
            'A normal month now brings in $6,067, against the $5,000 you set.',
          restartReady: true,
          restartIncomeThreshold: 5000,
          pausedOn: '2026-02-01',
        })}
      />,
    )

    expect(screen.getByText('Time to resume')).toBeInTheDocument()
    expect(screen.getByText(/now brings in \$6,067/)).toBeInTheDocument()
  })

  it('naming an amount clears the pause in the same write', async () => {
    const user = userEvent.setup()
    render(
      <SavingsPlanCard
        plan={plan({ status: 'paused', pausedOn: '2026-02-01' })}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: /set a monthly amount/i }),
    )
    await user.type(screen.getByLabelText('Monthly savings amount'), '500')
    await user.click(screen.getByRole('button', { name: /save amount/i }))

    expect(updateProfileMutate).toHaveBeenCalledTimes(1)
    expect(updateProfileMutate.mock.calls[0][0]).toEqual({
      monthlySavingsTarget: 500,
      savingsPausedOn: null,
      savingsPauseReason: null,
      savingsRestartIncomeThreshold: null,
    })
  })

  it('a pause must name the income that ends it', async () => {
    const user = userEvent.setup()
    render(<SavingsPlanCard plan={plan({ anchorMonthlyIncome: null })} />)

    await user.click(screen.getByRole('button', { name: /pause saving/i }))
    await user.click(
      screen.getAllByRole('button', { name: /pause saving/i }).slice(-1)[0],
    )

    expect(updateProfileMutate).not.toHaveBeenCalled()
  })

  it('dates the pause on the day it is taken', async () => {
    const user = userEvent.setup()
    render(<SavingsPlanCard plan={plan()} />)

    await user.click(screen.getByRole('button', { name: /pause saving/i }))
    const threshold = screen.getByLabelText(
      'Monthly income that restarts saving',
    )
    await user.clear(threshold)
    await user.type(threshold, '8000')
    await user.type(
      screen.getByLabelText('Why saving is paused'),
      'On unemployment',
    )
    await user.click(
      screen.getAllByRole('button', { name: /^pause saving$/i }).slice(-1)[0],
    )

    const payload = updateProfileMutate.mock.calls[0][0]
    expect(payload.savingsRestartIncomeThreshold).toBe(8000)
    expect(payload.savingsPauseReason).toBe('On unemployment')
    expect(payload.savingsPausedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(payload.monthlySavingsTarget).toBe(0)
  })
})
