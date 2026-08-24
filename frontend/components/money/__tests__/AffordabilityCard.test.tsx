import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdAffordability } from '@/lib/api/household'
import { AffordabilityCard } from '../AffordabilityCard'

function affordability(
  overrides: Partial<HouseholdAffordability> = {},
): HouseholdAffordability {
  return {
    freeToSpend: 11828.34,
    cashOnHand: 30494.75,
    billsDue: 88.38,
    billsDueThrough: '2026-09-06',
    remainingEssentials: 1290.32,
    essentialsBasis:
      '5,000 of the 5,000 essentials baseline is covered so far in August.',
    committedFunds: 0,
    cardBalances: 17287.71,
    missingInputs: [],
    status: 'estimate',
    headline:
      '$11,828 free to spend once everything owed through Sep 6 is covered.',
    detail:
      "Cash on hand, less bills due through Sep 6, the rest of this month's essentials, and what is owed on cards.",
    ...overrides,
  }
}

describe('AffordabilityCard', () => {
  it('shows the whole subtraction, not just the answer', () => {
    render(
      <AffordabilityCard affordability={affordability()} isLoading={false} />,
    )

    expect(screen.getByText('Cash on hand')).toBeInTheDocument()
    expect(screen.getByText('$30,495')).toBeInTheDocument()
    expect(
      screen.getByText(/less.*Bills due through Sep 6/),
    ).toBeInTheDocument()
    expect(screen.getByText('−$88')).toBeInTheDocument()
    expect(
      screen.getByText(/less.*Essentials still to come/),
    ).toBeInTheDocument()
    expect(screen.getByText('−$1,290')).toBeInTheDocument()
    // The $17,287 owed across three cards is the line that used to be invisible.
    expect(screen.getByText(/less.*Owed on cards/)).toBeInTheDocument()
    expect(screen.getByText('−$17,288')).toBeInTheDocument()
    expect(screen.getAllByText('$11,828')).toHaveLength(2)
  })

  it('reads the grade off the server rather than judging the figure itself', () => {
    render(
      <AffordabilityCard
        affordability={affordability({
          freeToSpend: 140,
          status: 'tight',
          headline: '$140 left once everything owed through Sep 6 is covered.',
        })}
        isLoading={false}
      />,
    )

    expect(screen.getByText('Tight')).toBeInTheDocument()
    expect(
      screen.getByText(
        '$140 left once everything owed through Sep 6 is covered.',
      ),
    ).toBeInTheDocument()
  })

  it('reports a shortfall as a negative number instead of a floor of zero', () => {
    render(
      <AffordabilityCard
        affordability={affordability({
          freeToSpend: -250,
          status: 'hold',
          headline: '$250 short of what is already owed through Sep 6.',
        })}
        isLoading={false}
      />,
    )

    expect(screen.getByText('Hold')).toBeInTheDocument()
    expect(screen.getAllByText('-$250')).toHaveLength(2)
  })

  it('names the inputs it does not have instead of counting them as zero', () => {
    render(
      <AffordabilityCard
        affordability={affordability({
          missingInputs: ['sinking_fund_balances', 'card_balances'],
        })}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText(/Not yet counted: sinking fund balances, card balances/),
    ).toBeInTheDocument()
  })

  it('hides sinking funds from the subtraction until there are any', () => {
    const { rerender } = render(
      <AffordabilityCard affordability={affordability()} isLoading={false} />,
    )
    expect(screen.queryByText(/Committed to sinking funds/)).toBeNull()

    rerender(
      <AffordabilityCard
        affordability={affordability({ committedFunds: 400 })}
        isLoading={false}
      />,
    )
    expect(screen.getByText(/Committed to sinking funds/)).toBeInTheDocument()
    expect(screen.getByText('−$400')).toBeInTheDocument()
  })

  it('names the stale input without hiding what the figure means', () => {
    render(
      <AffordabilityCard
        affordability={affordability()}
        isLoading={false}
        caveats={[
          'Cash and card balances need a refresh.',
          "This month's essentials are still an estimate.",
        ]}
      />,
    )

    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(
      screen.getByText('Cash and card balances need a refresh.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText("This month's essentials are still an estimate."),
    ).toBeInTheDocument()
    // The number and the sentence explaining it both stay: showing $11,828
    // while suppressing what it means is the worst of both.
    expect(
      screen.getByText(/free to spend once everything owed/),
    ).toBeInTheDocument()
    expect(screen.getAllByText('$11,828')).toHaveLength(2)
  })

  it('admits it cannot answer yet instead of showing a zero', () => {
    render(<AffordabilityCard affordability={null} isLoading={false} />)

    expect(
      screen.getByText(
        'Not enough cash and commitment data to answer this yet.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('$0')).toBeNull()
  })
})
