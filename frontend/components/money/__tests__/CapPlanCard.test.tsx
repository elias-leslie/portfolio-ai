import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdCapPlan } from '@/lib/api/household'
import { CapPlanCard } from '../CapPlanCard'

function plan(overrides: Partial<HouseholdCapPlan> = {}) {
  return {
    status: 'proposed',
    headline: '$1,594/mo to divide after essentials, saving and the funds.',
    detail:
      '$6,067 anchor - $0 saving - $1,349 fund accruals = $4,718. Essentials take $3,124 at what they actually cost, leaving $1,594 shaped across 10 categories.',
    anchorMonthlyIncome: 6067.39,
    savingsTarget: 0,
    sinkingFundTotal: 1349.25,
    availableForCategories: 4718.14,
    essentialsTotal: 3124.13,
    discretionaryPool: 1594.01,
    trailingMonthlyTotal: 7349.2,
    gapToTrailing: -2631.06,
    confirmedCapTotal: 0,
    driftDetail:
      'These categories currently run $2,631/mo above that, so the proposal is a cut, not a description.',
    rows: [
      {
        category: 'Groceries',
        essentiality: 'essential',
        source: 'essential',
        proposedCap: 1680.26,
        trailingMonthly: 1680.26,
        share: 0,
        confirmedCap: null,
        changeFromTrailing: 0,
        detail: 'Held at what it actually costs.',
      },
      {
        category: 'Household',
        essentiality: 'mixed',
        source: 'shaped',
        proposedCap: 895.31,
        trailingMonthly: 2373.27,
        share: 0.5617,
        confirmedCap: null,
        changeFromTrailing: -1477.96,
        detail: '56% of what the household spends outside essentials.',
      },
      {
        category: 'Travel',
        essentiality: 'discretionary',
        source: 'sinking_fund',
        proposedCap: 815.39,
        trailingMonthly: 1397.81,
        share: 0,
        confirmedCap: null,
        changeFromTrailing: -582.42,
        detail: 'Funded by the Travel sinking fund.',
      },
    ],
    ...overrides,
  } as HouseholdCapPlan
}

describe('CapPlanCard', () => {
  it('prints the subtraction the caps come out of', () => {
    render(<CapPlanCard plan={plan()} />)

    expect(screen.getByText('Income anchor')).toBeInTheDocument()
    expect(screen.getByText('less Sinking fund accruals')).toBeInTheDocument()
    expect(screen.getByText('less Essentials at cost')).toBeInTheDocument()
    expect(screen.getByText('$1,594')).toBeInTheDocument()
  })

  it('says plainly that the proposal is a cut when spending runs above income', () => {
    render(<CapPlanCard plan={plan()} />)

    expect(screen.getByText('$2,631 over')).toBeInTheDocument()
    expect(screen.getByText(/a cut, not a description/i)).toBeInTheDocument()
  })

  it('shows room rather than a cut when the anchor covers the spending', () => {
    render(
      <CapPlanCard
        plan={plan({
          gapToTrailing: 500,
          driftDetail: '$500/mo of room against what these categories run at.',
        })}
      />,
    )

    expect(screen.getByText('$500 of room')).toBeInTheDocument()
  })

  it('names each category basis so a cap can be argued with', () => {
    render(<CapPlanCard plan={plan()} />)

    expect(screen.getByText('Essential')).toBeInTheDocument()
    expect(screen.getByText('Shaped by history')).toBeInTheDocument()
    expect(screen.getByText('Sinking fund')).toBeInTheDocument()
    expect(screen.getByText('$2,373')).toBeInTheDocument()
  })

  it('says when income cannot be measured instead of proposing caps anyway', () => {
    render(
      <CapPlanCard
        plan={plan({
          status: 'no_anchor',
          headline: 'Caps cannot be priced until a normal month is measurable.',
          detail: 'The income anchor has no complete month to read yet.',
          anchorMonthlyIncome: null,
          discretionaryPool: 0,
          rows: [],
          driftDetail: '',
        })}
      />,
    )

    expect(
      screen.getByText(/cannot be priced until a normal month is measurable/i),
    ).toBeInTheDocument()
  })
})
