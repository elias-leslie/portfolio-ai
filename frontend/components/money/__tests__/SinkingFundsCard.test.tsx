import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdSinkingFund } from '@/lib/api/household'
import { SinkingFundsCard } from '../SinkingFundsCard'

const updateFundMutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUpdateHouseholdSinkingFund: () => ({
    mutate: updateFundMutate,
    isPending: false,
  }),
}))

function fund(overrides: Partial<HouseholdSinkingFund> = {}) {
  return {
    key: 'travel',
    label: 'Travel',
    status: 'derived',
    monthlyTarget: 815.39,
    headline: '$815/mo from what has been spent.',
    derivation: '$9,785 over 12 months -> $815/mo.',
    note: '',
    windowTotal: 9784.65,
    windowMonths: 12,
    categories: ['Travel'],
    transactionCount: 22,
    largest: {
      transactionId: 'txn-1',
      date: '2026-01-22',
      merchant: 'Carnival Cruise Line',
      category: 'Travel',
      amount: 2111,
    },
    largestDropped: false,
    monthlyTargetIncludingLargest: 815.39,
    overrideAmount: null,
    overrideSetOn: null,
    overrideNote: null,
    ...overrides,
  } as HouseholdSinkingFund
}

describe('SinkingFundsCard', () => {
  beforeEach(() => {
    updateFundMutate.mockReset()
  })

  it('prints the arithmetic behind each fund', () => {
    render(<SinkingFundsCard funds={[fund()]} />)

    expect(screen.getByText('Travel')).toBeInTheDocument()
    expect(screen.getByText('$815')).toBeInTheDocument()
    expect(
      screen.getByText(/\$9,785 over 12 months -> \$815\/mo/),
    ).toBeInTheDocument()
  })

  it('totals what the funds ask for each month', () => {
    render(
      <SinkingFundsCard
        funds={[
          fund(),
          fund({
            key: 'home_repair',
            label: 'Home repair',
            monthlyTarget: 291,
          }),
        ]}
      />,
    )

    expect(screen.getByText(/\$1,106\/mo set aside/)).toBeInTheDocument()
  })

  it('offers to set aside the largest purchase, naming it', async () => {
    const user = userEvent.setup()
    render(<SinkingFundsCard funds={[fund()]} />)

    await user.click(
      screen.getByRole('button', {
        name: /set aside Carnival Cruise Line \$2,111/i,
      }),
    )

    expect(updateFundMutate).toHaveBeenCalledWith({
      fundKey: 'travel',
      payload: { dropLargest: true },
    })
  })

  it('offers to count a set-aside purchase again', async () => {
    const user = userEvent.setup()
    render(<SinkingFundsCard funds={[fund({ largestDropped: true })]} />)

    await user.click(
      screen.getByRole('button', { name: /count Carnival Cruise Line/i }),
    )

    expect(updateFundMutate.mock.calls[0][0]).toEqual({
      fundKey: 'travel',
      payload: { dropLargest: false },
    })
  })

  it('asks for an amount when the ledger has nothing to derive from', () => {
    render(
      <SinkingFundsCard
        funds={[
          fund({
            key: 'gifts_holidays',
            label: 'Gifts & holidays',
            status: 'no_history',
            monthlyTarget: null,
            headline: 'Nothing to derive this from.',
            derivation: 'No purchases matched this fund in the last 12 months.',
            note: 'Nothing in the ledger is filed as gifts.',
            largest: null,
            windowTotal: 0,
            transactionCount: 0,
          }),
        ]}
      />,
    )

    expect(screen.getByText('Needs an amount')).toBeInTheDocument()
    expect(
      screen.getByText(/Nothing in the ledger is filed as gifts/),
    ).toBeInTheDocument()
    expect(screen.queryByText('$0')).toBeNull()
  })

  it('keeps the derivation visible under a declared amount', async () => {
    const user = userEvent.setup()
    render(
      <SinkingFundsCard
        funds={[
          fund({
            status: 'declared',
            monthlyTarget: 250,
            headline: '$250/mo, declared.',
            derivation: 'Trailing spend says $815/mo ($9,785 over 12 months).',
            overrideAmount: 250,
            overrideSetOn: '2026-08-24',
          }),
        ]}
      />,
    )

    expect(screen.getByText('Declared')).toBeInTheDocument()
    expect(
      screen.getByText(/Trailing spend says \$815\/mo/),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /use trailing spend/i }),
    )
    expect(updateFundMutate.mock.calls[0][0]).toEqual({
      fundKey: 'travel',
      payload: { monthlyOverride: null, overrideNote: null },
    })
  })

  it('declares an amount with the reason attached', async () => {
    const user = userEvent.setup()
    render(<SinkingFundsCard funds={[fund()]} />)

    await user.click(screen.getByRole('button', { name: /declare an amount/i }))
    const amount = screen.getByLabelText('Monthly amount for Travel')
    await user.clear(amount)
    await user.type(amount, '400')
    await user.type(
      screen.getByLabelText('Why Travel is declared'),
      'One trip planned',
    )
    await user.click(screen.getByRole('button', { name: /save amount/i }))

    expect(updateFundMutate.mock.calls[0][0]).toEqual({
      fundKey: 'travel',
      payload: { monthlyOverride: 400, overrideNote: 'One trip planned' },
    })
  })
})
