import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdSpendExclusions } from '@/lib/api/household'
import { ExcludedFromSpendCard } from '../ExcludedFromSpendCard'

function exclusions(
  overrides: Partial<HouseholdSpendExclusions> = {},
): HouseholdSpendExclusions {
  return {
    excludedCount: 139,
    excludedAmount: 448762,
    includedCount: 861,
    includedAmount: 24366,
    overriddenCount: 0,
    summary:
      '139 of 1,000 rows ($448,762) are held out of spend totals, most of it moved out of an account to another of yours ($183,306).',
    rules: [
      {
        rule: 'flow:transfer_out',
        label: 'Moved out of an account to another of yours',
        transactionCount: 36,
        totalAmount: 183306.34,
        appealable: false,
        restoredCount: 0,
        restoredAmount: 0,
        sampleMerchants: ['Chase Credit Cepay'],
      },
      {
        rule: 'category:cash',
        label: 'Cash withdrawals',
        transactionCount: 5,
        totalAmount: 1740,
        appealable: true,
        restoredCount: 0,
        restoredAmount: 0,
        sampleMerchants: ['Atm Withdrawal Authorized On'],
      },
    ],
    ...overrides,
  }
}

describe('ExcludedFromSpendCard', () => {
  it('states the cost of the exclusions rather than only that there are some', () => {
    render(<ExcludedFromSpendCard exclusions={exclusions()} />)

    expect(screen.getByText('$448,762')).toBeInTheDocument()
    expect(screen.getByText(/across 139 of 1,000 rows/)).toBeInTheDocument()
  })

  it('names each rule, what it holds, and what it matched', () => {
    render(<ExcludedFromSpendCard exclusions={exclusions()} />)

    expect(screen.getByText('Cash withdrawals')).toBeInTheDocument()
    expect(screen.getByText('$1,740')).toBeInTheDocument()
    expect(
      screen.getByText(/5 rows · Atm Withdrawal Authorized On/),
    ).toBeInTheDocument()
  })

  it('marks only the rules that match on wording as often wrong', () => {
    render(<ExcludedFromSpendCard exclusions={exclusions()} />)

    // One badge, on the cash rule -- a transfer is not a filter's guess about
    // a string, so offering to overrule it would be the wrong argument.
    const rules = within(screen.getByRole('list'))
    expect(rules.getAllByText('Often wrong')).toHaveLength(1)
  })

  it('shows the household its own corrections back', () => {
    render(
      <ExcludedFromSpendCard
        exclusions={exclusions({
          overriddenCount: 3,
          rules: [
            {
              rule: 'description:zelle to',
              label: 'Zelle sent',
              transactionCount: 41,
              totalAmount: 8200,
              appealable: true,
              restoredCount: 3,
              restoredAmount: 600,
              sampleMerchants: ['Zelle'],
            },
          ],
        })}
      />,
    )

    expect(
      screen.getByText(/3 of these now count as spend because you said so/),
    ).toBeInTheDocument()
  })

  it('says plainly when nothing was left out', () => {
    render(
      <ExcludedFromSpendCard
        exclusions={exclusions({
          excludedCount: 0,
          excludedAmount: 0,
          rules: [],
          summary: 'Every one of the 2 rows in this window counts as spend.',
        })}
      />,
    )

    expect(
      screen.getByText(
        'Every one of the 2 rows in this window counts as spend.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Often wrong')).not.toBeInTheDocument()
  })
})
