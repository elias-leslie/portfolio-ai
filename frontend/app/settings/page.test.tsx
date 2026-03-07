import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsPage from './page'

const mockRetry = vi.fn()

vi.mock('./useSettingsState', () => ({
  useSettingsState: vi.fn(() => ({
    riskTolerance: 5,
    allowLong: true,
    allowShort: false,
    allowOptions: false,
    allowCrypto: false,
    allowFutures: false,
    maxPositionSizePct: '20',
    displayTimezone: 'America/New_York',
    defaultRefreshMinutes: 15,
    watchlistOverride: null,
    newsOverride: null,
    newsLookbackHours: 24,
    newsMaxArticles: 10,
    showNews: true,
    autoExpand: false,
    scoreWeights: { price: 34, technical: 33, fundamental: 33 },
    technicalSubWeights: { rsi14: 34, trend: 33, macd: 33 },
    fundamentalSubWeights: {
      valuation: 25,
      growth: 25,
      health: 25,
      sentiment: 25,
    },
    setRiskTolerance: vi.fn(),
    setAllowLong: vi.fn(),
    setAllowShort: vi.fn(),
    setAllowOptions: vi.fn(),
    setAllowCrypto: vi.fn(),
    setAllowFutures: vi.fn(),
    setMaxPositionSizePct: vi.fn(),
    setDisplayTimezone: vi.fn(),
    setDefaultRefreshMinutes: vi.fn(),
    setWatchlistOverride: vi.fn(),
    setNewsOverride: vi.fn(),
    setNewsLookbackHours: vi.fn(),
    setNewsMaxArticles: vi.fn(),
    setShowNews: vi.fn(),
    setAutoExpand: vi.fn(),
    setScoreWeights: vi.fn(),
    setTechnicalSubWeights: vi.fn(),
    setFundamentalSubWeights: vi.fn(),
    hasChanges: false,
    changeCount: 0,
    tradingSummary: 'Risk 5/10',
    displaySummary: 'ET',
    watchlistSummary: 'Refresh 15m',
    handleSaveAll: vi.fn(),
    handleResetAll: vi.fn(),
    handleProfileLoad: vi.fn(),
    getCurrentPreferences: vi.fn(),
    preferences: null,
    isLoading: false,
    isPending: false,
    loadError: new Error('Preferences service unavailable'),
    retryLoad: mockRetry,
  })),
}))

describe('SettingsPage', () => {
  it('renders a useful error state when preferences fail to load', () => {
    render(<SettingsPage />)

    expect(screen.getByText('Error Loading Settings')).toBeInTheDocument()
    expect(
      screen.getByText('Preferences service unavailable'),
    ).toBeInTheDocument()
  })

  it('retries loading settings from the error state', () => {
    render(<SettingsPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Retry Loading' }))

    expect(mockRetry).toHaveBeenCalledTimes(1)
  })
})
