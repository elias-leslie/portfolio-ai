import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { del, post, put } from './client'

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
        profile_data: { risk_tolerance: 5 },
        is_active: true,
      }),
    }) as unknown as typeof fetch

    const result = await post('/api/settings/profiles', {
      profileData: { riskTolerance: 5 },
      isActive: true,
    })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/settings/profiles',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          profile_data: { risk_tolerance: 5 },
          is_active: true,
        }),
      }),
    )
    expect(result).toEqual({
      profileData: { riskTolerance: 5 },
      isActive: true,
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

    const result = await put('/api/settings/profiles/1', {
      profileData: { displayTimezone: 'America/New_York' },
    })

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/settings/profiles/1',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          profile_data: { display_timezone: 'America/New_York' },
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

    const result = await del<void>('/api/settings/profiles/1')

    expect(result).toBeUndefined()
  })
})
