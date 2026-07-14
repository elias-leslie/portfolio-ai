import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import { InvestmentAnalysisPanel } from '../InvestmentAnalysisPanel'

const usePortfolioAnalyticsMock = vi.fn()

vi.mock('@/lib/hooks/usePortfolio', () => ({
  usePortfolioAnalytics: () => usePortfolioAnalyticsMock(),
}))

const analytics: PortfolioAnalytics = {
  portfolioValue: {
    totalValue: 600_000,
    totalCostBasis: 450_000,
    totalGain: 150_000,
    totalGainPct: 33.333,
  },
  cashBalanceTotal: 50_000,
  cashInclusiveTotalValue: 650_000,
  effectiveTotalValue: 1_000_000,
  householdTotalValue: 1_000_000,
  householdInvestedTotalValue: 1_000_000,
  householdCashReserve: 25_000,
  householdInvestmentAccountsCount: 8,
  householdTotalsTrusted: true,
  accountControlStatus: 'clear',
  accountControlSummary: 'All material accounts reconcile.',
  accountControlBlockingIssueCount: 0,
  quotesUpdatedAt: '2026-07-14T15:00:00Z',
  quoteFreshnessStatus: 'fresh',
  quoteFreshnessLabel: 'Live quotes',
  portfolioBeta: 1.05,
  portfolioVolatility: 0.14,
  sharpeRatio: 1.8,
  concentration: {
    topHoldingPct: 18,
    top3Pct: 39,
    top10Pct: 72,
    herfindahlIndex: 900,
    method: 'lookthrough',
    topHoldingName: 'ACME',
    vehicleTopHoldingPct: 60,
    vehicleTop3Pct: 90,
    vehicleTop10Pct: 100,
    vehicleHerfindahlIndex: 4_200,
    vehicleTopHoldingName: 'INDEX',
    lookthroughCoveragePct: 95,
  },
  sectorExposure: { Technology: 42, Healthcare: 21 },
  riskProfile: {
    level: 'Moderate',
    score: 44,
    factors: { beta: 'Moderate market sensitivity' },
  },
  diversificationScore: {
    score: 82,
    level: 'Good',
    numHoldings: 28,
    numSectors: 9,
    method: 'lookthrough',
    lookthroughCoveragePct: 95,
  },
  topPerformers: [
    {
      symbol: 'ACME',
      gainPct: 25,
      gainAmount: 50_000,
      currentValue: 250_000,
      weightPct: 41.7,
    },
  ],
  bottomPerformers: [
    {
      symbol: 'BETA',
      gainPct: -5,
      gainAmount: -5_000,
      currentValue: 100_000,
      weightPct: 16.7,
    },
  ],
  numPositions: 5,
  numSymbols: 4,
}

describe('InvestmentAnalysisPanel', () => {
  beforeEach(() => {
    usePortfolioAnalyticsMock.mockReturnValue({
      data: analytics,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })
  })

  it('makes partial household coverage and metric scope explicit', () => {
    render(<InvestmentAnalysisPanel />)

    expect(screen.getByText('Partial household analysis')).toBeVisible()
    expect(
      screen.getByText(/65.0% of known household investment value/i),
    ).toBeVisible()
    expect(screen.getByText('Sector exposure')).toBeVisible()
    expect(screen.getByText('42.0%')).toBeVisible()
    expect(screen.getByText('Return extremes')).toBeVisible()
    expect(screen.getByRole('link', { name: 'ACME' })).toHaveAttribute(
      'href',
      '/symbols/ACME',
    )
    expect(
      screen.getByText(
        /not a complete holdings list, time-weighted performance, or a benchmark comparison/i,
      ),
    ).toBeVisible()
  })

  it('describes line-item analytics without claiming fund look-through', () => {
    usePortfolioAnalyticsMock.mockReturnValue({
      data: {
        ...analytics,
        concentration: {
          ...analytics.concentration,
          method: 'line_item',
          topHoldingName: null,
          lookthroughCoveragePct: 0,
        },
        diversificationScore: {
          ...analytics.diversificationScore!,
          method: 'line_item',
          lookthroughCoveragePct: 0,
        },
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })

    render(<InvestmentAnalysisPanel />)

    expect(
      screen.getByText(
        'Sector exposure from the priced fund and security line items in this workspace.',
      ),
    ).toBeVisible()
    expect(
      screen.getByText('Largest priced fund or security line-item exposure.'),
    ).toBeVisible()
    expect(screen.getByText('Top line-item holding')).toBeVisible()
    expect(screen.getByText(/28 priced line-item holdings/i)).toBeVisible()
    expect(
      screen.queryByText(
        'Largest underlying company exposure after fund look-through.',
      ),
    ).not.toBeInTheDocument()
  })

  it('blocks household trust while retaining clearly scoped position analytics', () => {
    usePortfolioAnalyticsMock.mockReturnValue({
      data: {
        ...analytics,
        householdTotalsTrusted: false,
        accountControlStatus: 'blocked',
        accountControlSummary: 'A material source account is not linked.',
        accountControlBlockingIssueCount: 1,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })

    render(<InvestmentAnalysisPanel />)

    expect(
      screen.getByText('Household total is blocked pending account review'),
    ).toBeVisible()
    expect(
      screen.getByText('A material source account is not linked.'),
    ).toBeVisible()
    expect(
      screen.getByRole('link', { name: /review account control/i }),
    ).toHaveAttribute('href', '/money?tab=accounts')
  })

  it('offers a working retry when analytics fail to load', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    usePortfolioAnalyticsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Analytics service unavailable'),
      refetch,
      isFetching: false,
    })

    render(<InvestmentAnalysisPanel />)
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Analytics service unavailable',
    )
    expect(refetch).toHaveBeenCalledTimes(1)
  })
})
