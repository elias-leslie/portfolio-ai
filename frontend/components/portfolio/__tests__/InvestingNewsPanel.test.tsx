import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NewsBundle } from '@/lib/api/news'
import type { PositionWithValue } from '@/lib/api/portfolio'
import type { SentimentArticle, WatchlistItem } from '@/lib/api/watchlist'
import { InvestingNewsPanel } from '../InvestingNewsPanel'

const useNewsIntelligenceMock = vi.fn()

vi.mock('@/lib/hooks/useNews', () => ({
  useNewsIntelligence: () => useNewsIntelligenceMock(),
}))

function buildArticle(
  overrides: Partial<SentimentArticle> = {},
): SentimentArticle {
  return {
    symbol: '__MARKET__',
    headline: 'Fed minutes reinforce higher-for-longer rate outlook',
    summary: 'Rates and liquidity remain the key market driver.',
    source: 'MarketWatch',
    publishedAt: '2026-04-11T11:30:00Z',
    fetchedAt: '2026-04-11T11:35:00Z',
    sentiment: {
      score: 0,
      label: 'neutral',
      confidence: 0.8,
      model: 'test',
    },
    contentHash: 'article-default',
    ...overrides,
  }
}

function buildWatchlistItem(
  overrides: Partial<WatchlistItem> = {},
): WatchlistItem {
  return {
    id: 'watch-default',
    symbol: 'VTI',
    createdAt: '2026-04-11T10:00:00Z',
    updatedAt: '2026-04-11T10:00:00Z',
    recentNews: {
      articles: [],
    },
    ...overrides,
  }
}

function buildPosition(
  overrides: Partial<PositionWithValue> = {},
): PositionWithValue {
  return {
    id: 'position-default',
    accountId: 'acct-1',
    symbol: 'VTI',
    shares: 10,
    costBasis: 200,
    positionType: 'long',
    createdAt: '2026-04-11T10:00:00Z',
    updatedAt: '2026-04-11T10:00:00Z',
    currentPrice: 220,
    currentValue: 2200,
    gain: 200,
    gainPct: 10,
    ...overrides,
  }
}

describe('InvestingNewsPanel', () => {
  beforeEach(() => {
    useNewsIntelligenceMock.mockReset()
    useNewsIntelligenceMock.mockReturnValue({
      data: {
        symbol: '__MARKET__',
        summary: {
          score: 0,
          scoreChange: 0,
          positiveCount: 0,
          neutralCount: 0,
          negativeCount: 0,
          articleCount: 0,
          modelBreakdown: {},
        },
        articles: [],
      } satisfies NewsBundle,
    })
  })

  it('keeps held and watching news while filtering backdrop headlines to true macro context', () => {
    useNewsIntelligenceMock.mockReturnValue({
      data: {
        symbol: '__MARKET__',
        summary: {
          score: 0.1,
          scoreChange: 0,
          positiveCount: 2,
          neutralCount: 3,
          negativeCount: 1,
          articleCount: 6,
          modelBreakdown: {},
        },
        articles: [
          buildArticle(),
          buildArticle({
            headline: 'EMCOR Group: Solid Business That Is Fully Valued',
            summary: 'Single-name valuation note.',
            source: 'Seeking Alpha',
            contentHash: 'article-emcor',
          }),
          buildArticle({
            headline: 'High-Yield REITs I Would Trust For Retirement Income',
            summary: 'Income listicle.',
            source: 'Seeking Alpha',
            contentHash: 'article-reit',
          }),
        ],
      } satisfies NewsBundle,
    })

    render(
      <InvestingNewsPanel
        positions={[buildPosition({ symbol: 'VTI' })]}
        watchlistItems={[
          buildWatchlistItem({
            symbol: 'VTI',
            signalStrength: 70,
            recentNews: {
              articles: [
                buildArticle({
                  symbol: 'VTI',
                  headline: 'VTI keeps attracting broad market inflows',
                  summary: 'Held position context.',
                  source: 'Reuters',
                  contentHash: 'article-vti',
                }),
              ],
            },
          }),
          buildWatchlistItem({
            id: 'watch-nvda',
            symbol: 'NVDA',
            signalStrength: 55,
            recentNews: {
              articles: [
                buildArticle({
                  symbol: 'NVDA',
                  headline: 'NVDA expands data-center backlog',
                  summary: 'Watching position context.',
                  source: 'Bloomberg',
                  contentHash: 'article-nvda',
                }),
              ],
            },
          }),
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Held' })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Watching' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Backdrop' }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/^Market$/)).not.toBeInTheDocument()

    expect(
      screen.getByText('VTI keeps attracting broad market inflows'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('NVDA expands data-center backlog'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Fed minutes reinforce higher-for-longer rate outlook'),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('EMCOR Group: Solid Business That Is Fully Valued'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('High-Yield REITs I Would Trust For Retirement Income'),
    ).not.toBeInTheDocument()
  })

  it('shows the empty-state copy when only irrelevant leftover market noise is available', () => {
    useNewsIntelligenceMock.mockReturnValue({
      data: {
        symbol: '__MARKET__',
        summary: {
          score: 0,
          scoreChange: 0,
          positiveCount: 0,
          neutralCount: 2,
          negativeCount: 0,
          articleCount: 2,
          modelBreakdown: {},
        },
        articles: [
          buildArticle({
            headline: "Rubrik's Growth Engines Are Working, But 18% Dilution Risk Weighs On The Upside",
            summary: 'Single-name analysis.',
            source: 'Seeking Alpha',
            contentHash: 'article-rbrk',
          }),
          buildArticle({
            headline: 'Will AI start going rogue? The chorus of warnings is getting louder.',
            summary: 'Technology culture feature.',
            source: 'MarketWatch',
            contentHash: 'article-ai',
          }),
        ],
      } satisfies NewsBundle,
    })

    render(<InvestingNewsPanel positions={[]} watchlistItems={[]} />)

    expect(
      screen.getByText(
        'No relevant headlines yet. Refresh symbols or market data to repopulate this view.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Backdrop')).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        "Rubrik's Growth Engines Are Working, But 18% Dilution Risk Weighs On The Upside",
      ),
    ).not.toBeInTheDocument()
  })
})
