import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdCoverage } from '@/lib/api/household'
import { CoverageCard } from '../CoverageCard'

function coverage(
  overrides: Partial<HouseholdCoverage> = {},
): HouseholdCoverage {
  return {
    score: 91,
    label: 'Strong coverage',
    summary:
      'Strong coverage: 1 of 4 spending accounts has gone quiet (Chase Sapphire Preferred ·8054).',
    components: [
      {
        key: 'balances',
        label: 'Balances current',
        score: 99,
        weight: 30,
        detail: '2 of 15 accounts are stale, holding $6,793 of $1,561,013.',
      },
      {
        key: 'spending_feeds',
        label: 'Spending feeds reporting',
        score: 75,
        weight: 30,
        detail:
          '1 of 4 spending accounts has gone quiet (Chase Sapphire Preferred ·8054).',
      },
      {
        key: 'connected_accounts',
        label: 'Known accounts connected',
        score: 94,
        weight: 20,
        detail:
          '1 account seen in evidence is not connected (Visa Credit ****4635).',
      },
      {
        key: 'classified_spend',
        label: 'Spend classified',
        score: 100,
        weight: 20,
        detail: 'All 641 tracked expense rows carry a category.',
      },
    ],
    ...overrides,
  }
}

describe('CoverageCard', () => {
  it('shows the score and the label it was derived from', () => {
    render(<CoverageCard coverage={coverage()} />)

    expect(screen.getByText('91%')).toBeInTheDocument()
    expect(screen.getByText('Strong coverage')).toBeInTheDocument()
  })

  it('publishes the working so the number can be checked, not trusted', () => {
    // A single figure that cannot be broken down is exactly how "99%
    // visibility" survived beside a stale net worth.
    render(<CoverageCard coverage={coverage()} />)

    expect(screen.getByText('Balances current')).toBeInTheDocument()
    expect(
      screen.getByText(
        '2 of 15 accounts are stale, holding $6,793 of $1,561,013.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        '1 account seen in evidence is not connected (Visa Credit ****4635).',
      ),
    ).toBeInTheDocument()
  })

  it('leads with the weakest component rather than restating the score', () => {
    render(<CoverageCard coverage={coverage()} />)

    expect(
      screen.getByText(
        'Strong coverage: 1 of 4 spending accounts has gone quiet (Chase Sapphire Preferred ·8054).',
      ),
    ).toBeInTheDocument()
  })

  it('renders a household that can see everything without a warning', () => {
    render(
      <CoverageCard
        coverage={coverage({
          score: 100,
          summary:
            'Strong coverage: every account is connected, current and classified.',
          components: [
            {
              key: 'balances',
              label: 'Balances current',
              score: 100,
              weight: 30,
              detail: 'All 15 accounts holding a balance are current.',
            },
          ],
        })}
      />,
    )

    // Both the headline and the single component read 100%.
    expect(screen.getAllByText('100%')).toHaveLength(2)
    expect(
      screen.getByText('All 15 accounts holding a balance are current.'),
    ).toBeInTheDocument()
  })
})
