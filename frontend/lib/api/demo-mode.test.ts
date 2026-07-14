import { describe, expect, it } from 'vitest'
import { demoResponseForPath } from './demo-mode'
import type { HouseholdFinanceDashboard } from './household'
import type { PortfolioAnalytics, PortfolioResponse } from './portfolio'

describe('demo mode portfolio trust fixtures', () => {
  it('keeps trusted portfolio totals aligned with the demo household dashboard', () => {
    const portfolio = demoResponseForPath('/api/portfolio') as PortfolioResponse
    const analytics = demoResponseForPath(
      '/api/portfolio/analytics',
    ) as PortfolioAnalytics
    const household = demoResponseForPath(
      '/api/household/dashboard',
    ) as HouseholdFinanceDashboard

    expect(portfolio.householdTotalsTrusted).toBe(true)
    expect(analytics.householdTotalsTrusted).toBe(true)
    expect(portfolio.householdTotalValue).toBe(
      household.overview.totalTrackedAssets,
    )
    expect(analytics.householdTotalValue).toBe(
      household.overview.totalTrackedAssets,
    )
    expect(portfolio.householdInvestedTotalValue).toBe(
      household.overview.investedAssets,
    )
    expect(analytics.householdInvestedTotalValue).toBe(
      household.overview.investedAssets,
    )
    expect(portfolio.householdCashReserve).toBe(household.overview.cashReserve)
    expect(analytics.householdCashReserve).toBe(household.overview.cashReserve)
    expect(portfolio.householdInvestmentAccountsCount).toBe(3)
    expect(analytics.householdInvestmentAccountsCount).toBe(3)
  })
})
