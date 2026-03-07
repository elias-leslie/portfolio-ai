import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchPreferences, updatePreferences } from './preferences'

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
      }),
    }) as unknown as typeof fetch

    await fetchPreferences()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/preferences',
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
      }),
    }) as unknown as typeof fetch

    await updatePreferences({ riskTolerance: 7 })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/preferences',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ risk_tolerance: 7 }),
      }),
    )
  })
})
