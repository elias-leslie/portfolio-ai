'use client'

import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { SpendTrendCard } from '../SpendTrendCard'

vi.mock('recharts', () => {
  const MockChart = ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  )
  const MockPart = () => null

  return {
    ResponsiveContainer: MockChart,
    LineChart: MockChart,
    Line: MockPart,
    Tooltip: MockPart,
    XAxis: MockPart,
    YAxis: MockPart,
  }
})

function dashboardWithTrend(months: string[]) {
  return {
    reports: {
      monthlySpendTrend: months.map((month) => ({
        month,
        totalSpend: 5000,
        transactionCount: 10,
      })),
    },
  } as HouseholdFinanceDashboard
}

function renderCard(months: string[]) {
  return render(
    <SpendTrendCard
      dashboard={dashboardWithTrend(months)}
      spendTrustStatus="current"
      spendTrustDetail="Current."
      spendTrustDegraded={false}
    />,
  )
}

describe('SpendTrendCard', () => {
  it('flags the trailing point as partial when it is the current month', () => {
    const currentMonth = new Date().toISOString().slice(0, 7)
    renderCard(['2026-01', currentMonth])

    expect(screen.getByText('Current month is partial.')).toBeInTheDocument()
  })

  it('omits the partial hint when the trend ends on a completed month', () => {
    renderCard(['2025-12', '2026-01'])

    expect(
      screen.queryByText('Current month is partial.'),
    ).not.toBeInTheDocument()
  })
})
