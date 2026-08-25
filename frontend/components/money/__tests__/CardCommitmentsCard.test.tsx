import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type {
  HouseholdCardCommitment,
  HouseholdCardCommitments,
} from '@/lib/api/household'
import { CardCommitmentsCard } from '../CardCommitmentsCard'

function card(
  overrides: Partial<HouseholdCardCommitment> = {},
): HouseholdCardCommitment {
  return {
    cardId: 'card-1',
    productName: 'Chase Sapphire Preferred',
    accountLabel: 'Chase Sapphire Preferred ·3627',
    accountMask: '3627',
    ownerName: 'Elias B Leslie',
    role: 'rotating',
    balanceOwed: 5926.5,
    balanceDetail: '$5,927 owed right now.',
    annualFee: 95,
    annualFeeDueDate: '2027-08-02',
    annualFeeDaysAway: 342,
    annualFeeDetail: '$95 renews Aug 02, 2027, 342 days away.',
    welcomeMinSpend: 5000,
    welcomeProgress: 5831.5,
    welcomeDeadline: '2026-10-21',
    welcomeDaysLeft: 57,
    welcomeStatus: 'earned',
    welcomeDetail: 'Bonus earned -- $5,832 against a $5,000 minimum.',
    ...overrides,
  }
}

function commitments(
  overrides: Partial<HouseholdCardCommitments> = {},
): HouseholdCardCommitments {
  return {
    status: 'committed',
    headline: '$17,336 owed across 3 cards, and $190/yr to keep them.',
    detail:
      'The fees are $16/mo of income already spoken for, so the caps come out after them.',
    cards: [card()],
    balanceTotal: 17336.41,
    balanceUnknownLabels: [],
    annualFeeYearly: 190,
    annualFeeMonthly: 15.83,
    nextFeeDetail:
      '2 fees totalling $190 land together on Aug 02, 2027, 342 days away.',
    welcomeOpenCount: 0,
    welcomeDetail: '2 welcome bonuses already earned; nothing is open.',
    ...overrides,
  }
}

describe('CardCommitmentsCard', () => {
  it('states what is owed, what the cards cost, and when the next fee lands', () => {
    render(<CardCommitmentsCard commitments={commitments()} />)

    expect(screen.getByText(/\$17,336 owed across 3 cards/)).toBeInTheDocument()
    expect(
      screen.getByText(/land together on Aug 02, 2027/),
    ).toBeInTheDocument()
    expect(screen.getByText('$16/mo of fees')).toBeInTheDocument()
  })

  it('names the card by owner and last four, since two share a product name', () => {
    render(
      <CardCommitmentsCard
        commitments={commitments({
          cards: [
            card(),
            card({
              cardId: 'card-2',
              accountMask: '8054',
              ownerName: 'Mariana Leslie',
            }),
          ],
        })}
      />,
    )

    expect(
      screen.getByText('Chase Sapphire Preferred (Elias ·3627)'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Chase Sapphire Preferred (Mariana ·8054)'),
    ).toBeInTheDocument()
  })

  it('says a card is not reporting rather than showing it as paid off', () => {
    render(
      <CardCommitmentsCard
        commitments={commitments({
          cards: [
            card({
              balanceOwed: null,
              balanceDetail:
                'No balance is reaching this card, so what it owes is unknown rather than zero.',
            }),
          ],
          balanceUnknownLabels: ['Chase Sapphire Preferred (Elias ·3627)'],
        })}
      />,
    )

    expect(screen.getByText('Not reporting')).toBeInTheDocument()
    expect(screen.getByText(/unknown rather than zero/)).toBeInTheDocument()
  })

  it('leads with an open bonus and the pace that still wins it', () => {
    render(
      <CardCommitmentsCard
        commitments={commitments({
          welcomeOpenCount: 1,
          welcomeDetail:
            '$3,000 to go by Oct 24, 2026 -- 60 days left, about $50/day. Route household spend here.',
          cards: [
            card({
              welcomeStatus: 'in_progress',
              welcomeDetail:
                '$3,000 to go by Oct 24, 2026 -- 60 days left, about $50/day. Route household spend here.',
            }),
          ],
        })}
      />,
    )

    expect(screen.getByText('1 bonus open')).toBeInTheDocument()
    expect(screen.getByText('Bonus open')).toBeInTheDocument()
    expect(screen.getAllByText(/about \$50\/day/).length).toBeGreaterThan(0)
  })

  it('says no card is recorded rather than reporting nothing owed', () => {
    render(
      <CardCommitmentsCard
        commitments={commitments({
          status: 'no_cards',
          detail:
            'Card rotation is routine here, so a card the household is using and the plan cannot see is a balance, a fee and a deadline that nothing is tracking. Add it on the Cards tab.',
          cards: [],
          balanceTotal: null,
        })}
      />,
    )

    expect(screen.getByText(/Add it on the Cards tab/)).toBeInTheDocument()
    expect(screen.queryByText('$0')).not.toBeInTheDocument()
  })
})
