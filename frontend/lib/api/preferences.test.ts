import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchPreferences,
  getWatchlistRefreshMinutes,
  updatePreferences,
} from './preferences'

describe('preferences api', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('requests preferences without a trailing slash', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        risk_tolerance: 5,
        allow_long: true,
        allow_short: false,
        allow_options: false,
        allow_crypto: false,
        allow_futures: false,
        max_position_size_pct: 20,
        default_refresh_minutes: 15,
        watchlist_refresh_override: null,
        portfolio_refresh_override: null,
        news_refresh_override: null,
        news_lookback_hours: 24,
        news_max_articles: 10,
        frontend_poll_interval: 30,
        watchlist_refresh_minutes: 15,
        watchlist_auto_expand: false,
        watchlist_price_weight: 50,
        watchlist_technical_weight: 50,
        display_timezone: 'America/New_York',
        watchlist_show_news: true,
        thesis_generation_enabled: false,
        auto_remove_on_invalidation: true,
        auto_trim_enabled: true,
        scheduled_jenny_operator_enabled: false,
        scheduled_ml_labeling_enabled: false,
        scheduled_strategy_research_enabled: false,
      }),
    } as unknown as Response)

    await fetchPreferences()

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/preferences',
      expect.objectContaining({
        method: 'GET',
      }),
    )
  })

  it('updates preferences without a trailing slash', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        risk_tolerance: 7,
        thesis_generation_enabled: true,
        auto_remove_on_invalidation: false,
        auto_trim_enabled: true,
        scheduled_jenny_operator_enabled: false,
        scheduled_ml_labeling_enabled: false,
        scheduled_strategy_research_enabled: false,
      }),
    } as unknown as Response)

    await updatePreferences({
      riskTolerance: 7,
      thesisGenerationEnabled: true,
      autoRemoveOnInvalidation: false,
    })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/preferences',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          risk_tolerance: 7,
          thesis_generation_enabled: true,
          auto_remove_on_invalidation: false,
        }),
      }),
    )
  })

  it('prefers the watchlist refresh override when resolving watchlist polling', () => {
    expect(
      getWatchlistRefreshMinutes({
        defaultRefreshMinutes: 15,
        watchlistRefreshOverride: 3,
        watchlistRefreshMinutes: 30,
      }),
    ).toBe(15)
  })

  it('falls back to the shared default refresh interval before the legacy field', () => {
    expect(
      getWatchlistRefreshMinutes({
        defaultRefreshMinutes: 12,
        watchlistRefreshOverride: null,
        watchlistRefreshMinutes: 30,
      }),
    ).toBe(15)
  })

  it('returns 15 when preferences is null', () => {
    expect(getWatchlistRefreshMinutes(null)).toBe(15)
  })

  it('returns 15 when preferences is undefined', () => {
    expect(getWatchlistRefreshMinutes()).toBe(15)
  })

  it('falls back to legacy watchlistRefreshMinutes when both overrides are null', () => {
    expect(
      getWatchlistRefreshMinutes({
        defaultRefreshMinutes: 0,
        watchlistRefreshOverride: null,
        watchlistRefreshMinutes: 25,
      }),
    ).toBe(25)
  })
})
