import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdIncomeAnchor } from '@/lib/api/household'
import { IncomeAnchorCard } from '../IncomeAnchorCard'

const updateProfileMutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdProfile: () => ({
    mutate: updateProfileMutate,
    isPending: false,
  }),
}))

function anchor(overrides: Partial<HouseholdIncomeAnchor> = {}) {
  return {
    status: 'measured',
    headline: '$6,067/mo is what a normal month brings in.',
    detail:
      'Median of May 2026, June 2026 and July 2026: $6,067, $7,985, $2,804.',
    monthlyIncome: 6067.39,
    source: 'median',
    sourceLabel: 'Median of 3 complete months',
    medianMonthlyIncome: 6067.39,
    monthsUsed: [
      { month: '2026-05', label: 'May 2026', amount: 6067.39, isMedian: true },
      {
        month: '2026-06',
        label: 'June 2026',
        amount: 7984.87,
        isMedian: false,
      },
      {
        month: '2026-07',
        label: 'July 2026',
        amount: 2804.36,
        isMedian: false,
      },
    ],
    completeMonthsAvailable: 7,
    overrideAmount: null,
    overrideSetOn: null,
    overrideNote: null,
    overrideAgeDays: null,
    overrideDrift: null,
    overrideStale: false,
    overrideStaleDetail: '',
    profileTarget: 6283,
    profileTargetGap: 215.61,
    profileTargetDetail:
      'The saved take-home target of $6,283 is $216 above the anchor.',
    ...overrides,
  } as HouseholdIncomeAnchor
}

describe('IncomeAnchorCard', () => {
  beforeEach(() => {
    updateProfileMutate.mockReset()
  })

  it('shows the months behind the median, not just the median', () => {
    render(<IncomeAnchorCard anchor={anchor()} />)

    // Twice on purpose: the anchor itself, and the month it came from.
    expect(screen.getAllByText('$6,067')).toHaveLength(2)
    expect(screen.getByText('May 2026')).toBeInTheDocument()
    expect(screen.getByText('$7,985')).toBeInTheDocument()
    expect(screen.getByText('$2,804')).toBeInTheDocument()
    expect(screen.getByText('median')).toBeInTheDocument()
  })

  it('keeps the saved take-home target visible beside what actually arrives', () => {
    render(<IncomeAnchorCard anchor={anchor()} />)

    expect(
      screen.getByText(/saved take-home target of \$6,283 is \$216 above/i),
    ).toBeInTheDocument()
  })

  it('shows a declared anchor with the measurement it outranks', () => {
    render(
      <IncomeAnchorCard
        anchor={anchor({
          status: 'declared',
          headline: '$9,000/mo, declared.',
          monthlyIncome: 9000,
          source: 'override',
          overrideAmount: 9000,
          overrideSetOn: '2026-08-01',
          overrideNote: 'SummitFlow contract starts',
        })}
      />,
    )

    expect(screen.getByText('$9,000')).toBeInTheDocument()
    expect(screen.getByText('Declared')).toBeInTheDocument()
    // The measurement is still on screen: a declaration never erases it.
    expect(screen.getByText('Measured median')).toBeInTheDocument()
    expect(screen.getAllByText('$6,067').length).toBeGreaterThan(0)
  })

  it('says when a declared anchor stopped matching what arrives', () => {
    render(
      <IncomeAnchorCard
        anchor={anchor({
          status: 'declared',
          monthlyIncome: 9000,
          overrideAmount: 9000,
          overrideSetOn: '2026-05-01',
          overrideStale: true,
          overrideStaleDetail:
            'Declared on May 01, 2026 and still $2,933 above what has actually arrived.',
        })}
      />,
    )

    expect(
      screen.getByText(/still \$2,933 above what has actually arrived/i),
    ).toBeInTheDocument()
  })

  it('dates a declaration on the day it is made', async () => {
    const user = userEvent.setup()
    render(<IncomeAnchorCard anchor={anchor()} />)

    await user.click(screen.getByRole('button', { name: /declare an anchor/i }))
    const amount = screen.getByLabelText('Declared monthly income')
    await user.clear(amount)
    await user.type(amount, '9000')
    await user.type(
      screen.getByLabelText('Why this anchor was declared'),
      'SummitFlow starts',
    )
    await user.click(screen.getByRole('button', { name: /save anchor/i }))

    expect(updateProfileMutate).toHaveBeenCalledTimes(1)
    const payload = updateProfileMutate.mock.calls[0][0]
    expect(payload.incomeAnchorOverride).toBe(9000)
    expect(payload.incomeAnchorOverrideNote).toBe('SummitFlow starts')
    expect(payload.incomeAnchorOverrideSetOn).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('clears the declaration back to the measurement', async () => {
    const user = userEvent.setup()
    render(
      <IncomeAnchorCard
        anchor={anchor({
          status: 'declared',
          overrideAmount: 9000,
          overrideSetOn: '2026-08-01',
        })}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: /use the measured median/i }),
    )

    expect(updateProfileMutate).toHaveBeenCalledWith({
      incomeAnchorOverride: null,
      incomeAnchorOverrideSetOn: null,
      incomeAnchorOverrideNote: null,
    })
  })

  it('refuses to declare an anchor of nothing', async () => {
    const user = userEvent.setup()
    render(<IncomeAnchorCard anchor={anchor()} />)

    await user.click(screen.getByRole('button', { name: /declare an anchor/i }))
    await user.clear(screen.getByLabelText('Declared monthly income'))
    await user.click(screen.getByRole('button', { name: /save anchor/i }))

    expect(updateProfileMutate).not.toHaveBeenCalled()
  })

  it('says it cannot measure rather than reporting zero', () => {
    render(
      <IncomeAnchorCard
        anchor={anchor({
          status: 'insufficient_history',
          headline: 'Not enough history to say what a normal month brings in.',
          detail: 'No complete calendar month of income is on record.',
          monthlyIncome: null,
          medianMonthlyIncome: null,
          monthsUsed: [],
          completeMonthsAvailable: 0,
          profileTarget: null,
          profileTargetGap: null,
          profileTargetDetail: '',
        })}
      />,
    )

    expect(screen.getByText('Not measurable')).toBeInTheDocument()
    expect(screen.queryByText('$0')).toBeNull()
  })
})
