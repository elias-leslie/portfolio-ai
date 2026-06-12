'use client'

import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { AllocationCard } from '../AllocationCard'

vi.mock('recharts', () => {
  const MockChart = ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  )

  return {
    ResponsiveContainer: MockChart,
    PieChart: MockChart,
    Pie: MockChart,
    Cell: MockChart,
    Tooltip: () => null,
  }
})

const accounts = Array.from({ length: 6 }, (_, index) => ({
  id: `account-${index + 1}`,
  label: `Cash account ${index + 1}`,
  assetGroup: 'cash',
  currentValue: 1000 * (index + 1),
  freshnessLabel: 'Fresh',
  matchStatus: 'linked',
})) as unknown as HouseholdFinanceDashboard['accounts']

const dashboard = {
  accounts,
  overview: { netWorthDetail: 'Current.' },
} as HouseholdFinanceDashboard

const allocationData = [{ assetGroup: 'cash', label: 'Cash', value: 21000 }]

function renderCard(selectedAccounts: HouseholdFinanceDashboard['accounts']) {
  return render(
    <AllocationCard
      dashboard={dashboard}
      allocationData={allocationData}
      selectedAssetGroup="cash"
      setSelectedAssetGroup={vi.fn()}
      selectedAccounts={selectedAccounts}
      netWorthTrustStatus="current"
    />,
  )
}

describe('AllocationCard', () => {
  it('says the drilldown is truncated instead of silently capping at 4', () => {
    renderCard(accounts)

    expect(screen.getByText('Showing 4 of 6 accounts')).toBeInTheDocument()
    expect(screen.getByText('Cash account 4')).toBeInTheDocument()
    expect(screen.queryByText('Cash account 5')).not.toBeInTheDocument()
  })

  it('skips the truncation note when every account fits', () => {
    renderCard(accounts.slice(0, 3))

    expect(screen.queryByText(/showing 4 of/i)).not.toBeInTheDocument()
    expect(screen.getByText('Cash account 3')).toBeInTheDocument()
  })
})
