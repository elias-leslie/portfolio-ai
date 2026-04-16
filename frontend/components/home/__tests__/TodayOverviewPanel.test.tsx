import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TodayOverviewPanel } from '../TodayOverviewPanel'

const useHouseholdDashboardMock = vi.fn()
const usePortfolioAnalyticsMock = vi.fn()
const useMarketIntelligenceMock = vi.fn()
const useHomeTodayBriefMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolioAnalytics: () => usePortfolioAnalyticsMock(),
}))

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketIntelligence: () => useMarketIntelligenceMock(),
}))

vi.mock('@/lib/hooks/useHomeTodayBrief', () => ({
  useHomeTodayBrief: () => useHomeTodayBriefMock(),
}))

describe('TodayOverviewPanel', () => {
  beforeEach(() => {
    useHouseholdDashboardMock.mockReturnValue({
      data: {
        overview: {
          investedAssets: 95000,
          retirementAssets: 60000,
          taxableAssets: 52000,
          cashReserve: 18000,
          totalTrackedAssets: 120000,
          liabilitiesTotal: 20000,
          netWorth: 100000,
          netWorthStatus: 'estimated',
          netWorthDetail:
            'Net worth estimate from 3 of 4 tracked accounts. 1 account missing current balances.',
          trackedAccountCount: 4,
          needsRefreshCount: 1,
          candidateAccountCount: 0,
          gapCount: 1,
          inboxCount: 1,
          coverageMonths: 4,
          lastTransactionDate: '2026-04-14',
          visibilityScore: 88,
          visibilityLabel: 'High',
          monthlySpendStatus: 'current',
          monthlySpendDetail: 'Monthly spend is current.',
          nextBestAction: 'Refresh one account.',
        },
        budgetSnapshot: {
          monthToDatePlan: 2500,
          monthToDateSpend: 2800,
          paceStatus: 'above_plan',
          paceDetail: 'Spending is running $300 above plan.',
        },
        portfolioContext: {
          cashReservesMonths: 10.8,
        },
      },
      isLoading: false,
    })

    usePortfolioAnalyticsMock.mockReturnValue({
      data: {
        householdTotalValue: 250000,
        householdInvestedTotalValue: 95000,
        householdCashReserve: 12000,
        effectiveTotalValue: 95000,
        portfolioValue: {
          totalValue: 95000,
        },
        quoteFreshnessStatus: 'fresh',
        quotesUpdatedAt: '2026-04-16T10:00:00Z',
        concentration: {
          topHoldingPct: 12,
        },
        diversificationScore: {
          score: 82,
          numSectors: 4,
        },
        numSymbols: 8,
      },
      isLoading: false,
    })

    useMarketIntelligenceMock.mockReturnValue({
      data: {
        fearGreed: {
          score: 55,
          label: 'Neutral',
          trend: 'flat',
        },
      },
      isLoading: false,
    })

    useHomeTodayBriefMock.mockReturnValue({
      data: {
        generatedAt: '2026-04-16T10:00:00Z',
        cacheTtlSeconds: 60,
        asOf: {
          household: '2026-04-16T10:00:00Z',
          portfolio: '2026-04-16T10:00:00Z',
          market: '2026-04-16T10:00:00Z',
          news: '2026-04-16T10:00:00Z',
        },
        marketStatus: 'open',
        brief: {
          headline: 'Stable',
          summary: 'Stable',
          stance: 'neutral',
          confidence: 'medium',
          whyNow: 'Test',
          bullets: ['Watch cash', 'Stay disciplined'],
        },
        catalysts: [],
        impacts: [],
        marketMetrics: [],
        sources: [],
        stalenessNotes: [],
      },
      isLoading: false,
    })
  })

  it('uses household net worth, shows cash runway months, and hides noisy detail from the tile body', () => {
    render(<TodayOverviewPanel />)

    expect(screen.getByText('$100,000')).toBeInTheDocument()
    expect(screen.queryByText('$250,000')).not.toBeInTheDocument()
    expect(screen.getByText('10.8 mo')).toBeInTheDocument()
    expect(screen.queryByText('4.0m')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Net worth estimate from 3 of 4 tracked accounts/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/Ledger /i)).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /estimate: more detail/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /10\.8 mo: more detail/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /cash reserve: more detail/i }),
    ).toBeInTheDocument()
  })
})
