import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchDetailedHealth } from './health'

describe('health api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('requests the detailed health endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        status: 'healthy',
        timestamp: '2026-03-10T00:00:00Z',
        version: '1.0.0',
        uptime_seconds: 42,
        checks: {},
        sources: {},
        services: {},
        api_quotas: [],
        recent_remediations: [],
      }),
    }) as unknown as typeof fetch

    await fetchDetailedHealth()

    expect(global.fetch).toHaveBeenCalledWith(
      '/health/detailed',
      expect.objectContaining({ method: 'GET' }),
    )
  })
})
