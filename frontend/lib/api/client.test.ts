import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { del, get, post, put } from './client'

describe('api client helpers', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('converts request bodies to snake_case and responses to camelCase', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        default_refresh_minutes: 15,
        show_news: true,
      }),
    }) as unknown as typeof fetch

    const result = await post('/api/preferences', {
      defaultRefreshMinutes: 15,
      showNews: true,
    })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/preferences',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          default_refresh_minutes: 15,
          show_news: true,
        }),
      }),
    )
    expect(result).toEqual({
      defaultRefreshMinutes: 15,
      showNews: true,
    })
  })

  it('supports PUT requests through the shared client', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        updated_at: '2026-03-06T12:00:00Z',
      }),
    }) as unknown as typeof fetch

    const result = await put('/api/preferences', {
      displayTimezone: 'America/New_York',
    })

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/preferences',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          display_timezone: 'America/New_York',
        }),
      }),
    )
    expect(result).toEqual({ updatedAt: '2026-03-06T12:00:00Z' })
  })

  it('returns undefined for 204 responses', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: new Headers(),
    }) as unknown as typeof fetch

    const result = await del<void>('/api/preferences')

    expect(result).toBeUndefined()
  })

  it('retries safe GET requests after transient failures', async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error('temporary network failure'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: vi.fn().mockResolvedValue({ ok: true }),
      }) as unknown as typeof fetch

    const result = await get<{ ok: boolean }>('/api/preferences')

    expect(global.fetch).toHaveBeenCalledTimes(2)
    expect(result).toEqual({ ok: true })
  })

  it('does not retry unsafe POST requests after transient failures', async () => {
    global.fetch = vi
      .fn()
      .mockRejectedValue(new Error('temporary network failure')) as unknown as typeof fetch

    await expect(
      post('/api/preferences', {
        defaultRefreshMinutes: 15,
      }),
    ).rejects.toThrow('temporary network failure')

    expect(global.fetch).toHaveBeenCalledTimes(1)
  })
})
