import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { HouseholdSpendVariance } from '@/lib/api/household'
import { WhatChangedCard } from '../WhatChangedCard'

function variance(
  overrides: Partial<HouseholdSpendVariance> = {},
): HouseholdSpendVariance {
  return {
    comparatorKey: 'prior_month',
    comparatorLabel: 'June 2026',
    monthSpend: 16708,
    comparatorSpend: 13704,
    change: 3004,
    changePct: 0.219,
    headline: 'July 2026 spent $3,004 more than June 2026.',
    detail:
      'Set the one-time purchases aside (largest: Costco $5,832) — $11,633 this month against $0 then — and everyday spending was $8,629 less.',
    everydayMonthSpend: 5075,
    everydayComparatorSpend: 13704,
    everydayChange: -8629,
    oneTimeMonthSpend: 11633,
    oneTimeComparatorSpend: 0,
    drivers: [
      {
        category: 'Travel',
        monthSpend: 498,
        comparatorSpend: 5655,
        contribution: -5157,
        shareOfChange: -0.6,
        largestPurchaseMerchant: 'Avis',
        largestPurchaseAmount: 343,
      },
    ],
    ...overrides,
  }
}

describe('WhatChangedCard', () => {
  it('says both true things about the month, not just the total', () => {
    render(<WhatChangedCard variance={variance()} />)

    expect(
      screen.getByText('July 2026 spent $3,004 more than June 2026.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/everyday spending was \$8,629 less/),
    ).toBeInTheDocument()
  })

  it('swaps the headline number when the outliers are set aside', () => {
    render(<WhatChangedCard variance={variance()} />)

    expect(screen.getByText('+$3,004')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Excluding one-time' }))

    expect(screen.getByText('−$8,629')).toBeInTheDocument()
    expect(
      screen.getByText(/one-time purchases set aside on both sides/),
    ).toBeInTheDocument()
  })

  it('shows a driver in the direction its money moved', () => {
    render(<WhatChangedCard variance={variance()} />)

    expect(screen.getByText('−$5,157')).toBeInTheDocument()
    expect(screen.getByText('-60%')).toBeInTheDocument()
  })

  it('offers no toggle when neither month had a one-time purchase', () => {
    render(
      <WhatChangedCard
        variance={variance({
          oneTimeMonthSpend: 0,
          oneTimeComparatorSpend: 0,
        })}
      />,
    )

    expect(
      screen.queryByRole('button', { name: /one-time/ }),
    ).not.toBeInTheDocument()
  })

  it('renders nothing when there is no prior month to compare against', () => {
    const { container } = render(<WhatChangedCard variance={null} />)

    expect(container).toBeEmptyDOMElement()
  })
})
