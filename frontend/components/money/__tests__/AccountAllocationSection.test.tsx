import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { buildHouseholdDashboard } from '@/app/__tests__/householdDashboardFixture'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { AccountAllocationSection } from '../AccountAllocationSection'

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

/**
 * The raw accounts below contradict the backend-owned allocation on purpose: if
 * this section ever re-derives the split from account balances instead of
 * reading `overview.assetAllocation`, these fail.
 */
function dashboardWithAllocation(): HouseholdFinanceDashboard {
  const base = buildHouseholdDashboard()
  return {
    ...base,
    overview: {
      ...base.overview,
      assetAllocation: [
        { assetGroup: 'real_estate', totalValue: 777 },
        { assetGroup: 'brokerage', totalValue: 400 },
      ],
    },
    accounts: [
      {
        ...base.accounts[0],
        id: 'account-1',
        label: 'Brokerage One',
        assetGroup: 'brokerage',
        currentValue: 99999,
      },
      {
        ...base.accounts[0],
        id: 'account-2',
        label: 'The House',
        assetGroup: 'real_estate',
        currentValue: 1,
      },
    ],
  } as unknown as HouseholdFinanceDashboard
}

describe('AccountAllocationSection', () => {
  it('renders the allocation the backend owns, not one derived from balances', () => {
    render(<AccountAllocationSection dashboard={dashboardWithAllocation()} />, {
      wrapper,
    })

    expect(screen.getByText('Account Allocation')).toBeInTheDocument()
    expect(screen.getByText('$777')).toBeInTheDocument()
    expect(screen.getByText('$400')).toBeInTheDocument()
  })

  it('drills into the raw accounts belonging to the selected group', async () => {
    const user = userEvent.setup()
    render(<AccountAllocationSection dashboard={dashboardWithAllocation()} />, {
      wrapper,
    })

    // First slice wins by default, and the backend sorts them.
    expect(screen.getByText('The House')).toBeInTheDocument()
    expect(screen.queryByText('Brokerage One')).toBeNull()

    await user.click(screen.getByText('Brokerage'))
    expect(screen.getByText('Brokerage One')).toBeInTheDocument()
  })

  it('says nothing at all rather than an empty donut when there is no allocation', () => {
    const base = buildHouseholdDashboard()
    render(
      <AccountAllocationSection
        dashboard={
          {
            ...base,
            overview: { ...base.overview, assetAllocation: [] },
          } as unknown as HouseholdFinanceDashboard
        }
      />,
      { wrapper },
    )

    expect(
      screen.getByText('No asset allocation visible yet.'),
    ).toBeInTheDocument()
  })
})
