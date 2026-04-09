import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NewsBundle } from '@/lib/api/news'
import type {
  PortfolioAnalytics,
  PortfolioResponse,
} from '@/lib/api/portfolio'
import { InvestingOverviewPanel } from '../InvestingOverviewPanel'

const useMarketIntelligenceMock = vi.fn()
const useNewsIntelligenceMock = vi.fn()

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketIntelligence: () => useMarketIntelligenceMock(),
}))

vi.mock('@/lib/hooks/useNews', () => ({
  useNewsIntelligence: () => useNewsIntelligenceMock(),
}))

vi.mock('@/components/market/MarketStatusBadge', () => ({
  MarketStatusBadge: () => <div>Market Open</div>,
}))

const portfolio: PortfolioResponse = {
  positions: [
    {
      id: 'position-1',
      accountId: 'acct-1',
      symbol: 'VTI',
      shares: 10,
      costBasis: 200,
      positionType: 'long',
      createdAt: '2026-04-09T12:00:00Z',
      updatedAt: '2026-04-09T12:00:00Z',
      currentPrice: 225,
      currentValue: 2250,
      gain: 250,
      gainPct: 12.5,
    },
  ],
  cashBalanceTotal: 0,
  totalValue: 2250,
  totalCostBasis: 2000,
  totalGain: 250,
  totalGainPct: 12.5,
}

const analytics: PortfolioAnalytics = {
  portfolioValue: {
    totalValue: 2250,
    totalCostBasis: 2000,
    totalGain: 250,
    totalGainPct: 12.5,
  },
  cashBalanceTotal: 0,
  cashInclusiveTotalValue: 2250,
  portfolioBeta: 1,
  portfolioVolatility: 12,
  sharpeRatio: 1.1,
  concentration: {
    topHoldingPct: 18,
    top3Pct: 40,
    top10Pct: 40,
    herfindahlIndex: 0.11,
  },
  sectorExposure: { Technology: 55, Financials: 20 },
  riskProfile: {
    level: 'Moderate',
    score: 68,
    factors: {},
  },
  diversificationScore: {
    score: 82,
    level: 'Strong',
    numHoldings: 5,
    numSectors: 4,
  },
  topPerformers: [],
  bottomPerformers: [],
  numPositions: 1,
  numSymbols: 5,
}

const marketNews: NewsBundle = {
  symbol: 'MARKET',
  summary: {
    score: 0.3,
    scoreChange: 0.05,
    positiveCount: 10,
    neutralCount: 8,
    negativeCount: 4,
    articleCount: 22,
    modelBreakdown: {},
  },
  articles: [],
}

describe('InvestingOverviewPanel', () => {
  beforeEach(() => {
    useMarketIntelligenceMock.mockReturnValue({
      data: {
        fearGreed: {
          score: 72,
          label: 'Greed',
          scoreChange: 0,
          signalCount: 5,
          lastUpdated: '2026-04-09T12:00:00Z',
          isStale: false,
          ageDays: 0,
          trend: 'up',
          trendChange: 8,
        },
        indicators: {
          sp500: { value: 6824.66, changePct: 0.4 },
          vix: { value: 14.2 },
          tnx: { value: 4.31 },
        },
      },
    })
    useNewsIntelligenceMock.mockReturnValue({
      data: marketNews,
    })
  })

  it('shows the unified investing overview strip instead of the old watchlist summary card', () => {
    render(
      <InvestingOverviewPanel
        portfolio={portfolio}
        analytics={analytics}
        accountsCount={2}
      />,
    )

    expect(screen.getByText('At a glance')).toBeInTheDocument()
    expect(screen.getByText('Market Open')).toBeInTheDocument()
    expect(screen.getByText('Portfolio Value')).toBeInTheDocument()
    expect(screen.getByText('$2,250')).toBeInTheDocument()
    expect(screen.getByText('Total Gain')).toBeInTheDocument()
    expect(screen.getByText('+12.50%')).toBeInTheDocument()
    expect(screen.getByText('Portfolio Health')).toBeInTheDocument()
    expect(screen.getByText('Well spread')).toBeInTheDocument()
    expect(screen.getByText('Market Mood')).toBeInTheDocument()
    expect(screen.getByText('Greed')).toBeInTheDocument()
    expect(screen.getByText('S&P 500')).toBeInTheDocument()
    expect(screen.getByText('+0.40%')).toBeInTheDocument()
    expect(screen.getByText('Volatility')).toBeInTheDocument()
    expect(screen.getByText('14.2')).toBeInTheDocument()
    expect(screen.getByText('10-Year Rate')).toBeInTheDocument()
    expect(screen.getByText('4.31%')).toBeInTheDocument()
    expect(screen.getByText('News Tone')).toBeInTheDocument()
    expect(screen.getByText('Constructive')).toBeInTheDocument()
    expect(screen.queryByText('Watchlist')).not.toBeInTheDocument()
  })
})
