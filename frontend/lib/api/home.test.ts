import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchHomeActionQueue, refreshToday } from './home'

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

  it('posts to the Today refresh endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        refreshed_at: '2026-06-04T13:30:00Z',
        quote_symbols_requested: 10,
        quote_symbols_refreshed: 10,
        quote_symbols_failed: [],
        macro_snapshot_date: '2026-06-04',
        macro_deployment_score: 64.1,
        cache_entries_invalidated: 4,
      }),
    }) as unknown as typeof fetch

    await refreshToday()

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/home/refresh-today',
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
