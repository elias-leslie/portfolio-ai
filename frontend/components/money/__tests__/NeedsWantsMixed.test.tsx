import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { buildHouseholdDashboard } from '@/app/__tests__/householdDashboardFixture'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { NeedsWantsMixedCard } from '../NeedsWantsMixedCard'

/**
 * The split used to show $3,217 / $4,074 against $8,103 of average monthly
 * spend: two shares summing to 90%, with the $811 `mixed` bucket invisible.
 * After task 1.6 the hidden bucket is far larger -- Household alone is a
 * quarter of spend -- so the three have to account for all of it.
 */
function withSplit(
  essentials: number,
  discretionary: number,
  mixed: number,
): HouseholdFinanceDashboard {
  const base = buildHouseholdDashboard()
  return {
    ...base,
    // The shared fixture is built for panels that never read allocation.
    overview: { ...base.overview, assetAllocation: [] },
    reports: {
      ...base.reports,
      executive: {
        ...base.reports.executive,
        averageMonthlySpend: essentials + discretionary + mixed,
        averageMonthlyEssentials: essentials,
        averageMonthlyDiscretionary: discretionary,
        averageMonthlyMixed: mixed,
      },
      categoryBreakdown: [
        {
          category: 'Groceries',
          essentiality: 'essential',
          monthlyAverage: essentials,
          shareOfSpend: 0,
          totalSpend: essentials,
        },
        {
          category: 'Retail',
          essentiality: 'discretionary',
          monthlyAverage: discretionary,
          shareOfSpend: 0,
          totalSpend: discretionary,
        },
        {
          category: 'Household',
          essentiality: 'mixed',
          monthlyAverage: mixed,
          shareOfSpend: 0,
          totalSpend: mixed,
        },
      ],
    },
  } as unknown as HouseholdFinanceDashboard
}

describe('needs / wants / mixed', () => {
  it('accounts for every tracked dollar rather than 90% of them', () => {
    render(
      <NeedsWantsMixedCard
        dashboard={withSplit(3217, 4074, 811)}
        isLoading={false}
      />,
    )

    // 3,217 + 4,074 = 7,292 against 8,102 of spend: the missing 811 used to be
    // invisible, and the two shares summed to 90%.
    expect(screen.getByText('$3,217')).toBeInTheDocument()
    expect(screen.getByText('$4,074')).toBeInTheDocument()
    expect(screen.getByText('$811')).toBeInTheDocument()
    expect(
      screen.getByText('$8,102/mo typical, split three ways.'),
    ).toBeInTheDocument()
    const shares = [...document.querySelectorAll('dt')].map((term) =>
      Number((term.textContent ?? '').replace(/[^0-9.]/g, '')),
    )
    expect(shares).toHaveLength(3)
    expect(shares.reduce((sum, share) => sum + share, 0)).toBe(100)
  })

  it('puts a mixed category in the mixed bucket, not in neither', () => {
    render(
      <NeedsWantsMixedCard
        dashboard={withSplit(3217, 4074, 811)}
        isLoading={false}
      />,
    )

    expect(screen.getByText(/Groceries \$3,217/)).toBeInTheDocument()
    expect(screen.getByText(/Retail \$4,074/)).toBeInTheDocument()
    expect(screen.getByText(/Household \$811/)).toBeInTheDocument()
  })

  it('says what mixed means, because only the household can settle it', () => {
    render(
      <NeedsWantsMixedCard
        dashboard={withSplit(3217, 4074, 811)}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText(/a Household or Cash row can be a repair or a treat/),
    ).toBeInTheDocument()
  })

  it('drops the mixed footnote when nothing is mixed', () => {
    render(
      <NeedsWantsMixedCard
        dashboard={withSplit(3000, 2000, 0)}
        isLoading={false}
      />,
    )

    expect(screen.getByText('$0')).toBeInTheDocument()
    expect(screen.queryByText(/can be a repair or a treat/)).toBeNull()
  })

  it('shows no shares at all rather than a false split with no spend', () => {
    render(
      <NeedsWantsMixedCard dashboard={withSplit(0, 0, 0)} isLoading={false} />,
    )

    expect(screen.getAllByText('—')).toHaveLength(3)
    expect(screen.queryByText(/leading/)).toBeNull()
  })
})
