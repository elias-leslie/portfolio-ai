import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TodayOverviewPanel } from '../TodayOverviewPanel'

const useHouseholdDashboardMock = vi.fn()
const useHouseholdNetWorthTrendMock = vi.fn()
const usePortfolioAnalyticsMock = vi.fn()
const useMarketIntelligenceMock = vi.fn()
const useHomeTodayBriefMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
  useHouseholdNetWorthTrend: () => useHouseholdNetWorthTrendMock(),
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
          netWorthStatus: 'known',
          netWorthDetail:
            'Known net worth from 3 of 4 tracked accounts. 1 account missing current balances.',
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

    useHouseholdNetWorthTrendMock.mockReturnValue({
      data: {
        generatedAt: '2026-04-16T10:00:00Z',
        asOfDate: '2026-04-16',
        status: 'known',
        detail:
          'Known net worth from 3 of 4 tracked accounts. Gaps: 1 missing balance.',
        methodology:
          'Current shares are repriced with stored daily closes. Cash, liabilities, and non-symbol accounts use latest available household balances.',
        points: [
          {
            date: '2026-01-16',
            netWorth: 90000,
            totalAssets: 110000,
            liabilities: 20000,
            pricedHoldingsValue: 50000,
            fixedAssets: 60000,
          },
          {
            date: '2026-04-16',
            netWorth: 100000,
            totalAssets: 120000,
            liabilities: 20000,
            pricedHoldingsValue: 60000,
            fixedAssets: 60000,
          },
        ],
        holdingsSymbolCount: 4,
        holdingsPositionCount: 6,
        gapCount: 1,
        needsRefreshCount: 1,
        missingBalanceAccountCount: 1,
        staleAccountCount: 0,
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
      screen.queryByText(/Known net worth from 3 of 4 tracked accounts/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/Ledger /i)).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /known: more detail/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /net worth trend/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /10\.8 mo: more detail/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /cash reserve: more detail/i }),
    ).toBeInTheDocument()
  })

  it('omits per-card horizon/as-of meta in favor of the section-level timestamp', () => {
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
        marketMetrics: [
          {
            key: 'sp500',
            label: 'S&P 500',
            value: '5,250.10',
            changePct: 0.42,
            detail: 'Broad market benchmark',
            tone: 'positive',
            horizon: 'Current quote · 1D vs prior close',
            asOf: '2026-04-16T10:00:00Z',
            asOfLabel: 'As of Apr 16, 6:00 AM ET',
          },
          {
            key: 'vix',
            label: 'VIX',
            value: '18.25',
            changePct: null,
            detail: 'Risk pricing',
            tone: 'neutral',
            horizon: 'Current quote · 1D vs prior close',
            asOf: null,
          },
        ],
        sources: [],
        stalenessNotes: [],
      },
      isLoading: false,
    })

    render(<TodayOverviewPanel />)

    expect(
      screen.queryByText(/Current quote · 1D vs prior close · As of/),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(/As of Apr 16, 6:00 AM ET/),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/As of time unavailable/)).not.toBeInTheDocument()
    expect(screen.getByText('Broad market benchmark')).toBeInTheDocument()
    expect(screen.getByText('Risk pricing')).toBeInTheDocument()
  })

  it('prefers live market intelligence metrics over cached brief strip values', () => {
    useMarketIntelligenceMock.mockReturnValue({
      data: {
        lastUpdated: '2026-05-04T19:48:56Z',
        indicators: {
          sp500: {
            value: 7201.71,
            changePct: -0.37,
            label: 'S&P 500',
            shortLabel: 'S&P',
            tooltip: '',
            signal: 'Neutral',
            emoji: '',
            lastUpdated: '2026-05-04T19:48:56Z',
          },
          vix: {
            value: 18.25,
            changePct: 7.59,
            label: 'VIX',
            shortLabel: 'VIX',
            tooltip: '',
            signal: 'Neutral',
            emoji: '',
            lastUpdated: '2026-05-04T19:48:56Z',
          },
          tnx: {
            value: 4.446,
            changePct: 1.55,
            label: '10Y Yield',
            shortLabel: '10Y',
            tooltip: '',
            signal: 'Neutral',
            emoji: '',
            lastUpdated: '2026-05-04T19:48:56Z',
          },
        },
        fearGreed: {
          score: 62,
          label: 'Greed',
          scoreChange: 0,
          signalCount: 7,
          lastUpdated: '2026-05-01T21:00:00Z',
          isStale: false,
          ageDays: 0,
        },
        sectorRotation: {
          leading: [
            {
              symbol: 'XLK',
              name: 'Technology',
              description: '',
              price: 250,
              changePct: 1.76,
              signal: 'Leading',
              lastUpdated: '2026-05-04T19:48:56Z',
            },
          ],
          neutral: [],
          lagging: [],
          leadingCount: 1,
          neutralCount: 0,
          laggingCount: 0,
        },
      },
      isLoading: false,
    })
    useHomeTodayBriefMock.mockReturnValue({
      data: {
        generatedAt: '2026-05-01T21:00:00Z',
        cacheTtlSeconds: 60,
        asOf: {
          household: '2026-05-01T21:00:00Z',
          portfolio: '2026-05-01T21:00:00Z',
          market: '2026-05-01T21:00:00Z',
          news: '2026-05-01T21:00:00Z',
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
        marketMetrics: [
          {
            key: 'sp500',
            label: 'S&P 500',
            value: '5,250.10',
            changePct: 0.42,
            detail: 'Broad market benchmark',
            tone: 'positive',
            horizon: 'Latest close',
            asOf: '2026-05-01T21:00:00Z',
          },
        ],
        sources: [],
        stalenessNotes: [],
      },
      isLoading: false,
    })

    render(<TodayOverviewPanel />)

    expect(screen.getByText('7,201.71')).toBeInTheDocument()
    expect(screen.queryByText('5,250.10')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Current quote · 1D vs prior close · As of May 4/),
    ).not.toBeInTheDocument()
    expect(screen.getByText('Intraday Mood')).toBeInTheDocument()
    expect(
      screen.queryByText(/Live proxy · Quote inputs · As of May 4/),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/Market data/)).toBeInTheDocument()
  })
})
