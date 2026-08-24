import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdRetirementContributionTracker } from '@/lib/api/household'
import { RetirementPhaseCard } from '../RetirementPhaseCard'

function block(
  overrides: Partial<HouseholdRetirementContributionTracker> = {},
): HouseholdRetirementContributionTracker {
  return {
    status: 'short',
    monthlyTarget: null,
    estimatedMonthlyContributions: 0,
    monthlyGap: 0,
    phase: 'accumulating_contributions_binding',
    phaseLabel: 'Accumulating - 9 years to 49',
    headline:
      "Today's assets support $6,429/mo against a $7,500/mo plan - a gap of $257,129 in investable assets.",
    detail: 'No contributions are visible, noted rather than graded.',
    currentAge: 40,
    targetRetirementAge: 49,
    yearsToTarget: 9,
    investableAssets: 1542870.67,
    withdrawalRate: 0.05,
    sustainableMonthlySpend: 6428.63,
    targetMonthlySpend: 7500,
    assetGap: 257129.33,
    spendPhase: null,
    yearsToNextSpendPhase: null,
    blindSpots: [],
    ...overrides,
  }
}

describe('RetirementPhaseCard', () => {
  it('names the phase, so the question the block is asking is legible', () => {
    render(<RetirementPhaseCard block={block()} isLoading={false} />)

    expect(screen.getByText('Accumulating - 9 years to 49')).toBeInTheDocument()
    expect(screen.getByText(/a gap of \$257,129/)).toBeInTheDocument()
  })

  it('shows the arithmetic behind the verdict, not just the verdict', () => {
    render(<RetirementPhaseCard block={block()} isLoading={false} />)

    expect(
      screen.getByText('Supported at 5.0% of $1,542,871'),
    ).toBeInTheDocument()
    expect(screen.getByText('$6,429/mo')).toBeInTheDocument()
    expect(screen.getByText('Plan assumes')).toBeInTheDocument()
    expect(screen.getByText('$7,500/mo')).toBeInTheDocument()
  })

  it('lets the plan hold without saving, instead of failing it for not saving', () => {
    render(
      <RetirementPhaseCard
        block={block({
          status: 'plan_holds',
          phase: 'accumulating_growth_carrying',
          headline:
            "The plan holds at a 0% savings rate. Today's investable assets already support $8,333/mo at your own withdrawal rule.",
        })}
        isLoading={false}
      />,
    )

    expect(screen.getByText('Plan holds')).toBeInTheDocument()
    expect(screen.getByText(/holds at a 0% savings rate/)).toBeInTheDocument()
  })

  it('reads the drawdown phase and the years to the next one', () => {
    render(
      <RetirementPhaseCard
        block={block({
          phase: 'drawing_down',
          phaseLabel: 'Go-go years - 26 years to the next',
          spendPhase: 'go_go',
          yearsToNextSpendPhase: 26,
          headline:
            'Spending runs $10,231/mo against the $6,429/mo today’s assets support at your own withdrawal rule.',
        })}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText('Go-go years - 26 years to the next'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Spending runs \$10,231\/mo/)).toBeInTheDocument()
  })

  it('spells out what it cannot see rather than leaving a zero to be read', () => {
    render(
      <RetirementPhaseCard
        block={block({
          blindSpots: [
            'no_retirement_account_activity',
            'withdrawal_rate_unset',
          ],
        })}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText(
        'No account in the ledger is labelled as a retirement account.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('No withdrawal rate is recorded.'),
    ).toBeInTheDocument()
  })

  it('drops the arithmetic when there is no rule to do it with', () => {
    render(
      <RetirementPhaseCard
        block={block({
          status: 'unmeasurable',
          withdrawalRate: null,
          sustainableMonthlySpend: null,
        })}
        isLoading={false}
      />,
    )

    expect(screen.queryByText(/Supported at/)).toBeNull()
    expect(screen.getByText('Unmeasurable')).toBeInTheDocument()
  })

  it('admits there is no phase instead of inventing one', () => {
    render(<RetirementPhaseCard block={null} isLoading={false} />)

    expect(
      screen.getByText('No retirement plan to read yet.'),
    ).toBeInTheDocument()
  })
})
