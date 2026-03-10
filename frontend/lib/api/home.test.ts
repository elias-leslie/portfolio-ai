import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchAutomationCenter, fetchHomeActionQueue } from './home'

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
      'http://localhost:8000/api/home/action-queue',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('requests the automation center endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: vi.fn().mockResolvedValue({
        generated_at: '2026-03-10T00:00:00Z',
        guardrails: [
          {
            key: 'thesis_generation_enabled',
            label: 'Thesis generation',
            value: 'Enabled',
            enabled: true,
            source: 'preferences',
            detail: 'Controls whether Jenny can auto-generate missing theses.',
          },
        ],
        recent_runs: [],
        warnings: [],
      }),
    }) as unknown as typeof fetch

    await fetchAutomationCenter()

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/home/automation-center',
      expect.objectContaining({ method: 'GET' }),
    )
  })
})
