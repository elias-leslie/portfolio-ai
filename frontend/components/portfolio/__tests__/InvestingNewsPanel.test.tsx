import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { NewsBundle, NewsHealthResponse } from '@/lib/api/news'
import type { PositionWithValue } from '@/lib/api/portfolio'
import type { SentimentArticle, WatchlistItem } from '@/lib/api/watchlist'
import { InvestingNewsPanel } from '../InvestingNewsPanel'

const useNewsIntelligenceMock = vi.fn()
const useNewsHealthMock = vi.fn()
const useWatchlistNewsMock = vi.fn()

vi.mock('@/lib/hooks/useNews', () => ({
  useNewsIntelligence: () => useNewsIntelligenceMock(),
  useWatchlistNews: () => useWatchlistNewsMock(),
}))

vi.mock('@/lib/hooks/useNewsHealth', () => ({
  useNewsHealth: () => useNewsHealthMock(),
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
    isMaterialEvent: false,
    sentiment: {
      score: 0,
      label: 'neutral',
      confidence: 0.8,
      model: 'test',
    },
    contentHash: 'article-default',
    qualityPrediction: true,
    qualityConfidence: 0.8,
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

function buildNewsHealth(
  overrides: Partial<NewsHealthResponse> = {},
): NewsHealthResponse {
  return {
    status: 'healthy',
    message: 'News pipeline healthy.',
    finbertAvailable: true,
    qualityModelAvailable: true,
    qualityScoringMode: 'model',
    marketLastRefreshedAt: '2026-04-24T12:00:00Z',
    watchlistLastRefreshedAt: '2026-04-24T12:00:00Z',
    latestRefreshedAt: '2026-04-24T12:00:00Z',
    latestRefreshAgeHours: 1,
    fallbackHeadlines24H: 0,
    headlines24H: 12,
    cacheTtlHours: 6,
    lookbackWindowHours: 24,
    fallbackRate24H: 0,
    fallbackAvgLatencyMs24H: null,
    fallbackP95LatencyMs24H: null,
    fallbackLastEventAt: null,
    sentimentRescored24H: 0,
    vendors: {},
    ...overrides,
  }
}

describe('InvestingNewsPanel', () => {
  beforeEach(() => {
    useNewsIntelligenceMock.mockReset()
    useNewsHealthMock.mockReset()
    useWatchlistNewsMock.mockReset()
    useNewsHealthMock.mockReturnValue({
      data: buildNewsHealth(),
    })
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
    useWatchlistNewsMock.mockReturnValue({
      data: {
        accountId: 'default',
        items: [],
      },
    })
  })

  it('keeps holdings and watchlist signals while deduping and tightening market context headlines', () => {
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
          buildArticle({
            headline:
              "Fed Chair Jerome Powell's 6-Word Warning to Wall Street Still Holds True More Than 6 Months Later",
            summary: null,
            qualityPrediction: false,
            qualityConfidence: 0.56,
            contentHash: 'article-powell-commentary',
          }),
          buildArticle({
            headline:
              "Software stocks are plunging. Why that's a warning sign for the entire market",
            summary:
              'A sharp drawdown in software leadership can signal narrower breadth and weaker risk appetite across the broader market.',
            source: 'MarketWatch',
            contentHash: 'article-software-risk',
          }),
          buildArticle({
            headline:
              "Software stocks are plunging. Why that's a warning sign for the entire market - Yahoo Finance",
            summary:
              'A sharp drawdown in software leadership can signal narrower breadth and weaker risk appetite across the broader market.',
            source: 'Yahoo Finance',
            contentHash: 'article-software-risk-yf',
          }),
          buildArticle({
            headline: 'High-Yield REITs I Would Trust For Retirement Income',
            summary: 'Income listicle.',
            source: 'Seeking Alpha',
            qualityPrediction: false,
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

    expect(
      screen.getByRole('heading', { name: 'Holdings' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Watchlist' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Market Context' }),
    ).toBeInTheDocument()

    expect(
      screen.getByText('VTI keeps attracting broad market inflows'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('NVDA expands data-center backlog'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Software stocks are plunging. Why that's a warning sign for the entire market",
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Sector Leadership')).toBeInTheDocument()
    expect(
      screen.getByText(/market leadership is broadening or narrowing/i),
    ).toBeInTheDocument()

    expect(
      screen.queryByText(
        "Fed Chair Jerome Powell's 6-Word Warning to Wall Street Still Holds True More Than 6 Months Later",
      ),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        'High-Yield REITs I Would Trust For Retirement Income',
      ),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        "Software stocks are plunging. Why that's a warning sign for the entire market - Yahoo Finance",
      ),
    ).not.toBeInTheDocument()
    expect(screen.getByText('News review audit')).toBeInTheDocument()
    expect(screen.getByText(/Reviewed 6 headlines/)).toBeInTheDocument()
    expect(screen.getByText(/shown 3/)).toBeInTheDocument()
  })

  it('shows the quiet-state copy when only generic or irrelevant market noise is available', () => {
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
            headline:
              "Rubrik's Growth Engines Are Working, But 18% Dilution Risk Weighs On The Upside",
            summary: 'Single-name analysis.',
            source: 'Seeking Alpha',
            qualityPrediction: false,
            contentHash: 'article-rbrk',
          }),
          buildArticle({
            headline:
              'Will AI start going rogue? The chorus of warnings is getting louder.',
            summary: 'Technology culture feature.',
            source: 'MarketWatch',
            qualityPrediction: false,
            contentHash: 'article-ai',
          }),
        ],
      } satisfies NewsBundle,
    })

    render(<InvestingNewsPanel positions={[]} watchlistItems={[]} />)

    expect(
      screen.getByText(
        'Reviewed 2 headlines; none passed the decision-useful filter.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('News review audit')).toBeInTheDocument()
    expect(screen.getByText(/suppressed 2/)).toBeInTheDocument()
    expect(screen.getByText(/Generic market noise:/)).toBeInTheDocument()
    expect(screen.queryByText('Market Context')).not.toBeInTheDocument()
    expect(
      screen.queryByText(
        "Rubrik's Growth Engines Are Working, But 18% Dilution Risk Weighs On The Upside",
      ),
    ).not.toBeInTheDocument()
  })

  it('distinguishes no ingested news from suppressed news', () => {
    render(<InvestingNewsPanel positions={[]} watchlistItems={[]} />)

    expect(
      screen.getByText('No ingested portfolio news reached this panel.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Reviewed 0 headlines/)).toBeInTheDocument()
  })

  it('does not show empty-news facts while portfolio inputs are still loading', () => {
    render(
      <InvestingNewsPanel positions={[]} watchlistItems={[]} isInputLoading />,
    )

    expect(
      screen.getByText('Loading portfolio and watchlist news context.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('No ingested portfolio news reached this panel.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/Reviewed 0 headlines/)).not.toBeInTheDocument()
  })

  it('shows source-disabled state when no decision-useful news is available', () => {
    useNewsHealthMock.mockReturnValue({
      data: buildNewsHealth({
        status: 'degraded',
        message: 'Some news sources are disabled.',
        vendors: {
          polygon: {
            configured: false,
            enabled: false,
            active: false,
            lastAttemptAt: null,
            lastSuccessAt: null,
            lastErrorAt: null,
            lastError: null,
            articlesLastFetch: 0,
            articlesLast24H: 0,
            lastArticleAt: null,
            notes: null,
            reason: 'missing credentials',
          },
        },
      }),
    })

    render(<InvestingNewsPanel positions={[]} watchlistItems={[]} />)

    expect(
      screen.getByText('1 news source disabled or unconfigured'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Some news sources are disabled.'),
    ).toBeInTheDocument()
  })

  it('shows stale source state when refresh age explains quiet news', () => {
    useNewsHealthMock.mockReturnValue({
      data: buildNewsHealth({
        status: 'down',
        message: 'No fresh news in 24h.',
        latestRefreshAgeHours: 14,
        cacheTtlHours: 6,
      }),
    })

    render(<InvestingNewsPanel positions={[]} watchlistItems={[]} />)

    expect(
      screen.getByText('Latest refresh 14.0h old; expected every 6.0h'),
    ).toBeInTheDocument()
    expect(screen.getByText('No fresh news in 24h.')).toBeInTheDocument()
  })

  it('picks the best symbol article instead of only checking the first recent headline', () => {
    render(
      <InvestingNewsPanel
        positions={[buildPosition({ symbol: 'AMZN' })]}
        watchlistItems={[
          buildWatchlistItem({
            symbol: 'AMZN',
            signalStrength: 60,
            recentNews: {
              articles: [
                buildArticle({
                  symbol: 'AMZN',
                  headline: 'Amazon stock is one of 5 names to watch this week',
                  summary: 'Generic commentary.',
                  source: 'Seeking Alpha',
                  qualityPrediction: false,
                  qualityConfidence: 0.3,
                  decisionValueScore: 0.0,
                  decisionValueLabel: 'low',
                  decisionValueReason:
                    'Commentary-heavy source with weaker decision value.',
                  contentHash: 'amzn-generic',
                }),
                buildArticle({
                  symbol: 'AMZN',
                  headline: 'Amazon expands same-day delivery footprint again',
                  summary:
                    'The company expanded same-day delivery coverage into more markets, a direct operating update for the held position.',
                  source: 'Reuters',
                  qualityPrediction: true,
                  qualityConfidence: 0.84,
                  decisionValueScore: 0.78,
                  decisionValueLabel: 'high',
                  decisionValueReason:
                    'High-impact company event with direct fundamental implications.',
                  contentHash: 'amzn-real',
                }),
              ],
            },
          }),
        ]}
      />,
    )

    expect(
      screen.getByText('Amazon expands same-day delivery footprint again'),
    ).toBeInTheDocument()
    expect(
      screen.queryByText('Amazon stock is one of 5 names to watch this week'),
    ).not.toBeInTheDocument()
  })
})
