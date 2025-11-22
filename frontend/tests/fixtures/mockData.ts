/**
 * Mock data utilities for testing
 */

export interface MockWatchlistItem {
  id: string
  symbol: string
  account_id: string
  created_at: string
  updated_at: string
  score: {
    overall: number
    price: { score: number; stale: boolean }
    technical: { score: number; stale: boolean }
  }
  signal_type?: string | null
  signal_strength?: number | null
}

export interface MockPortfolioPosition {
  id: string
  account_id: string
  symbol: string
  shares: number
  cost_basis: number
  created_at: string
  updated_at: string
}

export interface MockNewsArticle {
  id: string
  ticker: string
  headline: string
  summary: string
  url: string
  published_at: string
  source: string
  sentiment?: {
    label: string
    score: number
    confidence: number
  }
}

export interface MockIdea {
  id: string
  agent_type: string
  symbol: string
  entry_price: number
  stop_loss: number
  profit_target: number
  rationale: string
  created_at: string
}

/**
 * Create mock watchlist item with defaults
 */
export function mockWatchlistItem(overrides?: Partial<MockWatchlistItem>): MockWatchlistItem {
  return {
    id: 'test-watchlist-id',
    symbol: 'AAPL',
    account_id: 'default',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    score: {
      overall: 75.0,
      price: { score: 80.0, stale: false },
      technical: { score: 70.0, stale: false },
    },
    signal_type: 'BUY',
    signal_strength: 8,
    ...overrides,
  }
}

/**
 * Create mock portfolio position with defaults
 */
export function mockPortfolioPosition(
  overrides?: Partial<MockPortfolioPosition>
): MockPortfolioPosition {
  return {
    id: 'test-position-id',
    account_id: 'default',
    symbol: 'AAPL',
    shares: 100,
    cost_basis: 150.0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create mock news article with defaults
 */
export function mockNewsArticle(overrides?: Partial<MockNewsArticle>): MockNewsArticle {
  return {
    id: 'test-news-id',
    ticker: 'AAPL',
    headline: 'Test News Headline',
    summary: 'This is a test news article summary.',
    url: 'https://example.com/news',
    published_at: new Date().toISOString(),
    source: 'Test Source',
    sentiment: {
      label: 'positive',
      score: 0.8,
      confidence: 0.9,
    },
    ...overrides,
  }
}

/**
 * Create mock idea with defaults
 */
export function mockIdea(overrides?: Partial<MockIdea>): MockIdea {
  return {
    id: 'test-idea-id',
    agent_type: 'DiscoveryAgent',
    symbol: 'AAPL',
    entry_price: 150.0,
    stop_loss: 145.0,
    profit_target: 165.0,
    rationale: 'Strong technical breakout with volume confirmation',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create mock API response
 */
export function mockApiResponse<T>(data: T, overrides?: { status?: number; statusText?: string }) {
  return {
    ok: overrides?.status ? overrides.status < 400 : true,
    status: overrides?.status || 200,
    statusText: overrides?.statusText || 'OK',
    json: async () => data,
    text: async () => JSON.stringify(data),
  }
}
