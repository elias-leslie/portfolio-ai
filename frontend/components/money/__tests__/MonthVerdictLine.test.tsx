import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MonthVerdictLine } from '../MonthVerdictLine'

function verdict(overrides: Record<string, unknown> = {}) {
  return {
    status: 'under_plan',
    headline: 'June 2026 came in $1,012 under your caps.',
    detail: '2 under by $1,012 (most of it Groceries).',
    capTotal: 1900,
    cappedActual: 888,
    variance: -1012,
    overTotal: 0,
    underTotal: 1012,
    overCategoryCount: 0,
    underCategoryCount: 2,
    uncappedSpend: 0,
    uncappedCategoryCount: 0,
    largestOverCategory: null,
    largestOverAmount: 0,
    largestUnderCategory: 'Groceries',
    largestUnderAmount: 900,
    ...overrides,
  }
}

describe('MonthVerdictLine', () => {
  it('says the sentence the household asked for', () => {
    render(<MonthVerdictLine verdict={verdict()} isLoading={false} />)

    expect(
      screen.getByText('June 2026 came in $1,012 under your caps.'),
    ).toBeInTheDocument()
  })

  it('shows what the verdict nets out of, not just the verdict', () => {
    render(
      <MonthVerdictLine
        verdict={verdict({
          status: 'over_plan',
          headline: 'June 2026 came in $1,101 over your caps.',
          detail:
            '1 over by $1,128 (most of it Groceries) · 1 under by $27 (most of it Gas).',
        })}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText(
        '1 over by $1,128 (most of it Groceries) · 1 under by $27 (most of it Gas).',
      ),
    ).toBeInTheDocument()
  })

  it('refuses a verdict when most of the month has no cap', () => {
    render(
      <MonthVerdictLine
        verdict={verdict({
          status: 'plan_incomplete',
          headline:
            "Only $888 of July 2026's $16,708 has a cap, so there is no overall verdict yet.",
          detail: '$15,820 ran through 12 uncapped categories.',
        })}
        isLoading={false}
      />,
    )

    expect(
      screen.getByText(
        "Only $888 of July 2026's $16,708 has a cap, so there is no overall verdict yet.",
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/under your caps/)).not.toBeInTheDocument()
  })

  it('says nothing rather than guessing while the month is loading', () => {
    render(<MonthVerdictLine verdict={null} isLoading />)

    expect(screen.getByText('Reading the month…')).toBeInTheDocument()
  })
})
