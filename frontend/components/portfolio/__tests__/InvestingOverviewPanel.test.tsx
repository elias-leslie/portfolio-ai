import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NewsBundle } from '@/lib/api/news'
import type { PositionWithValue } from '@/lib/api/portfolio'
import type { WatchlistItem } from '@/lib/api/watchlist'
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

vi.mock('@/components/market/SentimentTrendChart', () => ({
  SentimentTrendChart: () => <div>Sentiment Trend Chart</div>,
}))

vi.mock('@/components/market/IndicatorsTrendChart', () => ({
  IndicatorsTrendChart: () => <div>Indicators Trend Chart</div>,
}))

vi.mock('@/components/market/SectorPerformanceChart', () => ({
  SectorPerformanceChart: () => <div>Sector Performance Chart</div>,
}))

const heldPositions: PositionWithValue[] = [
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
]

const watchlistItems: WatchlistItem[] = [
  {
    id: 'watch-1',
    symbol: 'VTI',
    createdAt: '2026-04-09T12:00:00Z',
    updatedAt: '2026-04-09T12:00:00Z',
    scoreAlert: true,
    signalStrength: 8,
    recentNews: {
      articles: [
        {
          symbol: 'VTI',
          headline: 'VTI rallies as broad market momentum improves',
          fetchedAt: '2026-04-09T12:00:00Z',
          publishedAt: '2026-04-09T12:00:00Z',
          source: 'Reuters',
          contentHash: 'held-article',
          sentiment: {
            score: 0.7,
            label: 'positive',
            confidence: 0.9,
            model: 'test',
          },
          actionableInsight: 'Held position has supportive price action today.',
        },
      ],
      summary: {
        score: 0.7,
        scoreChange: 0.2,
        positiveCount: 5,
        neutralCount: 2,
        negativeCount: 1,
        articleCount: 8,
        modelBreakdown: {},
      },
    },
  } as WatchlistItem,
]

const marketNews: NewsBundle = {
  symbol: 'MARKET',
  summary: {
    score: 0.1,
    scoreChange: 0.05,
    positiveCount: 10,
    neutralCount: 8,
    negativeCount: 4,
    articleCount: 22,
    modelBreakdown: {},
  },
  articles: [
    {
      symbol: 'MARKET',
      headline: 'Stocks edge higher before inflation data',
      fetchedAt: '2026-04-09T11:00:00Z',
      publishedAt: '2026-04-09T11:00:00Z',
      source: 'Bloomberg',
      url: 'https://example.com/market-story',
      contentHash: 'market-article',
      sentiment: {
        score: 0.2,
        label: 'neutral',
        confidence: 0.8,
        model: 'test',
      },
      impactSummary: 'Macro data is likely to drive the next market move.',
    },
  ],
}

describe('InvestingOverviewPanel', () => {
  beforeEach(() => {
    window.localStorage.clear()
    useMarketIntelligenceMock.mockReturnValue({
      data: {
        narrative:
          'Risk appetite improved, but defensive leadership still matters.',
        fearGreed: {
          score: 72,
          label: 'Greed',
        },
        indicators: {
          sp500: { changePct: 0.4 },
          vix: { value: 14.2 },
          tnx: { value: 4.31 },
        },
        lastUpdated: '2026-04-09T12:00:00Z',
      },
      isLoading: false,
    })
    useNewsIntelligenceMock.mockReturnValue({
      data: marketNews,
    })
  })

  it('shows the compact market pulse summary and relevant headlines', () => {
    render(
      <InvestingOverviewPanel
        watchlistItems={watchlistItems}
        positions={heldPositions}
      />,
    )

    expect(screen.getByText('Market Pulse')).toBeInTheDocument()
    expect(screen.getByText('Greed (72)')).toBeInTheDocument()
    expect(screen.getByText('+0.4%')).toBeInTheDocument()
    expect(screen.getByText('14.2')).toBeInTheDocument()
    expect(
      screen.getByText('Risk appetite improved, but defensive leadership still matters.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('VTI rallies as broad market momentum improves'),
    ).toBeInTheDocument()
    expect(screen.getByText('Held · VTI')).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: /Stocks edge higher before inflation data/i,
      }),
    ).toBeInTheDocument()
  })

  it('persists the market context collapse state', async () => {
    const user = userEvent.setup()

    render(
      <InvestingOverviewPanel
        watchlistItems={watchlistItems}
        positions={heldPositions}
      />,
    )

    expect(screen.getByText('Sentiment Trend Chart')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /toggle market context/i }),
    )

    expect(
      screen.queryByText('Sentiment Trend Chart'),
    ).not.toBeInTheDocument()
    expect(
      window.localStorage.getItem('portfolio-ai:investing-market-context-open'),
    ).toBe('false')
  })
})
