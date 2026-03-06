import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchProfiles } from './settings-profiles'

describe('settings profiles api', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('camelizes profile payloads from the backend', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue([
        {
          id: 1,
          user_id: 1,
          name: 'Default',
          description: 'Primary profile',
          profile_data: { display_timezone: 'America/New_York' },
          is_active: true,
          created_at: '2026-03-06T10:00:00Z',
          updated_at: '2026-03-06T11:00:00Z',
        },
      ]),
    }) as unknown as typeof fetch

    const result = await fetchProfiles()

    expect(result).toEqual([
      {
        id: 1,
        userId: 1,
        name: 'Default',
        description: 'Primary profile',
        profileData: { displayTimezone: 'America/New_York' },
        isActive: true,
        createdAt: '2026-03-06T10:00:00Z',
        updatedAt: '2026-03-06T11:00:00Z',
      },
    ])
  })
})
