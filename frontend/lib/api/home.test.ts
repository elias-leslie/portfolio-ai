import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchHomeActionQueue, fetchHomeTodayBrief } from './home'

describe('home api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('requests the home action queue endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        generated_at: '2026-03-10T00:00:00Z',
        actions: [],
        summary: 'Nothing urgent is queued.',
      }),
    }) as unknown as typeof fetch

    await fetchHomeActionQueue()

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/home/action-queue',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('requests the home today brief endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        generated_at: '2026-03-10T00:00:00Z',
        cache_ttl_seconds: 300,
        as_of: {
          household: '2026-03-10T00:00:00Z',
          portfolio: '2026-03-10T00:00:00Z',
          market: '2026-03-10T00:00:00Z',
          news: '2026-03-10T00:00:00Z',
        },
        market_status: 'open',
        brief: {
          headline: 'Markets firm as rates cool',
          summary: 'Rates eased and breadth improved.',
          stance: 'constructive',
          confidence: 'medium',
          why_now: 'Treasury pressure relaxed.',
          bullets: [],
        },
        catalysts: [],
        impacts: [],
        market_metrics: [],
        sources: [],
        staleness_notes: [],
      }),
    }) as unknown as typeof fetch

    await fetchHomeTodayBrief()

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/home/today-brief',
      expect.objectContaining({ method: 'GET' }),
    )
  })
})
